# Acceptance Tests

This directory contains user acceptance tests for the private video platform using browser automation with Playwright.

## Overview

The acceptance tests verify that the video platform works correctly from a user's perspective by automating real browser interactions. These tests cover:

- **Video Upload UI**: Testing the complete video upload workflow
- **Video Playback UI**: Testing video player functionality and controls
- **User Interactions**: Testing likes, comments, playlists, and other user features
- **Cross-Browser Compatibility**: Testing across Chrome, Firefox, and Safari
- **Accessibility**: Testing keyboard navigation, screen readers, and WCAG compliance

## Prerequisites

1. **Python Dependencies**:
   ```bash
   pip install playwright pytest-playwright pytest-asyncio
   ```

2. **Playwright Browsers**:
   ```bash
   playwright install chromium firefox webkit
   ```

3. **Test Server**: The FastAPI server should be running on `http://localhost:8000` during tests.

## Test Structure

### Test Files

- `test_video_upload_ui.py` - Video upload form and workflow tests
- `test_video_playback_ui.py` - Video player functionality tests  
- `test_user_interactions.py` - User interaction features (likes, comments, playlists)
- `test_cross_browser_compatibility.py` - Cross-browser compatibility tests
- `test_accessibility.py` - Accessibility and WCAG compliance tests

### Configuration Files

- `conftest.py` - Test fixtures and browser setup
- `pytest.ini` - Pytest configuration and markers
- `test_runner.py` - Test runner script with different test modes

## Running Tests

### Basic Test Execution

Run all acceptance tests:
```bash
python tests/acceptance/test_runner.py
```

Run specific test file:
```bash
pytest tests/acceptance/test_video_upload_ui.py -v
```

### Cross-Browser Testing

Test across all browsers:
```bash
python tests/acceptance/test_runner.py cross-browser
```

Test specific browser:
```bash
pytest tests/acceptance/test_cross_browser_compatibility.py --browser=firefox -v
```

### Accessibility Testing

Run accessibility tests:
```bash
python tests/acceptance/test_runner.py accessibility
```

Run with specific markers:
```bash
pytest tests/acceptance/ -m accessibility -v
```

### All Tests

Run complete test suite:
```bash
python tests/acceptance/test_runner.py all
```

## Test Configuration

### Environment Variables

- `TEST_BASE_URL` - Base URL for the application (default: http://localhost:8000)
- `PYTEST_CURRENT_TEST` - Current test context

### Browser Options

Tests support the following browsers:
- `chromium` - Google Chrome/Chromium
- `firefox` - Mozilla Firefox  
- `webkit` - Safari/WebKit

### Viewport Configurations

Tests include responsive design testing with:
- Mobile: 375x667 (iPhone)
- Tablet: 768x1024 (iPad)
- Desktop: 1920x1080

## Test Features

### Video Upload Tests

- Form element presence and validation
- File selection and format validation
- Metadata input validation (title, description, tags)
- Quality preset selection
- Upload progress tracking
- Error handling and recovery
- Responsive design testing

### Video Playback Tests

- Player element presence
- Play/pause controls
- Volume control
- Quality selection
- Fullscreen functionality
- Keyboard shortcuts
- Progress tracking and resume
- Adaptive quality switching
- Error handling

### User Interaction Tests

- Like/dislike functionality
- Comment submission and validation
- Comment replies and moderation
- Playlist creation and management
- Playlist playback
- Content sharing

### Cross-Browser Tests

- Video format support (MP4, WebM, etc.)
- HLS streaming compatibility
- JavaScript API support
- CSS feature compatibility
- Media Source Extensions
- Performance APIs
- Storage APIs

### Accessibility Tests

- Keyboard navigation
- ARIA labels and descriptions
- Screen reader support
- Focus management
- Color contrast compliance
- Skip links and heading structure

## Test Data

### Test Files

Tests use sample video files from `test_media/`:
- `test_720p.mp4` - Sample 720p video for upload testing

### Mock Data

Tests create temporary files and mock data as needed for:
- Invalid file format testing
- Large file testing
- Network condition simulation

## Debugging Tests

### Headed Mode

Run tests with visible browser for debugging:
```bash
pytest tests/acceptance/test_video_upload_ui.py --headed
```

### Screenshots

Tests automatically capture screenshots on failure when using Playwright.

### Console Logging

Browser console messages are logged during test execution for debugging.

### Slow Motion

Add slow motion for debugging:
```bash
pytest tests/acceptance/test_video_upload_ui.py --slowmo=1000
```

## CI/CD Integration

### GitHub Actions

Example workflow for running acceptance tests:

```yaml
name: Acceptance Tests
on: [push, pull_request]

jobs:
  acceptance-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install -r server/requirements.txt
          playwright install --with-deps
      - name: Start test server
        run: |
          uvicorn server.web.app.main:app --host 0.0.0.0 --port 8000 &
          sleep 10
      - name: Run acceptance tests
        run: python tests/acceptance/test_runner.py all
```

### Docker

Run tests in Docker container:
```bash
docker run --rm -v $(pwd):/workspace -w /workspace \
  mcr.microsoft.com/playwright/python:v1.40.0-jammy \
  bash -c "pip install -r server/requirements.txt && python tests/acceptance/test_runner.py"
```

## Performance Considerations

### Test Execution Time

- Basic tests: ~2-5 minutes
- Cross-browser tests: ~10-15 minutes  
- Full test suite: ~20-30 minutes

### Resource Usage

- Memory: ~500MB per browser instance
- CPU: Moderate usage during test execution
- Network: Minimal (local server testing)

## Troubleshooting

### Common Issues

1. **Browser not found**: Run `playwright install`
2. **Server not running**: Start FastAPI server on port 8000
3. **Timeout errors**: Increase timeout values in test configuration
4. **File not found**: Ensure test media files exist in `test_media/`

### Debug Commands

Check Playwright installation:
```bash
playwright --version
```

List installed browsers:
```bash
playwright show-trace
```

### Test Isolation

Each test runs in a fresh browser context to ensure isolation and prevent test interference.

## Contributing

When adding new acceptance tests:

1. Follow the existing test structure and naming conventions
2. Use appropriate test markers for categorization
3. Include both positive and negative test cases
4. Test responsive design and accessibility
5. Add appropriate documentation and comments
6. Ensure tests are deterministic and not flaky

## Best Practices

1. **Page Object Pattern**: Use page objects for complex UI interactions
2. **Wait Strategies**: Use explicit waits instead of sleep()
3. **Test Data**: Use fixtures for test data management
4. **Error Handling**: Include proper error handling and cleanup
5. **Assertions**: Use Playwright's expect() for better error messages
6. **Isolation**: Ensure tests don't depend on each other
7. **Performance**: Keep tests focused and avoid unnecessary operations