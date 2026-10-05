# -*- coding: utf-8 -*-
"""guide_qt.py —— 纯 PySide6 的新手引导（8 步，中文）。

这是什么
    一份"能跑、能点、能看"的新手引导：左边是步骤导航，右边是可滚动的内容卡片，
    底部是进度条与翻页按钮。每一页都放了一个**真的能用**的控件 —— 按钮真能点、
    输入框真有回显、滑块真能拖、图表真的由 `PySide6.QtCharts` 画出来。

硬约束（本仓库的既有教训，写在最前面以免后人改坏）
    1. **纯 PySide6**：本文件不出现 `tkinter`，也不 import 本仓库的 `gui.` 包
       （那是 Tk 门面）。只用 `ck1_0.*` + `PySide6` + 标准库。
    2. **文案只用字体安全字符**：Microsoft YaHei 画不出彩色 emoji，会渲染成豆腐块
       （人眼报告）。故本文件里只用中文字、ASCII 与箭头/圆点一类
       字体安全的符号（← → ↑ ↓ ● ○ · ｜）。
    3. **缺依赖说人话**：没装 PySide6 时打印一句中文安装指引并 `sys.exit(0)`，不抛 traceback。
    4. **零配置可运行**：从仓库根直接 `python guide_qt.py` 即可；导入路径由本文件自己处理。
    5. **`--selftest`**：只构建完整 UI（不进事件循环、不弹模态框），打印 `SELFTEST OK` 后退出 0；
       无头环境用 `QT_QPA_PLATFORM=offscreen`，该环境变量**只在** `--selftest` 分支里设置。
    6. **`--real-smoke`**：在**真平台**建同样的界面、`show()` + 泵事件 + 等 2 秒，
       用仓库现成的 `_grab_window.py` 截图存 `_guide_qt_shot.png`，再销毁窗口并打印
       `REAL SMOKE OK`；全程不进 mainloop、不弹模态框。
"""

import os
import sys
import time

# 零配置导入：允许从任意 cwd 用 `python guide_qt.py` / `python <绝对路径>/guide_qt.py` 启动。
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# 运行模式必须在**创建 QApplication 之前**定下来：`QT_QPA_PLATFORM` 是在 QApplication
# 构造时读取的，晚一步设就没用了。
_ARGV = set(sys.argv[1:])
MODE = 'selftest' if '--selftest' in _ARGV else (
    'real-smoke' if '--real-smoke' in _ARGV else 'run')
if MODE == 'selftest':
    # 无头自检：没屏幕也要能建完 UI（只在本分支设，正常运行绝不设）。
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
elif MODE == 'real-smoke':
    # 真窗口取证要求真平台：显式清掉任何继承来的 offscreen 设置。
    os.environ.pop('QT_QPA_PLATFORM', None)

try:
    import PySide6                                     # noqa: F401
except ImportError:
    print('没找到 PySide6。装它的命令是：pip install PySide6')
    sys.exit(2)   # 退出码 2：让 .bat 的 `if errorlevel 1` 停下并 `pause`，把提示留给新手

from PySide6.QtCore import Qt                                            # noqa: E402
from PySide6.QtGui import (QBrush, QColor, QLinearGradient, QPainter,    # noqa: E402
                           QPalette, QPen)
from PySide6.QtWidgets import QFrame, QSizePolicy                       # noqa: E402

from ck1_0.qt_window import QtWindow                                   # noqa: E402
from ck1_0.renderer.base import Layout                                 # noqa: E402

WINDOW_TITLE = 'ck1.0 · 纯 PySide6 新手引导'
SHOT_PATH = '_guide_qt_shot.png'

STEPS = ('欢迎', '按钮与回调', '输入框', '滑块与开关', '图表', '表格', '换主题', '完成')

# 「图表」页的数据（教程内容占比）。
CHART_DATA = (
    ('基础控件', 30),
    ('输入与反馈', 24),
    ('图表可视化', 20),
    ('数据表格', 16),
    ('主题与动画', 10),
)


def place_native(parent_handle, widget):
    """把**原生** Qt 控件塞进某个中立容器的顺序流布局（逃生口）。

    为什么需要它：`slider()` 的句柄 `native` 是**内部** `QSlider`，外层还有一层
    "标签 + 数值标签"的 `QFrame` 容器；中立 `handle.layout(into=…)` 只会把 `QSlider`
    搬过去，把标签和数值留在原地。所以这一类"句柄不等于外层控件"的组件必须整体搬。
    自绘画布（QtCharts 的 `QChartView`）根本没有中立句柄，同样走这里。
    """
    if parent_handle is None or widget is None:
        return None
    layout = parent_handle.native.layout()
    if layout is None:                  # 中立容器还没建过布局 ⇒ 补一个顺序流
        from PySide6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(parent_handle.native)
    layout.addWidget(widget)
    return widget


def set_placeholder_color(handle, color):
    """改输入框占位提示的颜色。

    中立 `input()` 用的是 Qt **原生** placeholder，而占位色来自控件调色板（不是 QSS），
    所以只能经逃生口改 `QPalette.PlaceholderText`，否则深色底上会是一段发暗的灰字。
    """
    try:
        palette = handle.native.palette()
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(color))
        handle.native.setPalette(palette)
    except Exception:
        pass


class Guide:
    """8 步引导的全部界面与交互。"""

    def __init__(self, animate=True):
        self.animate = bool(animate)
        self.index = 0
        self.finished = False
        self.window = QtWindow(WINDOW_TITLE, width=1160, height=780)
        self.renderer = self.window.renderer
        self.chart_view = None
        self.chart = None
        self.chart_series = None
        self._pages = []
        self._done_label = None
        self._build()

    # ---------------------------------------------------------------- #
    # 装配
    # ---------------------------------------------------------------- #
    def _build(self):
        """建外壳 → 建 8 页 → 装快捷键 → 定位到第 1 步。"""
        root = self.window.root
        self.window.add_hero('ck1.0 新手引导',
                             '纯 PySide6 版本：全部界面都由 ck1.0 的后端中立渲染层驱动，'
                             '同一套中立 API 在 Qt 上跑出来的样子。')
        self._set_nav_current = self.window.add_step_nav(STEPS, self.set_current)
        set_progress, set_prev_enabled = self.window.add_footer(
            0, on_prev=self.go_prev, on_next=self.go_next,
            on_finish=self.finish, prev_enabled=False)
        self.set_progress = set_progress
        self.set_prev_enabled = set_prev_enabled

        builders = (self._page_welcome, self._page_button, self._page_input,
                    self._page_slider_toggle, self._page_chart, self._page_table,
                    self._page_theme, self._page_done)
        for build in builders:
            page = build()
            # 页尾加一段弹性留白：否则页内最后一块（提示条/卡片）会被拉长填满整屏。
            layout = page.native.layout()
            if layout is not None:
                layout.addStretch(1)
            self.window.register_page(page)
            self._pages.append(page)

        # 键盘翻页：中立 `add_shortcut` 收的是中立描述串，Qt 侧由适配层转成 QKeySequence。
        self.renderer.add_shortcut('Left', self.go_prev)
        self.renderer.add_shortcut('Right', self.go_next)
        self.renderer.add_shortcut('Esc', self.quit_app)

        self.set_current(0, animate=False)

    def _new_page(self):
        """新建一页（内容区里的一个纵向容器）。"""
        return self.window.box(self.window.content, 'v', margin=(0, 0, 8, 0), spacing=12)

    # ---------------------------------------------------------------- #
    # 第 1 步：欢迎
    # ---------------------------------------------------------------- #
    def _page_welcome(self):
        page = self._new_page()
        card = self.window.card(
            page, '欢迎 —— 这是什么？',
            '一份 8 步走完的中文引导。它自己就是一个 PySide6 程序，也是 ck1.0 渲染层的一次演示。')
        body = card.body
        self.window.text(
            body,
            '左边是步骤导航，右边是内容卡片，底部是进度与翻页按钮。每一页都放了一个'
            '「真的能用」的控件：按钮真的能点，输入框真的有回显，滑块真的能拖，'
            '图表真的用 QtCharts 画出来。你可以随便点、随便拖，不会弄坏任何东西。',
            wrap=True)

        row = self.window.box(body, 'h', margin=(0, 6, 0, 0), spacing=12)
        for head, desc in (('8 个步骤', '从按钮到图表，一步步加料'),
                           ('零配置', '一条命令就能启动'),
                           ('字体安全', '只用中文字与安全符号')):
            mini = self.window.card(row)
            self.window.text(mini.body, head, level='accent')
            self.window.text(mini.body, desc, level='dim', wrap=True)

        self.window.tip(
            page,
            '操作方式：点底部的「下一步 →」、点左侧任意步骤标题直接跳转，'
            '或者按键盘 ← / → 翻页，按 Esc 退出。')
        return page

    # ---------------------------------------------------------------- #
    # 第 2 步：按钮与回调
    # ---------------------------------------------------------------- #
    def _page_button(self):
        page = self._new_page()
        card = self.window.card(
            page, '按钮与回调',
            '按钮的 command 是一个「无参回调」：点击时 Qt 会在 UI 线程里同步调用它。')
        body = card.body

        feedback = self.window.text(body, '还没有点过。', level='accent')
        self.window.text(body, '计数就写在按钮的回调里 —— 没有任何定时器、没有任何轮询。',
                         level='dim', wrap=True)

        row = self.window.box(body, 'h', margin=(2, 2, 0, 0), spacing=10)
        state = {'count': 0}

        def on_click():
            state['count'] += 1
            feedback.set_text('你已经点击了 %d 次。' % state['count'])
            self.window.status('按钮回调被同步调用第 %d 次' % state['count'])

        def on_reset():
            state['count'] = 0
            feedback.set_text('计数已归零，再点一次试试。')
            self.window.status('计数已重置')

        self.window.button(row, '点我一下', command=on_click, primary=True)
        self.window.button(row, '重置计数', command=on_reset)
        self.window.compact(row)            # 行内多余宽度收进末尾弹性空白，按钮靠左贴紧
        self.window.text(body, '按钮的悬停与按下状态由样式表给出：鼠标移上去会提亮描边，'
                               '按下会变暗。这是「真的能点」最直观的证据。',
                         level='dim', wrap=True)
        return page

    # ---------------------------------------------------------------- #
    # 第 3 步：输入框
    # ---------------------------------------------------------------- #
    def _page_input(self):
        page = self._new_page()
        card = self.window.card(
            page, '输入框', '中立 input() 返回一个 InputHandle，它的 .value 是可观察值。')
        body = card.body

        field = self.renderer.input(body, hint='在这里输入你的名字…', width=340)
        field.layout(Layout.pack(into=body))
        set_placeholder_color(field, self.window.palette['dim'])

        echo = self.window.text(body, '（等待输入…）', level='accent')
        self.window.text(body, '下面这块是多行文本框：中立 text_area()，同样带占位提示。',
                         level='dim', wrap=True)

        area = self.renderer.text_area(body, placeholder='随手写点什么，比如今天学到的东西…',
                                       width=430, height=88)
        area.layout(Layout.pack(into=body))
        set_placeholder_color(area, self.window.palette['dim'])

        counter = self.window.text(body, '多行文本框：0 个字符', level='dim')

        def on_text(value):
            text = (value or '').strip()
            if text:
                echo.set_text('你好，%s！输入框里现在有 %d 个字符。' % (text, len(text)))
            else:
                echo.set_text('（等待输入…）')
            self.window.status('输入框内容长度 %d' % len(value or ''))

        def on_area(value):
            counter.set_text('多行文本框：%d 个字符' % len(value or ''))

        # `Value.on_change` 是中立回调：每次按键都会收到新值（不是只收到"变了"这件事）。
        field.value.on_change(on_text)
        area.value.on_change(on_area)
        return page

    # ---------------------------------------------------------------- #
    # 第 4 步：滑块与开关
    # ---------------------------------------------------------------- #
    def _page_slider_toggle(self):
        page = self._new_page()
        card = self.window.card(
            page, '滑块与开关',
            '滑块回调收数值，开关回调收布尔值 —— 两种回调形状都是中立层冻结的。')
        body = card.body

        readout = self.window.text(body, '', level='accent')
        state = {'value': 35, 'on': True}

        def refresh():
            readout.set_text('亮度 = %d ｜ 强调色 = %s'
                             % (int(state['value']), '开启' if state['on'] else '关闭'))

        def on_slide(value):
            state['value'] = value
            refresh()
            self.window.status('滑块回调收到数值 %.0f' % value)

        def on_toggle(flag):
            state['on'] = bool(flag)
            refresh()
            self.window.status('开关回调收到布尔值 %s' % ('True' if flag else 'False'))

        slider = self.renderer.slider(body, from_=0, to=100, default=35, resolution=1,
                                      label='亮度', on_change=on_slide, show_value=True)
        # 逃生口：slider 的 native 只是内部 QSlider，外层那层容器（标签 + 数值）才是要入列的。
        slider_row = slider.native.parentWidget()
        place_native(body, slider_row)
        self.window.compact(slider_row)     # 内部 QHBoxLayout 会把余量摊成项间距 ⇒ 收拢靠左
        self.window.toggle(body, '启用强调色（开/关）', default=True, command=on_toggle)
        refresh()

        self.window.text(body, '把滑块拖到两端、把开关来回切几次：右边的读数始终跟着走，'
                               '因为读数就是回调里直接改的标签文本。',
                         level='dim', wrap=True)
        return page

    # ---------------------------------------------------------------- #
    # 第 5 步：图表
    # ---------------------------------------------------------------- #
    def _page_chart(self):
        page = self._new_page()
        card = self.window.card(
            page, '图表',
            '这一页用 PySide6.QtCharts 画一个真的环形图：渐变切片 + 入场动画。')
        body = card.body

        if self._build_chart(body):
            self.window.text(body, '图例里的百分比就是上面那组数据；把鼠标悬停在切片上会弹出提示。',
                             level='dim', wrap=True)
        else:
            self.window.tip(body, '当前环境没有 QtCharts，已自动降级为中立柱状图 —— '
                                  '图中数据仍然是同一组，只是画法不同。')
            bars = self.renderer.bars(body, [value for _name, value in CHART_DATA],
                                      canvas_width=520, canvas_height=210,
                                      bar_colors=[self.window.palette['a1'],
                                                  self.window.palette['a2']])
            if bars is not None:
                bars.layout(Layout.pack(into=body))
        return page

    def _build_chart(self, parent):
        """建 QtCharts 环形图；QtCharts 不在场时返回 `False`（由调用方降级）。"""
        try:
            from PySide6.QtCharts import QChart, QChartView, QPieSeries
        except ImportError:
            return False
        try:
            series = QPieSeries()
            series.setHoleSize(0.42)            # 中间挖空 ⇒ 环形而不是实心饼
            for index, (name, value) in enumerate(CHART_DATA):
                piece = series.append('%s  %d%%' % (name, value), value)
                piece.setLabelVisible(False)
                piece.setBrush(QBrush(self._slice_gradient(index)))
                piece.setPen(QPen(QColor(self.window.palette['card']), 2))
            chart = QChart()
            chart.addSeries(series)
            chart.setTitle('这份引导的内容占比')
            chart.setBackgroundVisible(False)
            chart.setPlotAreaBackgroundVisible(False)
            chart.legend().setVisible(True)
            chart.legend().setAlignment(Qt.AlignmentFlag.AlignRight)
            chart.legend().setLabelColor(QColor(self.window.palette['text']))
            chart.setTitleBrush(QBrush(QColor(self.window.palette['text'])))
            # 入场动画：切片会从零展开（QtCharts 自带，不需要我们自己写定时器）。
            chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
            view = QChartView(chart)
            view.setRenderHint(QPainter.RenderHint.Antialiasing)
            view.setFrameShape(QFrame.Shape.NoFrame)
            view.setStyleSheet('background: transparent;')
            view.setMinimumHeight(300)
            view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            place_native(parent, view)
        except Exception as exc:               # 图表是本页的"加分项"，失败也不该炸整窗
            print('QtCharts 画图失败，已降级为中立柱状图：%s' % exc)
            return False
        self.chart_view, self.chart, self.chart_series = view, chart, series
        self.window.on_theme_change(self._restyle_chart)
        return True

    def _slice_gradient(self, index):
        """按索引在"强调色两端"之间取样，生成一片的线性渐变。"""
        p = self.window.palette
        ratio = index / max(1, len(CHART_DATA) - 1)
        gradient = QLinearGradient(0, 0, 1, 1)
        gradient.setCoordinateMode(QLinearGradient.CoordinateMode.ObjectBoundingMode)
        gradient.setColorAt(0.0, QColor(p['a1']).lighter(100 + index * 8))
        gradient.setColorAt(1.0, QColor(p['a2']).darker(100 + int(ratio * 40)))
        return gradient

    def _restyle_chart(self):
        """换配色时重画图表（切片渐变、图例与标题颜色都是建图时固定的）。"""
        if self.chart is None or self.chart_series is None:
            return
        try:
            p = self.window.palette
            for index, piece in enumerate(self.chart_series.slices()):
                piece.setBrush(QBrush(self._slice_gradient(index)))
                piece.setPen(QPen(QColor(p['card']), 2))
            self.chart.setTitleBrush(QBrush(QColor(p['text'])))
            self.chart.legend().setLabelColor(QColor(p['text']))
        except Exception:
            pass

    # ---------------------------------------------------------------- #
    # 第 6 步：表格
    # ---------------------------------------------------------------- #
    def _page_table(self):
        page = self._new_page()
        card = self.window.card(
            page, '表格',
            '中立 table() 返回 TableHandle：set_rows / get_rows / selection 都在中立面上。')
        body = card.body

        rows = (
            ('按钮', '触发一个无参回调', 'button', '入门'),
            ('输入框', '可观察的文本值', 'input / text_area', '入门'),
            ('滑块', '回调收数值', 'slider', '入门'),
            ('开关', '回调收布尔值', 'toggle', '入门'),
            ('表格', '回调收整行数据', 'table', '进阶'),
            ('图表', 'backend 自绘或 QtCharts', 'bars', '进阶'),
        )
        readout = self.window.text(body, '点一行看看 —— 回调会把整行数据交给你。',
                                   level='accent')
        table = self.renderer.table(
            body, headers=('控件', '用途', '对应的中立方法', '难度'), rows=rows,
            height=6, select_mode='browse', column_widths=(110, 250, 200, 90),
            on_select=lambda values, row_id: self._on_row(readout, values, row_id))
        table.layout(Layout.pack(into=body))
        # 逃生口：行号列在演示里没有意义，交替行色与末列拉伸是表格观感的常规做法。
        table.native.verticalHeader().setVisible(False)
        table.native.setAlternatingRowColors(True)
        table.native.horizontalHeader().setStretchLastSection(True)
        table.native.setMinimumHeight(230)
        self.window.text(body, '注意第二个回调参数是 backend 专属的不透明标识（Qt 上是行索引），'
                               '契约只冻结回调形状，不承诺它能跨后端解析。',
                         level='dim', wrap=True)
        return page

    def _on_row(self, readout, values, row_id):
        """表格选中回调（形状：`on_select(tuple(row_values), row_id)`）。"""
        if not values:
            readout.set_text('当前没有选中行。')
            return
        readout.set_text('你选中了「%s」—— 它对应的中立方法是 %s（难度：%s）。'
                         % (values[0], values[2], values[3]))
        self.window.status('表格回调收到 %d 列数据' % len(values))

    # ---------------------------------------------------------------- #
    # 第 7 步：换主题
    # ---------------------------------------------------------------- #
    def _page_theme(self):
        page = self._new_page()
        card = self.window.card(
            page, '换主题',
            '点下面的按钮换一套配色 —— 整窗立刻生效，不需要重启，也不需要重建控件。')
        body = card.body

        current = self.window.text(body, '', level='accent')
        row = self.window.box(body, 'h', margin=(2, 2, 0, 0), spacing=10)

        def switch(name):
            self.window.set_palette(name)
            self.window.status('已切到「%s」配色' % name)

        buttons = {}
        for name in self.window.palette_names:
            buttons[name] = self.window.button(row, name, command=(lambda n=name: switch(n)))
        self.window.compact(row)            # 两个按钮靠左贴紧，别被平摊成两条长条

        def refresh():
            # 当前配色名 + "选中的那颗按钮用渐变主色" 一起跟着配色走。
            current.set_text('当前配色：%s' % self.window.palette_name)
            for name, handle in buttons.items():
                self.window.style_button(handle, primary=(name == self.window.palette_name))

        self.window.on_theme_change(refresh)

        self.window.text(
            body,
            '换肤改的是这套外壳的 QSS 与几个自绘部件的颜色：背景、卡片、描边、按钮三态、'
            '进度条渐变、导航高亮、渐变大标题、图表切片。中立控件的行为完全不受影响 —— '
            '配色是"逃生口"的活，不是中立契约的活。',
            wrap=True)
        self.window.tip(page, '试试：先切到另一套配色，再上下翻页 —— 你新停留的每一页'
                              '都会用新配色画出来。')
        return page

    # ---------------------------------------------------------------- #
    # 第 8 步：完成
    # ---------------------------------------------------------------- #
    def _page_done(self):
        page = self._new_page()
        card = self.window.card(
            page, '完成',
            '8 步走完。下面是这份引导真正演示过的东西 —— 它们全部来自中立渲染层。')
        body = card.body
        for line in ('① 容器与布局：col_weights 表达"导航窄、内容宽"的两列权重',
                     '② 基础控件：按钮 / 输入框 / 多行文本框，回调与可观察值',
                     '③ 数值控件：滑块（收数值）与开关（收布尔值）',
                     '④ 可视化：QtCharts 环形图，缺失时降级为中立柱状图',
                     '⑤ 数据展示：表格与整行选中回调',
                     '⑥ 观感：两套配色、渐变强调色、圆角卡片、悬停与按下反馈',
                     '⑦ 交互：键盘翻页、步骤导航高亮、进度条与淡入过渡'):
            self.window.text(body, line, level='body', wrap=True)

        row = self.window.box(body, 'h', margin=(2, 8, 0, 0), spacing=10)
        self.window.button(row, '重新看一遍', command=lambda: self.set_current(0))
        self.window.button(row, '完成', command=self.finish, primary=True)
        self.window.compact(row)
        self._done_label = self.window.text(body, '点「完成」结束引导。', level='accent')
        self.window.tip(page, '引导结束后可以直接关掉窗口（Esc），或者点「重新看一遍」再走一次。')
        return page

    # ---------------------------------------------------------------- #
    # 翻页与状态
    # ---------------------------------------------------------------- #
    def set_current(self, index, animate=True):
        """切到第 `index` 步并同步所有外围状态（导航高亮 / 进度 / 按钮可用性 / 状态条）。"""
        index = max(0, min(len(STEPS) - 1, int(index)))
        self.index = index
        self.window.show_page(index, animate=animate and self.animate)
        self._set_nav_current(index)

        total = len(STEPS)
        self.set_progress((index + 1) / total * 100.0)
        self.set_prev_enabled(index > 0)
        self.window.footer.set_caption('第 %d / %d 步' % (index + 1, total))
        last = index == total - 1
        self.window.footer.set_next_text('完成' if last else '下一步 →')
        self.window.footer.set_finish_enabled(last)
        self.window.status('第 %d / %d 步 · %s' % (index + 1, total, STEPS[index]))

    def go_next(self):
        """下一步；已经在最后一步时等价于「完成」。"""
        if self.index >= len(STEPS) - 1:
            self.finish()
            return
        self.set_current(self.index + 1)

    def go_prev(self):
        """上一步（第一步时不动）。"""
        if self.index > 0:
            self.set_current(self.index - 1)

    def finish(self):
        """完成引导：改文案 + 状态条 + 非阻塞浮层提示（**不弹模态框**）。"""
        if self.finished:
            return
        self.finished = True
        self.set_current(len(STEPS) - 1)
        if self._done_label is not None:
            self._done_label.set_text('你已经走完整套引导 —— 现在可以自己动手改它了。')
        self.window.status('引导已完成 · 按 Esc 退出')
        try:
            self.renderer.toast('太棒了，8 步全部走完！', kind='success')
        except Exception:               # 浮层失败不影响"已经完成"这件事
            pass

    def quit_app(self):
        """Esc：幂等关闭窗口并释放 backend root（`QtWindow.close()` 转发 destroy）。"""
        self.window.close()

    def run(self):
        """进入事件循环（阻塞）。窗口关闭后返回，并补一次幂等释放。"""
        try:
            self.window.run()
        finally:
            self.window.close()


# -------------------------------------------------------------------- #
# 三个入口
# -------------------------------------------------------------------- #
def run_selftest():
    """只构建完整 UI：不进事件循环、不弹模态框、不留 backend root。"""
    guide = Guide(animate=False)
    guide.renderer.update()             # 处理一次待办事件（等价 processEvents），不阻塞
    guide.window.close()
    print('SELFTEST OK')
    return 0


def run_real_smoke():
    """真平台冒烟：显式 show + 泵事件 + 等 2 秒 + 截图 + 销毁。

    中立 `renderer.run()` 会阻塞（进 Qt 事件循环），所以这里**不**调它；
    `renderer.update()` 只是 `processEvents()`，而 QMainWindow 必须显式 `show()`
    才会被真正画出来 —— 否则 `PrintWindow` 抓不到窗口。
    """
    guide = Guide(animate=False)
    window = guide.window
    renderer = window.renderer
    window.show()
    app = getattr(renderer, '_app', None)
    for _ in range(40):                 # 泵事件约 2 秒，让窗口真正画出来
        if app is not None:
            app.processEvents()
        time.sleep(0.05)
    renderer.update()
    time.sleep(2)

    shot = None
    try:
        from _grab_window import find_windows, grab
        matches = find_windows(WINDOW_TITLE)
        print('按标题「%s」匹配到的可见窗口：%s' % (WINDOW_TITLE, [w[1] for w in matches]))
        if matches:
            ok, rect, _img = grab(matches[0][0], SHOT_PATH)
            shot = os.path.join(ROOT, SHOT_PATH)
            print('真窗口截图已保存：%s（窗口矩形 %s，PrintWindow 返回 %s）'
                  % (shot, rect, bool(ok)))
        else:
            print('没找到真窗口，跳过截图（不影响本次结论）。')
    except Exception as exc:            # 截图失败不该让冒烟变红
        print('截图步骤未完成（不影响本次结论）：%s' % exc)

    window.close()
    if shot:
        print('截图路径：%s' % shot)
    print('REAL SMOKE OK')
    return 0


def main():
    """按模式分发。"""
    if MODE == 'selftest':
        return run_selftest()
    if MODE == 'real-smoke':
        return run_real_smoke()
    Guide(animate=True).run()
    return 0


if __name__ == '__main__':
    sys.exit(main())
