from pathlib import Path
from PIL import Image, ImageDraw

class Room:
    def __init__(self, name: str, points: list[tuple[float, float]]) -> None:
        self.name = name
        self.points = points

    def __repr__(self):        
        return f"Room({self.name}, Points: ({self.points}))"

    def write_wkt(self, file_path: Path) -> None:
        with open(file_path, 'w') as file:
            for (x, y) in self.points:
                file.write(f"POINT ({x} {y})\n")
    
    @staticmethod
    def draw_map(rooms, clusters=None, cluster_size=120.0, output_path="rooms.png", image_width=1000, image_height=1000, wall_color="black", room_color="lightgray", line_width=0.5, background_color="white", mirrored=False) -> None:

        img = Image.new("RGB", (image_width, image_height), background_color)
        draw = ImageDraw.Draw(img)

        for room in rooms.values():
            points = room.points
            if mirrored:
                points = [(image_width - x, y) for (x, y) in points]
                points.reverse()

            draw.polygon(
                [(x, y) for (x, y) in points],
                outline = wall_color,
                fill = room_color,
                width = int(line_width)
            )
        
        if clusters:
            Room.draw_clusters(draw, clusters, mirrored, cluster_size=cluster_size)

        try:
            img.save(output_path)
            print(f"Image saved to {output_path}")
        except Exception as e:
            print(f"Error saving image to {output_path}: {e}")

    @staticmethod
    def draw_clusters(draw, clusters, mirrored=False, color="red", line_width=1, cluster_size=120.0):
        for cluster in clusters:
            start_x, start_y = cluster

            if mirrored:
                start_x = draw.im.size[0] - start_x - cluster_size

            box = [
                (start_x, start_y),
                (start_x + cluster_size, start_y + cluster_size)
            ]
            
            draw.rectangle(box, outline=color, width=int(line_width))

if __name__ == "__main__":
    pass