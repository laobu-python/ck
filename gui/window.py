# gui/main_window.py
import tkinter as tk
from tkinter import ttk
from .advanced_widgets import AdvancedWidgetMixin, _dispatch_mousewheel

try:                                    # 脚本模式：cwd = 项目根，gui 为顶层包
    from ck1_0.core.theme import Theme
    from ck1_0.renderer.tk import TkRenderer
except ImportError:                     # 包模式：本文件即 ck1_0.gui.window
    from ..core.theme import Theme
    from ..renderer.tk import TkRenderer


class Btk(AdvancedWidgetMixin):
    def __init__(self, title="Tkinter App", width=800, height=600, theme=None):
        # 语义 token 表：theme=None 时使用基线（浅色）主题
        self.theme = theme if theme is not None else Theme.light()
        # （早期签字「backend root 进程内唯一」）：本窗口**不再自己 new `tk.Tk()`**。
        # 若这里新建 root，而 `add_shortcut`/`set_always_on_top`/`center_window` 又走 Renderer
        # （Renderer 自己也持有一个 `tk.Tk()`），进程内就会出现**两个 root**：用户看到两个窗口，
        # 且第二个 Renderer 会被 拒绝。故把 root 的**所有权移交给 Renderer**，本窗口只借用
        # 它的唯一 root。
        # `self.root` 仍是 `tk.Tk` 对象（`renderer.root.native`），因此 `main.py` /
        # `tutorial.py` / `advanced_widgets.py` 里所有 `app.root.xxx` 的既有用法**逐字不变**。
        # 主题实例同一个：`self.theme is self._renderer.theme`（视觉值只有一份来源）。
        self._renderer = TkRenderer(self.theme)
        self.root = self._renderer.root.native
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
        self.v_scrollbar = tk.Scrollbar(self.root, orient=self.theme.layout_main_scrollbar_orient,
                                        command=self.main_canvas.yview)
        self.main_canvas.configure(yscrollcommand=self.v_scrollbar.set)

        # toolbar 区域（可由 mixin 填充）
        self.toolbar_container = tk.Frame(self._main_container)
        self.toolbar_container.pack(side='top', fill='x')

        # 主画布与滚动条放在中间区域
        self.v_scrollbar.pack(in_=self._main_container,
                              side=self.theme.layout_main_scrollbar_side,
                              fill=self.theme.layout_main_scrollbar_fill)
        self.main_canvas.pack(in_=self._main_container,
                              side=self.theme.layout_main_canvas_side,
                              fill=self.theme.layout_main_canvas_fill,
                              expand=self.theme.layout_main_canvas_expand)

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
        self.root._ck10_wheel_bound = True
        self.root.bind_all("<MouseWheel>", lambda e: _dispatch_mousewheel(self.root, e))

        # **内容父容器中立化**
        # G 段 facade 需要**中立父容器 `Handle`**（base 的 `_validate_parent` 只收
        # `Handle`），而上面这套原生骨架按原设计**原样保留**。故把**既有的**内容
        # Frame 包成一个句柄 —— 既有属性/结构一行不动。实测：新控件仍落在**同一个**
        # `scrollable_frame` 里（`winfo_parent` 逐字相同）⇒ **零结构/视觉漂移**，
        # 的 6 个 `layout_main_*` token 也全部保留消费者。
        # 若将来给 base 加了与 `Handle.native` 对称的过渡期出口，本行改为
        # `self._renderer.adopt_native(self.scrollable_frame)` 即可（语义等价）。
        self._content = type(self._renderer.root)(self.scrollable_frame)

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
        label = self._renderer.label(self._content, label_text, color=tcolor,
                                     family=tzt, size=tsize, bold=tblod)
        self._update_scrollregion()
        return label

    def run(self):
        """进入事件循环，直到窗口关闭（拥有事件循环）。"""
        self._renderer.run()

    def center_window(self):
        """将窗口水平垂直居中显示在屏幕中央。"""
        self._renderer.center_window()

    def close(self):
        """关闭本窗口并**释放**它的 backend root（公开 API；幂等）。

        **为什么需要它**：（早期签字「backend root 进程内唯一」）要求
        —— 想在同一个进程里**再建**一个窗口，必须先把旧窗口的 Renderer 释放掉。此前这条纪律
        只能靠调用方去碰私有的 `app._renderer.destroy()`（`launcher.py` 就是这么写的），
        对新手不友好、也容易被写成 `root.destroy()`（那会留下**失效的单例登记**，下一个窗口
        撞上一句看不懂的英文 `TclError`）。

        行为：转发 `Renderer.destroy()` —— 销毁本窗口的原生控件、释放单例槽位；
        **重复调用静默返回**（幂等），此后可安全地再建一个 `MainWindow`/`Btk`。
        """
        self._renderer.destroy()

    def add_shortcut(self, sequence, callback):
        """注册一个全局快捷键。

        参数:
            sequence (str): **backend 中立**的按键描述串，例如 `'Ctrl+S'`、`'F5'`、`'Alt+Q'`。
                Tk 专属写法（如 `'<Control-s>'`）**不再接受**—— 描述串到
                Tk 序列的转换由 Tk 适配层完成，因此**同一份代码在 Tk 与 Qt 下都成立**，
                换后端不用改业务代码。写法无法识别时会**明确报错**（不静默失效）。
            callback (callable): 触发时调用的函数（**不接收** event 参数）
        """
        self._renderer.add_shortcut(sequence, callback)

    def set_always_on_top(self, flag=True):
        """设置窗口是否置顶显示。"""
        self._renderer.set_always_on_top(flag)