"""UI 冒烟测试：构造完整界面后自动退出，验证控件无构造错误。

需 Xvfb：xvfb-run -a python3 smoke_ui.py
"""
import customtkinter as ctk
from app import App

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")

root = ctk.CTk()
App(root, dnd_enabled=False)
root.after(600, root.destroy)   # 600ms 后自动关闭
root.mainloop()
print("UI_SMOKE_OK: 界面构造与启动流程无异常")
