from app.config import settings

def get_url(path: str) -> str:
    """
    Constructs a full API path, ensuring no double slashes.
    """
    prefix = settings.API_V1_PREFIX.rstrip("/")
    path = path.lstrip("/")
    return f"{prefix}/{path}"    