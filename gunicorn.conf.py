"""Gunicorn configuration; PM2 supervises the Gunicorn process."""

import os

bind = "127.0.0.1:" + os.getenv("PORT", "4043")
workers = max(1, int(os.getenv("GUNICORN_WORKERS", "2")))
timeout = 120
graceful_timeout = 30
keepalive = 5
accesslog = "-"
errorlog = "-"
capture_output = True
preload_app = True
