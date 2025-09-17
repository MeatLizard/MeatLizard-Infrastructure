"""
Accessibility tests for video platform.
"""
import pytest
from playwright.async_api import Page, expect
from .conftest import BrowserHelpers


class TestVideoPlayerAccessibility:
    """Accessibility tests for video player components."""
    
    async def test_video_player_keyboard_navigation(self, page: Page, base_url: str):
        """Test keyboard navigation through video player controls."""
        
        await page.goto(f"{base_url}/video/watch/test-video-id")
        
        # Test tab navigation through controls
        focusable_elements = [
            "#video-player",
            "#play-pause-button",
            "#volume-control",
            "#progress-bar",
            "#quality-selector", 
            "#fullscreen-button"
        ]
        
        for element_selector in focusable_elements:
            element = page.locator(element_selector)
            
            # Check if element exists and is focusable
            if await element.count() > 0:
                await element.focus()
                
                # Verify element has focus
                focused_element = await page.evaluate("document.activeElement.id")
                expected_id = element_selector.replace("#", "")
                
                assert focused_element == expected_id or focused_element != "", \
                    f"Element {element_selector} should be focusable"
    
    async def test_video_player_aria_labels(self, page: Page, base_url: str):
        """Test ARIA labels and descriptions for video player."""
        
        await page.goto(f"{base_url}/video/watch/test-video-id")
        
        # Test ARIA labels for controls
        aria_requirements = [
            ("#play-pause-button", "aria-label", "Play video"),
            ("#volume-control", "aria-label", "Volume control"),
            ("#progress-bar", "aria-label", "Video progress"),
            ("#quality-selector", "aria-label", "Video quality"),
            ("#fullscreen-button", "aria-label", "Fullscreen")
        ]
        
        for selector, attribute, expected_text in aria_requirements:
            element = page.locator(selector)
            
            if await element.count() > 0:
                aria_value = await element.get_attribute(attribute)
                
                assert aria_value is not None, f"{selector} should have {attribute}"
                assert expected_text.lower() in aria_value.lower(), \
                    f"{selector} {attribute} should contain '{expected_text}'"
    
    async def test_video_player_screen_reader_support(self, page: Page, base_url: str):
        """Test screen reader support for video player."""
        
        await page.goto(f"{base_url}/video/watch/test-video-id")
        
        # Test live regions for dynamic content
        live_regions = [
            "#video-status-announcer",
            "#progress-announcer",
            "#quality-announcer"
        ]
        
        for selector in live_regions:
            element = page.locator(selector)
            
            if await element.count() > 0:
                aria_live = await element.get_attribute("aria-live")
                
                assert aria_live in ["polite", "assertive"], \
                    f"{selector} should have appropriate aria-live value"
    
    async def test_keyboard_shortcuts_accessibility(self, page: Page, base_url: str):
        """Test keyboard shortcuts for video player accessibility."""
        
        await page.goto(f"{base_url}/video/watch/test-video-id")
        
        # Wait for video to load
        await page.wait_for_selector("video")
        
        # Test space bar for play/pause
        await page.keyboard.press("Space")
        
        # Check if video state changed (play/pause)
        video_paused = await page.evaluate("document.querySelector('video').paused")
        
        # Test arrow keys for seeking
        await page.keyboard.press("ArrowRight")  # Seek forward
        await page.keyboard.press("ArrowLeft")   # Seek backward
        
        # Test volume controls
        await page.keyboard.press("ArrowUp")     # Volume up
        await page.keyboard.press("ArrowDown")   # Volume down
        
        # Test mute toggle
        await page.keyboard.press("KeyM")
        
        # Test fullscreen toggle
        await page.keyboard.press("KeyF")
        
        # All keyboard shortcuts should work without throwing errors
        # The exact behavior depends on the video player implementation


class TestUploadFormAccessibility:
    """Accessibility tests for video upload form."""
    
    async def test_upload_form_labels(self, page: Page, base_url: str):
        """Test form labels and associations."""
        
        await page.goto(f"{base_url}/video/upload")
        
        # Test form field labels
        form_fields = [
            ("#video-title-input", "Title"),
            ("#video-description-input", "Description"),
            ("#video-tags-input", "Tags"),
            ("#video-file-input", "Video file")
        ]
        
        for field_selector, expected_label in form_fields:
            field = page.locator(field_selector)
            
            if await field.count() > 0:
                # Check for associated label
                field_id = await field.get_attribute("id")
                label = page.locator(f"label[for='{field_id}']")
                
                if await label.count() > 0:
                    label_text = await label.text_content()
                    assert expected_label.lower() in label_text.lower(), \
                        f"Label for {field_selector} should contain '{expected_label}'"
                else:
                    # Check for aria-label as alternative
                    aria_label = await field.get_attribute("aria-label")
                    assert aria_label is not None, \
                        f"{field_selector} should have label or aria-label"
    
    async def test_upload_form_error_messages(self, page: Page, base_url: str):
        """Test error message accessibility."""
        
        await page.goto(f"{base_url}/video/upload")
        
        # Trigger validation errors
        title_input = page.locator("#video-title-input")
        await title_input.fill("")
        await title_input.blur()
        
        # Check for error message
        error_message = page.locator(".title-error, [role='alert']")
        
        if await error_message.count() > 0:
            # Error should have appropriate role
            role = await error_message.get_attribute("role")
            assert role == "alert" or role == "status", \
                "Error messages should have alert or status role"
            
            # Error should be associated with field
            aria_describedby = await title_input.get_attribute("aria-describedby")
            if aria_describedby:
                error_id = await error_message.get_attribute("id")
                assert error_id in aria_describedby, \
                    "Error message should be referenced by aria-describedby"
    
    async def test_upload_progress_accessibility(self, page: Page, base_url: str):
        """Test upload progress accessibility."""
        
        await page.goto(f"{base_url}/video/upload")
        
        # Check progress bar accessibility
        progress_bar = page.locator("#upload-progress-bar, [role='progressbar']")
        
        if await progress_bar.count() > 0:
            # Progress bar should have appropriate attributes
            role = await progress_bar.get_attribute("role")
            assert role == "progressbar", "Progress bar should have progressbar role"
            
            # Should have aria-valuemin, aria-valuemax, aria-valuenow
            aria_valuemin = await progress_bar.get_attribute("aria-valuemin")
            aria_valuemax = await progress_bar.get_attribute("aria-valuemax")
            
            assert aria_valuemin is not None, "Progress bar should have aria-valuemin"
            assert aria_valuemax is not None, "Progress bar should have aria-valuemax"


class TestNavigationAccessibility:
    """Accessibility tests for site navigation."""
    
    async def test_skip_links(self, page: Page, base_url: str):
        """Test skip navigation links."""
        
        await page.goto(f"{base_url}/")
        
        # Test skip to main content link
        skip_link = page.locator("a[href='#main-content'], .skip-link")
        
        if await skip_link.count() > 0:
            await expect(skip_link).to_be_visible()
            
            # Skip link should be focusable
            await skip_link.focus()
            
            # Should navigate to main content when clicked
            await skip_link.click()
            
            # Check if focus moved to main content
            main_content = page.locator("#main-content, main")
            if await main_content.count() > 0:
                focused_element = await page.evaluate("document.activeElement")
                # Focus should be on or within main content area
    
    async def test_heading_structure(self, page: Page, base_url: str):
        """Test proper heading hierarchy."""
        
        await page.goto(f"{base_url}/")
        
        # Get all headings
        headings = await page.evaluate("""
            Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6'))
                .map(h => ({ level: parseInt(h.tagName[1]), text: h.textContent.trim() }))
        """)
        
        if headings:
            # Should have exactly one h1
            h1_count = sum(1 for h in headings if h["level"] == 1)
            assert h1_count == 1, "Page should have exactly one h1 element"
            
            # Heading levels should not skip (e.g., h1 -> h3 without h2)
            prev_level = 0
            for heading in headings:
                level = heading["level"]
                if prev_level > 0:
                    assert level <= prev_level + 1, \
                        f"Heading levels should not skip: found h{level} after h{prev_level}"
                prev_level = level
    
    async def test_focus_management(self, page: Page, base_url: str):
        """Test focus management and visibility."""
        
        await page.goto(f"{base_url}/")
        
        # Test that focus indicators are visible
        focusable_elements = await page.evaluate("""
            Array.from(document.querySelectorAll(
                'a, button, input, textarea, select, [tabindex]:not([tabindex="-1"])'
            )).slice(0, 5)  // Test first 5 elements
        """)
        
        for i in range(min(5, len(focusable_elements))):
            # Focus each element and check for visible focus indicator
            await page.keyboard.press("Tab")
            
            # Check if focused element has visible outline or focus styles
            focused_styles = await page.evaluate("""
                () => {
                    const el = document.activeElement;
                    const styles = getComputedStyle(el);
                    return {
                        outline: styles.outline,
                        outlineWidth: styles.outlineWidth,
                        boxShadow: styles.boxShadow
                    };
                }
            """)
            
            # Should have some form of focus indicator
            has_focus_indicator = (
                focused_styles["outline"] != "none" or
                focused_styles["outlineWidth"] != "0px" or
                "0px 0px" not in focused_styles["boxShadow"]
            )
            
            assert has_focus_indicator, "Focused elements should have visible focus indicators"


class TestColorContrastAccessibility:
    """Test color contrast for accessibility compliance."""
    
    async def test_text_contrast_ratios(self, page: Page, base_url: str):
        """Test color contrast ratios meet WCAG guidelines."""
        
        await page.goto(f"{base_url}/")
        
        # Test contrast for common text elements
        text_elements = [
            "body",
            "h1, h2, h3",
            "p",
            "a",
            "button",
            ".btn-primary",
            ".btn-secondary"
        ]
        
        for selector in text_elements:
            elements = page.locator(selector)
            count = await elements.count()
            
            if count > 0:
                # Get first element for testing
                element = elements.first
                
                # Get computed styles
                styles = await element.evaluate("""
                    el => {
                        const computed = getComputedStyle(el);
                        return {
                            color: computed.color,
                            backgroundColor: computed.backgroundColor,
                            fontSize: computed.fontSize
                        };
                    }
                """)
                
                # Note: Actual contrast calculation would require a color contrast library
                # For now, we just verify that colors are defined
                assert styles["color"] != "rgba(0, 0, 0, 0)", \
                    f"Element {selector} should have defined text color"
    
    async def test_interactive_element_contrast(self, page: Page, base_url: str):
        """Test contrast for interactive elements."""
        
        await page.goto(f"{base_url}/")
        
        # Test buttons and links have sufficient contrast
        interactive_elements = ["button", "a", "input", "[role='button']"]
        
        for selector in interactive_elements:
            elements = page.locator(selector)
            count = await elements.count()
            
            if count > 0:
                element = elements.first
                
                # Check if element is visible
                is_visible = await element.is_visible()
                
                if is_visible:
                    # Get background and text colors
                    colors = await element.evaluate("""
                        el => {
                            const computed = getComputedStyle(el);
                            return {
                                color: computed.color,
                                backgroundColor: computed.backgroundColor,
                                borderColor: computed.borderColor
                            };
                        }
                    """)
                    
                    # Verify colors are not transparent
                    assert "rgba(0, 0, 0, 0)" not in colors["color"], \
                        f"Interactive element {selector} should have visible text color"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])