"""
Tests for Imported Content Service.
"""
import pytest
from datetime import datetime, timedelta

from server.web.app.services.imported_content_service import ImportedContentService
from server.web.app.models import User, Video, ImportJob, VideoStatus, VideoVisibility, ImportStatus


class TestImportedContentService:
    """Test cases for ImportedContentService"""
    
    @pytest.fixture
    async def service(self, db_session):
        """Create ImportedContentService instance"""
        return ImportedContentService(db_session)
    
    @pytest.fixture
    async def test_user(self, db_session):
        """Create test user"""
        user = User(
            display_label="Test User",
            email="test@example.com"
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user
    
    @pytest.fixture
    async def test_video_with_import(self, db_session, test_user):
        """Create test video with associated import job"""
        # Create video
        video = Video(
            creator_id=test_user.id,
            title="Test Imported Video",
            description="Test description",
            original_filename="test.mp4",
            original_s3_key="test/video.mp4",
            file_size=1000000,
            duration_seconds=120,
            status=VideoStatus.ready,
            visibility=VideoVisibility.private
        )
        db_session.add(video)
        await db_session.commit()
        await db_session.refresh(video)
        
        # Create import job
        import_job = ImportJob(
            source_url="https://youtube.com/watch?v=test",
            platform="YouTube",
            import_config={"max_height": 720},
            requested_by=test_user.id,
            status=ImportStatus.completed,
            original_title="Original Test Video",
            original_uploader="Original Creator",
            original_upload_date=datetime.utcnow() - timedelta(days=30),
            original_duration=120,
            original_view_count=1000,
            original_like_count=50,
            video_id=video.id
        )
        db_session.add(import_job)
        await db_session.commit()
        await db_session.refresh(import_job)
        
        return video, import_job
    
    async def test_get_imported_videos(self, service, test_video_with_import):
        """Test getting imported videos"""
        video, import_job = test_video_with_import
        
        imported_videos = await service.get_imported_videos(
            user_id=str(video.creator_id)
        )
        
        assert len(imported_videos) == 1
        
        imported_video = imported_videos[0]
        assert imported_video["id"] == str(video.id)
        assert imported_video["title"] == video.title
        assert imported_video["attribution"]["source_url"] == import_job.source_url
        assert imported_video["attribution"]["platform"] == import_job.platform
        assert imported_video["attribution"]["original_title"] == import_job.original_title
    
    async def test_get_imported_videos_with_filters(self, service, test_video_with_import):
        """Test getting imported videos with filters"""
        video, import_job = test_video_with_import
        
        # Filter by platform
        youtube_videos = await service.get_imported_videos(
            user_id=str(video.creator_id),
            platform="YouTube"
        )
        assert len(youtube_videos) == 1
        
        # Filter by different platform
        tiktok_videos = await service.get_imported_videos(
            user_id=str(video.creator_id),
            platform="TikTok"
        )
        assert len(tiktok_videos) == 0
        
        # Filter by status
        ready_videos = await service.get_imported_videos(
            user_id=str(video.creator_id),
            status=VideoStatus.ready
        )
        assert len(ready_videos) == 1
    
    async def test_get_imported_video_by_id(self, service, test_video_with_import):
        """Test getting specific imported video by ID"""
        video, import_job = test_video_with_import
        
        imported_video = await service.get_imported_video_by_id(str(video.id))
        
        assert imported_video is not None
        assert imported_video["id"] == str(video.id)
        assert imported_video["title"] == video.title
        assert imported_video["attribution"]["source_url"] == import_job.source_url
        assert imported_video["creator"]["id"] == str(video.creator_id)
    
    async def test_get_imported_video_by_id_not_found(self, service):
        """Test getting non-existent imported video"""
        result = await service.get_imported_video_by_id("00000000-0000-0000-0000-000000000000")
        
        assert result is None
    
    async def test_update_imported_video_metadata(self, service, test_video_with_import):
        """Test updating imported video metadata"""
        video, import_job = test_video_with_import
        
        success = await service.update_imported_video_metadata(
            video_id=str(video.id),
            title="Updated Title",
            description="Updated description",
            tags=["tag1", "tag2"],
            category="entertainment",
            visibility=VideoVisibility.public,
            user_id=str(video.creator_id)
        )
        
        assert success is True
        
        # Verify update
        updated_video = await service.get_imported_video_by_id(str(video.id))
        assert updated_video["title"] == "Updated Title"
        assert updated_video["description"] == "Updated description"
        assert updated_video["tags"] == ["tag1", "tag2"]
        assert updated_video["category"] == "entertainment"
        assert updated_video["visibility"] == VideoVisibility.public
    
    async def test_update_imported_video_unauthorized(self, service, test_video_with_import, db_session):
        """Test updating video by unauthorized user"""
        video, import_job = test_video_with_import
        
        # Create another user
        other_user = User(
            display_label="Other User",
            email="other@example.com"
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)
        
        success = await service.update_imported_video_metadata(
            video_id=str(video.id),
            title="Hacked Title",
            user_id=str(other_user.id)
        )
        
        assert success is False
    
    async def test_bulk_update_imported_videos(self, service, test_video_with_import):
        """Test bulk updating imported videos"""
        video, import_job = test_video_with_import
        
        updated_count = await service.bulk_update_imported_videos(
            video_ids=[str(video.id)],
            visibility=VideoVisibility.public,
            category="entertainment",
            user_id=str(video.creator_id)
        )
        
        assert updated_count == 1
        
        # Verify update
        updated_video = await service.get_imported_video_by_id(str(video.id))
        assert updated_video["visibility"] == VideoVisibility.public
        assert updated_video["category"] == "entertainment"
    
    async def test_delete_imported_video(self, service, test_video_with_import):
        """Test deleting imported video"""
        video, import_job = test_video_with_import
        
        success = await service.delete_imported_video(
            video_id=str(video.id),
            user_id=str(video.creator_id)
        )
        
        assert success is True
        
        # Verify deletion
        deleted_video = await service.get_imported_video_by_id(str(video.id))
        assert deleted_video is None
    
    async def test_delete_imported_video_unauthorized(self, service, test_video_with_import, db_session):
        """Test deleting video by unauthorized user"""
        video, import_job = test_video_with_import
        
        # Create another user
        other_user = User(
            display_label="Other User",
            email="other@example.com"
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)
        
        success = await service.delete_imported_video(
            video_id=str(video.id),
            user_id=str(other_user.id)
        )
        
        assert success is False
    
    async def test_get_import_statistics(self, service, test_video_with_import):
        """Test getting import statistics"""
        video, import_job = test_video_with_import
        
        stats = await service.get_import_statistics(
            user_id=str(video.creator_id),
            days=30
        )
        
        assert stats["total_imports"] == 1
        assert stats["successful_imports"] == 1
        assert stats["failed_imports"] == 0
        assert stats["success_rate"] == 100.0
        assert "YouTube" in stats["platform_breakdown"]
        assert stats["platform_breakdown"]["YouTube"]["total"] == 1
        assert len(stats["recent_imports"]) == 1
    
    async def test_check_copyright_compliance(self, service, test_video_with_import):
        """Test copyright compliance check"""
        video, import_job = test_video_with_import
        
        compliance = await service.check_copyright_compliance(str(video.id))
        
        assert compliance["video_id"] == str(video.id)
        assert isinstance(compliance["compliant"], bool)
        assert isinstance(compliance["issues"], list)
        assert isinstance(compliance["attribution_complete"], bool)
        assert isinstance(compliance["recommendations"], list)
    
    async def test_generate_attribution_text_standard(self, service, test_video_with_import):
        """Test generating standard attribution text"""
        video, import_job = test_video_with_import
        
        attribution = await service.generate_attribution_text(
            video_id=str(video.id),
            format_type="standard"
        )
        
        assert isinstance(attribution, str)
        assert import_job.original_title in attribution
        assert import_job.original_uploader in attribution
        assert import_job.platform in attribution
        assert import_job.source_url in attribution
    
    async def test_generate_attribution_text_youtube(self, service, test_video_with_import):
        """Test generating YouTube-style attribution text"""
        video, import_job = test_video_with_import
        
        attribution = await service.generate_attribution_text(
            video_id=str(video.id),
            format_type="youtube"
        )
        
        assert isinstance(attribution, str)
        assert "Original video:" in attribution
        assert import_job.source_url in attribution
        assert import_job.original_uploader in attribution
    
    async def test_generate_attribution_text_academic(self, service, test_video_with_import):
        """Test generating academic-style attribution text"""
        video, import_job = test_video_with_import
        
        attribution = await service.generate_attribution_text(
            video_id=str(video.id),
            format_type="academic"
        )
        
        assert isinstance(attribution, str)
        assert import_job.original_uploader in attribution
        assert import_job.original_title in attribution
        assert import_job.platform in attribution
        assert import_job.source_url in attribution
    
    async def test_organize_imported_content_by_platform(self, service, test_video_with_import):
        """Test organizing content by platform"""
        video, import_job = test_video_with_import
        
        organized = await service.organize_imported_content(
            organization_type="platform",
            user_id=str(video.creator_id)
        )
        
        assert organized["organization_type"] == "platform"
        assert "YouTube" in organized["groups"]
        assert len(organized["groups"]["YouTube"]) == 1
        assert organized["summary"]["YouTube"] == 1
    
    async def test_organize_imported_content_by_date(self, service, test_video_with_import):
        """Test organizing content by date"""
        video, import_job = test_video_with_import
        
        organized = await service.organize_imported_content(
            organization_type="date",
            user_id=str(video.creator_id)
        )
        
        assert organized["organization_type"] == "date"
        assert len(organized["groups"]) >= 1
        assert len(organized["summary"]) >= 1
    
    async def test_organize_imported_content_by_uploader(self, service, test_video_with_import):
        """Test organizing content by uploader"""
        video, import_job = test_video_with_import
        
        organized = await service.organize_imported_content(
            organization_type="uploader",
            user_id=str(video.creator_id)
        )
        
        assert organized["organization_type"] == "uploader"
        assert "Original Creator" in organized["groups"]
        assert len(organized["groups"]["Original Creator"]) == 1
    
    async def test_organize_imported_content_by_status(self, service, test_video_with_import):
        """Test organizing content by status"""
        video, import_job = test_video_with_import
        
        organized = await service.organize_imported_content(
            organization_type="status",
            user_id=str(video.creator_id)
        )
        
        assert organized["organization_type"] == "status"
        assert VideoStatus.ready in organized["groups"]
        assert len(organized["groups"][VideoStatus.ready]) == 1
    
    async def test_organize_imported_content_invalid_type(self, service, test_video_with_import):
        """Test organizing content with invalid type"""
        video, import_job = test_video_with_import
        
        with pytest.raises(ValueError, match="Unknown organization type"):
            await service.organize_imported_content(
                organization_type="invalid",
                user_id=str(video.creator_id)
            )
    
    def test_format_standard_attribution(self, service):
        """Test standard attribution formatting"""
        attribution_data = {
            "original_title": "Test Video",
            "original_uploader": "Test Creator",
            "platform": "YouTube",
            "source_url": "https://youtube.com/watch?v=test"
        }
        
        result = service._format_standard_attribution(attribution_data)
        
        assert "Test Video" in result
        assert "Test Creator" in result
        assert "YouTube" in result
        assert "https://youtube.com/watch?v=test" in result
    
    def test_format_youtube_attribution(self, service):
        """Test YouTube attribution formatting"""
        attribution_data = {
            "source_url": "https://youtube.com/watch?v=test",
            "original_uploader": "Test Creator"
        }
        
        result = service._format_youtube_attribution(attribution_data)
        
        assert "Original video:" in result
        assert "https://youtube.com/watch?v=test" in result
        assert "Test Creator" in result
    
    def test_format_academic_attribution(self, service):
        """Test academic attribution formatting"""
        attribution_data = {
            "original_uploader": "Test Creator",
            "original_title": "Test Video",
            "platform": "YouTube",
            "source_url": "https://youtube.com/watch?v=test",
            "original_upload_date": "2024-01-15T10:00:00Z"
        }
        
        result = service._format_academic_attribution(attribution_data)
        
        assert "Test Creator" in result
        assert "Test Video" in result
        assert "YouTube" in result
        assert "https://youtube.com/watch?v=test" in result
        assert "2024" in result
    
    def test_get_compliance_recommendations(self, service):
        """Test getting compliance recommendations"""
        issues = ["Missing original uploader information", "Missing source URL"]
        
        recommendations = service._get_compliance_recommendations("YouTube", issues)
        
        assert len(recommendations) > 0
        assert any("attribution" in rec.lower() for rec in recommendations)
        assert any("link" in rec.lower() for rec in recommendations)
    
    def test_organize_by_platform(self, service):
        """Test organizing videos by platform"""
        videos = [
            {"attribution": {"platform": "YouTube"}},
            {"attribution": {"platform": "TikTok"}},
            {"attribution": {"platform": "YouTube"}}
        ]
        
        result = service._organize_by_platform(videos)
        
        assert result["organization_type"] == "platform"
        assert len(result["groups"]["YouTube"]) == 2
        assert len(result["groups"]["TikTok"]) == 1
        assert result["summary"]["YouTube"] == 2
        assert result["summary"]["TikTok"] == 1