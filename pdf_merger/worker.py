"""后台线程：调 engine，结果写 bus。绝不直接访问 UI。"""
import threading

from bus import Bus
from config import MergeConfig, validate
from pdf_engine import build_merged, render_preview, export


class Worker:
    def __init__(self, bus: Bus):
        self.bus = bus
        self._tid = 0          # 任务版本号，旧任务结果会被丢弃
        self._thread = None

    def _spawn(self, fn):
        self._tid += 1
        tid = self._tid
        t = threading.Thread(target=fn, args=(tid,), daemon=True)
        self._thread = t
        t.start()

    def preview(self, files, cfg: MergeConfig):
        cfg = validate(cfg)

        def task(tid):
            try:
                self.bus.log("渲染预览…")
                png = render_preview(files, cfg, log=self.bus.log)
                if tid == self._tid:        # 防抖：丢弃过期结果
                    self.bus.preview(png)
            except Exception as e:
                self.bus.error(f"预览失败: {e}")

        self._spawn(task)

    def export(self, files, cfg: MergeConfig, out_path: str):
        cfg = validate(cfg)

        def task(tid):
            try:
                self.bus.log(f"开始导出 {cfg.export_format.upper()} → {out_path}")
                doc = build_merged(files, cfg, log=self.bus.log)
                try:
                    paths = export(doc, out_path, cfg)
                finally:
                    doc.close()
                if tid == self._tid:
                    self.bus.done(paths)
            except Exception as e:
                self.bus.error(f"导出失败: {e}")

        self._spawn(task)
