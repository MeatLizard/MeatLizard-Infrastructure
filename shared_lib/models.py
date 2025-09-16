# shared_lib/models.py
from pydantic import BaseModel

class LlamaModel(BaseModel):
    name: str
    path: str
    description: str
