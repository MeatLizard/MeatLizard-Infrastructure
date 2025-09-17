"""
Configuration for acceptance tests with browser automation.
"""
import pytest
import asyncio
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from typing import AsyncGenerator
import os


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def browser() -> AsyncGenerator[Browser, None]:
    """Launch browser for testing."""
    async with async_playwright() as p:
        # Use Chromium for consistent testing
        browser = await p.chromium.launch(
            headless=True,  # Set to False for debugging
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-web-security",
                "--allow-running-insecure-content"
            ]
        )
        yield browser
        await browser.close()


@pytest.fixture(scope="function")
async def browser_context(browser: Browser) -> AsyncGenerator[BrowserContext, None]:
    """Create a new browser context for each test."""
    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        permissions=["camera", "microphone"],  # For media tests
        ignore_https_errors=True
    )
    yield context
    await context.close()


@pytest.fixture(scope="function")
async def page(browser_context: BrowserContext) -> AsyncGenerator[Page, None]:
    """Create a new page for each test."""
    page = await browser_context.new_page()
    
    # Set up console logging for debugging
    page.on("console", lambda msg: print(f"Console: {msg.text}"))
    page.on("pageerror", lambda error: print(f"Page Error: {error}"))
    
    yield page
    await page.close()


@pytest.fixture(scope="function")
async def authenticated_page(page: Page) -> Page:
    """Create an authenticated page with user session."""
    # Navigate to login page
    await page.goto("http://localhost:8000/auth/login")
    
    # Fill login form (mock authentication)
    await page.fill("#username", "test_user")
    await page.fill("#password", "test_password")
    await page.click("#login-button")
    
    # Wait for authentication to complete
    await page.wait_for_url("**/dashboard")
    
    return page


@pytest.fixture(scope="function")
async def mobile_page(browser_context: BrowserContext) -> AsyncGenerator[Page, None]:
    """Create a page with mobile viewport."""
    # Set mobile viewport
    await browser_context.set_viewport_size({"width": 375, "height": 667})
    
    page = await browser_context.new_page()
    yield page
    await page.close()


@pytest.fixture(scope="function")
async def tablet_page(browser_context: BrowserContext) -> AsyncGenerator[Page, None]:
    """Create a page with tablet viewport."""
    # Set tablet viewport
    await browser_context.set_viewport_size({"width": 768, "height": 1024})
    
    page = await browser_context.new_page()
    yield page
    await page.close()


@pytest.fixture
def test_video_file():
    """Path to test video file."""
    return os.path.join(os.path.dirname(__file__), "..", "..", "test_media", "test_720p.mp4")


@pytest.fixture
def base_url():
    """Base URL for the application."""
    return os.getenv("TEST_BASE_URL", "http://localhost:8000")


class BrowserHelpers:
    """Helper methods for browser automation tests."""
    
    @staticmethod
    async def wait_for_video_load(page: Page, timeout: int = 30000):
        """Wait for video to load and be ready for playback."""
        await page.wait_for_function(
            "document.querySelector('video') && document.querySelector('video').readyState >= 3",
            timeout=timeout
        )
    
    @staticmethod
    async def wait_for_upload_complete(page: Page, timeout: int = 60000):
        """Wait for video upload to complete."""
        await page.wait_for_selector(".upload-success", timeout=timeout)
    
    @staticmethod
    async def simulate_network_condition(page: Page, condition: str):
        """Simulate different network conditions."""
        conditions = {
            "slow": {"download": 500 * 1024, "upload": 500 * 1024, "latency": 2000},
            "fast": {"download": 10 * 1024 * 1024, "upload": 10 * 1024 * 1024, "latency": 10},
            "offline": {"download": 0, "upload": 0, "latency": 0}
        }
        
        if condition in conditions:
            await page.context.set_extra_http_headers({"Connection": condition})
    
    @staticmethod
    async def check_accessibility(page: Page):
        """Run basic accessibility checks."""
        # Check for alt text on images
        images_without_alt = await page.evaluate("""
            Array.from(document.querySelectorAll('img')).filter(img => !img.alt).length
        """)
        
        # Check for proper heading structure
        headings = await page.evaluate("""
            Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6')).map(h => h.tagName)
        """)
        
        # Check for form labels
        unlabeled_inputs = await page.evaluate("""
            Array.from(document.querySelectorAll('input, textarea, select')).filter(input => {
                return !input.labels || input.labels.length === 0;
            }).length
        """)
        
        return {
            "images_without_alt": images_without_alt,
            "headings": headings,
            "unlabeled_inputs": unlabeled_inputs
        }


@pytest.fixture
def browser_helpers():
    """Provide browser helper methods."""
    return BrowserHelpers