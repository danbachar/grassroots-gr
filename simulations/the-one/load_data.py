from itertools import takewhile
from pickle import dump
from argparse import ArgumentParser

# Disclaimer: Claude 4.0 helped writing this code, especially in plotting. Data processing and loading was done by us.

class Hop:
    def __init__(self, from_node: str, to_node: str, hop_time: float, from_node_degree: int) -> None:
        self.from_node = from_node
        self.to_node = to_node
        self.hop_time = hop_time  # Time it took for this specific hop
        self.from_node_degree = from_node_degree  # Node degree of the transmitting node at timestamp
    
    def __str__(self) -> str:
        return f"Hop({self.from_node} -> {self.to_node}, time: {self.hop_time:.3f}s, degree: {self.from_node_degree})"

class Message:
    """
    Message class to represent message data with the following attributes:
    - ID: Message identifier
    - distance: Distance travelled by the message
    - size: Size of the message in bytes
    - peer_density: Number of peer connections at message creation time
    - hop_count: Number of hops the message took
    - delivery_time: Time taken to deliver the message
    - is_delivered: Was the message delivered successfully
    - hops: the hops the message took (aggregated from transmissions and hops)
    """
    def __init__(self, message_id, distance=0, size=0, peer_density=0, hop_count=0, delivery_time=0, is_delivered=0):
        self.id = message_id
        self.distance = distance
        self.size = size
        self.peer_density = peer_density
        self.hop_count = hop_count
        self.delivery_time = delivery_time
        self.is_delivered = is_delivered
        self.hops: list[Hop] = []
        
    def setHops(self, hops: list[Hop]) -> None:
        self.hops = hops
    
    def __str__(self):
        return f"Message(id={self.id}, distance={self.distance}, size={self.size}, peer_density={self.peer_density}, hop_count={self.hop_count}, delivery_time={self.delivery_time}, is_delivered={self.is_delivered})"
        
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
    def __init__(self, timestamp: str, from_node: str, to_node: str, message_id: str, creation_time: str, delivery_time: str) -> None:
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
    def __init__(self, timestamp: str, from_node: str, message_id: str, action: str, to_node = "", extra = "") -> None:
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
        node_name: Host name in format 'random_stationary_{hostid}'
    Returns:
        Host ID as a string
    """
    splitted = node_name.split("_")
    return splitted[2]

def load_distance_delay_data(file_path) -> list[Message]:
    """
    Load distance delay report data
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
                
                msg = Message(message_id, distance=distance, hop_count=hop_count, delivery_time=delivery_time, is_delivered=delivery_time == -1 or hop_count == -1)
                messages.append(msg)
            else:
                print("Cannot load distance delay delay of line due to missing 4 parts, have {} parts:", line, len(parts))
    return messages

def load_delivered_messages_data(file_path) -> dict[str, dict['size': int, 'hops': list[str]]]:
    """
    Load delivered messages report data
    Format: time, ID, size, hopcount, deliveryTime, fromHost, toHost, remainingTtl, isResponse, path
    
    Returns: Dict of message ID -> { size: message_size, hops: [node_ids]}
    """
    message_sizes_and_hops = {}
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
                message_sizes_and_hops[message_id] = { 'size': size, 'hops': hops }
            else:
                print("Cannot load message delivery data line due to missing 3 parts, have {} parts:", line, len(parts))
    return message_sizes_and_hops

def parse_message_transmission_line(line: str) -> TransmissionEvent:
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
        
    # (self, timestamp: str, from_node: str, message_id: str, action: str, to_node = "", extra = "")
    if action == 'C':
        message_id = parts[3]
        return TransmissionEvent(timestamp, from_node, message_id, action)
    if (action == 'A') or (action == 'S') or (action == 'DE'):
        to_node = parts[3]
        if len(parts) < 5: 
            print("LINE CANNOT BE PARSED")
            print(line)
            return None
        else:
            message_id = parts[4]
            extra = parts[5] if action == 'DE' else '' # D for first delivery (message destination received the message/transmission), R for relayed
            return TransmissionEvent(timestamp, from_node, message_id, action, to_node, extra)
    else:
        return None # TODO: handle drop?

def parse_message_transmissions(event_log_file: str, message_ids_and_paths: dict[str, set[str]], connectivity_by_time: dict[float, dict[str, dict[str, set[str]]]]) -> dict[str, Transmission]:
    """
    Parse EventLogReport to extract message transmission events.
    
    Args:
        - event_log_file: Path to EventLogReport.txt
        - message_id_and_paths: message IDs, along with the path they took to their destination
        - connectivity_by_time: dictionary representing connectivity state at timestamp per node
        
    Returns:
        Dict of message ID to transmission with timing and hop information
    """
    transmissions = {}
    transmissions_events_per_message: dict[str, list[TransmissionEvent]] = {} # store all events per message ID

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
            if transmission_event.message_id in message_ids_and_paths:
                path = message_ids_and_paths[transmission_event.message_id]
                if (transmission_event.from_node in path and transmission_event.action == 'C') or transmission_event.to_node in path: # either the created event, or for delivery the destination of this transmission is in the path
                    if transmission_event.message_id not in transmissions_events_per_message:
                        transmissions_events_per_message[transmission_event.message_id] = []
                    transmissions_events_per_message[transmission_event.message_id].append(transmission_event)
    
    for message_id, events in transmissions_events_per_message.items():
        path = message_ids_and_paths[message_id]

        # events are already sorted by timestamp
        created_event = next((t for t in events if t.action == 'C'), None) # only one created event per transmission
        if created_event is None:
            print(f"No created event found for message ID {message_id}. Skipping transmission. S")
            raise("fuck")
        
        delivered_event = next((t for t in events if t.extra == 'D'), None) # only one created event per transmission
        if delivered_event is None:
            print(f"No delivered event found for message ID {message_id}. Skipping transmission. Something is wrong")
            raise("fuck")
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

            hop = Hop(from_hop.from_node, to_hop.to_node, duration, node_degree)
            transmission.add_hop(hop)

        transmissions[transmission.message_id] = transmission

    return transmissions

def parse_connectivity_report(connectivity_file: str) -> dict[float, dict[str, set[str]]]:
    """
    Parse ConnectivityONEReport to build a time-indexed connectivity graph.
    
    Args:
        connectivity_file: Path to ConnectivityONEReport.txt
        
    Returns:
        Dictionary mapping timestamp -> node -> set of connected nodes
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
    neighbors = set()
    for time in sorted(valid_times):
        connectivity_at_time = connectivity_state[time]
        if node_id in connectivity_at_time:
            # add all neighbours connected at the timestamp, and remove all neighbors that were dropped
            connections_established_at_time = connectivity_at_time[node_id]['up']
            neighbors |= connections_established_at_time
            
            connections_dropped_at_time = connectivity_at_time[node_id]['down']
            neighbors -= connections_dropped_at_time
    
    return neighbors

def load_transmission_data(event_log_file: str, connectivity_file: str, delivered_messages_with_hops: dict[str, set[str]]) -> dict[str, Transmission]:
    """
    Calculate peer density and latency for each transmitting node at the time of message transmission.
    
    Args:
        - event_log_file: Path to EventLogReport.txt
        - connectivity_file: Path to ConnectivityONEReport.txt
        - delivered_messages_with_hops: dictionary that maps delivered message ids to the paths they took
        
    Returns:
        Dict of message ID to transmission
    """
    connectivity_by_time = parse_connectivity_report(connectivity_file)
    
    transmissions = parse_message_transmissions(event_log_file, delivered_messages_with_hops, connectivity_by_time)
    
    return transmissions

def split_unified_report(scenario_prefix, ranges, runs, message_size: str = "247"):
    # identifiers can be:
    # DD for distance delay
    # DM for delivered messages
    # EL for event log
    # CO for connectivity ONE
    distance_delay_row_identifier="DD"
    delivered_messages_row_identifier="DM"
    connectivity_row_identifier="CO"
    event_log_row_identifier="EL"

    for range_suffix in ranges:        
        for run in range(1, runs + 1):
            distance_file_path = f"reports_data/{scenario_prefix}_{message_size}_run{run}_range{range_suffix}_DistanceDelayReport.txt"
            delivered_file_path = f"reports_data/{scenario_prefix}_{message_size}_run{run}_range{range_suffix}_DeliveredMessagesReport.txt"
            connectivity_file_path = f"reports_data/{scenario_prefix}_{message_size}_run{run}_range{range_suffix}_ConnectivityONEReport.txt"
            eventlog_file_path = f"reports_data/{scenario_prefix}_{message_size}_run{run}_range{range_suffix}_EventLogReport.txt"
            unified_report_file_path = f"reports_data/{scenario_prefix}_{message_size}_run{run}_range{range_suffix}_UnifiedReport.txt"
            
            with open(unified_report_file_path, "r") as unified_report_file, open(distance_file_path, "w") as distance_file,  open(delivered_file_path, "w") as delivered_file, open(connectivity_file_path, "w") as connectivity_file, open(eventlog_file_path, "w") as eventlog_file:
                for line in unified_report_file:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    report_identifier, line = line.split(": ")

                    if report_identifier == distance_delay_row_identifier:
                        distance_file.write(line + "\n")
                    elif report_identifier == delivered_messages_row_identifier:
                        delivered_file.write(line + "\n")
                    elif report_identifier == connectivity_row_identifier:
                        connectivity_file.write(line + "\n")
                    elif report_identifier == event_log_row_identifier:
                        eventlog_file.write(line + "\n")
                    else:
                        raise ValueError(f"got unexpected report identifier: {report_identifier}")


def main():
    DEFAULT_RANGES = ["12", "50", "120"]
    DEFAULT_NUM_RUNS = 50
    DEFAULT_SCENARIO_NAME = "GR"
    DEFAULT_MESSAGE_SIZE = "247"

    parser = ArgumentParser(description="Combine reports generated from The ONE")
    parser.add_argument("--ranges", nargs="+", default=DEFAULT_RANGES, help="List of communication ranges to process. Default is " + str(DEFAULT_RANGES))
    parser.add_argument("--runs", type=int, default=DEFAULT_NUM_RUNS, help="Number of runs to process for each range. Default is " + str(DEFAULT_NUM_RUNS))
    parser.add_argument("--scenario-name", type=str, default="GR", help="Scenario name to process for the reports " + str(DEFAULT_SCENARIO_NAME))
    parser.add_argument("--message-size", type=str, default=DEFAULT_MESSAGE_SIZE, help="Message size used in the simulation filenames. Default is " + str(DEFAULT_MESSAGE_SIZE))

    args = parser.parse_args()
    ranges = args.ranges
    runs = args.runs
    scenario_prefix = args.scenario_name
    message_size = args.message_size

    print(f"Received ranges {ranges}, runs {runs}, and message size {message_size}")

    print("Splitting unified report data to individual reports...")
    split_unified_report(scenario_prefix, ranges, runs, message_size)
    
    
    with open("message.pkl", "wb") as f:
        dump(messages, f)
if __name__ == "__main__":
    main()
