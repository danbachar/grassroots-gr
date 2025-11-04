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
        (0, 0), (400, 0), (400, 200),
        (200, 200), (200, 400), (0, 400)
    ]

    # adjust for offset
    hall_points = [(x + x_offset, y + y_offset) for (x, y) in hall_points]

    hall = Room("hall", hall_points)
    hall.write_wkt(data_dir / f"{room_name}.wkt")
    
    rooms = {"hall": hall}

    clusters = [(0, 0), (100, 0), (200, 0), (300, 0),
                (0, 100), (100, 100), (200, 100), (300, 100),
                (0, 200), (100, 200), (200, 200), (300, 200),
                (0, 300), (100, 300), (200, 300), (300, 300)]
    clusters = [(x + x_offset, y + y_offset) for (x, y) in clusters]
    Room.draw_map(rooms, clusters=clusters, cluster_size=100, output_path=data_dir / f"{room_name}.png", 
                  image_width=500, image_height=500, mirrored=mirrored)
    