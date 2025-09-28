from pathlib import Path
from argparse import ArgumentParser

if __name__ == "__main__":
    
    settings_dir = Path("the-one")

    parser = ArgumentParser(description="Generate map files")
    parser.add_argument("--cluster_size", type=int, required=True, help="Cluster size (in meters)")
    parser.add_argument("--hosts_per_cluster", type=int, required=True, help="Number of hosts per cluster")
    parser.add_argument("--number_clusters", type=int, required=True, help="Number of clusters in room")
    parser.add_argument("--x_offset", type=int, required=False, default=0, help="Map X axis offset. Default is 0.")
    parser.add_argument("--y_offset", type=int, required=False, default=0, help="Map Y axis offset. Default is 0.")
    # The assumtion is that the room is L shaped, and width and height are equal, so that the room is actually comprised out 3 identical squares

    args = parser.parse_args()
    cluster_size = args.cluster_size
    hosts_per_cluster = args.hosts_per_cluster
    number_clusters = args.number_clusters
    x_offset = args.x_offset
    y_offset = args.y_offset

    settings_file = settings_dir / "GR-settings.txt"

    # Read the existing content of the settings file
    with open(settings_file, 'r') as file:
        lines = file.readlines()

    # Find the start of the group settings and prepare the new settings
    new_lines = []
    found_start = False
    for line in lines:
        if line.strip().startswith("#####[START]>Group"):
            found_start = True
            new_lines.append(line)  # Keep the start marker line
            new_lines.append(f"Scenario.nrofHostGroups = {number_clusters}\n")
            new_lines.append(f"Group.nrofHosts = {hosts_per_cluster}\n")
            new_lines.append(f"Group.numberOfClusters = {number_clusters}\n")
            new_lines.append(f"Group.clusterSize = {cluster_size}\n")
            new_lines.append(f"Group.offsetX = {x_offset}\n")
            new_lines.append(f"Group.offsetY = {y_offset}\n")
            for i in range(number_clusters):
                group_number = f"Group{i+1}"
                new_lines.append(f"{group_number}.clusterID = {i}\n")
                new_lines.append(f"{group_number}.groupID = random_stationary_{i}_\n")
        elif found_start and line.strip().startswith("Group"):
            # Skip old group lines if we are replacing them
            continue
        else:
            new_lines.append(line)

    # Write the modified content back to the file
    with open(settings_file, 'w') as file:
        file.writelines(new_lines)
