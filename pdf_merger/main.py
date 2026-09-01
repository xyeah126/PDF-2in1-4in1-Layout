"""入口：初始化 customtkinter + 可选拖拽 root，启动 App。"""
import customtkinter as ctk


def _make_root():
    """尝试启用 tkinterdnd2 拖拽；失败则降级为普通 CTk。"""
    try:
        from tkinterdnd2 import TkinterDnD

        class Root(ctk.CTk, TkinterDnD.DnDWrapper):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                self.TkdndVersion = TkinterDnD._require_tkdnd()

        return Root, True
    except Exception:
        return ctk.CTk, False


def main():
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    Root, dnd = _make_root()
    root = Root()
    from app import App
    App(root, dnd_enabled=dnd)
    root.mainloop()


if __name__ == "__main__":
    main()
