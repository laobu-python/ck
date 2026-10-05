"""renderer.py —— QtRenderer。

本批只交付 **button / toggle** 两个组件的真实实现，以及承载所必需的
`_destroy_root` / `is_alive` / `root`。**其余 35 个抽象方法一律抛
`NotSupportedError`**（可选能力未实现必须显式抛，**不得**静默 no-op / 返回 `None`）。

Qt 的 root 语义见 `接口合同`：
    `QApplication` 是**进程级共享**对象，**不属于**任何单个 Renderer —— 它是 所说
    "backend root" 的**载体**而非其**本体**；Renderer 拥有的是自己的 `QMainWindow`。
    `_destroy_root()` **只**销毁 `QMainWindow`，**绝不**触碰 `QApplication.instance()`。

PySide6 的导入发生在**模块顶层**（本模块只有在 `ck1_0.renderer.qt.QtRenderer` 被取用时
才会被导入 —— 见该包的惰性 `__getattr__`），且**模块级绝不创建 `QApplication`**。
"""

import os

from typing import Any, Callable, Optional, Sequence, Tuple

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import (QFont, QFontMetrics, QImage, QKeySequence, QPixmap,
                           QShortcut)
from PySide6.QtWidgets import (  # noqa: E402
    QCompleter,
    QVBoxLayout,
    QButtonGroup,
    QComboBox,
    QAbstractItemView,
    QFileDialog,
    QGridLayout,
    QInputDialog,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QListWidget,
    QMenu,
    QTabWidget,
    QToolButton,
    QSlider,
    QDoubleSpinBox,
    QLineEdit,
    QProgressBar,
    QRadioButton,
    QScrollArea,
    QWidget,
    QTextEdit,
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
)

try:
    import shiboken6
except ImportError:                     # pragma: no cover
    shiboken6 = None

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
    RendererClosedError,
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
from .handles import (QtBarsCanvas, QtBarsHandle, QtCheckboxHandle, QtComboHandle,
                      QtFloatValue, QtHandle, QtInputHandle, QtLabelsHolder, QtListHandle,
                      QtFormHandle, QtNotebookHandle, QtNumValue, QtSliderHandle, QtTableHandle,
                      QtStatusBarHandle,
                      QtProgressHandle, QtSpinboxHandle, QtTextVarValue,
                      QtRadioGroupHandle, QtScrollableHandle,
                      QtTextAreaHandle,
                      QtTimerHandle, QtToggleHandle, QtTooltipHandle, QtMediaHandle,
                      QtAnimationHandle, QtLabelHandle,
                      _ensure_grid_layout, _flush_deferred_deletes, apply_qt_layout)

try:                                    # 可选依赖（首版同策略：缺 Pillow 不致命）
    from PIL import Image as _PIL_Image
    _PIL_AVAILABLE = True
except ImportError:                     # pragma: no cover
    _PIL_Image = None
    _PIL_AVAILABLE = False

__all__ = ["QtRenderer"]


_SHORTCUT_MODS = {"ctrl": "Ctrl", "control": "Ctrl", "alt": "Alt", "shift": "Shift",
                  "cmd": "Meta", "command": "Meta", "meta": "Meta", "super": "Meta"}
_SHORTCUT_KEYS = {"esc": "Esc", "escape": "Esc", "enter": "Return", "return": "Return",
                  "space": "Space", "tab": "Tab", "backspace": "Backspace", "del": "Del",
                  "delete": "Del", "insert": "Ins", "home": "Home", "end": "End",
                  "pageup": "PgUp", "pagedown": "PgDown", "up": "Up", "down": "Down",
                  "left": "Left", "right": "Right", "plus": "+", "minus": "-"}
for _i in range(1, 13):
    _SHORTCUT_KEYS["f%d" % _i] = "F%d" % _i


def _qt_key_sequence(sequence):
    """**中立描述串 → Qt 原生写法**（Qt 侧不解释 Tk 序列，只用 `'Ctrl+S'` 形态）。

    校验规则与 Tk 侧**同一套**（形状非法 ⇒ `NotSupportedError`），保证两后端受理面一致。
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
    if len(key_raw) == 1 and key_raw.isalnum():
        key = key_raw.upper()
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
    return "+".join(mods + [key])


def _qt_media_frames(path, max_frames=None):
    """用 Pillow 打开图片并返回**独立副本**帧列表；任何失败 ⇒ `None`（冻结语义）。

    与 Tk 侧同名助手同语义（路径为空 / 文件不存在 / 无 Pillow / 解码异常 ⇒ `None`）。
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


def _qt_warn_animated(path, total_frames, shown_frame):
    """多帧提示（与 Tk 侧同义；**只提示，不改语义**）。"""
    print("提示：%s 是多帧图片（共 %d 帧），当前显示第 %d 帧；"
          "可用 animation() 播放、show_frames() 预览全部帧。"
          % (os.path.basename(path), total_frames, shown_frame))


def _qt_pixmap_from_image(img):
    """PIL 图 → `QPixmap`（RGBA 直传，不做色彩空间转换）。"""
    rgba = img.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    qimg = QImage(data, rgba.width, rgba.height, rgba.width * 4,
                  QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg.copy())


def _qt_filters(types):
    """把 `(描述, 通配)` 列表转成 Qt 的过滤器串。

    Tk 允许通配符是**元组**（`('*.png', '*.jpg')`）；直接 `%s` 会渲染出破损的
    `图片 (('*.png', '*.jpg'))` ⇒ 这里把元组/列表**归一化**为空格分隔（Qt 的写法）。
    """
    out = []
    for desc, wild in types:
        if isinstance(wild, (tuple, list)):
            wild = " ".join(str(x) for x in wild)
        out.append("%s (%s)" % (desc, wild))
    return ";;".join(out)

_ANCHOR_FLAGS = {"n": "AlignTop", "s": "AlignBottom", "e": "AlignRight",
                 "w": "AlignLeft", "center": "AlignCenter",
                 "ne": "AlignTop|AlignRight", "nw": "AlignTop|AlignLeft",
                 "se": "AlignBottom|AlignRight", "sw": "AlignBottom|AlignLeft"}


def _anchor_alignment(anchor):
    """Tk 风格锚点串 → `Qt.AlignmentFlag`（未知取值 ⇒ `NotSupportedError`，不静默）。"""
    spec = _ANCHOR_FLAGS.get(str(anchor).lower())
    if spec is None:
        raise NotSupportedError("label.anchor 不支持：%r" % (anchor,))
    flags = None
    for name in spec.split("|"):
        flag = getattr(Qt, name)
        flags = flag if flags is None else (flags | flag)
    return flags


class QtRenderer(Renderer):
    """基于 PySide6 的 renderer（最小实现）。

   生命周期
        子类 `__init__` **必须先调用 `super().__init__(theme)`** 再建立 backend root ——
       单例校验与登记发生在 `super().__init__()` 内（纪律），第 2 个实例会在分配
        `QMainWindow` **之前**被拒。随后按：`QApplication` 缺失则由本实例创建并
        记为创建者，否则复用进程里已有的那个。
    """

    def __init__(self, theme=None):
        # 纪律：登记先于 root 创建（顺序不可调换）
        super().__init__(theme)

        # QApplication 进程级共享 —— 缺失才创建，且记下"是不是我建的"
        existing = QApplication.instance()
        if existing is None:
            self._owns_app = True
            self._app = QApplication([])
        else:
            self._owns_app = False
            self._app = existing

        # Renderer 拥有的是自己的 QMainWindow（= 所说的 "backend root"）
        self._window = QMainWindow()
        self._root_handle = QtHandle(self._window)
        # 本 Renderer 弹过的 toast
        self._toasts = []
        # 本 Renderer 拥有的只读报告窗口；`_destroy_root()` 时统一关闭
        self._reports = []
        # 本 Renderer 注册的全局快捷键：持有 `QShortcut` 引用（**否则会被 GC 掉**），
        # 并记下中立串 -> Qt 原生串，供诊断/探针读回
        self._shortcuts = []
        self._shortcut_keys = {}
        # 本 Renderer 创建的动画句柄：`clear_media()` 逐个停止并销毁
        self._media = []
        # 本 Renderer 排定的定时器：`destroy()` 时统一取消
        #（QTimer 的父对象 = 本窗口，故窗口析构也会级联释放；这里显式停表以让
        #  `TimerHandle.is_active()` 在 destroy() 后立刻给出确定的 False）
        self._timers = []

    # ------------------------------------------------------------------ #
    # /  生命周期（真实实现）
    # ------------------------------------------------------------------ #
    def _destroy_root(self) -> None:
        """销毁**本实例自己的** `QMainWindow`。**幂等**；正常情况下不抛异常。

        **只**释放自己建立的资源 —— **绝不**触碰
        `QApplication.instance()`，也**不调用** `quit()`；进程退出时 `QApplication`
        由 Python 解释器回收（`self._owns_app` 为真时 likewise **什么都不做**）。

        幂等性：`deleteLater()` 只投递 `DeferredDelete`，故此处**立即排空**事件队列
        （无头环境没有 `app.exec()`），返回时 C++ 对象已析构；随后把 `_window` 置 `None`，
        于是 `is_alive()` 直接得到确定的 `False`（无需再查询）⇒ base `destroy()` 得以
       释放单例槽位，**不会锁死**（对照 的）。

       若释放**确实失败**（窗口仍在），异常原样上抛 ⇒ base 保守保留槽位。
        """
        window = getattr(self, "_window", None)
        if window is None:
            return                                  # 已释放 / 半构造：无需释放
        for _t in list(getattr(self, "_timers", None) or []):
            _t.cancel()
        if getattr(self, "_timers", None):
            self._timers.clear()
        # 先关掉本 Renderer 拥有的报告窗口。它们以 `self._window` 为 transient
        # parent，窗口析构本会级联，但显式关闭让 `Handle.exists()` 在 destroy() 返回后
        # **立刻**给出确定的 False，并保证不残留顶层窗。
        for _h in list(getattr(self, "_reports", None) or []):
            _h.destroy()
        if getattr(self, "_reports", None):
            self._reports.clear()
        try:
            window.deleteLater()
            _flush_deferred_deletes()
        except Exception:
            # 释放失败？还是窗口早已不存在？用"中立测活"判定（不匹配错误文本）
            if self._window_still_valid(window):
                raise                                # 真·释放失败：保留槽位
        self._window = None

    @staticmethod
    def _window_still_valid(window) -> bool:
        """私有测活（**不抛**）：供 `_destroy_root()` 区分"释放失败"与"早已不存在"。"""
        try:
            if shiboken6 is not None:
                return bool(shiboken6.isValid(window))
            window.objectName()
            return True
        except Exception:               # noqa: BLE001
            return False

    def is_alive(self) -> bool:
        """root 是否仍然存在且可用。

       判据（`接口合同` 的"诚实定义"）：
            `self._window is not None` **且** `QApplication.instance() is not None`
            **且** 窗口的 C++ 对象尚未被删除（`shiboken6.isValid`）。
        **禁止**用 `isVisible()` / `isHidden()`（明文禁止以"窗口可见/已 map"判定）。

        **查询失败时上抛 `RendererClosedError`（Qt 语境下的对应异常）。这与 TkRenderer
       的选①一致。** —— 二者都遵守 「`is_alive()` 承载，查询失败**不得吞成
        `False`**」；差别仅在**异常类型**：Tk 侧原样传播 `TclError`（见），
        Qt 侧统一翻译为 base 文档承诺的 `RendererClosedError`（`base.py:1329`），
       原始异常经 `raise ... from exc` 保留因果链。**要求的选择已在此显式声明。**

        `self._window is None` 表示"从未建立"或"已成功销毁"—— 两种情况都是**确定的**
        不存在，直接 `False`，无需查询，也不会掩盖任何失败。
        """
        window = getattr(self, "_window", None)
        if window is None:
            return False
        if QApplication.instance() is None:
            return False
        try:
            if shiboken6 is not None:
                return bool(shiboken6.isValid(window))
            window.objectName()                 # 回退判据：已删除对象会抛 RuntimeError
            return True
        except Exception as exc:                # 查询失败 ⇒ 上抛，绝不吞成 False
            raise RendererClosedError(
                "QtRenderer.is_alive(): 查询 QMainWindow 存活失败（底层对象不可问）"
            ) from exc

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

        注：本检查**先于** parent 校验 —— "该能力本批不支持"比"参数非法"更根本，
       且与 `TkRenderer` 的顺序一致。
        """
        if layout is not None:
            raise NotSupportedError(
                "%s: layout not supported in "
                "（本批只接受 layout=None，收到 %r）" % (method, layout)
            )

    @staticmethod
    def _resolve_font(size, bold) -> QFont:
        """按 Theme 解析出的字号/加粗构造 `QFont`（供 button 使用）。"""
        font = QFont()
        font.setPointSize(int(size))
        font.setBold(bool(bold))
        return font

    # ------------------------------------------------------------------ #
    # 组件：button（真实实现）
    # ------------------------------------------------------------------ #
    def button(self, parent: Handle, text: str,
               command: Optional[Callable[[], None]] = None,
               width: Optional[int] = None, height: Optional[int] = None,
               color: Optional[str] = None, family: Optional[str] = None,
               size: Optional[int] = None, bold: Optional[bool] = None,
               layout: Optional[Layout] = None) -> Handle:
        """按钮（`command` **无参**、UI 线程同步；`clicked` 用**默认直连**）。

       视觉参数 `None` ⇒ 取 `Theme` token：
        `color→default_color` / `family→default_family` /
        `size→label_default_size` / `bold→label_default_bold`；
        `width/height` ⇒ `button_default_width` / `button_default_height`。

        **宽度/高度的单位换算（本批新增跨后端语义，已登记）**：
        Tk 的 `Button` 宽/高以**字符/行**为单位，Qt **没有**等价单位（只有像素）。
        故用 `QFontMetrics` 把 Theme 值换算成像素并按**最小尺寸**应用 ——
        这样默认视觉量级与 Tk 相近，又不把控件钉死（`setFixedSize` 会破坏布局弹性）。
       是否改用固定尺寸/其它换算，留待本版目视确认。
        """
        self._ensure_alive()
        self._reject_layout(layout, "button")
        resolved = self._validate_parent(parent)
        theme = self.theme

        family_name = theme.default_family if family is None else family
        point_size = theme.label_default_size if size is None else size
        is_bold = theme.label_default_bold if bold is None else bold
        track_w = theme.button_default_width if width is None else width
        track_h = theme.button_default_height if height is None else height

        button = QPushButton(text, resolved.native)
        font = self._resolve_font(point_size, is_bold)
        font.setFamily(str(family_name))
        button.setFont(font)
        button.setStyleSheet(
            "QPushButton { color: %s; }"
            % (theme.default_color if color is None else color)
        )
        metrics = QFontMetrics(font)
        button.setMinimumSize(metrics.horizontalAdvance("0") * int(track_w),
                              metrics.height() * int(track_h))
        if command is not None:
            # 默认直连（AutoConnection 在 UI 线程等同 DirectConnection）
            button.clicked.connect(lambda: command())
        return QtHandle(button)

    # ------------------------------------------------------------------ #
    # 组件：toggle（真实实现，QCheckBox + QSS）
    # ------------------------------------------------------------------ #
    def toggle(self, parent: Handle, text: str = "开关", default: bool = False,
               command: Optional[Callable[[bool], None]] = None,
               width: Optional[int] = None, height: Optional[int] = None,
               on_color: Optional[str] = None, off_color: Optional[str] = None,
               layout: Optional[Layout] = None) -> ToggleHandle:
        """开关（`command` 收 `bool`；`None` ⇒ 取 `Theme` token）。

        实现策略：**容器 `QFrame` + `QCheckBox`（QSS 着色）+ `QLabel`**（任务书默认方案；
        Qt 原生没有"开关"控件，QCheckBox+QSS 是无自绘依赖下最直接的等价物）。

        `text=''` 时**仍然创建标签**（内容为空串），与首版的
        `if text:` 有意不同。

       形状注记：`width`/`height` **已消费**，且**不需要单位换算** —— 二者在首版就是
        **像素**（首版把它们交给 `tk.Canvas(frame, width=width, height=height)`，
        `advanced_widgets.py:770`）；Qt 侧同样按 px 应用到 `QCheckBox` 指示器（QSS）。
        `None` ⇒ 取 `toggle_default_width` / `toggle_default_height`。
        与 Tk 的差别只在**呈现方式**：Tk 是自绘轨道 + 白色滑块，Qt 是着色指示器（**无滑块**）
        —— 属视觉差异，连同 QSS 的 `1px`/`3px` 字面量一并登记（本版目视确认）。
        """
        self._ensure_alive()
        self._reject_layout(layout, "toggle")
        resolved = self._validate_parent(parent)
        theme = self.theme

        frame = QFrame(resolved.native)
        row = QHBoxLayout(frame)
        row.setContentsMargins(0, 0, 0, 0)
        checkbox = QCheckBox(frame)
        checkbox.setChecked(bool(default))
        # 无条件创建标签（空串 ⇒ 标签存在但内容为空）
        label = QLabel(text, frame)
        row.addWidget(checkbox)
        row.addWidget(label)

        handle = QtToggleHandle(
            frame, checkbox, label, bool(default), command,
            theme.toggle_on if on_color is None else on_color,
            theme.toggle_off if off_color is None else off_color,
            theme.toggle_outline,
            theme.toggle_default_width if width is None else width,
            theme.toggle_default_height if height is None else height,
            theme.toggle_border_width, theme.toggle_radius,
        )
        checkbox.clicked.connect(handle._on_click)
        handle._redraw()
        return handle

    # ------------------------------------------------------------------ #
    # 事件循环（真实实现）
    # ------------------------------------------------------------------ #
    def run(self) -> None:
        """进入 Qt 事件循环（`QApplication.exec()`），直到最后一个窗口关闭。

        base 契约：返回 `None`；**阻塞**；**返回后不自动 destroy**。
        返回条件（base 原文"直到窗口关闭或 `destroy()`"）：Qt 默认
        `quitOnLastWindowClosed=True`，故关闭最后一个窗口即退出循环；`destroy()`
        销毁 `QMainWindow` 亦走同一路径。**返回后不自动 destroy** ⇒ `is_alive()` 可能
        仍为真，释放责任在调用方。
        `QApplication` 是**进程级共享**对象 —— 本方法只**进入**它的
        循环，**不**调用 `quit()`，也**不**触碰其生命周期（`_destroy_root()` 同样不碰；
        `self._owns_app` 为真时亦什么都不做）。
        `destroy()` 之后的调用抛 `RendererClosedError`。
        """
        self._ensure_alive()
        self._app.exec()

    def update(self) -> None:
        """处理一次待办事件（**非阻塞**），供脚本与测试使用。

        base 契约：返回 `None`；非阻塞，处理完当前队列即返回；**不**进入主循环。
        实现：`QApplication.processEvents()`。
        `destroy()` 之后的调用抛 `RendererClosedError`。
        """
        self._ensure_alive()
        self._app.processEvents()

    # ------------------------------------------------------------------ #
    # 其余抽象方法：显式 NotSupportedError（不得静默 no-op）
    # 「哪些已实现」的权威清单 = 本实现的 methods 行
    # （此处**不写死数量**：每批都会变，写死的数字必然过期）
    # ------------------------------------------------------------------ #
    # ------------------------------------------------------------------ #
    # 窗口级方法（真实实现）
    # ------------------------------------------------------------------ #
    def set_title(self, text: str) -> None:
        """设置窗口标题（`text` 逐字交给 Qt：中文/空串均合法）。

        base 契约：返回 `None`；同步；无回调/无所有权变更；`destroy()` 后抛
        `RendererClosedError`。
        """
        self._ensure_alive()
        self._window.setWindowTitle(text)

    def set_size(self, width: int, height: int) -> None:
        """设置窗口几何（像素，`QWidget.resize`）。

        base 契约：返回 `None`；同步；`destroy()` 后抛 `RendererClosedError`。
        **已知后端差异（登记）**：Qt **原样应用**请求值（本环境实测 `1x1`、
        `1920x1080` 均按请求读回），而 Tk 侧受 WM/屏幕钳制；契约只承诺"请求"，
        **不承诺读回值与请求值相等**。详见 `开发期探针 parity`。
        """
        self._ensure_alive()
        self._window.resize(width, height)

    def center_window(self) -> None:
        """把窗口居中到**整个屏幕**的中心（与 Tk 侧同口径：`winfo_screenwidth/height`）。

        实现：取窗口所在屏幕（`QWidget.screen()`，**不**触碰进程级 `QApplication`
       的生命周期，遵守）的 `geometry()`（**整屏**，非 `availableGeometry()` ——
        与 Tk 的 `winfo_screen*` 同口径，故两端可用同一断言体），把窗口矩形中心
        对齐屏幕中心，再 `move()` 左上角。**只改位置，不改尺寸**。
        base 契约：返回 `None`；同步；`destroy()` 后抛 `RendererClosedError`。
        """
        self._ensure_alive()
        window = self._window
        screen = window.screen() or QApplication.primaryScreen()
        if screen is None:                          # 极端环境无屏幕信息 ⇒ 无可居中
            return
        frame = window.frameGeometry()
        frame.moveCenter(screen.geometry().center())
        window.move(frame.topLeft())

    def schedule(self, delay_ms: int, callback: Callable[[], None]) -> TimerHandle:
        """在 UI 线程延迟执行**一次** `callback`（中立化落点）。

        base 契约：注册同步返回 `TimerHandle`；回调**无参**、在 UI 线程同步执行；
        定时器归本 Renderer 所有，`TimerHandle.cancel()` 或 `destroy()` 释放；
        `destroy()` 之后回调不得再执行；`destroy()` 之后调用本方法抛
        `RendererClosedError`。
        实现：单次触发 `QTimer`（**父对象 = 本 Renderer 的 `QMainWindow`** ⇒ 窗口析构
        时级联释放；`_destroy_root()` 里还会显式 `stop()`）+ `QtTimerHandle`。
        **不**用 `QTimer.singleShot`：那个形态拿不到句柄，无法满足 `cancel()`。
        """
        self._ensure_alive()
        timer = QTimer(self._window)
        timer.setSingleShot(True)
        timer.timeout.connect(callback)
        timer.start(delay_ms)
        handle = QtTimerHandle(timer)
        self._timers.append(handle)
        return handle

    def label(self, parent: Handle, text: str,
              color: Optional[str] = None, family: Optional[str] = None,
              size: Optional[int] = None, bold: Optional[bool] = None,
              anchor: Optional[str] = None,
              layout: Optional[Layout] = None) -> Handle:
        """文本标签（**生效点**）。

        视觉参数默认值 → `Theme` token（同 Tk 侧）：`color→default_color` /
        `family→default_family` / **`size→label_default_size`（12）/ `bold→label_default_bold`（False）**。
        ⚠️ **与首版的有意差异**：首版 `label_ck` 默认 20/粗体，本层为 12/非粗体；
       标题层级由调用方显式传参（`title_size`/`title_weight`）。目视签收在。
        `anchor` 按 Tk 风格锚点串映射到 `Qt.AlignmentFlag`；无法识别的字母 ⇒ `NotSupportedError`。
        """
        self._ensure_alive()
        self._reject_layout(layout, "label")
        resolved = self._validate_parent(parent)
        theme = self.theme
        widget = QLabel(text, resolved.native)
        font = self._resolve_font(theme.label_default_size if size is None else size,
                                  theme.label_default_bold if bold is None else bold)
        font.setFamily(str(theme.default_family if family is None else family))
        widget.setFont(font)
        widget.setStyleSheet("color: %s;" % (theme.default_color if color is None else color))
        if anchor is not None:
            widget.setAlignment(_anchor_alignment(anchor))
        return QtLabelHandle(widget)

    def labels(self, parent: Handle, data: Optional[Sequence[str]] = None,
               background: Optional[str] = None,
               label_background: Optional[str] = None,
               label_color: Optional[str] = None,
               height: Optional[int] = None,
               layout: Optional[Layout] = None) -> Handle:
        """"序号 + 文本"标签列表（再套一层垂直滚动容器**）。

        结构：`QScrollArea`（垂直）**+ 每项一个 `QLabel`**（`QVBoxLayout`，QSS 着色）——
       与 Tk 侧同构，也逐项对齐首版 `scrollable_labels`。的落地版把内容钉成
        `setFixedHeight(labels_default_height)` ⇒ 条目一多就被**静默裁掉**且无处可滚；
       按人裁定「要方便便捷，再套一层」后改为"内容随条目自然长高、外层可滚"。
       空 `data` ⇒ `['默认标签']`（与首版一致）；`height=None` ⇒ `labels_default_height`
        （**视口**高度；不再是内容的固定高度）。
        """
        self._ensure_alive()
        self._reject_layout(layout, "labels")
        theme = self.theme
        items = list(data) if data else ["默认标签"]
        bg = theme.labels_background if background is None else background
        # 外层垂直滚动容器（`QScrollArea`；内容随条目长高 ⇒ 真的能滚）
        area = self.scrollable(parent, width=theme.labels_default_width,
                               height=theme.labels_default_height if height is None else height,
                               background=bg)
        holder = area.content.native
        holder.setStyleSheet("background-color: %s;" % bg)
        box = QVBoxLayout(holder)
        for i, text in enumerate(items):
            lbl = QLabel("%d. %s" % (i + 1, text))
            lbl.setStyleSheet("color: %s; background-color: %s; padding: %dpx %dpx;"
                              % (theme.labels_label_color if label_color is None
                                 else label_color,
                                 theme.labels_label_background if label_background is None
                                 else label_background,
                                 theme.labels_label_pady, theme.labels_label_padx))
            box.addWidget(lbl)
        handle = QtLabelsHolder(area.native, holder, len(items))
        return handle

    def input(self, parent: Handle, hint: str = "请输入",
              width: Optional[int] = None, family: Optional[str] = None,
              size: Optional[int] = None, bold: Optional[bool] = None,
              layout: Optional[Layout] = None) -> InputHandle:
        """单行输入框。占位符用 Qt **原生** `setPlaceholderText`（机制与 Tk 不同，
        但 `.value.get()` 的可观察语义一致：只显示占位符时为 `''`，见 `QtTextValue`）。
        token：`width→input_default_width` / `family→default_family` /
        `size→label_default_size` / `bold→label_default_bold`。
        """
        self._ensure_alive()
        self._reject_layout(layout, "input")
        resolved = self._validate_parent(parent)
        theme = self.theme
        widget = QLineEdit(resolved.native)
        widget.setPlaceholderText(hint)
        font = self._resolve_font(theme.label_default_size if size is None else size,
                                  theme.label_default_bold if bold is None else bold)
        font.setFamily(str(theme.default_family if family is None else family))
        widget.setFont(font)
        if width is not None:
            widget.setFixedWidth(width)
        return QtInputHandle(widget)

    def text_area(self, parent: Handle, placeholder: str = "请输入文本...",
                  width: Optional[int] = None, height: Optional[int] = None,
                  layout: Optional[Layout] = None) -> TextAreaHandle:
        """多行文本框：`QTextEdit` + **原生** `setPlaceholderText`（自带垂直滚动）。
        token：`width→input_text_area_width` / `height→input_text_area_height`。
        """
        self._ensure_alive()
        self._reject_layout(layout, "text_area")
        resolved = self._validate_parent(parent)
        theme = self.theme
        widget = QTextEdit(resolved.native)
        widget.setPlaceholderText(placeholder)
        widget.setFixedSize(theme.input_text_area_width if width is None else width,
                            theme.input_text_area_height if height is None else height)
        return QtTextAreaHandle(widget)

    def checkbox(self, parent: Handle, text: str = "复选框", default: bool = False,
                 command: Optional[Callable[[], None]] = None,
                 layout: Optional[Layout] = None) -> CheckboxHandle:
        """复选框：`QCheckBox`；值中性化为 `CheckboxHandle.value`（同值不触发）。"""
        self._ensure_alive()
        self._reject_layout(layout, "checkbox")
        resolved = self._validate_parent(parent)
        widget = QCheckBox(text, resolved.native)
        widget.setChecked(bool(default))
        handle = QtCheckboxHandle(widget, default, command)

        def _on_toggled(checked):
            if handle._value._suppress:
                return
            new = bool(checked)
            if new != handle._value._value:
                handle._value._value = new
                for cb in list(handle._value._callbacks):
                    cb(new)
                handle._fire_command()

        widget.toggled.connect(_on_toggled)
        return handle

    def radio_group(self, parent: Handle, options: Sequence[str], default: int = 0,
                    layout: Optional[Layout] = None) -> RadioGroupHandle:
        """单选组：`QFrame` 容器 + `QButtonGroup`（互斥）+ 每项一个 `QRadioButton`；
       变量值 = 选中**索引**（与首版 `IntVar` 语义一致）。**回调：无**（base 契约明文）。
        """
        self._ensure_alive()
        self._reject_layout(layout, "radio_group")
        resolved = self._validate_parent(parent)
        frame = QFrame(resolved.native)
        group = QButtonGroup(frame)
        buttons = []
        for i, opt in enumerate(options):
            rb = QRadioButton(opt, frame)
            group.addButton(rb, i)
            buttons.append(rb)
        handle = QtRadioGroupHandle(frame, group, buttons, options, default)
        buttons[default].setChecked(True)

        def _on_clicked(btn_id):
            if handle._value._suppress:
                return
            new = int(btn_id)
            if new != handle._value._value:
                handle._value._value = new
                for cb in list(handle._value._callbacks):
                    cb(new)

        group.idClicked.connect(_on_clicked)
        return handle


    def progress(self, parent: Handle, max_value: float = 100,
                 width: Optional[int] = None,
                 layout: Optional[Layout] = None) -> ProgressHandle:
        """进度条：首版的 Canvas 进度条 → `QProgressBar`。

        视觉映射：`progress_background`（底色）→ 容器/条底、`progress_track`（轨道）→ 未完成段、
        `progress_fill`（已完成段）→ `chunk` 颜色；`width=None ⇒ Theme.progress_default_width`，
        高度 ⇒ `Theme.progress_default_height`。夹取语义见 `QtProgressHandle.update`。
        """
        self._ensure_alive()
        self._reject_layout(layout, "progress")
        resolved = self._validate_parent(parent)
        theme = self.theme
        bar = QProgressBar(resolved.native)
        bar.setRange(0, 1000)
        bar.setValue(0)
        bar.setFixedHeight(theme.progress_default_height)
        # width=None ⇒ **必须**取 token（与 Tk 侧同口径；漏掉会退回 QProgressBar 的默认宽度，
        # 造成跨后端宽度不一致 —— 本批牙齿/断言当场发现该漏项）
        bar.setFixedWidth(theme.progress_default_width if width is None else width)
        bar.setStyleSheet(
            "QProgressBar { background-color: %s; border: 1px solid %s; }"
            "QProgressBar::chunk { background-color: %s; }"
            % (theme.progress_background, theme.progress_track, theme.progress_fill))
        return QtProgressHandle(bar, max_value)

    def combo(self, parent: Handle, options: Sequence[str],
              default: Optional[str] = None, width: Optional[int] = None,
              editable: bool = True,
              on_select: Optional[Callable[[str], None]] = None,
              layout: Optional[Layout] = None) -> ComboHandle:
        """下拉框：`QComboBox`；`editable=False ⇒ setEditable(False)`；选择回调
        `on_select(current_value)`。`default=None ⇒ options[0]`（Qt 无"空选项"语义，已在报告登记）。
        token：`width→combo_default_width`、`pady/padx→combo_pady/combo_padx`。
        """
        self._ensure_alive()
        self._reject_layout(layout, "combo")
        resolved = self._validate_parent(parent)
        theme = self.theme
        widget = QComboBox(resolved.native)
        widget.addItems([str(o) for o in options])
        widget.setEditable(bool(editable))
        handle = QtComboHandle(widget, options, default, on_select)
        if default is None:
            # 中性化：Tk 侧 `default=None` 给出空串；Qt 用"无选中"表达同一语义
            #（而不是 options[0]），两端 `.value.get()` 因此都从 '' 开始。
            widget.setCurrentIndex(-1)
            handle._value._value = ""
        else:
            handle._sync_visual()
        widget.currentTextChanged.connect(lambda text: handle._fire_select(text)
                                          if not handle._value._suppress else None)
        if editable:
            # **输入时过滤候选（首版 `create_combo_box` 的"自动补全"；登记为留到）**
            # 与 Tk 侧同语义：不区分大小写的**子串**匹配 + 弹出候选列表（Qt 由 `QCompleter` 承担；
            # `MatchContains` == 子串，`CaseInsensitive` == 不区分大小写）。
            _comp = QCompleter([str(o) for o in options], widget)
            _comp.setCaseSensitivity(Qt.CaseInsensitive)
            _comp.setFilterMode(Qt.MatchContains)
            _comp.setCompletionMode(QCompleter.PopupCompletion)
            widget.setCompleter(_comp)
        return handle

    def slider(self, parent: Handle, from_: float = 0, to: float = 100,
               default: Optional[float] = None, resolution: float = 1,
               width: Optional[int] = None, label: str = "",
               on_change: Optional[Callable[[float], None]] = None,
               show_value: bool = True,
               layout: Optional[Layout] = None) -> SliderHandle:
        """滑块：`QSlider`（整数刻度 + `resolution` 缩放映射）+ 标签 + 值标签。

        token 与 Tk 侧同一组；`default=None ⇒ from_`；吸附与 `on_change` 语义同 Tk。
        """
        self._ensure_alive()
        self._reject_layout(layout, "slider")
        resolved = self._validate_parent(parent)
        theme = self.theme
        lo = theme.slider_default_from if from_ is None else from_
        hi = theme.slider_default_to if to is None else to
        rs = theme.slider_default_resolution if resolution is None else resolution
        wd = theme.slider_default_width if width is None else width
        frame = QFrame(resolved.native)
        box = QHBoxLayout(frame)
        if label:
            box.addWidget(QLabel(label))
        scale = QSlider(Qt.Orientation.Horizontal)
        scale.setRange(int(lo / rs), int(hi / rs))
        scale.setSingleStep(1)
        scale.setFixedWidth(wd)
        box.addWidget(scale)
        value_label = None
        if show_value:
            value_label = QLabel("")
            value_label.setFixedWidth(theme.slider_value_width * 6)
            box.addWidget(value_label)
        handle = QtSliderHandle(scale, frame, value_label, default, lo, hi, rs, on_change)
        handle._sync_visual()

        def _on_moved(raw):
            if handle._value._suppress:
                return
            snapped = handle._value._snap(float(raw) * handle._res)
            if snapped != handle._value._value:
                handle._value._value = snapped
                if value_label is not None:
                    value_label.setText("%g" % snapped)
                for cb in list(handle._value._callbacks):
                    cb(snapped)
                handle._fire_change()

        scale.valueChanged.connect(_on_moved)
        return handle

    def spinbox(self, parent: Handle, from_: float = 0, to: float = 100,
                default: Optional[float] = None, step: float = 1,
                width: Optional[int] = None,
                command: Optional[Callable[[float], None]] = None,
                layout: Optional[Layout] = None) -> SpinboxHandle:
        """数值微调框：`QDoubleSpinBox`；中性规则同 Tk 侧（程序化 set 不触发 `command`）。"""
        self._ensure_alive()
        self._reject_layout(layout, "spinbox")
        resolved = self._validate_parent(parent)
        theme = self.theme
        lo = theme.spin_default_from if from_ is None else from_
        hi = theme.spin_default_to if to is None else to
        st = theme.spin_default_step if step is None else step
        wd = theme.spin_default_width if width is None else width
        init = lo if default is None else default
        widget = QDoubleSpinBox(resolved.native)
        widget.setRange(lo, hi)
        widget.setSingleStep(st)
        widget.setDecimals(2)
        handle = QtSpinboxHandle(widget, init, lo, hi, command)
        handle._sync_visual()
        widget.valueChanged.connect(lambda v: handle._fire_command()
                                    if not handle._value._suppress else None)
        return handle


    def searchable_list(self, parent: Handle, items: Sequence[str],
                        height: Optional[int] = None,
                        on_select: Optional[Callable[[str], None]] = None,
                        placeholder: str = "输入关键字过滤…",
                        layout: Optional[Layout] = None) -> ListHandle:
        """可搜索列表（落点）：`QLineEdit`（原生 `placeholderText`）+
        `QListWidget`（**键盘导航由 Qt 原生提供**）+ 实时不区分大小写过滤。
        """
        self._ensure_alive()
        self._reject_layout(layout, "searchable_list")
        resolved = self._validate_parent(parent)
        theme = self.theme
        frame = QWidget(resolved.native)
        box = QVBoxLayout(frame)
        entry = QLineEdit(frame)
        entry.setPlaceholderText(placeholder if placeholder else theme.list_placeholder)
        box.addWidget(entry)
        list_widget = QListWidget(frame)
        list_widget.setFixedHeight((theme.list_default_height if height is None else height)
                                   * theme.list_row_height)
        box.addWidget(list_widget)
        handle = QtListHandle(frame, list_widget, entry, items, on_select,
                              placeholder if placeholder else theme.list_placeholder)
        handle._apply_filter()
        entry.textChanged.connect(lambda _t: handle._apply_filter())
        list_widget.itemActivated.connect(lambda _i: handle._select_current())
        list_widget.itemDoubleClicked.connect(lambda _i: handle._select_current())
        return handle


    def table(self, parent: Handle, headers: Sequence[str],
              rows: Optional[Sequence[Sequence[Any]]] = None,
              height: Optional[int] = None, select_mode: str = "browse",
              on_select: Optional[Callable[[Tuple[Any, ...], Any], None]] = None,
              column_widths: Optional[Sequence[int]] = None,
              layout: Optional[Layout] = None) -> TableHandle:
        """表格（落点）：`QTableWidget` + 行选择。

        Qt 没有 Tk 的 item id ⇒ 回调第二个实参是**行索引（`int`）**；与 Tk 的 `str` iid
        **不同且不可互解** —— 契约只冻结回调**形状**，调用方不得解析该值。
        token 与 Tk 侧同一组（`select_mode` 映射：`browse→SingleSelection`、`extended→ExtendedSelection`）。
        """
        self._ensure_alive()
        self._reject_layout(layout, "table")
        resolved = self._validate_parent(parent)
        theme = self.theme
        table = QTableWidget(resolved.native)
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels([str(h) for h in headers])
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
            if (select_mode or theme.table_select_mode) == "extended"
            else QAbstractItemView.SelectionMode.SingleSelection)
        handle = QtTableHandle(table, headers)
        handle.set_rows(rows or [])
        if height is not None:
            table.setMinimumHeight(height * 20)
        if column_widths is not None:
            for idx, width in enumerate(column_widths):
                table.setColumnWidth(idx, width)
        if on_select is not None:
            def _emit():
                row = table.currentRow()
                if row < 0:
                    on_select((), None)
                    return
                values = tuple(table.item(row, j).text() if table.item(row, j) else ""
                               for j in range(table.columnCount()))
                on_select(values, row)
            table.itemSelectionChanged.connect(_emit)
        return handle


    def form(self, parent: Handle, fields: Sequence[Any],
             width: Optional[int] = None,
             layout: Optional[Layout] = None) -> FormHandle:
        """表单（commit 2）：`QWidget` + `QGridLayout`；字段 kind 与 Tk 侧一一对应
        （`entry→QLineEdit`、`combo→QComboBox`、`check→QCheckBox`、`spin→QDoubleSpinBox`、
        `slider→QSlider`(整数刻度)、`text→QTextEdit`）。
        """
        self._ensure_alive()
        self._reject_layout(layout, "form")
        resolved = self._validate_parent(parent)
        theme = self.theme
        frame = QWidget(resolved.native)
        grid = QGridLayout(frame)
        # `form_grid_cell_padx` 是**二元组**（登记为 (5, 10) 形态）⇒ Qt 需解包成左右
        cell = theme.form_grid_cell_padx
        left = int(cell[0] if isinstance(cell, (tuple, list)) else cell)
        right = int(cell[1] if isinstance(cell, (tuple, list)) and len(cell) > 1 else left)
        grid.setContentsMargins(left, int(theme.form_pady), right, int(theme.form_pady))
        grid.setVerticalSpacing(theme.form_grid_pady)
        kinds, widgets = {}, {}
        for row, spec in enumerate(fields):
            key, label, kind = spec[0], spec[1], spec[2]
            args = list(spec[3:])
            grid.addWidget(QLabel(label), row, 0)
            if kind == "combo":
                w = QComboBox(frame)
                if args:
                    w.addItems([str(x) for x in args[0]])
                # 中性化（同 combo）：Tk 侧 combo 初始为空串 ⇒ Qt 用"无选中"表达同一语义
                w.setCurrentIndex(-1)
                # 修复**：默认值（首版的 combo `*args[1]`）—— **必须**放在
                # `setCurrentIndex(-1)` **之后**，否则会被它清掉（首版就栽在这里）。
                if len(args) > 1 and args[1] != "":
                    w.setCurrentText(str(args[1]))
            elif kind == "check":
                w = QCheckBox(frame)
                # 修复**：默认值（首版的 check *args[0]）
                w.setChecked(bool(args[0]) if args else False)
            elif kind == "spin":
                w = QDoubleSpinBox(frame)
                w.setRange(float(args[0]) if args else 0.0,
                           float(args[1]) if len(args) > 1 else 100.0)
            elif kind == "slider":
                w = QSlider(Qt.Orientation.Horizontal)
                w.setRange(int(args[0]) if args else 0, int(args[1]) if len(args) > 1 else 100)
            elif kind == "text":
                w = QTextEdit(frame)
                w.setFixedHeight(theme.form_text_lines * 18)
                # 修复**：默认值（首版的 text *args[1]）
                if len(args) > 1 and args[1]:
                    w.setPlainText(str(args[1]))
            else:
                w = QLineEdit(frame)
                # 修复**：默认值（首版的 entry *args[0]）
                if args:
                    w.setText(str(args[0]))
            grid.addWidget(w, row, 1)
            kinds[key] = kind
            widgets[key] = w
        return QtFormHandle(frame, kinds, widgets)


    def notebook(self, parent: Handle, tabs: Sequence[Any],
                 height: Optional[int] = None, width: Optional[int] = None,
                 layout: Optional[Layout] = None) -> NotebookHandle:
        """页签容器（第 1 个 commit：content callable 收 `Handle`）：`QTabWidget`。

        `content` 语义与 Tk 侧一致（`None` / callable / Handle 列表 / 单个 Handle）；
        token 同一组（`notebook_default_size` 默认 `(600, 280)`）。
        """
        self._ensure_alive()
        self._reject_layout(layout, "notebook")
        resolved = self._validate_parent(parent)
        theme = self.theme
        dw, dh = theme.notebook_default_size
        nb = QTabWidget(resolved.native)
        nb.setFixedSize(dw if width is None else width, dh if height is None else height)
        titles = []
        for title, content in tabs:
            page = QWidget()
            box = QVBoxLayout(page)
            box.setContentsMargins(0, theme.notebook_content_pady, 0,
                                   theme.notebook_content_pady)
            handle = QtHandle(page)
            if callable(content) and not isinstance(content, Handle):
                content(handle)                      #：传 Handle
            elif isinstance(content, (list, tuple)):
                for child in content:
                    box.addWidget(child.native)
            elif content is not None:
                box.addWidget(content.native)
            nb.addTab(page, title)
            titles.append(title)
        return QtNotebookHandle(nb, titles)


    def scrollable(self, parent: Handle, width: Optional[int] = None,
                   height: Optional[int] = None,
                   background: Optional[str] = None,
                   layout: Optional[Layout] = None) -> ScrollableHandle:
        """**垂直**可滚动容器：`QScrollArea` + 内容 `QWidget`（垂直滚动条常驻策略由 Qt 定）。

        token：`width→scroll_default_width` / `height→scroll_default_height` /
        `background→scroll_background`（QSS 底色）/ 边框 `scroll_border`。
        """
        self._ensure_alive()
        self._reject_layout(layout, "scrollable")
        resolved = self._validate_parent(parent)
        theme = self.theme
        area = QScrollArea(resolved.native)
        area.setWidgetResizable(True)
        content = QWidget()
        bg = theme.scroll_background if background is None else background
        content.setStyleSheet("background-color: %s;" % bg)
        area.setStyleSheet("QScrollArea { background-color: %s; border: %dpx solid %s; }"
                           % (bg, theme.scroll_border, bg))
        area.setWidget(content)
        area.setFixedSize(theme.scroll_default_width if width is None else width,
                          theme.scroll_default_height if height is None else height)
        return QtScrollableHandle(area, content)

    def visualization_canvas(self, parent: Handle,
                             width: Optional[int] = None,
                             height: Optional[int] = None,
                             background: Optional[str] = None,
                             layout: Optional[Layout] = None) -> ScrollableHandle:
        """**水平**可滚动可视化画布：`QScrollArea`（**只能水平滚动**）+ 内容 `QWidget`。

        token：`viz_default_size`（默认 `(800, 120)`）/ `viz_background` / `viz_border`。
        """
        self._ensure_alive()
        self._reject_layout(layout, "visualization_canvas")
        resolved = self._validate_parent(parent)
        theme = self.theme
        dw, dh = theme.viz_default_size
        area = QScrollArea(resolved.native)
        area.setWidgetResizable(True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        bg = theme.viz_background if background is None else background
        content.setStyleSheet("background-color: %s;" % bg)
        area.setStyleSheet("QScrollArea { background-color: %s; border: %dpx solid %s; }"
                           % (bg, theme.viz_border, bg))
        area.setWidget(content)
        area.setFixedSize(dw if width is None else width, dh if height is None else height)
        return QtScrollableHandle(area, content)


    def bars(self, parent: Handle, data: Optional[Sequence[float]] = None,
             canvas_width: Optional[int] = None,
             canvas_height: Optional[int] = None,
             background: Optional[str] = None,
             min_bar_width: Optional[int] = None,
             padding: Optional[int] = None, label_rotation: int = 0,
             show_bg_stripes: bool = True,
             bar_colors: Optional[Sequence[str]] = None,
             layout: Optional[Layout] = None) -> Optional[Handle]:
        """自绘柱状图（+，落点）：`QtBarsCanvas`（`paintEvent` + `QPainter`）。

        **空 `data` ⇒ `None`**（冻结语义）；绘制（条纹/渐变/旋转标签/描边）**全部归 backend**。
：外层套**水平滚动容器**
        （`visualization_canvas`），内层画布宽度取**绘制所需宽度**（与 Tk 同一公式；
        `min_bar_width` 顶住时 > 视口宽）⇒ 长数据**真的**能横向滚，柱子不再被**静默裁掉**。
        token 与 Tk 侧同一组。
        """
        self._ensure_alive()
        self._reject_layout(layout, "bars")
        if not data:
            return None
        theme = self.theme
        w = theme.bars_default_width if canvas_width is None else canvas_width
        h = theme.bars_default_height if canvas_height is None else canvas_height
        opts = {
            "background": theme.bars_background if background is None else background,
            "stripe": theme.bars_stripe, "stripe_light": theme.bars_stripe_light,
            "text_color": theme.bars_text_color, "outline": theme.bars_outline,
            "padding": theme.bars_padding if padding is None else padding,
            "spacing": theme.bars_spacing,
            "min_bar_width": theme.bars_min_bar_width if min_bar_width is None else min_bar_width,
            "label_band": theme.bars_label_band, "height_reserve": theme.bars_height_reserve,
            "font_min": theme.bars_font_min, "font_max": theme.bars_font_max,
            "label_rotation": label_rotation, "stripes": bool(show_bg_stripes),
            "colors": list(bar_colors) if bar_colors else _qt_gradient_palette(len(data)),
        }
        n = len(data)
        # 与 Tk 侧**同一公式**（`QtBarsCanvas.paintEvent` 内部也用这条 ⇒ 两边柱宽一致）
        step = max(opts["min_bar_width"],
                   (w - 2 * opts["padding"] - (n - 1) * opts["spacing"]) // n)
        need_w = max(w, 2 * opts["padding"] + n * step + (n - 1) * opts["spacing"])
        # 外层水平滚动容器（`QScrollArea`）；内容宽度 = 绘制所需宽度
        area = self.visualization_canvas(parent, width=w, height=h,
                                         background=opts["background"])
        widget = QtBarsCanvas(area.content.native, data, opts)
        # 底色同时写进 QSS：既是 Qt 的常规做法，也让"底色 token 已消费"可直接读回（断言证据）
        widget.setStyleSheet("background-color: %s;" % opts["background"])
        widget.setFixedSize(need_w, h)
        return QtBarsHandle(area.native, area.content.native, widget, n)


    def container(self, parent: Handle, layout: Optional[Layout] = None,
                  col_weights: Optional[Sequence[int]] = None) -> Handle:
        """创建一个普通容器（/，已签）。

        `layout` 描述**该容器自身在 `parent` 中**如何放置；`None` ⇒ 取实现默认
        （Qt 适配层 = **顺序流**：把容器加进 `parent` 的垂直布局，必要时创建；
        若 `parent` 是 `QMainWindow` 则用其 central widget —— Qt 不允许直接给
        QMainWindow 设布局）。
        `col_weights` 是该容器**自身网格**的各列权重；判据系在 `layout.kind`：
          * `layout is None` / `kind='pack'` ⇒ 顺序流容器 ⇒ `col_weights` 无意义，
            **按允许的静默忽略处理**；
          * `kind='grid'` ⇒ 容器自身建 `QGridLayout` ⇒ `setColumnStretch(i, w)`；
           已有非网格布局却要求网格 ⇒ `NotSupportedError`（不得静默）。
       只保证"容器被放进 `parent` 的几何管理"，**不**承诺权属（Qt 上
        `addWidget()` 会 `setParent`，`into` 销毁会**连带销毁**用户控件 —— 见 `apply_qt_layout`）。
        异常：`InvalidParentError` / `RendererClosedError` / `NotSupportedError`。
        """
        self._ensure_alive()
        resolved = self._validate_parent(parent)
        frame = QFrame(resolved.native)
        effective = Layout.pack() if layout is None else layout
        # ：同 Tk —— `col_weights` 作用于**容器自身的内部网格**，
        # 与容器自己在 `parent` 中怎么摆无关 ⇒ 给了就设置（`_ensure_grid_layout` 会按需建
        # `QGridLayout`；纯顺序流容器上这些 stretch 是惰性的）。
        if col_weights is not None:
            grid = _ensure_grid_layout(frame)
            for _i, _w in enumerate(col_weights):
                grid.setColumnStretch(_i, _w)
        apply_qt_layout(frame, effective)
        return QtHandle(frame)

    def toolbar(self, parent: Handle,
                items: Optional[Sequence[Any]] = None) -> Handle:
        """工具条：`QWidget` + `QHBoxLayout` + `QPushButton` / `QToolButton`+`QMenu`。

        `items` 结构同 Tk 侧（`(text, command, kind[, menu_items])`）；token 同一组。
        """
        self._ensure_alive()
        resolved = self._validate_parent(parent)
        theme = self.theme
        bar = QWidget(resolved.native)
        box = QHBoxLayout(bar)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(theme.toolbar_item_padx)
        for item in (items or []):
            text, command, kind = item[0], item[1], item[2]
            extra = item[3] if len(item) > 3 else None
            if kind == "menu":
                mb = QToolButton(bar)
                mb.setText(text)
                menu = QMenu(mb)
                for entry in (extra or []):
                    label, action = entry[0], entry[1]
                    act = menu.addAction(label)
                    if action is not None:
                        act.triggered.connect(lambda _c=False, a=action: a())
                mb.setMenu(menu)
                mb.setPopupMode(QToolButton.InstantPopup)
                box.addWidget(mb)
            else:
                btn = QPushButton(text, bar)
                if command is not None:
                    btn.clicked.connect(lambda _c=False, a=command: a())
                box.addWidget(btn)
        return QtHandle(bar)

    def status_bar(self, parent: Handle,
                   initial_text: str = "Ready") -> StatusBarHandle:
        """状态栏：`QLabel`（QSS 边框/下沉观感）+ `StatusBarHandle.set_status`。"""
        self._ensure_alive()
        resolved = self._validate_parent(parent)
        theme = self.theme
        widget = QLabel(initial_text or theme.status_default_text, resolved.native)
        widget.setStyleSheet("QLabel { border: %dpx solid palette(mid); }"
                            % theme.status_borderwidth)
        widget.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return QtStatusBarHandle(widget)


    # ------------------------------------------------------------------ #
    # 剪贴板（真实实现；已销毁 ⇒ RendererClosedError）
    # ------------------------------------------------------------------ #
    def set_clipboard_text(self, text: str) -> None:
        """写入系统剪贴板（`QApplication.clipboard().setText(text)`）。

        **的边界说明**：剪贴板是**进程级 GUI 服务**（`QClipboard` 挂在与
        `QApplication` 同一层级），Qt 没有控件级替代品（`QWidget` 无 clipboard API）——
        故这里**必须**取 `QApplication.clipboard()`。这是**只取服务、不碰生命周期**：
        本方法**不**创建/销毁/`quit()` `QApplication`，`_destroy_root()` 亦不碰它。
        base 契约：返回 `None`；同步；`destroy()` 后抛 `RendererClosedError`。
        """
        self._ensure_alive()
        clipboard = QApplication.clipboard()
        if clipboard is None:                       # 极端环境无剪贴板服务
            raise NotSupportedError("Qt 环境未提供 QClipboard（无法实现剪贴板能力）")
        clipboard.setText(text)

    def get_clipboard_text(self) -> str:
        """读取系统剪贴板；**无内容时返回空串**（base 明文）。

       同上：只取 `QApplication.clipboard()` 服务，不触碰其生命周期。
        `destroy()` 后抛 `RendererClosedError`。
        """
        self._ensure_alive()
        clipboard = QApplication.clipboard()
        if clipboard is None:
            return ''
        return clipboard.text() or ''

    def message(self, title: str, text: str, kind: str = "info") -> None:
        """模态消息框：`info→QMessageBox.information` /
        `warning→…warning` / `error→…critical`；**未知 `kind` 无动作**（首版明文）。

        **同步性**：Qt 的 `QMessageBox.information` 内部 `exec()` ⇒ **阻塞**；探针同样只能打桩断言 dispatch。
        """
        self._ensure_alive()
        fn = {"info": QMessageBox.information, "warning": QMessageBox.warning,
              "error": QMessageBox.critical}.get(kind)
        if fn is None:
            return                                   #：未知 kind 不动作
        fn(self._window, title, text)

    def ask_input(self, title: str = "输入", prompt: str = "请输入:",
                  default: str = "") -> Optional[str]:
        """**同步**文本输入框。

        要求："Qt 侧须以局部事件循环实现同步语义"** —— 本实现调用 Qt 的**阻塞式**对话框
        `QInputDialog.getText(...)`：它内部**跑一个局部（嵌套）事件循环**直到用户确认/取消，
        因此**保持同步返回**（返回 `str | None`），**不**改用信号/回调异步化。
        返回：确认 ⇒ `str`；取消/关闭 ⇒ `None`。
        """
        self._ensure_alive()
        text, ok = QInputDialog.getText(self._window, title, prompt,
                                        QLineEdit.EchoMode.Normal, default)
        return text if ok else None

    def ask_save_path(self, title: str = "保存文件",
                      defaultextension: str = ".csv",
                      filetypes: Optional[Sequence[Tuple[str, str]]] = None
                      ) -> Optional[str]:
        """**同步**保存路径选择：`QFileDialog.getSaveFileName(...)`（同样**局部事件循环**）。

        `filetypes=None` ⇒ 首版默认类型；**取消/空路径 ⇒ `None`**（与 Tk 侧归一化一致）。
        """
        self._ensure_alive()
        types = (list(filetypes) if filetypes is not None
                 else [("CSV 文件", "*.csv"), ("所有文件", "*.*")])
        filters = _qt_filters(types)
        path, _sel = QFileDialog.getSaveFileName(self._window, title,
                                                 "out" + defaultextension, filters)
        return path or None


    def ask_open_path(self, title: str = "选择文件",
                      filetypes: Optional[Sequence[Tuple[str, str]]] = None
                      ) -> Optional[str]:
        """**同步**打开文件路径选择：`QFileDialog.getOpenFileName(...)`（局部事件循环）。

        `filetypes=None` ⇒ `(('所有文件','*.*'),)`；**取消/空路径 ⇒ `None`**（与 Tk 归一化一致）。
        """
        self._ensure_alive()
        types = (list(filetypes) if filetypes is not None else [("所有文件", "*.*")])
        filters = _qt_filters(types)
        path, _sel = QFileDialog.getOpenFileName(self._window, title, "", filters)
        return path or None

    def ask_directory(self, title: str = "选择目录") -> Optional[str]:
        """**同步**目录选择：`QFileDialog.getExistingDirectory(...)`（局部事件循环）。"""
        self._ensure_alive()
        path = QFileDialog.getExistingDirectory(self._window, title)
        return path or None


    def report_window(self, title: str, text: str) -> Handle:
        """只读文本报告窗口（首版 `show_image_report` 的**展示部分**）。

        **顶层部件**（base 契约：不接受 `parent`，由本 Renderer 自己拥有）。
       只负责**展示**；报告**内容**属数据层（`utils/apng.py`）；首版的三个按钮
        属**业务组合**，由 C/G 段用 `container` + `button` + 本句柄组合。

        Qt 形态：`QWidget(self._window, Qt.Window)`（**顶层窗 + transient parent**）
        + 只读 `QTextEdit`（`setReadOnly(True)`、`NoWrap`、字体 = token `report`、
        正文 = `text`）。**滚动条由 `QTextEdit` 原生自带**（对照 Tk 侧显式
        `Scrollbar`）——这是允许的 backend 差异，不进本位面契约。

        返回：窗口 `Handle`（`destroy()` 关窗，幂等）。
        同步性：同步返回，**不进入局部事件循环**（非模态）。
        释放：随本句柄 `destroy()` 或 `Renderer.destroy()` 释放。
        """
        self._ensure_alive()
        theme = self.theme
        holder = QWidget(self._window, Qt.WindowType.Window)
        holder.setWindowTitle(title)
        width, height = theme.media_report_window_size
        holder.resize(int(width), int(height))

        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        body = QTextEdit(holder)
        body.setReadOnly(True)
        body.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        fam, size = theme.report
        font = body.font()
        font.setFamily(str(fam))
        font.setPointSize(int(size))
        body.setFont(font)
        body.setPlainText(text)
        layout.addWidget(body)
        holder.show()

        handle = QtHandle(holder)
        self._reports.append(handle)
        return handle

    def toast(self, text: str, duration_ms: Optional[int] = None,
              kind: str = "info") -> None:
        """轻提示：无边框置顶 `QLabel` 顶层窗 + `QTimer` 到期关闭；未知 kind 回退 `info`。

        token 与 Tk 侧同一组（颜色 / 字体 / 内边距 / 底距 / 默认时长）。
        """
        self._ensure_alive()
        theme = self.theme
        color = {"info": theme.toast_info, "success": theme.toast_success,
                 "warning": theme.toast_warning, "error": theme.toast_error}.get(
                     kind, theme.toast_info)
        duration = theme.toast_default_duration_ms if duration_ms is None else duration_ms
        fam, size = theme.toast
        top = QLabel(text, None, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        top.setStyleSheet("background-color: %s; color: %s; padding: %dpx %dpx;"
                          % (color, theme.toast_text_color, theme.toast_pady,
                             theme.toast_padx))
        f = top.font()
        f.setFamily(str(fam))
        f.setPointSize(int(size))
        top.setFont(f)
        top.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, bool(theme.toast_topmost))
        screen = self._window.screen().geometry() if self._window.screen() else None
        top.adjustSize()
        if screen is not None:
            top.move(max(0, screen.center().x() - top.width() // 2),
                     max(0, screen.height() - top.height() - theme.toast_bottom_offset))
        top.show()
        timer = QTimer(top)
        timer.setSingleShot(True)
        timer.timeout.connect(top.close)
        timer.start(duration)
        self._toasts.append((top, timer))

    # ------------------------------------------------------------------ #
    # 窗口置顶与全局快捷键
    # ------------------------------------------------------------------ #
    def set_always_on_top(self, flag: bool = True) -> None:
        """置顶开关：`Qt.WindowStaysOnTopHint`。

        **Qt 特性（已登记）**：改窗口标志会让窗口**隐藏**，故必须紧跟一次 `show()`；
        否则"置顶成功但窗口消失"。本方法封装该顺序，调用方无需知道。
        """
        self._ensure_alive()
        win = self._window
        win.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, bool(flag))
        win.show()                              # Qt：改 flag 后必须重新 show

    def add_shortcut(self, sequence: str, callback: Callable[[], None]) -> None:
        """注册全局快捷键。

        **落地**：`sequence` 是 backend 中立描述串（如 `'Ctrl+S'`），Qt 侧在
        `_qt_key_sequence()` 里校验并规整为 Qt 原生写法（`'Ctrl+S'`），
        再交给 `QShortcut` + `QKeySequence`。无法识别 ⇒ `NotSupportedError`（不静默）。
        回调**无参**；`QShortcut` 的引用由本 Renderer 持有（否则会被 GC）。
        """
        self._ensure_alive()
        key_text = _qt_key_sequence(sequence)
        cut = QShortcut(QKeySequence(key_text), self._window)
        cut.activated.connect(lambda: callback())
        self._shortcuts.append(cut)
        self._shortcut_keys[key_text] = sequence

    # ------------------------------------------------------------------ #
    # 菜单栏与提示气泡
    # ------------------------------------------------------------------ #
    def menu_bar(self, parent: Handle, items: Optional[Sequence[Any]] = None) -> Handle:
        """窗口菜单栏（首版 `create_menu`）。

        **窗口级**部件：`parent` **显式**表达"属于哪个窗口"（通常传 `Renderer.root`）。
        Qt 形态：取该窗口的原生菜单栏 `QMainWindow.menuBar()`。

        `items` 每项 `(菜单名, [(标签, 无参回调), ...])`；**重复调用 = 替换**
        （与 Tk 侧 `root.config(menu=…)` 语义一致：本侧先 `clear()` 再重建）。
        返回：菜单栏 `Handle`（`native` = `QMenuBar`）。
        异常：`parent` 不是 `QMainWindow`（如普通 `QWidget`）⇒ `NotSupportedError` ——
       根菜单栏是**窗口级**结构，普通控件没有可挂载的菜单栏（已把
        "根菜单栏结构"登记为 backend 边界；本层不静默降级为"浮层菜单"）。
        """
        self._ensure_alive()
        resolved = self._validate_parent(parent)
        win = resolved.native
        if not isinstance(win, QMainWindow):
            raise NotSupportedError(
                "menu_bar 需要 QMainWindow 作为 parent（窗口级菜单栏）；收到 %s"
                % type(win).__name__)
        bar = win.menuBar()
        bar.clear()
        for entry in (items or []):
            name, sub = entry[0], (entry[1] if len(entry) > 1 else None)
            menu = bar.addMenu(name)
            for item in (sub or []):
                label, command = item[0], (item[1] if len(item) > 1 else None)
                act = menu.addAction(label)
                if command is not None:
                    act.triggered.connect(lambda _checked=False, cb=command: cb())
        return QtHandle(bar)

    def tooltip(self, target: Handle, text: str,
                delay_ms: Optional[int] = None) -> TooltipHandle:
        """给控件挂提示气泡（首版 `create_tooltip`）。

        `target` 是**显式**目标句柄；Enter/Leave 经事件过滤器进入，延迟用单次 `QTimer`，
        显示/隐藏用原生 `QToolTip`。
        （已登记）**：Qt 侧只消费 `tooltip_delay_ms` + 文本；`tooltip_background` /
        `tooltip_relief` / `tooltip_borderwidth` / `tooltip_offset` **不被本侧消费**
        （`QToolTip` 由 QSS 驱动、样式固定）—— 目视结论留。
        返回：`TooltipHandle`（`native` = 目标控件）。
        """
        self._ensure_alive()
        resolved = self._validate_parent(target)
        return QtTooltipHandle(resolved.native, text, self.theme, delay_ms)

    # ------------------------------------------------------------------ #
    # 媒体：静态图 / 逐帧预览（Pillow 可选）
    # ------------------------------------------------------------------ #
    def photo(self, parent: Handle, path: str, text: str = "",
              color: Optional[str] = None, family: Optional[str] = None,
              size: Optional[int] = None, bold: Optional[bool] = None,
              frame: int = 0, warn_animated: bool = True,
              layout: Optional[Layout] = None) -> Optional[MediaHandle]:
        """静态图片（可取多帧文件的第 `frame` 帧）；语义与 Tk 侧逐条一致。

        **冻结语义**：无 Pillow / 路径为空 / 文件不存在 / 解码失败 ⇒ `None`（不抛）。
        结构：容器 + 图片 `QLabel` + 说明 `QLabel`。token 同 Tk 侧（`media_caption_*`）。
        """
        self._ensure_alive()
        resolved = self._validate_parent(parent)
        theme = self.theme
        frames = _qt_media_frames(path)
        if not frames:
            return None
        total = len(frames)
        idx = int(frame)
        if not (0 <= idx < total):          # 越界 ⇒ None（对齐首版：`seek` 越界即失败）
            return None
        if warn_animated and total > 1:
            _qt_warn_animated(path, total, idx)
        box = QWidget(resolved.native)
        vbox = QVBoxLayout(box)
        vbox.setContentsMargins(0, 0, 0, 0)
        image_label = QLabel(box)
        image_label.setPixmap(_qt_pixmap_from_image(frames[idx]))
        vbox.addWidget(image_label)
        box._ck10_image_label = image_label
        if text:
            caption = QLabel(text, box)
            font = caption.font()
            font.setFamily(str(theme.media_caption_family if family is None else family))
            font.setPointSize(int(theme.media_caption_size if size is None else size))
            font.setBold(bool(theme.media_caption_weight == "bold") if bold is None else bool(bold))
            caption.setFont(font)
            caption.setStyleSheet("color: %s;"
                                  % (theme.media_caption_color if color is None else color))
            vbox.addWidget(caption)
            box._ck10_caption_label = caption
        if layout is not None:
            apply_qt_layout(box, layout)
        return QtMediaHandle(box)

    def frame_preview(self, parent: Handle, path: str, columns: int = 3,
                      thumb_width: Optional[int] = None, labels: bool = True,
                      max_frames: Optional[int] = None,
                      layout: Optional[Layout] = None) -> Optional[Handle]:
        """逐帧缩略图预览（首版 `show_frames`）；语义与 Tk 侧逐条一致。

        `thumb_width=None` ⇒ token `media_thumb_width`（像素值不在 base 硬编码）。
        冻结语义：路径为空 / 无 Pillow / 解码失败 ⇒ `None`。
        """
        self._ensure_alive()
        resolved = self._validate_parent(parent)
        theme = self.theme
        width = int(theme.media_thumb_width if thumb_width is None else thumb_width)
        frames = _qt_media_frames(path, max_frames=max_frames)
        if not frames:
            return None
        cols = max(1, int(columns))
        box = QWidget(resolved.native)
        grid = QGridLayout(box)
        grid.setContentsMargins(0, 0, 0, 0)
        keep = []
        for idx, img in enumerate(frames):
            ratio = width / float(img.width or 1)
            thumb = img.resize((width, max(1, int(img.height * ratio))))
            pix = _qt_pixmap_from_image(thumb)
            keep.append(pix)
            cell = QWidget(box)
            cell_box = QVBoxLayout(cell)
            cell_box.setContentsMargins(0, 0, 0, 0)
            image_label = QLabel(cell)
            image_label.setPixmap(pix)
            cell_box.addWidget(image_label)
            if labels:
                tag = QLabel("默认图/封面" if idx == 0 else "帧 %d" % idx, cell)
                font = tag.font()
                fam, fsize = theme.media_frame[0], theme.media_frame[1]
                font.setFamily(str(fam))
                font.setPointSize(int(fsize))
                font.setBold(len(theme.media_frame) > 2 and theme.media_frame[2] == "bold")
                tag.setFont(font)
                tag.setStyleSheet("color: %s;"
                                  % (theme.media_frame_default if idx == 0
                                     else theme.media_frame_animation))
                cell_box.addWidget(tag)
            grid.addWidget(cell, idx // cols, idx % cols)
        box._ck10_photos = keep
        box._ck10_media_grid = grid
        if layout is not None:
            apply_qt_layout(box, layout)
        return QtMediaHandle(box)

    def animation(self, parent: Handle, path: str, text: str = "",
                  color: Optional[str] = None, family: Optional[str] = None,
                  size: Optional[int] = None, bold: Optional[bool] = None,
                  start: int = 0, max_frames: Optional[int] = None,
                  max_loops: Optional[int] = None,
                  on_frame: Optional[Callable[[int, int], None]] = None,
                  frame_delay: Optional[int] = None,
                  layout: Optional[Layout] = None) -> AnimationHandle:
        """播放动画；语义与 Tk 侧逐条一致（失败哨兵 / 延迟下限 / 轮数 / 回调 / 释放）。"""
        self._ensure_alive()
        resolved = self._validate_parent(parent)
        theme = self.theme
        frames = _qt_media_frames(path, max_frames=max_frames) or []
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
        box = QWidget(resolved.native)
        vbox = QVBoxLayout(box)
        vbox.setContentsMargins(0, 0, 0, 0)
        image_label = QLabel(box)
        vbox.addWidget(image_label)
        box._ck10_image_label = image_label
        if text:
            caption = QLabel(text, box)
            font = caption.font()
            font.setFamily(str(theme.media_caption_family if family is None else family))
            font.setPointSize(int(theme.media_caption_size if size is None else size))
            font.setBold(bool(theme.media_caption_weight == "bold") if bold is None else bool(bold))
            caption.setFont(font)
            caption.setStyleSheet("color: %s;"
                                  % (theme.media_caption_color if color is None else color))
            vbox.addWidget(caption)
            box._ck10_caption_label = caption
        if layout is not None:
            apply_qt_layout(box, layout)
        handle = QtAnimationHandle(self, box, image_label, frames, delays, theme,
                                   start=start, max_loops=max_loops, on_frame=on_frame)
        self._media.append(handle)
        return handle

    # ------------------------------------------------------------------ #
    # 媒体释放
    # ------------------------------------------------------------------ #
    def clear_media(self) -> None:
        """停止并销毁本 Renderer 创建的**全部动画**，并清空登记（幂等）。

       语义与 Tk 侧逐条一致（范围收窄理由见 Tk 侧 docstring 与报告）：
        只处理 `animation` 句柄（renderer 侧唯一持有状态的媒体），不影响其它控件。
        异常：Renderer 已销毁 ⇒ `RendererClosedError`；其余情况不抛（幂等）。
        """
        self._ensure_alive()
        for handle in list(self._media):
            try:
                handle.stop()
                handle.destroy()
            except Exception:                   # noqa: BLE001 —— 幂等
                pass
        self._media.clear()

    def _live_toasts(self):
        """私有：当前仍存活的 toast 数量（供探针读取）。"""
        alive = [(w, t) for (w, t) in self._toasts if w.isVisible()]
        self._toasts = alive
        return len(alive)





def _qt_gradient_palette(n: int):
    """按索引生成渐变调色板（**backend 自己的**视觉实现）。"""
    out = []
    for i in range(max(1, n)):
        t = i / max(1, n - 1) if n > 1 else 0.0
        out.append("#%02x%02x%02x" % (int(0x4c + t * (0x21 - 0x4c)),
                                      int(0xaf + t * (0x96 - 0xaf)),
                                      int(0x50 + t * (0xf3 - 0x50))))
    return out
