from room import Room
from pathlib import Path
from argparse import ArgumentParser

if __name__ == "__main__":
    
    the_one_dir = Path("the-one")
    data_dir = Path("the-one/data")

    parser = ArgumentParser(description="Generate map files")
    parser.add_argument("--x_offset", type=int, required=False, default=0, help="Map X axis offset. Default is 0.")
    parser.add_argument("--y_offset", type=int, required=False, default=0, help="Map Y axis offset. Default is 0.")
    parser.add_argument("--name", type=str, required=True, help="Room name")
    parser.add_argument("--mirrored", type=bool, required=False, default=False, help="Should the room be horizontally mirrored? Default is False.")

    args = parser.parse_args()
    x_offset = args.x_offset
    y_offset = args.y_offset
    room_name = args.name
    mirrored = args.mirrored
    
    # hardcoded for now
    hall_points = [
        (0, 0), (480, 0), (480, 240),
        (240, 240), (240, 480), (0, 480)
    ]

    # adjust for offset
    hall_points = [(x + x_offset, y + y_offset) for (x, y) in hall_points]

    hall = Room("hall", hall_points)
    hall.write_wkt(data_dir / f"{room_name}.wkt")
    
    rooms = {"hall": hall}

    clusters = [(0, 0), (120, 0), (240, 0), (360, 0),
                (0, 120), (120, 120), (240, 120), (360, 120),
                (0, 240), (120, 240), (240, 240), (360, 240),
                (0, 360), (120, 360), (240, 360), (360, 360)]
    clusters = [(x + x_offset, y + y_offset) for (x, y) in clusters]
    Room.draw_map(rooms, clusters=clusters, cluster_size=120, output_path=data_dir / f"{room_name}.png", 
                  image_width=580, image_height=580, mirrored=mirrored)
    