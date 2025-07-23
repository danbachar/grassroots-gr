from room import Room
from pathlib import Path
from argparse import ArgumentParser
import pickle

if __name__ == "__main__":
    
    the_one_dir = Path("the-one")
    data_dir = Path("the-one/data")

    parser = ArgumentParser(description="Generate map files")
    parser.add_argument("--x_offset", type=int, required=False, default=0, help="Map X axis offset. Default is 0.")
    parser.add_argument("--y_offset", type=int, required=False, default=0, help="Map Y axis offset. Default is 0.")
    parser.add_argument("--scale", type=int, required=False, default=1, help="Scale of the map file. Default is 1.")
    parser.add_argument("--hosts", type=int, required=False, default=10, help="Number of hosts for the simulation. Default is 10.")
    parser.add_argument("--name", type=str, required=True, help="Room name")

    args = parser.parse_args()
    total_hosts = args.hosts
    x_offset = args.x_offset
    y_offset = args.y_offset
    scale = args.scale
    room_name = args.name
    
    # hardcoded for now
    hall_points = [
        (0, 0), (200, 0), (200, 200),
        (100, 200), (100, 100), (0, 100)
    ]

    # adjust for offset
    hall_points = [(x + x_offset, y + y_offset) for (x, y) in hall_points]

    hall = Room("hall", hall_points)
    hall.write_wkt(data_dir / f"{room_name}.wkt")
    
    rooms = {"hall": hall}
    
    Room.draw_map(rooms, output_path=data_dir / "hall.png", 
                  image_width=250, image_height=250, scale=scale,
                  x_offset=x_offset, y_offset=y_offset)
    