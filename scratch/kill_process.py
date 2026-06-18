import os
import signal
try:
    os.kill(22985, signal.SIGTERM)
    print("Sent SIGTERM to 22985")
except Exception as e:
    print("Error:", e)
