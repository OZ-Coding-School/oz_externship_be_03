import queue
import threading
from typing import Dict, List


class NotificationEventSystem:
    def __init__(self):
        self.user_queues: Dict[int, queue.Queue] = {}
        self.lock = threading.Lock()

    def get_or_create_queue(self, user_id: int) -> queue.Queue:
        with self.lock:
            if user_id not in self.user_queues:
                self.user_queues[user_id] = queue.Queue()
                return self.user_queues[user_id]

    def notify_user(self, user_id: int):
        user_queue = self.get_or_create_queue(user_id)
        user_queue.put("new_notification")

    def wait_for_notification(self, user_id: int, timeout: float = 1.0) -> bool:
        user_queue = self.get_or_create_queue(user_id)
        try:
            user_queue.get(timeout=timeout)
            return True
        except queue.Empty:
            return False


notification_events = NotificationEventSystem()
