from itertools import takewhile
from pickle import dump
from argparse import ArgumentParser
import re

# Disclaimer: Claude 4.0 helped writing this code, especially in plotting.
class Topology:
    def __init__(self) -> None:
        self.connections: dict[str, set[str]] = {}

    def add_connection(self, source: str, target: str) -> None:
        if source not in self.connections:
            self.connections[source] = set()
        self.connections[source].add(target)

    def remove_connection(self, source: str, target: str) -> None:
        if source in self.connections:
            self.connections[source].discard(target)

    def get_number_of_links(self) -> int:
        count = 0
        links_counted: dict[str, set[str]] = {}
        for node, neighbors in self.connections.items():
            for neighbor in neighbors:
                source, target = tuple(sorted([node, neighbor]))
                neighbours = links_counted.get(source)
                if neighbours is None:
                    links_counted[source] = set([target])
                    count += 1
                else:
                    if target not in neighbours:
                        count += 1
                        links_counted[source].add(target)
        return count

class Configuration:
    def __init__(self, run_number: int, range: int, max_degree: int, mode: int) -> None:
        self.run_number = run_number
        self.range = range
        self.max_degree = max_degree
        self.mode = mode

    def __str__(self) -> str:
        return f"Configuration(run={self.run_number}, range={self.range}, max_degree={self.max_degree}, mode={'intra' if self.mode == 0 else 'inter'})"
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, Configuration):
            return False
        return (self.run_number == other.run_number and 
                self.range == other.range and 
                self.max_degree == other.max_degree and 
                self.mode == other.mode)
    
    def __hash__(self) -> int:
        return hash((self.run_number, self.range, self.max_degree, self.mode))
class HostInfo:
    def __init__(self, host_id: str, x: float, y: float) -> None:
        self.host_id = host_id
        self.x = x
        self.y = y
        
    def get_coordinates(self) -> tuple[float, float]:
        return (self.x, self.y)
        
    def distance_to(self, other: 'HostInfo') -> float:
        """Calculate Euclidean distance to another host"""
        dx = self.x - other.x
        dy = self.y - other.y
        return (dx*dx + dy*dy)**0.5
    
    def __str__(self) -> str:
        return f"HostInfo({self.host_id} at ({self.x:.2f},{self.y:.2f}))"

class Hop:
    def __init__(self, from_node: str, to_node: str, hop_time: float, from_node_degree: int) -> None:
        self.from_node = from_node
        self.to_node = to_node
        self.hop_time = hop_time  # Time it took for this specific hop
        self.from_node_degree = from_node_degree  # Node degree of the transmitting node at timestamp
    
    def __str__(self) -> str:
        return f"Hop({self.from_node} -> {self.to_node})"
class DeliveredMessageDTO:
    """
    Minimal DTO to carry message ID, hop nodes, and size
    """
    def __init__(self, message_id: str, hops: list[str], size: int) -> None:
        self.id = message_id
        self.hops = hops
        self.size = size
class Message:
    """
    Message class to represent message data with the following attributes:
    - ID: Message identifier
    - Creation time: Timestamp when the message was created
    - distance: Distance travelled by the message
    - size: Size of the message in bytes
    - communication_range: Communication range setting for this message's simulation
    - peer_density: Number of peer connections at message creation time
    - hop_count: Number of hops the message took
    - delivery_time: Time taken to deliver the message
    - is_delivered: Was the message delivered successfully
    - hops: the hops the message took (aggregated from transmissions and hops)
    - mode: inter- vs. intra-cluster message: 0 for intra, 1 for inter
    - source: source node
    - target: (final) destination node
    - source_host: HostInfo object for source node
    - target_host: HostInfo object for target node
    - run: run number this message came from
    - scenario_name: scenario name prefix (e.g., "GR")
    - message_size: message size used in simulation
    - max_degree: maximum allowed node degree for this simulation
    """
    def __init__(self, message_id: str, creation_time: float=0, distance: float=0, size: int=0, communication_range: int=0, peer_density: int=0, hop_count: int=0, delivery_time: float=0, is_delivered: bool=False, mode: int=0, source: str="", target: str="", source_host: HostInfo=None, target_host: HostInfo=None, run: int=0, scenario_name: str="", message_size: int=0, max_degree: int=0):
        self.id = message_id
        self.creation_time = creation_time
        self.distance = distance
        self.size = size
        self.communication_range = communication_range
        self.peer_density = peer_density
        self.hop_count = hop_count
        self.delivery_time = delivery_time
        self.is_delivered = is_delivered
        self.hops: list[Hop] = []
        self.mode = mode # 0 for intra-cluster, 1 for inter-cluster
        self.source = source
        self.target = target
        self.source_host = source_host
        self.target_host = target_host
        self.run = run
        self.scenario_name = scenario_name
        self.message_size = message_size
        self.max_degree = max_degree
        
    def setHops(self, hops: list[Hop]) -> None:
        self.hops = hops
    
    def __str__(self):
        return f"Message(id={self.id}, distance={self.distance}, size={self.size}, communication_range={self.communication_range}, peer_density={self.peer_density}, hop_count={self.hop_count}, delivery_time={self.delivery_time}, is_delivered={self.is_delivered}, mode={'intra' if self.mode == 0 else 'inter'}, source={self.source}, target={self.target}, run={self.run}, scenario={self.scenario_name}, max_degree={self.max_degree}, hops=[{', '.join(str(hop) for hop in self.hops)}])"
        
class Transmission:
    """ Transmission represents a transmission of a message in hop
    - timestamp: timestamp when the transmission happened
    - from_node: the transmitting node
    - to_node: the node receiving the transmission
    - message_id: the ID of the message: this stays the same between hops
    - creation_time: time when the transmission was created
    - delivery_time: time when the transmission was delivered
    - total_delivery_time: total time it took for the transmission to be delivered, incl. hops
    """
    def __init__(self, timestamp: float, from_node: str, to_node: str, message_id: str, creation_time: float, delivery_time: float) -> None:
        self.timestamp = timestamp
        self.from_node = from_node
        self.to_node = to_node
        self.message_id = message_id
        self.hops: list[Hop] = []
        self.creation_time = creation_time
        self.delivery_time = delivery_time
        self.total_delivery_time=0.0 # TODO: check if there is a diff between delivery time and total delivery time
    
    def add_hop(self, hop: Hop) -> None:
        self.hops.append(hop)
        self.total_delivery_time += hop.hop_time

class TransmissionEvent:
    """ Transmission event represents more or less a message-related row in the event log report
    - timestamp: timestamp when the transmission happened
    - from_node: the transmitting node
    - to_node: the node receiving the transmission
    - message_id: the ID of the message: this stays the same between hops
    - action: C for created, S for sent, DE for delivery
    - extra: D for final delivery (transmission reached goal), or R for relayed (hop)
    """
    def __init__(self, timestamp: float, from_node: str, message_id: str, action: str, to_node: str = "", extra: str = "") -> None:
        self.timestamp = timestamp
        self.from_node = from_node
        self.message_id = message_id
        self.action = action
        self.to_node = to_node
        self.extra = extra
    def __str__(self) -> str:
        return f"TransmissionEvent({self.timestamp}: FROM {self.from_node} ID: {self.message_id} ACTION: {self.action}, TO_NODE: {self.to_node} EXTRA: {self.extra})"

def get_host_id_from_host_name(node_name: str) -> str:
    """
    Extract host ID from host name.
    Args:
        node_name: Host name in format 'random_stationary_{clusterid}_{hostid}'
    Returns:
        Host ID as a string
    """
    splitted = node_name.split("_")
    if len(splitted) < 4:
        raise ValueError(f"Node name '{node_name}' does not conform to expected format 'random_stationary_{{clusterid}}_{{hostid}}'")
    return splitted[3]

def parse_hl_lines_from_unified_report(unified_report_file: str) -> dict[str, HostInfo]:
    """
    Parse HL lines from unified report to extract host location information.
    
    Args:
        unified_report_file: Path to the unified report file
        
    Returns:
        Dictionary mapping host_name to HostInfo objects
    """
    hosts: dict[str, HostInfo] = {}
    
    with open(unified_report_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('HL:'):
                # Format: HL: random_stationary_cluster_hostid (x.xx,y.yy)
                parts = line.split()
                if len(parts) >= 3:
                    host_name = parts[1]  # e.g., "random_stationary_0_5"
                    coord_str = parts[2]  # e.g., "(63.92,81.15)"
                    
                    # Extract coordinates from (x.xx,y.yy) format
                    coord_match = re.match(r'\(([0-9.-]+),([0-9.-]+)\)', coord_str)
                    if coord_match:
                        x = float(coord_match.group(1))
                        y = float(coord_match.group(2))
                        host_id = get_host_id_from_host_name(host_name)
                        hosts[host_name] = HostInfo(host_id, x, y)
                        
    return hosts

def load_distance_delay_data(file_path: str, mode: int, delivered_messages: set[str], run: int = 0, scenario_name: str = "", message_size: int = 0, max_degree: int = 0) -> list[Message]:
    """
    Load distance delay report data
    Args:
        - file_path: Path to the distance delay report file
        - mode: 0 for intra-cluster messages, 1 for inter-cluster messages
        - run: run number
        - scenario_name: scenario name prefix
        - message_size: message size
    Format: distance, delivery_time, hop_count, message_id
    """
    messages: list[Message] = []
    
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('#') or not line:
                print(f"Skipped line: {line}")
                continue
            parts = line.split()
            if len(parts) >= 4:
                distance = float(parts[0])
                delivery_time = float(parts[1])
                hop_count = int(parts[2])
                message_id = parts[3]
                is_delivered = message_id in delivered_messages
                msg = Message(message_id, distance=distance, hop_count=hop_count, delivery_time=delivery_time, is_delivered=is_delivered, mode=mode, run=run, scenario_name=scenario_name, message_size=message_size, max_degree=max_degree)
                messages.append(msg)
            else:
                print("Cannot load distance delay delay of line due to missing 4 parts, have {} parts:", line, len(parts))
    return messages

def load_delivered_messages_data(file_path: str) -> list[DeliveredMessageDTO]:
    """
    Load delivered messages report data
    Format: time, ID, size, hopcount, deliveryTime, fromHost, toHost, remainingTtl, isResponse, path

    Returns: List of DeliveredMessageDTO
    """
    messages: list[DeliveredMessageDTO] = []
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('#') or not line:
                print(f"Skipped line: {line}")
                continue
            parts = line.split()
            if len(parts) >= 3:
                message_id = parts[1]
                size = int(parts[2])
                hops = parts[-1].split('->')
                dto = DeliveredMessageDTO(message_id, hops, size)
                messages.append(dto)
            else:
                print("Cannot load message delivery data line due to missing 3 parts, have {} parts:", line, len(parts))
    return messages

def parse_message_transmission_line(line: str) -> None|TransmissionEvent:
    """
    Parse a single line of message transmission data.
    
    Args:
        line: A string representing a line from EventLogReport.txt
        
    Returns:
        Transmission object with parsed data
    """
    parts = line.split()
    timestamp = float(parts[0])
    action = parts[1]
    from_node = parts[2]

    # Actions: 
    # C for created
    # S (Send) for message transfer started
    # DE for delivered
    # DR for dropped
    # A for delivered again
        
    if action == 'C':
        to_node = parts[3]  # target node
        message_id = parts[4]
        return TransmissionEvent(timestamp, from_node, message_id, action, to_node)
    if (action == 'A') or (action == 'S') or (action == 'DE'):
        to_node = parts[3]
        message_id = parts[4]
        extra = parts[5] if action == 'DE' else '' # D for first delivery (message destination received the message/transmission), R for relayed
        return TransmissionEvent(timestamp, from_node, message_id, action, to_node, extra)
    if action == 'DR':
        # handle drop
        return None
    else:
        print("LINE CANNOT BE PARSED: Action is not recognized")
        print(line)
        return None # TODO: handle drop?

def parse_message_transmissions(event_log_file: str, delivered_messages: list[DeliveredMessageDTO], connectivity_by_time: dict[float, dict[str, dict[str, set[str]]]]) -> dict[str, Transmission]:
    """
    Parse EventLogReport to extract message transmission events.
    
    Args:
        - event_log_file: Path to EventLogReport.txt
        - delivered_messages: delivered messages, along with the path they took to their destination
        - connectivity_by_time: dictionary representing connectivity state at timestamp per node
        
    Returns:
        Dict of message ID to transmission with timing and hop information
    """
    transmissions: dict[str, Transmission] = {}
    transmissions_events_per_message: dict[str, list[TransmissionEvent]] = {} # store all events per message ID
    delivered_messages_by_id = {msg.id: msg for msg in delivered_messages}
    with open(event_log_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or 'CONN' in line:
                # skip lines not related to messages, or comments
                continue
            transmission_event = parse_message_transmission_line(line)
            if transmission_event is None:
                continue

            # we only store transmission events that are part of the successful delivery of a message
            if transmission_event.message_id in delivered_messages_by_id:
                path = delivered_messages_by_id[transmission_event.message_id].hops
                # either the created event, or for delivery the destination of this transmission is in the path
                if (transmission_event.from_node in path and transmission_event.action == 'C') or transmission_event.to_node in path:
                    if transmission_event.message_id not in transmissions_events_per_message:
                        transmissions_events_per_message[transmission_event.message_id] = []
                    transmissions_events_per_message[transmission_event.message_id].append(transmission_event)
    
    for message_id, events in transmissions_events_per_message.items():
        path = delivered_messages_by_id[message_id].hops

        # events are already sorted by timestamp
        created_event = next((t for t in events if t.action == 'C'), None) # only one created event per transmission
        if created_event is None:
            raise ValueError(f"No created event found for message ID {message_id}. Cannot load data.")

        delivered_event = next((t for t in events if t.extra == 'D'), None) # only one created event per transmission
        if delivered_event is None:
            raise ValueError(f"No delivered event found for message ID {message_id}. Cannot load data.")
        hops = [created_event] + [t for t in events if t.action == 'DE' and t.extra == 'R'] + [delivered_event]
        
        hops_paired = list(zip(hops, hops[1:])) # Pair all delivered events with the created event and final delivery event to create hops
        
        transmission = Transmission(delivered_event.timestamp, created_event.from_node, delivered_event.to_node, created_event.message_id, created_event.timestamp, delivered_event.timestamp)
        
        for (from_hop, to_hop) in hops_paired:
            duration = float(to_hop.timestamp) - float(from_hop.timestamp)

            timestamp = from_hop.timestamp
            from_node = from_hop.from_node
            
            # Get neighbors for hop transmitting node at transmission time
            neighbors = get_neighbors_at_time_for_node(connectivity_by_time, timestamp, from_node)
            node_degree = len(neighbors)

            hop = Hop(to_hop.from_node, to_hop.to_node, duration, node_degree)
            transmission.add_hop(hop)

        transmissions[transmission.message_id] = transmission

    return transmissions

def parse_connectivity_report(connectivity_file: str) -> dict[float, dict[str, dict[str, set[str]]]]:
    """
    Parse ConnectivityONEReport to build a time-indexed connectivity graph.
    
    Args:
        connectivity_file: Path to ConnectivityONEReport.txt
        
    Returns:
        Dictionary mapping timestamp -> node -> { up: up connection events to nodes, down: down connection event to nodes }
    """
    connectivity_by_time: dict[float, dict[str, dict[str, set[str]]]] = {}
    
    with open(connectivity_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            parts = line.split()
            if len(parts) >= 5 and parts[1] == 'CONN':
                timestamp = float(parts[0])
                node1, node2 = parts[2], parts[3]
                status = parts[4]  # 'up' or 'down'
                
                if timestamp not in connectivity_by_time:
                    timestamp_connectivity_state = {}
                    timestamp_connectivity_state[node1] = {'up': set(), 'down': set()}
                    timestamp_connectivity_state[node2] = {'up': set(), 'down': set()}
                    connectivity_by_time[timestamp] = timestamp_connectivity_state
                if node1 not in connectivity_by_time[timestamp]:
                    connectivity_by_time[timestamp][node1] = {'up': set(), 'down': set()}
                if node2 not in connectivity_by_time[timestamp]:
                    connectivity_by_time[timestamp][node2] = {'up': set(), 'down': set()}

                connectivity_by_time[timestamp][node1][status].add(node2)
                connectivity_by_time[timestamp][node2][status].add(node1)
                    
    
    return connectivity_by_time

def get_final_topology(connectivity_by_time: dict[float, dict[str, dict[str, set[str]]]]) -> Topology:
    """
    Get the final topology state from connectivity events by replaying all connection/disconnection events.
    
    Args:
        connectivity_by_time: Time-indexed connectivity events
        
    Returns:
        Topology mapping node_id -> set of connected neighbor node_ids
    """
    topology: Topology = Topology()
    
    for timestamp in sorted(connectivity_by_time.keys()):
        for node_id, connections in connectivity_by_time[timestamp].items():
            
            for connected_id in connections['up']:
                topology.add_connection(node_id, connected_id)
            
            for disconnected_id in connections['down']:
                topology.remove_connection(node_id, disconnected_id)
    
    return topology

def get_neighbors_at_time_for_node(connectivity_state: dict[float, dict[str, dict[str, set[str]]]], 
                           target_time: float, node_name: str) -> set[str]:
    """
    Get the connectivity state at a specific time (or closest available time) for a specific node.
    
    Args:
        connectivity_state: Complete connectivity state by timestamp, node, and status
        target_time: The time to query
        node_name: Node name to built connectivity state for
        
    Returns:
        Connectivity state (node -> set of connected nodes)
    """
    # Find all timestamps <= target_time, take advantage of report being sorted
    valid_times = list(takewhile(lambda t: t <= target_time, connectivity_state.keys()))

    node_id = get_host_id_from_host_name(node_name)
    neighbors: set[str] = set()
    for time in sorted(valid_times):
        connectivity_at_time = connectivity_state[time]
        if node_id in connectivity_at_time:
            # add all neighbours connected at the timestamp, and remove all neighbors that were dropped
            connections_established_at_time = connectivity_at_time[node_id]['up']
            neighbors |= connections_established_at_time
            
            connections_dropped_at_time = connectivity_at_time[node_id]['down']
            neighbors -= connections_dropped_at_time
    
    return neighbors

def load_all_created_messages(event_log_file: str, message_size: int, communication_range: float, run: int = 0, scenario_name: str = "", max_degree: int = 0) -> list[Message]:
    """
    Load all created messages from EventLogReport, including undelivered ones.
    
    Args:
        event_log_file: Path to EventLogReport.txt
        message_size: Size of messages for this simulation
        communication_range: Communication range for this simulation
        run: run number
        scenario_name: scenario name prefix
        max_degree: constrained max degree
        
    Returns:
        List of all Message objects that were created
    """
    created_messages: list[Message] = []
    
    with open(event_log_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or 'CONN' in line:
                continue
                
            parts = line.split()
            if len(parts) >= 5 and parts[1] == 'C':  # Created message
                timestamp = float(parts[0])
                from_node = parts[2]
                to_node = parts[3]
                message_id = parts[4]
                
                # Create a basic message object for created messages
                # We don't have distance/delivery info for undelivered messages
                msg = Message(message_id, creation_time=timestamp, distance=0, size=message_size,
                              communication_range=int(communication_range), delivery_time=0, hop_count=0,
                              source=from_node, target=to_node, run=run, scenario_name=scenario_name, message_size=message_size, max_degree=max_degree)

                created_messages.append(msg)
    
    return created_messages

def combine_run_message_data(config: Configuration, scenario_prefix: str, message_size: int) -> tuple[list[Message], list[Message], Topology]:
    messages: list[Message] = []
    delivered_messages: list[Message] = []

    run = config.run_number
    range_suffix = str(config.range)
    mode = config.mode
    max_degree = config.max_degree

    distance_file = f"reports_data/{scenario_prefix}_size{message_size}_run{run}_range{range_suffix}_mode{mode}_maxdeg{max_degree}_DistanceDelayReport.txt"
    delivered_file = f"reports_data/{scenario_prefix}_size{message_size}_run{run}_range{range_suffix}_mode{mode}_maxdeg{max_degree}_DeliveredMessagesReport.txt"
    connectivity_file = f"reports_data/{scenario_prefix}_size{message_size}_run{run}_range{range_suffix}_mode{mode}_maxdeg{max_degree}_ConnectivityONEReport.txt"
    eventlog_file = f"reports_data/{scenario_prefix}_size{message_size}_run{run}_range{range_suffix}_mode{mode}_maxdeg{max_degree}_EventLogReport.txt"
    unified_report_file = f"reports_data/{scenario_prefix}_size{message_size}_run{run}_range{range_suffix}_mode{mode}_maxdeg{max_degree}_UnifiedReport.txt"

    host_info = parse_hl_lines_from_unified_report(unified_report_file)

    delivered_message_dtos = load_delivered_messages_data(delivered_file)
    delivered_message_ids = set(msg.id for msg in delivered_message_dtos)
    distance_messages = load_distance_delay_data(distance_file, mode, delivered_message_ids, run, scenario_prefix, message_size, max_degree)
    distance_data = {msg.id: msg for msg in distance_messages}  # Create lookup by message ID
    
    created_messages_run = load_all_created_messages(eventlog_file, message_size, float(range_suffix), run, scenario_prefix, max_degree)
    for msg in created_messages_run:
        if msg.id in distance_data:
            msg.distance = distance_data[msg.id].distance
            msg.delivery_time = distance_data[msg.id].delivery_time
            msg.hop_count = distance_data[msg.id].hop_count
        msg.mode = mode
        
        if msg.source in host_info:
            msg.source_host = host_info[msg.source]
        if msg.target in host_info:
            msg.target_host = host_info[msg.target]

        messages.append(msg)    

    transmissions_data = load_transmission_data(eventlog_file, connectivity_file, delivered_message_dtos)
    connectivity_by_time = parse_connectivity_report(connectivity_file)
    final_topology = get_final_topology(connectivity_by_time)
    
    for msg in distance_messages:
        if msg.id in delivered_message_ids:
            delivered_message = delivered_message_dtos[[m.id for m in delivered_message_dtos].index(msg.id)]
            msg.size = delivered_message.size
            msg.hops = transmissions_data[msg.id].hops
            created_message = next(m for m in created_messages_run if m.id == msg.id)
            msg.source = created_message.source
            msg.target = created_message.target
            
            if msg.source in host_info:
                msg.source_host = host_info[msg.source]
            if msg.target in host_info:
                msg.target_host = host_info[msg.target]

            msg.communication_range = int(range_suffix)
            # Ensure run, scenario_name, and message_size are set for delivered messages
            msg.run = run
            msg.scenario_name = scenario_prefix
            msg.message_size = message_size
            msg.max_degree = max_degree
            delivered_messages.append(msg)
    
    for msg in created_messages_run + delivered_messages:
        msg.id = f"{msg.id}_run{run}_range{range_suffix}"
    
    return created_messages_run, delivered_messages, final_topology

def combine_all_message_data(scenario_prefix: str, range_suffixes: list[int], num_runs: int, message_size: int, max_degrees: list[int]) -> tuple[list[Message], list[Message], dict[Configuration, Topology]]:
    """
    Combine data to get all messages, as well as delivered messages, and topologies.

    Returns:
        Tuple of (all_messages, delivered_messages, topologies)
        where topologies is a dict with key (range, mode, max_degree, run) -> topology dict
    """
    all_messages: list[Message] = []
    delivered_messages: list[Message] = []
    delivered_message_ids: set[str] = set()
    all_topologies: dict[Configuration, Topology] = {}
    
    for max_degree in max_degrees:
        for mode in [0,1]: # 0 for intra, 1 for inter
            for range_suffix in range_suffixes:
                print(f"Combining all messages for communication range {range_suffix}... in mode {'intra' if mode == 0 else 'inter'}, max_degree {max_degree}")
                
                for run in range(1, num_runs + 1):
                    print(f" Processing run {run}/{num_runs}...")
                    config = Configuration(run, range_suffix, max_degree, mode)
                    created_messages_run, delivered_messages_run, topology = combine_run_message_data(config, scenario_prefix, message_size)
                    
                    all_messages.extend(created_messages_run)
                    delivered_messages.extend(delivered_messages_run)
                    delivered_message_ids.update(msg.id for msg in delivered_messages_run)

                    all_topologies[config] = topology

    for msg in all_messages:
        msg.is_delivered = msg.id in delivered_message_ids
    
    return all_messages, delivered_messages, all_topologies

def load_transmission_data(event_log_file: str, connectivity_file: str, delivered_messages_with_hops: list[DeliveredMessageDTO]) -> dict[str, Transmission]:
    """
    Calculate peer density and latency for each transmitting node at the time of message transmission.
    
    Args:
        - event_log_file: Path to EventLogReport.txt
        - connectivity_file: Path to ConnectivityONEReport.txt
        - delivered_messages_with_hops: list of DeliveredMessageDTO
    Returns:
        Dict of message ID to transmission
    """
    connectivity_by_time = parse_connectivity_report(connectivity_file)
    
    return parse_message_transmissions(event_log_file, delivered_messages_with_hops, connectivity_by_time)

def split_unified_report_to_report_paths(unified_report_file_path: str, distance_file_path: str, delivered_file_path: str, connectivity_file_path: str, eventlog_file_path: str, hl_file_path: str):
    # report identifiers can be:
    # DD for distance delay report
    # DM for delivered messages report
    # EL for event log report
    # CO for connectivity ONE report
    # HL for host location report
    distance_delay_row_identifier="DD"
    delivered_messages_row_identifier="DM"
    connectivity_row_identifier="CO"
    event_log_row_identifier="EL"
    host_location_row_identifier="HL:"

    with open(unified_report_file_path, "r") as unified_report_file, open(distance_file_path, "w") as distance_file, open(delivered_file_path, "w") as delivered_file, open(connectivity_file_path, "w") as connectivity_file, open(eventlog_file_path, "w") as eventlog_file:
        hl_file = None
        if hl_file_path:
            hl_file = open(hl_file_path, "w")
            
        for line in unified_report_file:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # TODO: improve this
            if line.startswith(host_location_row_identifier):
                if hl_file:
                    hl_file.write(line + "\n")
                continue
                
            if ": " not in line:
                continue
                
            report_identifier, line_content = line.split(": ", 1)

            if report_identifier == distance_delay_row_identifier:
                distance_file.write(line_content + "\n")
            elif report_identifier == delivered_messages_row_identifier:
                delivered_file.write(line_content + "\n")
            elif report_identifier == connectivity_row_identifier:
                connectivity_file.write(line_content + "\n")
            elif report_identifier == event_log_row_identifier:
                eventlog_file.write(line_content + "\n")
            else:
                raise ValueError(f"got unexpected report identifier: {report_identifier}")
        
        if hl_file:
            hl_file.close()

def split_unified_report(scenario_prefix: str, ranges: list[int], runs: int, message_size: int, max_degrees: list[int]):
    for max_degree in max_degrees:
        for range_suffix in ranges:
            for run in range(1, runs + 1):
                for mode in [0,1]: # 0 for intra, 1 for inter
                    distance_file_path = f"reports_data/{scenario_prefix}_size{message_size}_run{run}_range{range_suffix}_mode{mode}_maxdeg{max_degree}_DistanceDelayReport.txt"
                    delivered_file_path = f"reports_data/{scenario_prefix}_size{message_size}_run{run}_range{range_suffix}_mode{mode}_maxdeg{max_degree}_DeliveredMessagesReport.txt"
                    connectivity_file_path = f"reports_data/{scenario_prefix}_size{message_size}_run{run}_range{range_suffix}_mode{mode}_maxdeg{max_degree}_ConnectivityONEReport.txt"
                    eventlog_file_path = f"reports_data/{scenario_prefix}_size{message_size}_run{run}_range{range_suffix}_mode{mode}_maxdeg{max_degree}_EventLogReport.txt"
                    hl_file_path = f"reports_data/{scenario_prefix}_size{message_size}_run{run}_range{range_suffix}_mode{mode}_maxdeg{max_degree}_HostLocationReport.txt"
                    unified_report_file_path = f"reports_data/{scenario_prefix}_size{message_size}_run{run}_range{range_suffix}_mode{mode}_maxdeg{max_degree}_UnifiedReport.txt"
                    split_unified_report_to_report_paths(unified_report_file_path, distance_file_path, delivered_file_path, connectivity_file_path, eventlog_file_path, hl_file_path)
def main():
    DEFAULT_RANGES = [1, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120]
    DEFAULT_NUM_RUNS = 20
    DEFAULT_SCENARIO_NAME = "GR"
    DEFAULT_MESSAGE_SIZE = 247

    parser = ArgumentParser(description="Combine reports generated from The ONE")
    parser.add_argument("--ranges", type=int, nargs="+", default=DEFAULT_RANGES, help="List of communication ranges to process. Default is " + str(DEFAULT_RANGES))
    parser.add_argument("--runs", type=int, default=DEFAULT_NUM_RUNS, help="Number of runs to process for each range. Default is " + str(DEFAULT_NUM_RUNS))
    parser.add_argument("--scenario-name", type=str, default="GR", help="Scenario name to process for the reports " + str(DEFAULT_SCENARIO_NAME))
    parser.add_argument("--message-size", type=int, default=DEFAULT_MESSAGE_SIZE, help="Message size used in the simulation filenames. Default is " + str(DEFAULT_MESSAGE_SIZE))
    parser.add_argument("--max-degrees", type=int, nargs="+", default=[1,2,3,4,5,6,7,8,9,10], help="List of max node degrees to process")

    args = parser.parse_args()
    ranges: list[int] = args.ranges
    runs: int = args.runs
    scenario_prefix: str = args.scenario_name
    message_size: int = args.message_size
    max_degrees: list[int] = args.max_degrees

    print(f"Received ranges {ranges}, runs {runs}, and message size {message_size}")

    print("Splitting unified report data to individual reports...")
    split_unified_report(scenario_prefix, ranges, runs, message_size, max_degrees)
    
    print("Combining all message data (including undelivered)...")
    all_messages, delivered_messages, topologies = combine_all_message_data(scenario_prefix, ranges, runs, message_size, max_degrees)
    print("All message data combined!")
    
    with open("all_messages.pkl", "wb") as f:
        dump(all_messages, f)
        
    with open("delivered_messages.pkl", "wb") as f:
        dump(delivered_messages, f)
    
    with open("topologies.pkl", "wb") as f:
        dump(topologies, f)
    
    print("Data saved to pickle files: all_messages.pkl, delivered_messages.pkl, topologies.pkl")

if __name__ == "__main__":
    main()
