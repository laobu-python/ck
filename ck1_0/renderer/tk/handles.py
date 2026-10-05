"""handles.py —— Tk 后端的中立句柄与值。

本模块**顶层不 import tkinter**：只持有原生控件引用并调用其方法，因此
`import ck1_0.renderer.tk.handles` 不需要 tkinter 存在。
（唯一的例外是 `TkToggleHandle._make_label` 的**函数内**导入 —— 那条路径是
"标签缺失时补建"的防御分支，正常流程恒由 renderer 建好标签，故此导入
不会在模块导入期发生。）

契约要点（详见 `ck1_0/renderer/base.py` 的 `Handle` / `Value` / `ToggleHandle`）
    * `exists()` 与 `Renderer.is_alive()` 的**异常策略相反是有意的**：
      `exists()` 探测失败 ⇒ 返回 `False`（不承载）；`is_alive()` 必须上抛。
    * `ToggleHandle` 的回调纪律（两后端必须一致）：
      同值 ⇒ 不触发、不重绘；变更时**先 `on_change` 后 `command`**；
      每次可见变更 `command` **恰好一次**（点击路径内部必须走 `value.set()`，
      不得再额外直调 `command`）。
    *：`set_enabled(False)` **只阻止用户交互**，程序化 API 仍可用，**不得改变值**。
    *：`text=''` 仍**创建**标签（内容为空串），与首版的 `if text:` 有意不同。
"""

from __future__ import annotations

import tkinter as tk

try:                                    # 可选依赖（与 renderer 同策略：缺 Pillow 不致命）
    from PIL import ImageTk as _PIL_ImageTk
except ImportError:                     # pragma: no cover
    _PIL_ImageTk = None

from ..base import (FormHandle, Handle, InvalidParentError, NotebookHandle,
                    NotSupportedError,
                    CheckboxHandle, ComboHandle, InputHandle, RadioGroupHandle, ScrollableHandle,
                    FormHandle, SliderHandle, SpinboxHandle, ListHandle, NotebookHandle,
                    TableHandle,
                    StatusBarHandle,
                    AnimationHandle,
                    LabelHandle,
                    MediaHandle,
                    TextAreaHandle, ProgressHandle, RendererClosedError, TimerHandle, ToggleHandle,
                    TooltipHandle, Value)

__all__ = ["TkHandle", "TkTimerHandle", "TkToggleHandle", "TkValue", "TkProgressHandle",
           "apply_tk_layout", "TkTextValue", "TkInputHandle", "TkTextAreaHandle",
           "TkCheckValue", "TkCheckboxHandle", "TkIndexValue", "TkRadioGroupHandle",
           "TkScrollableHandle", "TkBarsHandle", "TkLabelsHandle", "TkTextVarValue", "TkComboHandle",
           "TkFloatValue", "TkSpinboxHandle", "TkNumValue", "TkSliderHandle", "TkListHandle", "TkStatusBarHandle", "TkNotebookHandle", "TkFormHandle", "TkTableHandle", "TkTooltipHandle", "TkMediaHandle", "TkAnimationHandle",
           "TkLabelHandle"]


def apply_tk_layout(widget, layout) -> None:
    """把 `Layout` 意图应用到 Tk 控件（**含 `into`**）。

    （已签）：`pack(in_=…)`/`grid(in_=…)` 的 `-in` **只重设几何管理** ——
    **不改控件树、不转移所有权**：主体 `winfo_parent()` 不变、`into` 的
    `winfo_children()` 不含主体、`into` 销毁后主体**仍存活**（只是 `winfo_manager()` 变空）。

   三处显式异常（不得静默）：
      * `layout.into` 非 `Handle` ⇒ `InvalidParentError`；
      * `layout.into` 已失效 ⇒ `RendererClosedError`（由 `Handle.native` 的存活校验抛出）；
      * Tk 无法接管几何（典型：`into` 不是主体 parent 本身或其后代）⇒ `NotSupportedError`
        （把 Tcl 的 `can't pack … inside …` 译成契约异常，不让 `TclError` 泄漏）。
    """
    into = getattr(layout, "into", None)
    kw = {}
    if into is not None:
        if not isinstance(into, Handle):
            raise InvalidParentError(
                "layout.into 必须是 Handle 或 None，收到 %r" % (into,)
            )
        kw["in_"] = into.native          # 已失效 ⇒ RendererClosedError
    try:
        if layout.kind == "pack":
            widget.pack(side=layout.side, fill=(layout.fill or "none"),
                        expand=bool(layout.expand), padx=layout.padx, pady=layout.pady,
                        anchor=layout.anchor, **kw)
        elif layout.kind == "grid":
            widget.grid(row=layout.row, column=layout.column, rowspan=layout.rowspan,
                        columnspan=layout.columnspan, padx=layout.padx, pady=layout.pady,
                        sticky=(layout.sticky or ""), **kw)
        else:
            raise NotSupportedError("未知布局 kind: %r" % (layout.kind,))
    except tk.TclError as exc:
        raise NotSupportedError(
            "Tk 无法把该控件交给 into 接管几何（-in 要求 into 是主体 parent 本身或其后代）：%s"
            % (exc,)
        ) from exc


class TkHandle(Handle):
    """包装单个 Tk 控件的句柄。

    私有属性:
        _widget: 被包装的 Tk 控件（构造后不再更换）。
    """

    def __init__(self, widget):
        self._widget = widget

    # ------------------------------------------------------------------ #
    # Handle 抽象面
    # ------------------------------------------------------------------ #
    @property
    def native(self) -> object:
        """**逃生口**：返回被包装的 Tk 控件。句柄已失效时抛 `RendererClosedError`。"""
        self._ensure_alive()
        return self._widget

    def _ensure_alive(self) -> None:
        """私有：句柄已失效时抛 `RendererClosedError`（供内部与 Value 复用）。"""
        if not self.exists():
            raise RendererClosedError(
                "%s 已失效（控件已销毁或其祖先已销毁）" % type(self).__name__
            )

    def exists(self) -> bool:
        """底层 Tk 控件当前是否仍存在。

        实现中立语义：**只问控件自身**（`winfo_exists()`），**不问** parent 是否存活
。查询失败 ⇒ 返回 `False`（`Handle.exists` 的异常策略，与
        `Renderer.is_alive()` 相反）。
        """
        try:
            return bool(self._widget.winfo_exists())
        except Exception:  # noqa: BLE001 —— 契约：探测失败即视为不存在
            return False

    def destroy(self) -> None:
        """销毁控件及其子树；**幂等**，已销毁时静默返回。"""
        if self.exists():
            try:
                self._widget.destroy()
            except Exception:  # noqa: BLE001 —— 并发/已消失：幂等语义要求静默
                pass

    def layout(self, layout) -> None:
        """（重新）应用布局（真实实现）。

        `layout.into is None` ⇒ 在主体**当前所属**容器内重排自身；
        `layout.into` 是 `Handle` ⇒ 请求该容器**接管几何管理**（Tk `-in`）。

        **语义（已签）**：`-in` 只重设几何管理，**不改控件树、不转移所有权** ——
        主体的 `winfo_parent()` 不变；`into` 的 `winfo_children()` 不含主体；`into` 被
        `destroy()` 后主体**仍存活**，只是 `winfo_manager()` 变空（本方法不承诺生命周期）。
        异常：见模块级 `apply_tk_layout`（`InvalidParentError` / `RendererClosedError` /
        `NotSupportedError`）；本句柄已失效时抛 `RendererClosedError`。
        """
        self._ensure_alive()
        apply_tk_layout(self._widget, layout)

    def set_enabled(self, enabled: bool) -> None:
        """启用/禁用**用户交互**；**不改变控件的值**。"""
        self._ensure_alive()
        self._widget.configure(state=("normal" if enabled else "disabled"))


class TkValue(Value):
    """包装 Tk 侧状态的可观察值（本批为 `bool`）。

    值本身存在本对象里（不依赖 `tk.BooleanVar`），因此 `get()` 不触碰 Tk；
    视觉同步与组件级回调经 `_handle` 完成。
    """

    def __init__(self, handle: TkToggleHandle, initial: bool):
        self._handle = handle
        self._value = bool(initial)
        self._callbacks = []

    def get(self):
        """读取当前值；所属控件已销毁时抛 `RendererClosedError`。"""
        self._handle._ensure_alive()
        return self._value

    def set(self, value) -> None:
        """写入新值。

       纪律（与 Qt 后端必须一致）：
            同值 ⇒ **直接返回**（不触发回调、不重绘）；
            变更 ⇒ ① 更新内部值 → ② 重绘视觉（`ToggleHandle` 要求"写入值与显示
            状态不得脱节"）→ ③ 触发 `on_change` → ④ 触发组件级 `command`。
            **先 `on_change` 后 `command`**，且 `command` 恰好一次。
        """
        self._handle._ensure_alive()
        resolved = bool(value)
        if resolved == self._value:
            return                      # 同值：不触发、不重绘
        self._value = resolved
        self._handle._redraw()
        for callback in list(self._callbacks):
            callback(resolved)
        self._handle._fire_command(resolved)

    def on_change(self, callback):
        """注册变更回调，返回幂等的退订函数。"""
        self._handle._ensure_alive()
        self._callbacks.append(callback)

        def _unsubscribe():
            try:
                self._callbacks.remove(callback)
            except ValueError:
                pass

        return _unsubscribe


class TkToggleHandle(ToggleHandle):
    """复合开关句柄：容器 Frame + 轨道/滑块 Canvas + 标签。

    私有属性:
        _frame/_canvas/_label: 三个原生控件；
        _value: `TkValue`；
        _command: 组件级回调（收 `bool`）；
        _enabled:  的交互开关（为假时点击无效，但不影响程序化 API）。
    """

    def __init__(self, frame, canvas, label, width, height,
                 on_color, off_color, knob, outline, default, command):
        self._frame = frame
        self._canvas = canvas
        self._label = label
        self._width = width
        self._height = height
        self._on_color = on_color
        self._off_color = off_color
        self._knob = knob
        self._outline = outline
        self._command = command
        self._enabled = True
        self._value = TkValue(self, default)

    # ------------------------------------------------------------------ #
    # 私有：视觉与回调
    # ------------------------------------------------------------------ #
    def _redraw(self) -> None:
        """按当前值重绘轨道与滑块（配方取自首版 `create_toggle_switch`）。"""
        canvas = self._canvas
        width, height = self._width, self._height
        knob_r = height // 2 - 3
        track = self._on_color if self._value.get() else self._off_color
        canvas.delete("all")
        canvas.create_rectangle(knob_r, 2, width - knob_r, height - 2,
                                fill=track, outline="")
        canvas.create_oval(0, 0, height, height, fill=track, outline="")
        canvas.create_oval(width - height, 0, width, height, fill=track, outline="")
        cx = (width - knob_r - 3) if self._value.get() else (knob_r + 3)
        canvas.create_oval(cx - knob_r, 3, cx + knob_r, height - 3,
                           fill=self._knob, outline=self._outline)

    def _fire_command(self, value: bool) -> None:
        """触发组件级回调（`command` 恰好一次的**唯一**出口）。"""
        if self._command is not None:
            self._command(value)

    def _on_click(self, event=None) -> None:
        """用户点击：**走 `value.set()`**，因此回调顺序与去重由 `TkValue` 保证。

        `_enabled` 为假（禁用）时直接返回 —— 只阻止用户交互。
        """
        if not self._enabled:
            return
        if not self.exists():
            return
        self._value.set(not self._value.get())

    # ------------------------------------------------------------------ #
    # ToggleHandle / Handle 抽象面
    # ------------------------------------------------------------------ #
    @property
    def value(self):
        """本开关的 `Value`（`bool`）。"""
        self._ensure_alive()
        return self._value

    def set_text(self, text: str) -> None:
        """更新标签文本（**空串合法**）。只改文本：不改值、不触发任何回调。

        防御性行为（**非 base 契约义务**）：若标签已被单独销毁（例如用户直接调用
        `label.destroy()`），本实现会补建新标签。base 只要求"更新文本、空串合法、标签仍存在、
        句柄失效抛 `RendererClosedError`"；**Qt 后端无需复制此行为**（守卫查实际存在性，非 `is None`）。
        """
        self._ensure_alive()
        if not self._label_alive():
            self._label = self._make_label(text)
        self._label.configure(text=text)

    def _label_alive(self) -> bool:
        """标签当前是否仍存在。

        `_ensure_alive()` 已先行通过（容器存活 ⇒ 解释器存活），故此处
        `winfo_exists()` 不会因"应用已销毁"而抛，无需 try/except。
        """
        return self._label is not None and bool(self._label.winfo_exists())

    def _make_label(self, text: str):
        """（补建路径）重建标签控件，仍 `side='left'`，故位于 Canvas 右侧。"""
        import tkinter as tk

        label = tk.Label(self._frame, text=text)
        label.pack(side="left")
        return label

    @property
    def native(self) -> object:
        """**逃生口**：返回最外层容器 Frame（Canvas/Label 见各自私有属性）。"""
        self._ensure_alive()
        return self._frame

    def exists(self) -> bool:
        """最外层容器是否仍存在；查询失败 ⇒ `False`。"""
        try:
            return bool(self._frame.winfo_exists())
        except Exception:  # noqa: BLE001 —— 契约：探测失败即视为不存在
            return False

    def destroy(self) -> None:
        """销毁容器及其子树（Canvas/Label 随之销毁）；**幂等**。"""
        if self.exists():
            try:
                self._frame.destroy()
            except Exception:  # noqa: BLE001 —— 幂等语义要求静默
                pass

    def set_enabled(self, enabled: bool) -> None:
        """`False` ⇒ **只阻止用户交互**；程序化 `value.set()` 仍可用；**不改变值**。"""
        self._ensure_alive()
        self._enabled = bool(enabled)

    def layout(self, layout) -> None:
        """（重新）应用布局（语义同 `TkHandle.layout`，含 的 `-in` 说明）。"""
        self._ensure_alive()
        apply_tk_layout(self._frame, layout)

    # 与 TkHandle 同名同义的私有助手（两个句柄类各自独立，不共享基类以避免菱形）
    def _ensure_alive(self) -> None:
        """私有：句柄已失效时抛 `RendererClosedError`。"""
        if not self.exists():
            raise RendererClosedError(
                "%s 已失效（控件已销毁或其祖先已销毁）" % type(self).__name__
            )


class TkTimerHandle(TimerHandle):
    """`TkRenderer.schedule()` 返回的定时器句柄（中立化落点）。

    **不继承 `Handle`**：base 的 `TimerHandle` 是独立 ABC，只要求 `cancel()` /
    `is_active()` —— 定时器没有控件、没有 parent、没有布局/启用语义。

    私有属性:
        _root: 排定该定时器的 `tk.Tk`；
        _id: `Tk.after()` 返回的定时器 id（`native` 逃生口）；
        _cancelled: `cancel()` 是否已被调用（**只**记录显式取消，不是"回调是否跑过"的推断）。
    """

    def __init__(self, root, timer_id):
        self._root = root
        self._id = timer_id
        self._cancelled = False

    @property
    def native(self) -> object:
        """**逃生口**：`Tk.after()` 的定时器 id。"""
        return self._id

    def cancel(self) -> None:
        """取消定时器，**幂等**（契约"异常: 无"）。

        Tcl 的 `after cancel` 对未知 id 本就安全（实测不抛），这里仍统一兜住异常，
        以覆盖"解释器已销毁"等边界；`_cancelled` 保证重复调用不再触碰 Tcl。
        """
        if self._cancelled:
            return
        self._cancelled = True
        try:
            self._root.tk.call("after", "cancel", self._id)
        except Exception:                       # noqa: BLE001 —— 契约：cancel 不抛
            pass

    def is_active(self) -> bool:
        """定时器是否**仍处于已排定（尚未触发/取消）状态**。

        实现中立：查 Tcl 的 `after info <id>`（排定中返回非空元组；已触发/已取消抛
        `TclError`）。**不得**用"回调是否跑过"推断（base 明文）。
        **本机 Python 3.11 的 `tkinter` 没有 `Misc.after_info()`**（3.13 才加入），
        故直接走 `tk.call('after', 'info', …)` —— 与 `after_info()` 内部同一条 Tcl 命令。
       查询失败 ⇒ `False`（base 明文允许：本方法不承载该纪律）。
        """
        if self._cancelled:
            return False
        try:
            return bool(self._root.tk.call("after", "info", self._id))
        except Exception:                       # noqa: BLE001
            return False


class TkProgressHandle(ProgressHandle, TkHandle):
    """`TkRenderer.progress()` 返回的进度条句柄。

    复合结构：`Frame`（容器）+ `Canvas`（背景矩形 + 前景矩形）。
    `update(value)` 逐行复刻首版 `create_progress_bar` 的**夹取语义**：
    `max_value <= 0` 时 `value > 0` 视为满，否则按 `value / max_value` 比例算宽度并夹到 `[0, width]`。

    私有属性:
        _frame/_canvas: 原生控件（`native` 逃生口返回 **Canvas**，即进度条的可见部分）；
        _rect: 前景矩形 item id（带 tag `progress_fill`，供探针按 tag 读回宽度比）；
        _max/_width: 夹取与比例换算用。
    """

    def __init__(self, frame, canvas, rect, max_value, width, height):
        # 复用 TkHandle 的 exists/destroy/layout/set_enabled（作用于**复合结构的 Frame**）
        TkHandle.__init__(self, frame)
        self._frame = frame
        self._canvas = canvas
        self._rect = rect
        self._max = max_value
        self._width = width
        self._height = height

    @property
    def native(self) -> object:
        """**逃生口**：绘制该进度条的 `tk.Canvas`（复合结构的可见部分）。"""
        self._ensure_alive()
        return self._canvas

    def update(self, value: float) -> None:
        """更新进度；实现须夹到 `[0, max_value]`（`max_value <= 0` ⇒ `value > 0` 视为满）。"""
        if self._max <= 0:
            progress_width = self._width if value > 0 else 0
        else:
            progress_width = (value / self._max) * self._width
        progress_width = max(0, min(self._width, progress_width))
        self._canvas.coords(self._rect, 0, 0, progress_width, self._height)


class TkTextValue(Value):
    """文本型 neutral `Value`（`input` / `text_area` 的 `.value`）。

    **占位符中性化（核心语义决定）**：Tk 用"把提示文本真的插进控件并染灰"实现占位符，
    故控件内容会等于占位符；本类让 `get()` 在**只显示占位符**时返回 `''` —— 这样
    `value.get()` 的语义在两个后端一致（Qt 用原生 `placeholderText()`，内容本来就是空）。
    用户输入触发（Tk `<KeyRelease>`）与程序化 `set()` 都会触发 `on_change`（各恰好一次）。
    """

    def __init__(self, handle, placeholder, multi=False):
        self._handle = handle
        self._widget = handle._widget
        self._placeholder = placeholder
        self._multi = multi
        self._callbacks = []
        self._widget.bind("<KeyRelease>", lambda _e: self._fire())

    def _raw(self) -> str:
        return (self._widget.get("1.0", "end-1c") if self._multi
                else self._widget.get())

    def _fire(self):
        for cb in list(self._callbacks):
            cb(self.get())

    def get(self):
        """读取当前值；**只显示占位符时返回空串**（后端中性化）；已销毁 ⇒ `RendererClosedError`。"""
        self._handle._ensure_alive()
        raw = self._raw()
        return "" if raw == self._placeholder else raw

    def set(self, value) -> None:
        """写入新值。

        **中性化**：写入后内容为空 ⇒ **重新显示灰色占位符**（与 Qt 的原生
        `placeholderText` 在空内容时始终可见一致）；`get()` 依旧把它遮蔽成 `''`。
        非空 ⇒ 写入正文并把文字色切回 `input_text_color`。
        """
        self._handle._ensure_alive()
        text = "" if value is None else str(value)
        if self._multi:
            self._widget.delete("1.0", "end")
        else:
            self._widget.delete(0, "end")
        if text:
            if self._multi:
                self._widget.insert("1.0", text)
            else:
                self._widget.insert(0, text)
            self._widget.config(fg=self._handle._text_color)
        else:
            # 空 ⇒ 恢复占位符（中性语义；Qt 侧由原生 placeholder 承担同一职责）
            if self._multi:
                self._widget.insert("1.0", self._placeholder)
            else:
                self._widget.insert(0, self._placeholder)
            self._widget.config(fg=self._handle._theme.placeholder_color)
        self._fire()

    def on_change(self, callback) -> None:
        """注册"值变化"回调（**收一个参数**：新值）。"""
        self._callbacks.append(callback)


class TkInputHandle(InputHandle, TkHandle):
    """单行输入框句柄。"""

    def __init__(self, widget, placeholder, theme):
        TkHandle.__init__(self, widget)
        self._placeholder = placeholder
        self._theme = theme
        self._text_color = theme.input_text_color
        self._value = TkTextValue(self, placeholder, multi=False)

    @property
    def value(self):
        return self._value

    def set_placeholder(self, text: str) -> None:
        """替换占位提示；**若当前正显示占位符**则同步刷新为新文本（不覆盖用户已输入的值）。"""
        self._ensure_alive()
        if self._value.get() == "" and self._widget.get() == self._placeholder:
            self._widget.delete(0, "end")
            self._widget.insert(0, text)
            self._widget.config(fg=self._theme.placeholder_color)
        self._placeholder = text
        self._value._placeholder = text


class TkTextAreaHandle(TextAreaHandle, TkHandle):
    """多行文本框句柄。"""

    def __init__(self, widget, placeholder, theme):
        TkHandle.__init__(self, widget)
        self._placeholder = placeholder
        self._theme = theme
        self._text_color = theme.input_text_color
        self._value = TkTextValue(self, placeholder, multi=True)

    @property
    def value(self):
        return self._value

    def set_placeholder(self, text: str) -> None:
        self._ensure_alive()
        if self._value.get() == "" and self._value._raw() == self._placeholder:
            self._widget.delete("1.0", "end")
            self._widget.insert("1.0", text)
            self._widget.config(fg=self._theme.placeholder_color)
        self._placeholder = text
        self._value._placeholder = text


class TkCheckValue(Value):
    """`checkbox` 的 neutral `Value`（bool）。

    纪律（与 toggle 一致）：**同值 ⇒ 直接返回**（不触发、不重绘）；
    变更 ⇒ 更新值 → 触发 `on_change` → 触发组件级 `command`（**先 on_change 后 command**，各恰好一次）。
    """

    def __init__(self, handle, initial):
        self._handle = handle
        self._value = bool(initial)
        self._callbacks = []

    def get(self):
        self._handle._ensure_alive()
        return self._value

    def set(self, value) -> None:
        self._handle._ensure_alive()
        resolved = bool(value)
        if resolved == self._value:
            return
        self._value = resolved
        self._handle._sync_visual()
        for cb in list(self._callbacks):
            cb(resolved)
        self._handle._fire_command()

    def on_change(self, callback) -> None:
        self._callbacks.append(callback)


class TkCheckboxHandle(CheckboxHandle, TkHandle):
    """复选框句柄。"""

    def __init__(self, widget, var, default, command, value_cls):
        TkHandle.__init__(self, widget)
        self._var = var
        self._command = command
        self._value = value_cls(self, default)

    @property
    def value(self):
        return self._value

    def _fire_command(self) -> None:
        if self._command is not None:
            self._command()

    def _sync_visual(self) -> None:
        """把 neutral 值同步到原生变量（用户点击时由 Tk 变量回调反向同步，见 renderer）。"""
        self._var.set(1 if self._value._value else 0)

    def set_enabled(self, enabled: bool) -> None:
        """启用/禁用交互；**不改变值**。"""
        self._ensure_alive()
        self._widget.config(state=(tk.NORMAL if enabled else tk.DISABLED))


class TkIndexValue(Value):
    """`radio_group` 的 neutral `Value`（选中**索引**，int）。首版语义：变量值 = 选中索引。"""

    def __init__(self, handle, initial):
        self._handle = handle
        self._value = int(initial)
        self._callbacks = []

    def get(self):
        self._handle._ensure_alive()
        return self._value

    def set(self, value) -> None:
        self._handle._ensure_alive()
        resolved = int(value)
        if resolved == self._value:
            return
        self._value = resolved
        self._handle._sync_visual()
        for cb in list(self._callbacks):
            cb(resolved)

    def on_change(self, callback) -> None:
        self._callbacks.append(callback)


class TkRadioGroupHandle(RadioGroupHandle, TkHandle):
    """单选组句柄；`native` 为**容器 Frame**。"""

    def __init__(self, frame, var, options, default, value_cls):
        TkHandle.__init__(self, frame)
        self._var = var
        self._options = list(options)
        self._value = value_cls(self, default)

    @property
    def value(self):
        return self._value

    @property
    def options(self):
        return list(self._options)

    def _sync_visual(self) -> None:
        self._var.set(self._value._value)

    def set_enabled(self, enabled: bool) -> None:
        self._ensure_alive()
        for rb in self._widget.winfo_children():
            try:
                rb.config(state=(tk.NORMAL if enabled else tk.DISABLED))
            except tk.TclError:
                pass


class TkScrollableHandle(ScrollableHandle, TkHandle):
    """可滚动容器句柄。

    复合结构：外层 `Frame`（`native`）+ `Canvas` + `Scrollbar` + 内容 `Frame`（`.content`）。
    滚轮与 `scrollregion` **归 backend**（中立契约没有滚轮 API）：滚轮绑定在画布与内容框架上
    （**不**使用首版的全局 `bind_all` 分发，避免多实例互相覆盖）。
    """

    def __init__(self, frame, canvas, scrollbar, content, horizontal=False):
        TkHandle.__init__(self, frame)
        self._canvas = canvas
        self._scrollbar = scrollbar
        self._content = TkHandle(content)
        self._horizontal = horizontal
        if horizontal:
            canvas.configure(xscrollcommand=scrollbar.set)
            scrollbar.configure(orient=tk.HORIZONTAL, command=canvas.xview)
            content.bind("<Configure>",
                         lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.bind("<Shift-MouseWheel>",
                        lambda e: canvas.xview_scroll(-1 if e.delta > 0 else 1, "units"))
        else:
            canvas.configure(yscrollcommand=scrollbar.set)
            scrollbar.configure(orient=tk.VERTICAL, command=canvas.yview)
            content.bind("<Configure>",
                         lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.bind("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))
            content.bind("<MouseWheel>",
                         lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))

    @property
    def content(self):
        """内部内容容器（可放子控件 / 绘图）。"""
        return self._content


class TkBarsHandle(TkScrollableHandle):
    """`bars` 句柄：外层是**水平滚动容器**。

    `native` = 外层 `Frame`（**可 pack / 可 `.layout(...)`**，与首版返回外层容器一致），
    `.content` = 内容 `Frame`，`art` = **自绘画布**（绘制证据读它：`find_withtag('bar')`）；
    `drawn` == 实际画出的柱数。

   渐变 RGB、旋转标签、条纹 stipple 全是 Tk Canvas 概念 —— 本类只把它们画在
    **backend 自己的** Canvas 上；中立契约只给"数据 + 视觉参数"。
    **`art` 的存在理由**：之后 `native` 变成外层滚动容器，自绘画布不再等于 `native`；
    断言与调用方要读绘制结果时用 `art`（不用去祖先链里找）。
    """

    def __init__(self, frame, canvas, scrollbar, content, art, drawn):
        TkScrollableHandle.__init__(self, frame, canvas, scrollbar, content, horizontal=True)
        self.art = art
        self.drawn = drawn


class TkLabelsHandle(TkScrollableHandle):
    """`labels` 句柄：外层是**垂直滚动容器**。

    `native` = 外层 `Frame`（**可 pack / 可 `.layout(...)`** —— 与首版返回外层 Frame 一致），
    `.content` = 内容 `Frame`（每项一个 `Label` 排在它里面）；`drawn` == 实际条目数。

    **为什么 `native` 不指向内容 Frame**：内容 Frame 由 `Canvas.create_window` 托管，新手若对它
   调 `.layout(...)`（首版的写法）会撞 Tk 的 geometry 冲突；返回外层容器则天然可用。
    """

    def __init__(self, frame, canvas, scrollbar, content, drawn):
        TkScrollableHandle.__init__(self, frame, canvas, scrollbar, content)
        self.drawn = drawn


class TkTextVarValue(Value):
    """字符串型 neutral `Value`（`combo` 用）。

   中性回调规则（两端一致）：**程序化 `set()` 只触发 `on_change`**；组件级
    `on_select` 只在**用户选择**（原生 `<<ComboboxSelected>>`）时触发 —— 这样"程序化写入
    不冒充用户操作"在两个 backend 上语义一致。
    """

    def __init__(self, handle, initial):
        self._handle = handle
        self._value = "" if initial is None else str(initial)
        self._callbacks = []

    def get(self):
        self._handle._ensure_alive()
        return self._value

    def set(self, value) -> None:
        self._handle._ensure_alive()
        new = "" if value is None else str(value)
        if new == self._value:
            return
        self._value = new
        self._handle._sync_visual()
        for cb in list(self._callbacks):
            cb(new)

    def on_change(self, callback) -> None:
        self._callbacks.append(callback)


class TkComboHandle(ComboHandle, TkHandle):
    """下拉框句柄；`native` = `ttk.Combobox`。"""

    def __init__(self, widget, options, default, on_select):
        TkHandle.__init__(self, widget)
        self._options = list(options)
        self._on_select = on_select
        self._value = TkTextVarValue(self, default)
        # **跨后端对齐**：`value` 必须是**活值**。
        # 实测：Qt 侧 `currentTextChanged` 会在**任何**文本变化（含用户输入）时更新 `_value`，
        # 而本类原先只在 `<<ComboboxSelected>>` 时更新 ⇒ 输入后 `value.get()` 是**旧值**
        # （首版的 `combo_var` 是 StringVar，本来就是活的）。这里在 `<KeyRelease>` 上同步：
        # 更新 `_value` 并触发 `on_change`（**不**触发 `on_select` ——  的冻结规则是
        # 「`on_select` 只在**选择**时触发」）。
        widget.bind("<KeyRelease>", lambda _e: self._sync_from_widget())

    def _apply_completion(self) -> None:
        """按当前输入过滤候选（**首版 `create_combo_box` 的自动补全语义**）：
        不区分大小写的**子串**匹配；无命中 ⇒ 回落到完整候选表；随后弹出下拉。
        独立成方法（而不是塞在渲染层的闭包里）是为了**可确定性断言** —— 与可搜索列表的
        `_apply_filter()` 同法；`<KeyRelease>` 的绑定只决定「谁在什么时候调它」。
        """
        typed = self._widget.get()
        allv = [str(o) for o in self._options]
        matches = [o for o in allv if typed.lower() in o.lower()] if typed else []
        self._widget["values"] = matches if matches else allv
        self._widget.event_generate("<Down>")

    def _sync_from_widget(self) -> None:
        """把控件里的文本同步进 neutral 值并触发 `on_change`（同值不触发）。"""
        text = self._widget.get()
        if text == self._value._value:
            return
        self._value._value = text
        for _cb in list(self._value._callbacks):
            _cb(text)

    @property
    def value(self):
        return self._value

    def _sync_visual(self) -> None:
        self._widget.set(self._value._value)

    def _fire_select(self) -> None:
        self._value._value = self._widget.get()
        if self._on_select is not None:
            self._on_select(self._value._value)


class TkFloatValue(Value):
    """浮点型 neutral `Value`（`spinbox` 用）；`set()` 夹到 `[lo, hi]`（两端一致）。"""

    def __init__(self, handle, initial, lo, hi):
        self._handle = handle
        self._lo = float(lo)
        self._hi = float(hi)
        self._value = min(max(float(initial), self._lo), self._hi)
        self._callbacks = []

    def get(self):
        self._handle._ensure_alive()
        return self._value

    def set(self, value) -> None:
        self._handle._ensure_alive()
        new = min(max(float(value), self._lo), self._hi)
        if new == self._value:
            return
        self._value = new
        self._handle._sync_visual()
        for cb in list(self._callbacks):
            cb(new)

    def on_change(self, callback) -> None:
        self._callbacks.append(callback)


class TkSpinboxHandle(SpinboxHandle, TkHandle):
    """数值微调框句柄；`command` 只在**原生/用户**改变时触发（与 Qt 侧一致）。"""

    def __init__(self, widget, default, lo, hi, command):
        TkHandle.__init__(self, widget)
        self._command = command
        self._value = TkFloatValue(self, default, lo, hi)

    @property
    def value(self):
        return self._value

    def _sync_visual(self) -> None:
        self._widget.set(self._value._value)

    def _fire_command(self) -> None:
        if self._command is not None:
            self._command(self._value._value)


class TkNumValue(Value):
    """数值型 neutral `Value`（`slider`）；`set()` 夹到 `[lo, hi]` 并按 `resolution` 吸附。"""

    def __init__(self, handle, initial, lo, hi, resolution):
        self._handle = handle
        self._lo, self._hi, self._res = float(lo), float(hi), float(resolution) or 1.0
        self._value = self._snap(initial)
        self._callbacks = []

    def _snap(self, v):
        v = min(max(float(v), self._lo), self._hi)
        return round(v / self._res) * self._res

    def get(self):
        self._handle._ensure_alive()
        return self._value

    def set(self, value) -> None:
        self._handle._ensure_alive()
        new = self._snap(value)
        if new == self._value:
            return
        self._value = new
        self._handle._sync_visual()
        for cb in list(self._callbacks):
            cb(new)

    def on_change(self, callback) -> None:
        self._callbacks.append(callback)


class TkSliderHandle(SliderHandle, TkHandle):
    """滑块句柄；`native` = `ttk.Scale`。程序化 `set()` 只触发 `on_change`（规则）。

    **复合控件**：真实结构是「外层 `Frame`（标签 + 滑轨 + 数值）」，而 `native` 是其中的
    `ttk.Scale`（契约冻结，不改）⇒ 句柄另外持有**外层容器**，由 `outer` 公开
    （三个引导的两拨独立实现都撞到过"对 `native` 排队会把标签落下"）。
    """

    def __init__(self, widget, outer, value_label, default, lo, hi, resolution, on_change):
        TkHandle.__init__(self, widget)
        self._outer_handle = TkHandle(outer)
        self._value_label = value_label
        self._on_change = on_change
        self._value = TkNumValue(self, lo if default is None else default, lo, hi, resolution)

    @property
    def outer(self):
        """**入列单位**：外层 `Frame`（`native` 是它里面的 `ttk.Scale`）。"""
        return self._outer_handle

    @property
    def value(self):
        return self._value

    def _sync_visual(self) -> None:
        self._widget.set(self._value._value)
        if self._value_label is not None:
            self._value_label.config(text=self._fmt(self._value._value))

    @staticmethod
    def _fmt(v):
        return ("%g" % v)

    def _fire_change(self) -> None:
        if self._on_change is not None:
            self._on_change(self._value._value)


class TkListHandle(ListHandle, TkHandle):
    """可搜索列表句柄。

    `Up`/`Down`/`Enter` 键位属于 **backend** —— Tk 侧显式 `bind`（本类暴露 `nav_keys`
    供断言读取"确实装了哪些键位"）；base 只承诺 `on_select` + `set_items`。
    """

    def __init__(self, frame, listbox, entry, items, on_select, placeholder=""):
        TkHandle.__init__(self, frame)
        self._listbox = listbox
        self._entry = entry
        # 中性化：Entry 里的**占位符**不算过滤词（与 `input` 的占位符中性化同法）
        self._placeholder = placeholder
        self._all = list(items)
        self._on_select = on_select
        self._value = TkTextVarValue(self, None)
        self.nav_keys = ["<Down>", "<Up>", "<Return>"]

    @property
    def native(self):
        self._ensure_alive()
        return self._listbox

    @property
    def value(self):
        return self._value

    @property
    def selection(self):
        sel = self._listbox.curselection()
        return self._listbox.get(sel[0]) if sel else None

    def set_items(self, items) -> None:
        """替换全部候选并**按当前过滤词重新过滤**（与首版的 `set_items` 一致）。"""
        self._ensure_alive()
        self._all = list(items)
        self._apply_filter()

    def _sync_visual(self) -> None:
        """把 neutral 过滤词写回过滤框并**重新过滤**（`Value.set()` 的落地）。

        **为什么必须有它**（实测发现）：`Value.set` 是 base 的**抽象公共 API**，而
        `TkTextVarValue.set` 会回调 `self._handle._sync_visual()`；本类原先没有该方法 ⇒
        `list.value.set('x')` 直接抛 `AttributeError`（**两个 backend 同错**：Qt 侧对称缺失）。
       对照：首版的对应写法 `search_var.set('x')` 是**能用**的（StringVar + trace 重新过滤）。
        语义与 `get()` / `_filtered()` **对称**：空串 ⇒ 恢复占位符（占位符不算过滤词 ⇒ 显示全部）。
        """
        text = "" if self._value._value is None else str(self._value._value)
        self._entry.delete(0, "end")
        self._entry.insert(0, text if text else self._placeholder)
        self._apply_filter()

    def _filtered(self):
        raw = self._entry.get()
        kw = "" if raw == self._placeholder else raw.strip().lower()
        return [x for x in self._all if kw in str(x).lower()] if kw else list(self._all)

    def _apply_filter(self) -> None:
        self._listbox.delete(0, "end")
        for x in self._filtered():
            self._listbox.insert("end", x)

    def _select_current(self) -> None:
        item = self.selection
        if item is None:
            return
        self._value._value = item
        if self._on_select is not None:
            self._on_select(item)

    def _move(self, delta) -> None:
        sel = self._listbox.curselection()
        n = self._listbox.size()
        if n == 0:
            return
        idx = 0 if not sel else max(0, min(n - 1, sel[0] + delta))
        self._listbox.selection_clear(0, "end")
        self._listbox.selection_set(idx)
        self._listbox.activate(idx)


class TkStatusBarHandle(StatusBarHandle, TkHandle):
    """状态栏句柄；`native` = `tk.Label`；`set_status(text)` 即改标签文本。"""

    def __init__(self, widget):
        TkHandle.__init__(self, widget)

    def set_status(self, text: str) -> None:
        self._ensure_alive()
        self._widget.config(text="" if text is None else str(text))


class TkNotebookHandle(NotebookHandle, TkHandle):
    """页签容器句柄（第 1 个 commit）；`native` = `ttk.Notebook`。"""

    def __init__(self, widget, titles, frames):
        TkHandle.__init__(self, widget)
        self._titles = list(titles)
        self._frames = list(frames)

    @property
    def tabs(self):
        return list(self._titles)

    def select(self, title: str) -> None:
        """切换到指定页签；未知标题 ⇒ `InvalidParentError`（显式拒绝，不静默）。"""
        self._ensure_alive()
        if title not in self._titles:
            raise InvalidParentError("未登记的页签标题：%r" % (title,))
        self._widget.select(self._frames[self._titles.index(title)])


class TkFormHandle(FormHandle, TkHandle):
    """表单句柄（commit 2）；`native` = 外层 `Frame`。

    `get_values()` 返回中性 dict（entry/combo/text → `str`、check → `bool`、spin/slider → `float`）；
    `set_values(data)` **只设置已存在的 key**，未知 key **打印提示并跳过**（首版语义）。
    """

    def __init__(self, frame, kinds, widgets, vars_):
        TkHandle.__init__(self, frame)
        self._kinds = dict(kinds)
        self._widgets = dict(widgets)
        self._vars = dict(vars_)

    def get_values(self):
        self._ensure_alive()
        out = {}
        for key, kind in self._kinds.items():
            w = self._widgets[key]
            if kind == "check":
                out[key] = bool(self._vars[key].get())
            elif kind in ("spin", "slider"):
                # ttk.Spinbox.get() 返回**字符串**（可能为空）⇒ 防御性转换（两端取值同型 float）
                out[key] = float(w.get() or 0)
            elif kind == "text":
                out[key] = w.get("1.0", "end-1c")
            else:
                out[key] = str(w.get())
        return out

    def set_values(self, data) -> None:
        self._ensure_alive()
        for key, value in dict(data).items():
            if key not in self._kinds:
                print("form.set_values: 未知字段 %r，已跳过" % (key,))
                continue
            kind = self._kinds[key]
            w = self._widgets[key]
            if kind == "check":
                self._vars[key].set(bool(value))
            elif kind in ("spin", "slider"):
                w.set(float(value))
            elif kind == "text":
                w.delete("1.0", "end")
                w.insert("1.0", "" if value is None else str(value))
            elif kind == "combo":
                w.set("" if value is None else str(value))
            else:
                w.delete(0, "end")
                w.insert(0, "" if value is None else str(value))


class TkTableHandle(TableHandle, TkHandle):
    """表格句柄；`native` = `ttk.Treeview`。

    `on_select` 的第二个实参是 **Tk Treeview 的 item id（`str`）** —— 这是 **backend 概念**，
    对调用方**不透明**、跨后端不保证可解析（Qt 侧对应的是**行索引 `int`**）。契约只冻结
    "回调收 `(values_tuple, row_id)`"这一**形状**。
    """

    def __init__(self, tree, outer, headers):
        TkHandle.__init__(self, tree)
        # **复合控件**：真实结构是「外层 `Frame`（Treeview + 垂直滚动条）」，而 `native` 是 Treeview
        # （契约冻结）⇒ 另外持有外层容器，由 `outer` 公开。
        self._outer_handle = TkHandle(outer)
        self._headers = list(headers)

    @property
    def outer(self):
        """**入列单位**：外层 `Frame`（`native` 是它里面的 `ttk.Treeview`）。"""
        return self._outer_handle

    def set_rows(self, rows) -> None:
        self._ensure_alive()
        for iid in self._widget.get_children():
            self._widget.delete(iid)
        for row in (rows or []):
            self._widget.insert("", "end", values=tuple(row))

    def get_rows(self):
        self._ensure_alive()
        return [tuple(self._widget.item(i, "values")) for i in self._widget.get_children()]

    @property
    def selection(self):
        self._ensure_alive()
        sel = self._widget.selection()
        return sel[0] if sel else None


class TkTooltipHandle(TooltipHandle, TkHandle):
    """提示气泡句柄；`native` = **被挂载的目标控件**。

    为什么 `native` 不是气泡窗口：气泡是**临时**对象（显示时才有、隐藏即销毁），
    拿它当"存在性基准"会让 `exists()` 随显隐抖动，违反 `Handle.exists()` 的实现中立定义
    （"底层对象当前是否仍然存在/可用"）。因此存在性以 **target** 为准，气泡 widget 经
    `_tip` 读取（未显示 ⇒ `None`）。

   行为（token 与首版 `create_tooltip` 同一组）：
        * `<Enter>` 起 **延迟** `handle._delay` 毫秒显示（`delay_ms=None` ⇒ `tooltip_delay_ms`）；
        * `<Leave>` 立即隐藏（并取消未到期的延迟）；
        * `show()`/`hide()` 是**显式**入口：`show()` 立即显示（不受 delay 影响），`hide()` 幂等。
    视觉：`tooltip_background` / `tooltip_relief` / `tooltip_borderwidth` / `tooltip_padx` /
    `tooltip_pady`，位置 = 指针 + `tooltip_offset`。

    `layout()` / `set_enabled()` 对**气泡**不适用 ⇒ `NotSupportedError`（不静默）。
    """

    def __init__(self, target, text, theme, delay_ms=None):
        TkHandle.__init__(self, target)
        self._target = target
        self._text = text
        self._theme = theme
        self._delay = theme.tooltip_delay_ms if delay_ms is None else int(delay_ms)
        self._tip = None
        self._after = None
        # 互见引用：目标控件保留一份句柄，便于探针/应用层确认"已挂提示"
        # （同首版 `_ensure_global_mousewheel` 的 `_ck10_wheel_bound` 先例）
        try:
            target._ck10_tooltip = self
        except Exception:                       # noqa: BLE001 —— 目标不允许挂属性时忽略
            pass
        target.bind("<Enter>", self._on_enter, add="+")
        target.bind("<Leave>", self._on_leave, add="+")

    # ---------------------------------------------------------------- #
    # 悬停驱动
    # ---------------------------------------------------------------- #
    def _on_enter(self, _event=None):
        if self._tip is not None or self._after is not None:
            return
        self._after = self._target.after(max(0, self._delay), self._do_show)

    def _on_leave(self, _event=None):
        self._cancel_pending()
        self._do_hide()

    def _cancel_pending(self):
        if self._after is not None:
            try:
                self._target.after_cancel(self._after)
            except Exception:                   # noqa: BLE001 —— 已触发/已销毁：幂等
                pass
            self._after = None

    def _do_show(self):
        self._after = None
        if self._tip is not None or not self.exists():
            return
        theme = self._theme
        dx, dy = theme.tooltip_offset
        tip = tk.Toplevel(self._target)
        tip.wm_overrideredirect(True)
        tip.wm_geometry("+%d+%d" % (self._target.winfo_pointerx() + dx,
                                    self._target.winfo_pointery() + dy))
        label = tk.Label(tip, text=self._text,
                         background=theme.tooltip_background,
                         relief=theme.tooltip_relief,
                         borderwidth=theme.tooltip_borderwidth,
                         padx=theme.tooltip_padx, pady=theme.tooltip_pady)
        label.pack()
        self._tip = tip

    def _do_hide(self):
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:                   # noqa: BLE001 —— 幂等
                pass
            self._tip = None

    # ---------------------------------------------------------------- #
    # TooltipHandle / Handle 面
    # ---------------------------------------------------------------- #
    def show(self) -> None:
        """立即显示（**不受** `delay_ms` 影响）。已显示时幂等。"""
        self._ensure_alive()
        self._do_show()

    def hide(self) -> None:
        """立即隐藏（幂等）；同时取消未到期的延迟。"""
        self._ensure_alive()
        self._cancel_pending()
        self._do_hide()

    def destroy(self) -> None:
        """销毁气泡并解除绑定（幂等）；**不销毁 target**（契约：句柄归 target 所有）。"""
        self._cancel_pending()
        self._do_hide()
        try:
            self._target.unbind("<Enter>")
            self._target.unbind("<Leave>")
            if getattr(self._target, "_ck10_tooltip", None) is self:
                del self._target._ck10_tooltip
        except Exception:                       # noqa: BLE001 —— 目标已销毁：幂等
            pass

    def layout(self, layout) -> None:
        raise NotSupportedError("tooltip 不参与布局（气泡位置 = 指针 + tooltip_offset）")

    def set_enabled(self, enabled: bool) -> None:
        raise NotSupportedError("tooltip 不支持 set_enabled")


class TkMediaHandle(MediaHandle, TkHandle):
    """静态图片 / 逐帧预览容器句柄；`native` = 外层容器。

    为与 Qt 侧**结构一致**，`photo`/`frame_preview` 都返回"容器 + 图片 `Label` + 说明 `Label`"：

        * `photo`：`native` = `tk.Frame`；视觉 = 图片在上、说明文字在下（等价首版
         单 `Label` 的 `compound='top'`；**结构**不同、**可见结果**相同，见报告）；
        * `frame_preview`：`native` = 栅格 `tk.Frame`，每格 = 缩略图 + 帧标签。

   图片对象存在 `container._ck10_photos`（首版的 `self.photo_img` 同因：Tk 的
    `PhotoImage` 若无人引用会被 GC，图片随即消失）。
    """


class TkAnimationHandle(AnimationHandle, TkHandle):
    """动画句柄；`native` = 外层容器（`Frame`）。

    **失败哨兵（冻结）**：`animation()` **永不返回 `None`**；加载失败 / 无 Pillow 时
    `frame_count == 0`（对应首版的 `0` 哨兵）。失败时容器仍然创建（空图）——
   这是把首版"返回 `0` 且不建控件"**中性化**为"总能拿到句柄"的必然结果，
   调用方可用 `frame_count == 0` 判断并自行 `destroy()`（见报告）。

    播放：每帧延迟 = `frame_delay`（显式）或文件自带 `duration`，**一律不低于**
    `media_min_frame_delay_ms`（首版同规则）；`start` 为起始帧；`max_loops=None`
    表示无限；每显示一帧调用 `on_frame(index, total)`。定时器经 `Renderer.schedule`
    排定（因此 `Renderer.destroy()` 会取消它们）。
    """

    def __init__(self, renderer, container, image_label, frames, delays, theme,
                 start=0, max_loops=None, on_frame=None):
        TkHandle.__init__(self, container)
        self._renderer = renderer
        self._image_label = image_label
        self._frames = list(frames)
        self._delays = list(delays)
        self._theme = theme
        self._start = max(0, int(start))
        self._index = self._start if self._frames else 0
        self._max_loops = max_loops
        self._loops = 0
        self._timer = None
        self._stopped = not self._frames
        self._on_frame = on_frame
        self._photos = []
        if self._frames:
            self._show(self._index)
            self._schedule_next()

    # ---------------------------------------------------------------- #
    # 播放
    # ---------------------------------------------------------------- #
    @property
    def frame_count(self) -> int:
        """实际加载的帧数；失败 / 无 Pillow ⇒ `0`（冻结哨兵）。"""
        return len(self._frames)

    def _delay_for(self, idx: int) -> int:
        """第 `idx` 帧的**有效**延迟（毫秒）：显式 `frame_delay` > 文件 `duration` > 最小值。"""
        want = self._delays[idx] if idx < len(self._delays) and self._delays[idx] else None
        if want is None:
            want = self._theme.media_min_frame_delay_ms
        return max(int(self._theme.media_min_frame_delay_ms), int(want))

    def _show(self, idx: int) -> None:
        photo = _PIL_ImageTk.PhotoImage(self._frames[idx])
        self._photos = [photo]                      # 只保当前帧（避免无限增长）
        self._image_label.configure(image=photo)
        self._image_label._ck10_photo = photo
        if self._on_frame is not None:
            self._on_frame(idx, len(self._frames))

    def _schedule_next(self) -> None:
        if self._stopped or len(self._frames) < 2:
            return
        self._timer = self._renderer.schedule(self._delay_for(self._index), self._advance)

    def _advance(self) -> None:
        self._timer = None
        if self._stopped or not self.exists():
            return
        nxt = self._index + 1
        if nxt >= len(self._frames):
            self._loops += 1
            if self._max_loops is not None and self._loops >= int(self._max_loops):
                self._index = 0
                self._show(0)
                self._stopped = True            # 达到轮数上限 ⇒ 停止（契约：不再回调）
                return
            nxt = 0
        self._index = nxt
        self._show(nxt)
        self._schedule_next()

    # ---------------------------------------------------------------- #
    # AnimationHandle / Handle 面
    # ---------------------------------------------------------------- #
    def stop(self) -> None:
        """停止播放但**保留控件**（幂等）；取消未触发的定时器，其后不再回调。"""
        self._stopped = True
        if self._timer is not None:
            try:
                self._timer.cancel()
            except Exception:                   # noqa: BLE001 —— 幂等
                pass
            self._timer = None

    def destroy(self) -> None:
        """停止播放并销毁容器（幂等）。"""
        self.stop()
        TkHandle.destroy(self)

    def layout(self, layout) -> None:
        apply_tk_layout(self._container if hasattr(self, "_container") else self._widget, layout)

    def set_enabled(self, enabled: bool) -> None:
        raise NotSupportedError("animation 不支持 set_enabled")


class TkLabelHandle(LabelHandle, TkHandle):
    """文本标签句柄（(a)）；`native` = `tk.Label`。

    新手友好：`h.set_text("你好")` 即改文案，无需记 `configure(text=…)`。
    """

    def set_text(self, text: str) -> None:
        self._ensure_alive()
        self._widget.config(text="" if text is None else str(text))
