"""Write the OpenAPI contract to openapi.json at the repo root.

uv run python -m scripts.export_openapi          # write
uv run python -m scripts.export_openapi --check  # fail if the file is stale
"""

import json
import sys
from pathlib import Path

from app.main import app

TARGET = Path(__file__).resolve().parents[1] / "openapi.json"


def render() -> str:
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    content = render()
    if "--check" in sys.argv:
        if not TARGET.exists() or TARGET.read_text() != content:
            print("openapi.json is stale. Run: uv run python -m scripts.export_openapi")
            return 1
        print("openapi.json is up to date")
        return 0
    TARGET.write_text(content)
    print(f"Wrote {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
