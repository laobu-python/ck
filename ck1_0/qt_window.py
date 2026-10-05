# -*- coding: utf-8 -*-
"""ck1_0.qt_window —— Qt 门面：一个新手友好、可复用的窗口外壳。

为什么有这个模块
    `QtRenderer` 是**后端中立渲染层**的 Qt 实现，它只提供"一个一个控件"，
    没有"窗口整体该长什么样"这一层。而新手遇到的第一个问题恰恰是"我的窗口怎么摆"；
    这个问题的答案（深色底、圆角卡片、留白层级、悬停反馈、步骤导航、翻页与进度）
    在每个用 Qt 写引导/工具的人手里都会被重写一遍。本模块把这份重复劳动收成一个小外壳，
    让调用方只关心"这一页放什么控件"。

三条纪律
    1. **导入期零副作用**：`import ck1_0.qt_window` 不创建 `QApplication`、不创建
       `QtRenderer`；一切资源都在 `QtWindow(...)` **实例化**时才建立（进程内只允许
       一个存活的 `Renderer`，若在导入期建根，任何一次 import 都会抢走那个唯一槽位）。
    2. **中立优先、逃生口显式**：控件一律走 `Renderer` 的中立工厂方法（`container` /
       `label` / `button` / `toggle` / `progress` / `scrollable` / ...）；中立契约**没有**的
      视觉参数（布局间距与边距、圆角、渐变、滚动区尺寸策略、透明度动画）走 允许的
       逃生口 `handle.native`，并在每一处写明"为什么必须走逃生口"。
    3. **不引入第三方依赖**：只用 `ck1_0.*` + `PySide6` + 标准库。

已知的中立层缺口（本模块因此走逃生口的地方，逐条登记）
    * `Renderer` 没有"显示窗口"的中立方法（`run()` 只进事件循环）⇒ `QtWindow.show()` 用
      `root.native.show()`。**这是必须的**：QMainWindow 不 show 就永远不会被画出来。
    * `Handle.layout(Layout.pack(padx=..., pady=...))` 的 padding 在 Qt 适配层被忽略
      （`apply_qt_layout` 只做 `addWidget`）⇒ 间距只能由 `QLayout.setContentsMargins/Spacing`
      给出。
    * `scrollable()` 用 `setFixedSize(theme.scroll_default_*)` 钉死尺寸 ⇒ 想让它随窗口伸缩
      必须先解除固定尺寸并改 `QSizePolicy`。
    * 视觉词（背景色 / 边框 / 圆角 / 渐变 / hover / 禁用态）不在中立签名里（=(b)：中立
      API **不**扩张视觉参数面）⇒ 统一由 QSS 提供，经 `root.native.setStyleSheet(...)` 施加。
    * 中立 `label()` / `button()` 的 `color` 缺省是 `Theme.default_color`（`#000000`，深色底上
      不可读），且**每个控件自带一份 QSS**（子控件的 QSS 优先级高于祖先）⇒ 本模块每次建
      控件都显式给色，并把"换配色后重下控件 QSS"登记成刷新项。
    * `slider()` 的句柄 `native` 是**内部** `QSlider`，外层还有一层"标签 + 数值"容器；
      中立 `layout(into=…)` 只会搬走 `QSlider` ⇒ 见 `guide_qt.py` 的 `place_native` 用法。
"""

from typing import Callable, Dict, List, Optional, Sequence, Tuple

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetrics, QLinearGradient,
                           QPainter, QPen)
from PySide6.QtWidgets import (QCheckBox, QFrame, QGraphicsOpacityEffect, QHBoxLayout,
                               QLabel, QSizePolicy, QVBoxLayout, QWidget)

try:                                    # 包模式（`import ck1_0.qt_window`）
    from .renderer.base import Handle, LabelHandle, Layout
    from .renderer.qt import QtRenderer
except ImportError:                     # 脚本模式（cwd = 仓库根，`ck1_0` 在 sys.path 上）
    from ck1_0.renderer.base import Handle, LabelHandle, Layout
    from ck1_0.renderer.qt import QtRenderer

__all__ = ['QtWindow', 'Card', 'PALETTES']

# Qt 的"无上限"尺寸（`QWIDGETSIZE_MAX`）。解除 `setFixedSize` 时必须还原到它，
# 否则控件仍然被钉死。
_QWIDGETSIZE_MAX = 16777215
_FAMILY = 'Microsoft YaHei'

# 两套配色：深色底 + 渐变强调色（青→紫 / 琥珀→玫红）。键名在 QSS 模板里逐字使用。
PALETTES: Dict[str, Dict[str, str]] = {
    '深空青紫': {
        'label': '深空青紫',
        'bg': '#0a0f1c', 'card': '#141d33', 'card_soft': '#101828', 'tip': '#131c31',
        'hero1': '#17203a', 'hero2': '#101a30',
        'border': '#26314f', 'text': '#e8eefc', 'dim': '#93a3c4',
        'a1': '#22d3ee', 'a2': '#a855f7', 'on': '#06131f', 'ok': '#34d399',
        'btn': '#1b2440', 'btn_hover': '#232f52', 'btn_press': '#0e1730',
    },
    '暖阳琥珀': {
        'label': '暖阳琥珀',
        'bg': '#16110b', 'card': '#241b12', 'card_soft': '#1d160e', 'tip': '#221a11',
        'hero1': '#2a1e12', 'hero2': '#1e150d',
        'border': '#3d2f21', 'text': '#fbeee0', 'dim': '#c0a68c',
        'a1': '#f59e0b', 'a2': '#f43f5e', 'on': '#1a1006', 'ok': '#4ade80',
        'btn': '#2c2116', 'btn_hover': '#3a2b1c', 'btn_press': '#1a130c',
    },
}

# 文字层级表：大标题 / 副标题 / 正文 / 次要文字 + 两种强调。
_LEVELS: Dict[str, Tuple[int, bool, str]] = {
    'title': (17, True, 'text'),
    'subtitle': (13, False, 'text'),
    'body': (12, False, 'text'),
    'dim': (10, False, 'dim'),
    'accent': (12, True, 'a1'),
    'ok': (12, True, 'ok'),
}


def build_qss(p: Dict[str, str]) -> str:
    """按配色生成全局 QSS（深色底 + 渐变强调色 + 圆角卡片 + 悬停/按下反馈）。

    QSS 里**不放任何彩色 emoji**：本仓库在 Microsoft YaHei 下踩过"彩色 emoji 变豆腐块"
   的坑，故一切图形语义都用字体安全符号或 `QPainter` 自绘。
    """
    return """
QMainWindow { background-color: %(bg)s; }
QWidget#ckShell { background-color: %(bg)s; }
QLabel { background: transparent; color: %(text)s; }

QFrame#ckHeroCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 %(hero1)s, stop:1 %(hero2)s);
    border: 1px solid %(border)s;
    border-radius: 18px;
}
QFrame#ckCard {
    background-color: %(card)s;
    border: 1px solid %(border)s;
    border-radius: 14px;
}
QFrame#ckNavCard {
    background-color: %(card_soft)s;
    border: 1px solid %(border)s;
    border-radius: 14px;
}
QFrame#ckFooterCard {
    background-color: %(card_soft)s;
    border: 1px solid %(border)s;
    border-radius: 14px;
}
QFrame#ckTipCard {
    background-color: %(tip)s;
    border: 1px solid %(border)s;
    border-left: 3px solid %(a1)s;
    border-radius: 10px;
}
QFrame#ckAccentBar {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 %(a1)s, stop:1 %(a2)s);
    border: none;
    border-radius: 2px;
}

QPushButton {
    color: %(text)s;
    background-color: %(btn)s;
    border: 1px solid %(border)s;
    border-radius: 10px;
    padding: 7px 16px;
}
QPushButton:hover { background-color: %(btn_hover)s; border-color: %(a1)s; }
QPushButton:pressed { background-color: %(btn_press)s; }
QPushButton:disabled { color: %(dim)s; background-color: %(card)s; }

QLineEdit {
    background-color: %(card)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 10px;
    padding: 8px 12px;
    selection-background-color: %(a2)s;
}
QLineEdit:focus { border-color: %(a1)s; }

QTextEdit {
    background-color: %(card)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 10px;
    padding: 6px 8px;
}

QSlider::groove:horizontal { height: 8px; background: %(border)s; border-radius: 4px; }
QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 %(a1)s, stop:1 %(a2)s);
    border-radius: 4px;
}
QSlider::handle:horizontal {
    background: %(text)s; width: 16px; margin: -5px 0; border-radius: 8px;
}
QSlider::handle:horizontal:hover { background: %(a1)s; }

QTableWidget {
    background-color: %(card)s;
    alternate-background-color: %(card_soft)s;
    gridline-color: %(border)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 10px;
    selection-background-color: %(a2)s;
    selection-color: %(text)s;
}
QHeaderView::section {
    background-color: %(card_soft)s;
    color: %(dim)s;
    padding: 7px 10px;
    border: none;
    border-right: 1px solid %(border)s;
    border-bottom: 1px solid %(border)s;
}
QTableCornerButton::section { background-color: %(card_soft)s; border: none; }

QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: %(border)s; border-radius: 5px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: %(a1)s; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0; }
QScrollBar::handle:horizontal { background: %(border)s; border-radius: 5px; min-width: 28px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
""" % p


class _GradientTitle(QWidget):
    """渐变文字大标题（自绘）。

    为什么自绘：QSS 的 `color` **不支持渐变**，而"青→紫渐变大标题"是这个外壳
    "高级感"的主视觉。用 `QPainter` + `QPen(QBrush(QLinearGradient))` 画文字是不引
    第三方依赖的唯一办法（与本仓库"需要图标/图形就自己画"的同一思路）。
    """

    def __init__(self, text: str, parent=None, point_size: int = 25,
                 color_a: str = '#22d3ee', color_b: str = '#a855f7'):
        super().__init__(parent)
        self._text = text
        self._c1, self._c2 = color_a, color_b
        self._font = QFont(_FAMILY)
        self._font.setPointSize(point_size)
        self._font.setBold(True)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(QFontMetrics(self._font).height() + 8)

    def set_colors(self, color_a: str, color_b: str) -> None:
        """换主题时改渐变两端（并请求重绘）。"""
        self._c1, self._c2 = color_a, color_b
        self.update()

    def set_text(self, text: str) -> None:
        """改文案（同时刷新尺寸请求）。"""
        self._text = text
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:                        # noqa: N802 —— Qt 命名
        metrics = QFontMetrics(self._font)
        return QSize(metrics.horizontalAdvance(self._text) + 6, metrics.height() + 8)

    def paintEvent(self, _event) -> None:               # noqa: N802 —— Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0, 0, max(1, self.width()), 0)
        gradient.setColorAt(0.0, QColor(self._c1))
        gradient.setColorAt(1.0, QColor(self._c2))
        painter.setFont(self._font)
        painter.setPen(QPen(QBrush(gradient), 0))
        painter.drawText(self.rect(),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         self._text)
        painter.end()


class Card:
    """一张内容卡片：圆角 `QFrame`（`handle`）+ 内部纵向流容器（`body`）。

    调用方通常只用 `card.body` 当 parent 继续放控件。
    """

    __slots__ = ('handle', 'body')

    def __init__(self, handle: Handle, body: Handle):
        self.handle = handle
        self.body = body

    def __repr__(self) -> str:
        return '<Card %r>' % (self.handle,)


class _Footer:
    """底部区域控制器（`QtWindow.add_footer` 的返回值）。

    `add_footer` 按任务书返回 `(set_progress, set_prev_enabled)` 两个可调用对象；
    其余能力（改下一步文案、禁用完成按钮、改进度说明）挂在本对象上，
    调用方从 `QtWindow.footer` 取用。
    """

    def __init__(self, handle: Handle):
        self.handle = handle
        self._progress = None
        self._caption: Optional[LabelHandle] = None
        self._prev = None
        self._next = None
        self._finish = None

    # --- 任务书要求的两件套 ------------------------------------------- #
    def set_progress(self, value: float) -> None:
        """更新进度条（0..100；夹取由 `ProgressHandle.update` 负责）。"""
        if self._progress is not None:
            self._progress.update(value)

    def set_prev_enabled(self, flag: bool) -> None:
        """启用/禁用「上一步」（中立 `Handle.set_enabled`，：只挡交互、不改值）。"""
        if self._prev is not None:
            self._prev.set_enabled(bool(flag))

    # --- 附加能力 ------------------------------------------------------ #
    def set_caption(self, text: str) -> None:
        """改进度条右侧的说明文字（如「第 3 / 8 步」）。"""
        if self._caption is not None:
            self._caption.set_text(text)

    def set_next_text(self, text: str) -> None:
        """改「下一步」的文案（最后一步时改成「完成」之类）。"""
        if self._next is not None:
            self._next.native.setText(text)

    def set_next_enabled(self, flag: bool) -> None:
        """启用/禁用「下一步」。"""
        if self._next is not None:
            self._next.set_enabled(bool(flag))

    def set_finish_enabled(self, flag: bool) -> None:
        """启用/禁用「完成」。"""
        if self._finish is not None:
            self._finish.set_enabled(bool(flag))


class QtWindow:
    """把 `QtRenderer` 包成"新手友好"的窗口外壳。

    典型用法（零配置即可跑）::

        win = QtWindow('我的第一个窗口')
        win.add_hero('你好，Qt', '这是一句副标题')
        card = win.card()
        win.text(card.body, '正文写在卡片里。')
        win.run()

    属性:
        renderer: 本窗口拥有的 `QtRenderer`（`run()` / `destroy()` 都在它上面）。
        root:     backend root 的 `Handle`（`root.native` 即 `QMainWindow`）。
        content:  可滚动内容区的 `Handle`，调用方可直接往里放控件。
        footer:   `add_footer` 之后可用的底部控制器（`_Footer`）。
    """

    # ---------------------------------------------------------------- #
    # 构造
    # ---------------------------------------------------------------- #
    def __init__(self, title: str = 'ck1.0', width: int = 1080, height: int = 720,
                 theme=None):
        # 中立工厂：`QtRenderer` 自己复用/创建进程级 QApplication，并拥有一个 QMainWindow。
        # 注意：进程内只允许一个存活的 Renderer —— 这里就是"建根"的唯一时机。
        self.renderer = QtRenderer(theme)
        self._palette_name = next(iter(PALETTES))
        self._palette = dict(PALETTES[self._palette_name])
        self._refreshers: List[Callable[[], None]] = []
        self._texts: List[Tuple[LabelHandle, str]] = []
        self._pages: List[QWidget] = []
        self._animations: List[QPropertyAnimation] = []
        self._status_label: Optional[LabelHandle] = None
        self._hero_title: Optional[_GradientTitle] = None
        self._nav_buttons: List[Handle] = []
        self._nav_index = -1
        self._scroll_area = None
        self._footer: Optional[_Footer] = None

        self.renderer.set_title(title)
        self.renderer.set_size(*self._fit_screen(width, height))

        self.root = self.renderer.root
        self._build_shell()
        self.on_theme_change(self._restyle_texts)
        self._apply_style()
        # 逃生口（必须）：中立契约没有"显示窗口"的方法，而 `run()` 只负责进事件循环；
        # QMainWindow 不被 show 就永远不会画出来（父代理在真机上实测确认过）。
        self.show()
        # 先 show 再居中：show 之前 `frameGeometry()` 不含窗口装饰，算出来的落点会偏。
        self.renderer.center_window()

    @staticmethod
    def _fit_screen(width: int, height: int) -> Tuple[int, int]:
        """把请求尺寸夹到屏幕可用区域内（窗口自适应，避免小屏上超出边界）。"""
        try:
            from PySide6.QtWidgets import QApplication
            screen = QApplication.primaryScreen()
            if screen is not None:
                available = screen.availableGeometry()
                width = min(int(width), max(720, available.width() - 80))
                height = min(int(height), max(520, available.height() - 80))
        except Exception:               # 查询失败 ⇒ 用请求值（无屏幕信息时也照常可建）
            pass
        return int(width), int(height)

    def _build_shell(self) -> None:
        """骨架：hero / body（导航 + 内容）/ footer / 状态条，四行网格。

        结构全部由**中立** `container(..., Layout.grid(...), col_weights=...)` 搭建：
        `col_weights` 作用于容器**自身**的内部网格，正好用来表达
        "导航窄、内容宽"这种两列权重。唯一走逃生口的是行伸缩与内边距 —— 中立层没有
        这两个概念。
        """
        shell = self.renderer.container(self.root, col_weights=[1])
        shell.native.setObjectName('ckShell')
        layout = shell.native.layout()
        layout.setContentsMargins(22, 18, 22, 14)
        layout.setSpacing(14)
        layout.setRowStretch(1, 1)              # 第 1 行（body）吃掉全部剩余高度
        self._shell = shell

        self._hero_host = self._cell(shell, 0)
        self._body_host = self._cell(shell, 1, col_weights=[0, 1])
        self._footer_host = self._cell(shell, 2)
        self._status_host = self._cell(shell, 3)

        body_layout = self._body_host.native.layout()
        if body_layout is not None:
            body_layout.setContentsMargins(0, 0, 0, 0)
            body_layout.setSpacing(14)
            body_layout.setRowStretch(0, 1)
        self._nav_host = self.renderer.container(self._body_host,
                                                 Layout.grid(row=0, column=0))
        self._content_host = self.renderer.container(self._body_host,
                                                     Layout.grid(row=0, column=1))
        # 导航列给一个舒服的宽度区间（中立层无"宽度提示"概念 ⇒ 逃生口）。
        self._nav_host.native.setMinimumWidth(206)
        self._nav_host.native.setMaximumWidth(268)

        self._build_content_area()

    def _cell(self, shell: Handle, row: int, col_weights=None) -> Handle:
        """在 shell 网格里取一个单元格（`col_weights` 给该单元格**自身**的内部网格）。"""
        return self.renderer.container(shell, Layout.grid(row=row, column=0),
                                       col_weights=col_weights)

    def _build_content_area(self) -> None:
        """可滚动内容区。

        选 `scrollable()` 而不是裸 `container()`：8 步引导的内容长度不一，长内容必须
        能滚。代价是 `scrollable()` 会 `setFixedSize(theme.scroll_default_*)` 把尺寸钉死，
        故这里用逃生口解除固定尺寸并改成"可伸缩"（否则放大窗口时内容区不跟着长）。
        """
        width = max(360, self.renderer.theme.scroll_default_width)
        height = max(260, self.renderer.theme.scroll_default_height)
        scroll = self.renderer.scrollable(self._content_host, width=width, height=height,
                                          background=self._palette['card_soft'])
        scroll.layout(Layout.pack(into=self._content_host))
        area = scroll.native
        area.setMinimumSize(0, 0)
        area.setMaximumSize(_QWIDGETSIZE_MAX, _QWIDGETSIZE_MAX)
        area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        if area.layout() is not None:       # QScrollArea 的内部布局未必已经建好
            area.layout().setContentsMargins(0, 0, 0, 0)
        self._scroll_area = area
        self._scroll_handle = scroll
        self.content = scroll.content
        self.on_theme_change(self._restyle_scroll)

    def _restyle_scroll(self) -> None:
        """把内容区外层与内层的底色刷新成当前配色（`scrollable()` 自带浅色底 QSS）。"""
        background = self._palette['card_soft']
        try:
            self._scroll_area.setStyleSheet(
                'QScrollArea { background-color: %s; border: none; }' % background)
            self.content.native.setStyleSheet('background-color: %s;' % background)
        except Exception:               # 控件已被销毁（窗口关闭中）⇒ 静默跳过
            pass

    # ---------------------------------------------------------------- #
    # 样式与主题
    # ---------------------------------------------------------------- #
    @property
    def palette_names(self) -> List[str]:
        """可用配色名（顺序即定义顺序）。"""
        return list(PALETTES.keys())

    @property
    def palette(self) -> Dict[str, str]:
        """当前配色的只读副本。"""
        return dict(self._palette)

    @property
    def palette_name(self) -> str:
        """当前配色名。"""
        return self._palette_name

    @property
    def footer(self) -> '_Footer':
        """底部控制器（`add_footer` 之后可用；还没建时抛 `RuntimeError`）。"""
        if self._footer is None:
            raise RuntimeError('还没有调用 QtWindow.add_footer(...)，底部区域不存在')
        return self._footer

    def on_theme_change(self, callback: Callable[[], None]) -> None:
        """登记"换配色后要重画什么"的回调（并立刻调用一次，保证初值一致）。"""
        self._refreshers.append(callback)
        try:
            callback()
        except Exception:               # 初次施加失败不应阻断窗口构建
            pass

    def set_palette(self, name: str) -> None:
        """切换配色并**立刻**生效（重下全局 QSS + 跑一遍所有局部刷新）。

        未知名字抛 `KeyError`（快速失败，不静默回落）。
        """
        if name not in PALETTES:
            raise KeyError('未知配色 %r（可用：%s）' % (name, '、'.join(PALETTES)))
        self._palette_name = name
        self._palette = dict(PALETTES[name])
        self._apply_style()

    def _apply_style(self) -> None:
        """把全局 QSS 施加到 backend root，再跑一遍局部刷新回调。"""
        self.root.native.setStyleSheet(build_qss(self._palette))
        for refresh in list(self._refreshers):
            try:
                refresh()
            except Exception:           # 单个刷新项失败不影响整窗换肤
                pass

    def _level_style(self, level: str) -> Tuple[int, bool, str]:
        """层级 → 中立 `label()` 的 (size, bold, 颜色值)。"""
        size, bold, key = _LEVELS.get(level, _LEVELS['body'])
        return size, bold, self._palette[key]

    # ---------------------------------------------------------------- #
    # 通用零件
    # ---------------------------------------------------------------- #
    def box(self, parent: Optional[Handle] = None, orientation: str = 'v',
            margin: Sequence[int] = (0, 0, 0, 0), spacing: int = 10) -> Handle:
        """建一个中立容器，并把它的原生布局调成指定方向/间距/边距。

        返回中立 `Handle`（`container()` 的产物），可直接当 `parent` 或 `into` 使用。
        间距与方向**不在**中立签名里（`Layout.pack` 的 padx/pady 在 Qt 适配层被忽略）
        ⇒ 走逃生口建 `QVBoxLayout` / `QHBoxLayout`。
        """
        parent = self.content if parent is None else parent
        handle = self.renderer.container(parent, Layout.pack())
        native = handle.native
        layout = QVBoxLayout(native) if orientation == 'v' else QHBoxLayout(native)
        layout.setContentsMargins(*[int(v) for v in margin])
        layout.setSpacing(int(spacing))
        return handle

    def card(self, parent: Optional[Handle] = None, title: Optional[str] = None,
             subtitle: Optional[str] = None) -> Card:
        """建一张圆角卡片（可选标题/副标题），返回 `Card(handle, body)`。"""
        outer = self.box(parent, 'v', margin=(20, 16, 20, 18), spacing=8)
        outer.native.setObjectName('ckCard')
        if title:
            self.text(outer, title, level='title')
        if subtitle:
            self.text(outer, subtitle, level='dim', wrap=True)
        return Card(outer, outer)

    def text(self, parent: Handle, content: str, level: str = 'body',
             wrap: bool = False) -> LabelHandle:
        """放一段文字。

        `level` 给层级（大标题/副标题/正文/次要文字四档 + `accent`/`ok` 两种强调）：
        层级差异由中立参数 `size`/`bold`/`color` 表达 —— 这三个参数中立签名里**有**。
        `wrap` 是唯一的例外（中立层无换行控制）。所有标签都登记进刷新表，
        否则换配色后旧文字会留着上一套配色的颜色。
        """
        size, bold, color = self._level_style(level)
        label = self.renderer.label(parent, content, color=color, family=_FAMILY,
                                    size=size, bold=bold)
        if wrap:
            label.native.setWordWrap(True)
        label.layout(Layout.pack(into=parent))
        self._texts.append((label, level))
        return label

    def _restyle_texts(self) -> None:
        """把已建标签的文字色刷新成当前配色（逐控件 QSS ⇒ 必须逐个重下）。"""
        for label, level in list(self._texts):
            try:
                if not label.exists():
                    continue
                _size, _bold, color = self._level_style(level)
                label.native.setStyleSheet('color: %s;' % color)
            except Exception:
                continue

    def button(self, parent: Handle, content: str, command: Optional[Callable[[], None]] = None,
               size: int = 12, bold: bool = False, primary: bool = False) -> Handle:
        """建一个按钮并放进 `parent` 的流布局。

        必须显式给 `color=`：中立 `button()` 的缺省文字色是 `Theme.default_color`
        （`#000000`），在深色底上是"黑字黑底"（就是踩了这个语义坑）。
        """
        handle = self.renderer.button(parent, content, command=command,
                                      color=self._palette['text'], size=size, bold=bold)
        handle.layout(Layout.pack(into=parent))
        handle.native.setCursor(Qt.CursorShape.PointingHandCursor)
        self.on_theme_change(lambda h=handle: self.style_button(h, primary))
        return handle

    def style_button(self, handle: Handle, primary: bool = False) -> None:
        """重新施加按钮样式（`primary=True` 走渐变主色）。

        公开的理由：调用方可能想让"当前选中"的按钮**跟配色一起变**（例如换主题页的两个
        配色按钮）—— 逐控件 QSS 会盖住全局 QSS，故换肤后必须有人再喊一次。
        """
        try:
            if not handle.exists():
                return
            handle.native.setStyleSheet(self._primary_qss() if primary
                                        else self._button_qss())
        except Exception:
            pass

    def _button_qss(self) -> str:
        """次要按钮：深色底 + 描边，hover 提亮并把描边换成强调色。"""
        return """
QPushButton {
    color: %(text)s; background-color: %(btn)s; border: 1px solid %(border)s;
    border-radius: 10px; padding: 7px 16px;
}
QPushButton:hover { background-color: %(btn_hover)s; border-color: %(a1)s; }
QPushButton:pressed { background-color: %(btn_press)s; }
QPushButton:disabled { color: %(dim)s; background-color: %(card)s; }
""" % self._palette

    def _primary_qss(self) -> str:
        """主按钮：渐变强调色（青→紫），hover 时两端对调。"""
        return """
QPushButton {
    color: %(on)s; border: none; border-radius: 10px; padding: 8px 20px;
    font-weight: bold;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 %(a1)s, stop:1 %(a2)s);
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 %(a2)s, stop:1 %(a1)s);
}
QPushButton:pressed { background: %(a2)s; }
QPushButton:disabled { color: %(dim)s; background: %(card)s; }
""" % self._palette

    def toggle(self, parent: Handle, content: str, default: bool = False,
               command: Optional[Callable[[bool], None]] = None) -> Handle:
        """建一个开关并放进 `parent` 的流布局。

        中立 `toggle()` 把 on/off 色做成**参数**（这两个是中立签名里有的），但**描边色**
        取 `Theme.toggle_outline`（`#999`，浅色主题的灰）⇒ 只能事后用逃生口重下那一段
        QSS，否则深色底上会出现一道突兀的亮灰边框。
        """
        handle = self.renderer.toggle(parent, content, default=default, command=command,
                                      on_color=self._palette['a1'],
                                      off_color=self._palette['card'])
        handle.layout(Layout.pack(into=parent))
        self.compact(handle)            # 内部 QHBoxLayout 会把余量摊成项间距 ⇒ 收拢靠左
        self.on_theme_change(lambda h=handle: self._style_toggle(h))
        return handle

    def _style_toggle(self, handle: Handle) -> None:
        """重下开关指示器的 QSS（尺寸沿用 theme 的两个 token，不另造数字）。"""
        try:
            if not handle.exists():
                return
            checkbox = handle.native.findChild(QCheckBox)
            if checkbox is None:
                return
            theme = self.renderer.theme
            checkbox.setStyleSheet(
                'QCheckBox::indicator { border: 1px solid %(border)s; border-radius: 5px;'
                ' width: %(w)dpx; height: %(h)dpx; background-color: %(card)s; }'
                'QCheckBox::indicator:checked { background-color: %(a1)s; }'
                % dict(self._palette, w=int(theme.toggle_default_width),
                       h=int(theme.toggle_default_height)))
            checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        except Exception:
            pass

    def tip(self, parent: Handle, content: str) -> Handle:
        """高亮提示条（左侧一道渐变强调线）。"""
        box = self.box(parent, 'v', margin=(14, 10, 14, 10), spacing=4)
        box.native.setObjectName('ckTipCard')
        self.text(box, content, level='dim', wrap=True)
        return box

    def compact(self, target) -> None:
        """把一行控件"左对齐收拢"：在该行布局的末尾加一段弹性空白。

        为什么需要：`QtRenderer` 造的复合控件（`toggle`/`slider`）内部是 `QHBoxLayout`，
        而 QHBoxLayout 会把多余宽度**平摊成项间距** ⇒ 控件被拉得七零八落。
        末尾加一段 stretch 就把余量交给它，前面的控件自然靠左贴紧。
        接受中立 `Handle` 或原生 `QWidget`（`slider` 的外层容器没有中立句柄）。
        """
        widget = getattr(target, 'native', target)
        layout = widget.layout() if widget is not None else None
        if layout is not None:
            layout.addStretch(1)

    # ---------------------------------------------------------------- #
    # 任务书要求的五件套
    # ---------------------------------------------------------------- #
    def add_hero(self, title: str, subtitle: str) -> Handle:
        """顶部大标题区：渐变卡片 + 渐变文字大标题 + 副标题 + 渐变强调条。"""
        hero = self.box(self._hero_host, 'v', margin=(24, 20, 24, 20), spacing=6)
        hero.native.setObjectName('ckHeroCard')

        accent = QFrame()
        accent.setObjectName('ckAccentBar')
        accent.setFixedHeight(4)
        accent.setFixedWidth(96)
        hero.native.layout().addWidget(accent)

        gradient_title = _GradientTitle(title, color_a=self._palette['a1'],
                                        color_b=self._palette['a2'])
        hero.native.layout().addWidget(gradient_title)
        self._hero_title = gradient_title
        self._hero_card = hero

        self.text(hero, subtitle, level='dim', wrap=True)
        self.on_theme_change(self._restyle_hero)
        return hero

    def _restyle_hero(self) -> None:
        """刷新英雄区的渐变文字两端颜色。"""
        if self._hero_title is not None:
            self._hero_title.set_colors(self._palette['a1'], self._palette['a2'])

    def add_step_nav(self, steps: Sequence[str],
                     on_select: Callable[[int], None]) -> Callable[[int], None]:
        """左侧步骤导航：每步一个按钮，当前步用渐变高亮；点击即跳转。

        返回 `set_current(index)` —— 调用方负责在切页时喊它一声。
        """
        card = self.box(self._nav_host, 'v', margin=(14, 14, 14, 14), spacing=6)
        card.native.setObjectName('ckNavCard')
        self.text(card, '学习路线', level='dim')
        self.text(card, '共 %d 步 · 点标题可跳转' % len(steps), level='dim', wrap=True)

        buttons: List[Handle] = []
        for index, name in enumerate(steps):
            handle = self.button(card, '%d. %s' % (index + 1, name),
                                 command=(lambda i=index: on_select(i)))
            buttons.append(handle)
        self._nav_buttons = buttons

        def set_current(index: int) -> None:
            for i, handle in enumerate(buttons):
                try:
                    if handle.exists():
                        handle.native.setStyleSheet(self._nav_qss(i == index))
                except Exception:
                    continue
            self._nav_index = index

        # 换配色后必须重下导航两态（逐控件 QSS 会盖住全局 QSS）。
        self._refreshers.append(lambda: set_current(self._nav_index))
        return set_current

    def _nav_qss(self, active: bool) -> str:
        """导航按钮的"当前步 / 普通步"两态样式。"""
        p = self._palette
        if active:
            return ('QPushButton { color: %(on)s; border: none; border-radius: 10px;'
                    ' padding: 9px 12px; text-align: left; font-weight: bold;'
                    ' background: qlineargradient(x1:0, y1:0, x2:1, y2:0,'
                    ' stop:0 %(a1)s, stop:1 %(a2)s); }' % p)
        return ('QPushButton { color: %(dim)s; background: transparent;'
                ' border: 1px solid transparent; border-radius: 10px;'
                ' padding: 9px 12px; text-align: left; }'
                'QPushButton:hover { color: %(text)s; background-color: %(btn)s;'
                ' border-color: %(border)s; }' % p)

    def add_footer(self, progress_value: float = 0,
                   on_prev: Optional[Callable[[], None]] = None,
                   on_next: Optional[Callable[[], None]] = None,
                   on_finish: Optional[Callable[[], None]] = None,
                   prev_enabled: bool = True) -> Tuple[Callable[[float], None],
                                                       Callable[[bool], None]]:
        """底部：进度条 + 「← 上一步」/「下一步 →」/「完成」。

        返回任务书要求的 `(set_progress, set_prev_enabled)`；其余控制项见 `self.footer`。
        """
        footer = self.box(self._footer_host, 'h', margin=(16, 12, 16, 12), spacing=12)
        footer.native.setObjectName('ckFooterCard')
        controller = _Footer(footer)
        self._footer = controller

        controller._prev = self.button(footer, '← 上一步', command=on_prev)

        bar = self.renderer.progress(footer, max_value=100,
                                     width=self.renderer.theme.progress_default_width)
        bar.layout(Layout.pack(into=footer))
        # `progress()` 用 setFixedWidth 定宽 + 自带一份浅色 QSS ⇒ 两处都要用逃生口改写。
        bar.native.setMinimumWidth(180)
        bar.native.setMaximumWidth(_QWIDGETSIZE_MAX)
        bar.native.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        bar.native.setFormat('')
        controller._progress = bar
        self.on_theme_change(lambda b=bar: self._style_progress(b))

        controller._caption = self.text(footer, '', level='dim')
        controller._next = self.button(footer, '下一步 →', command=on_next)
        controller._finish = self.button(footer, '完成', command=on_finish,
                                         bold=True, primary=True)

        controller.set_progress(progress_value)
        controller.set_prev_enabled(prev_enabled)
        return controller.set_progress, controller.set_prev_enabled

    def _style_progress(self, bar) -> None:
        """重下进度条 QSS（默认那份是浅色 token，深色底上很扎眼）。"""
        try:
            if not bar.exists():
                return
            bar.native.setStyleSheet(
                'QProgressBar { background-color: %(card)s; border: 1px solid %(border)s;'
                ' border-radius: 8px; }'
                'QProgressBar::chunk { border-radius: 7px; background:'
                ' qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 %(a1)s, stop:1 %(a2)s); }'
                % self._palette)
        except Exception:
            pass

    def status(self, text: str) -> None:
        """底部状态文字（懒建一个标签，之后的调用只改文本）。"""
        if self._status_label is None:
            strip = self.box(self._status_host, 'h', margin=(6, 0, 6, 0), spacing=8)
            self._status_label = self.text(strip, text, level='dim')
        else:
            self._status_label.set_text(text)

    # ---------------------------------------------------------------- #
    # 页面切换（供引导使用：淡入 + 滚动复位）
    # ---------------------------------------------------------------- #
    def register_page(self, page_handle: Handle) -> None:
        """登记一个"页"（`content` 里的容器），供 `show_page` 切换可见性。"""
        page_handle.native.setVisible(False)
        self._pages.append(page_handle.native)

    def show_page(self, index: int, animate: bool = True) -> None:
        """只显示第 `index` 页，并做一次淡入过渡。"""
        for i, native in enumerate(self._pages):
            native.setVisible(i == index)
        if index < 0 or index >= len(self._pages):
            return
        self.scroll_top()
        if animate:
            self._fade_in(self._pages[index])

    def scroll_top(self) -> None:
        """把内容区滚回顶部（翻页后不清滚动位置，会让人以为页面是空的）。"""
        try:
            self._scroll_area.verticalScrollBar().setValue(0)
        except Exception:
            pass

    def _fade_in(self, widget: QWidget) -> None:
        """给页面挂一个透明度动画（`QGraphicsOpacityEffect` + `QPropertyAnimation`）。

        为什么走原生：中立契约里**没有**动画原语（`Handle` 只有 native/layout/…），
        而"翻页淡入"是外壳的观感要求。`setGraphicsEffect` 把 effect 的所有权交给控件，
        动画又以控件为 parent ⇒ 不会被 Python GC 掉。
        """
        try:
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
            animation = QPropertyAnimation(effect, b'opacity', widget)
            animation.setDuration(240)
            animation.setStartValue(0.0)
            animation.setEndValue(1.0)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            animation.start()
            self._animations.append(animation)      # 再保一份引用（双保险）
            self._animations = self._animations[-8:]
        except Exception:               # 动画失败不影响"页已经切过去了"这件正事
            pass

    # ---------------------------------------------------------------- #
    # 生命周期
    # ---------------------------------------------------------------- #
    def show(self) -> None:
        """显示窗口（幂等）。中立契约没有 show ⇒ 逃生口 `root.native`。"""
        native = self.root.native
        if not native.isVisible():
            native.show()

    def run(self) -> None:
        """进入 Qt 事件循环（阻塞，直到窗口关闭）。返回后**不**自动销毁。"""
        self.show()
        self.renderer.run()

    def close(self) -> None:
        """幂等关窗并释放 backend root（满足 单例纪律）。

        先 `QWidget.close()` 再 `Renderer.destroy()`，顺序不能反：`destroy()` 走的是
        `deleteLater()`（**不发**关闭事件），若只调它，`quitOnLastWindowClosed` 不会触发
        ⇒ 正在跑的 `run()` 事件循环会**永远不返回**。先 close 让事件循环按 Qt 的常规路径
        退出，再销毁 root（`close()` 本身是幂等的）。
        """
        try:
            self.root.native.close()
        except Exception:               # root 已释放 / 从未建立 ⇒ 无需关闭
            pass
        try:
            self.renderer.destroy()
        except Exception:               # destroy() 契约是幂等且不抛；真抛了也不该炸新手
            pass
