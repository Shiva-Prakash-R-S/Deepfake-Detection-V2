import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app import app

if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("  🛡️  Deepfake Detection AI - Web Application")
    print("=" * 65)
    print("  👉 FRONTEND LINK (Open in browser): http://localhost:5173")
    print("  👉 Or Direct Web UI Link:          http://127.0.0.1:5000")
    print("=" * 65 + "\n")
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
