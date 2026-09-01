"""端到端预览管线冒烟：文件→worker线程→bus→主线程CTkImage显示。

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
state = {"ok": False, "err": None}


def step1():
    app.files = list(files)
    app.sel = 3
    app._render_files()
    app._trigger_preview()          # 起后台线程渲染
    root.after(900, step2)


def step2():
    try:
        state["ok"] = app.preview_label.cget("image") is not None
    except Exception as e:
        state["err"] = str(e)
    root.after(50, root.destroy)


root.after(100, step1)
root.mainloop()

img_set = app.preview_label.cget("image") is not None
print("PREVIEW_PIPELINE_OK:", state["ok"], "| image set:", img_set)
if state["err"]:
    print("ERR:", state["err"])
sys.exit(0 if state["ok"] and img_set else 1)
