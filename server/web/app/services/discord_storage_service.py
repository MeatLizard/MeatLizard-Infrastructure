
import aiohttp
import os
from .base_service import BaseService

class DiscordStorageService:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def upload_file(self, file_path: str):
        async with aiohttp.ClientSession() as session:
            with open(file_path, "rb") as f:
                data = aiohttp.FormData()
                data.add_field("file", f, filename=os.path.basename(file_path))
                
                async with session.post(self.webhook_url, data=data) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        raise Exception(f"Failed to upload file to Discord: {response.status}")
