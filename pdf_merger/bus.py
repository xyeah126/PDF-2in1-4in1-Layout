"""线程安全消息队列 + 主线程 after 轮询分发。

铁律：后台线程只往这里写消息，绝不直接访问 UI 控件；
主线程通过 after(80) 轮询取消息并分发给 handler。
"""
import queue


class Bus:
    def __init__(self):
        self._q: "queue.Queue" = queue.Queue()
        self._root = None
        self._h: dict = {}

    # ---- 后台线程写口 ----
    def log(self, msg: str, level: str = "info"):
        self._q.put(("log", level, msg))

    def preview(self, png: bytes):
        self._q.put(("preview", png))

    def done(self, path: str):
        self._q.put(("done", path))

    def error(self, msg: str):
        self._q.put(("error", msg))

    # ---- 主线程读口 ----
    def start(self, root, handlers: dict):
        """handlers 需含 log/preview/done/error 四个回调。"""
        self._root = root
        self._h = handlers
        self._poll()

    def _poll(self):
        try:
            while True:
                m = self._q.get_nowait()
                k = m[0]
                if k == "log":
                    self._h["log"](m[2], m[1])
                elif k == "preview":
                    self._h["preview"](m[1])
                elif k == "done":
                    self._h["done"](m[1])
                elif k == "error":
                    self._h["error"](m[1])
        except queue.Empty:
            pass
        self._root.after(80, self._poll)
