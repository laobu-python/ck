"""renderer.py —— TkRenderer。

本批只交付 **button / toggle** 两个组件的真实实现，以及承载所必需的
`_destroy_root` / `is_alive` / `root`。**其余 35 个抽象方法一律抛
`NotSupportedError`**（可选能力未实现必须显式抛，**不得**静默 no-op / 返回 `None`）。

tkinter 的导入发生在**模块顶层**（允许），但**模块级绝不创建 `tk.Tk()`** ——
root 只在 `TkRenderer.__init__` 里创建。
"""

import os
import tkinter as tk

try:                                    # 可选依赖（首版同策略：缺 Pillow 不致命）
    from PIL import Image as _PIL_Image
    from PIL import ImageTk as _PIL_ImageTk
    _PIL_AVAILABLE = True
except ImportError:                     # pragma: no cover
    _PIL_Image = _PIL_ImageTk = None
    _PIL_AVAILABLE = False
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Callable, Optional, Sequence, Tuple

from ..base import (
    AnimationHandle,
    MediaHandle,
    CheckboxHandle,
    ComboHandle,
    FormHandle,
    Handle,
    InputHandle,
    Layout,
    ListHandle,
    NotebookHandle,
    NotSupportedError,
    ProgressHandle,
    RadioGroupHandle,
    Renderer,
    ScrollableHandle,
    SliderHandle,
    SpinboxHandle,
    StatusBarHandle,
    TableHandle,
    TextAreaHandle,
    TimerHandle,
    ToggleHandle,
    TooltipHandle,
)
from .handles import (TkCheckValue, TkCheckboxHandle, TkComboHandle, TkFloatValue,
                      TkHandle, TkIndexValue, TkListHandle, TkNumValue, TkSliderHandle,
                      TkFormHandle, TkNotebookHandle, TkSpinboxHandle, TkStatusBarHandle,
                      TkTooltipHandle, TkMediaHandle, TkAnimationHandle, TkLabelHandle,
                      TkTableHandle,
                      TkTextVarValue,
                      TkBarsHandle, TkInputHandle, TkLabelsHandle, TkProgressHandle,
                      TkRadioGroupHandle, TkScrollableHandle,
                      TkTextAreaHandle,
                      TkTimerHandle, TkToggleHandle, apply_tk_layout)

__all__ = ["TkRenderer"]


def _tk_is_multi(handle) -> bool:
    return bool(getattr(handle._value, "_multi", False))


def _tk_raw(handle) -> str:
    w = handle._widget
    return w.get("1.0", "end-1c") if _tk_is_multi(handle) else w.get()


def _tk_clear(handle) -> None:
    w = handle._widget
    w.delete("1.0", "end") if _tk_is_multi(handle) else w.delete(0, "end")


def _tk_insert(handle, text) -> None:
    w = handle._widget
    w.insert("1.0", text) if _tk_is_multi(handle) else w.insert(0, text)


def _tk_focus_in(handle) -> None:
    """`<FocusIn>`：内容仍等于占位符 ⇒ 清空并转正文色（首版语义）。"""
    if _tk_raw(handle) == handle._placeholder:
        _tk_clear(handle)
        handle._widget.config(fg=handle._theme.input_text_color)


def _tk_focus_out(handle) -> None:
    """`<FocusOut>`：内容为空 ⇒ 恢复灰色占位符（首版语义）。"""
    if _tk_raw(handle) == "":
        _tk_insert(handle, handle._placeholder)
        handle._widget.config(fg=handle._theme.placeholder_color)


_SHORTCUT_MODS = {"ctrl": "Control", "control": "Control", "alt": "Alt",
                  "shift": "Shift", "cmd": "Command", "command": "Command",
                  "meta": "Meta", "super": "Super"}
_SHORTCUT_KEYS = {"esc": "Escape", "escape": "Escape", "enter": "Return",
                  "return": "Return", "space": "space", "tab": "Tab",
                  "backspace": "BackSpace", "del": "Delete", "delete": "Delete",
                  "insert": "Insert", "home": "Home", "end": "End",
                  "pageup": "Prior", "pagedown": "Next", "up": "Up",
                  "down": "Down", "left": "Left", "right": "Right",
                  "plus": "plus", "minus": "minus"}
for _i in range(1, 13):
    _SHORTCUT_KEYS["f%d" % _i] = "F%d" % _i


def _tk_sequence(sequence):
    """**中立描述串 → Tk 序列**（落地：转换只发生在 Tk 适配层）。

    受理形态：`'Ctrl+S'` / `'Ctrl+Shift+S'` / `'Alt+F4'` / `'F5'` / `'Escape'` / `'Ctrl+plus'`。
    规则（**不静默**）：
      * 形状非法（空串、缺键、键位是修饰键本身、修饰键未知、键名未知）⇒ `NotSupportedError`；
      * 单个可打印字符 ⇒ 小写（Tk 序列里 `s` 表示小写字母键）；
      * 修饰键按 `Control/Alt/Shift/Command/Meta/Super` 映射，顺序保持输入顺序。
    """
    text = (sequence or "").strip()
    if not text:
        raise NotSupportedError("add_shortcut: 空的中立描述串")
    parts = [p.strip() for p in text.split("+")]
    key_raw = parts[-1]
    mods_raw = parts[:-1]
    if not key_raw:
        raise NotSupportedError("add_shortcut: 缺少键位：%r" % (sequence,))
    key_low = key_raw.lower()
    if key_low in _SHORTCUT_MODS:
        raise NotSupportedError("add_shortcut: 键位不能是修饰键本身：%r" % (sequence,))
    if len(key_raw) == 1 and (key_raw.isalnum()):
        key = key_low
    elif key_low in _SHORTCUT_KEYS:
        key = _SHORTCUT_KEYS[key_low]
    else:
        raise NotSupportedError("add_shortcut: 无法识别的键位 %r（描述串 %r）"
                                % (key_raw, sequence))
    mods = []
    for raw in mods_raw:
        mapped = _SHORTCUT_MODS.get(raw.lower())
        if mapped is None:
            raise NotSupportedError("add_shortcut: 无法识别的修饰键 %r（描述串 %r）"
                                    % (raw, sequence))
        mods.append(mapped)
    return "<" + "-".join(mods + [key]) + ">"


def _tk_media_frames(path, max_frames=None):
    """用 Pillow 打开图片并返回**独立副本**帧列表；任何失败 ⇒ `None`（冻结语义）。

    `path` 为空 / 文件不存在 / 无 Pillow / 解码异常一律 `None` —— **不得**抛给调用方
    （首版 `photo`/`show_frames` 的"缺依赖/文件失败 ⇒ `None`"语义）。
    """
    if not _PIL_AVAILABLE or not path:
        return None
    try:
        if not os.path.isfile(path):
            return None
        img = _PIL_Image.open(path)
        total = int(getattr(img, "n_frames", 1) or 1)
        if max_frames is not None:
            total = max(1, min(total, int(max_frames)))
        out = []
        for idx in range(total):
            if idx:
                img.seek(idx)
            out.append(img.convert("RGBA").copy())
        return out
    except Exception:                       # noqa: BLE001 —— 契约：失败 ⇒ None
        return None


def _tk_warn_animated(path, total_frames, shown_frame):
    """多帧提示（首版 `photo(warn_animated=True)` 的同义行为：**只提示，不改语义**）。"""
    print("提示：%s 是多帧图片（共 %d 帧），当前显示第 %d 帧；"
          "可用 animation() 播放、show_frames() 预览全部帧。"
          % (os.path.basename(path), total_frames, shown_frame))


class TkRenderer(Renderer):
    """基于 tkinter 的 renderer（最小实现）。

   生命周期
        子类 `__init__` **必须先调用 `super().__init__(theme)`** 再建立 backend root ——
        单例校验与登记发生在 `super().__init__()` 内，因此第 2 个实例会在分配 root
        **之前**被拒（不泄漏孤儿 root）。漏调 `super()` 会被 `__init_subclass__`
       包装的构造当场发现。
    """

    def __init__(self, theme=None):
        # 纪律：登记先于 root 创建（顺序不可调换）
        super().__init__(theme)
        self._tk_root = tk.Tk()
        self._root_handle = TkHandle(self._tk_root)
        # 本 Renderer 排定的定时器：`destroy()` 时统一取消（契约"随 destroy() 释放"）
        self._timers = []
        # 本 Renderer 弹过的 toast 顶层窗；`_destroy_root()` 前需清掉，避免孤儿窗口
        self._toasts = []
        # 本 Renderer 拥有的只读报告窗口；`_destroy_root()` 时统一关闭
        self._reports = []
        # 本 Renderer 注册的全局快捷键：Tk 序列 -> **中立描述串**（供诊断/探针读回）
        self._shortcuts = {}
        # 本 Renderer 创建的动画句柄：`clear_media()` 逐个停止并销毁
        self._media = []

    # ------------------------------------------------------------------ #
    # 生命周期（真实实现）
    # ------------------------------------------------------------------ #
    def _destroy_root(self) -> None:
        """销毁**本实例自己的** Tk root。**幂等**；正常情况下不抛异常。

        **只**回收自己造的资源，**不触碰任何进程级共享对象**。
       必须能安全处理"半构造"实例 —— 未建立的资源按"无需释放"处理
        （故用 `getattr` 而非直接属性访问）。

        **幂等性 / "异常: 无"（base 冻结契约）**：base 要求本方法"重复调用须静默返回"。
        但存在一条真实路径会打破天真实现 —— **root 已被外部销毁**（典型：用户点窗口
        关闭按钮 → `Tk.destroy()` 拆掉 Tcl 解释器）。此时再 `root.destroy()` 会抛
        `TclError: ... application has been destroyed`，若让异常逸出，`_tk_root` 永远
        清不掉 ⇒ `is_alive()` 永远抛 ⇒ base `destroy()` 走保守分支 ⇒ **槽位永不释放、
        进程内再也建不出 Renderer**（推翻 base 自己"不会永久锁死"的承诺）。

        因此这里**区分两种失败**（判据是"中立测活"，不是匹配错误文本）：
            * root **确已不存在**（`winfo_exists()` 返回 0，或解释器已死到连它都调不动）
              ⇒ 视为"无需释放"，**静默清引用**；
            * root **仍然存活** ⇒ 释放确实失败，**原样重抛**，由 base 保留槽位。
        """
        root = getattr(self, "_tk_root", None)
        if root is None:
            return                                  # 已释放 / 半构造：无需释放
        # 先取消本 Renderer 排定的全部定时器（契约：定时器随 destroy() 释放，
        # 且 destroy() 之后回调不得再执行）。Tk 在 root.destroy() 时也会取消 after，
        # 这里显式取消是为了让 `TimerHandle.is_active()` 立刻给出确定的 False。
        for _t in list(getattr(self, "_timers", None) or []):
            _t.cancel()
        if getattr(self, "_timers", None):
            self._timers.clear()
        # 先关掉本 Renderer 拥有的报告窗口。root.destroy() 本会级联销毁它们，
        # 但显式关闭让 `Handle.exists()` 在 destroy() 返回后**立刻**给出确定的 False。
        for _h in list(getattr(self, "_reports", None) or []):
            _h.destroy()
        if getattr(self, "_reports", None):
            self._reports.clear()
        try:
            root.destroy()
        except tk.TclError:
            try:
                still_there = bool(root.winfo_exists())
            except tk.TclError:
                still_there = False                 # 解释器已销毁 ⇒ root 确定不存在
            if still_there:
                raise                                # 真·释放失败：保留槽位
        # 只有确认 root 确已不存在时才清引用
        self._tk_root = None

    def is_alive(self) -> bool:
        """root 是否仍然存在且可用。

        实现中立：**只问 root 自身**（`winfo_exists()`）；**禁止**用"窗口可见/已
        map/事件循环在跑"。
        异常策略：查询**失败必须上抛**，**不得**吞成 `False`（与 `Handle.exists()`
       相反是有意的 —— 本方法承载）。`_tk_root is None` 表示"从未建立"或
        "已成功销毁"，那两种情况都是**确定的**不存在，直接 `False`，无需查询。

        **外部销毁路径的裁决（复审，人类选①：维持快速失败）**
            root 被外部销毁后（真实场景：用户点窗口关闭按钮），`winfo_exists()` 会抛
            `TclError: ... application has been destroyed`。按上述契约，本方法**原样上抛**
            —— 于是 `Renderer.current()` / `self.root` 在该路径上也上抛（`TclError`，
           而非 `RendererClosedError`）。这是**有意接受**的取舍：的快速失败优先于
            "查询失败一律当不存在"。
            **不会因此锁死**：`_destroy_root()` 已按 base 契约做成幂等（见其文档），
            外部销毁后调用一次 `destroy()` 即可静默清引用 → 本方法随即返回 `False`
            → base 释放单例槽位 → 进程内可再次构造 Renderer。**无需重启进程。**
        """
        root = getattr(self, "_tk_root", None)
        if root is None:
            return False
        return bool(root.winfo_exists())

    @property
    def root(self) -> Handle:
        """root 容器句柄（所有显式 `parent` 的最终祖先）。"""
        self._ensure_alive()
        return self._root_handle

    # ------------------------------------------------------------------ #
    # 私有助手
    # ------------------------------------------------------------------ #
    def _reject_layout(self, layout, method: str) -> None:
        """本批只支持 `layout=None`；非 None 一律显式拒绝（不得静默忽略）。

        注：本检查**先于** parent 校验 —— "该能力本批不支持"是比"参数非法"
        更根本的原因，先报它可避免调用方看到误导性的次级错误。
        """
        if layout is not None:
            raise NotSupportedError(
                "%s: layout not supported in "
                "（本批只接受 layout=None，收到 %r）" % (method, layout)
            )

    # ------------------------------------------------------------------ #
    # 组件：button（真实实现）
    # ------------------------------------------------------------------ #
    def button(self, parent: Handle, text: str,
               command: Optional[Callable[[], None]] = None,
               width: Optional[int] = None, height: Optional[int] = None,
               color: Optional[str] = None, family: Optional[str] = None,
               size: Optional[int] = None, bold: Optional[bool] = None,
               layout: Optional[Layout] = None) -> Handle:
        """按钮（`command` **无参**、UI 线程同步）。

       视觉参数 `None` ⇒ 取 `Theme` token：
        `color→default_color` / `family→default_family` /
        `size→label_default_size` / `bold→label_default_bold`；
        `width/height` ⇒ `button_default_width` / `button_default_height`。
        """
        self._ensure_alive()
        self._reject_layout(layout, "button")
        resolved = self._validate_parent(parent)
        theme = self.theme

        widget = tk.Button(
            resolved.native,
            text=text,
            fg=theme.default_color if color is None else color,
            font=(
                theme.default_family if family is None else family,
                theme.label_default_size if size is None else size,
                "bold" if (theme.label_default_bold if bold is None else bold) else "",
            ),
            width=theme.button_default_width if width is None else width,
            height=theme.button_default_height if height is None else height,
        )
        if command is not None:
            widget.configure(command=command)
        return TkHandle(widget)

    # ------------------------------------------------------------------ #
    # 组件：toggle（真实实现）
    # ------------------------------------------------------------------ #
    def toggle(self, parent: Handle, text: str = "开关", default: bool = False,
               command: Optional[Callable[[bool], None]] = None,
               width: Optional[int] = None, height: Optional[int] = None,
               on_color: Optional[str] = None, off_color: Optional[str] = None,
               layout: Optional[Layout] = None) -> ToggleHandle:
        """开关（`command` 收 `bool`；`None` ⇒ 取 `Theme` token）。

        `text=''` 时**仍然创建标签**（内容为空串），与首版的
        `if text:` 有意不同。
       绘制配方取自首版 `create_toggle_switch`（Frame + Canvas + Label）。
        """
        self._ensure_alive()
        self._reject_layout(layout, "toggle")
        resolved = self._validate_parent(parent)
        theme = self.theme

        track_w = theme.toggle_default_width if width is None else width
        track_h = theme.toggle_default_height if height is None else height

        frame = tk.Frame(resolved.native)
        frame.pack(pady=theme.toggle_frame_pady)
        canvas = tk.Canvas(frame, width=track_w, height=track_h,
                           bg=frame["bg"], highlightthickness=0)
        canvas.pack(side="left", padx=theme.toggle_canvas_padx)
        # 无条件创建标签（空串 ⇒ 标签存在但内容为空）
        label = tk.Label(frame, text=text)
        label.pack(side="left")

        handle = TkToggleHandle(
            frame, canvas, label, track_w, track_h,
            theme.toggle_on if on_color is None else on_color,
            theme.toggle_off if off_color is None else off_color,
            theme.toggle_knob, theme.toggle_outline,
            default, command,
        )
        canvas.bind("<Button-1>", handle._on_click)
        handle._redraw()
        return handle

    # ------------------------------------------------------------------ #
    # 事件循环（真实实现）
    # ------------------------------------------------------------------ #
    def run(self) -> None:
        """进入 Tk 主循环，直到窗口关闭 / 循环退出 / `destroy()`。

        base 契约：返回 `None`；**阻塞**；**返回后不自动 destroy**—— 因此
        `run()` 返回后 `is_alive()` 可能仍为真（窗口被关闭但未销毁），释放责任在调用方。
        `destroy()` 之后的调用抛 `RendererClosedError`（先过 `_ensure_alive()`）。
       异常：循环期间 Tk 解释器被外部销毁时 `TclError` 原样上抛（既有取舍，
        已登记）。
        """
        self._ensure_alive()
        self._tk_root.mainloop()

    def update(self) -> None:
        """处理一次待办事件（**非阻塞**），供脚本与测试使用。

        base 契约：返回 `None`；非阻塞，处理完当前队列即返回；**不**进入主循环。
        `Tk.update()` 正是该语义（处理全部待办事件，含 idle 队列后返回）。
        `destroy()` 之后的调用抛 `RendererClosedError`。
        """
        self._ensure_alive()
        self._tk_root.update()

    # ------------------------------------------------------------------ #
    # 其余抽象方法：显式 NotSupportedError（不得静默 no-op）
    # 「哪些已实现」的权威清单 = 本实现的 methods 行
    # （此处**不写死数量**：每批都会变，写死的数字必然过期）
    # ------------------------------------------------------------------ #
    # ------------------------------------------------------------------ #
    # 窗口级方法（真实实现）
    # ------------------------------------------------------------------ #
    def set_title(self, text: str) -> None:
        """设置窗口标题（`text` 逐字交给 Tk：中文/空串均合法）。

        base 契约：返回 `None`；同步；无回调/无所有权变更；`destroy()` 后抛
        `RendererClosedError`。与首版一致（`Btk.__init__` 的 `title('…')`）。
        """
        self._ensure_alive()
        self._tk_root.title(text)

    def set_size(self, width: int, height: int) -> None:
        """设置窗口几何（像素）。与首版一致（`Btk.__init__` 的 `geometry(f"{w}x{h}")`）。

        base 契约：返回 `None`；同步（**窗口管理器**可能延迟到下一次事件循环才生效 ——
        未 map 前 `winfo_width/height` 恒为 `1`，读回前先 `update()`）。
        `destroy()` 后抛 `RendererClosedError`。
        **已知后端差异（登记）**：请求值会被 WM/屏幕钳制（本环境实测
        `1920x1080 → 1711x1048`、`1x1 → 120x1`）；契约只承诺"请求"，
        **不承诺读回值与请求值相等**。详见 `开发期探针 parity`。
        """
        self._ensure_alive()
        self._tk_root.geometry(f"{width}x{height}")

    def center_window(self) -> None:
        """按屏幕尺寸把窗口水平/垂直居中（与首版 `Btk.center_window` **同一算法**）。

       算法（逐行对齐首版）：`update_idletasks()` → 读当前 `winfo_width/height`
        与 `winfo_screenwidth/height` → `x = max(0, (sw - w) // 2)`、`y` 同理 →
        `geometry(f"+{x}+{y}")`（**只改位置，不改尺寸**）。
        base 契约：返回 `None`；同步（窗口管理器可能延迟到下一次事件循环生效，
        读回前先 `update()`）；`destroy()` 后抛 `RendererClosedError`。
        """
        self._ensure_alive()
        root = self._tk_root
        root.update_idletasks()
        w, h = root.winfo_width(), root.winfo_height()
        x = max(0, (root.winfo_screenwidth() - w) // 2)
        y = max(0, (root.winfo_screenheight() - h) // 2)
        root.geometry(f"+{x}+{y}")

    def schedule(self, delay_ms: int, callback: Callable[[], None]) -> TimerHandle:
        """在 UI 线程延迟执行**一次** `callback`（中立化落点）。

        base 契约：注册同步返回 `TimerHandle`；回调**无参**、在 UI 线程同步执行；
        定时器归本 Renderer 所有，`TimerHandle.cancel()` 或 `destroy()` 释放；
        `destroy()` 之后回调不得再执行；`destroy()` 之后调用本方法抛
        `RendererClosedError`。
        实现：`Tk.after(delay_ms, callback)` + `TkTimerHandle`（`cancel()` 幂等；
        `is_active()` 查 Tcl `after info`）。
        """
        self._ensure_alive()
        timer_id = self._tk_root.after(delay_ms, callback)
        handle = TkTimerHandle(self._tk_root, timer_id)
        self._timers.append(handle)
        return handle

    def label(self, parent: Handle, text: str,
              color: Optional[str] = None, family: Optional[str] = None,
              size: Optional[int] = None, bold: Optional[bool] = None,
              anchor: Optional[str] = None,
              layout: Optional[Layout] = None) -> Handle:
        """文本标签（**生效点**）。

       视觉参数默认值 → `Theme` token：
        `color→default_color` / `family→default_family` /
        **`size→label_default_size`（=12）/ `bold→label_default_bold`（=False）**。

        ⚠️ **与首版的有意差异**：首版的
        `label_ck` 默认 `tsize=20, tblod=True`，本层改为 **12 / 非粗体** ⇒ 正文 label 的
       默认外观**故意变化**；标题层级仍由调用方显式传 20/粗体（`接口合同` 的
        `title_size`/`title_weight`，见）。目视签收在。
        `compound="top"` 与 `pady=Theme.label_y` 与首版 `label_ck` 一致。
        """
        self._ensure_alive()
        self._reject_layout(layout, "label")
        resolved = self._validate_parent(parent)
        theme = self.theme
        widget = tk.Label(
            resolved.native, text=text, compound="top",
            fg=theme.default_color if color is None else color,
            font=(theme.default_family if family is None else family,
                  theme.label_default_size if size is None else size,
                  "bold" if (theme.label_default_bold if bold is None else bold) else ""),
        )
        if anchor is not None:
            try:
                widget.configure(anchor=anchor)
            except tk.TclError as exc:
                widget.destroy()          # 不留孤儿控件
                raise NotSupportedError(
                    "label.anchor 不支持：%r（Tk 取值须为 n/ne/e/se/s/sw/w/nw/center）"
                    % (anchor,)) from exc
        widget.pack(pady=theme.label_y)
        return TkLabelHandle(widget)

    def labels(self, parent: Handle, data: Optional[Sequence[str]] = None,
               background: Optional[str] = None,
               label_background: Optional[str] = None,
               label_color: Optional[str] = None,
               height: Optional[int] = None,
               layout: Optional[Layout] = None) -> Handle:
        """"序号 + 文本"标签列表（再套一层垂直滚动容器**）。

       结构逐项对齐首版 `scrollable_labels`：**垂直滚动容器 + 每项一个 `Label`**。
        （落地版是"单张平坦 Canvas"：既没有滚动条，条目一多还会被画布宽度**静默裁掉**；
       按人裁定「要方便便捷，再套一层」后改为本结构。）
        空 `data` ⇒ `['默认标签']`；字号取 `Theme.labels`（`('Arial', 10)`）。
        token：`background→labels_background`（滚动容器底色）、`label_background→
        labels_label_background`、`label_color→labels_label_color`、`height→labels_default_height`
        （**视口**高度）、`labels_label_padx/pady`、`labels_default_width`（**视口**宽度）。
        """
        self._ensure_alive()
        self._reject_layout(layout, "labels")
        theme = self.theme
        items = list(data) if data else ["默认标签"]
        band_bg = theme.labels_background if background is None else background
        # 外层垂直滚动容器（`scrollable` 自己会 pack 进 `parent`）
        box = self.scrollable(parent, width=theme.labels_default_width,
                              height=theme.labels_default_height if height is None else height,
                              background=band_bg)
        holder = box.content.native
        holder.configure(bg=band_bg)
        box.native.configure(bg=band_bg)
        for i, text in enumerate(items):
            tk.Label(holder, text="%d. %s" % (i + 1, text),
                     bg=(theme.labels_label_background if label_background is None
                         else label_background),
                     fg=(theme.labels_label_color if label_color is None else label_color),
                     font=theme.labels, anchor="w",
                     padx=theme.labels_label_padx, pady=theme.labels_label_pady
                     ).pack(fill=tk.X)
        return TkLabelsHandle(box.native, box._canvas, box._scrollbar, holder, len(items))

    def input(self, parent: Handle, hint: str = "请输入",
              width: Optional[int] = None, family: Optional[str] = None,
              size: Optional[int] = None, bold: Optional[bool] = None,
              layout: Optional[Layout] = None) -> InputHandle:
        """单行输入框。占位符/焦点语义逐行对齐首版 `input_box`：初始灰色 `hint`、
        `<FocusIn>` 且内容==hint ⇒ 清空转 `input_text_color`、`<FocusOut>` 且空 ⇒ 恢复占位符。

        token：`width→input_default_width` / `family→default_family` / `size→label_default_size` /
        `bold→label_default_bold` / `pady=input_y` / `ipady=input_ipady`。
        **中性化**：`.value.get()` 只显示占位符时返回 `''`（见 `TkTextValue`）。
        """
        self._ensure_alive()
        self._reject_layout(layout, "input")
        resolved = self._validate_parent(parent)
        theme = self.theme
        widget = tk.Entry(
            resolved.native,
            width=theme.input_default_width if width is None else width,
            font=(theme.default_family if family is None else family,
                  theme.label_default_size if size is None else size,
                  "bold" if (theme.label_default_bold if bold is None else bold) else ""))
        widget.pack(pady=theme.input_y, ipady=theme.input_ipady)
        handle = TkInputHandle(widget, hint, theme)
        widget.insert(0, hint)
        widget.config(fg=theme.placeholder_color)
        widget.bind("<FocusIn>", lambda _e: _tk_focus_in(handle))
        widget.bind("<FocusOut>", lambda _e: _tk_focus_out(handle))
        return handle

    def text_area(self, parent: Handle, placeholder: str = "请输入文本...",
                  width: Optional[int] = None, height: Optional[int] = None,
                  layout: Optional[Layout] = None) -> TextAreaHandle:
        """带垂直滚动条的多行文本框。结构/语义逐行对齐首版 `create_text_area`：
        `Frame`（`pady=input_text_area_pady`）+ `Text`（左，fill=BOTH/expand）+ `Scrollbar`
        （右，fill=Y）+ 双向 `yscrollcommand`/`command` 接线；占位符与焦点语义同 `input`。
        token：`width→input_text_area_width` / `height→input_text_area_height`。
        """
        self._ensure_alive()
        self._reject_layout(layout, "text_area")
        resolved = self._validate_parent(parent)
        theme = self.theme
        frame = tk.Frame(resolved.native)
        frame.pack(pady=theme.input_text_area_pady)
        widget = tk.Text(frame,
                         width=theme.input_text_area_width if width is None else width,
                         height=theme.input_text_area_height if height is None else height)
        scrollbar = tk.Scrollbar(frame)
        widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        widget.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=widget.yview)
        handle = TkTextAreaHandle(widget, placeholder, theme)
        widget.insert("1.0", placeholder)
        widget.config(fg=theme.placeholder_color)
        widget.bind("<FocusIn>", lambda _e: _tk_focus_in(handle))
        widget.bind("<FocusOut>", lambda _e: _tk_focus_out(handle))
        return handle

    def checkbox(self, parent: Handle, text: str = "复选框", default: bool = False,
                 command: Optional[Callable[[], None]] = None,
                 layout: Optional[Layout] = None) -> CheckboxHandle:
        """复选框。首版 `create_checkbox` = `(BooleanVar, Checkbutton)`；本层把值
       中性化为 `CheckboxHandle.value`（bool，纪律：**同值不触发**，变更时先 `on_change`
        后 `command`，各一次）。token：`pady=checkbox_y`、`default→checkbox_default`。
        """
        self._ensure_alive()
        self._reject_layout(layout, "checkbox")
        resolved = self._validate_parent(parent)
        theme = self.theme
        # ：`tk.*Var()` 必须**绑定控件宿主**，不能靠
        # tkinter 的 default root。原因（实测）：default root **只在为空时被认领**（首个根胜出），
        # 而 `ttk.Style()` 之类会先造一个隐藏根 ⇒ 不带 `master=` 的变量落进**另一个 Tcl 解释器**；
        # `Checkbutton(variable=<变量名>)` 传过去的只是**名字**，目标解释器会按需新建同名变量，
        # 于是"控件写的变量"与"回调读的变量"不是同一个 ⇒ `command` 一次都不触发、值停在初值，
        # **且无任何报错**。`master=` 让变量与控件同解释器，从根上消除该静默失效。
        var = tk.IntVar(master=resolved.native, value=1 if default else 0)
        widget = tk.Checkbutton(resolved.native, text=text, variable=var)
        widget.pack(pady=theme.checkbox_y)
        handle = TkCheckboxHandle(widget, var, default, command, TkCheckValue)

        def _on_toggle():
            new = bool(var.get())
            if new != handle._value._value:
                handle._value._value = new           # 用户点击：先同步内部值
                for cb in list(handle._value._callbacks):
                    cb(new)
                handle._fire_command()

        widget.config(command=_on_toggle)
        return handle

    def radio_group(self, parent: Handle, options: Sequence[str], default: int = 0,
                    layout: Optional[Layout] = None) -> RadioGroupHandle:
        """单选组。首版 `create_radio_group` = `(IntVar, [Radiobutton])`，变量值 =
        选中**索引**，默认索引 `default`；`RadioGroupHandle.value` 中性化为该索引。
        **回调：无**（base 契约明文）。token：`pady=radio_y`、`anchor=radio_anchor`。
        """
        self._ensure_alive()
        self._reject_layout(layout, "radio_group")
        resolved = self._validate_parent(parent)
        theme = self.theme
        frame = tk.Frame(resolved.native)
        frame.pack(pady=theme.radio_y)
        # （甲）：同 `checkbox`，变量显式绑宿主 —— 否则 `trace_add` 会加在**别的解释器**的
        # 变量上，点击单选按钮永远不触发 `on_change`（静默）。
        var = tk.IntVar(master=frame, value=default)
        for i, opt in enumerate(options):
            rb = tk.Radiobutton(frame, text=opt, variable=var, value=i,
                                anchor=theme.radio_anchor)
            rb.pack(anchor=theme.radio_anchor)
        handle = TkRadioGroupHandle(frame, var, options, default, TkIndexValue)

        def _on_select():
            new = int(var.get())
            if new != handle._value._value:
                handle._value._value = new
                for cb in list(handle._value._callbacks):
                    cb(new)

        var.trace_add("write", lambda *_: _on_select())
        return handle


    def progress(self, parent: Handle, max_value: float = 100,
                 width: Optional[int] = None,
                 layout: Optional[Layout] = None) -> ProgressHandle:
        """进度条：把首版返回的**闭包**中性化为 `ProgressHandle.update(value)`。

       逐行复刻首版 `create_progress_bar`：`Frame` + `Canvas(height=Theme.progress_default_height)`，
        背景矩形 `progress_track`、前景矩形 `progress_fill`（带 tag `progress_fill` 供探针读回宽度比）；
        `width=None ⇒ Theme.progress_default_width`。夹取语义见 `TkProgressHandle.update`。
        """
        self._ensure_alive()
        self._reject_layout(layout, "progress")
        resolved = self._validate_parent(parent)
        theme = self.theme
        bar_w = theme.progress_default_width if width is None else width
        bar_h = theme.progress_default_height
        frame = tk.Frame(resolved.native)
        # pady=10 与首版 `create_progress_bar` 逐字一致；该字面量**未**登记 token
        # （无 progress pady 行），按纪律不擅自新增 token ⇒ 保留字面量并登记为 未登记字面量。
        frame.pack(pady=10)
        canvas = tk.Canvas(frame, width=bar_w, height=bar_h, bg=theme.progress_background)
        canvas.pack()
        canvas.create_rectangle(0, 0, bar_w, bar_h, fill=theme.progress_track, outline="")
        rect = canvas.create_rectangle(0, 0, 0, bar_h, fill=theme.progress_fill,
                                       outline="", tags="progress_fill")
        return TkProgressHandle(frame, canvas, rect, max_value, bar_w, bar_h)

    def combo(self, parent: Handle, options: Sequence[str],
              default: Optional[str] = None, width: Optional[int] = None,
              editable: bool = True,
              on_select: Optional[Callable[[str], None]] = None,
              layout: Optional[Layout] = None) -> ComboHandle:
        """下拉框。首版 `create_combo_box`：`(StringVar, ttk.Combobox)`、`default=None ⇒ ''`、
        `editable=False ⇒ readonly`、选择时回调 `on_select(current_value)`。
        token：`width→combo_default_width`、`pady/padx→combo_pady/combo_padx`。
        **本批未实现** 首版的"输入时过滤候选"（留 的 combo 重写，已在报告登记）。
        """
        self._ensure_alive()
        self._reject_layout(layout, "combo")
        resolved = self._validate_parent(parent)
        theme = self.theme
        widget = ttk.Combobox(resolved.native, values=list(options),
                              width=theme.combo_default_width if width is None else width,
                              state=("normal" if editable else "readonly"))
        widget.pack(pady=theme.combo_pady, padx=theme.combo_padx)
        handle = TkComboHandle(widget, options, default, on_select)
        handle._sync_visual()
        widget.bind("<<ComboboxSelected>>", lambda _e: handle._fire_select())
        if editable:
            # **输入时过滤候选（首版 `create_combo_box` 的"自动补全"；登记为留到）**
            # 语义与首版逐字一致：不区分大小写的**子串**匹配；无命中 ⇒ 回落到完整列表；
            # 每次输入后 `event_generate("<Down>")` 弹出下拉。
            # `add="+"` 是必须的：句柄已在 `<KeyRelease>` 上装了"活值同步"，直接 `bind` 会**覆盖**它。
            widget.bind("<KeyRelease>", lambda _e: handle._apply_completion(), add="+")
        return handle

    def slider(self, parent: Handle, from_: float = 0, to: float = 100,
               default: Optional[float] = None, resolution: float = 1,
               width: Optional[int] = None, label: str = "",
               on_change: Optional[Callable[[float], None]] = None,
               show_value: bool = True,
               layout: Optional[Layout] = None) -> SliderHandle:
        """滑块。首版 `create_slider`：`default=None ⇒ from_`、按 `resolution` 吸附、
        变化时更新右侧值标签并调用 `on_change(value)`。
        token：`from_/to/resolution/width` 默认取 `slider_default_*`、`pady→slider_pady`、
        标签/值标签的 `padx/width` 取 `slider_label_padx`/`slider_value_padx`/`slider_value_width`。
        """
        self._ensure_alive()
        self._reject_layout(layout, "slider")
        resolved = self._validate_parent(parent)
        theme = self.theme
        lo = theme.slider_default_from if from_ is None else from_
        hi = theme.slider_default_to if to is None else to
        rs = theme.slider_default_resolution if resolution is None else resolution
        wd = theme.slider_default_width if width is None else width
        frame = tk.Frame(resolved.native)
        frame.pack(pady=theme.slider_pady)
        if label:
            tk.Label(frame, text=label).pack(side=tk.LEFT, padx=theme.slider_label_padx)
        scale = ttk.Scale(frame, from_=lo, to=hi, length=wd,
                          orient=getattr(tk, str(theme.slider_orient).upper(), tk.HORIZONTAL))
        scale.pack(side=tk.LEFT)
        value_label = None
        if show_value:
            value_label = tk.Label(frame, width=theme.slider_value_width)
            value_label.pack(side=tk.LEFT, padx=theme.slider_value_padx)
        handle = TkSliderHandle(scale, frame, value_label, default, lo, hi, rs, on_change)

        def _on_scale(_raw):
            snapped = handle._value._snap(scale.get())
            if snapped != handle._value._value:
                handle._value._value = snapped
                if value_label is not None:
                    value_label.config(text=TkSliderHandle._fmt(snapped))
                for cb in list(handle._value._callbacks):
                    cb(snapped)
                handle._fire_change()

        scale.configure(command=_on_scale)
        handle._sync_visual()
        return handle

    def spinbox(self, parent: Handle, from_: float = 0, to: float = 100,
                default: Optional[float] = None, step: float = 1,
                width: Optional[int] = None,
                command: Optional[Callable[[float], None]] = None,
                layout: Optional[Layout] = None) -> SpinboxHandle:
        """数值微调框。首版 `create_spinbox`：`default=None ⇒ from_`、`command(var.get())`。
        token：`from_/to/step/width` 默认取 `spin_default_from/to/step/width`、`pady/padx→spin_pady/padx`。
        中性规则（两端一致）：**程序化 `value.set()` 只触发 `on_change`**；`command` 只在原生/用户改变时触发。
        """
        self._ensure_alive()
        self._reject_layout(layout, "spinbox")
        resolved = self._validate_parent(parent)
        theme = self.theme
        lo = theme.spin_default_from if from_ is None else from_
        hi = theme.spin_default_to if to is None else to
        st = theme.spin_default_step if step is None else step
        wd = theme.spin_default_width if width is None else width
        init = lo if default is None else default
        widget = ttk.Spinbox(resolved.native, from_=lo, to=hi, increment=st, width=wd)
        widget.pack(pady=theme.spin_pady, padx=theme.spin_padx)
        handle = TkSpinboxHandle(widget, init, lo, hi, command)
        handle._sync_visual()
        widget.configure(command=lambda: handle._fire_command())
        return handle


    def searchable_list(self, parent: Handle, items: Sequence[str],
                        height: Optional[int] = None,
                        on_select: Optional[Callable[[str], None]] = None,
                        placeholder: str = "输入关键字过滤…",
                        layout: Optional[Layout] = None) -> ListHandle:
        """可搜索列表（落点）。

       结构对齐首版 `create_searchable_list`：`Frame`（`pady=list_container_pady`）+
        过滤 `Entry`（占位符 `placeholder`，默认取 `list_placeholder`）+ `Listbox`
        （`height→list_default_height`）+ `Scrollbar`。
        **过滤**：实时、**不区分大小写**的子串匹配（首版语义）。
        `Up`/`Down`/`Enter` 键位由 **backend** 定义并安装（本层绑定 `nav_keys` 中的三个序列；
        base 只承诺 `on_select` 与 `set_items`）。
        token：`list_padx`、`list_pady`、`list_default_height`、`list_scroll_width`、`list_placeholder`。
        """
        self._ensure_alive()
        self._reject_layout(layout, "searchable_list")
        resolved = self._validate_parent(parent)
        theme = self.theme
        frame = tk.Frame(resolved.native)
        frame.pack(pady=theme.list_container_pady)
        entry = tk.Entry(frame, width=theme.list_scroll_width // 8)
        entry.pack(padx=theme.list_padx, pady=theme.list_pady, fill=tk.X)
        entry.insert(0, placeholder if placeholder else theme.list_placeholder)
        entry.config(fg=theme.placeholder_color)
        box = tk.Frame(frame)
        box.pack(padx=theme.list_padx, pady=theme.list_pady, fill=tk.BOTH)
        listbox = tk.Listbox(box, height=theme.list_default_height if height is None else height)
        scrollbar = tk.Scrollbar(box)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=listbox.yview)
        handle = TkListHandle(frame, listbox, entry, items, on_select,
                              placeholder if placeholder else theme.list_placeholder)
        handle._apply_filter()
        entry.bind("<KeyRelease>", lambda _e: handle._apply_filter())
        listbox.bind("<Double-Button-1>", lambda _e: handle._select_current())
        for seq, delta in (("<Down>", 1), ("<Up>", -1)):
            listbox.bind(seq, lambda _e, d=delta: handle._move(d))
        listbox.bind("<Return>", lambda _e: handle._select_current())
        return handle


    def table(self, parent: Handle, headers: Sequence[str],
              rows: Optional[Sequence[Sequence[Any]]] = None,
              height: Optional[int] = None, select_mode: str = "browse",
              on_select: Optional[Callable[[Tuple[Any, ...], Any], None]] = None,
              column_widths: Optional[Sequence[int]] = None,
              layout: Optional[Layout] = None) -> TableHandle:
        """表格（落点）。

       首版 `create_table`：`Treeview(columns=headers)`；行可为 tuple/list；选择回调
        `on_select(tuple(values), row_id)`；无 `column_widths` 时**按标题/内容估算**列宽
        （`title*table_title_width_factor` 与 `len(cell)*table_row_width_factor+table_row_width_extra`
        取大，再夹到 `[table_column_width_min, table_column_width_max]`）。
        `row_id` 是 **Tk item id（`str`）**，**对调用方不透明**、跨后端不保证可解析；
        契约只冻结 `(values, row_id)` 的**形状**。
        token：`pady→table_container_pady`、`height→table_default_height`、
        `select_mode→table_select_mode`、`anchor→table_anchor`。
        """
        self._ensure_alive()
        self._reject_layout(layout, "table")
        resolved = self._validate_parent(parent)
        theme = self.theme
        frame = tk.Frame(resolved.native)
        frame.pack(pady=theme.table_container_pady)
        tree = ttk.Treeview(frame, columns=list(headers), show="headings",
                            height=theme.table_default_height if height is None else height,
                            selectmode=select_mode or theme.table_select_mode)
        data = [tuple(r) for r in (rows or [])]
        for idx, head in enumerate(headers):
            tree.heading(head, text=head)
            if column_widths is not None:
                width = column_widths[idx]
            else:
                widest = max([len(str(head)) * theme.table_title_width_factor]
                             + [len(str(r[idx])) * theme.table_row_width_factor
                                + theme.table_row_width_extra for r in data] or [0])
                width = max(theme.table_column_width_min,
                            min(theme.table_column_width_max, widest))
            tree.column(head, width=width, anchor=theme.table_anchor)
        for row in data:
            tree.insert("", "end", values=row)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = tk.Scrollbar(frame, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        handle = TkTableHandle(tree, frame, headers)
        if on_select is not None:
            tree.bind("<<TreeviewSelect>>",
                      lambda _e: on_select(tuple(tree.item(tree.selection()[0], "values"))
                                           if tree.selection() else (),
                                           tree.selection()[0] if tree.selection() else None))
        return handle


    def form(self, parent: Handle, fields: Sequence[Any],
             width: Optional[int] = None,
             layout: Optional[Layout] = None) -> FormHandle:
        """表单（commit 2）。首版 `create_form`：`fields` 每项 `(key, label, kind, *args)`，
        `kind ∈ {entry, combo, check, spin, slider, text}`；`get_values()` 返回 dict，
        `set_values(data)` **只设已存在 key**、未知 key **打印并跳过**。
        token：`width→form_default_width`、`pady→form_pady`、`form_grid_pady`、
        标签/单元格 `padx→form_grid_label_padx/form_grid_cell_padx`、`text` 高度 `form_text_lines`。
        """
        self._ensure_alive()
        self._reject_layout(layout, "form")
        resolved = self._validate_parent(parent)
        theme = self.theme
        frame = tk.Frame(resolved.native, width=theme.form_default_width if width is None
                         else width)
        frame.pack(pady=theme.form_pady)
        kinds, widgets, vars_ = {}, {}, {}
        for row, spec in enumerate(fields):
            key, label, kind = spec[0], spec[1], spec[2]
            args = list(spec[3:])
            tk.Label(frame, text=label).grid(row=row, column=0, sticky="w",
                                             padx=theme.form_grid_label_padx,
                                             pady=theme.form_grid_pady)
            if kind == "combo":
                w = ttk.Combobox(frame, values=list(args[0]) if args else [])
                # 默认值（首版：`(key, label, "combo", [选项], 默认值)`）
                if len(args) > 1:
                    w.set(str(args[1]))
            elif kind == "check":
                w = tk.Checkbutton(frame)
                # （甲）：同族站点，变量显式绑宿主（`form` 的 check 字段）。
                # 默认值（首版：`(key, label, "check", 默认bool)`）
                vars_[key] = tk.IntVar(master=frame, value=1 if (args and args[0]) else 0)
                w.config(variable=vars_[key])
            elif kind == "spin":
                w = ttk.Spinbox(frame, from_=args[0] if args else 0,
                                to=args[1] if len(args) > 1 else 100)
                # 初值：显式第三参 > from_（不设会让 `.get()` 返回空串，取值转换会炸）
                w.set(args[2] if len(args) > 2 else (args[0] if args else 0))
            elif kind == "slider":
                w = ttk.Scale(frame, from_=args[0] if args else 0,
                              to=args[1] if len(args) > 1 else 100)
                w.set(args[2] if len(args) > 2 else (args[0] if args else 0))
            elif kind == "text":
                w = tk.Text(frame, height=theme.form_text_lines)
                # 默认值（首版：`(key, label, "text", 行数, 默认文本)`）
                if len(args) > 1 and args[1]:
                    w.insert("1.0", str(args[1]))
            else:
                w = tk.Entry(frame)
                # 默认值（首版：`(key, label, "entry", 默认值)`）
                if args:
                    w.insert(0, str(args[0]))
            w.grid(row=row, column=1, sticky="we", padx=theme.form_grid_cell_padx,
                   pady=theme.form_grid_pady)
            kinds[key] = kind
            widgets[key] = w
        return TkFormHandle(frame, kinds, widgets, vars_)


    def notebook(self, parent: Handle, tabs: Sequence[Any],
                 height: Optional[int] = None, width: Optional[int] = None,
                 layout: Optional[Layout] = None) -> NotebookHandle:
        """页签容器（第 1 个 commit；的 renderer 侧落点）。

        `tabs` 每项 `(title, content)`，`content` 可为：
          * `None` ⇒ 空页；
          * **callable** ⇒ **以 `Handle`（内容页句柄）为唯一实参调用** —— 这正是 的修复：
           首版传的是 `tk.Frame`（Tk 泄漏），本层改传 backend 无关的 `Handle`
            （应用层 callable 的改写属 /，见 行）；
          * 控件列表/元组（元素为 `Handle`）⇒ 依次 `pack` 进内容页；
          * 单个 `Handle` ⇒ 直接放进内容页。
        token：`pady→notebook_pady`、内容页 `pady→notebook_content_pady`、
        尺寸 `notebook_default_size=(600, 280)`（`width`/`height` 可覆盖）。
        """
        self._ensure_alive()
        self._reject_layout(layout, "notebook")
        resolved = self._validate_parent(parent)
        theme = self.theme
        dw, dh = theme.notebook_default_size
        nb = ttk.Notebook(resolved.native, width=dw if width is None else width,
                          height=dh if height is None else height)
        nb.pack(pady=theme.notebook_pady)
        titles, frames = [], []
        for title, content in tabs:
            frame = tk.Frame(nb)
            frame.pack(pady=theme.notebook_content_pady)
            handle = TkHandle(frame)
            if callable(content) and not isinstance(content, Handle):
                content(handle)                      #：传 Handle，不传 tk.Frame
            elif isinstance(content, (list, tuple)):
                for child in content:
                    child.native.pack()
            elif content is not None:
                content.native.pack()
            nb.add(frame, text=title)
            titles.append(title)
            frames.append(frame)
        return TkNotebookHandle(nb, titles, frames)


    def scrollable(self, parent: Handle, width: Optional[int] = None,
                   height: Optional[int] = None,
                   background: Optional[str] = None,
                   layout: Optional[Layout] = None) -> ScrollableHandle:
        """**垂直**可滚动容器。结构对齐首版 `create_scrollable_canvas`：
        外层 `Frame` + `Canvas(bg=scroll_background, width/height=scroll_default_*)` +
        垂直 `Scrollbar` + 内容 `Frame`（`create_window` 承载，`<Configure>` 更新 `scrollregion`）。
        token：`width→scroll_default_width` / `height→scroll_default_height` /
        `background→scroll_background` / canvas 边框 `scroll_border`。
        **滚轮/scrollregion 归 backend**（中立契约无滚轮 API）。
        """
        self._ensure_alive()
        self._reject_layout(layout, "scrollable")
        resolved = self._validate_parent(parent)
        theme = self.theme
        frame = tk.Frame(resolved.native)
        canvas = tk.Canvas(frame,
                           width=theme.scroll_default_width if width is None else width,
                           height=theme.scroll_default_height if height is None else height,
                           bg=theme.scroll_background if background is None else background,
                           highlightthickness=theme.scroll_border)
        scrollbar = tk.Scrollbar(frame)
        content = tk.Frame(canvas)
        canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)   # 与首版一致
        frame.pack()
        return TkScrollableHandle(frame, canvas, scrollbar, content)

    def visualization_canvas(self, parent: Handle,
                             width: Optional[int] = None,
                             height: Optional[int] = None,
                             background: Optional[str] = None,
                             layout: Optional[Layout] = None) -> ScrollableHandle:
        """**水平**可滚动可视化画布。结构对齐首版 `create_scrollable_visualization_canvas`：
        `Canvas(bg=viz_background, 尺寸=viz_default_size)` + 水平 `Scrollbar` + 内容 `Frame`。
        token：`viz_default_size`（默认 `(800, 120)`）/ `viz_background` / `viz_border`。
        """
        self._ensure_alive()
        self._reject_layout(layout, "visualization_canvas")
        resolved = self._validate_parent(parent)
        theme = self.theme
        dw, dh = theme.viz_default_size
        frame = tk.Frame(resolved.native)
        canvas = tk.Canvas(frame,
                           width=dw if width is None else width,
                           height=dh if height is None else height,
                           bg=theme.viz_background if background is None else background,
                           highlightthickness=theme.viz_border)
        scrollbar = tk.Scrollbar(frame)
        content = tk.Frame(canvas)
        canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        frame.pack()
        return TkScrollableHandle(frame, canvas, scrollbar, content, horizontal=True)


    def bars(self, parent: Handle, data: Optional[Sequence[float]] = None,
             canvas_width: Optional[int] = None,
             canvas_height: Optional[int] = None,
             background: Optional[str] = None,
             min_bar_width: Optional[int] = None,
             padding: Optional[int] = None, label_rotation: int = 0,
             show_bg_stripes: bool = True,
             bar_colors: Optional[Sequence[str]] = None,
             layout: Optional[Layout] = None) -> Optional[Handle]:
        """水平可滚动柱状图（+，落点）。

        **空 `data` ⇒ 返回 `None`**（首版冻结语义，base 契约明文）。绘制（渐变 RGB 公式、
        旋转标签、条纹 stipple）**全部归 backend**（Tk Canvas）；中立契约只给数据 + 视觉参数。
：外层套 **水平滚动容器**
        （`visualization_canvas`，首版的 `scrollable_bars` 就是"水平 Scrollbar + 内容 Frame"），
        内层画布宽度取**绘制所需宽度**（`min_bar_width` 顶住时 > 视口宽）⇒ 长数据**真的**能横向滚，
        且柱子不会被画布边界**静默裁掉**。
        token：`bars_background / bars_stripe / bars_stripe_light / bars_text_color / bars_outline /
        bars_default_width / bars_default_height / bars_min_bar_width / bars_padding / bars_spacing /
        bars_label_band / bars_height_reserve / bars_font_*`。
        """
        self._ensure_alive()
        self._reject_layout(layout, "bars")
        if not data:
            return None                                  # 冻结哨兵：空数据 ⇒ None
        resolved = self._validate_parent(parent)
        theme = self.theme
        w = theme.bars_default_width if canvas_width is None else canvas_width
        h = theme.bars_default_height if canvas_height is None else canvas_height
        bg = theme.bars_background if background is None else background
        pad = theme.bars_padding if padding is None else padding
        min_w = theme.bars_min_bar_width if min_bar_width is None else min_bar_width
        n = len(data)
        step = max(min_w, (w - 2 * pad - (n - 1) * theme.bars_spacing) // n)
        # 内容宽度 = 绘制所需宽度（≥ 视口宽）⇒ 水平滚动真的有行程
        need_w = max(w, 2 * pad + n * step + (n - 1) * theme.bars_spacing)
        box = self.visualization_canvas(parent, width=w, height=h, background=bg)
        box.native.configure(bg=bg)
        canvas = tk.Canvas(box.content.native, width=need_w, height=h, bg=bg,
                           highlightthickness=0)
        canvas.pack()
        bottom = h - theme.bars_label_band - theme.bars_height_reserve
        if show_bg_stripes:
            y, idx = pad, 0
            while y < bottom:
                canvas.create_rectangle(0, y, need_w, y + 8,
                                        fill=(theme.bars_stripe if idx % 2 == 0
                                              else theme.bars_stripe_light),
                                        outline="")
                y += 8
                idx += 1
        mx = max(data) or 1
        colors = list(bar_colors) if bar_colors else _gradient_palette(n)
        for i, v in enumerate(data):
            bh = int((bottom - pad) * (float(v) / float(mx)))
            x = pad + i * (step + theme.bars_spacing)
            canvas.create_rectangle(x, bottom - bh, x + step, bottom,
                                    fill=colors[i % len(colors)],
                                    outline=theme.bars_outline, tags="bar")
            canvas.create_text(x + step / 2, bottom + theme.bars_label_band // 2, text=str(v),
                               fill=theme.bars_text_color,
                               font=(theme.bars_font_family,
                                     max(theme.bars_font_min,
                                         min(theme.bars_font_max, step // 4 or theme.bars_font_min))),
                               angle=label_rotation, tags="label")
        return TkBarsHandle(box.native, box._canvas, box._scrollbar, box.content.native,
                            canvas, n)


    # ------------------------------------------------------------------ #
    # 媒体释放
    # ------------------------------------------------------------------ #
    def clear_media(self) -> None:
        """停止并销毁本 Renderer 创建的**全部动画**，并清空登记（幂等）。

        **范围（与首版的差异，已登记）**：首版的 `MediaMixin.clear_media()` 清的是
        mixin 自己的"当前媒体"状态（`gif_label`/`frames`/`photo_img`/`_last_image_path`），
        还会销毁**它自己创建的那一个** label。renderer 层没有"当前媒体"这种隐式单例：
        `photo`/`frame_preview` 的句柄**归其显式 `parent` 所有**（销毁它们会越权），
        只有 `animation` 持有 renderer 侧状态（定时器/播放中）⇒ 本方法只针对**动画**：
        逐个 `stop()` + `destroy()` 并清空 `_media`。**不影响**其它控件。

        异常：Renderer 已销毁 ⇒ `RendererClosedError`；其余情况不抛（幂等）。
        """
        self._ensure_alive()
        for handle in list(self._media):
            try:
                handle.stop()
                handle.destroy()
            except Exception:                   # noqa: BLE001 —— 已被外部销毁：幂等
                pass
        self._media.clear()

    def container(self, parent: Handle, layout: Optional[Layout] = None,
                  col_weights: Optional[Sequence[int]] = None) -> Handle:
        """创建一个普通容器（/，已签）。

        `layout` 描述**该容器自身在 `parent` 中**如何放置；`None` ⇒ 取实现默认
        （Tk 适配层 = **顺序流** `pack`）。
        `col_weights` 是该容器**自身网格**的各列权重；本实现把"容器是否走网格"
       的判据系在 `layout.kind` 上：
          * `layout is None` 或 `kind='pack'` ⇒ **顺序流**容器 ⇒ `col_weights` 无意义，
            **按允许的静默忽略处理**（顺序流没有"列"这一概念）；
          * `kind='grid'` ⇒ 容器自身建网格 ⇒ 逐列 `grid_columnconfigure(i, weight=w)`；
           若网格存在却无法设置权重 ⇒ `NotSupportedError`（不得静默）。
       本方法只保证"容器被放进 `parent` 的几何管理"，**不**承诺权属；
        `layout.into` 非 `None` 时语义见 `apply_tk_layout`。
        异常：`InvalidParentError`（`parent` 非法）/ `RendererClosedError`（已销毁）/
        `NotSupportedError`（无法接管几何）。
        """
        self._ensure_alive()
        resolved = self._validate_parent(parent)
        frame = tk.Frame(resolved.native)
        effective = Layout.pack() if layout is None else layout
        # ：`col_weights` 是"**容器自身内部网格**"的列权重，与"容器自己在
        # `parent` 中怎么摆"是两件事 ⇒ **只要调用方给了就设置**（纯顺序流容器上它是惰性的：
        # 没有网格子项时 `grid_columnconfigure` 不影响任何布局）。原来的 `kind == "grid"` 门槛
        # 让 `pack_in_grid`（自身顺序流 + 内部网格）永远拿不到权重 ⇒ 静默丢弃。
        if col_weights is not None:
            try:
                for _i, _w in enumerate(col_weights):
                    frame.grid_columnconfigure(_i, weight=_w)
            except tk.TclError as exc:
                raise NotSupportedError(
                    "container: 无法设置列权重：%s" % (exc,)) from exc
        apply_tk_layout(frame, effective)
        return TkHandle(frame)

    def toolbar(self, parent: Handle,
                items: Optional[Sequence[Any]] = None) -> Handle:
        """工具条。首版 `create_toolbar`：`items` 每项 `(text, command, kind[, menu_items])`，
        `kind='button'|'menu'`，横向排列、`fill=x`。
        token：`padx/pady→toolbar_item_padx/toolbar_item_pady`、菜单 `tearoff→toolbar_menu_tearoff`。
        **例外（已批准）**：演示层把工具条放进 **root 容器**，其合法性由调用方传入的
        `parent` 决定；renderer 只按显式 parent 建控件，不设隐式"当前容器"。
        """
        self._ensure_alive()
        resolved = self._validate_parent(parent)
        theme = self.theme
        bar = tk.Frame(resolved.native)
        bar.pack(fill=tk.X)
        for item in (items or []):
            text, command, kind = item[0], item[1], item[2]
            extra = item[3] if len(item) > 3 else None
            if kind == "menu":
                mb = tk.Menubutton(bar, text=text)
                menu = tk.Menu(mb, tearoff=theme.toolbar_menu_tearoff)
                for entry in (extra or []):
                    label, action = entry[0], entry[1]
                    menu.add_command(label=label, command=action)
                mb.config(menu=menu)
                mb.pack(side=tk.LEFT, padx=theme.toolbar_item_padx,
                        pady=theme.toolbar_item_pady)
            else:
                btn = tk.Button(bar, text=text, command=command)
                btn.pack(side=tk.LEFT, padx=theme.toolbar_item_padx,
                         pady=theme.toolbar_item_pady)
        return TkHandle(bar)

    def status_bar(self, parent: Handle,
                   initial_text: str = "Ready") -> StatusBarHandle:
        """状态栏。首版 `create_status_bar`：返回 `(label, set_status)`；本层中性化为
        `StatusBarHandle.set_status(text)`。
        token：`initial_text`（空/None ⇒ `status_default_text`）、`bd→status_borderwidth`、
        `relief→status_relief`、`anchor→status_anchor`、`fill=x`。
        """
        self._ensure_alive()
        resolved = self._validate_parent(parent)
        theme = self.theme
        widget = tk.Label(resolved.native,
                          text=(initial_text or theme.status_default_text),
                          bd=theme.status_borderwidth, relief=theme.status_relief,
                          anchor=theme.status_anchor)
        widget.pack(fill=tk.X)
        return TkStatusBarHandle(widget)


    # ------------------------------------------------------------------ #
    # 窗口置顶与全局快捷键
    # ------------------------------------------------------------------ #
    def set_always_on_top(self, flag: bool = True) -> None:
        """置顶开关：Tk `root.attributes('-topmost', bool(flag))`（首版同写法）。"""
        self._ensure_alive()
        self._tk_root.attributes("-topmost", bool(flag))

    def add_shortcut(self, sequence: str, callback: Callable[[], None]) -> None:
        """注册全局快捷键。

        **落地**：`sequence` 是**backend 中立描述串**（如 `'Ctrl+S'`），
        Tk 专属写法（`'<Control-s>'`）**不接受**；转换由本适配层的 `_tk_sequence()` 完成。
       无法识别的修饰键/键位 ⇒ `NotSupportedError`（**不静默**）。
        回调**无参**、在 UI 线程同步执行；绑定随 `Renderer.destroy()`（root 销毁）释放。
        """
        self._ensure_alive()
        tk_seq = _tk_sequence(sequence)
        self._tk_root.bind(tk_seq, lambda _event: callback())
        self._shortcuts[tk_seq] = sequence

    # ------------------------------------------------------------------ #
    # 菜单栏与提示气泡
    # ------------------------------------------------------------------ #
    def menu_bar(self, parent: Handle, items: Optional[Sequence[Any]] = None) -> Handle:
        """窗口菜单栏（首版 `create_menu`）。

        **窗口级**部件：按 base 契约以**显式** `parent` 表达"这个菜单栏属于哪个窗口"
        （通常传 `Renderer.root`），挂载点是该容器的**顶层窗**（Tk `winfo_toplevel()`）。

        `items` 每项 `(菜单名, [(标签, 无参回调), ...])`；子菜单 `tearoff=theme.menu_tearoff`
        （首版同值）。**重复调用 = 替换**（与首版 `root.config(menu=…)` 一致；
       旧菜单栏在本层显式 `destroy()`，不留孤儿控件 —— 首版会漏掉）。
        返回：菜单栏 `Handle`（`native` = 顶层 `tk.Menu`）。
        """
        self._ensure_alive()
        resolved = self._validate_parent(parent)
        theme = self.theme
        top = resolved.native.winfo_toplevel()
        bar = tk.Menu(top)
        for entry in (items or []):
            name, sub = entry[0], (entry[1] if len(entry) > 1 else None)
            menu = tk.Menu(bar, tearoff=theme.menu_tearoff)
            bar.add_cascade(label=name, menu=menu)
            for item in (sub or []):
                label, command = item[0], (item[1] if len(item) > 1 else None)
                menu.add_command(label=label, command=command)
        old = getattr(self, "_menu_bar", None)
        top.config(menu=bar)
        if old is not None and old is not bar:
            try:
                old.destroy()                   # 替换语义：旧栏显式回收（幂等）
            except Exception:                   # noqa: BLE001
                pass
        self._menu_bar = bar
        return TkHandle(bar)

    def tooltip(self, target: Handle, text: str,
                delay_ms: Optional[int] = None) -> TooltipHandle:
        """给控件挂提示气泡（首版 `create_tooltip`）。

        `target` 是**显式**目标句柄（base 契约："tooltip 的'父'"）。悬停 `<Enter>` 起
        **延迟** `delay_ms` 毫秒显示（`None` ⇒ token `tooltip_delay_ms`=400），`<Leave>` 立即隐藏；
        显式 `show()` 不受延迟影响。
        token：`tooltip_background` / `tooltip_relief` / `tooltip_borderwidth` / `tooltip_padx` /
        `tooltip_pady` / `tooltip_offset` / `tooltip_delay_ms`（**全部被消费**；Qt 侧不消费前四项，见）。
        返回：`TooltipHandle`（`native` = 目标控件；气泡窗口经 `_tip` 读取）。
        """
        self._ensure_alive()
        resolved = self._validate_parent(target)
        return TkTooltipHandle(resolved.native, text, self.theme, delay_ms)

    # ------------------------------------------------------------------ #
    # 媒体：静态图 / 逐帧预览（Pillow 可选）
    # ------------------------------------------------------------------ #
    def photo(self, parent: Handle, path: str, text: str = "",
              color: Optional[str] = None, family: Optional[str] = None,
              size: Optional[int] = None, bold: Optional[bool] = None,
              frame: int = 0, warn_animated: bool = True,
              layout: Optional[Layout] = None) -> Optional[MediaHandle]:
        """静态图片（可取多帧文件的第 `frame` 帧）。

        **冻结语义**：无 Pillow / 路径为空 / 文件不存在 / 解码失败 ⇒ `None`（不抛）。
        `warn_animated=True` 且文件多帧 ⇒ 打印一条提示（首版同义；**只提示不改行为**）。
        token：`media_caption_compound`/`media_caption_color`/`media_caption_family`/
        `media_caption_size`/`media_caption_weight`（文字），`media_frame_grid_padx/pady`（间距）。
        返回容器句柄（结构见 `TkMediaHandle`）。
        """
        self._ensure_alive()
        resolved = self._validate_parent(parent)
        theme = self.theme
        frames = _tk_media_frames(path)
        if not frames:
            return None
        total = len(frames)
        idx = int(frame)
        if not (0 <= idx < total):          # 越界 ⇒ None（对齐首版：`seek` 越界即失败）
            return None
        if warn_animated and total > 1:
            _tk_warn_animated(path, total, idx)
        photo = _PIL_ImageTk.PhotoImage(frames[idx])
        box = tk.Frame(resolved.native)
        image_label = tk.Label(box, image=photo)
        image_label.pack()
        box._ck10_photos = [photo]
        box._ck10_image_label = image_label
        if text:
            caption = tk.Label(
                box, text=text, compound=theme.media_caption_compound,
                fg=theme.media_caption_color if color is None else color,
                font=(theme.media_caption_family if family is None else family,
                      theme.media_caption_size if size is None else size,
                      theme.media_caption_weight
                      if (bold is None and theme.media_caption_weight) else ("bold" if bold else "")))
            caption.pack()
            box._ck10_caption_label = caption
        if layout is not None:
            apply_tk_layout(box, layout)
        else:
            box.pack()
        return TkMediaHandle(box)

    def frame_preview(self, parent: Handle, path: str, columns: int = 3,
                      thumb_width: Optional[int] = None, labels: bool = True,
                      max_frames: Optional[int] = None,
                      layout: Optional[Layout] = None) -> Optional[Handle]:
        """逐帧缩略图预览（首版 `show_frames`）。

        `thumb_width=None` ⇒ token `media_thumb_width`（**像素值不在 base 硬编码**）。
        冻结语义同 `photo`：路径为空 / 无 Pillow / 解码失败 ⇒ `None`。
        第 0 帧标注用 `media_frame_default`（红）、其余帧用 `media_frame_animation`（绿），
        字体 `media_frame`；格间距 `media_frame_grid_padx/pady`。
        """
        self._ensure_alive()
        resolved = self._validate_parent(parent)
        theme = self.theme
        width = int(theme.media_thumb_width if thumb_width is None else thumb_width)
        frames = _tk_media_frames(path, max_frames=max_frames)
        if not frames:
            return None
        box = tk.Frame(resolved.native)
        keep = []
        cols = max(1, int(columns))
        for idx, img in enumerate(frames):
            ratio = width / float(img.width or 1)
            thumb = img.resize((width, max(1, int(img.height * ratio))))
            ph = _PIL_ImageTk.PhotoImage(thumb)
            keep.append(ph)
            cell = tk.Frame(box)
            cell.grid(row=idx // cols, column=idx % cols,
                      padx=theme.media_frame_grid_padx, pady=theme.media_frame_grid_pady)
            tk.Label(cell, image=ph).pack()
            if labels:
                tk.Label(cell, text=("默认图/封面" if idx == 0 else "帧 %d" % idx),
                         fg=theme.media_frame_default if idx == 0 else theme.media_frame_animation,
                         font=theme.media_frame).pack()
        box._ck10_photos = keep
        if layout is not None:
            apply_tk_layout(box, layout)
        else:
            box.pack()
        return TkMediaHandle(box)

    def animation(self, parent: Handle, path: str, text: str = "",
                  color: Optional[str] = None, family: Optional[str] = None,
                  size: Optional[int] = None, bold: Optional[bool] = None,
                  start: int = 0, max_frames: Optional[int] = None,
                  max_loops: Optional[int] = None,
                  on_frame: Optional[Callable[[int, int], None]] = None,
                  frame_delay: Optional[int] = None,
                  layout: Optional[Layout] = None) -> AnimationHandle:
        """播放动画（GIF/APNG/动态 WebP）。

        **失败哨兵（冻结）**：**永不返回 `None`**；加载失败 / 无 Pillow ⇒ `frame_count == 0`
        （对应首版 `animation(...) -> int` 的 `0`）。此时容器仍然创建（空图），
        调用方按 `frame_count == 0` 判断并自行 `destroy()`。
        `start` = 起始帧；`max_frames` 限制**加载**帧数；`max_loops=None` 无限；
        每帧回调 `on_frame(index, total)`；`frame_delay` 覆盖每帧延迟（仍受
        `media_min_frame_delay_ms` 下限约束，同首版）。
        token：`media_min_frame_delay_ms`(20) + `media_caption_*`（说明文字）。
        """
        self._ensure_alive()
        resolved = self._validate_parent(parent)
        theme = self.theme
        frames = _tk_media_frames(path, max_frames=max_frames) or []
        delays = []
        if frames:
            try:
                img = _PIL_Image.open(path)
                for idx in range(len(frames)):
                    if idx:
                        img.seek(idx)
                    delays.append(int(img.info.get("duration") or 0))
            except Exception:                   # noqa: BLE001 —— 取不到延时 ⇒ 用最小值
                delays = []
        if frame_delay is not None:
            delays = [int(frame_delay)] * len(frames)
        box = tk.Frame(resolved.native)
        image_label = tk.Label(box)
        image_label.pack()
        box._ck10_image_label = image_label
        if text:
            caption = tk.Label(
                box, text=text, compound=theme.media_caption_compound,
                fg=theme.media_caption_color if color is None else color,
                font=(theme.media_caption_family if family is None else family,
                      theme.media_caption_size if size is None else size,
                      theme.media_caption_weight
                      if (bold is None and theme.media_caption_weight) else ("bold" if bold else "")))
            caption.pack()
            box._ck10_caption_label = caption
        if layout is not None:
            apply_tk_layout(box, layout)
        else:
            box.pack()
        handle = TkAnimationHandle(self, box, image_label, frames, delays, theme,
                                   start=start, max_loops=max_loops, on_frame=on_frame)
        self._media.append(handle)
        return handle


    # ------------------------------------------------------------------ #
    # 剪贴板（真实实现；已销毁 ⇒ RendererClosedError）
    # ------------------------------------------------------------------ #
    def set_clipboard_text(self, text: str) -> None:
        """写入系统剪贴板（Tk `clipboard_clear()` + `clipboard_append(text)`）。

       与首版一致（`gui/advanced_widgets.py:1084-1085` 的写法；首版只在文本非空时写，
        本层按契约**如实写入传入文本**，含空串）。base 契约：返回 `None`；同步；
        `destroy()` 后抛 `RendererClosedError`。
        """
        self._ensure_alive()
        self._tk_root.clipboard_clear()
        self._tk_root.clipboard_append(text)

    def get_clipboard_text(self) -> str:
        """读取系统剪贴板；**无内容/无文本形式时返回空串**（base 明文：`返回 str；无内容返回空串`）。

        Tk 在"剪贴板为空 / 只有非文本形式（如图片）"时 `clipboard_get()` 抛 `TclError`，
        按契约译成**空串**（不是异常、也不是 `None`）。`destroy()` 后抛 `RendererClosedError`。
        """
        self._ensure_alive()
        try:
            return self._tk_root.clipboard_get()
        except tk.TclError:
            return ''

    def message(self, title: str, text: str, kind: str = "info") -> None:
        """模态消息框。

       映射（首版 `create_message_box` 的语义）：`info→showinfo` / `warning→showwarning` /
        `error→showerror`；**未知 `kind` 无动作**（首版明文；`接口合同`）。
        **同步性**：模态 ⇒ **阻塞**直到用户关闭（中立契约"同步返回"）。因此**探针不得直接调用**，
        只能对 `tkinter.messagebox` 打桩后断言 **dispatch**（本批 parity 即如此做）。
        """
        self._ensure_alive()
        fn = {"info": messagebox.showinfo, "warning": messagebox.showwarning,
              "error": messagebox.showerror}.get(kind)
        if fn is None:
            return                                   #：未知 kind **不动作**（不静默降级）
        # **显式传 parent**。Tk 的对话框无 parent 时会退回**进程级** `_default_root`
        #（`commondialog.Dialog.show()` → `master = self.master or _get_temp_root()`），
        # 这是隐式进程级依赖，与纪律相悖，且多根/迁移期/测试下会把对话框挂到别的根。
        fn(title, text, parent=self._tk_root)

    def ask_input(self, title: str = "输入", prompt: str = "请输入:",
                  default: str = "") -> Optional[str]:
        """**同步**文本输入框。

        实现：Tk `simpledialog.askstring(title, prompt, initialvalue=default)` —— **阻塞**直到确认/取消。
        返回：确认 ⇒ `str`；**取消/关闭 ⇒ `None`**（契约冻结；Tk 侧原生即返回 `None`）。
        探针注意：模态阻塞 ⇒ parity 用**打桩记录 dispatch**，不直接调用。
        """
        self._ensure_alive()
        return simpledialog.askstring(title, prompt, initialvalue=default,
                                      parent=self._tk_root)      #：显式 parent

    def ask_save_path(self, title: str = "保存文件",
                      defaultextension: str = ".csv",
                      filetypes: Optional[Sequence[Tuple[str, str]]] = None
                      ) -> Optional[str]:
        """**同步**保存路径选择。

        实现：Tk `filedialog.asksaveasfilename(...)`；`filetypes=None` ⇒ `(('CSV 文件','*.csv'),
        ('所有文件','*.*'))`（首版默认）。
        返回：确认 ⇒ `str`；**取消 ⇒ `None`** —— Tk 取消时返回**空串**，本层按契约**归一化为 `None`**
        （契约原文："取消返回 `None`（首版上游也可能返回空串，语义同）"）。
        """
        self._ensure_alive()
        # 判据用 `is None`（`[]` 是"显式给空过滤表"，不是"未提供"）
        types = (list(filetypes) if filetypes is not None
                 else [("CSV 文件", "*.csv"), ("所有文件", "*.*")])
        path = filedialog.asksaveasfilename(title=title, defaultextension=defaultextension,
                                            filetypes=types, parent=self._tk_root)
        return path or None


    def ask_open_path(self, title: str = "选择文件",
                      filetypes: Optional[Sequence[Tuple[str, str]]] = None
                      ) -> Optional[str]:
        """**同步**打开文件路径选择。

        实现：Tk `filedialog.askopenfilename(...)`；`filetypes=None` ⇒ `(('所有文件','*.*'),)`
        （首版 `create_file_dialog` 的默认）。
       返回：确认 ⇒ `str`；**取消 ⇒ `None`**（："取消 ⇒ `None`（冻结）"；
        Tk 取消返回空串 ⇒ 本层**归一化为 `None`**）。
        """
        self._ensure_alive()
        types = (list(filetypes) if filetypes is not None else [("所有文件", "*.*")])
        path = filedialog.askopenfilename(title=title, filetypes=types,
                                          parent=self._tk_root)
        return path or None

    def ask_directory(self, title: str = "选择目录") -> Optional[str]:
        """**同步**目录选择：Tk `filedialog.askdirectory(...)`。

        返回：确认 ⇒ `str`；**取消 ⇒ `None`**（同上归一化；`title` 默认 `'选择目录'`，
        媒体拆帧导出用 `Theme.media_export_dialog_title` = `'选择拆帧输出目录'`）。
        """
        self._ensure_alive()
        path = filedialog.askdirectory(title=title, parent=self._tk_root)
        return path or None


    def report_window(self, title: str, text: str) -> Handle:
        """只读文本报告窗口（首版 `show_image_report` 的**展示部分**）。

        **顶层部件**（base 契约：不接受 `parent`，由本 Renderer 自己拥有）。
       只负责**展示** —— 报告**内容**由数据层（`utils/apng.py`）生成；首版里的
        「复制报告 / 拆帧导出… / 关闭」三个按钮属**业务组合**，不在本层：由 C/G 段用
        `container` + `button` + `本句柄` 组合（`关闭` = `handle.destroy()`）。

       结构逐行对齐首版：`Toplevel`（几何 = token `media_report_window_size`）
        + `Text`（`wrap='none'`、只读、字体 = token `report`）+ 垂直/水平 `Scrollbar`
        （双向 `yscrollcommand`/`command` 接线）+ `rowconfigure/columnconfigure` 权重。

        返回：窗口 `Handle`（`destroy()` 关窗，幂等）。
        同步性：同步返回，**不进入局部事件循环**（非模态，与 `message`/`ask_*` 相对）。
        释放：随本句柄 `destroy()` 或 `Renderer.destroy()` 释放。
        """
        self._ensure_alive()
        theme = self.theme
        win = tk.Toplevel(self._tk_root)
        win.title(title)
        win.geometry("%dx%d" % tuple(theme.media_report_window_size))
        win.transient(self._tk_root)

        body = tk.Text(win, wrap="none", font=theme.report)
        yscroll = tk.Scrollbar(win, orient="vertical", command=body.yview)
        xscroll = tk.Scrollbar(win, orient="horizontal", command=body.xview)
        body.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        body.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        win.rowconfigure(0, weight=1)
        win.columnconfigure(0, weight=1)

        body.insert("1.0", text)
        body.configure(state="disabled")

        handle = TkHandle(win)
        self._reports.append(handle)
        return handle

    def toast(self, text: str, duration_ms: Optional[int] = None,
              kind: str = "info") -> None:
        """轻提示：无边框置顶小窗，`duration_ms` 后自动销毁（首版 `show_toast`）。

        `kind∈{info, success, warning, error}` 决定底色（token）；**未知 kind 回退 `info`**（首版明文）。
        token：`toast_default_duration_ms`、`toast_info/success/warning/error`、`toast_text_color`、
        `toast_overrideredirect`/`toast_topmost`、`toast`（字体）、`toast_padx/pady`、`toast_bottom_offset`。
        """
        self._ensure_alive()
        theme = self.theme
        color = {"info": theme.toast_info, "success": theme.toast_success,
                 "warning": theme.toast_warning, "error": theme.toast_error}.get(
                     kind, theme.toast_info)
        duration = theme.toast_default_duration_ms if duration_ms is None else duration_ms
        root = self._tk_root
        top = tk.Toplevel(root)
        top.overrideredirect(bool(theme.toast_overrideredirect))
        top.attributes("-topmost", bool(theme.toast_topmost))
        fam, size = theme.toast
        tk.Label(top, text=text, bg=color, fg=theme.toast_text_color,
                 font=(fam, size), padx=theme.toast_padx,
                 pady=theme.toast_pady).pack()
        root.update_idletasks()
        x = root.winfo_screenwidth() // 2 - top.winfo_reqwidth() // 2
        y = root.winfo_screenheight() - top.winfo_reqheight() - theme.toast_bottom_offset
        top.geometry("+%d+%d" % (max(0, x), max(0, y)))
        top.after(duration, top.destroy)
        self._toasts.append(top)

    def _live_toasts(self):
        """私有：当前仍存活的 toast 顶层窗数量（供探针读取，避免直接依赖 Toplevel 计数）。"""
        alive = [t for t in self._toasts if bool(t.winfo_exists())]
        self._toasts = alive
        return len(alive)



def _gradient_palette(n: int):
    """按索引生成渐变调色板（这是 **backend 自己的**视觉实现，不属 base 契约）。"""
    out = []
    for i in range(max(1, n)):
        t = i / max(1, n - 1) if n > 1 else 0.0
        out.append("#%02x%02x%02x" % (int(0x4c + t * (0x21 - 0x4c)),
                                      int(0xaf + t * (0x96 - 0xaf)),
                                      int(0x50 + t * (0xf3 - 0x50))))
    return out
