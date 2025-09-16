# shared_lib/metrics.py
from pydantic import BaseModel
from datetime import datetime

class GpuStats(BaseModel):
    utilization: float
    memory_free: float
    memory_used: float
    temperature: float

class ClientBotMetrics(BaseModel):
    timestamp: datetime
    gpu_stats: GpuStats
    tokens_per_second: float
    is_online: bool

class ServerBotMetrics(BaseModel):
    timestamp: datetime
    active_sessions: int
    messages_per_minute: float
    uptime: float
