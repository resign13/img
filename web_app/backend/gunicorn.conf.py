import os

bind = f"127.0.0.1:{os.getenv('APP_PORT', '10000')}"
workers = 1
threads = 4
timeout = 300
