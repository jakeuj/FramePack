import time

from threading import Thread, Lock, Event


class Listener:
    task_queue = []
    lock = Lock()
    thread = None
    stop_event = Event()

    @classmethod
    def _process_tasks(cls):
        while not cls.stop_event.is_set():
            task = None
            with cls.lock:
                if cls.task_queue:
                    task = cls.task_queue.pop(0)

            if task is None:
                time.sleep(0.001)
                continue

            func, args, kwargs = task
            try:
                func(*args, **kwargs)
            except KeyboardInterrupt:
                print("Task interrupted by user")
                # 清空剩餘任務
                with cls.lock:
                    cls.task_queue.clear()
                break
            except Exception as e:
                print(f"Error in listener thread: {e}")

    @classmethod
    def add_task(cls, func, *args, **kwargs):
        with cls.lock:
            cls.task_queue.append((func, args, kwargs))

        if cls.thread is None or not cls.thread.is_alive():
            cls.stop_event.clear()
            cls.thread = Thread(target=cls._process_tasks, daemon=True)
            cls.thread.start()

    @classmethod
    def stop_all_tasks(cls):
        """停止所有任務並清空隊列"""
        cls.stop_event.set()
        with cls.lock:
            cls.task_queue.clear()

        # 等待線程結束
        if cls.thread and cls.thread.is_alive():
            cls.thread.join(timeout=5.0)
            if cls.thread.is_alive():
                print("Warning: Listener thread did not stop gracefully")

        # 重置狀態
        cls.stop_event.clear()
        cls.thread = None

    @classmethod
    def clear_queue(cls):
        """清空任務隊列"""
        with cls.lock:
            cls.task_queue.clear()


def async_run(func, *args, **kwargs):
    Listener.add_task(func, *args, **kwargs)


class FIFOQueue:
    def __init__(self):
        self.queue = []
        self.lock = Lock()

    def push(self, item):
        with self.lock:
            self.queue.append(item)

    def pop(self):
        with self.lock:
            if self.queue:
                return self.queue.pop(0)
            return None

    def top(self):
        with self.lock:
            if self.queue:
                return self.queue[0]
            return None

    def next(self):
        while True:
            with self.lock:
                if self.queue:
                    return self.queue.pop(0)

            time.sleep(0.001)


class AsyncStream:
    def __init__(self):
        self.input_queue = FIFOQueue()
        self.output_queue = FIFOQueue()
