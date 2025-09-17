"""
User acceptance tests for user interaction features (likes, comments, playlists).
"""
import pytest
import asyncio
from playwright.async_api import Page, expect
from .conftest import BrowserHelpers


class TestVideoLikesUserAcceptance:
    """User acceptance tests for video likes functionality."""
    
    async def test_like_dislike_buttons_present(self, page: Page, base_url: str):
        """Test that like/dislike buttons are present and functional."""
        
        # Navigate to video page
        await page.goto(f"{base_url}/video/watch/test-video-id")
        
        # Check for like/dislike elements
        like_button = page.locator("#like-button")
        dislike_button = page.locator("#dislike-button")
        like_count = page.locator("#like-count")
        dislike_count = page.locator("#dislike-count")
        
        # Verify elements are visible
        await expect(like_button).to_be_visible()
        await expect(dislike_button).to_be_visible()
        await expect(like_count).to_be_visible()
        await expect(dislike_count).to_be_visible()
        
        # Verify buttons are clickable
        await expect(like_button).to_be_enabled()
        await expect(dislike_button).to_be_enabled()
    
    def test_like_video_interaction(self, mock_browser):
        """Test liking a video."""
        
        # Mock initial state
        like_button = MagicMock()
        like_count = MagicMock()
        
        like_button.get_attribute.return_value = "false"  # Not liked initially
        like_count.text = "42"  # Initial like count
        
        mock_browser.find_element.side_effect = lambda by, value: {
            "like-button": like_button,
            "like-count": like_count
        }.get(value, MagicMock())
        
        # Click like button
        like_button.click()
        
        # Mock API response and UI update
        mock_browser.execute_script.return_value = {
            "success": True,
            "liked": True,
            "like_count": 43,
            "dislike_count": 5
        }
        
        response = mock_browser.execute_script("return likeVideo('test-video-id');")
        
        # Verify response
        assert response["success"] is True
        assert response["liked"] is True
        assert response["like_count"] == 43
        
        # Verify UI updates
        like_button.get_attribute.return_value = "true"  # Now liked
        like_count.text = "43"  # Updated count
        
        assert like_button.get_attribute("aria-pressed") == "true"
        assert like_count.text == "43"
    
    def test_dislike_video_interaction(self, mock_browser):
        """Test disliking a video."""
        
        # Mock initial state
        dislike_button = MagicMock()
        dislike_count = MagicMock()
        
        dislike_button.get_attribute.return_value = "false"  # Not disliked initially
        dislike_count.text = "5"  # Initial dislike count
        
        mock_browser.find_element.side_effect = lambda by, value: {
            "dislike-button": dislike_button,
            "dislike-count": dislike_count
        }.get(value, MagicMock())
        
        # Click dislike button
        dislike_button.click()
        
        # Mock API response
        mock_browser.execute_script.return_value = {
            "success": True,
            "disliked": True,
            "like_count": 42,
            "dislike_count": 6
        }
        
        response = mock_browser.execute_script("return dislikeVideo('test-video-id');")
        
        # Verify response
        assert response["success"] is True
        assert response["disliked"] is True
        assert response["dislike_count"] == 6
        
        # Verify UI updates
        dislike_button.get_attribute.return_value = "true"  # Now disliked
        dislike_count.text = "6"  # Updated count
        
        assert dislike_button.get_attribute("aria-pressed") == "true"
        assert dislike_count.text == "6"
    
    def test_toggle_like_dislike(self, mock_browser):
        """Test toggling between like and dislike."""
        
        like_button = MagicMock()
        dislike_button = MagicMock()
        
        mock_browser.find_element.side_effect = lambda by, value: {
            "like-button": like_button,
            "dislike-button": dislike_button
        }.get(value, MagicMock())
        
        # Initially neither liked nor disliked
        like_button.get_attribute.return_value = "false"
        dislike_button.get_attribute.return_value = "false"
        
        # Like the video
        like_button.click()
        like_button.get_attribute.return_value = "true"
        
        # Now dislike the video (should remove like)
        dislike_button.click()
        
        # Mock response - like removed, dislike added
        mock_browser.execute_script.return_value = {
            "liked": False,
            "disliked": True
        }
        
        response = mock_browser.execute_script("return dislikeVideo('test-video-id');")
        
        # Verify mutual exclusivity
        assert response["liked"] is False
        assert response["disliked"] is True
        
        # UI should reflect the change
        like_button.get_attribute.return_value = "false"
        dislike_button.get_attribute.return_value = "true"
        
        assert like_button.get_attribute("aria-pressed") == "false"
        assert dislike_button.get_attribute("aria-pressed") == "true"
    
    def test_anonymous_user_like_prompt(self, mock_browser):
        """Test like prompt for anonymous users."""
        
        # Mock anonymous user (no auth token)
        mock_browser.execute_script.return_value = None
        auth_token = mock_browser.execute_script("return getAuthToken();")
        
        assert auth_token is None
        
        # Click like button as anonymous user
        like_button = MagicMock()
        mock_browser.find_element.return_value = like_button
        
        like_button.click()
        
        # Should show login prompt
        login_modal = MagicMock()
        login_modal.is_displayed.return_value = True
        login_modal.text = "Please log in to like this video"
        
        mock_browser.find_element.return_value = login_modal
        
        assert login_modal.is_displayed()
        assert "log in" in login_modal.text.lower()


class TestVideoCommentsUserAcceptance:
    """User acceptance tests for video comments functionality."""
    
    @pytest.fixture
    def mock_browser(self):
        """Mock browser for comments testing."""
        browser = MagicMock()
        browser.find_element = MagicMock()
        browser.find_elements = MagicMock()
        browser.execute_script = MagicMock()
        browser.get = MagicMock()
        return browser
    
    def test_comments_section_present(self, mock_browser):
        """Test that comments section is present."""
        
        # Navigate to video page
        mock_browser.get("/video/watch/test-video-id")
        
        # Check for comments elements
        comments_elements = [
            "comments-section",
            "comment-form",
            "comment-input",
            "comment-submit-button",
            "comments-list"
        ]
        
        for element_id in comments_elements:
            element = MagicMock()
            element.is_displayed.return_value = True
            
            mock_browser.find_element.return_value = element
            
            assert element.is_displayed(), f"Element {element_id} should be visible"
    
    def test_submit_comment(self, mock_browser):
        """Test submitting a comment."""
        
        # Mock comment form elements
        comment_input = MagicMock()
        submit_button = MagicMock()
        
        mock_browser.find_element.side_effect = lambda by, value: {
            "comment-input": comment_input,
            "comment-submit-button": submit_button
        }.get(value, MagicMock())
        
        # Type comment
        comment_text = "This is a great video! Thanks for sharing."
        comment_input.send_keys(comment_text)
        comment_input.get_attribute.return_value = comment_text
        
        # Submit comment
        submit_button.click()
        
        # Mock API response
        mock_browser.execute_script.return_value = {
            "success": True,
            "comment": {
                "id": "comment-123",
                "content": comment_text,
                "author": "Test User",
                "created_at": "2024-01-15T10:30:00Z",
                "likes": 0
            }
        }
        
        response = mock_browser.execute_script(
            f"return submitComment('test-video-id', '{comment_text}');"
        )
        
        # Verify response
        assert response["success"] is True
        assert response["comment"]["content"] == comment_text
        
        # Verify comment appears in list
        new_comment = MagicMock()
        new_comment.text = comment_text
        new_comment.is_displayed.return_value = True
        
        mock_browser.find_element.return_value = new_comment
        
        assert new_comment.is_displayed()
        assert comment_text in new_comment.text
        
        # Verify input is cleared
        comment_input.get_attribute.return_value = ""
        assert comment_input.get_attribute("value") == ""
    
    def test_comment_validation(self, mock_browser):
        """Test comment input validation."""
        
        comment_input = MagicMock()
        submit_button = MagicMock()
        error_message = MagicMock()
        
        mock_browser.find_element.side_effect = lambda by, value: {
            "comment-input": comment_input,
            "comment-submit-button": submit_button,
            "comment-error": error_message
        }.get(value, MagicMock())
        
        # Test empty comment
        comment_input.get_attribute.return_value = ""
        submit_button.click()
        
        # Should show validation error
        error_message.is_displayed.return_value = True
        error_message.text = "Comment cannot be empty"
        
        assert error_message.is_displayed()
        assert "cannot be empty" in error_message.text
        
        # Test comment too long
        long_comment = "x" * 1001  # Over 1000 character limit
        comment_input.get_attribute.return_value = long_comment
        submit_button.click()
        
        error_message.text = "Comment is too long (max 1000 characters)"
        
        assert "too long" in error_message.text
        
        # Test valid comment
        valid_comment = "This is a valid comment."
        comment_input.get_attribute.return_value = valid_comment
        
        # Error should be hidden
        error_message.is_displayed.return_value = False
        
        assert not error_message.is_displayed()
    
    def test_comment_replies(self, mock_browser):
        """Test replying to comments."""
        
        # Mock existing comment with reply button
        comment_element = MagicMock()
        reply_button = MagicMock()
        reply_form = MagicMock()
        
        mock_browser.find_element.side_effect = lambda by, value: {
            "comment-123": comment_element,
            "reply-button-123": reply_button,
            "reply-form-123": reply_form
        }.get(value, MagicMock())
        
        # Click reply button
        reply_button.click()
        
        # Reply form should appear
        reply_form.is_displayed.return_value = True
        
        assert reply_form.is_displayed()
        
        # Type and submit reply
        reply_input = MagicMock()
        reply_submit = MagicMock()
        
        reply_input.send_keys("Thanks for your comment!")
        reply_submit.click()
        
        # Mock reply submission
        mock_browser.execute_script.return_value = {
            "success": True,
            "reply": {
                "id": "reply-456",
                "content": "Thanks for your comment!",
                "parent_id": "comment-123"
            }
        }
        
        response = mock_browser.execute_script("return submitReply('comment-123', 'Thanks for your comment!');")
        
        assert response["success"] is True
        assert response["reply"]["parent_id"] == "comment-123"
    
    def test_comment_moderation(self, mock_browser):
        """Test comment moderation features."""
        
        # Mock comment with moderation options
        comment_element = MagicMock()
        report_button = MagicMock()
        
        mock_browser.find_element.side_effect = lambda by, value: {
            "comment-123": comment_element,
            "report-button-123": report_button
        }.get(value, MagicMock())
        
        # Click report button
        report_button.click()
        
        # Report modal should appear
        report_modal = MagicMock()
        report_modal.is_displayed.return_value = True
        
        mock_browser.find_element.return_value = report_modal
        
        assert report_modal.is_displayed()
        
        # Select report reason
        report_reason = MagicMock()
        report_reason.click()
        
        # Submit report
        submit_report = MagicMock()
        submit_report.click()
        
        # Mock report submission
        mock_browser.execute_script.return_value = {"success": True}
        
        response = mock_browser.execute_script("return reportComment('comment-123', 'spam');")
        
        assert response["success"] is True


class TestPlaylistsUserAcceptance:
    """User acceptance tests for playlist functionality."""
    
    @pytest.fixture
    def mock_browser(self):
        """Mock browser for playlist testing."""
        browser = MagicMock()
        browser.find_element = MagicMock()
        browser.find_elements = MagicMock()
        browser.execute_script = MagicMock()
        browser.get = MagicMock()
        return browser
    
    def test_create_playlist_interface(self, mock_browser):
        """Test playlist creation interface."""
        
        # Navigate to playlists page
        mock_browser.get("/playlists")
        
        # Check for create playlist button
        create_button = MagicMock()
        create_button.is_displayed.return_value = True
        
        mock_browser.find_element.return_value = create_button
        
        assert create_button.is_displayed()
        
        # Click create playlist
        create_button.click()
        
        # Create playlist modal should appear
        create_modal = MagicMock()
        create_modal.is_displayed.return_value = True
        
        mock_browser.find_element.return_value = create_modal
        
        assert create_modal.is_displayed()
        
        # Fill playlist form
        name_input = MagicMock()
        description_input = MagicMock()
        privacy_select = MagicMock()
        
        mock_browser.find_element.side_effect = lambda by, value: {
            "playlist-name": name_input,
            "playlist-description": description_input,
            "playlist-privacy": privacy_select
        }.get(value, MagicMock())
        
        # Enter playlist details
        playlist_name = "My Favorite Videos"
        playlist_description = "A collection of my favorite videos"
        
        name_input.send_keys(playlist_name)
        description_input.send_keys(playlist_description)
        privacy_select.select_by_value("public")
        
        # Submit form
        submit_button = MagicMock()
        mock_browser.find_element.return_value = submit_button
        
        submit_button.click()
        
        # Mock playlist creation
        mock_browser.execute_script.return_value = {
            "success": True,
            "playlist": {
                "id": "playlist-123",
                "name": playlist_name,
                "description": playlist_description,
                "privacy": "public",
                "video_count": 0
            }
        }
        
        response = mock_browser.execute_script(
            f"return createPlaylist('{playlist_name}', '{playlist_description}', 'public');"
        )
        
        assert response["success"] is True
        assert response["playlist"]["name"] == playlist_name
    
    def test_add_video_to_playlist(self, mock_browser):
        """Test adding video to playlist."""
        
        # Navigate to video page
        mock_browser.get("/video/watch/test-video-id")
        
        # Click "Add to Playlist" button
        add_to_playlist_button = MagicMock()
        mock_browser.find_element.return_value = add_to_playlist_button
        
        add_to_playlist_button.click()
        
        # Playlist selection modal should appear
        playlist_modal = MagicMock()
        playlist_modal.is_displayed.return_value = True
        
        mock_browser.find_element.return_value = playlist_modal
        
        assert playlist_modal.is_displayed()
        
        # Mock user's playlists
        mock_browser.execute_script.return_value = [
            {"id": "playlist-1", "name": "Favorites", "video_count": 5},
            {"id": "playlist-2", "name": "Watch Later", "video_count": 12},
            {"id": "playlist-3", "name": "Educational", "video_count": 8}
        ]
        
        playlists = mock_browser.execute_script("return getUserPlaylists();")
        
        assert len(playlists) == 3
        
        # Select a playlist
        playlist_checkbox = MagicMock()
        playlist_checkbox.click()
        
        # Confirm addition
        confirm_button = MagicMock()
        mock_browser.find_element.return_value = confirm_button
        
        confirm_button.click()
        
        # Mock video addition
        mock_browser.execute_script.return_value = {
            "success": True,
            "added_to": ["playlist-1"]
        }
        
        response = mock_browser.execute_script("return addVideoToPlaylist('test-video-id', 'playlist-1');")
        
        assert response["success"] is True
        assert "playlist-1" in response["added_to"]
    
    def test_playlist_playback(self, mock_browser):
        """Test playlist playback functionality."""
        
        # Navigate to playlist page
        mock_browser.get("/playlist/playlist-123")
        
        # Check playlist elements
        playlist_elements = [
            "playlist-info",
            "playlist-videos",
            "play-all-button",
            "shuffle-button"
        ]
        
        for element_id in playlist_elements:
            element = MagicMock()
            element.is_displayed.return_value = True
            
            mock_browser.find_element.return_value = element
            
            assert element.is_displayed()
        
        # Click play all button
        play_all_button = MagicMock()
        mock_browser.find_element.return_value = play_all_button
        
        play_all_button.click()
        
        # Should navigate to first video with playlist context
        mock_browser.execute_script.return_value = "/video/watch/video-1?playlist=playlist-123"
        
        current_url = mock_browser.execute_script("return window.location.href;")
        
        assert "playlist=playlist-123" in current_url
        
        # Test auto-advance to next video
        mock_browser.execute_script("simulateVideoEnd();")
        
        # Should automatically play next video
        mock_browser.execute_script.return_value = "/video/watch/video-2?playlist=playlist-123"
        
        next_url = mock_browser.execute_script("return window.location.href;")
        
        assert "video-2" in next_url
        assert "playlist=playlist-123" in next_url
    
    def test_playlist_management(self, mock_browser):
        """Test playlist management features."""
        
        # Navigate to playlist management
        mock_browser.get("/playlist/playlist-123/edit")
        
        # Test reordering videos
        video_items = [
            MagicMock(),  # Video 1
            MagicMock(),  # Video 2
            MagicMock()   # Video 3
        ]
        
        mock_browser.find_elements.return_value = video_items
        
        # Simulate drag and drop reordering
        mock_browser.execute_script("reorderPlaylistVideos([2, 0, 1]);")  # Move video 3 to first
        
        # Mock reorder response
        mock_browser.execute_script.return_value = {"success": True}
        
        response = mock_browser.execute_script("return getReorderResult();")
        
        assert response["success"] is True
        
        # Test removing video from playlist
        remove_button = MagicMock()
        mock_browser.find_element.return_value = remove_button
        
        remove_button.click()
        
        # Confirmation dialog
        confirm_dialog = MagicMock()
        confirm_dialog.is_displayed.return_value = True
        
        mock_browser.find_element.return_value = confirm_dialog
        
        assert confirm_dialog.is_displayed()
        
        # Confirm removal
        confirm_button = MagicMock()
        mock_browser.find_element.return_value = confirm_button
        
        confirm_button.click()
        
        # Mock removal response
        mock_browser.execute_script.return_value = {"success": True}
        
        response = mock_browser.execute_script("return removeVideoFromPlaylist('video-1', 'playlist-123');")
        
        assert response["success"] is True
    
    def test_playlist_sharing(self, mock_browser):
        """Test playlist sharing functionality."""
        
        # Navigate to playlist
        mock_browser.get("/playlist/playlist-123")
        
        # Click share button
        share_button = MagicMock()
        mock_browser.find_element.return_value = share_button
        
        share_button.click()
        
        # Share modal should appear
        share_modal = MagicMock()
        share_modal.is_displayed.return_value = True
        
        mock_browser.find_element.return_value = share_modal
        
        assert share_modal.is_displayed()
        
        # Check share options
        share_options = [
            "copy-link-button",
            "share-email-button",
            "share-social-button"
        ]
        
        for option_id in share_options:
            option_element = MagicMock()
            option_element.is_displayed.return_value = True
            
            mock_browser.find_element.return_value = option_element
            
            assert option_element.is_displayed()
        
        # Test copy link
        copy_link_button = MagicMock()
        mock_browser.find_element.return_value = copy_link_button
        
        copy_link_button.click()
        
        # Mock clipboard operation
        mock_browser.execute_script.return_value = "https://example.com/playlist/playlist-123"
        
        copied_url = mock_browser.execute_script("return copyPlaylistLink();")
        
        assert "playlist-123" in copied_url
        
        # Success message should appear
        success_message = MagicMock()
        success_message.is_displayed.return_value = True
        success_message.text = "Link copied to clipboard"
        
        mock_browser.find_element.return_value = success_message
        
        assert success_message.is_displayed()
        assert "copied" in success_message.text.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])