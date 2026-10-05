"""handles.py —— Qt 后端的中立句柄与值。

与 `ck1_0/renderer/tk/handles.py` **结构镜像**，语义差异只在"如何判定底层对象是否仍存在"。

契约要点（详见 `ck1_0/renderer/base.py` 的 `Handle` / `Value` / `ToggleHandle`）
    * `exists()` 与 `Renderer.is_alive()` 的**异常策略相反是有意的**：
      `exists()` 探测失败 ⇒ 返回 `False`（不承载）；`is_alive()` 必须上抛。
    * `ToggleHandle` 的回调纪律（两后端必须一致）：
      同值 ⇒ 不触发、不重绘；变更时**先 `on_change` 后 `command`**；
      每次可见变更 `command` **恰好一次**（点击路径内部必须走 `value.set()`）。
    *：`set_enabled(False)` **只阻止用户交互**，程序化 API 仍可用，**不得改变值**。
    *：`text=''` 仍**创建**标签（内容为空串），与首版的 `if text:` 有意不同。

`exists()` 的判据（本批选择，含理由）
    **首选 `shiboken6.isValid(widget)`** —— 它直接问"底层 C++ 对象是否还活着"，
    与 base 对 `exists()` 的实现中立定义（"底层对象当前是否仍然存在/可用"）**逐字对应**，
   且**不看 parent**（明文禁止用"原 parent 仍存活"推断）。
    实测本机 PySide6 **6.11.2** 的 `shiboken6` 暴露 `isValid`，故这是实际生效的路径。
    `shiboken6` 不可导入时退回"调用一次无害的 Qt 方法，抛异常即视为不存在"。
"""

from __future__ import annotations

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

try:                                    # PySide6 必然带 shiboken6；缺失时走回退判据
    import shiboken6
except ImportError:                     # pragma: no cover
    shiboken6 = None

from PySide6 import QtCore
from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (QApplication, QGridLayout, QMainWindow, QToolTip, QVBoxLayout,
                               QWidget)

__all__ = ["QtHandle", "QtTimerHandle", "QtToggleHandle", "QtValue", "QtProgressHandle",
           "apply_qt_layout", "QtTextValue", "QtInputHandle", "QtTextAreaHandle",
           "QtCheckValue", "QtCheckboxHandle", "QtIndexValue", "QtRadioGroupHandle",
           "QtScrollableHandle", "QtBarsCanvas", "QtLabelsHolder", "QtBarsHandle", "QtTextVarValue",
           "QtComboHandle", "QtFloatValue", "QtSpinboxHandle", "QtNumValue", "QtSliderHandle", "QtListHandle", "QtStatusBarHandle", "QtNotebookHandle", "QtFormHandle", "QtTableHandle", "QtTooltipHandle", "QtMediaHandle", "QtAnimationHandle",
           "QtLabelHandle"]


_STICKY_MAP = {"n": Qt.AlignmentFlag.AlignTop, "s": Qt.AlignmentFlag.AlignBottom,
               "e": Qt.AlignmentFlag.AlignRight, "w": Qt.AlignmentFlag.AlignLeft}


def _qt_layout_host(widget):
    """返回**可承载布局**的宿主控件：`QMainWindow` ⇒ 其 `centralWidget()`（必要时创建）。

    QMainWindow 不允许直接 `setLayout`（Qt 会拒绝/告警），故统一改用其 central widget。
    """
    if isinstance(widget, QMainWindow):
        host = widget.centralWidget()
        if host is None:
            host = QWidget()
            widget.setCentralWidget(host)
        return host
    return widget


def _ensure_flow_layout(widget):
    """确保宿主是**顺序流**容器（缺失则建垂直布局）并返回其布局。"""
    host = _qt_layout_host(widget)
    lay = host.layout()
    if lay is None:
        lay = QVBoxLayout(host)
    return lay


def _ensure_grid_layout(widget):
    """确保宿主是**网格**容器并返回其 `QGridLayout`。

   已有**非网格**布局 ⇒ `NotSupportedError`（容器本应支持网格却无法设置 ⇒ 不得静默忽略）。
    """
    host = _qt_layout_host(widget)
    lay = host.layout()
    if lay is None:
        lay = QGridLayout(host)
    elif not isinstance(lay, QGridLayout):
        raise NotSupportedError(
            "目标容器已有非网格布局（%s），无法作为网格容器（不得静默）"
            % type(lay).__name__)
    return lay


def apply_qt_layout(widget, layout) -> None:
    """把 `Layout` 意图应用到 Qt 控件（**含 `into`**）。

    （已签）：Qt 的 `layout().addWidget()` **必然** `setParent` ——
    主体 `parent()` **变为** `into` 的宿主、原 parent 的 `children()` 变空、
    原 parent 销毁后主体**仍可用**；反之 **`into` 销毁 ⇒ 主体连带销毁**（**危险点**：
    适配层不得隐瞒，调用方不得假定句柄仍可用，只能用 `Handle.exists()` 探测）。

   三处显式异常：`layout.into` 非 `Handle` ⇒ `InvalidParentError`；
    `layout.into` 已失效 ⇒ `RendererClosedError`（`Handle.native` 负责）；
    无 parent 且无 `into`、或网格目标已有非网格布局、或 `sticky` 含未支持字符 ⇒ `NotSupportedError`。
    """
    into = getattr(layout, "into", None)
    if into is not None and not isinstance(into, Handle):
        raise InvalidParentError(
            "layout.into 必须是 Handle 或 None，收到 %r" % (into,)
        )
    target = _qt_layout_host(into.native) if into is not None else widget.parentWidget()
    if target is None:
        raise NotSupportedError(
            "该控件没有 parent，且未给出 layout.into ⇒ 无法接管几何（不得静默）")
    if layout.kind == "pack":
        _ensure_flow_layout(target).addWidget(widget)
    elif layout.kind == "grid":
        grid = _ensure_grid_layout(target)
        grid.addWidget(widget, layout.row, layout.column,
                       layout.rowspan, layout.columnspan)
        flags, unknown = [], []
        for ch in (layout.sticky or ""):
            if ch in _STICKY_MAP:
                flags.append(_STICKY_MAP[ch])
            elif ch not in " ":
                unknown.append(ch)
        if unknown:
            raise NotSupportedError("grid.sticky 含未支持字符：%r" % (unknown,))
        if flags:
            align = flags[0]
            for f in flags[1:]:
                align |= f
            grid.setAlignment(widget, align)
    else:
        raise NotSupportedError("未知布局 kind: %r" % (layout.kind,))


def _flush_deferred_deletes() -> None:
    """排空 `DeferredDelete` 事件。

    `deleteLater()` 只**投递**事件；无头环境下没有 `app.exec()`，必须手动排空，
    否则 C++ 对象不会真正析构、`shiboken6.isValid()` 仍为真。
   与 `开发期探针 qt_evidence:86` 用的是同一模式
    （`QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)`）。
    """
    QtCore.QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _widget_alive(widget) -> bool:
    """底层 QWidget 是否仍然存在（**不抛**；探测失败即视为不存在）。

    私有助手，用于 `destroy()` 内部的"中立测活"判别 —— 不是公开 API。
    """
    if widget is None:
        return False
    try:
        if shiboken6 is not None:
            return bool(shiboken6.isValid(widget))
        widget.objectName()             # 已删除的 C++ 对象会抛 RuntimeError
        return True
    except Exception:                   # noqa: BLE001 —— 探测失败即视为不存在
        return False


class QtHandle(Handle):
    """包装单个 QWidget 的句柄。

    私有属性:
        _widget: 被包装的 QWidget（构造后不再更换）。
    """

    def __init__(self, widget):
        self._widget = widget

    # ------------------------------------------------------------------ #
    # Handle 抽象面
    # ------------------------------------------------------------------ #
    @property
    def native(self) -> object:
        """**逃生口**：返回被包装的 QWidget。句柄已失效时抛 `RendererClosedError`。"""
        self._ensure_alive()
        return self._widget

    def _ensure_alive(self) -> None:
        """私有：句柄已失效时抛 `RendererClosedError`（供内部与 `QtValue` 复用）。"""
        if not self.exists():
            raise RendererClosedError(
                "%s 已失效（底层 QWidget 已被销毁）" % type(self).__name__
            )

    def exists(self) -> bool:
        """底层 QWidget 当前是否仍存在（`shiboken6.isValid`）。

        **只问控件自身**，不问 parent 是否存活。查询失败 ⇒ `False`
        （`Handle.exists` 的异常策略，与 `Renderer.is_alive()` 相反）。
        """
        return _widget_alive(self._widget)

    def destroy(self) -> None:
        """销毁控件及其子树；**幂等**，已销毁时静默返回。

        `deleteLater()` + 排空 `DeferredDelete`，因此返回时 C++ 对象**已**析构，
        `exists()` 立刻变 `False`（不依赖后续事件循环）。
        """
        if not self.exists():
            return
        try:
            self._widget.deleteLater()
            _flush_deferred_deletes()
        except Exception:               # noqa: BLE001 —— 幂等语义要求静默
            pass

    def layout(self, layout) -> None:
        """（重新）应用布局（真实实现）。

        `layout.into is None` ⇒ 在本控件**当前所属**容器内重排自身；
        `layout.into` 是 `Handle` ⇒ 请求该容器接管几何（`into.layout().addWidget(self)`）。

        **危险点（已签）**：Qt 的 `addWidget()` **必然** `setParent` ⇒
        （a）本控件 `parent()` 变为 `into` 的宿主、原 parent 不再拥有它、原 parent 销毁后
        本控件**仍可用**；（b）**`into` 被 `destroy()` 时本控件会被连带销毁** ——
        调用方不得假定句柄仍可用，必须用 `Handle.exists()` 探测。
        异常见模块级 `apply_qt_layout`；本句柄已失效时抛 `RendererClosedError`。
        """
        self._ensure_alive()
        apply_qt_layout(self._widget, layout)

    def set_enabled(self, enabled: bool) -> None:
        """启用/禁用**用户交互**；**不改变控件的值**。"""
        self._ensure_alive()
        self._widget.setEnabled(bool(enabled))


class QtValue(Value):
    """包装 Qt 侧状态的可观察值（本批为 `bool`）。

    值本身存在本对象里，不依赖 `QCheckBox.isChecked()`；视觉同步与组件级回调经
    `_handle` 完成（与 `TkValue` 同构）。
    """

    def __init__(self, handle: QtToggleHandle, initial: bool):
        self._handle = handle
        self._value = bool(initial)
        self._callbacks = []

    def get(self):
        """读取当前值；所属控件已销毁时抛 `RendererClosedError`。"""
        self._handle._ensure_alive()
        return self._value

    def set(self, value) -> None:
        """写入新值。

       纪律（与 Tk 后端**必须一致**）：
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


class QtToggleHandle(ToggleHandle):
    """复合开关句柄：容器 `QFrame` + 状态 `QCheckBox` + 文本 `QLabel`。

    私有属性:
        _frame/_checkbox/_label: 三个原生控件；
        _value: `QtValue`；
        _command: 组件级回调（收 `bool`）；
        _enabled:  的交互开关（为假时点击无效，但不影响程序化 API）。
    """

    def __init__(self, frame, checkbox, label, default, command,
                 on_color, off_color, outline, track_w, track_h,
                 border_width=1, radius=3):
        self._frame = frame
        self._checkbox = checkbox
        self._label = label
        self._command = command
        self._on_color = on_color
        self._off_color = off_color
        self._outline = outline
        self._track_w = int(track_w)
        self._track_h = int(track_h)
        # （批准 (i)）：QSS 的边框/圆角改为 **token 驱动**（默认值仅为兜底）
        self._border_width = int(border_width)
        self._radius = int(radius)
        self._enabled = True
        # 与 TkToggleHandle 同构：`QtValue` 需要反向引用句柄，故在句柄内构造
        self._value = QtValue(self, default)

    # ------------------------------------------------------------------ #
    # 私有：视觉与回调
    # ------------------------------------------------------------------ #
    def _redraw(self) -> None:
        """按当前值重绘：**同步 `QCheckBox` 勾选态** + 把**当前**轨道色写进 QSS。

        为什么必须回写 `setChecked`：本对象持有 Python 侧的值，`QCheckBox` 另持一份
        控件侧状态，而**可见视觉由后者驱动**。`ToggleHandle` 契约要求"`value.set(v)`
        必须更新控件视觉 —— **写入值与显示状态不得脱节**"；只改 QSS 而不同步勾选态，
        会让"值 = True 但控件未勾选"或反之，并使后续点击算出**错误的翻转方向**
        （实测：`value.set(False)` 后控件仍为 checked ⇒ 下次点击产生 `clicked(False)`
        ⇒ 与当前值同值 ⇒ `command` 不触发）。

        `setChecked()` 只发 `toggled`（**不发** `clicked`），而点击路径只连 `clicked`，
        故此处不会重入、不会让 `command` 触发第二次；值未变时 `setChecked` 亦为 no-op。
        """
        self._checkbox.setChecked(self._value.get())
        track = self._on_color if self._value.get() else self._off_color
        # 尺寸来自 `width`/`height` 参数（`None` ⇒ Theme `toggle_default_width/height`）。
        # **单位是像素**，与首版一致：首版把这两个值交给
        # `tk.Canvas(frame, width=width, height=height)`（`advanced_widgets.py:770`），
        # Canvas 宽高即像素 —— 故 Qt 直接按 px 应用**不需要任何单位换算**。
        # 边框/圆角**已 token 化**（批准 (i)； ③）：
        # 取自 `Theme.toggle_border_width` / `Theme.toggle_radius`，不再写死字面量。
        self._checkbox.setStyleSheet(
            "QCheckBox::indicator { border: %dpx solid %s; border-radius: %dpx;"
            " width: %dpx; height: %dpx; background-color: %s; }"
            "QCheckBox::indicator:checked { background-color: %s; }"
            % (self._border_width, self._outline, self._radius,
               self._track_w, self._track_h, track, self._on_color)
        )

    def _fire_command(self, value: bool) -> None:
        """触发组件级回调（`command` 恰好一次的**唯一**出口）。"""
        if self._command is not None:
            self._command(value)

    def _on_click(self, checked: bool) -> None:
        """用户点击：**走 `value.set()`**，因此回调顺序与去重由 `QtValue` 保证。

        `_enabled` 为假（禁用）时直接返回 —— 只阻止用户交互。
        Qt 在发 `clicked` **之前**已自行翻转 `isChecked()`，故此处用信号携带的
        `checked` 值，**不要**再取反。
        """
        if not self._enabled:
            return
        if not self.exists():
            return
        self._value.set(bool(checked))

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
        `label.deleteLater()`），本实现会补建新标签。base 只要求"更新文本、空串合法、
        标签仍存在、句柄失效抛 `RendererClosedError`"；**Qt 与 Tk 在本批各自实现，
        彼此无需复制此行为**（守卫查实际存在性，非 `is None`）。
        """
        self._ensure_alive()
        if not self._label_alive():
            self._label = self._make_label(text)
        self._label.setText(text)

    def _label_alive(self) -> bool:
        """标签当前是否仍存在（`_ensure_alive()` 已先行通过）。"""
        return _widget_alive(self._label)

    def _make_label(self, text: str):
        """（补建路径）重建标签控件并并入布局。"""
        from PySide6.QtWidgets import QLabel

        label = QLabel(text, self._frame)
        self._frame.layout().addWidget(label)
        return label

    @property
    def native(self) -> object:
        """**逃生口**：返回最外层容器 `QFrame`（checkbox/label 见各自私有属性）。"""
        self._ensure_alive()
        return self._frame

    def exists(self) -> bool:
        """最外层容器是否仍存在；查询失败 ⇒ `False`。"""
        return _widget_alive(self._frame)

    def destroy(self) -> None:
        """销毁容器及其子树（checkbox/label 随之销毁）；**幂等**。"""
        if not self.exists():
            return
        try:
            self._frame.deleteLater()
            _flush_deferred_deletes()
        except Exception:               # noqa: BLE001 —— 幂等语义要求静默
            pass

    def set_enabled(self, enabled: bool) -> None:
        """`False` ⇒ **只阻止用户交互**；程序化 `value.set()` 仍可用；**不改变值**。

        用 `QCheckBox.setEnabled(False)`：Qt 自身会忽略禁用控件的点击，本实现另有
        `_enabled` 守卫双保险。**不**触碰 `value`。
        """
        self._ensure_alive()
        self._enabled = bool(enabled)
        self._checkbox.setEnabled(self._enabled)

    def _ensure_alive(self) -> None:
        """私有：句柄已失效时抛 `RendererClosedError`。"""
        if not self.exists():
            raise RendererClosedError(
                "%s 已失效（底层 QFrame 已被销毁）" % type(self).__name__
            )

    def layout(self, layout) -> None:
        """（重新）应用布局；语义同 `QtHandle.layout`（含 危险点）。"""
        self._ensure_alive()
        apply_qt_layout(self._frame, layout)


class QtTimerHandle(TimerHandle):
    """`QtRenderer.schedule()` 返回的定时器句柄（中立化落点）。

    包装一个 `QTimer`（`setSingleShot(True)`，父对象 = 本 Renderer 的 `QMainWindow`
    ⇒ `destroy()` 时随之析构）。**不继承 `Handle`**（同 Tk 侧理由）。

    私有属性:
        _timer: 被包装的 `QTimer`（`native` 逃生口）。
    """

    def __init__(self, timer):
        self._timer = timer

    @property
    def native(self) -> object:
        """**逃生口**：被包装的 `QTimer`。"""
        return self._timer

    def cancel(self) -> None:
        """取消定时器，**幂等**（契约"异常: 无"）。"""
        try:
            self._timer.stop()
        except Exception:                       # noqa: BLE001 —— 契约：cancel 不抛
            pass

    def is_active(self) -> bool:
        """定时器是否**仍处于已排定（尚未触发/取消）状态**（`QTimer.isActive()`）。

        已触发的单次定时器 `isActive()` 自动变 `False`；C++ 对象已被删除时查询抛
       异常 ⇒ `False`（base 明文允许：本方法不承载该纪律）。
        """
        try:
            return bool(self._timer.isActive()) and _widget_alive(self._timer)
        except Exception:                       # noqa: BLE001
            return False


class QtProgressHandle(ProgressHandle, QtHandle):
    """`QtRenderer.progress()` 返回的进度条句柄。

   包装 `QProgressBar`。`update(value)` 复刻首版 `create_progress_bar` 的夹取语义：
    按 `value / max_value` 求比例并夹到 `[0, 1]`；`max_value <= 0` 时 `value > 0` 视为满。
    内部把比例量化到 `0..1000`（`QProgressBar` 只吃整数），**比例精度 0.1%**，远高于像素分辨率。
    """

    def __init__(self, bar, max_value):
        # 复用 QtHandle 的 exists/destroy/layout/set_enabled（作用于 QProgressBar 自身）
        QtHandle.__init__(self, bar)
        self._bar = bar
        self._max = max_value

    def update(self, value: float) -> None:
        if self._max <= 0:
            ratio = 1.0 if value > 0 else 0.0
        else:
            ratio = max(0.0, min(1.0, float(value) / float(self._max)))
        self._bar.setRange(0, 1000)
        self._bar.setValue(int(round(ratio * 1000)))


class QtTextValue(Value):
    """文本型 neutral `Value`（Qt 侧；`input` / `text_area` 的 `.value`）。

    Qt 用**原生** placeholder（`QLineEdit.placeholderText()` / `QTextEdit` 的占位由
    `placeholderText` 属性提供），控件内容天然为空 ⇒ `get()` 与 Tk 侧的中性化结果一致。
    用户输入（`textChanged`）与程序化 `set()` 都触发 `on_change`（各恰好一次；程序化写入用
    `_suppress` 抑制信号回调，避免重复触发）。
    """

    def __init__(self, handle, placeholder, multi=False):
        self._handle = handle
        self._widget = handle._widget
        self._placeholder = placeholder
        self._multi = multi
        self._callbacks = []
        self._suppress = False
        self._widget.textChanged.connect(self._on_text_changed)

    def _on_text_changed(self):
        if not self._suppress:
            self._fire()

    def _fire(self):
        for cb in list(self._callbacks):
            cb(self.get())

    def get(self):
        """读取当前值；已销毁 ⇒ `RendererClosedError`。"""
        self._handle._ensure_alive()
        return self._widget.toPlainText() if self._multi else self._widget.text()

    def set(self, value) -> None:
        text = "" if value is None else str(value)
        self._handle._ensure_alive()
        self._suppress = True
        try:
            if self._multi:
                self._widget.setPlainText(text)
            else:
                self._widget.setText(text)
        finally:
            self._suppress = False
        self._fire()

    def on_change(self, callback) -> None:
        self._callbacks.append(callback)


class QtInputHandle(InputHandle, QtHandle):
    """单行输入框句柄。"""

    def __init__(self, widget):
        QtHandle.__init__(self, widget)
        self._placeholder = widget.placeholderText()      # 与 Tk 侧同名属性，供断言/文档一致
        self._value = QtTextValue(self, self._placeholder, multi=False)

    @property
    def value(self):
        return self._value

    def set_placeholder(self, text: str) -> None:
        self._ensure_alive()
        self._widget.setPlaceholderText(text)
        self._value._placeholder = text


class QtTextAreaHandle(TextAreaHandle, QtHandle):
    """多行文本框句柄。"""

    def __init__(self, widget):
        QtHandle.__init__(self, widget)
        self._placeholder = widget.placeholderText()
        self._value = QtTextValue(self, self._placeholder, multi=True)

    @property
    def value(self):
        return self._value

    def set_placeholder(self, text: str) -> None:
        self._ensure_alive()
        self._widget.setPlaceholderText(text)
        self._value._placeholder = text


class QtCheckValue(Value):
    """`checkbox` 的 neutral `Value`（bool）。纪律同 Tk 侧（同值不触发）。"""

    def __init__(self, handle, initial):
        self._handle = handle
        self._value = bool(initial)
        self._callbacks = []
        self._suppress = False

    def get(self):
        self._handle._ensure_alive()
        return self._value

    def set(self, value) -> None:
        self._handle._ensure_alive()
        resolved = bool(value)
        if resolved == self._value:
            return
        self._suppress = True
        try:
            self._value = resolved
            self._handle._sync_visual()
        finally:
            self._suppress = False
        for cb in list(self._callbacks):
            cb(resolved)
        self._handle._fire_command()

    def on_change(self, callback) -> None:
        self._callbacks.append(callback)


class QtCheckboxHandle(CheckboxHandle, QtHandle):
    """复选框句柄。"""

    def __init__(self, widget, default, command):
        QtHandle.__init__(self, widget)
        self._command = command
        self._value = QtCheckValue(self, default)

    @property
    def value(self):
        return self._value

    def _fire_command(self) -> None:
        if self._command is not None:
            self._command()

    def _sync_visual(self) -> None:
        self._widget.setChecked(bool(self._value._value))


class QtIndexValue(Value):
    """`radio_group` 的 neutral `Value`（选中**索引**，int）。"""

    def __init__(self, handle, initial):
        self._handle = handle
        self._value = int(initial)
        self._callbacks = []
        self._suppress = False

    def get(self):
        self._handle._ensure_alive()
        return self._value

    def set(self, value) -> None:
        self._handle._ensure_alive()
        resolved = int(value)
        if resolved == self._value:
            return
        self._suppress = True
        try:
            self._value = resolved
            self._handle._sync_visual()
        finally:
            self._suppress = False
        for cb in list(self._callbacks):
            cb(resolved)

    def on_change(self, callback) -> None:
        self._callbacks.append(callback)


class QtRadioGroupHandle(RadioGroupHandle, QtHandle):
    """单选组句柄；`native` 为**容器 QFrame**。"""

    def __init__(self, frame, group, buttons, options, default):
        QtHandle.__init__(self, frame)
        self._group = group
        self._buttons = list(buttons)
        self._options = list(options)
        self._value = QtIndexValue(self, default)

    @property
    def value(self):
        return self._value

    @property
    def options(self):
        return list(self._options)

    def _sync_visual(self) -> None:
        btn = self._buttons[self._value._value]
        btn.setChecked(True)

    def set_enabled(self, enabled: bool) -> None:
        self._ensure_alive()
        for b in self._buttons:
            b.setEnabled(bool(enabled))


class QtScrollableHandle(ScrollableHandle, QtHandle):
    """可滚动容器句柄；`native` = 外层 `QScrollArea`，`.content` = 内部内容控件。"""

    def __init__(self, area, content):
        QtHandle.__init__(self, area)
        self._content = QtHandle(content)

    @property
    def content(self):
        return self._content


class QtBarsCanvas(QWidget):
    """`bars` 的 Qt 自绘画布（绘制归 backend）。

   实现要点（对应首版 `scrollable_bars` 的视觉参数）：条带条纹（`bars_stripe` /
    `bars_stripe_light`）、柱体（`bar_colors` 或按索引渐变）、白描边（`bars_outline`）、
    标签带（`bars_label_band`）+ 底部预留（`bars_height_reserve`）、标签可旋转（`label_rotation`）、
    字号随柱宽在 `bars_font_min..bars_font_max` 间取值。
    `rects` 为实际柱体矩形列表（断言用机器证据）。
    """

    def __init__(self, parent, data, opts):
        QWidget.__init__(self, parent)
        self._data = list(data)
        self._o = opts
        self.rects = []

    def paintEvent(self, _event):                              # noqa: N802 (Qt 命名)
        from PySide6.QtGui import QColor, QPainter, QPen
        from PySide6.QtCore import Qt as _Qt
        o = self._o
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(o["background"]))
        n = len(self._data)
        top = o["padding"]
        bottom = self.height() - o["label_band"] - o["height_reserve"]
        avail = max(1, self.width() - 2 * o["padding"])
        step = max(o["min_bar_width"], (avail - (n - 1) * o["spacing"]) // max(1, n))
        mx = max(self._data) or 1
        if o["stripes"]:
            stripe_h = 8
            y = top
            idx = 0
            while y < bottom:
                p.fillRect(0, int(y), self.width(), stripe_h,
                           QColor(o["stripe"] if idx % 2 == 0 else o["stripe_light"]))
                y += stripe_h
                idx += 1
        p.setPen(QPen(QColor(o["outline"])))
        p.setPen(QPen(QColor(o["text_color"])))
        self.rects = []
        for i, v in enumerate(self._data):
            h = int((bottom - top) * (float(v) / float(mx)))
            x = o["padding"] + i * (step + o["spacing"])
            rect = (x, bottom - h, step, h)
            self.rects.append(rect)
            p.fillRect(x, bottom - h, step, h, QColor(o["colors"][i % len(o["colors"])]))
            p.drawRect(x, bottom - h, step, h)
            p.save()
            p.translate(x + step / 2.0, bottom + 4)
            p.rotate(o["label_rotation"])
            f = p.font()
            f.setPointSize(max(o["font_min"], min(o["font_max"], step // 4 or o["font_min"])))
            p.setFont(f)
            p.drawText(0, 0, str(v))
            p.restore()
        p.end()
class QtLabelsHolder(QtScrollableHandle):
    """`labels` 句柄：外层是**垂直滚动容器**（`QScrollArea`）。

    `native` = 外层 `QScrollArea`（**可 `.layout(...)`**，与首版返回外层容器一致），
    `.content` = 内容 `QWidget`（每项一个 `QLabel` 排在它的 `QVBoxLayout` 里）；`drawn` == 条目数。
    """

    def __init__(self, area, content, drawn):
        QtScrollableHandle.__init__(self, area, content)
        self.drawn = drawn


class QtBarsHandle(QtScrollableHandle):
    """`bars` 句柄：外层是**水平滚动容器**（`QScrollArea`）。

    `native` = 外层 `QScrollArea`（**可 `.layout(...)`**）；`.content` = 内容 `QWidget`；
    `art` = **自绘画布**（`QtBarsCanvas`；绘制证据读它的 `rects`）；`drawn` == 柱数。
    """

    def __init__(self, area, content, art, drawn):
        QtScrollableHandle.__init__(self, area, content)
        self.art = art
        self.drawn = drawn


class QtTextVarValue(Value):
    """字符串型 neutral `Value`（`combo`；中性规则见 Tk 侧同名类）。"""

    def __init__(self, handle, initial):
        self._handle = handle
        self._value = "" if initial is None else str(initial)
        self._callbacks = []
        self._suppress = False

    def get(self):
        self._handle._ensure_alive()
        return self._value

    def set(self, value) -> None:
        self._handle._ensure_alive()
        new = "" if value is None else str(value)
        if new == self._value:
            return
        self._suppress = True
        try:
            self._value = new
            self._handle._sync_visual()
        finally:
            self._suppress = False
        for cb in list(self._callbacks):
            cb(new)

    def on_change(self, callback) -> None:
        self._callbacks.append(callback)


class QtComboHandle(ComboHandle, QtHandle):
    """下拉框句柄；`native` = `QComboBox`（`editable=False` ⇒ 非可编辑）。"""

    def __init__(self, widget, options, default, on_select):
        QtHandle.__init__(self, widget)
        self._options = list(options)
        self._on_select = on_select
        self._value = QtTextVarValue(self, default if default is not None else
                                     (options[0] if options else ""))

    @property
    def value(self):
        return self._value

    def _sync_visual(self) -> None:
        self._widget.setCurrentText(self._value._value)

    def _fire_select(self, text) -> None:
        self._value._value = text or ""
        if self._on_select is not None:
            self._on_select(self._value._value)


class QtFloatValue(Value):
    """浮点型 neutral `Value`（`spinbox`；`set()` 夹到 `[lo, hi]`）。"""

    def __init__(self, handle, initial, lo, hi):
        self._handle = handle
        self._lo = float(lo)
        self._hi = float(hi)
        self._value = min(max(float(initial), self._lo), self._hi)
        self._callbacks = []
        self._suppress = False

    def get(self):
        self._handle._ensure_alive()
        return self._value

    def set(self, value) -> None:
        self._handle._ensure_alive()
        new = min(max(float(value), self._lo), self._hi)
        if new == self._value:
            return
        self._suppress = True
        try:
            self._value = new
            self._handle._sync_visual()
        finally:
            self._suppress = False
        for cb in list(self._callbacks):
            cb(new)

    def on_change(self, callback) -> None:
        self._callbacks.append(callback)


class QtSpinboxHandle(SpinboxHandle, QtHandle):
    """数值微调框句柄；`native` = `QDoubleSpinBox`。"""

    def __init__(self, widget, default, lo, hi, command):
        QtHandle.__init__(self, widget)
        self._command = command
        self._value = QtFloatValue(self, default, lo, hi)

    @property
    def value(self):
        return self._value

    def _sync_visual(self) -> None:
        self._widget.setValue(self._value._value)

    def _fire_command(self) -> None:
        if self._command is not None:
            self._command(self._value._value)


class QtNumValue(Value):
    """数值型 neutral `Value`（`slider`）；夹取 + 按 `resolution` 吸附。"""

    def __init__(self, handle, initial, lo, hi, resolution):
        self._handle = handle
        self._lo, self._hi, self._res = float(lo), float(hi), float(resolution) or 1.0
        self._value = self._snap(initial)
        self._callbacks = []
        self._suppress = False

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
        self._suppress = True
        try:
            self._value = new
            self._handle._sync_visual()
        finally:
            self._suppress = False
        for cb in list(self._callbacks):
            cb(new)

    def on_change(self, callback) -> None:
        self._callbacks.append(callback)


class QtSliderHandle(SliderHandle, QtHandle):
    """滑块句柄；`native` = `QSlider`（整数刻度按 `resolution` 缩放映射）。

    **复合控件**：真实结构是「外层 `QFrame`（标签 + 滑轨 + 数值）」，而 `native` 是其中的
    `QSlider`（契约冻结，不改）⇒ 句柄另外持有**外层容器**，由 `outer` 公开。
    """

    def __init__(self, widget, outer, value_label, default, lo, hi, resolution, on_change):
        QtHandle.__init__(self, widget)
        self._outer_handle = QtHandle(outer)
        self._value_label = value_label
        self._on_change = on_change
        self._res = float(resolution) or 1.0
        self._value = QtNumValue(self, lo if default is None else default, lo, hi, resolution)

    @property
    def outer(self):
        """**入列单位**：外层 `QFrame`（`native` 是它里面的 `QSlider`）。"""
        return self._outer_handle

    @property
    def value(self):
        return self._value

    def _sync_visual(self) -> None:
        self._widget.setValue(int(round(self._value._value / self._res)))
        if self._value_label is not None:
            self._value_label.setText("%g" % self._value._value)

    def _fire_change(self) -> None:
        if self._on_change is not None:
            self._on_change(self._value._value)


class QtListHandle(ListHandle, QtHandle):
    """可搜索列表句柄。

    `Up`/`Down` 由 **`QListWidget` 原生**提供（Qt 自己处理键盘导航），`Enter`
    （`itemActivated`）由 backend 接线；base 只承诺 `on_select` + `set_items`。
    """

    def __init__(self, frame, list_widget, entry, items, on_select, placeholder=""):
        QtHandle.__init__(self, frame)
        self._list = list_widget
        self._entry = entry
        self._placeholder = placeholder
        self._all = list(items)
        self._on_select = on_select
        self._value = QtTextVarValue(self, None)
        self.nav_source = "QListWidget-native"

    @property
    def native(self):
        self._ensure_alive()
        return self._list

    @property
    def value(self):
        return self._value

    @property
    def selection(self):
        item = self._list.currentItem()
        return item.text() if item is not None else None

    def set_items(self, items) -> None:
        self._ensure_alive()
        self._all = list(items)
        self._apply_filter()

    def _sync_visual(self) -> None:
        """把 neutral 过滤词写回过滤框并**重新过滤**（`Value.set()` 的落地；与 Tk 侧对称）。

        **为什么必须有它**（实测发现）：`Value.set` 是 base 的**抽象公共 API**，而
        `QtTextVarValue.set` 会回调 `self._handle._sync_visual()`；本类原先没有该方法 ⇒
        `list.value.set('x')` 直接抛 `AttributeError`（**两个 backend 同错**）。
       首版的对应写法 `search_var.set('x')` 是**能用**的（StringVar + trace 重新过滤）。
        语义与 `get()` / `_filtered()` **对称**：空串 ⇒ 恢复占位符（占位符不算过滤词 ⇒ 显示全部）。
        """
        text = "" if self._value._value is None else str(self._value._value)
        self._entry.setText(text if text else self._placeholder)
        self._apply_filter()

    def _filtered(self):
        raw = self._entry.text()
        kw = "" if raw == self._placeholder else raw.strip().lower()
        return [x for x in self._all if kw in str(x).lower()] if kw else list(self._all)

    def _apply_filter(self) -> None:
        self._list.clear()
        for x in self._filtered():
            self._list.addItem(x)

    def _select_current(self) -> None:
        item = self.selection
        if item is None:
            return
        self._value._value = item
        if self._on_select is not None:
            self._on_select(item)


class QtStatusBarHandle(StatusBarHandle, QtHandle):
    """状态栏句柄；`native` = `QLabel`；`set_status(text)` 即 `setText`。"""

    def __init__(self, widget):
        QtHandle.__init__(self, widget)

    def set_status(self, text: str) -> None:
        self._ensure_alive()
        self._widget.setText("" if text is None else str(text))


class QtNotebookHandle(NotebookHandle, QtHandle):
    """页签容器句柄（第 1 个 commit）；`native` = `QTabWidget`。"""

    def __init__(self, widget, titles):
        QtHandle.__init__(self, widget)
        self._titles = list(titles)

    @property
    def tabs(self):
        return list(self._titles)

    def select(self, title: str) -> None:
        self._ensure_alive()
        if title not in self._titles:
            raise InvalidParentError("未登记的页签标题：%r" % (title,))
        self._widget.setCurrentIndex(self._titles.index(title))


class QtFormHandle(FormHandle, QtHandle):
    """表单句柄（commit 2）；`native` = 外层 `QWidget`。

    值与 Tk 侧同型（`str`/`bool`/`float`）；`set_values` 未知 key **打印提示并跳过**；
    `slider` 在 Qt 上以整数刻度承载（`float` 值经四舍五入映射，取值仍返回 `float`）。
    """

    def __init__(self, frame, kinds, widgets):
        QtHandle.__init__(self, frame)
        self._kinds = dict(kinds)
        self._widgets = dict(widgets)

    def get_values(self):
        self._ensure_alive()
        out = {}
        for key, kind in self._kinds.items():
            w = self._widgets[key]
            if kind == "check":
                out[key] = bool(w.isChecked())
            elif kind in ("spin", "slider"):
                out[key] = float(w.value())
            elif kind == "text":
                out[key] = w.toPlainText()
            elif kind == "combo":
                out[key] = str(w.currentText())
            else:
                out[key] = str(w.text())
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
                w.setChecked(bool(value))
            elif kind in ("spin", "slider"):
                w.setValue(int(round(float(value))))
            elif kind == "text":
                w.setPlainText("" if value is None else str(value))
            elif kind == "combo":
                w.setCurrentText("" if value is None else str(value))
            else:
                w.setText("" if value is None else str(value))


class QtTableHandle(TableHandle, QtHandle):
    """表格句柄；`native` = `QTableWidget`。

    `on_select` 的第二个实参是**行索引（`int`）** —— Qt 没有 Tk 那种 item id，
    故该实参**只对 backend 自己有意义**、对调用方**不透明**（不得跨后端解析）。
    """

    def __init__(self, table, headers):
        QtHandle.__init__(self, table)
        self._headers = list(headers)

    def set_rows(self, rows) -> None:
        from PySide6.QtWidgets import QTableWidgetItem
        self._ensure_alive()
        data = [tuple(r) for r in (rows or [])]
        self._widget.setRowCount(len(data))
        for i, row in enumerate(data):
            for j, val in enumerate(row):
                self._widget.setItem(i, j, QTableWidgetItem(str(val)))

    def get_rows(self):
        self._ensure_alive()
        out = []
        for i in range(self._widget.rowCount()):
            out.append(tuple(self._widget.item(i, j).text() if self._widget.item(i, j) else ""
                             for j in range(self._widget.columnCount())))
        return out

    @property
    def selection(self):
        self._ensure_alive()
        row = self._widget.currentRow()
        return row if row >= 0 else None


class _QtHoverFilter(QObject):
    """私有：把目标控件的 Enter/Leave 事件转给 `QtTooltipHandle`。

    `Handle` 不是 `QObject`，无法直接 `installEventFilter`，故用一个极薄的 `QObject`
    转发（父对象 = 目标控件，随之销毁）。
    """

    def __init__(self, handle):
        super().__init__(handle._target)
        self._handle = handle

    def eventFilter(self, obj, event):          # noqa: N802 —— Qt 命名
        try:
            kind = event.type()
            if kind == QEvent.Type.Enter:
                self._handle._on_enter()
            elif kind == QEvent.Type.Leave:
                self._handle._on_leave()
        except Exception:                        # noqa: BLE001 —— 事件过滤器不得抛
            pass
        return False


class QtTooltipHandle(TooltipHandle, QtHandle):
    """提示气泡句柄；`native` = **被挂载的目标控件**。

    存在性以 **target** 为准（同 Tk 侧理由：气泡是临时对象，显隐不应抖动 `exists()`）。

    实现：悬停 Enter/Leave 经 `_QtHoverFilter` 进入 `_on_enter`/`_on_leave`；
    延迟用 `QTimer.singleShot` 等价的单次 `QTimer`；显示/隐藏用**原生 `QToolTip`**
    （`QToolTip.showText` / `hideText`）；`show()` 不受 delay 影响、`hide()` 幂等。

    （预授权登记）**：Qt 的 `QToolTip` 呈现由 **QSS 驱动且固定**，
   无法逐项对齐首版的 `tooltip_background='lightyellow'` / `tooltip_relief='solid'` /
    `tooltip_borderwidth=1` / `tooltip_offset=(12,12)`。因此本侧**只消费** `tooltip_delay_ms`
    与文本；上述四项**不被 Qt 侧消费**（Tk 侧全消费），属**已知且已登记**的后端差异，
   目视结论留给。**本调用点不允许静默**：若需要逐像素一致，应由 C/G 段用
    `label` + `container` 自绘气泡替代 `QToolTip`（当前未采用）。

    `layout()` / `set_enabled()` 对气泡不适用 ⇒ `NotSupportedError`（不静默）。
    """

    def __init__(self, target, text, theme, delay_ms=None):
        QtHandle.__init__(self, target)
        self._target = target
        self._text = text
        self._theme = theme
        self._delay = theme.tooltip_delay_ms if delay_ms is None else int(delay_ms)
        self._timer = None
        self._filter = _QtHoverFilter(self)
        target.installEventFilter(self._filter)
        try:
            target._ck10_tooltip = self
        except Exception:                       # noqa: BLE001
            pass

    # ---------------------------------------------------------------- #
    # 悬停驱动
    # ---------------------------------------------------------------- #
    def _on_enter(self):
        if self._timer is not None:
            return
        timer = QtCore.QTimer(self._target)
        timer.setSingleShot(True)
        timer.timeout.connect(self._do_show)
        self._timer = timer
        timer.start(max(0, self._delay))

    def _on_leave(self):
        self._cancel_pending()
        self._do_hide()

    def _cancel_pending(self):
        if self._timer is not None:
            try:
                self._timer.stop()
            except Exception:                   # noqa: BLE001
                pass
            self._timer = None

    def _do_show(self):
        self._timer = None
        if not self.exists():
            return
        QToolTip.showText(QCursor.pos(), self._text, self._target)

    def _do_hide(self):
        QToolTip.hideText()

    # ---------------------------------------------------------------- #
    # TooltipHandle / Handle 面
    # ---------------------------------------------------------------- #
    def show(self) -> None:
        """立即显示（**不受** `delay_ms` 影响）。"""
        self._ensure_alive()
        self._do_show()

    def hide(self) -> None:
        """立即隐藏（幂等）；同时取消未到期的延迟。"""
        self._ensure_alive()
        self._cancel_pending()
        self._do_hide()

    def destroy(self) -> None:
        """销毁气泡并解除事件过滤器（幂等）；**不销毁 target**。"""
        self._cancel_pending()
        self._do_hide()
        try:
            self._target.removeEventFilter(self._filter)
            if getattr(self._target, "_ck10_tooltip", None) is self:
                del self._target._ck10_tooltip
        except Exception:                       # noqa: BLE001 —— 目标已销毁：幂等
            pass

    def layout(self, layout) -> None:
        raise NotSupportedError("tooltip 不参与布局（气泡位置由 QToolTip 决定，见）")

    def set_enabled(self, enabled: bool) -> None:
        raise NotSupportedError("tooltip 不支持 set_enabled")


class QtMediaHandle(MediaHandle, QtHandle):
    """静态图片 / 逐帧预览容器句柄；`native` = 外层 `QWidget`。

    结构**与 Tk 侧一致**：容器 + 图片 `QLabel` + 说明 `QLabel`（图片在上、文字在下）。
    图片对象存在 `container._ck10_image_label`（`QLabel.pixmap()`）与
    `container._ck10_photos`（逐帧预览的 `QPixmap` 列表，保持引用避免被回收）。
    """


class QtAnimationHandle(AnimationHandle, QtHandle):
    """动画句柄；`native` = 外层容器（`QWidget`）。

    与 Tk 侧**逐条同语义**：失败哨兵（`frame_count == 0`，`animation` 永不返回 `None`）；
    每帧延迟 = `frame_delay` 或文件 `duration`，**一律不低于** `media_min_frame_delay_ms`；
    `start` 起始帧；`max_loops=None` 无限；每帧 `on_frame(index, total)`；
    定时器经 `Renderer.schedule` 排定（`Renderer.destroy()` 会取消）。
    """

    def __init__(self, renderer, container, image_label, frames, delays, theme,
                 start=0, max_loops=None, on_frame=None):
        QtHandle.__init__(self, container)
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
        self._pixmaps = []
        if self._frames:
            self._show(self._index)
            self._schedule_next()

    @property
    def frame_count(self) -> int:
        """实际加载的帧数；失败 / 无 Pillow ⇒ `0`（冻结哨兵）。"""
        return len(self._frames)

    def _delay_for(self, idx: int) -> int:
        want = self._delays[idx] if idx < len(self._delays) and self._delays[idx] else None
        if want is None:
            want = self._theme.media_min_frame_delay_ms
        return max(int(self._theme.media_min_frame_delay_ms), int(want))

    def _show(self, idx: int) -> None:
        from .renderer import _qt_pixmap_from_image
        pix = _qt_pixmap_from_image(self._frames[idx])
        self._pixmaps = [pix]
        self._image_label.setPixmap(pix)
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
                self._stopped = True
                return
            nxt = 0
        self._index = nxt
        self._show(nxt)
        self._schedule_next()

    def stop(self) -> None:
        """停止播放但**保留控件**（幂等）。"""
        self._stopped = True
        if self._timer is not None:
            try:
                self._timer.cancel()
            except Exception:                   # noqa: BLE001
                pass
            self._timer = None

    def destroy(self) -> None:
        """停止播放并销毁容器（幂等）。"""
        self.stop()
        QtHandle.destroy(self)

    def layout(self, layout) -> None:
        apply_qt_layout(self._widget, layout)

    def set_enabled(self, enabled: bool) -> None:
        raise NotSupportedError("animation 不支持 set_enabled")


class QtLabelHandle(LabelHandle, QtHandle):
    """文本标签句柄（(a)）；`native` = `QLabel`。"""

    def set_text(self, text: str) -> None:
        self._ensure_alive()
        self._widget.setText("" if text is None else str(text))
