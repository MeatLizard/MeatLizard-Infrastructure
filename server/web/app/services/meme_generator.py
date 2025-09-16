
from PIL import Image, ImageDraw, ImageFont

class MemeGenerator:
    def __init__(self, font_path: str = "impact.ttf"):
        self.font_path = font_path

    def generate_meme(self, image_path: str, top_text: str, bottom_text: str) -> Image:
        img = Image.open(image_path)
        draw = ImageDraw.Draw(img)
        
        font_size = int(img.width / 10)
        font = ImageFont.truetype(self.font_path, font_size)

        # Top text
        text_width, text_height = draw.textsize(top_text, font)
        x = (img.width - text_width) / 2
        y = 10
        draw.text((x, y), top_text, font=font, fill="white", stroke_width=2, stroke_fill="black")

        # Bottom text
        text_width, text_height = draw.textsize(bottom_text, font)
        x = (img.width - text_width) / 2
        y = img.height - text_height - 10
        draw.text((x, y), bottom_text, font=font, fill="white", stroke_width=2, stroke_fill="black")
        
        return img
