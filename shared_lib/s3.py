# shared_lib/s3.py
import os
import boto3
from dotenv import load_dotenv

load_dotenv()

class S3Client:
    def __init__(self):
        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
            region_name=os.getenv("S3_REGION"),
        )
        self.bucket_name = os.getenv("S3_BUCKET_NAME")

    def upload_file(self, file_path: str, object_name: str):
        self.s3.upload_file(file_path, self.bucket_name, object_name)

    def download_file(self, object_name: str, file_path: str):
        self.s3.download_file(self.bucket_name, object_name, file_path)

def get_s3_client():
    return S3Client()
