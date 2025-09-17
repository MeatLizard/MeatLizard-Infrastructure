"""
Tests for Content Moderation Service
"""
import pytest
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

from server.web.app.services.content_moderation_service import (
    ContentModerationService, 
    ModerationAction, 
    ModerationReason, 
    ReportType
)
from server.web.app.models import Video, VideoComment, User, VideoStatus, VideoVisibility


class TestContentModerationService:
    
    @pytest.fixture
    def service(self):
        return ContentModerationService()
    
    @pytest.fixture
    def mock_video(self):
        return Video(
            id=uuid.uuid4(),
            creator_id=uuid.uuid4(),
            title="Test Video with Inappropriate Content",
            description="This video contains some bad words and spam content",
            tags=["test", "inappropriate", "spam"],
            original_filename="test.mp4",
            original_s3_key="videos/test.mp4",
            file_size=1000000,
            duration_seconds=120,
            status=VideoStatus.ready,
            visibility=VideoVisibility.public,
            created_at=datetime.utcnow()
        )
    
    @pytest.fixture
    def mock_comment(self):
        return VideoComment(
            id=uuid.uuid4(),
            video_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            content="This is a spam comment with inappropriate language",
            created_at=datetime.utcnow()
        )
    
    @pytest.fixture
    def mock_user(self):
        return User(
            id=uuid.uuid4(),
            display_label="Test User",
            email="test@example.com",
            created_at=datetime.utcnow()
        )
    
    @pytest.mark.asyncio
    async def test_scan_video_content_success(self, service, mock_video):
        """Test successful video content scanning"""
        with patch.object(service, 'get_db_session') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_session
            
            # Mock video query
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = mock_video
            mock_session.execute.return_value = mock_result
            
            # Mock scan result storage
            with patch.object(service, '_store_scan_results'):
                result = await service.scan_video_content(
                    video_id=mock_video.id,
                    scan_metadata=True
                )
            
            assert "video_id" in result
            assert "scan_timestamp" in result
            assert "metadata_scan" in result
            assert "overall_risk" in result
            assert "recommended_action" in result
    
    @pytest.mark.asyncio
    async def test_scan_video_content_not_found(self, service):
        """Test video scanning with non-existent video"""
        with patch.object(service, 'get_db_session') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_session
            
            # Mock video query returning None
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result
            
            result = await service.scan_video_content(
                video_id=uuid.uuid4(),
                scan_metadata=True
            )
            
            assert result["success"] is False
            assert result["error"] == "video_not_found"
    
    @pytest.mark.asyncio
    async def test_scan_comment_content_success(self, service, mock_comment):
        """Test successful comment content scanning"""
        with patch.object(service, 'get_db_session') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_session
            
            # Mock comment query
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = mock_comment
            mock_session.execute.return_value = mock_result
            
            # Mock scan result storage
            with patch.object(service, '_store_scan_results'):
                result = await service.scan_comment_content(comment_id=mock_comment.id)
            
            assert "comment_id" in result
            assert "text_scan" in result
            assert "overall_risk" in result
    
    def test_scan_text_content_profanity(self, service):
        """Test text scanning for profanity"""
        text_with_profanity = "This is a fucking terrible video"
        result = service._scan_text_content(text_with_profanity)
        
        assert "profanity" in result["flags"]
        assert result["risk_level"] == "medium"
    
    def test_scan_text_content_spam(self, service):
        """Test text scanning for spam patterns"""
        spam_text = "Click here to buy now! Limited time offer!"
        result = service._scan_text_content(spam_text)
        
        assert "spam" in result["flags"]
        assert result["risk_level"] == "medium"
    
    def test_scan_text_content_hate_speech(self, service):
        """Test text scanning for hate speech"""
        hate_text = "I hate all people from that country"
        result = service._scan_text_content(hate_text)
        
        assert "hate_speech" in result["flags"]
        assert result["risk_level"] == "high"
    
    def test_scan_text_content_personal_info(self, service):
        """Test text scanning for personal information"""
        personal_info_text = "My email is test@example.com and SSN is 123-45-6789"
        result = service._scan_text_content(personal_info_text)
        
        assert "personal_info" in result["flags"]
        assert result["risk_level"] == "medium"
    
    def test_scan_text_content_clean(self, service):
        """Test text scanning with clean content"""
        clean_text = "This is a perfectly normal and appropriate comment"
        result = service._scan_text_content(clean_text)
        
        assert len(result["flags"]) == 0
        assert result["risk_level"] == "low"
    
    @pytest.mark.asyncio
    async def test_submit_content_report_success(self, service, mock_user):
        """Test successful content report submission"""
        content_id = uuid.uuid4()
        
        with patch.object(service, 'get_db_session') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_session
            
            # Mock existing report check (no existing report)
            with patch.object(service, '_check_existing_report', return_value=None):
                # Mock event logging
                with patch.object(service, '_log_moderation_event'):
                    # Mock report count check
                    with patch.object(service, '_get_report_count', return_value=1):
                        result = await service.submit_content_report(
                            reporter_id=mock_user.id,
                            content_type=ReportType.VIDEO,
                            content_id=content_id,
                            reason=ModerationReason.INAPPROPRIATE_CONTENT,
                            description="This video contains inappropriate content"
                        )
            
            assert result["success"] is True
            assert "report_id" in result
    
    @pytest.mark.asyncio
    async def test_submit_content_report_already_reported(self, service, mock_user):
        """Test content report submission when already reported"""
        content_id = uuid.uuid4()
        
        # Mock existing report
        with patch.object(service, '_check_existing_report', return_value=True):
            result = await service.submit_content_report(
                reporter_id=mock_user.id,
                content_type=ReportType.VIDEO,
                content_id=content_id,
                reason=ModerationReason.SPAM
            )
            
            assert result["success"] is False
            assert result["error"] == "already_reported"
    
    @pytest.mark.asyncio
    async def test_apply_moderation_action_success(self, service, mock_user):
        """Test successful moderation action application"""
        content_id = uuid.uuid4()
        
        with patch.object(service, 'get_db_session') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_session
            
            # Mock action execution
            with patch.object(service, '_execute_moderation_action', return_value=True):
                # Mock event logging and notifications
                with patch.object(service, '_log_moderation_event'):
                    with patch.object(service, '_notify_content_creator'):
                        result = await service.apply_moderation_action(
                            content_type="video",
                            content_id=content_id,
                            action=ModerationAction.HIDDEN,
                            reason=ModerationReason.INAPPROPRIATE_CONTENT,
                            moderator_id=mock_user.id,
                            notes="Content violates community guidelines"
                        )
            
            assert result["success"] is True
            assert "moderation_id" in result
    
    @pytest.mark.asyncio
    async def test_apply_moderation_action_failed(self, service, mock_user):
        """Test failed moderation action application"""
        content_id = uuid.uuid4()
        
        with patch.object(service, 'get_db_session') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_session
            
            # Mock action execution failure
            with patch.object(service, '_execute_moderation_action', return_value=False):
                result = await service.apply_moderation_action(
                    content_type="video",
                    content_id=content_id,
                    action=ModerationAction.REMOVED,
                    reason=ModerationReason.VIOLENCE,
                    moderator_id=mock_user.id
                )
            
            assert result["success"] is False
            assert result["error"] == "action_failed"
    
    def test_get_recommended_action(self, service):
        """Test moderation action recommendations based on risk level"""
        assert service._get_recommended_action("low") == ModerationAction.APPROVED
        assert service._get_recommended_action("medium") == ModerationAction.FLAGGED
        assert service._get_recommended_action("high") == ModerationAction.HIDDEN
        assert service._get_recommended_action("critical") == ModerationAction.REMOVED
    
    def test_risk_priority(self, service):
        """Test risk level priority calculation"""
        assert service._risk_priority("low") == 1
        assert service._risk_priority("medium") == 2
        assert service._risk_priority("high") == 3
        assert service._risk_priority("critical") == 4
    
    def test_load_profanity_patterns(self, service):
        """Test profanity pattern loading"""
        patterns = service._load_profanity_patterns()
        assert isinstance(patterns, list)
        assert len(patterns) > 0
        
        # Test that patterns are valid regex
        import re
        for pattern in patterns:
            try:
                re.compile(pattern)
            except re.error:
                pytest.fail(f"Invalid regex pattern: {pattern}")
    
    def test_load_spam_patterns(self, service):
        """Test spam pattern loading"""
        patterns = service._load_spam_patterns()
        assert isinstance(patterns, list)
        assert len(patterns) > 0
        
        # Test that patterns are valid regex
        import re
        for pattern in patterns:
            try:
                re.compile(pattern)
            except re.error:
                pytest.fail(f"Invalid regex pattern: {pattern}")
    
    @pytest.mark.asyncio
    async def test_get_moderation_queue(self, service, mock_user):
        """Test moderation queue retrieval"""
        with patch.object(service, 'get_db_session') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_session
            
            # Mock reports query
            mock_result = AsyncMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_session.execute.return_value = mock_result
            
            # Mock content details and scan results
            with patch.object(service, '_get_content_details', return_value={}):
                with patch.object(service, '_get_scan_results', return_value={}):
                    items = await service.get_moderation_queue(
                        moderator_id=mock_user.id,
                        limit=10
                    )
            
            assert isinstance(items, list)
    
    @pytest.mark.asyncio
    async def test_get_moderation_history(self, service):
        """Test moderation history retrieval"""
        content_id = uuid.uuid4()
        
        with patch.object(service, 'get_db_session') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_session
            
            # Mock history query
            mock_result = AsyncMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_session.execute.return_value = mock_result
            
            history = await service.get_moderation_history(content_id=content_id)
            
            assert isinstance(history, list)