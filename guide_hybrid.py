# -*- coding: utf-8 -*-
"""ck1.0 新手引导 · Tk + PySide6 混合版（guide_hybrid.py）。

一句话
    同一个进程里：窗口外壳、分组标题、步骤导航、状态栏、「← 上一步 / 下一步 → / 完成」
    全部是 **Tkinter**（走本仓库的中立渲染层 `ck1_0/renderer`，父容器显式传入）；
    窗口下方那块彩色面板是**真的 PySide6** —— Qt 画像素、Qt 收事件、QSS 圆角渐变、
    QtCharts 环形图带动画。两套 UI 框架同时活着，并且真的在互相通信。

怎么把 Qt 塞进 Tk（本文件的核心技术，结论以真机实测为准）
    姿势 A（`QWindow.fromWinId` + `QWidget.createWindowContainer` + 屏幕坐标跟随）：
        实测会把 Tk 宿主 frame 的 HWND **重新挂到 Qt 容器窗口下面**，于是面板变成
        一个"浮"在屏幕上的独立顶层窗口：得自己跟随 Tk 移动/缩放、自己处理层级
        （Tk 主窗一被激活就可能盖住它），而且 Qt 用**逻辑像素**（本机 1.5 倍）、
        Tk 用**物理像素**，坐标要除一次 dpr 才对得上。实测抓屏时面板跑到窗口外。
    姿势 B（真子窗口）：先把 Qt 窗口 `show()` 出来拿到它的 HWND，再用 Win32
        `SetParent` 挂到 Tk 宿主 frame 的 HWND 下，样式改成 `WS_CHILD`。
        实测：面板**真的长在 Tk 窗口里** —— 随 Tk 窗口移动、随画布滚动、被 Tk 窗口
        裁剪、Tk 最小化时一起消失；位置交给 Windows 自己管，只需在 `<Configure>`
        时用 `SetWindowPos` 同步尺寸（Qt 的逻辑尺寸 = 物理尺寸 / dpr）。
    所以本文件**优先用 B**；B 不可用时退回 A（悬浮跟随，并在界面上如实标注），
    再不行就退化成「纯 Tk 界面 + 一句说明」。新手友好库的底线是**不崩、还能用**。

事件泵
    Qt 没有自己的 `exec()` 循环：Tk 的 `after(16, ...)` 反复调
    `QApplication.processEvents()`，Qt 的定时器（图表动画）、重绘、鼠标事件都靠这一泵。

三个开关
    python guide_hybrid.py               打开引导窗口（零配置，双击 bat 也行）
    python guide_hybrid.py --float-qt    诊断用：强制先试"悬浮跟随"姿势（默认先试真子窗口）
    python guide_hybrid.py --selftest    只建完整 Tk UI + Qt 对象，**不 show、不进 mainloop**，
                                         打印 `SELFTEST OK` 后 `sys.exit(0)`（无头也能过）
    python guide_hybrid.py --real-smoke  真平台建窗 + 截图（`_grab_window.py`）+
                                         打印 `REAL SMOKE OK` 后 `sys.exit(0)`

纪律
    * 只新增本文件与 `7-新手引导-混合.bat`，**不改仓库里任何既有文件**；
    * 界面文案全中文，只用字体安全符号（← → · ｜ ① ②），**不用彩色 emoji**
      —— Microsoft YaHei 画不出 emoji，会渲染成豆腐块（仓库教训）；
    * 零配置：从仓库根 `python guide_hybrid.py` 直接跑，不引入新的第三方依赖；
    * 复合控件（滑块 / 表格）的"入列单位"用中立契约的 `handle.outer`（接口合同），
      不再对内部的 `native` 调 `layout(...)`、也不再用 `native.master` 逃生口。
"""
import ctypes
import os
import sys
import time

# 零配置导入：允许从任意 cwd 用 `python guide_hybrid.py` 启动。
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# 运行模式必须在**创建 QApplication 之前**定下来：`QT_QPA_PLATFORM` 是 QApplication
# 构造时读的，晚一步设就没用了（与 `guide_qt.py` 同一套做法）。
_ARGV = set(sys.argv[1:])
# 诊断开关（可选）：强制先试"悬浮跟随"姿势，用来对比两种嵌入姿势的实测现象。
_FORCE_FLOAT = '--float-qt' in _ARGV
MODE = 'selftest' if '--selftest' in _ARGV else (
    'real-smoke' if '--real-smoke' in _ARGV else 'run')
if MODE == 'selftest':
    # 无头自检：没有屏幕也要能把 Tk UI 与 Qt 对象建完（只在本分支设，正常运行绝不设）。
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
elif MODE == 'real-smoke':
    # 真窗口取证要求真平台：显式清掉继承来的 offscreen 设置。
    os.environ.pop('QT_QPA_PLATFORM', None)

import tkinter as tk                                        # noqa: E402  混合版的"外壳"一侧

from ck1_0.renderer.base import Layout                     # noqa: E402
from gui.main_window import MainWindow                      # noqa: E402
from gui.widgets import _content_parent, _renderer_of       # noqa: E402

# PySide6 是"可选依赖"：没装就整块降级为纯 Tk 引导，绝不让 traceback 糊新手一脸。
_QT_IMPORT_ERROR = ''
try:
    from PySide6 import __version__ as QT_VERSION
    from PySide6.QtCore import QMargins, Qt, QTimer
    from PySide6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter,
                               QPen, QWindow)
    from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QFrame,
                                   QHBoxLayout, QLabel, QLineEdit, QPushButton, QSlider,
                                   QStackedWidget, QTableWidget, QTableWidgetItem,
                                   QVBoxLayout, QWidget)
    HAVE_QT = True
except Exception as _exc:                                   # ImportError / DLL 缺失 / ...
    HAVE_QT = False
    QT_VERSION = ''
    _QT_IMPORT_ERROR = str(_exc)

# QtCharts 也可能是单独缺席的，一样降级（图表面板退成"说明 + 按钮"，其余照常）。
_QTCHARTS_ERROR = ''
try:
    from PySide6.QtCharts import QChart, QChartView, QPieSeries
    HAVE_QTCHARTS = True
except Exception as _exc2:
    HAVE_QTCHARTS = False
    _QTCHARTS_ERROR = str(_exc2)

# ---------------------------------------------------------------------- #
# 常量（步骤结构 / 配色 / 文案与另外两版引导保持一致）
# ---------------------------------------------------------------------- #
_FONT = 'Microsoft YaHei'
_TITLE = 'ck1.0 · Tk + PySide6 混合新手引导'
# --real-smoke 按这个片段找真窗口。必须够长："ck1.0" 会同时命中启动器与另外两版引导。
_WINDOW_MARK = 'Tk + PySide6 混合'
_SHOT_NAME = '_guide_hybrid_shot.png'
_STEP_COUNT = 8
_PUMP_MS = 16                       # 事件泵节拍（约 60 帧/秒）

# Qt 面板的尺寸预算。Tk 用**物理像素**、Qt 用**逻辑像素**（本机 1.5 倍），
# 所以宿主 frame 的物理尺寸 = 逻辑尺寸 * dpr，再夹到上限里（别把窗口撑到屏幕外）：
#   * `_QT_LOGICAL_W/H` 是 Qt 面板**内容排版**用的逻辑尺寸；
#   * `_HOST_MAX_W/H`   是宿主 frame 的物理上限（窗口宽 / 屏幕高的现实约束）。
# 这样在 100% DPI 上不必留一大块空框，在 150% DPI 上又不会把 Qt 内容压扁。
_QT_LOGICAL_W, _QT_LOGICAL_H = 640, 300
_QT_LOGICAL_H_MAX = 360             # 面板逻辑高度的上限（再胖也不许无限长）
_HOST_MAX_W, _HOST_MAX_H = 960, 500
_HOST_W, _HOST_H = _HOST_MAX_W, _HOST_MAX_H   # 建 Tk 骨架时的初值，Qt 起来后按 dpr 重算
_WIN_W, _WIN_H_MIN = 1040, 700      # 窗口宽度 / 最小高度（物理像素）
_STEP_AREA_H = 200                  # Tk 步骤说明区的兜底高度（实际按 winfo_reqheight 量）
_QT_HINT_H = 30                     # Qt 区域里那行中文说明（物理像素）
_BODY_H = _STEP_AREA_H + _QT_HINT_H + _HOST_H + 12   # 内容区固定高度（pack_propagate(False)）

# 8 个步骤：编号 / 标题 / 副标题 / 正文，与 guide_tk.py、guide_qt.py 对齐。
STEPS = [
    ('欢迎', '认识混合版：两套 UI 框架同一个进程',
     '这一版上面是 Tkinter（窗口外壳、导航、状态栏），\n下面那块彩色面板是真的 PySide6。'),
    ('按钮与回调', 'Tk 按钮与 Qt 按钮并排',
     '同一个窗口里放两个框架的按钮：Tk 按钮走中立渲染层，\nQt 按钮走 Qt 自己的信号槽，两边都往同一条状态栏写字。'),
    ('输入框', 'Tk 输入框与 Qt 输入框',
     'Tk 的输入框在上面那一行，Qt 的输入框在彩色面板里；\n每敲一个字，Tk 状态栏都会立刻收到反馈。'),
    ('滑块与开关', '连续值与开关量',
     'Tk 滑块/开关给的是数值与布尔值；\nQt 那边的滑块/复选框一样把值送回 Tk 的状态栏。'),
    ('图表', '真 QtCharts 环形图',
     '彩色面板里的环形图是 QtCharts 画的，定时器每 120 毫秒推一次数据，\n切片自己会动。点 Tk 按钮换数据，动的是 Qt 的图。'),
    ('表格', 'Tk 表格与 Qt 表格',
     '两块表格来自两套框架：上面是 Tk 的中立表格，\n面板里是 Qt 的 QTableWidget。点 Qt 表格的行，Tk 状态栏会应答。'),
    ('换主题', '一次点击，两边一起换色',
     '点下面的按钮：Tk 的角色色表与 Qt 面板的 QSS 都由同一份调色板驱动，\n一次点击两边同时生效，不用重启窗口。'),
    ('完成', '回顾与下一步',
     '8 步走完了：左边 Tk 一直在跑自己的事件循环，\n右边 Qt 一直活在同一个进程里，靠 Tk 的 after 把 Qt 的事件泵起来。'),
]

# 两套配色：同一份调色板同时喂给 Tk（角色 → 颜色）与 Qt（QSS）。
_PALETTES = {
    'light': {
        'name': '浅色',
        'app_bg': '#eef1f6', 'card': '#ffffff', 'field': '#f7f9fc',
        'fg': '#1f2933', 'muted': '#6b7280',
        'accent': '#2f6fed', 'accent_dark': '#1f57c9', 'accent_fg': '#ffffff',
        'nav_bg': '#e3e8f0', 'border': '#cfd7e3', 'status_bg': '#dde3ec',
        'qt_grad_a': '#4d8df6', 'qt_grad_b': '#7b5cf0', 'qt_grad_fg': '#ffffff',
        'qt_slice_a': '#4d8df6', 'qt_slice_b': '#7b5cf0',
    },
    'dark': {
        'name': '深色',
        'app_bg': '#171d26', 'card': '#212936', 'field': '#151b24',
        'fg': '#eef2f7', 'muted': '#9aa7b8',
        'accent': '#4d8df6', 'accent_dark': '#3a76d8', 'accent_fg': '#ffffff',
        'nav_bg': '#2b3546', 'border': '#3d4859', 'status_bg': '#12171f',
        'qt_grad_a': '#3f6fd8', 'qt_grad_b': '#6b46d8', 'qt_grad_fg': '#ffffff',
        'qt_slice_a': '#63a4ff', 'qt_slice_b': '#a98bff',
    },
}

# Qt 环形图的数据（两套轮换），Tk 侧按钮换的是它。
_CHART_DATA = (
    (('基础控件', 30), ('输入与反馈', 24), ('图表可视化', 20), ('数据表格', 16), ('主题与动画', 10)),
    (('Tk 外壳', 26), ('Qt 面板', 34), ('事件泵', 14), ('图表动画', 18), ('主题联动', 8)),
)

# Qt 表格（QTableWidget）的数据。
_QT_TABLE_HEADERS = ('部分', '负责什么', '谁画的')
_QT_TABLE_ROWS = (
    ('Tkinter', '窗口外壳、步骤导航、状态栏', 'Tk'),
    ('PySide6', '彩色面板、按钮、输入框、滑块', 'Qt'),
    ('QtCharts', '环形图的切片与入场动画', 'Qt'),
    ('Win32', '把 Qt 窗口挂成 Tk 的子窗口', 'Windows'),
    ('事件泵', 'Tk 的 after 里调 Qt 的 processEvents', '两边'),
)

# Tk 侧表格的数据（中立 table 控件）。
_TK_TABLE_HEADERS = ['控件', '哪一侧', '交互方式']
_TK_TABLE_ROWS = [
    [('标签 label', 'Tk（中立层）', '只看不点'),
     ('按钮 button', 'Tk（中立层）', '鼠标左键单击'),
     ('输入框 input', 'Tk（中立层）', '键盘输入')],
    [('QPushButton', 'Qt（真 PySide6）', '点击发信号'),
     ('QLineEdit', 'Qt（真 PySide6）', '输入即回显'),
     ('QTableWidget', 'Qt（真 PySide6）', '点行选中')],
]

# Win32 常量（真子窗口嵌入用；只在 Windows 分支里被读到）。
_GWL_STYLE = -16
_WS_CHILD = 0x40000000
_WS_POPUP = 0x80000000
_WS_CAPTION = 0x00C00000
_SWP_NOZORDER = 0x0004
_SWP_FRAMECHANGED = 0x0020
_SWP_NOACTIVATE = 0x0010
_SWP_SHOWWINDOW = 0x0040
_SWP_NOSENDCHANGING = 0x0400
# 稳态尺寸同步用的标志：**故意不含 `SWP_FRAMECHANGED`**。
# 实测（真机、dpr=1.5、宿主 960x354）：带 FRAMECHANGED 去 SetWindowPos，Qt 会重算一遍窗口几何，
# 把自己按尺寸提示撑回 960x471（Qt 日志：`Unable to set geometry 960x354 … Resulting geometry:
# 960x471`），于是 WS_CHILD 被宿主裁掉 117px；去掉 FRAMECHANGED 后同一调用立刻得到 960x354。
# 需要 FRAMECHANGED 的只有"样式改成 WS_CHILD 那一次"，见 `_embed_as_child_window`。
_SWP_SYNC = _SWP_NOZORDER | _SWP_NOACTIVATE | _SWP_SHOWWINDOW | _SWP_NOSENDCHANGING


def _s32(value):
    """把无符号 32 位样式值转成 `SetWindowLongW` 要的有符号整数（否则 ctypes 会 Overflow）。"""
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value >= 0x80000000 else value


def _qt_qss(p):
    """按调色板生成 Qt 面板的 QSS：圆角、渐变、按钮三态、滑块、表头都在这里。

    用 `%` 而不是 `str.format`：QSS 里遍地是花括号，`%` 写法不用把每个括号都写成双份。
    """
    return """
    QWidget#panelRoot { background: %(card)s; }
    QLabel { color: %(fg)s; font-family: "Microsoft YaHei"; font-size: 13px; }
    QLabel#panelTitle { font-size: 17px; font-weight: bold; color: %(accent)s; }
    QLabel#panelHint { color: %(muted)s; font-size: 12px; }
    QLabel#panelStep { color: %(muted)s; font-size: 12px; }
    QLabel#onGrad { color: %(qt_grad_fg)s; font-size: 15px; font-weight: bold; }
    QLabel#onGradSmall { color: %(qt_grad_fg)s; font-size: 12px; }
    QFrame#gradCard {
        border-radius: 16px;
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                    stop:0 %(qt_grad_a)s, stop:1 %(qt_grad_b)s);
    }
    QFrame#softCard {
        border-radius: 12px;
        background: %(field)s;
        border: 1px solid %(border)s;
    }
    QPushButton {
        background: %(accent)s; color: %(accent_fg)s; border: none;
        border-radius: 9px; padding: 8px 18px;
        font-family: "Microsoft YaHei"; font-size: 13px;
    }
    QPushButton:hover { background: %(accent_dark)s; }
    QPushButton:pressed { background: %(accent_dark)s; padding-top: 9px; }
    QPushButton#ghost { background: %(nav_bg)s; color: %(fg)s; }
    QPushButton#ghost:hover { background: %(border)s; }
    QLineEdit {
        background: %(field)s; color: %(fg)s; border: 1px solid %(border)s;
        border-radius: 9px; padding: 7px 12px;
        font-family: "Microsoft YaHei"; font-size: 13px;
    }
    QLineEdit:focus { border: 1px solid %(accent)s; }
    QCheckBox { color: %(fg)s; font-family: "Microsoft YaHei"; font-size: 13px; spacing: 8px; }
    QSlider::groove:horizontal { height: 6px; background: %(border)s; border-radius: 3px; }
    QSlider::sub-page:horizontal { background: %(accent)s; border-radius: 3px; }
    QSlider::handle:horizontal {
        width: 16px; margin: -6px 0; border-radius: 8px; background: %(accent)s;
    }
    QTableWidget {
        background: %(card)s; color: %(fg)s; gridline-color: %(border)s;
        border: 1px solid %(border)s; border-radius: 9px;
        font-family: "Microsoft YaHei"; font-size: 12px;
    }
    QTableWidget::item:selected { background: %(accent)s; color: %(accent_fg)s; }
    QHeaderView::section {
        background: %(nav_bg)s; color: %(fg)s; border: none; padding: 5px;
        font-family: "Microsoft YaHei"; font-size: 12px;
    }
    """ % p


class GuideHybrid:
    """Tk + PySide6 8 步混合引导。

    设计要点:
      * Tk 负责外壳：头部说明 / 步骤条 / 内容区 / 底部导航 / 窗口级状态栏；
      * 8 个步骤各自是**常驻**的 Tk 容器（切步只 pack / pack_forget），
        输入框里敲的字、滑块位置、表格选中项来回切步不会丢；
      * 内容区底部固定留出一块"Qt 区"（见 `_relayout_qt_area`），里面是**一整块真 Qt
        面板**（QStackedWidget 8 页，随步骤换页）—— 面板位置固定，切步时不会跳；
      * Qt 与 Tk 双向通信：Qt 的按钮/输入框/表格把结果写进 **Tk 状态栏**；
        Tk 的按钮也能反过来改 **Qt 图表**的数据。
    """

    def __init__(self):
        self.app = MainWindow(_TITLE, _WIN_W, _WIN_H_MIN)
        self.app.center_window()
        self.r = _renderer_of(self.app)
        self.content = _content_parent(self.app)

        self.step = 0
        self.palette_name = 'light'
        self.palette = _PALETTES[self.palette_name]

        self._themed = []               # [原生控件, 角色]：换主题时按角色统一重刷
        self._nav_buttons = []
        self._step_frames = []

        # 演示状态
        self.tk_click_count = 0
        self.chart_variant = 0
        self.table_variant = 0
        self.tk_table = None

        # Qt 一侧的句柄与状态
        self._qt_app = None
        self._qt_holder = None          # 真 Qt 面板的顶层窗口（嵌入后成为 Tk 的子窗口）
        self._qt_stack = None
        self._qt_step_label = None
        self._qt_theme_label = None
        self._qt_echo = None
        self._qt_click_label = None
        self._qt_slider_label = None
        self._qt_toggle_label = None
        self._qt_table = None
        self._qt_chart = None
        self._qt_series = None
        self._qt_chart_label = None
        self._qt_timer = None
        self._qt_phase = 0.0
        self._qt_host = None            # Tk 宿主 frame（原生 tk.Frame）
        self._qt_host_hwnd = 0
        self._qt_holder_hwnd = 0
        self._qt_embed_mode = '未尝试'
        self._qt_embed_detail = ''
        self._qt_mismatch_streak = 0    # 连续多少次看门狗发现"Qt 窗口 != 宿主 frame"
        self._qt_absorbed = False       # 是否已经用过"把宿主撑高"的兜底
        self._user32 = None
        self._pump_tick = 0
        self._pump_running = False

        self._build()
        self._apply_palette()
        self.goto(0)
        self._start_pump()

    # ------------------------------------------------------------------ #
    # 搭 Tk 骨架
    # ------------------------------------------------------------------ #
    def _build(self):
        self._build_header()
        self._build_navbar()
        self._build_body()
        self._build_footer()
        self.status_handle, self.set_status = self.app.create_status_bar(
            '就绪：左侧步骤可点，下面那块彩色面板是真的 PySide6')
        self._themed.append([self.status_handle.native, 'status'])
        # Qt 面板必须在 Tk 宿主 frame 建好之后再建，最后才尝试嵌入。
        self._build_qt_panel()
        self._embed_qt()

    def _build_header(self):
        head = self.r.container(self.content, Layout.pack(fill='x'))
        self._themed.append([head.native, 'card'])
        self._label(head, 'ck1.0 新手引导 · 混合版', role='title', size=22, bold=True,
                    pady=(14, 2))
        self._label(head, '八步走完常用控件：窗口外壳与导航是 Tkinter，内容面板是真的 PySide6',
                    role='muted', size=10, pady=(0, 4))
        self._label(head, '这一版：窗口和按钮是 Tkinter，彩色面板是真的 PySide6'
                          '（同一个进程里两套 UI 框架同时活着）。',
                    role='hi', size=10, bold=True, wrap=980, pady=(0, 12))

    def _build_navbar(self):
        bar = self.r.container(self.content, Layout.pack(fill='x'))
        self._themed.append([bar.native, 'nav_bar'])
        for i, (title, _sub, _text) in enumerate(STEPS):
            # 闭包陷阱：循环变量 i 必须在默认参数里定格，否则 8 个按钮都会跳到第 8 步。
            handle = self._button(bar, '%d %s' % (i + 1, title),
                                  (lambda idx: (lambda: self.goto(idx)))(i),
                                  role='nav', width=10, size=9, bold=False,
                                  pack=Layout.pack(side='left', padx=2, pady=6))
            self._nav_buttons.append(handle.native)

    def _build_body(self):
        body = self.r.container(self.content, Layout.pack(fill='both', expand=True))
        native = body.native
        self.body = body
        self._themed.append([native, 'card'])
        # 逃生口：中立契约没有"固定高度容器"，而切步时下面的 Qt 面板不该上下跳
        # ⇒ 用 pack_propagate(False) 把内容区高度钉住（与 guide_tk.py 同一手法）。
        native.configure(height=_BODY_H)
        native.pack_propagate(False)

        # 先摆 Qt 区域（side='bottom'），剩下的高度留给 8 个步骤容器。
        self._build_qt_area(body)

        builders = [self._step_welcome, self._step_button, self._step_input,
                    self._step_slider, self._step_chart, self._step_table,
                    self._step_theme, self._step_done]
        for i, build in enumerate(builders):
            step = self.r.container(body, None)
            step.native.pack_forget()
            self._themed.append([step.native, 'card'])
            self._step_frames.append(step)
            self._step_heading(step, i)
            build(step)

    def _build_qt_area(self, body):
        """Qt 区域的 Tk 侧容器：一行说明 + 一块空的宿主 frame。

        宿主 frame 是本文件的"接口"：Qt 面板最终会变成它的一个 Win32 子窗口。
        它自己不放 Tk 子控件（放了也看不见 —— Qt 窗口会盖在整块区域上），
        只有降级时才会往里面塞一行中文说明。
        """
        area = self.r.container(body, None)
        area.native.configure(height=_QT_HINT_H + _HOST_H + 12)
        area.native.pack(side='bottom', fill='x')
        area.native.pack_propagate(False)
        self._themed.append([area.native, 'card'])
        self._qt_area = area.native

        self._qt_hint = self._label(area, '下面这块彩色面板是真的 PySide6：Qt 画像素、'
                                          'Qt 收事件、QSS 圆角渐变、QtCharts 动画；'
                                          '包围它的窗口、按钮、状态栏都是 Tkinter。',
                                    role='muted', size=10, wrap=980, pady=(4, 0))
        # 宿主 frame：Tk 里的一块"空格"，Qt 面板正好嵌进它里面。
        # 它是本文件里**唯一**不走中立渲染层的 Tk 控件，而且是有意的：它不是"控件"，
        # 而是一块**交给 Qt 用的宿主窗口**（任务书的姿势就是 `tk.Frame(...)` + `winfo_id()`），
        # 中立层没有、也不该有"给我一个原生 HWND"的 API。它的子控件只有一个降级说明标签。
        self._qt_host = tk.Frame(area.native, width=_HOST_W, height=_HOST_H,
                                 bg=self.palette['nav_bg'], highlightthickness=0)
        self._qt_host.pack(anchor='w', padx=26, pady=(4, 6))
        self._qt_host.pack_propagate(False)
        self._qt_host.bind('<Configure>', lambda _e: self._sync_qt_geometry())
        # 降级时才显示的说明标签（嵌入成功时它一直藏着）：这时界面本来就已经是纯 Tk 了，
        # 直接用 tk.Label 最直白，也让"混合版里两侧都真的在用"这件事在代码里看得见。
        self._qt_notice = tk.Label(self._qt_host, text='', justify='left', anchor='w',
                                   font=(_FONT, 11), wraplength=_HOST_MAX_W - 60)
        self._themed.append([self._qt_notice, 'field'])

    def _relayout_qt_area(self, host_w, host_h):
        """按 dpr 重算宿主 frame 的物理尺寸，并重新分配内容区高度（Tk 侧整体重排一次）。

        步骤区的高度**按实际需要量**（`winfo_reqheight`），不用写死的常数：
        Tk 的字号按"点"算，DPI 越高像素越大（144 DPI 下 11pt 就是 22px），
        写死高度会在高 DPI 上把最后一行控件裁掉。
        """
        host_h = max(80, int(host_h))
        self._qt_host.configure(width=max(320, int(host_w)), height=host_h)
        # 那一行说明在高 DPI 下会折成两行（10pt 在 144 DPI 就是 20px）⇒ 高度也得量出来，
        # 否则它会把下面最晚 pack 的宿主 frame 挤矮（实测：要 236 只给到 204）。
        hint_h = _QT_HINT_H
        try:
            hint_h = int(self._qt_hint.native.winfo_reqheight()) + 4
        except Exception:
            pass
        area_h = hint_h + host_h + 12
        self._qt_area.configure(height=area_h)
        try:
            self.app.root.update_idletasks()
        except Exception:
            pass
        step_need = _STEP_AREA_H
        try:
            step_need = max([f.native.winfo_reqheight() for f in self._step_frames]
                            or [_STEP_AREA_H])
        except Exception:
            pass
        self.body.native.configure(height=step_need + area_h)
        try:
            self.app.root.update_idletasks()
        except Exception:
            pass
        self._fit_window_height()

    def _fit_window_height(self):
        """把窗口高度撑到"内容够用"为止（最多留 80px 给任务栏/标题栏）。

        为什么要动态撑：Qt 面板的物理高度随 dpr 变、Tk 的字体随 DPI 变，
        两边的需要量都不是常数；与其写死一个在别人机器上会被裁的高度，
        不如量出内容需要多少就撑到多少（超出屏幕的部分仍可滚动查看）。
        """
        try:
            need = self.content.native.winfo_reqheight() + 10
            screen_h = self.app.root.winfo_screenheight()
            want = int(min(max(_WIN_H_MIN, need), max(_WIN_H_MIN, screen_h - 80)))
            self.app.root.geometry('%dx%d' % (_WIN_W, want))
            self.app.center_window()
        except Exception:
            pass

    def _show_qt_notice(self, text):
        """嵌入失败时的优雅降级：在宿主格里显示一句中文说明，引导照常可用。"""
        try:
            self._qt_notice.configure(text=text)
            self._qt_notice.pack(fill='both', expand=True, padx=14, pady=14)
            self._relayout_qt_area(_HOST_MAX_W, 120)
        except Exception:
            pass

    def _build_footer(self):
        foot = self.r.container(self.content, Layout.pack(fill='x'))
        self._themed.append([foot.native, 'card'])
        self.prev_handle = self._button(foot, '← 上一步', lambda: self.step_delta(-1),
                                        role='ghost', width=10,
                                        pack=Layout.pack(side='left', padx=(26, 6), pady=10))
        self.next_handle = self._button(foot, '下一步 →', lambda: self.step_delta(1),
                                        role='primary', width=10,
                                        pack=Layout.pack(side='left', padx=6, pady=10))
        self.done_handle = self._button(foot, '完成', self._finish, role='primary', width=8,
                                        pack=Layout.pack(side='left', padx=6, pady=10))
        self.progress_handle = self.r.progress(foot, _STEP_COUNT, width=200)
        # progress() 自己把内部 Frame 按整个宽度摆好；这里重新摆成左侧流，与三个按钮同一行。
        # `layout()` 作用于复合结构的 **Frame**（`TkProgressHandle` 把 frame 交给 `TkHandle`），
        # 而 `native` 是里面那块可见的 Canvas —— 与 `slider`/`table` 的结构同源，但进度条的
        # 外层 Frame **没有**暴露成句柄（`outer` 自反），所以下面给它上色只能走 `native.master`
        # 这个**颜色**逃生口（不是摆放逃生口：摆放用的是 `layout()`）。
        self.progress_handle.layout(Layout.pack(side='left', padx=(18, 8), pady=10))
        self._themed.append([self.progress_handle.native.master, 'card'])
        self._themed.append([self.progress_handle.native, 'card'])
        self.progress_text = self._label(foot, '第 1 / 8 步', role='muted', size=10,
                                         side='left', padx=6, pady=10)

    # ------------------------------------------------------------------ #
    # 每一步的 Tk 侧内容
    # ------------------------------------------------------------------ #
    def _step_heading(self, parent, index):
        """一行标题（标题与副标题合并）：Tk 侧要留出高度给下面的 Qt 面板。"""
        title, sub, _text = STEPS[index]
        self._label(parent, '第 %d 步 · %s —— %s' % (index + 1, title, sub), role='title',
                    size=14, bold=True, pady=(8, 2))

    def _step_welcome(self, parent):
        self._label(parent, STEPS[0][2], role='text', size=11, wrap=960, pady=(0, 4))
        row = self._row(parent, pady=(0, 2))
        self._button(row, '开始吧 →', lambda: self.goto(1), role='primary', width=12,
                     pack=Layout.pack(side='left', padx=(0, 10), pady=4))
        self._label(row, 'Tk 窗口里长着一块真 Qt 面板 —— 点下面的步骤条翻页看',
                    role='muted', size=10, side='left', padx=0, pady=4)

    def _step_button(self, parent):
        self._label(parent, STEPS[1][2], role='text', size=11, wrap=960, pady=(0, 2))
        row = self._row(parent, pady=(0, 2))
        self._button(row, '我是 Tk 按钮', self._on_tk_click, role='primary', width=14,
                     pack=Layout.pack(side='left', padx=(0, 10), pady=4))
        self.tk_click_label = self._label(row, 'Tk 按钮：还没有被点过', role='muted', size=10,
                                          side='left', padx=0, pady=4)

    def _step_input(self, parent):
        self._label(parent, STEPS[2][2], role='text', size=11, wrap=960, pady=(0, 2))
        row = self._row(parent, pady=(0, 2))
        self.input_handle = self.r.input(row, hint='在这里输入你的名字', width=26,
                                         family=_FONT, size=11)
        # 输入框句柄包的就是 Entry 本身 ⇒ 直接 layout 安全（pack 默认居中，要显式靠左）。
        self.input_handle.layout(Layout.pack(side='left', padx=(0, 10), pady=4))
        self._themed.append([self.input_handle.native, 'field'])
        self._button(row, '填入示例文本', self._fill_sample, role='ghost', width=12,
                     pack=Layout.pack(side='left', padx=(0, 10), pady=4))
        self.echo_label = self._label(row, 'Tk 回显：（还没有输入）', role='muted', size=10,
                                      side='left', padx=0, pady=4)
        # 中立 `Value.on_change`：用户按键与程序化 set() 都会回调。
        self.input_handle.value.on_change(self._on_typed)

    def _step_slider(self, parent):
        self._label(parent, STEPS[3][2], role='text', size=11, wrap=960, pady=(0, 2))
        self.slider_handle = self.r.slider(parent, from_=0, to=100, default=40, resolution=1,
                                           width=320, on_change=self._on_volume)
        # 滑块是**复合控件**（外层 Frame + 标签 + ttk.Scale + 数值）：句柄的 `native` 指向内部那个
        # Scale，对它 layout 会把滑轨从"标签 + 滑轨 + 数值"这一行里拆出来（三个引导都踩过）。
        # 中立契约现在给了 `handle.outer`（接口合同 /）—— 排它、刷色都对外层容器。
        self.slider_handle.outer.layout(Layout.pack(anchor='w', padx=26, pady=0))
        self._themed.append([self.slider_handle.outer.native, 'card'])
        row = self._row(parent, pady=(0, 2))
        self.volume_label = self._label(row, 'Tk 滑块：40', role='text', size=10,
                                        side='left', padx=0, pady=2)
        self.toggle_handle = self.r.toggle(row, 'Tk 开关：静音提示', default=False,
                                           command=self._on_toggle)
        self.toggle_handle.layout(Layout.pack(side='left', padx=(16, 8)))
        self.toggle_label = self._label(row, '开关状态：关', role='muted', size=10,
                                        side='left', padx=0, pady=2)

    def _step_chart(self, parent):
        self._label(parent, STEPS[4][2], role='text', size=11, wrap=960, pady=(0, 2))
        row = self._row(parent, pady=(0, 2))
        self._button(row, '换一组数据（Tk 按钮）', self._regen_chart, role='ghost', width=18,
                     pack=Layout.pack(side='left', padx=(0, 10), pady=4))
        self.chart_label = self._label(row, 'Qt 图表当前数据：%s' % self._chart_text(0),
                                       role='muted', size=10, side='left', padx=0, pady=4)

    def _step_table(self, parent):
        self._label(parent, STEPS[5][2], role='text', size=11, wrap=960, pady=(0, 2))
        row = self._row(parent, pady=(0, 2))
        self._button(row, '换一批数据（Tk 表格）', self._regen_table, role='ghost', width=18,
                     pack=Layout.pack(side='left', padx=(0, 10), pady=4))
        self.table_label = self._label(row, 'Tk 表格选中：（还没有选）', role='muted', size=10,
                                       side='left', padx=0, pady=4)
        # 表格句柄包的是内部 ttk.Treeview，外框（带滚动条）是它的 master。
        self.tk_table = self.r.table(parent, _TK_TABLE_HEADERS, rows=_TK_TABLE_ROWS[0],
                                     height=1, on_select=self._on_row,
                                     column_widths=(150, 190, 190))
        # 同滑块：表格也是复合控件（外层 Frame + Treeview + 纵向滚动条），排外层容器。
        self.tk_table.outer.layout(Layout.pack(anchor='w', padx=26, pady=(0, 2)))
        self._themed.append([self.tk_table.outer.native, 'card'])
        self._themed.append([self.tk_table.native, 'tree'])

    def _step_theme(self, parent):
        self._label(parent, STEPS[6][2], role='text', size=11, wrap=960, pady=(0, 2))
        row = self._row(parent, pady=(0, 2))
        self._button(row, '浅色主题', lambda: self._set_palette('light'), role='primary',
                     width=10, pack=Layout.pack(side='left', padx=(0, 8), pady=4))
        self._button(row, '深色主题', lambda: self._set_palette('dark'), role='primary',
                     width=10, pack=Layout.pack(side='left', padx=0, pady=4))
        self.theme_label = self._label(row, '当前主题：浅色（Tk + Qt 一起换）', role='hi',
                                       size=10, bold=True, side='left', padx=12, pady=4)

    def _step_done(self, parent):
        self._label(parent, STEPS[7][2], role='text', size=11, wrap=960, pady=(0, 2))
        row = self._row(parent, pady=(0, 2))
        self._button(row, '重新开始', lambda: self.goto(0), role='ghost', width=10,
                     pack=Layout.pack(side='left', padx=(0, 8), pady=4))
        self._button(row, '退出引导', self.close, role='primary', width=10,
                     pack=Layout.pack(side='left', padx=0, pady=4))
        self._label(row, '想继续探索：python main.py 看完整演示，python launcher.py 挑入口',
                    role='muted', size=10, side='left', padx=12, pady=4)

    # ------------------------------------------------------------------ #
    # 建真 Qt 面板（QStackedWidget 8 页，随步骤换页）
    # ------------------------------------------------------------------ #
    def _build_qt_panel(self):
        """建好 Qt 对象（**不 show**）：QApplication 进程级复用 + 面板 + 8 页内容 + 动画定时器。"""
        if not HAVE_QT:
            self._qt_embed_mode = '已降级：纯 Tk'
            self._qt_embed_detail = '没装 PySide6（%s）' % _QT_IMPORT_ERROR
            print('没找到 PySide6，本次退化成「纯 Tk 引导」。装它的命令是：pip install PySide6')
            self._show_qt_notice('当前环境没有 PySide6，所以这块面板画不出来。\n'
                                 '引导的其余部分照常可用 —— 装好 PySide6 再运行本文件即可看到它。')
            return
        try:
            self._qt_app = QApplication.instance() or QApplication([])
            holder = QWidget()
            holder.setObjectName('panelRoot')
            # 无边框 + 工具窗口：不要标题栏、不在任务栏留按钮、不抢焦点。
            # **故意不加** `WindowDoesNotAcceptFocus`：那样会带上 WS_EX_NOACTIVATE，
            # 面板里的 QLineEdit 就永远拿不到键盘焦点（点进去也打不了字）。
            holder.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
            # 出现时不抢焦点（否则启动那一下会把焦点从 Tk 窗口夺走）；
            # 这不影响"点进来以后能用键盘"：WA_ShowWithoutActivating 只管 show() 那一次。
            holder.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            holder.setMinimumSize(0, 0)     # 让宿主 frame 的尺寸说了算（不被布局最小尺寸顶住）
            root = QVBoxLayout(holder)
            root.setContentsMargins(14, 10, 14, 10)
            root.setSpacing(6)

            head = QHBoxLayout()
            title = QLabel('真的 PySide6 面板')
            title.setObjectName('panelTitle')
            head.addWidget(title)
            head.addStretch(1)
            self._qt_step_label = QLabel('第 1 步 / 共 8 步')
            self._qt_step_label.setObjectName('panelStep')
            head.addWidget(self._qt_step_label)
            root.addLayout(head)

            self._qt_stack = QStackedWidget()
            self._qt_stack.setMinimumSize(0, 0)
            for build in (self._qt_page_welcome, self._qt_page_button, self._qt_page_input,
                          self._qt_page_slider, self._qt_page_chart, self._qt_page_table,
                          self._qt_page_theme, self._qt_page_done):
                page = build()
                page.setMinimumSize(0, 0)
                self._qt_stack.addWidget(page)
            root.addWidget(self._qt_stack, 1)
            self._qt_holder = holder

            # 宿主 frame 的物理尺寸按 dpr 折算（Tk 物理像素 = Qt 逻辑像素 * dpr）：
            # 100% DPI 上不留空框，150% DPI 上也不把 Qt 内容压扁。
            dpr = self._qt_dpr()
            # 高度取 Qt **自己算出来的"舒服高度"**（真字体下 ≈ 330 逻辑像素）：5 行图例、
            # 5 行表格这类内容的真实尺寸比拍脑袋的常数大，用 sizeHint 才不会被它自家的
            # QChartView / 布局裁掉半行（实测：写死 236 逻辑像素时环形图图例被裁到只剩两行半）。
            want_h = _QT_LOGICAL_H
            try:
                want_h = max(_QT_LOGICAL_H,
                             min(_QT_LOGICAL_H_MAX, int(holder.sizeHint().height())))
            except Exception:
                pass
            host_w = min(_HOST_MAX_W, max(_QT_LOGICAL_W, int(round(_QT_LOGICAL_W * dpr))))
            host_h = min(_HOST_MAX_H, max(want_h, int(round(want_h * dpr))))
            self._relayout_qt_area(host_w, host_h)

            # 动画：Qt 自己的定时器，由 Tk 的事件泵推动（processEvents 会派发 Qt 定时器）。
            self._qt_timer = QTimer()
            self._qt_timer.setInterval(120)
            self._qt_timer.timeout.connect(self._qt_anim_tick)
            self._qt_timer.start()
            self._qt_apply_palette()        # 先上好 QSS，再让它出现在屏幕上（免得闪一下白底）
            self._qt_embed_mode = '已建对象（尚未嵌入）'
        except Exception as exc:            # 建 Qt 对象就失败：整块降级，但引导照常可用
            # 注意：Qt 控件没了以后，之前存下的 Python 包装对象就成了"悬空引用"
            # （再碰它会抛 libshiboken 的 RuntimeError）⇒ 这里必须一并清干净。
            self._qt_holder = None
            self._qt_stack = None
            self._qt_step_label = None
            self._qt_theme_label = None
            self._qt_echo = None
            self._qt_click_label = None
            self._qt_slider_label = None
            self._qt_toggle_label = None
            self._qt_table = None
            self._qt_chart = None
            self._qt_series = None
            self._qt_chart_label = None
            self._qt_timer = None
            self._qt_embed_mode = '已降级：纯 Tk'
            self._qt_embed_detail = 'Qt 对象创建失败：%s' % exc
            print('PySide6 对象创建失败，本次退化成「纯 Tk 引导」：%s' % exc)
            self._show_qt_notice('PySide6 对象创建失败，这块面板画不出来。\n'
                                 '引导的其余部分照常可用：%s' % exc)

    def _qt_page(self, title, hint):
        """一页的通用骨架：标题 + 说明，返回 (page, layout) 让调用方继续加控件。"""
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(4, 6, 4, 4)
        lay.setSpacing(8)
        label = QLabel(title)
        label.setObjectName('panelTitle')
        lay.addWidget(label)
        sub = QLabel(hint)
        sub.setObjectName('panelHint')
        sub.setWordWrap(True)
        lay.addWidget(sub)
        return page

    def _qt_page_welcome(self):
        page = self._qt_page('欢迎来到 Qt 这一侧',
                             '这块面板不是 Tk 画的：圆角、渐变、字号、按钮三态全部来自 Qt 的 QSS。')
        lay = page.layout()
        card = QFrame()
        card.setObjectName('gradCard')
        card.setMinimumHeight(86)
        inner = QVBoxLayout(card)
        inner.setContentsMargins(18, 14, 18, 14)
        line1 = QLabel('同一个进程，两套 UI 框架')
        line1.setObjectName('onGrad')
        line2 = QLabel('Tkinter 管窗口与导航；PySide6 管这块彩色面板。')
        line2.setObjectName('onGradSmall')
        inner.addWidget(line1)
        inner.addWidget(line2)
        lay.addWidget(card)
        lay.addStretch(1)
        return page

    def _qt_page_button(self):
        page = self._qt_page('Qt 按钮与信号槽',
                             '点下面的 Qt 按钮：回调发生在 Qt 的信号槽里，结果写进 Tk 的状态栏。')
        lay = page.layout()
        self._qt_click_label = QLabel('Qt 按钮：还没有被点过')
        lay.addWidget(self._qt_click_label)
        row = QHBoxLayout()
        btn = QPushButton('我是 Qt 按钮')
        btn.clicked.connect(self._qt_on_button)
        row.addWidget(btn)
        btn2 = QPushButton('让 Tk 按钮计数 +1')
        btn2.setObjectName('ghost')
        btn2.clicked.connect(self._on_tk_click)     # Qt 反过来调 Tk 侧的槽
        row.addWidget(btn2)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(1)
        return page

    def _qt_page_input(self):
        page = self._qt_page('Qt 输入框（QLineEdit）',
                             '在 Qt 的输入框里打字：每次 textChanged 都会同步到 Tk 的状态栏。')
        lay = page.layout()
        self._qt_line = QLineEdit()
        self._qt_line.setPlaceholderText('在 Qt 输入框里输入点什么…')
        self._qt_line.textChanged.connect(self._qt_on_text)
        lay.addWidget(self._qt_line)
        self._qt_echo = QLabel('Qt 回显：（还没有输入）')
        lay.addWidget(self._qt_echo)
        lay.addStretch(1)
        return page

    def _qt_page_slider(self):
        page = self._qt_page('Qt 滑块与复选框',
                             'QSlider 给数值、QCheckBox 给布尔值 —— 两个信号都接到 Tk 的状态栏。')
        lay = page.layout()
        self._qt_slider_label = QLabel('Qt 滑块：40')
        lay.addWidget(self._qt_slider_label)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(40)
        slider.valueChanged.connect(self._qt_on_slider)
        lay.addWidget(slider)
        self._qt_toggle_label = QLabel('Qt 复选框：未勾选')
        lay.addWidget(self._qt_toggle_label)
        box = QCheckBox('启用强调色（勾一下试试）')
        box.toggled.connect(self._qt_on_toggle)
        lay.addWidget(box)
        lay.addStretch(1)
        return page

    def _qt_page_chart(self):
        page = self._qt_page('真 QtCharts 环形图',
                             '切片每 120 毫秒由 QTimer 推一次数据，动画与重绘都在 Qt 里完成。')
        lay = page.layout()
        if HAVE_QTCHARTS:
            try:
                series = QPieSeries()
                series.setHoleSize(0.45)        # 中间挖空 ⇒ 环形
                for name, value in _CHART_DATA[0]:
                    # 图例只放名字、不放数值（数值在 Tk 那行"当前数据"里逐项列全了）：
                    # 5 行图例在面板里本来就不宽裕，短一点才不会被自家 view 裁掉半行。
                    piece = series.append(name, value)
                    piece.setLabelVisible(False)
                chart = QChart()
                chart.addSeries(series)
                chart.setBackgroundVisible(False)
                chart.setPlotAreaBackgroundVisible(False)
                # QtCharts 默认给图表留 ~29 逻辑像素的四周外边距，在小面板里那是"要命的"：
                # 实测 604x136 的画布只剩 plotArea 36 高（环形半径 ≈18），看着就是个小圈。
                chart.setMargins(QMargins(0, 0, 0, 0))
                chart.legend().setVisible(True)
                # 图例放**底边横排**而不是右边竖排：5 条数据竖着排会超出面板高度，
                # 被 QChartView 自己裁掉最后两条（实测：右边竖排只显示得下 3 条）。
                chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
                chart.legend().setFont(QFont(_FONT, 8))     # 字号收小一点，横排一行的宽度够用
                # **不开** QtCharts 自带的系列动画：我们的 QTimer 每 120ms 改一次切片值，
                # 若同时开着系列动画，每次改值都会重启一遍入场动画 ⇒ 饼图长期停在
                # "刚展开一半"的状态（实拍：环形被画成一小段弧）。关掉它，改值即时生效，
                # 由定时器做出连续、确定的"呼吸"效果，截图与肉眼看到的都是一整个环。
                chart.setAnimationOptions(QChart.AnimationOption.NoAnimation)
                view = QChartView(chart)
                view.setRenderHint(QPainter.RenderHint.Antialiasing)
                view.setFrameShape(QFrame.Shape.NoFrame)
                view.setStyleSheet('background: transparent;')
                view.setMinimumHeight(70)
                lay.addWidget(view, 1)
                self._qt_chart, self._qt_series = chart, series
            except Exception as exc:            # 图表是加分项：画不出来也不该炸整块面板
                note = 'QtCharts 画图失败：%s' % exc
                lay.addWidget(QLabel(note))
                print(note)
        else:
            lay.addWidget(QLabel('当前环境没有 QtCharts（%s），这一页只保留按钮演示。'
                                 % _QTCHARTS_ERROR))
        row = QHBoxLayout()
        # 这行标签必须**短**且允许换行：QLabel 的最小宽度等于整行文字宽度，
        # 长文案会把布局的最小宽度顶到 800 多（实测 896），把图表挤扁。
        self._qt_chart_label = QLabel('当前数据：第 1 组')
        self._qt_chart_label.setObjectName('panelHint')
        self._qt_chart_label.setWordWrap(True)
        row.addWidget(self._qt_chart_label)
        row.addStretch(1)
        btn = QPushButton('换一组数据（Qt 按钮）')
        btn.clicked.connect(self._regen_chart)
        row.addWidget(btn)
        lay.addLayout(row)
        return page

    def _qt_page_table(self):
        page = self._qt_page('真 Qt 表格（QTableWidget）',
                             '点任意一行：选中事件由 Qt 捕获，结果同样写进 Tk 的状态栏。')
        lay = page.layout()
        table = QTableWidget(len(_QT_TABLE_ROWS), len(_QT_TABLE_HEADERS))
        table.setHorizontalHeaderLabels(list(_QT_TABLE_HEADERS))
        for row, values in enumerate(_QT_TABLE_ROWS):
            for col, value in enumerate(values):
                table.setItem(row, col, QTableWidgetItem(value))
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setStretchLastSection(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setMinimumHeight(80)
        table.itemSelectionChanged.connect(self._qt_on_table_row)
        lay.addWidget(table, 1)
        self._qt_table = table
        return page

    def _qt_page_theme(self):
        page = self._qt_page('换主题：Qt 的 QSS 跟着 Tk 一起换',
                             '下面两个按钮是 Qt 按钮：点它们和点 Tk 的按钮效果一样，两边同时换色。')
        lay = page.layout()
        row = QHBoxLayout()
        for name in ('light', 'dark'):
            btn = QPushButton(_PALETTES[name]['name'] + '主题')
            btn.setObjectName('ghost')
            btn.clicked.connect((lambda n: (lambda: self._set_palette(n)))(name))
            row.addWidget(btn)
        self._qt_theme_label = QLabel('当前主题：浅色')
        row.addWidget(self._qt_theme_label)
        row.addStretch(1)
        lay.addLayout(row)
        tip = QLabel('换色改的是「角色 → 颜色」这张表：Tk 侧重刷控件底色，'
                     'Qt 侧重新生成 QSS，控件一个都不用重建。')
        tip.setObjectName('panelHint')
        tip.setWordWrap(True)
        lay.addWidget(tip)
        lay.addStretch(1)
        return page

    def _qt_page_done(self):
        page = self._qt_page('Qt 这一侧的小结',
                             '这块面板从头到尾活在 Tk 的窗口里：Qt 画、Qt 收事件、Tk 管窗口。')
        lay = page.layout()
        for line in ('Qt 面板用 Win32 真子窗口的方式嵌进 Tk 宿主 frame',
                     'Qt 的按钮 / 输入框 / 表格回调都写进 Tk 的状态栏',
                     'Tk 的按钮反过来改 Qt 图表的数据，Qt 的定时器由 Tk 的 after 泵推动'):
            item = QLabel('· ' + line)
            item.setObjectName('panelHint')
            lay.addWidget(item)
        row = QHBoxLayout()
        btn = QPushButton('在 Tk 状态栏留一句')
        btn.clicked.connect(lambda: self._set_status('这一行是 Tk 的状态栏，被 Qt 按钮写进来了'))
        row.addWidget(btn)
        btn2 = QPushButton('退出引导')
        btn2.setObjectName('ghost')
        btn2.clicked.connect(self.close)
        row.addWidget(btn2)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(1)
        return page

    # ------------------------------------------------------------------ #
    # 把 Qt 塞进 Tk：先试真子窗口，再试悬浮跟随，最后纯 Tk
    # ------------------------------------------------------------------ #
    def _embed_qt(self):
        """尝试把 Qt 面板嵌进 Tk 宿主 frame（三个梯度，失败一律不崩）。"""
        if self._qt_holder is None or self._qt_host is None:
            return False
        if not sys.platform.startswith('win'):
            self._qt_embed_mode = '已降级：纯 Tk'
            self._qt_embed_detail = '当前系统不是 Windows，未做跨窗口嵌入'
            print('提示：当前系统不是 Windows，Qt 面板不做窗口嵌入，引导照常可用。')
            self._show_qt_notice('当前系统不是 Windows，本版不做跨框架窗口嵌入。\n'
                                 '引导的其余部分照常可用；窗口外壳与导航仍然是 Tkinter。')
            return False
        if MODE == 'selftest':
            # 无头自检只建对象：offscreen 平台下没有真 HWND，嵌入相关代码整体不进。
            self._qt_embed_mode = '已建对象（自检不嵌入）'
            self._qt_embed_detail = 'QT_QPA_PLATFORM=%s' % os.environ.get('QT_QPA_PLATFORM', '')
            return False
        # 两个梯度都试一遍；默认顺序是"实测更好的那个在前"，`--float-qt` 可以反过来，
        # 方便后来人自己复现两种姿势的差别。
        tiers = [('真子窗口（Win32 SetParent）', self._embed_as_child_window),
                 ('悬浮跟随（createWindowContainer）', self._embed_as_window_container)]
        if _FORCE_FLOAT:
            tiers.reverse()
        for name, tier in tiers:
            try:
                if tier():
                    return True
            except Exception as exc:
                print('%s 失败（%s），换下一种姿势。' % (name, exc))
        self._qt_embed_mode = '已降级：纯 Tk'
        self._qt_embed_detail = '两种嵌入姿势都不可用'
        print('Qt 面板未能嵌入 Tk 窗口，已退化成「纯 Tk 界面 + 一句说明」，引导照常可用。')
        self._show_qt_notice('Qt 面板没能嵌进 Tk 的窗口，本版已退化成纯 Tk 界面。\n'
                             '引导的每一步都照常可用，只是少了下面那块彩色面板。')
        return False

    def _win32(self):
        """取 user32 并**显式声明参数类型**（否则 64 位下样式值会溢出 / 句柄被截断）。"""
        if self._user32 is not None:
            return self._user32
        import ctypes.wintypes as wt
        user32 = ctypes.windll.user32
        user32.SetWindowLongW.restype = ctypes.c_long
        user32.SetWindowLongW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_long]
        user32.GetWindowLongW.restype = ctypes.c_long
        user32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
        user32.SetParent.restype = wt.HWND
        user32.SetParent.argtypes = [wt.HWND, wt.HWND]
        user32.GetParent.restype = wt.HWND
        user32.GetParent.argtypes = [wt.HWND]
        user32.SetWindowPos.restype = wt.BOOL
        user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                                        ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        # 没有 argtypes 时 ctypes 会把句柄当 32 位 int 传 —— 句柄一大就被截断。
        user32.GetWindowRect.restype = wt.BOOL
        user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
        self._user32 = user32
        return user32

    def _embed_as_child_window(self):
        """姿势 B：Win32 `SetParent` 把 Qt 窗口变成 Tk 宿主 frame 的 `WS_CHILD` 子窗口。

        为什么先走这条：实测这样嵌进去以后，Qt 面板**真的在 Tk 窗口的坐标系里** ——
        随 Tk 窗口移动、随画布滚动、被 Tk 窗口裁剪，Tk 最小化时一起消失；
        位置归 Windows 管，我们只需要在宿主 `<Configure>` 时同步一次尺寸。
        """
        self.app.root.update()               # 先让 Tk 把宿主 frame 的 HWND 建出来
        self._qt_host_hwnd = int(self._qt_host.winfo_id())
        holder = self._qt_holder
        holder.show()                        # Qt 先当成普通顶层窗口出现，才拿得到 HWND
        self._qt_app.processEvents()
        hwnd = int(holder.winId())
        user32 = self._win32()
        style = user32.GetWindowLongW(hwnd, _GWL_STYLE)
        new_style = _s32((style & ~_WS_POPUP & ~_WS_CAPTION) | _WS_CHILD)
        user32.SetWindowLongW(hwnd, _GWL_STYLE, new_style)
        user32.SetParent(hwnd, self._qt_host_hwnd)
        if int(user32.GetParent(hwnd)) != self._qt_host_hwnd:
            raise RuntimeError('SetParent 没有生效，父窗口仍是 %s' % user32.GetParent(hwnd))
        self._qt_holder_hwnd = hwnd
        holder.move(0, 0)                    # Qt 眼里自己在左上角（子窗口坐标是相对父窗口的）
        # **唯一一次**带 FRAMECHANGED 的调用：改完样式要让 WS_CHILD 真正生效。
        width = max(1, int(self._qt_host.winfo_width()))
        height = max(1, int(self._qt_host.winfo_height()))
        user32.SetWindowPos(hwnd, 0, 0, 0, width, height, _SWP_SYNC | _SWP_FRAMECHANGED)
        self._sync_qt_geometry()             # 再走一遍稳态同步，抹掉 Qt 自己撑出来的多余高度
        holder.raise_()
        self._qt_embed_mode = '真嵌入（Win32 子窗口）'
        self._qt_embed_detail = '宿主 HWND=%s，Qt 窗口 HWND=%s' % (self._qt_host_hwnd, hwnd)
        return True

    def _embed_as_window_container(self):
        """姿势 A（降级用）：`QWindow.fromWinId(宿主)` + `createWindowContainer` + 屏幕坐标跟随。

        实测局限（所以只当备胎）：Qt 会把 Tk 宿主 HWND 收进自己的顶层容器窗口里，
        面板于是"浮"在屏幕上，移动/缩放/层级都得自己追。这里把位置与尺寸都按
        `物理像素 / dpr` 换算成 Qt 的逻辑像素，并挂上跟随回调。
        """
        self.app.root.update()
        self._qt_host_hwnd = int(self._qt_host.winfo_id())
        foreign = QWindow.fromWinId(self._qt_host_hwnd)
        holder = QWidget.createWindowContainer(foreign)
        holder.setParent(None)
        holder.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        holder.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        holder.show()
        self._qt_holder = holder              # 后续几何同步都作用在容器上
        self._sync_qt_geometry()
        self._qt_embed_mode = '降级：悬浮跟随（不是真嵌入）'
        self._qt_embed_detail = 'createWindowContainer 把面板浮在了 Tk 窗口上方，靠屏幕坐标跟随'
        return True

    def _qt_dpr(self):
        """Qt 的逻辑像素倍率（本机 1.5）：尺寸换算要用，缺了就按 1.0 处理。"""
        try:
            ratio = float(self._qt_holder.devicePixelRatio())
            if ratio > 0:
                return ratio
        except Exception:
            pass
        try:
            return float(self._qt_app.primaryScreen().devicePixelRatio()) or 1.0
        except Exception:
            return 1.0

    def _sync_qt_geometry(self):
        """把 Qt 面板对齐到 Tk 宿主 frame：尺寸用物理像素，Qt 逻辑尺寸按 dpr 折算。

        Tk 用**物理像素**（`winfo_width`），Qt 用**逻辑像素**（本机 1.5 倍），
        所以 `holder.resize()` 要除一次 dpr，`SetWindowPos` 用物理值 —— 这是本任务
        最容易踩的坑，写在这里当注释留给后来人。
        """
        if self._qt_holder is None or self._qt_host is None:
            return
        try:
            width = max(1, int(self._qt_host.winfo_width()))
            height = max(1, int(self._qt_host.winfo_height()))
        except Exception:
            return
        dpr = self._qt_dpr()
        try:
            self._qt_holder.resize(max(1, int(round(width / dpr))),
                                   max(1, int(round(height / dpr))))
        except Exception:
            pass
        if not self._qt_holder_hwnd:
            # 姿势 A：Qt 窗口是独立顶层窗口 ⇒ 几何用**屏幕坐标**（同样按 dpr 折算）。
            try:
                x = int(self._qt_host.winfo_rootx())
                y = int(self._qt_host.winfo_rooty())
                self._qt_holder.setGeometry(int(round(x / dpr)), int(round(y / dpr)),
                                            max(1, int(round(width / dpr))),
                                            max(1, int(round(height / dpr))))
            except Exception:
                pass
            return
        try:
            # 稳态同步：不带 FRAMECHANGED（原因见 `_SWP_SYNC` 的注释）。
            self._win32().SetWindowPos(self._qt_holder_hwnd, 0, 0, 0, width, height, _SWP_SYNC)
        except Exception:
            pass

    def _qt_geometry_report(self):
        """给 --real-smoke 用的一行取证：宿主 frame 与 Qt 窗口的屏幕矩形是否重合。"""
        if self._qt_host is None:
            return 'Qt 面板：未创建'
        try:
            hx, hy = self._qt_host.winfo_rootx(), self._qt_host.winfo_rooty()
            hw, hh = self._qt_host.winfo_width(), self._qt_host.winfo_height()
        except Exception:
            return 'Qt 面板：宿主 frame 已销毁'
        if not self._qt_holder_hwnd:
            return ('Qt 面板嵌入方式：%s ｜ 宿主 frame 物理矩形=(%d, %d, %dx%d) ｜ %s'
                    % (self._qt_embed_mode, hx, hy, hw, hh, self._qt_embed_detail))
        try:
            import ctypes.wintypes as wt
            rect = wt.RECT()
            self._win32().GetWindowRect(self._qt_holder_hwnd, ctypes.byref(rect))
            same = (rect.left == hx and rect.top == hy
                    and rect.right - rect.left == hw and rect.bottom - rect.top == hh)
            return ('Qt 面板嵌入方式：%s ｜ 宿主 frame 物理矩形=(%d, %d, %dx%d) ｜ '
                    'Qt 窗口物理矩形=(%d, %d, %d, %d) ｜ 完全重合=%s'
                    % (self._qt_embed_mode, hx, hy, hw, hh, rect.left, rect.top,
                       rect.right, rect.bottom, same))
        except Exception as exc:
            return 'Qt 面板嵌入方式：%s ｜ 取矩形失败：%s' % (self._qt_embed_mode, exc)

    # ------------------------------------------------------------------ #
    # 事件泵 + 几何看门狗
    # ------------------------------------------------------------------ #
    def _start_pump(self):
        """Qt 没有自己的 exec 循环：用 Tk 的 after 反复调 processEvents 把 Qt 泵起来。"""
        if self._qt_app is None:
            return
        self._pump_running = True

        def pump():
            if not self._pump_running:
                return
            try:
                self._qt_app.processEvents()
            except Exception:
                pass
            self._pump_tick += 1
            if self._pump_tick % 8 == 0:        # 每约 0.13 秒查一次尺寸漂移（很便宜）
                self._check_qt_geometry()
            try:
                self.app.root.after(_PUMP_MS, pump)
            except Exception:
                self._pump_running = False      # 窗口已销毁：安静收摊

        try:
            self.app.root.after(_PUMP_MS, pump)
        except Exception:
            self._pump_running = False

    def _check_qt_geometry(self):
        """看门狗：宿主 frame 的位置/尺寸一变（或 Qt 自己想挪窝），就把它按回去。

        Qt 仍然以为自己是"顶层窗口"，个别操作（`show()`、布局变化）会让它按屏幕坐标
        去 `SetWindowPos` —— 那在子窗口坐标里就是错的。所以这里每约 0.13 秒比对一次
        「Qt 窗口矩形 vs Tk 宿主 frame 矩形」，不一致就重贴：既修尺寸漂移，也修位置漂移。
        """
        if self._qt_holder is None or self._qt_host is None:
            return
        try:
            if self.app.root.state() == 'iconic':      # 最小化时坐标没有意义，别空转重贴
                return
        except Exception:
            pass
        if not self._qt_holder_hwnd:
            if self._qt_embed_mode.startswith('降级：悬浮'):
                self._sync_qt_geometry()
            return
        try:
            import ctypes.wintypes as wt
            rect = wt.RECT()
            self._win32().GetWindowRect(self._qt_holder_hwnd, ctypes.byref(rect))
            want = (int(self._qt_host.winfo_rootx()), int(self._qt_host.winfo_rooty()),
                    max(1, int(self._qt_host.winfo_width())),
                    max(1, int(self._qt_host.winfo_height())))
            qt = (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
            if qt == want:
                self._qt_mismatch_streak = 0
                return
            self._qt_mismatch_streak += 1
            self._sync_qt_geometry()
            # 兜底（只在别的机器上 Qt 死活不肯缩小时才会走到）：宿主比 Qt 矮就把它**撑高**。
            # 宁可窗口高一点、内容区滚动，也不要把 Qt 面板底部裁掉 —— 连续约 5 秒都没对齐才动手。
            if (not self._qt_absorbed and self._qt_mismatch_streak >= 40
                    and qt[3] > want[3] + 4):
                self._qt_absorbed = True
                print('提示：Qt 面板比宿主 frame 高，已把宿主撑到 %dx%d（不裁面板）。'
                      % (max(want[2], qt[2]), qt[3]))
                self._relayout_qt_area(max(want[2], qt[2]), qt[3])
        except Exception:
            pass

    def reveal_qt_panel(self):
        """显式让 Qt 面板出现并重新对齐（`--real-smoke` 用：真平台才需要"露脸"）。"""
        if self._qt_holder is None:
            return
        try:
            self._qt_holder.show()
            self._qt_holder.raise_()
        except Exception:
            pass
        if self._qt_app is not None:
            try:
                self._qt_app.processEvents()
            except Exception:
                pass
        self._sync_qt_geometry()

    # ------------------------------------------------------------------ #
    # Qt 回调：全部写回 Tk 的状态栏（证明两侧真的在通信）
    # ------------------------------------------------------------------ #
    def _qt_on_button(self):
        self.qt_click_count = getattr(self, 'qt_click_count', 0) + 1
        if self._qt_click_label is not None:
            self._qt_click_label.setText('Qt 按钮：已经点了 %d 次' % self.qt_click_count)
        self._set_status('Qt 按钮的信号槽跑了第 %d 次（这一行是 Tk 的状态栏）'
                         % self.qt_click_count)

    def _qt_on_text(self, value):
        text = value or ''
        if self._qt_echo is not None:
            if text:
                self._qt_echo.setText('Qt 回显：%s（%d 个字符）' % (text, len(text)))
            else:
                self._qt_echo.setText('Qt 回显：（还没有输入）')
        self._set_status('Qt 输入框内容长度：%d' % len(text))

    def _qt_on_slider(self, value):
        if self._qt_slider_label is not None:
            self._qt_slider_label.setText('Qt 滑块：%d' % int(value))
        self._set_status('Qt 滑块回调收到数值 %d' % int(value))

    def _qt_on_toggle(self, flag):
        if self._qt_toggle_label is not None:
            self._qt_toggle_label.setText('Qt 复选框：%s' % ('已勾选' if flag else '未勾选'))
        self._set_status('Qt 复选框回调收到布尔值 %s' % ('True' if flag else 'False'))

    def _qt_on_table_row(self):
        if self._qt_table is None:
            return
        row = self._qt_table.currentRow()
        if row < 0 or row >= len(_QT_TABLE_ROWS):
            return
        values = _QT_TABLE_ROWS[row]
        self._set_status('Qt 表格选中第 %d 行：%s ｜ %s' % (row + 1, values[0], values[1]))

    def _qt_anim_tick(self):
        """Qt 定时器：推一次环形图数据（只在图表那一步动，别的时候空转）。"""
        if self._qt_series is None or self.step != 4:
            return
        try:
            import math
            self._qt_phase += 0.18
            base = _CHART_DATA[self.chart_variant]
            for index, piece in enumerate(self._qt_series.slices()):
                piece.setValue(base[index][1] * (1.0 + 0.14 * math.sin(self._qt_phase + index)))
        except Exception:
            pass

    def _regen_chart(self):
        """换一组图表数据（Tk 按钮与 Qt 按钮共用这一个回调）。"""
        self.chart_variant = (self.chart_variant + 1) % len(_CHART_DATA)
        base = _CHART_DATA[self.chart_variant]
        if self._qt_series is not None:
            try:
                for index, piece in enumerate(self._qt_series.slices()):
                    piece.setValue(base[index][1])
            except Exception:
                pass
        if self._qt_chart_label is not None:
            self._qt_chart_label.setText('当前数据：第 %d 组' % (self.chart_variant + 1))
        if self.chart_label is not None:
            self.chart_label.set_text('Qt 图表当前数据：%s' % self._chart_text(self.chart_variant))
        self._set_status('Qt 环形图已换成第 %d 组数据（按钮来自 Tk）' % (self.chart_variant + 1))

    @staticmethod
    def _chart_text(variant):
        return ' · '.join('%s %d' % (name, value)
                          for name, value in _CHART_DATA[variant % len(_CHART_DATA)])

    # ------------------------------------------------------------------ #
    # Tk 回调
    # ------------------------------------------------------------------ #
    def _on_tk_click(self):
        self.tk_click_count += 1
        if getattr(self, 'tk_click_label', None) is not None:
            self.tk_click_label.set_text('Tk 按钮：已经点了 %d 次' % self.tk_click_count)
        self._set_status('Tk 按钮的中立回调跑了第 %d 次' % self.tk_click_count)
        if self._qt_click_label is not None and self.tk_click_count == 1:
            self._qt_click_label.setText('Qt 标签也被 Tk 的按钮改了（双向通信）')

    def _on_typed(self, value):
        if getattr(self, 'echo_label', None) is not None:
            self.echo_label.set_text('Tk 回显：%s' % (value if value else '（还没有输入）'))
        self._set_status('Tk 输入框内容长度：%d' % len(value or ''))

    def _fill_sample(self):
        self.input_handle.value.set('张三')
        self._set_status('已把「张三」写进 Tk 输入框（set() 也会触发回显）')

    def _on_volume(self, value):
        if getattr(self, 'volume_label', None) is not None:
            self.volume_label.set_text('Tk 滑块：%d' % int(round(value)))
        self._set_status('Tk 滑块拖动中：%d' % int(round(value)))

    def _on_toggle(self, value):
        if getattr(self, 'toggle_label', None) is not None:
            self.toggle_label.set_text('开关状态：%s' % ('开' if value else '关'))
        self._set_status('Tk 开关被切成「%s」' % ('开' if value else '关'))

    def _regen_table(self):
        self.table_variant = (self.table_variant + 1) % len(_TK_TABLE_ROWS)
        if self.tk_table is not None:
            self.tk_table.set_rows(_TK_TABLE_ROWS[self.table_variant])
        self._set_status('Tk 表格已换成第 %d 批数据' % (self.table_variant + 1))

    def _on_row(self, values, _row_id):
        text = ' ｜ '.join(str(v) for v in values) if values else '（空行）'
        if getattr(self, 'table_label', None) is not None:
            self.table_label.set_text('Tk 表格选中：%s' % text)
        self._set_status('Tk 表格选中：%s' % text)

    def _finish(self):
        if self.step < _STEP_COUNT - 1:
            self.goto(_STEP_COUNT - 1)
        else:
            self._set_status('引导完成：想继续探索就运行 python main.py')

    # ------------------------------------------------------------------ #
    # 步骤切换
    # ------------------------------------------------------------------ #
    def step_delta(self, delta):
        self.goto(self.step + int(delta))

    def goto(self, index):
        """切到第 `index` 步（0 基）：Tk 换步骤容器，Qt 换 QStackedWidget 的那一页。"""
        index = max(0, min(_STEP_COUNT - 1, int(index)))
        self.step = index
        for i, frame in enumerate(self._step_frames):
            if i == index:
                frame.native.pack(side='top', fill='both', expand=True)
            else:
                frame.native.pack_forget()
        self.prev_handle.set_enabled(index > 0)
        self.next_handle.set_enabled(index < _STEP_COUNT - 1)
        self.progress_handle.update(index + 1)
        self.progress_text.set_text('第 %d / %d 步 · %s' % (index + 1, _STEP_COUNT,
                                                           STEPS[index][0]))
        self._paint_nav()
        # Qt 侧跟着翻页（面板本身位置不动，只换页，所以不会跳）
        if self._qt_stack is not None:
            try:
                self._qt_stack.setCurrentIndex(index)
            except Exception:
                pass
        if self._qt_step_label is not None:
            try:
                self._qt_step_label.setText('第 %d 步 / 共 %d 步 · %s'
                                            % (index + 1, _STEP_COUNT, STEPS[index][0]))
            except Exception:
                self._qt_step_label = None
        self._set_status('第 %d 步：%s —— Tk 换页，Qt 面板也跟着换页'
                         % (index + 1, STEPS[index][0]))

    # ------------------------------------------------------------------ #
    # 主题：一份调色板，Tk 与 Qt 同时换
    # ------------------------------------------------------------------ #
    def _set_palette(self, name):
        self.palette_name = name if name in _PALETTES else 'light'
        self._apply_palette()
        if getattr(self, 'theme_label', None) is not None:
            self.theme_label.set_text('当前主题：%s（Tk + Qt 一起换）' % self.palette['name'])
        if self._qt_theme_label is not None:
            self._qt_theme_label.setText('当前主题：%s' % self.palette['name'])
        self._set_status('主题已切换为「%s」：Tk 重刷角色色表，Qt 重新生成 QSS，都不用重启'
                         % self.palette['name'])

    def _apply_palette(self):
        self.palette = _PALETTES[self.palette_name]
        p = self.palette
        # 窗口骨架（Btk 建的原生容器）不由 _themed 管理，单独刷一遍
        for native in (self.app.root, self.app._main_container, self.app.toolbar_container,
                       self.app.main_canvas, self.app.scrollable_frame):
            try:
                native.configure(bg=p['app_bg'])
            except Exception:
                pass
        try:
            self.app.statusbar_container.configure(bg=p['status_bg'])
        except Exception:
            pass
        for native, role in self._themed:
            self._paint(native, role)
        self._paint_ttk()
        self._paint_nav()
        if self._qt_host is not None:
            try:
                self._qt_host.configure(bg=p['nav_bg'])
            except Exception:
                pass
        self._qt_apply_palette()

    def _role_colors(self, role):
        """角色 → (底色, 前景色, 按下底色, 按下前景色)。`None` 表示该角色不用这个槽位。"""
        p = self.palette
        table = {
            'card': (p['card'], p['fg'], None, None),
            'nav_bar': (p['nav_bg'], None, None, None),
            'status': (p['status_bg'], p['fg'], None, None),
            'title': (p['card'], p['fg'], None, None),
            'text': (p['card'], p['fg'], None, None),
            'muted': (p['card'], p['muted'], None, None),
            'hi': (p['card'], p['accent'], None, None),
            'field': (p['field'], p['fg'], None, None),
            'tree': (p['card'], p['fg'], None, None),
            'primary': (p['accent'], p['accent_fg'], p['accent_dark'], p['accent_fg']),
            'ghost': (p['nav_bg'], p['fg'], p['border'], p['fg']),
            'nav': (p['nav_bg'], p['fg'], p['border'], p['fg']),
            'nav_on': (p['accent'], p['accent_fg'], p['accent'], p['accent_fg']),
        }
        return table.get(role, (p['card'], p['fg'], None, None))

    def _paint(self, native, role):
        """按角色给**原生** Tk 控件上色（逃生口：中立契约没有 bg/fg/按下态）。"""
        bg, fg, abg, afg = self._role_colors(role)
        try:
            cls = native.winfo_class()
        except Exception:
            return
        try:
            if cls in ('Frame', 'Toplevel', 'Canvas', 'Labelframe'):
                native.configure(bg=bg)
            elif cls == 'Label':
                native.configure(bg=bg, fg=fg if fg is not None else self.palette['fg'])
            elif cls == 'Button':
                native.configure(bg=bg, fg=fg, activebackground=abg or bg,
                                 activeforeground=afg or fg, relief='flat', bd=0)
            elif cls == 'Entry':
                native.configure(bg=bg, fg=fg, insertbackground=fg, relief='flat',
                                 highlightthickness=1,
                                 highlightbackground=self.palette['border'],
                                 highlightcolor=self.palette['accent'])
            elif cls == 'Scrollbar':
                native.configure(bg=self.palette['border'], troughcolor=self.palette['nav_bg'],
                                 activebackground=self.palette['accent'], bd=0)
            # ttk 控件（Treeview / Scale）不吃 bg/fg ⇒ 交给 _paint_ttk
        except Exception:
            pass

    def _paint_ttk(self):
        """ttk 控件（表格）靠 `ttk.Style` 上色，用 Btk 建窗时持有的那一个单例。"""
        style = getattr(self.app, '_ttk_style', None)
        if style is None:
            return
        p = self.palette
        try:
            style.configure('Treeview', background=p['card'], fieldbackground=p['card'],
                            foreground=p['fg'], borderwidth=0)
            style.configure('Treeview.Heading', background=p['nav_bg'], foreground=p['fg'])
            style.map('Treeview', background=[('selected', p['accent'])],
                      foreground=[('selected', p['accent_fg'])])
        except Exception:
            pass

    def _paint_nav(self):
        for i, native in enumerate(self._nav_buttons):
            self._paint(native, 'nav_on' if i == self.step else 'nav')

    def _qt_apply_palette(self):
        """把同一份调色板喂给 Qt：QSS 换一套 + 图表颜色跟着换。"""
        if self._qt_holder is None:
            return
        p = self.palette
        try:
            self._qt_holder.setStyleSheet(_qt_qss(p))
        except Exception:
            pass
        if self._qt_chart is None:
            return
        try:
            for index, piece in enumerate(self._qt_series.slices()):
                gradient = QLinearGradient(0, 0, 1, 1)
                gradient.setCoordinateMode(QLinearGradient.CoordinateMode.ObjectBoundingMode)
                gradient.setColorAt(0.0, QColor(p['qt_slice_a']).lighter(100 + index * 10))
                gradient.setColorAt(1.0, QColor(p['qt_slice_b']).darker(100 + index * 6))
                piece.setBrush(QBrush(gradient))
                piece.setPen(QPen(QColor(p['card']), 2))
            self._qt_chart.setTitleBrush(QBrush(QColor(p['fg'])))
            self._qt_chart.legend().setLabelColor(QColor(p['fg']))
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # 自检与收尾
    # ------------------------------------------------------------------ #
    def selfcheck(self):
        """把"用户真的动手"会走的回调各跑一遍（**不进 mainloop**）。

        只把控件建出来是不够的：回调里的拼写错误要等用户点下去才暴露。
        这里逐条调用 Tk 侧与 Qt 侧的槽，`--selftest` 才真的能证明"两边都能用"。
        """
        self._on_tk_click()
        self._on_typed('测试')
        self._fill_sample()
        self._on_volume(66.6)
        self._on_toggle(True)
        self._regen_table()
        self._on_row(('标签 label', 'Tk（中立层）', '只看不点'), 'i001')
        self._qt_on_button()
        self._qt_on_text('混合版')
        self._qt_on_slider(72)
        self._qt_on_toggle(True)
        self._regen_chart()
        self._qt_anim_tick()
        if self._qt_table is not None:
            self._qt_table.selectRow(1)
            self._qt_on_table_row()
        self.step_delta(1)
        self.step_delta(-1)
        self._set_palette('dark')
        self._set_palette('light')
        self._finish()

    def qt_summary(self):
        """一行中文小结：Qt 面板到底嵌进去了没有（给冒烟输出与报告用）。"""
        if not HAVE_QT:
            return 'Qt 面板：未使用（没装 PySide6，退化成纯 Tk 界面）'
        return 'Qt 面板：%s ｜ %s' % (self._qt_embed_mode, self._qt_embed_detail)

    def close(self):
        """幂等收尾：停泵 → 摘掉 Qt 子窗口 → 销毁 Qt 控件 → 释放 Tk backend root。"""
        self._pump_running = False
        if self._qt_timer is not None:
            try:
                self._qt_timer.stop()
            except Exception:
                pass
        if self._qt_holder is not None and self._qt_holder_hwnd:
            # 先把 Qt 窗口从 Tk 宿主里摘出来，再销毁：反过来会让 Windows 在窗口
            # 已死的父窗口上做销毁，日志里会冒一串看不懂的 Qt 警告。
            try:
                self._win32().SetParent(self._qt_holder_hwnd, 0)
            except Exception:
                pass
            self._qt_holder_hwnd = 0
        if self._qt_holder is not None:
            try:
                self._qt_holder.close()
                self._qt_holder.deleteLater()
            except Exception:
                pass
            self._qt_holder = None
        if self._qt_app is not None:
            try:
                self._qt_app.processEvents()
            except Exception:
                pass
        self.app.close()                    # 幂等；释放 backend root，进程里才能再开窗口

    # ------------------------------------------------------------------ #
    # 小工具：创建 Tk 控件并登记配色
    # ------------------------------------------------------------------ #
    def _label(self, parent, text, role='text', size=11, bold=False, wrap=None,
               padx=26, pady=(0, 6), side='top'):
        handle = self.r.label(parent, text, family=_FONT, size=size, bold=bold)
        native = handle.native
        native.configure(justify='left', anchor='w')
        if wrap:
            native.configure(wraplength=wrap)       # 中立契约无 wraplength（逃生口）
        handle.layout(Layout.pack(side=side, anchor='w', padx=padx, pady=pady,
                                  fill=('x' if wrap else None)))
        self._themed.append([native, role])
        return handle

    def _button(self, parent, text, command, role='primary', width=12, size=11,
                bold=True, pack=None):
        handle = self.r.button(parent, text, command=command, family=_FONT, size=size,
                               bold=bold, width=width, height=1)
        native = handle.native
        native.configure(cursor='hand2', pady=4)    # 扁平化 + 手型光标（逃生口）
        handle.layout(pack if pack is not None else Layout.pack(anchor='w', padx=26, pady=6))
        self._themed.append([native, role])
        return handle

    def _row(self, parent, padx=26, pady=(0, 6)):
        row = self.r.container(parent, Layout.pack(anchor='w', padx=padx, pady=pady))
        self._themed.append([row.native, 'card'])
        return row

    def _set_status(self, text):
        self.set_status(text)


# ---------------------------------------------------------------------- #
# 入口
# ---------------------------------------------------------------------- #
def _run_selftest():
    """只构建完整 UI（Tk + Qt 对象），不进 mainloop、不 show、不留 backend root。

    `QT_QPA_PLATFORM=offscreen` 下也要过：嵌入相关的代码整体不进（真 embedding 需要
    真 HWND，offscreen 平台没有），所以它不可能把自检弄挂。
    """
    guide = GuideHybrid()
    try:
        guide.app.root.update()             # 真的建完并渲染一遍（不进事件循环）
        guide.selfcheck()                   # Tk 与 Qt 两侧的回调都走一遍
        for index in range(_STEP_COUNT):
            guide.goto(index)
        guide.goto(0)
        guide.app.root.update()
        print(guide.qt_summary())
        print('SELFTEST OK')
    finally:
        guide.close()


def _largest_window(grabber, windows):
    """在标题匹配的窗口里挑**面积最大**的那个，返回 `(hwnd, title)` 或 `None`。

    为什么需要挑：Tk 的浮层提示会沿用同一个标题 ⇒ `find_windows` 可能同时命中
    「主窗口」和「气泡」，枚举顺序还不稳定（guide_tk.py 的实测教训）。
    主窗口一定是其中面积最大的那个。
    """
    import ctypes
    best, best_area = None, -1
    for hwnd, title in windows or []:
        try:
            rect = grabber.wt.RECT()
            grabber.user32.GetWindowRect(hwnd, ctypes.byref(rect))
            area = max(0, rect.right - rect.left) * max(0, rect.bottom - rect.top)
        except Exception:
            continue
        if area > best_area:
            best, best_area = (hwnd, title), area
    return best


def _run_real_smoke():
    """真窗口冒烟：真平台建窗 → 露出窗口 → 截图 → 释放 backend root。"""
    shot_path = os.path.join(ROOT, _SHOT_NAME)
    # 先导入截图工具：它在导入期调用 SetProcessDPIAware()，必须在建窗前生效，
    # 否则窗口按系统缩放建好后进程才变 DPI 感知，截出来的尺寸会与窗口不一致。
    grabber = None
    try:
        import _grab_window as grabber
    except Exception as exc:
        print('提示：无法导入截图工具 _grab_window.py（%s），本次跳过截图。' % exc)

    guide = GuideHybrid()
    try:
        guide.app.root.update()
        guide.reveal_qt_panel()             # 显式让 Qt 面板出现（幂等）
        time.sleep(2)                       # 留出窗口真正上屏的时间
        guide.app.root.update()
        if guide._qt_app is not None:       # 泵事件：让 Qt 画完这一帧
            for _ in range(40):
                guide._qt_app.processEvents()
                guide.app.root.update()
                time.sleep(0.03)
        print(guide.qt_summary())
        print(guide._qt_geometry_report())
        if grabber is not None:
            try:
                windows = grabber.find_windows(_WINDOW_MARK)
                target = _largest_window(grabber, windows)
                if target is not None:
                    hwnd, title = target
                    ok, rect, img = grabber.grab(hwnd, shot_path)
                    print('已截图：%s（窗口 %r，PrintWindow=%s，矩形 %s，像素 %dx%d）'
                          % (shot_path, title, bool(ok), rect, img.size[0], img.size[1]))
                else:
                    print('未找到标题含「%s」的可见窗口，本次跳过截图。' % _WINDOW_MARK)
            except Exception as exc:
                print('截图失败（已忽略，不影响冒烟结论）：%s' % exc)
        print('REAL SMOKE OK')
    finally:
        guide.close()


def main():
    argv = sys.argv[1:]
    if '--selftest' in argv:
        _run_selftest()
        return 0
    if '--real-smoke' in argv:
        _run_real_smoke()
        return 0
    guide = GuideHybrid()
    try:
        guide.app.run()                     # 拥有 Tk 事件循环（Qt 由泵推着走）
    finally:
        guide.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
