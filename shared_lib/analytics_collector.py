
from datetime import datetime
from typing import Dict, Any
from uuid import UUID

from server.background_worker import process_analytics_event

class AnalyticsCollector:
    def track_event(self, event_type: str, user_id: UUID = None, content_id: UUID = None, data: Dict[str, Any] = None):
        event_data = {
            "event_type": event_type,
            "user_id": user_id,
            "content_id": content_id,
            "timestamp": datetime.utcnow(),
            "data": data or {},
        }
        process_analytics_event.delay(event_data)

analytics_collector = AnalyticsCollector()
