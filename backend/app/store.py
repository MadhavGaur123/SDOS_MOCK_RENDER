import json
from pathlib import Path


def ensure_json_file(path, default_value):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text(json.dumps(default_value, indent=2), encoding="utf-8")


def read_json(path, default_value):
    ensure_json_file(path, default_value)
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default_value


def write_json(path, value):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2), encoding="utf-8")
