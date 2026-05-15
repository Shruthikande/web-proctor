# shared.py
import threading

output_frame = None
frame_lock = threading.Lock()
# adding a warning counter
warning_count    = 0
warning_messages = []   # list of recent violations
warning_lock     = threading.Lock()