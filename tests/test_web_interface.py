"""
Test the web interface integration.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_static_files():
    """Test that static file paths are correct."""
    
    server_dir = os.path.join(os.path.dirname(__file__), "..", "server")
    
    # Check that static files exist
    static_files = [
        "web/app/static/css/chat.css",
        "web/app/static/js/chat.js",
        "web/app/templates/index.html",
        "web/app/templates/chat.html"
    ]
    
    for file_path in static_files:
        full_path = os.path.join(server_dir, file_path)
        assert os.path.exists(full_path), f"Missing file: {file_path}"
        print(f"✓ {file_path} exists")
    
    print("\n✅ All static files exist!")

def test_template_content():
    """Test that templates contain expected content."""
    
    server_dir = os.path.join(os.path.dirname(__file__), "..", "server")
    
    # Test chat template
    chat_template = os.path.join(server_dir, "web/app/templates/chat.html")
    with open(chat_template, 'r') as f:
        content = f.read()
        assert "chat-window" in content
        assert "messages" in content
        assert "input-bar" in content
        assert "/static/css/chat.css" in content
        assert "/static/js/chat.js" in content
        print("✓ Chat template has required elements")
    
    # Test index template
    index_template = os.path.join(server_dir, "web/app/templates/index.html")
    with open(index_template, 'r') as f:
        content = f.read()
        assert "AI Chat System" in content
        assert "Start Chatting" in content
        assert "/chat" in content
        print("✓ Index template has required elements")
    
    print("\n✅ All template content tests passed!")

def test_css_structure():
    """Test that CSS file has required styles."""
    
    server_dir = os.path.join(os.path.dirname(__file__), "..", "server")
    css_file = os.path.join(server_dir, "web/app/static/css/chat.css")
    
    with open(css_file, 'r') as f:
        content = f.read()
        
        required_classes = [
            ".sidebar", ".chat-window", ".messages", ".bubble",
            ".input-bar", ".loading-overlay", ".bubble.user", ".bubble.bot"
        ]
        
        for css_class in required_classes:
            assert css_class in content, f"Missing CSS class: {css_class}"
            print(f"✓ {css_class} style exists")
    
    print("\n✅ All CSS structure tests passed!")

def test_javascript_structure():
    """Test that JavaScript file has required functionality."""
    
    server_dir = os.path.join(os.path.dirname(__file__), "..", "server")
    js_file = os.path.join(server_dir, "web/app/static/js/chat.js")
    
    with open(js_file, 'r') as f:
        content = f.read()
        
        required_functions = [
            "class ChatInterface", "initializeSession", "sendMessage",
            "addMessage", "updateStatus", "setLoading"
        ]
        
        for func in required_functions:
            assert func in content, f"Missing JavaScript function: {func}"
            print(f"✓ {func} exists")
    
    print("\n✅ All JavaScript structure tests passed!")

if __name__ == "__main__":
    print("Running web interface tests...")
    print("=" * 50)
    
    try:
        test_static_files()
        test_template_content()
        test_css_structure()
        test_javascript_structure()
        
        print("\n🎉 All web interface integration tests passed!")
        print("\nNote: API endpoint tests require httpx package and database setup.")
        print("Run the server with: python server/run_web_server.py")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)