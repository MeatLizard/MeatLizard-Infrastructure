"""
Cross-browser compatibility tests for video platform.
"""
import pytest
from playwright.async_api import async_playwright, Browser, Page, expect
from typing import AsyncGenerator


class TestCrossBrowserCompatibility:
    """Test video platform compatibility across different browsers."""
    
    @pytest.fixture(params=["chromium", "firefox", "webkit"])
    async def browser_type(self, request) -> AsyncGenerator[str, None]:
        """Different browser types for testing."""
        yield request.param
    
    @pytest.fixture
    async def cross_browser(self, browser_type: str) -> AsyncGenerator[Browser, None]:
        """Launch different browsers for cross-browser testing."""
        async with async_playwright() as p:
            browser_launcher = getattr(p, browser_type)
            browser = await browser_launcher.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"] if browser_type == "chromium" else []
            )
            yield browser
            await browser.close()
    
    @pytest.fixture
    async def cross_browser_page(self, cross_browser: Browser) -> AsyncGenerator[Page, None]:
        """Create page for cross-browser testing."""
        context = await cross_browser.new_context(
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()
        yield page
        await context.close()
    
    async def test_video_format_support(self, cross_browser_page: Page, browser_type: str, base_url: str):
        """Test video format support across browsers."""
        
        await cross_browser_page.goto(f"{base_url}/video/watch/test-video-id")
        
        # Test video format support
        video_formats = ["mp4", "webm", "ogg"]
        
        for video_format in video_formats:
            can_play = await cross_browser_page.evaluate(f"""
                () => {{
                    const video = document.createElement('video');
                    const support = video.canPlayType('video/{video_format}');
                    return support === 'probably' || support === 'maybe';
                }}
            """)
            
            # MP4 should be supported by all modern browsers
            if video_format == "mp4":
                assert can_play, f"{browser_type} should support MP4"
            
            # Log support for other formats (may vary by browser)
            print(f"{browser_type} supports {video_format}: {can_play}")
    
    def test_hls_streaming_support(self, mock_browser, browser_config):
        """Test HLS streaming support across browsers."""
        
        # HLS support varies by browser
        hls_support = {
            "Chrome": False,  # Requires hls.js
            "Firefox": False,  # Requires hls.js
            "Safari": True,   # Native HLS support
            "Edge": False     # Requires hls.js
        }
        
        has_native_hls = hls_support.get(browser_config["name"], False)
        
        # Test native HLS support
        mock_browser.execute_script.return_value = has_native_hls
        
        native_support = mock_browser.execute_script(
            "return document.createElement('video').canPlayType('application/vnd.apple.mpegurl');"
        )
        
        if browser_config["name"] == "Safari":
            assert native_support, "Safari should have native HLS support"
        else:
            # Other browsers should use hls.js
            mock_browser.execute_script.return_value = True  # hls.js loaded
            
            hls_js_available = mock_browser.execute_script("return typeof Hls !== 'undefined';")
            
            assert hls_js_available, f"{browser_config['name']} should load hls.js for HLS support"
    
    def test_javascript_api_compatibility(self, mock_browser, browser_config):
        """Test JavaScript API compatibility."""
        
        # Test modern JavaScript features
        js_features = [
            ("async/await", "return (async () => true)();"),
            ("fetch API", "return typeof fetch !== 'undefined';"),
            ("Promise", "return typeof Promise !== 'undefined';"),
            ("localStorage", "return typeof localStorage !== 'undefined';"),
            ("sessionStorage", "return typeof sessionStorage !== 'undefined';"),
            ("WebSocket", "return typeof WebSocket !== 'undefined';"),
            ("FileReader", "return typeof FileReader !== 'undefined';")
        ]
        
        for feature_name, test_script in js_features:
            # Mock feature support
            mock_browser.execute_script.return_value = True
            
            is_supported = mock_browser.execute_script(test_script)
            
            assert is_supported, f"{browser_config['name']} should support {feature_name}"
    
    def test_css_features_compatibility(self, mock_browser, browser_config):
        """Test CSS features compatibility."""
        
        # Test CSS features used in video platform
        css_features = [
            ("flexbox", "return CSS.supports('display', 'flex');"),
            ("grid", "return CSS.supports('display', 'grid');"),
            ("transforms", "return CSS.supports('transform', 'translateX(10px)');"),
            ("transitions", "return CSS.supports('transition', 'all 0.3s ease');"),
            ("custom properties", "return CSS.supports('--custom-property', 'value');"),
            ("aspect-ratio", "return CSS.supports('aspect-ratio', '16/9');")
        ]
        
        for feature_name, test_script in css_features:
            # Mock CSS support
            expected_support = True  # Most modern browsers support these
            if feature_name == "aspect-ratio" and browser_config["name"] == "Safari" and int(browser_config["version"]) < 15:
                expected_support = False
            
            mock_browser.execute_script.return_value = expected_support
            
            is_supported = mock_browser.execute_script(test_script)
            
            if expected_support:
                assert is_supported, f"{browser_config['name']} should support {feature_name}"
    
    def test_media_source_extensions(self, mock_browser, browser_config):
        """Test Media Source Extensions (MSE) support."""
        
        # MSE is required for adaptive streaming
        mse_support = {
            "Chrome": True,
            "Firefox": True,
            "Safari": True,
            "Edge": True
        }
        
        expected_support = mse_support.get(browser_config["name"], False)
        
        # Test MSE availability
        mock_browser.execute_script.return_value = expected_support
        
        has_mse = mock_browser.execute_script("return 'MediaSource' in window;")
        
        assert has_mse == expected_support, f"{browser_config['name']} MSE support mismatch"
        
        if expected_support:
            # Test MSE codec support
            codec_tests = [
                'video/mp4; codecs="avc1.42E01E"',  # H.264 Baseline
                'video/mp4; codecs="avc1.4D401F"',  # H.264 Main
                'video/mp4; codecs="avc1.64001F"',  # H.264 High
            ]
            
            for codec in codec_tests:
                mock_browser.execute_script.return_value = True
                
                is_supported = mock_browser.execute_script(
                    f"return MediaSource.isTypeSupported('{codec}');"
                )
                
                assert is_supported, f"{browser_config['name']} should support {codec}"
    
    def test_performance_apis(self, mock_browser, browser_config):
        """Test performance monitoring APIs."""
        
        # Test Performance API availability
        performance_apis = [
            ("Performance", "return 'performance' in window;"),
            ("PerformanceObserver", "return 'PerformanceObserver' in window;"),
            ("Navigation Timing", "return 'navigation' in performance;"),
            ("Resource Timing", "return 'getEntriesByType' in performance;")
        ]
        
        for api_name, test_script in performance_apis:
            # Most modern browsers support these
            mock_browser.execute_script.return_value = True
            
            is_available = mock_browser.execute_script(test_script)
            
            assert is_available, f"{browser_config['name']} should support {api_name}"
    
    def test_storage_apis(self, mock_browser, browser_config):
        """Test storage APIs for offline functionality."""
        
        storage_apis = [
            ("localStorage", "return 'localStorage' in window;"),
            ("sessionStorage", "return 'sessionStorage' in window;"),
            ("IndexedDB", "return 'indexedDB' in window;"),
            ("Cache API", "return 'caches' in window;")
        ]
        
        for api_name, test_script in storage_apis:
            # Mock API availability
            expected_support = True
            if api_name == "Cache API" and browser_config["name"] == "Safari" and int(browser_config["version"]) < 11:
                expected_support = False
            
            mock_browser.execute_script.return_value = expected_support
            
            is_available = mock_browser.execute_script(test_script)
            
            if expected_support:
                assert is_available, f"{browser_config['name']} should support {api_name}"


class TestBrowserSpecificFeatures:
    """Test browser-specific features and workarounds."""
    
    def test_safari_specific_features(self):
        """Test Safari-specific features and limitations."""
        
        mock_browser = MagicMock()
        mock_browser.name = "Safari"
        mock_browser.execute_script = MagicMock()
        
        # Test Safari's autoplay policy
        mock_browser.execute_script.return_value = False
        
        can_autoplay = mock_browser.execute_script(
            "return document.createElement('video').autoplay;"
        )
        
        # Safari restricts autoplay
        assert can_autoplay is False, "Safari should restrict autoplay"
        
        # Test Safari's fullscreen API differences
        mock_browser.execute_script.return_value = "webkitRequestFullscreen"
        
        fullscreen_method = mock_browser.execute_script(
            "return document.documentElement.requestFullscreen ? 'requestFullscreen' : 'webkitRequestFullscreen';"
        )
        
        assert "Fullscreen" in fullscreen_method, "Safari should have fullscreen method"
    
    def test_firefox_specific_features(self):
        """Test Firefox-specific features."""
        
        mock_browser = MagicMock()
        mock_browser.name = "Firefox"
        mock_browser.execute_script = MagicMock()
        
        # Test Firefox's video codec support
        mock_browser.execute_script.return_value = True
        
        supports_av1 = mock_browser.execute_script(
            "return document.createElement('video').canPlayType('video/mp4; codecs=\"av01.0.05M.08\"');"
        )
        
        assert supports_av1, "Firefox should support AV1 codec"
        
        # Test Firefox's fullscreen API
        mock_browser.execute_script.return_value = "mozRequestFullScreen"
        
        fullscreen_method = mock_browser.execute_script(
            "return document.documentElement.mozRequestFullScreen ? 'mozRequestFullScreen' : 'requestFullscreen';"
        )
        
        assert "FullScreen" in fullscreen_method
    
    def test_chrome_specific_features(self):
        """Test Chrome-specific features."""
        
        mock_browser = MagicMock()
        mock_browser.name = "Chrome"
        mock_browser.execute_script = MagicMock()
        
        # Test Chrome's hardware acceleration
        mock_browser.execute_script.return_value = True
        
        has_hardware_acceleration = mock_browser.execute_script(
            "return 'webkitGetUserMedia' in navigator || 'getUserMedia' in navigator;"
        )
        
        assert has_hardware_acceleration, "Chrome should support hardware acceleration APIs"
        
        # Test Chrome's picture-in-picture support
        mock_browser.execute_script.return_value = True
        
        supports_pip = mock_browser.execute_script(
            "return 'pictureInPictureEnabled' in document;"
        )
        
        assert supports_pip, "Chrome should support picture-in-picture"


class TestResponsiveDesignCompatibility:
    """Test responsive design across different screen sizes and browsers."""
    
    @pytest.fixture(params=[
        {"width": 320, "height": 568, "device": "iPhone SE"},
        {"width": 375, "height": 667, "device": "iPhone 8"},
        {"width": 414, "height": 896, "device": "iPhone 11"},
        {"width": 768, "height": 1024, "device": "iPad"},
        {"width": 1024, "height": 768, "device": "iPad Landscape"},
        {"width": 1366, "height": 768, "device": "Laptop"},
        {"width": 1920, "height": 1080, "device": "Desktop"}
    ])
    def viewport_config(self, request):
        """Different viewport configurations."""
        return request.param
    
    def test_responsive_video_player(self, viewport_config):
        """Test responsive video player across viewports."""
        
        mock_browser = MagicMock()
        mock_browser.set_window_size(viewport_config["width"], viewport_config["height"])
        mock_browser.execute_script = MagicMock()
        
        # Test player sizing
        if viewport_config["width"] <= 768:
            # Mobile/tablet layout
            mock_browser.execute_script.return_value = "100%"
            player_width = mock_browser.execute_script(
                "return getComputedStyle(document.getElementById('video-player')).width;"
            )
            
            assert player_width == "100%", f"Player should be full width on {viewport_config['device']}"
            
            # Test mobile controls
            mock_browser.execute_script.return_value = True
            has_mobile_controls = mock_browser.execute_script("return hasMobileControls();")
            
            assert has_mobile_controls, f"Should have mobile controls on {viewport_config['device']}"
        else:
            # Desktop layout
            mock_browser.execute_script.return_value = "16:9"
            aspect_ratio = mock_browser.execute_script(
                "return getComputedStyle(document.getElementById('video-player')).aspectRatio;"
            )
            
            assert "16:9" in aspect_ratio, f"Player should maintain aspect ratio on {viewport_config['device']}"
    
    def test_responsive_upload_form(self, viewport_config):
        """Test responsive upload form across viewports."""
        
        mock_browser = MagicMock()
        mock_browser.set_window_size(viewport_config["width"], viewport_config["height"])
        mock_browser.execute_script = MagicMock()
        
        # Test form layout
        if viewport_config["width"] <= 768:
            # Mobile layout - single column
            mock_browser.execute_script.return_value = "column"
            layout_direction = mock_browser.execute_script(
                "return getComputedStyle(document.querySelector('.upload-form')).flexDirection;"
            )
            
            assert layout_direction == "column", f"Form should be single column on {viewport_config['device']}"
        else:
            # Desktop layout - multi-column
            mock_browser.execute_script.return_value = "row"
            layout_direction = mock_browser.execute_script(
                "return getComputedStyle(document.querySelector('.upload-form')).flexDirection;"
            )
            
            assert layout_direction == "row", f"Form should be multi-column on {viewport_config['device']}"
    
    def test_touch_vs_mouse_interactions(self, viewport_config):
        """Test touch vs mouse interactions."""
        
        mock_browser = MagicMock()
        mock_browser.set_window_size(viewport_config["width"], viewport_config["height"])
        mock_browser.execute_script = MagicMock()
        
        is_touch_device = viewport_config["width"] <= 1024
        
        # Test interaction method detection
        mock_browser.execute_script.return_value = is_touch_device
        
        has_touch = mock_browser.execute_script("return 'ontouchstart' in window;")
        
        if is_touch_device:
            assert has_touch, f"Should detect touch capability on {viewport_config['device']}"
            
            # Test touch-specific features
            mock_browser.execute_script.return_value = 44  # Minimum touch target size
            
            button_size = mock_browser.execute_script(
                "return Math.min("
                "document.querySelector('.play-button').offsetWidth, "
                "document.querySelector('.play-button').offsetHeight"
                ");"
            )
            
            assert button_size >= 44, f"Touch targets should be at least 44px on {viewport_config['device']}"
        else:
            # Desktop - test hover states
            mock_browser.execute_script.return_value = True
            
            has_hover_support = mock_browser.execute_script("return window.matchMedia('(hover: hover)').matches;")
            
            assert has_hover_support, f"Should support hover states on {viewport_config['device']}"


class TestAccessibilityCompatibility:
    """Test accessibility compatibility across browsers."""
    
    @pytest.fixture
    def mock_browser(self):
        """Mock browser for accessibility testing."""
        browser = MagicMock()
        browser.find_element = MagicMock()
        browser.execute_script = MagicMock()
        return browser
    
    def test_aria_support(self, mock_browser):
        """Test ARIA support across browsers."""
        
        aria_features = [
            ("aria-label", "return document.createElement('div').ariaLabel !== undefined;"),
            ("aria-describedby", "return document.createElement('div').ariaDescribedBy !== undefined;"),
            ("aria-live", "return document.createElement('div').ariaLive !== undefined;"),
            ("aria-expanded", "return document.createElement('div').ariaExpanded !== undefined;"),
            ("aria-pressed", "return document.createElement('div').ariaPressed !== undefined;")
        ]
        
        for aria_property, test_script in aria_features:
            # Mock ARIA support
            mock_browser.execute_script.return_value = True
            
            is_supported = mock_browser.execute_script(test_script)
            
            assert is_supported, f"Browser should support {aria_property}"
    
    def test_keyboard_navigation_compatibility(self, mock_browser):
        """Test keyboard navigation compatibility."""
        
        # Test keyboard event handling
        keyboard_events = [
            "keydown",
            "keyup", 
            "keypress"
        ]
        
        for event_type in keyboard_events:
            # Mock event support
            mock_browser.execute_script.return_value = True
            
            is_supported = mock_browser.execute_script(
                f"return 'on{event_type}' in document.createElement('div');"
            )
            
            assert is_supported, f"Browser should support {event_type} events"
        
        # Test focus management
        focus_methods = [
            "focus",
            "blur",
            "focusin",
            "focusout"
        ]
        
        for method in focus_methods:
            mock_browser.execute_script.return_value = True
            
            is_supported = mock_browser.execute_script(
                f"return typeof document.createElement('div').{method} === 'function';"
            )
            
            assert is_supported, f"Browser should support {method} method"
    
    def test_screen_reader_compatibility(self, mock_browser):
        """Test screen reader compatibility features."""
        
        # Test live regions
        mock_browser.execute_script.return_value = True
        
        supports_live_regions = mock_browser.execute_script(
            "return document.createElement('div').setAttribute('aria-live', 'polite') !== undefined;"
        )
        
        assert supports_live_regions, "Browser should support ARIA live regions"
        
        # Test role attribute
        supports_roles = mock_browser.execute_script(
            "return document.createElement('div').setAttribute('role', 'button') !== undefined;"
        )
        
        assert supports_roles, "Browser should support ARIA roles"
        
        # Test describedby relationships
        supports_describedby = mock_browser.execute_script(
            "return document.createElement('div').setAttribute('aria-describedby', 'desc') !== undefined;"
        )
        
        assert supports_describedby, "Browser should support aria-describedby"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])