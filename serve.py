from __future__ import annotations

import os

from waitress import serve

from wsgi import application


if __name__ == "__main__":
    port = int(os.getenv("PORT") or "10000")
    serve(application, host="0.0.0.0", port=port)
