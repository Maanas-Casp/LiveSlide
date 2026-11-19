def unavailable(source: str, details: str) -> None:
    raise RuntimeError(f"{source} ingestion is not configured: {details}")
