# gui/main_window.py
import tkinter as tk
from tkinter import ttk
from .advanced_widgets import AdvancedWidgetMixin, _dispatch_mousewheel


class Btk(AdvancedWidgetMixin):
    def __init__(self, title="Tkinter App", width=800, height=600):
        self.root = tk.Tk()
        self.root.title(title)
        self.root.geometry(f"{width}x{height}")

        # 初始化 ttk 样式（若可用）
        try:
            self._ttk_style = ttk.Style()
        except Exception:
            self._ttk_style = None

        # 主画布 + 滚动条
        # 保留一个主容器，以便放置 toolbar / canvas / statusbar
        self._main_container = tk.Frame(self.root)
        self._main_container.pack(fill='both', expand=True)

        self.main_canvas = tk.Canvas(self._main_container)
        self.v_scrollbar = tk.Scrollbar(self.root, orient="vertical", command=self.main_canvas.yview)
        self.main_canvas.configure(yscrollcommand=self.v_scrollbar.set)

        # toolbar 区域（可由 mixin 填充）
        self.toolbar_container = tk.Frame(self._main_container)
        self.toolbar_container.pack(side='top', fill='x')

        # 主画布与滚动条放在中间区域
        self.v_scrollbar.pack(in_=self._main_container, side="right", fill="y")
        self.main_canvas.pack(in_=self._main_container, side="left", fill="both", expand=True)

        # 状态栏容器（可由 mixin 更新状态文本）
        self.statusbar_container = tk.Frame(self.root)
        self.statusbar_container.pack(side='bottom', fill='x')

        # 可滚动内容框架
        self.scrollable_frame = tk.Frame(self.main_canvas)
        # 保存 create_window 的返回 id，后续调整画布尺寸时直接引用，避免查找所有 item 引发错误
        self._scrollable_window_id = self.main_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        # 绑定滚动区域更新
        self.scrollable_frame.bind("<Configure>", self._on_frame_configure)
        self.main_canvas.bind("<Configure>", self._on_canvas_configure)

        # 全局滚轮：只注册一次，按鼠标指针位置分发到对应画布（垂直/水平）。
        # 避免多个画布各自 bind_all/unbind_all 互相覆盖导致滚动失效。
        self.root._ck8_wheel_bound = True
        self.root.bind_all("<MouseWheel>", lambda e: _dispatch_mousewheel(self.root, e))

    def _on_frame_configure(self, event):
        self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        canvas_width = event.width
        # 如果保存了 window id，则直接调整该 window 的宽度；否则回退到按 tag 查找（更兼容但不稳定）
        try:
            if hasattr(self, '_scrollable_window_id') and self._scrollable_window_id is not None:
                self.main_canvas.itemconfig(self._scrollable_window_id, width=canvas_width)
            else:
                items = self.main_canvas.find_withtag("all")
                if items:
                    self.main_canvas.itemconfig(items[0], width=canvas_width)
        except Exception:
            # 忽略调整失败，避免因单次错误导致整个界面崩溃
            pass

    def _on_mousewheel(self, event):
        """兼容旧接口：转发给全局滚轮分发器。"""
        _dispatch_mousewheel(self.root, event)

    def label_ck(self, label_text, tcolor='#000000', tzt='Microsoft YaHei', tsize=20, tblod=True):
        # 与 WidgetMixin.label_ck 保持一致的签名，避免被本类遮蔽后
        # 文档中 tcolor/tzt/tblod 等参数传入时抛 TclError。
        label = tk.Label(self.scrollable_frame, text=label_text, compound="top")
        label.config(fg=tcolor, font=(tzt, tsize, "bold" if tblod else ''))
        label.pack(pady=10)
        self._update_scrollregion()
        return label

    def run(self):
        self.root.mainloop()

    def center_window(self):
        """将窗口水平垂直居中显示在屏幕中央。"""
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        x = max(0, (self.root.winfo_screenwidth() - w) // 2)
        y = max(0, (self.root.winfo_screenheight() - h) // 2)
        self.root.geometry(f"+{x}+{y}")

    def add_shortcut(self, sequence, callback):
        """注册一个全局快捷键。

        参数:
            sequence (str): 键序列，如 '<Control-s>'、'<F5>'、'<Alt-q>'
            callback (callable): 触发时调用的函数
        """
        self.root.bind(sequence, lambda e: callback())

    def set_always_on_top(self, flag=True):
        """设置窗口是否置顶显示。"""
        self.root.attributes('-topmost', bool(flag))