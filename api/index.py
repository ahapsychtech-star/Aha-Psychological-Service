import os
import sys

# ── Ensure the project root is the working directory ──────────────────────────
# Vercel runs functions from within /var/task (or a sub-directory).  We need
# the root on sys.path for "from app import app" and on the filesystem for
# Flask's send_from_directory('.', ...) and os.path.exists() calls.
_HERE = os.path.dirname(os.path.abspath(__file__))       # .../api/
_ROOT = os.path.dirname(_HERE)                            # project root

if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Change the working directory so send_from_directory('.', ...) resolves
# relative to the project root (where portals/, uploads/, login.html, etc. live).
try:
    os.chdir(_ROOT)
except OSError:
    pass  # Already there or not writable — proceed and let Flask handle it

# Vercel Python runtime expects a WSGI-compatible `app` object.
# Importing the existing Flask app keeps all existing routes and APIs intact.
from app import app  # noqa: E402
