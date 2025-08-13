#!/usr/bin/env python3
import asyncio
import logging
import sys
import random
import threading
import queue
import time
import argparse
import os
from re import findall
from contextlib import suppress
from typing import Any, Optional
from enum import Enum
from bless import (
    BlessServer,
    BlessGATTCharacteristic,
    GATTCharacteristicProperties,
    GATTAttributePermissions,
)

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak import BleakClient, BleakScanner
from socket import gethostname
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Peer:
    def __init__(self, name: str, device: BLEDevice, rssi: int):
        self.name = name
        self.device = device
        self.rssi = rssi

    def __str__(self) -> str:
        return f"Peer(name={self.name}, device={self.device}, rssi={self.rssi}, addr={self.device.address})"

class ConnectedPeer(Peer):
    def __init__(self, peer: Peer, client: BleakClient):
        super().__init__(name=peer.name, device=peer.device, rssi=peer.rssi)
        self.client = client

class MESSAGE_TYPE(Enum):
    DATA = "DATA"
    RTS = "RTS"
    CTS = "CTS"

    @classmethod
    def is_message_type(cls, msg_type: str) -> bool:
        return msg_type == 'DATA' or msg_type == 'RTS' or msg_type == 'CTS'

class Message:
    def __init__(self, id: str, timestamp_ms: int, msg_type: MESSAGE_TYPE, data_content: str, size: int = 0, incoming: bool = True) -> None:
        self.id = id
        self.timestamp_ms = timestamp_ms
        self.msg_type = msg_type
        self.data_content = data_content
        self.size = size if size != 0 else len(self.__str__())
        self.incoming = incoming

    def __str__(self):
        message = f"[{self.id}][{self.msg_type.value}][{self.data_content}]"

        if self.msg_type == MESSAGE_TYPE.DATA and self.incoming is False:
            # insert padding
            remaining_size = self.size - len(message)
            if remaining_size > 0:
                padded_message = f"[{self.id}][{self.msg_type.value}][{self.data_content}" + '1' * remaining_size + "]"
                message = padded_message
            elif remaining_size < 0:
                pass
                # TODO: crop message?

        return message

class ThroughputTestPeer:
    def __init__(self, peer_name: str, test_duration: int = 30, num_runs: int = 3, 
                 delay_between_runs: int = 5, message_size: int = 100, range_id: str = "default",
                 inner_frame_time_us: float = 4.5):
        self.peer_name = peer_name
        self.device_name = f"PiChat-{self.peer_name}"
        
        # Test parameters
        self.test_duration = test_duration  # seconds per test run
        self.num_runs = num_runs
        self.delay_between_runs = delay_between_runs
        self.message_size = message_size
        self.range_id = range_id
        self.inner_frame_time_us = inner_frame_time_us  # Inner frame time in microseconds
        
        # UUIDs - same for all peers
        self.SERVICE_UUID = "A07498CA-AD5B-474E-940D-16F1FBE7E8CD"
        self.MESSAGE_CHAR_UUID = "87654321-4321-4321-4321-CBA987654321"
        self.STATUS_CHAR_UUID = "51FF12BB-3ED8-46E5-B4F9-D64E2FEC021B"
        
        # Server state
        self.server: Optional[BlessServer] = None
        
        # Message tracking
        self.outgoing_messages_count = 0
        self.incoming_messages_count = 0
        self.test_active = False
        self.experiment_active = True
        
        # RTS/CTS Protocol state
        self.clear_to_send = False
        self.should_send_ping = True  # This node wants to be sender initially
        
        self.incoming_message_processor_task: asyncio.Task[None] = asyncio.create_task(self.process_incoming_message_queue())
        self.outgoing_message_sender_thread: threading.Thread = threading.Thread(
                target=self.process_outgoing_messages_queue,
                daemon=True,
                name="OutgoingMessageSender"
            )
        self.event_loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()

        self.active_connections: dict[str, ConnectedPeer] = {}
        
        self.incoming_message_queue: asyncio.Queue[Message] = asyncio.Queue()
        self.outgoing_message_queue: queue.Queue[Message] = queue.Queue()
        
        self.trusted_pattern = "PiChat-"
        
        # Create range directory structure
        self.range_dir = os.path.join("ranges", str(self.range_id))
        os.makedirs(self.range_dir, exist_ok=True)
        
        # Buffered logging
        self.incoming_log_files: list[str] = []
        self.outgoing_log_files: list[str] = []
        self.incoming_log_filename = ""
        self.outgoing_log_filename = ""
        self.received_log_buffer: list[str] = []
        self.sent_log_buffer: list[str] = []
        self.buffer_size_limit = 1000
        
        print(f"🎯 Initialized peer: {self.device_name}")
        print(f"📂 Range directory: {self.range_dir}")
        print(f"⚡ Inner frame time: {self.inner_frame_time_us}μs")
        
    def is_trusted_peer(self, device_name: str) -> bool:
        """Check if device name matches trusted pattern and is not self"""
        if not device_name:
            return False
        return (device_name.startswith(self.trusted_pattern) and 
                device_name != self.device_name)

    def create_outgoing_message(self, msg_type: MESSAGE_TYPE = MESSAGE_TYPE.DATA, data_content: str="") -> Message:
        """Create a message with format: [M_ID][MSG_TYPE][DATA_CONTENT]"""
        msg_id = f"{self.peer_name}_M_{self.outgoing_messages_count}"

        creation_timestamp_ms = int(time.time() * 1000)
        return Message(msg_id, creation_timestamp_ms, msg_type, data_content, self.message_size, False)

    def is_own_message(self, message: Message) -> bool:
        """Check if a message was sent by this node"""
        return message.id.startswith(f"{self.peer_name}_")

    def create_ping_message(self) -> Message:
        """Create a PING data message"""
        return self.create_outgoing_message(msg_type=MESSAGE_TYPE.DATA, data_content="PING")

    def create_pong_message(self) -> Message:
        """Create a PONG data message"""
        return self.create_outgoing_message(msg_type=MESSAGE_TYPE.DATA, data_content="PONG")

    def parse_message(self, message: str, timestamp: int) -> Optional[Message]:
        """Parse message to extract message_id, msg_type, and data_content"""
        try:
            # Expect format: [M_PEERID_MSGID][MSG_TYPE][DATA_CONTENT]
            matches = findall(r'\[(\w*)\]', message)
            if len(matches) != 3:
                logger.error(f"Invalid message format: {message}")
                return None
            msg_id, msg_type, data_content = matches
            if not MESSAGE_TYPE.is_message_type(msg_type):
                logger.error(f"Unknown message type: {msg_type}")
                return None
            
            return Message(msg_id, timestamp, msg_type=MESSAGE_TYPE[msg_type], data_content=data_content, size=len(message), incoming=True)
        except Exception as e:
            logger.error(f"Error parsing message: {e}")
            return None

    def prepare_logs(self, run_number: int):
        """Setup the log filename for a specific run"""
        # Create new log filenames with run number in the range directory
        base_filename = f"throughput_test_{self.peer_name}_{int(time.time())}"
        self.incoming_log_filename = os.path.join(self.range_dir, f"{base_filename}_run_{run_number}_incoming.csv")
        self.outgoing_log_filename = os.path.join(self.range_dir, f"{base_filename}_run_{run_number}_outgoing.csv")

        self.incoming_log_files.append(self.incoming_log_filename)
        self.outgoing_log_files.append(self.outgoing_log_filename)

        # Clear the buffers for this run
        self.received_log_buffer = []
        self.sent_log_buffer = []

    def flush_buffer(self, buffer: list[str], log_filename: str):
        """Flush a message buffer to file"""
        if not buffer or not log_filename:
            return
        
        try:
            # Check if this is the first write (to add header)
            file_exists = os.path.exists(log_filename)
            
            with open(log_filename, 'a') as f:
                if not file_exists:
                    f.write("message_id,timestamp,message_length\n")

                f.writelines(buffer)

            logger.info(f"📝 Flushed {len(buffer)} log entries to {log_filename}")
            buffer.clear()
            
        except Exception as e:
            logger.error(f"Error flushing received log buffer: {e}")
    
    def add_to_log_buffer(self, log_line: str, to_received: bool = True):
        """Add a log line to a messages buffer and flush if buffer is full"""
        if to_received:
            buffer = self.received_log_buffer
            log_file = self.incoming_log_filename
        else:
            buffer = self.sent_log_buffer
            log_file = self.outgoing_log_filename
        buffer.append(log_line)

        should_flush = len(buffer) >= self.buffer_size_limit
        if should_flush:
            self.flush_buffer(buffer, log_file)

    def log_message(self, message: Message):
        """Log message details"""
        try:
            log_line = f"{message.id},{message.timestamp_ms},{message.size}\n"
            self.add_to_log_buffer(log_line, message.incoming)
            
        except Exception as e:
            logger.error(f"Error logging sent message: {e}")
    
    def handle_peer_message(self, characteristic: BlessGATTCharacteristic, value: bytearray) -> Any:
        """Handle incoming messages from clients"""
        try:
            message_decoded = value.decode('utf-8')
            receive_creation_timestamp_ms = int(time.time() * 1000)
            
            message = self.parse_message(message_decoded, receive_creation_timestamp_ms)
            if message is None:
                print(f"❌ Received a message we couldn't parse: {message_decoded}")
                return

            if not self.is_own_message(message):
                if self.got_control_message.is_set() and self.got_data_message.is_set():
                    self.incoming_message_queue.put_nowait(message)
                else:
                    if message.msg_type == MESSAGE_TYPE.CTS or message.msg_type == MESSAGE_TYPE.RTS:
                        # TODO: why does the message queue keep getting items after it was emptied from the previous run?
                        if not self.got_control_message.is_set():
                            self.got_control_message.set()

                    elif message.msg_type == MESSAGE_TYPE.DATA:
                        if not self.got_data_message.is_set():
                            self.got_data_message.set()
                    
                    self.process_message(message) # process first control or data messages immediately for the control loop
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            traceback.print_exc()
    
    def read_request(self, characteristic: BlessGATTCharacteristic) -> bytearray:
        """Handle read requests from clients"""
        try:
            if characteristic.uuid.lower() == self.STATUS_CHAR_UUID.lower():
                # Return status information as JSON
                status_info: dict[str, str|int] = {
                    "device_name": self.device_name,
                    "test_active": self.test_active,
                    "experiment_active": self.experiment_active,
                    "should_send_ping": self.should_send_ping,
                    "clear_to_send": self.clear_to_send,
                    "message_count": self.outgoing_messages_count
                }
                status_json = str(status_info).encode('utf-8')
                return bytearray(status_json)
            else:
                print(f"⚠️ Read request for unknown characteristic: {characteristic.uuid}")
                return bytearray(b"UNKNOWN")
        except Exception as e:
            logger.error(f"Error handling read request: {e}")
            return bytearray(b"ERROR")

    def create_cts_message(self) -> Message:
        """Create a CTS (Clear To Send) message"""
        return self.create_outgoing_message(msg_type=MESSAGE_TYPE.CTS)

    def send_cts(self):
        """Send a CTS response to all connected peers"""
        try:
            cts_message = self.create_cts_message()
            self.outgoing_message_queue.put_nowait(cts_message)
        except Exception as e:
            logger.error(f"Error queueing CTS response: {e}")
    
    def create_rts_message(self) -> Message:
        """Create an RTS (Request To Send) message"""
        return self.create_outgoing_message(msg_type=MESSAGE_TYPE.RTS)
    
    def send_rts(self):
        """Send a RTS request to all connected peers"""
        try:
            rts_message = self.create_rts_message()
            self.outgoing_message_queue.put_nowait(rts_message)
        except Exception as e:
            logger.error(f"Error queueing RTS: {e}")
    
    async def start_ping_sequence(self): # TODO: accept pong partner
        """Start sending PING messages continuously after becoming the PING sender"""
        try:
            while not self.clear_to_send and self.should_send_ping:
                # TODO: actually should not happen, refactor: remove sleep, async-await
                await asyncio.sleep(self.inner_frame_time_us / 1e6)
            
            if not self.should_send_ping:
                print(f"🔴 Node role changed to responder, stopping PING sequence")
                return
            print(f"🟢 Clear to send, starting PING sequence")
            while self.test_active and self.should_send_ping:
                ping_message = self.create_ping_message()
                self.outgoing_message_queue.put_nowait(ping_message)
                await asyncio.sleep(0) # TODO: needed? relinquish control
        except Exception as e:
            logger.error(f"Error in start_ping_sequence: {e}")

    def send_pong_response(self):
        pong_message = self.create_pong_message()
        self.outgoing_message_queue.put_nowait(pong_message)

    def process_outgoing_messages_queue(self):
        """
        Thread-based outgoing message processor with precise IFS timing.
        This function runs in a separate thread and handles sending outgoing messages every IFS.
        """

        while len(self.active_connections.keys()) == 0:
            logger.error("❌ No active connections to send messages to")
            time.sleep(1)


        sent_first_data = False        
        first_key = next(iter(self.active_connections))
        connected_peer = self.active_connections[first_key]

        while self.experiment_active:
            try:
                # Wait for message with precise timeout (4.5μs)
                if self.outgoing_message_queue.empty():
                    continue

                message = self.outgoing_message_queue.get(
                    timeout=self.inner_frame_time_us / 1e6
                )
                self.log_message(message)
                if message.msg_type != MESSAGE_TYPE.DATA or self.outgoing_messages_count % 100 == 0:
                    print(f"🚀 Sending outgoing message #{self.outgoing_messages_count}: {message.msg_type.value}")

                should_send_response = False # message.msg_type != MESSAGE_TYPE.DATA or not sent_first_data
                success: bool = asyncio.run_coroutine_threadsafe(
                    self.send_message_to_peer(connected_peer, message, response=should_send_response),
                    self.event_loop
                ).result()
                if not success:
                    logger.error(f"Failed to send message to {connected_peer.name}")
                    self.outgoing_message_queue.put_nowait(message)
                else:
                    self.outgoing_messages_count += 1
                    if message.msg_type == MESSAGE_TYPE.DATA and not sent_first_data:
                        sent_first_data = True

                self.outgoing_message_queue.task_done() # mark task as done to dequeue it
                
            except queue.Empty:
                # No message to send within timeout period
                continue
            except Exception as e:
                logger.error(f"Error in threaded outgoing message processing: {e}")
                has_active_connections = len(list(filter(lambda p: p.client.is_connected, self.active_connections.values()))) > 0
                if not has_active_connections:
                    self.experiment_active = False
                    print("❌ No active connections, stopping outgoing message sender thread")
                    break

        print(f"🛑 Stopped threaded outgoing message sender (sent {self.outgoing_messages_count} messages)")

    async def process_incoming_message_queue(self):
        """
        Process messages from the queue asynchronously without blocking.
        This function runs in the background and handles incoming messages as they arrive.
        """
        
        message_count = 0
        while self.experiment_active:
            try:
                # Wait for a message with a timeout to allow periodic checking of experiment_active
                message = await asyncio.wait_for(
                    self.incoming_message_queue.get(), 
                    timeout=self.inner_frame_time_us / 1e6
                )
                self.process_message(message)
                
            except asyncio.TimeoutError:
                # No message received in timeout period, continue loop
                continue
            except Exception as e:
                logger.error(f"Error in continuous message processing: {e}")
                raise(ValueError("Error in message processing"))
        
        print(f"🛑 Stopped continuous message processor (processed {message_count} messages)")

    def process_message(self, message: Message):
        """
        Process a single message based on its type and current protocol state.
        
        Args:
            message: The message to process
        """
        try:
            self.incoming_messages_count += 1
            self.log_message(message)
                
            if message.msg_type == MESSAGE_TYPE.RTS:
                self.handle_rts_message(message)
            elif message.msg_type == MESSAGE_TYPE.CTS:
                self.handle_cts_message(message)
            elif message.msg_type == MESSAGE_TYPE.DATA:
                self.handle_data_message(message)
            else:
                logger.warning(f"Unknown message type: {message.msg_type}")
                
        except Exception as e:
            logger.error(f"Error processing message {message.id}: {e}")

    def handle_rts_message(self, message: Message):
        """Handle RTS (Request To Send) messages"""
        self.should_send_ping = False
        self.clear_to_send = False
        self.send_cts()

    def handle_cts_message(self, message: Message):
        """Handle CTS (Clear To Send) messages"""
        self.clear_to_send = True

    def handle_data_message(self, message: Message):
        """Handle DATA messages (PING/PONG)"""        
        if self.test_active:
            if message.data_content.startswith("PING"):
                # pong_message = self.create_pong_message()
                # self.outgoing_message_queue.put_nowait(pong_message)
                # self.send_pong_response()
                pass
            elif message.data_content.startswith("PONG"):
                pass # don't do anything
            else:
                logger.warning(f"Received unknown DATA message content: {message.data_content}")
        
    async def start_server(self):
        """Start GATT server"""
        
        self.server = BlessServer(name=self.device_name, loop=asyncio.get_event_loop())
        self.got_control_message = asyncio.Event()
        self.got_data_message = asyncio.Event()
        self.server.read_request_func = self.read_request
        self.server.write_request_func = self.handle_peer_message
        
        await self.server.add_new_service(self.SERVICE_UUID)
        
        # Add message characteristic (write)
        await self.server.add_new_characteristic(
            self.SERVICE_UUID,
            self.MESSAGE_CHAR_UUID,
            GATTCharacteristicProperties.write | GATTCharacteristicProperties.write_without_response,
            None,
            GATTAttributePermissions.writeable
        )
        
        # Add status characteristic (read)
        await self.server.add_new_characteristic(
            self.SERVICE_UUID,
            self.STATUS_CHAR_UUID,
            GATTCharacteristicProperties.read,
            None,
            GATTAttributePermissions.readable
        )
        
        await self.server.start()
        print(f"✅ GATT server '{self.device_name}' started!")
        
        return self.server
    
    async def discover_peers(self, scan_duration: int = 5, max_discovery_retries: int = 3) -> list[Peer]:
        """Discover trusted peer devices, with retries and HCI reset on failure"""

        peers: list[Peer] = []
        discovery_attempt = 0

        while not peers and discovery_attempt < max_discovery_retries:
            discovery_attempt += 1
            
            while len(peers) == 0:
                def detection_callback(device: BLEDevice, advertisement_data: AdvertisementData):
                    if advertisement_data.local_name is None and device.name is None:
                        raise(ValueError(f"Device {device} and advertisement {advertisement_data} have no name!"))
                    
                    device_name: str = str(advertisement_data.local_name or device.name)
                    
                    # Only connect to trusted peers (not self)
                    if self.is_trusted_peer(device_name):
                        # Check if advertising our service
                        if self.SERVICE_UUID.lower() in [uuid.lower() for uuid in advertisement_data.service_uuids]:
                            peer_addresses = map(lambda p: p.device.address, peers)
                            if device.address not in peer_addresses:
                                logger.debug(f"🤝 Found trusted peer: {device_name} ({device.address}) RSSI: {advertisement_data.rssi}")
                                peers.append(Peer(name=device_name, device=device, rssi=advertisement_data.rssi))

                scanner = BleakScanner(detection_callback=detection_callback, service_uuids=[self.SERVICE_UUID])
                
                logger.debug(f"🔍 Attempt {discovery_attempt}/{max_discovery_retries}: scanning for trusted peers (pattern: {self.trusted_pattern}*)...")
                await scanner.start()
                await asyncio.sleep(scan_duration)
                await scanner.stop()
            if not peers:
                logger.debug(f"    ❌ No trusted peers found")
                if discovery_attempt < max_discovery_retries:
                    logger.debug("    🔄 Restarting HCI interface and retrying...")
                    self.restart_hci_interface()
                    await asyncio.sleep(3)  # Wait for HCI to restart
                else:
                    logger.error("    ❌ No trusted peers found after all attempts. Cannot run experiment.")
                    raise(ValueError("No trusted peers found after all attempts. Cannot run experiment."))
        logger.info(f"✅ Discovered {len(peers)} trusted peers")
        return peers
    
    def restart_hci_interface(self):
        """Restart the HCI interface to reset BLE state"""
        os.system("sudo hciconfig hci0 reset")
        time.sleep(1)
        print("🔄 HCI interface reset")

    async def connect_to_peer(self, peer: Peer) -> Optional[ConnectedPeer]:
        """Connect to a trusted peer"""
        if peer.device.address in self.active_connections:
            connected_peer = self.active_connections[peer.device.address]
            try:
                if connected_peer.client.is_connected:
                    return connected_peer
                else:
                    logger.debug(f"Peer is connected but client is not: reconnecting {peer.name}")
                    await connected_peer.client.connect()
            except Exception as e:
                logger.error(f"Error reconnecting to {peer.name}: {e}")
                del self.active_connections[peer.device.address]
        client = BleakClient(peer.device.address)
        try:
            await client.connect()
        except Exception as e:
            logger.error(f"Error connecting to {peer.name}: {e}")
            return None

        try:
            # Verify service exists
            chat_service = None
            
            for service in client.services:
                if service.uuid.lower() == self.SERVICE_UUID.lower():
                    chat_service = service
                    break
            
            if not chat_service:
                await client.disconnect()
                return None
            
            # Verify message characteristic exists
            message_char = None
            for char in chat_service.characteristics:
                if char.uuid.lower() == self.MESSAGE_CHAR_UUID.lower():
                    message_char = char
                    break
            
            if not message_char:
                await client.disconnect()
                return None
            
            
            # Read GATT characteristic to verify connection works
            try:
                await client.read_gatt_char(self.STATUS_CHAR_UUID)
            except Exception as e:
                print(f"⚠️ Connection test failed to {peer.name}: {e}")
                await client.disconnect()
                return None
            
            return ConnectedPeer(peer, client)
            
        except Exception as e:
            logger.error(f"Connection failed to {peer.name}: {e}")
            self.restart_hci_interface()
            return None

    async def send_message_to_peer(self, peer: ConnectedPeer, message: Message, response: bool) -> bool:
        """Send message to a specific peer with retry mechanism"""
        message_bytes = message.__str__().encode('utf-8')

        try:
            # Use write-without-response for maximum throughput
            await peer.client.write_gatt_char(self.MESSAGE_CHAR_UUID, message_bytes, response=response)
        except Exception as e:
            # TODO: better exception handling if write fails
            # BleakGattCharacteristicNotFoundError
            # if a characteristic with the handle or UUID specified by char_specifier could not be found.

            # backend-spe
            # ific exceptions: if the write operation failed.

            logger.error(f"Error sending message to {peer.name}")
            logger.error(e)
            traceback.print_exc()
                
            return False
                
        return True
                
    async def perform_run(self):
        """Perform a round of ping-pong: send RTS/CTS, then PING or answer to PING with PONG"""

        first_key = next(iter(self.active_connections))
        connected_peer = self.active_connections[first_key]

        
        # Wait [1-5s) to see if we receive RTS before sending our own RTS
        initial_wait_time = random.uniform(1, 5)
        logger.debug(f"⏳ Waiting {initial_wait_time}s for first message before potentially sending initial RTS")

        got_control_message = await event_wait(self.got_control_message, initial_wait_time)
        if got_control_message:
            # RTS or CTS received during wait period
            if not self.should_send_ping:
                # Other node sent RTS, we became ponger
                logger.info("This node is the ponger")
            else:
                # Other node sent CTS, we became sender
                logger.debug(f"📤 Received CTS during wait - this should not happen")
                return
                # self.send_rts()
                # asyncio.create_task(self.start_ping_sequence())
        else:
            # No RTS received, this node will be the sender
            rts_message = self.create_rts_message()
            result = await self.send_message_to_peer(connected_peer, rts_message, False)
            if not result:
                logger.error("❌ Failed to send RTS message, cannot continue run")
                return
            logger.info("This node is the pinger")

            asyncio.create_task(self.start_ping_sequence())

        await asyncio.sleep(self.test_duration)
        self.test_active = False

    async def prepare_and_perform_run(self, run_number: int):
        """Run a single throughput test for the specified duration"""
        logger.info(f"🏃 Starting ping-pong test run {run_number}/{self.num_runs}")

        self.prepare_logs(run_number)
        
        self.test_active = True
        
        # Reset state for this run
        self.outgoing_messages_count = 0
        self.incoming_messages_count = 0
        self.got_control_message.clear()
        self.got_data_message.clear()
        self.should_send_ping = True
        self.clear_to_send = False

        start_time = time.time()
        await self.perform_run()
        total_time = time.time() - start_time

        await self.cleanup_message_queue(False)
        
        print(f"✅ Run {run_number} complete:")
        print(f"   ⏱️ Total time: {total_time:.2f}s")
        print(f"   � Total messages sent: {self.outgoing_messages_count}")
        print(f"   📥 Total messages received: {self.incoming_messages_count}")
        print(f"   📝 Received log: {self.incoming_log_filename}")
        print(f"   📝 Sent log: {self.outgoing_log_filename}")

    async def connect_to_peers(self, peers: list[Peer], max_connection_retries: int = 3) -> dict[str, ConnectedPeer]:
        """Connect to discovered peer devices, with retries"""

        successful_connections = 0
        active_connections: dict[str, ConnectedPeer] = {}

        for connection_attempt in range(1, max_connection_retries + 1):
            logger.debug(f"🔗 Connection attempt {connection_attempt}/{max_connection_retries}")
            successful_connections = 0
            
            for peer in peers:
                connected_peer = await self.connect_to_peer(peer)
                if connected_peer:
                    active_connections[peer.device.address] = connected_peer
                    successful_connections += 1
                else:
                    logger.debug(f"❌ Failed to establish connection to {peer.device.address}")

            if successful_connections > 0:
                logger.debug(f"✅ Successfully connected to {successful_connections}/{len(peers)} peers")
                break
            elif connection_attempt < max_connection_retries:
                logger.debug("🔄 No successful connections. Restarting HCI interface and retrying...")
                self.restart_hci_interface()
                await asyncio.sleep(3)  # Wait for HCI to restart
                active_connections.clear()
            else:
                logger.error("❌ Failed to establish any connections after all attempts. Cannot run experiment.")
                traceback.print_exc()
                raise(ValueError("❌ Failed to establish any connections after all attempts. Cannot run experiment."))
        
        # Wait longer for BLE connections to fully stabilize
        await asyncio.sleep(5)
        return active_connections
    
    async def start_throughput_experiment(self):
        """Start the complete ping-pong experiment with RTS/CTS protocol"""
        logger.info(f"🔄 Will run {self.num_runs} tests of {self.test_duration}s each, with {self.delay_between_runs}s delay between runs")
        logger.info(f"📏 Message size: {self.message_size} bytes")
        print("=" * 70)
        
        await self.start_server()
        await asyncio.sleep(3) # waiting for server to stabilize
        
        peers = await self.discover_peers()
        active_peers = await self.connect_to_peers(peers)
        if not len(active_peers.keys()):
            logger.error("❌ No active connections found, cannot start experiment")
            return
        
        self.active_connections = active_peers
        self.outgoing_message_sender_thread.start()
        for run_number in range(1, self.num_runs + 1):

            await self.prepare_and_perform_run(run_number)
            
            if run_number < self.num_runs:
                logger.debug(f"⏳ Waiting {self.delay_between_runs}s before next run...")
                await asyncio.sleep(self.delay_between_runs)
        
        logger.info(f"🏁 Experiment complete! All {self.num_runs} runs finished.")
        logger.info(f"📝 Log files created:")
        for i, (incoming_log_file, outgoing_log_file) in enumerate(zip(self.incoming_log_files, self.outgoing_log_files), 1):
            logger.info(f"   Run {i}: {incoming_log_file}, {outgoing_log_file}")

        await self.cleanup()

    async def cleanup_stale_connections(self):
        for connected_peer in self.active_connections.values():
            try:
                await connected_peer.client.disconnect()
            except:
                pass
        self.active_connections.clear()

    async def cleanup_message_queue(self, should_cancel: bool = True):
        def empty_asyncio_queue(q: asyncio.Queue[Message]):
            if not q.empty():
                print(f"Clearing {q.qsize()} items from the asyncio queue")
                while not q.empty():
                    q.get_nowait()
                    q.task_done()
                print(f"Asyncio queue now has {q.qsize()} items")

        def empty_thread_queue(q: queue.Queue[Message]):
            if not q.empty():
                print(f"Clearing {q.qsize()} items from the thread queue")
                while not q.empty():
                    try:
                        q.get_nowait()
                        q.task_done()
                    except queue.Empty:
                        break
                print(f"Thread queue now has {q.qsize()} items")

        if self.received_log_buffer:
            self.flush_buffer(self.received_log_buffer, self.incoming_log_filename)
        if self.sent_log_buffer:
            self.flush_buffer(self.sent_log_buffer, self.outgoing_log_filename)

        logger.info("Clearing incoming message queue...")
        empty_asyncio_queue(self.incoming_message_queue)

        logger.info("Clearing outgoing message queue...")
        empty_thread_queue(self.outgoing_message_queue)

        if should_cancel:
            if self.incoming_message_processor_task and not self.incoming_message_processor_task.done():
                self.incoming_message_processor_task.cancel()
                try:
                    await self.incoming_message_processor_task
                except asyncio.CancelledError:
                    pass
            if self.outgoing_message_sender_thread and self.outgoing_message_sender_thread.is_alive():
                # The thread will stop when self.experiment_active becomes False
                self.outgoing_message_sender_thread.join(timeout=2.0)
                if self.outgoing_message_sender_thread.is_alive():
                    logger.warning("Outgoing message sender thread did not stop gracefully")

    async def cleanup(self):
        """Flush message queue and close it, along with every connected peer"""
        self.experiment_active = False
        self.test_active = False

        await self.cleanup_message_queue()

        await self.cleanup_stale_connections()

        # reset HCI interface to make sure a clean state is left for future experiments
        self.restart_hci_interface()
        
        if self.server:
            await self.server.stop()

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='BLE Ping-Pong Test Peer with CTS-First Protocol')
    parser.add_argument('peer_name', nargs='?', default=None,
                       help='Peer name/number (default: random 1-255)')
    parser.add_argument('-d', '--duration', type=int, default=30,
                       help='Test duration in seconds (default: 30)')
    parser.add_argument('-r', '--runs', type=int, default=3,
                       help='Number of test runs (default: 3)')
    parser.add_argument('-w', '--wait', type=int, default=5,
                       help='Delay between runs in seconds (default: 5)')
    parser.add_argument('-s', '--size', type=int, default=100,
                       help='Message size in bytes (default: 100)')
    parser.add_argument('--range', type=str, default="default",
                       help='Range identifier for organizing logs (default: "default")')
    parser.add_argument('--inner-frame-time', type=float, default=4.5,
                       help='Inner frame time in microseconds (default: 4.5μs)')
    
    return parser.parse_args()

async def event_wait(evt: asyncio.Event, timeout: float) -> bool:
        # suppress TimeoutError because we'll return False in case of timeout
        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(evt.wait(), timeout)
        return evt.is_set()

async def main():
    args = parse_arguments()
    
    # Determine peer name
    if args.peer_name:
        peer_name = args.peer_name
    else:
        peer_name = gethostname()
    
    # Validate arguments
    if args.duration <= 0:
        print("❌ Test duration must be positive")
        sys.exit(1)
    
    if args.runs <= 0:
        print("❌ Number of runs must be positive")
        sys.exit(1)
    
    if args.wait < 0:
        print("❌ Delay between runs cannot be negative")
        sys.exit(1)
    
    if args.size <= 0:
        print("❌ Message size must be positive")
        sys.exit(1)
    
    if args.inner_frame_time <= 0:
        print("❌ Inner frame time must be positive")
        sys.exit(1)
    
    peer = ThroughputTestPeer(
        peer_name=peer_name,
        test_duration=args.duration,
        num_runs=args.runs,
        delay_between_runs=args.wait,
        message_size=args.size,
        range_id=args.range,
        inner_frame_time_us=args.inner_frame_time
    )
    
    try:
        await peer.start_throughput_experiment()
    except KeyboardInterrupt:
        print(f"\n🛑 {peer.device_name} interrupted by user")
        await peer.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
