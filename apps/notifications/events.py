import threading
from typing import Dict, List
import queue

class NotificationEventSystem:
    def __init__(self):
        self.user_queues:Dict[int, queue.Queue] = {}
        self.lock = threading.Lock()

