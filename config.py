"""Load the two supported settings from a project-local .env file."""
import os
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent / ".env"
KEYS = {"OPENAI_API_KEY", "OPENAI_MODEL", "DATABASE_URL", "OPENAI_EMBEDDING_MODEL"}


def load_env(path=ENV_PATH, environ=None):
    target = os.environ if environ is None else environ
    path = Path(path)
    if not path.exists():
        return
    parsed = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not separator or key not in KEYS:
            raise ValueError(f"Unsupported .env setting at line {number}.")
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError(f"Unclosed quote in .env at line {number}.")
            value = value[1:-1]
        parsed[key] = value
    # Environment wins, even when explicitly empty. No expansion or execution.
    for key, value in parsed.items():
        target.setdefault(key, value)
