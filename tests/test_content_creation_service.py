
import pytest
from unittest.mock import patch

from server.web.app.services.content_creation_service import ContentCreationService

@pytest.fixture
def content_creation_service():
    return ContentCreationService(api_key="test_api_key")

@patch("openai.Completion.create")
def test_generate_caption(mock_create, content_creation_service):
    mock_create.return_value.choices[0].text = "This is a witty caption."
    
    caption = content_creation_service.generate_caption("This is some text.")
    
    assert caption == "This is a witty caption."

@patch("openai.Completion.create")
def test_rewrite_text(mock_create, content_creation_service):
    mock_create.return_value.choices[0].text = "This is the rewritten text."
    
    rewritten_text = content_creation_service.rewrite_text("This is the original text.")
    
    assert rewritten_text == "This is the rewritten text."
