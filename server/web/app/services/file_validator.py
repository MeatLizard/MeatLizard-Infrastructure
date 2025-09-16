from fastapi import UploadFile, HTTPException, status

class FileValidator:
    def __init__(self, max_size_mb: int = 1024, allowed_content_types: list = None):
        self.max_size_bytes = max_size_mb * (1024 ** 2)
        self.allowed_content_types = allowed_content_types or ["video/mp4", "image/jpeg", "image/png"]

    def validate(self, file: UploadFile):
        if file.size > self.max_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds the limit of {self.max_size_mb} MB."
            )
        
        if file.content_type not in self.allowed_content_types:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"File type '{file.content_type}' is not allowed."
            )

# Dependency for FastAPI
def get_file_validator() -> FileValidator:
    return FileValidator()