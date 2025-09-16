import pytest
from unittest.mock import patch, MagicMock
from uuid import uuid4

from shared_lib.analytics_collector import AnalyticsCollector

@patch('shared_lib.analytics_collector.process_analytics_event.delay')
def test_analytics_collector_sends_event_to_celery(mock_delay):
    collector = AnalyticsCollector()
    
    user_id = uuid4()
    content_id = uuid4()
    
    collector.track_event(
        "test_event",
        user_id=user_id,
        content_id=content_id,
        data={"foo": "bar"}
    )
    
    mock_delay.assert_called_once()
    call_args = mock_delay.call_args[0][0]
    
    assert call_args['event_type'] == 'test_event'
    assert call_args['user_id'] == user_id
    assert call_args['content_id'] == content_id
    assert call_args['data'] == {"foo": "bar"}