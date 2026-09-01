"""端到端预览管线冒烟：文件→worker线程→bus→主线程Canvas绘制。

xvfb-run -a python3 smoke_preview.py
"""
import os
import sys
import tempfile
import customtkinter as ctk
import pymupdf as fitz
from app import App

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")
root = ctk.CTk()

# 生成 4 个单页 PDF
tmp = tempfile.mkdtemp()
files = []
for i in range(4):
    p = os.path.join(tmp, f"p{i + 1}.pdf")
    d = fitz.open()
    pg = d.new_page(width=595, height=842)
    pg.insert_text((200, 400), f"P{i + 1}", fontsize=40, color=(0.2, 0.2, 0.6))
    d.save(p)
    d.close()
    files.append(p)

app = App(root, dnd_enabled=False)
state = {"ok": False, "err": None, "stage": 0}


def step1():
    app.files = list(files)
    app.sel = 3
    app._render_files()
    app._trigger_preview()          # 起后台线程渲染
    root.after(900, step2)


def step2():
    # 模拟：删除所有文件 → 再重新添加 → 触发"重建 tk.Image"的高风险路径
    # 这是用户真实流程：删除→再添加→pyimage not found 崩溃
    state["stage"] = 1
    app._clear_preview()            # 清空、销毁旧 PhotoImage
    root.after(100, step3)


def step3():
    app.files = list(files)
    app.sel = 3
    app._render_files()
    app._trigger_preview()          # 重新出预览（重建 tk.Image）
    root.after(900, step4)


def step4():
    try:
        # 验证 Canvas 有 image item + PhotoImage 存活
        cv = app.prev_canvas
        ids = cv.find_all()
        has_img = any(cv.type(i) == "image" for i in ids)
        tk_alive = app._prev_tk is not None and hasattr(app._prev_tk, "width")
        state["ok"] = has_img and tk_alive
    except Exception as e:
        state["err"] = str(e)
        import traceback
        traceback.print_exc()
    root.after(50, root.destroy)


root.after(100, step1)
root.mainloop()

print("PREVIEW_PIPELINE_OK:", state["ok"],
      "| canvas has image:", state["ok"])
if state["err"]:
    print("ERR:", state["err"])
sys.exit(0 if state["ok"] else 1)
