
import pytest
from PIL import Image
import os

from server.web.app.services.meme_generator import MemeGenerator

@pytest.fixture
def meme_generator():
    # You'll need to provide a path to a font file for this test to work.
    # For example, you can download "Impact.ttf" and place it in the tests directory.
    font_path = "impact.ttf"
    if not os.path.exists(font_path):
        pytest.skip("Font file not found.")
        
    return MemeGenerator(font_path)

def test_generate_meme(meme_generator):
    # Create a dummy image for testing
    image_path = "test_image.png"
    img = Image.new('RGB', (500, 500), color = 'red')
    img.save(image_path)
    
    top_text = "Top Text"
    bottom_text = "Bottom Text"
    
    meme = meme_generator.generate_meme(image_path, top_text, bottom_text)
    
    assert meme is not None
    assert meme.size == (500, 500)
    
    # Clean up the dummy image
    os.remove(image_path)
