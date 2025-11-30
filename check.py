import os
from pathlib import Path

def load_env_key(key: str, env_path: Path = Path(".env")) -> str | None:
    if os.getenv(key):
        return os.getenv(key)
    if not env_path.exists():
        return None
    for line in env_path.read_text().splitlines():
        if not line or line.strip().startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() == key:
            return v.strip().strip('"').strip("'")
    return None

api_key = load_env_key("OPENROUTER_API_KEY")
print("OPENROUTER_API_KEY:", api_key)
