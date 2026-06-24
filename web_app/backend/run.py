from __future__ import annotations

import os
import sys


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_ROOT = os.path.dirname(CURRENT_DIR)
REPO_ROOT = os.path.dirname(WEB_ROOT)
DESKTOP_ROOT = os.path.join(REPO_ROOT, "desktop_app")

for path in (WEB_ROOT, DESKTOP_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)


from backend.app import create_app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
