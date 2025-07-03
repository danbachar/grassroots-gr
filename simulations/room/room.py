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
    def draw_map(rooms, output_path="rooms.png", image_width=1000, image_height=1000, scale=1, wall_color="black", room_color="lightgray", line_width=0.5, background_color="white", x_offset = 0, y_offset = 0) -> None:

        img = Image.new("RGB", (image_width * scale, image_height * scale), background_color)
        draw = ImageDraw.Draw(img)

        for room in rooms.values():
            draw.polygon(
                [(x * scale, y * scale) for (x, y) in room.points],
                outline = wall_color,
                fill = room_color,
                width = int(line_width * scale)
            )
            
        try:
            img.save(output_path)
            print(f"Image saved to {output_path}")
        except Exception as e:
            print(f"Error saving image to {output_path}: {e}")

if __name__ == "__main__":
    pass