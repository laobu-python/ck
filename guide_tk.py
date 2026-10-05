# -*- coding: utf-8 -*-
"""ck1.0 轻量级 Tkinter 新手引导（guide_tk.py）。

用法:
    python guide_tk.py                打开引导窗口（零配置，双击 bat 也行）
    python guide_tk.py --selftest     只构建完整 UI（root.update()，不进 mainloop），
                                      打印 SELFTEST OK 后退出（给验收脚本用）
    python guide_tk.py --real-smoke   构建 UI + 真窗口截图（_grab_window.py）+
                                      打印 REAL SMOKE OK 后退出

为什么单独有这一版:
    仓库里有 Qt 版与混合版引导，但它们都要装 PySide6（几百 MB）。这一版**只用 Tkinter**
    （Python 自带）+ 本库自己的中立渲染层（`ck1_0/renderer/base.py` + Tk 实现），
    装好 Python 就能跑，最省资源；它同时也是「同一份中立契约在 Tk 后端的真机样本」。

实现纪律（与仓库既有约定一致）:
    * 控件一律走中立渲染层（`Renderer.label/button/input/slider/toggle/table/bars/...`），
     父容器**显式**传入（禁止隐式当前容器）；
    * 中立契约没有的视觉参数（bg/fg/relief/cursor/justify/wraplength/padx/pady 等）
     用**契约允许的逃生口** `handle.native.configure(...)` 补齐（项目已批准的 做法，
      范例见 `launcher.py`）；
    * 文案全中文，只用字母数字与字体安全符号（本文件里的圈点与箭头），
      **禁止彩色 emoji** —— Microsoft YaHei 画不出 emoji，会渲染成豆腐块方框（教训）。
"""
import os
import sys

from ck1_0.renderer.base import Layout
from gui.main_window import MainWindow
from gui.widgets import _content_parent, _renderer_of

# 中文字体统一走雅黑：ASCII 与汉字都在同一个字体里，不会出现字体拼凑的毛边。
_FONT = 'Microsoft YaHei'
_TITLE = 'ck1.0 新手引导（Tk 轻量版）'
# --real-smoke 按这个片段找真窗口。**必须足够长**：`ck1.0` 会同时命中启动器
# （标题「ck1.0 新手启动器」）和另外两版引导 —— 首版只按 `ck1.0` 找，抓到的其实是启动器窗口。
_WINDOW_MARK = '新手引导（Tk 轻量版）'
_STEP_COUNT = 8

# 8 个步骤：同一套步骤编号 / 标题，与另外两个版本的引导保持一致。
# 每项 = (标题, 一句话副标题, 正文说明)
#
# 注意：正文里**手写换行**（而不是只靠 `wraplength`）：Tk 只在**空格**处折行，一整段没有空格的
# 中文会被当成一个"长单词"整体挪到下一行 ⇒ 出现"第一行很短、第二行戳出边界"的难看排版
# （首版实拍就是这个样子）。故这里每行控制在 25 个汉字以内，wraplength 只当安全网。
STEPS = [
    ('欢迎', '认识 ck1.0 与这份轻量级引导',
     '欢迎使用 ck1.0。接下来 8 步会带你走一遍\n最常用的控件，每一步都能真的动手试。'),
    ('按钮与回调', '点一下就有人应答',
     '按钮点下去要有反应，靠的是「回调函数」\n（command）。点下面的按钮，它会被调用一次。'),
    ('输入框', '边打字边回显',
     '输入框的内容可以随时读出来。\n在下面输入时，每敲一个键，下面那行字就跟着变。'),
    ('滑块与开关', '连续值和开关量',
     '滑块给的是连续数值（比如音量 0 到 100），\n开关给的是「开 / 关」两种状态。'),
    ('图表', '用真实数据画柱状图',
     '把一串数字交给 scrollable_bars，就得到一张\n可横向滚动的柱状图。数据换了，图也跟着换。'),
    ('表格', '列出、选中、换一批数据',
     '表格用来放多行多列的数据。\n点任意一行试试，选中内容会显示在下面。'),
    ('换主题', '一键切换整套配色',
     '配色属于「主题」。点一下按钮，\n整个界面的底色和文字颜色立刻换掉，不用重启窗口。'),
    ('完成', '回顾与下一步',
     '8 步走完了。你已经见过按钮、输入框、滑块、\n开关、图表、表格和主题切换。'),
]

# 两套配色。浅色是默认；深色用于第 7 步演示「换主题立刻生效」。
# 键名是**角色**而不是控件名 —— 同一角色被一批控件共用，换主题时只改这一处。
_PALETTES = {
    'light': {
        'name': '浅色',
        'app_bg': '#eef1f6', 'card': '#ffffff', 'field': '#f7f9fc',
        'fg': '#1f2933', 'muted': '#6b7280',
        'accent': '#2f6fed', 'accent_dark': '#1f57c9', 'accent_fg': '#ffffff',
        'nav_bg': '#e3e8f0', 'border': '#cfd7e3', 'status_bg': '#dde3ec',
    },
    'dark': {
        'name': '深色',
        'app_bg': '#171d26', 'card': '#212936', 'field': '#151b24',
        'fg': '#eef2f7', 'muted': '#9aa7b8',
        'accent': '#4d8df6', 'accent_dark': '#3a76d8', 'accent_fg': '#ffffff',
        'nav_bg': '#2b3546', 'border': '#3d4859', 'status_bg': '#12171f',
    },
}

_BAR_DATA = [
    [42, 68, 55, 91, 37, 74, 63, 88],
    [80, 25, 96, 51, 44, 70, 33, 62],
    [58, 58, 12, 87, 74, 29, 95, 41],
]

_TABLE_HEADERS = ['控件', '作用', '交互方式']
_TABLE_DATA = [
    [('标签 label', '显示一行文字', '只看不点'),
     ('按钮 button', '点一下触发回调', '鼠标左键单击'),
     ('输入框 input', '读入一行文字', '键盘输入'),
     ('滑块 slider', '选一个连续数值', '拖动滑块'),
     ('开关 toggle', '开 / 关两种状态', '点击轨道')],
    [('柱状图 bars', '把数字画成柱子', '横向滚动查看'),
     ('表格 table', '多行多列数据', '点行选中'),
     ('进度条 progress', '显示完成度', '程序更新'),
     ('状态栏 status_bar', '一行提示文字', '程序更新'),
     ('选项卡 notebook', '分页放内容', '点击页签')],
]


class GuideTk:
    """轻量级 Tkinter 新手引导。

    设计要点:
      * 界面自上而下四段：头部标题 / 步骤条 / 内容区 / 底部导航，另有窗口级状态栏；
      * 8 个步骤各自是一个**常驻**容器（切步只做 pack / pack_forget），
        这样输入框里已经敲的字、滑块位置、表格选中项在来回切步时**不会丢**；
      * 所有控件的配色登记进 `self._themed`，第 7 步换主题时统一重刷 —— 一处改、全局生效。
    """

    def __init__(self):
        self.app = MainWindow(_TITLE, 1000, 760)
        self.app.center_window()
        self.r = _renderer_of(self.app)
        self.content = _content_parent(self.app)

        self.step = 0
        self.palette_name = 'light'
        self.palette = _PALETTES[self.palette_name]

        # [原生控件, 角色]：换主题时按角色统一重刷（角色语义见 _role_colors）
        self._themed = []
        self._nav_buttons = []          # 步骤条的原生按钮（按当前步高亮）
        self._step_frames = []          # 8 个步骤的中立容器句柄

        # 演示状态：交互只改这些值，再刷新界面
        self.click_count = 0
        self.bars_variant = 0
        self.table_variant = 0
        self.bars_handle = None
        self._chart_parent = None

        self._build()
        self._apply_palette()
        self.goto(0)

    # ------------------------------------------------------------------ #
    # 搭骨架
    # ------------------------------------------------------------------ #
    def _build(self):
        """按「头部 / 步骤条 / 内容区 / 底部导航 / 状态栏」把整窗搭起来。"""
        self._build_header()
        self._build_navbar()
        self._build_body()
        self._build_footer()
        # 状态栏是**窗口级**部件：create_status_bar 落在 root 底部的 statusbar_container 里
        self.status_handle, self.set_status = self.app.create_status_bar(
            '就绪：点上面的步骤条也可以直接跳转')
        self._themed.append([self.status_handle.native, 'status'])

    def _build_header(self):
        head = self.r.container(self.content, Layout.pack(fill='x'))
        self._themed.append([head.native, 'card'])
        self._label(head, 'ck1.0 新手引导', role='title', size=22, bold=True, pady=(16, 2))
        self._label(head, '八步走完常用控件：按钮 · 输入框 · 滑块与开关 · 图表 · 表格 · 主题',
                    role='muted', size=10, pady=(0, 4))
        self._label(head, '这一版只用 Tkinter，装好 Python 就能跑，最省资源（不需要 PySide6）。',
                    role='hi', size=10, bold=True, wrap=900, pady=(0, 14))

    def _build_navbar(self):
        bar = self.r.container(self.content, Layout.pack(fill='x'))
        self._themed.append([bar.native, 'nav_bar'])
        for i, (title, _sub, _text) in enumerate(STEPS):
            # 闭包陷阱：循环变量 i 必须在默认参数里定格，否则 8 个按钮都会跳到第 8 步。
            # 宽度 9 字符 + 字号 9 + padx 2：8 个按钮并排后仍留得下窗口宽度（首版用
            # width=10/size=10 时第 8 个按钮被右边缘裁掉了半截，实拍发现）。
            handle = self._button(bar, '%d %s' % (i + 1, title),
                                  (lambda idx: (lambda: self.goto(idx)))(i),
                                  role='nav', width=9, size=9, bold=False,
                                  pack=Layout.pack(side='left', padx=2, pady=6))
            self._nav_buttons.append(handle.native)

    def _build_body(self):
        self.body = self.r.container(self.content, Layout.pack(fill='both', expand=True))
        native = self.body.native
        self._themed.append([native, 'card'])
        # 逃生口：中立契约没有「固定高度容器」，而步骤切换时下方按钮不该上下跳动
        # ⇒ 用 pack_propagate(False) 把内容区高度钉住（Tk 专属手法，Qt 侧对应
        # setFixedHeight；属 同族的视觉缺口，登记在批报告里）。
        # 高度取 400（Tk 的 Frame height 单位是**像素**，且字号按点数被 DPI 放大 1.25 倍）：
        # 首个版本写 360 时，内容最长的第 8 步末尾被底部按钮压掉了一行（实拍发现）。
        native.configure(height=400)
        native.pack_propagate(False)

        builders = [self._step_welcome, self._step_button, self._step_input,
                    self._step_slider, self._step_chart, self._step_table,
                    self._step_theme, self._step_done]
        for i, build in enumerate(builders):
            step = self.r.container(self.body, None)
            step.native.pack_forget()          # 先全部藏起来，由 goto() 决定显示哪一个
            self._themed.append([step.native, 'card'])
            self._step_frames.append(step)
            self._step_heading(step, i)
            build(step)

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
        # progress() 自己把内部 Frame 按整个宽度摆在父容器里；这里重新摆成左侧流，
        # 与三个按钮同一行（layout() 作用在它的 Frame 上，见 TkProgressHandle）。
        self.progress_handle.layout(Layout.pack(side='left', padx=(18, 8), pady=10))
        self._themed.append([self.progress_handle.native.master, 'card'])
        self._themed.append([self.progress_handle.native, 'card'])
        self.progress_text = self._label(foot, '第 1 / 8 步', role='muted', size=10,
                                         side='left', padx=6, pady=10)

    # ------------------------------------------------------------------ #
    # 每步的内容（都真的能操作）
    # ------------------------------------------------------------------ #
    def _step_heading(self, parent, index):
        title, sub, _text = STEPS[index]
        self._label(parent, '第 %d 步 · %s' % (index + 1, title), role='title',
                    size=14, bold=True, pady=(16, 2))
        self._label(parent, sub, role='muted', size=10, pady=(0, 8))

    def _step_welcome(self, parent):
        self._label(parent, STEPS[0][2], role='text', size=11, wrap=900, pady=(0, 8))
        self._label(parent, '轻量级：只用 Tkinter 和 ck1.0 自带的中立渲染层，\n'
                            '装好 Python 就能跑，最省资源（不需要 PySide6）。',
                    role='hi', size=11, bold=True, wrap=900, pady=(0, 12))
        self._button(parent, '开始吧 →', lambda: self.goto(1), role='primary', width=12,
                     pack=Layout.pack(anchor='w', padx=26, pady=(0, 10)))

    def _step_button(self, parent):
        self._label(parent, STEPS[1][2], role='text', size=11, wrap=900, pady=(0, 12))
        self._button(parent, '点我一下', self._on_click, role='primary', width=12,
                     pack=Layout.pack(anchor='w', padx=26, pady=(0, 8)))
        self.click_label = self._label(parent, '按钮还没有被点过。', role='muted', size=11,
                                       pady=(0, 6))

    def _step_input(self, parent):
        self._label(parent, STEPS[2][2], role='text', size=11, wrap=900, pady=(0, 6))
        self.input_handle = self.r.input(parent, hint='在这里输入你的名字', width=30,
                                         family=_FONT, size=11)
        # 输入框句柄包的就是 Entry 本身、且它的 parent 就是本步骤容器 ⇒ 直接 layout 安全。
        # （pack 的默认 anchor 是 center ⇒ 不重排的话输入框会飘到中间去。）
        self.input_handle.layout(Layout.pack(anchor='w', padx=26, pady=(4, 0)))
        self._themed.append([self.input_handle.native, 'field'])
        self.echo_label = self._label(parent, '实时回显：（还没有输入）', role='muted', size=11,
                                      pady=(10, 8))
        # 中立 `Value.on_change`：用户按键与程序化 set() 都会回调，无需直接 bind Tk 事件
        self.input_handle.value.on_change(self._on_typed)
        self._button(parent, '填入示例文本', self._fill_sample, role='ghost', width=12,
                     pack=Layout.pack(anchor='w', padx=26, pady=(0, 8)))

    def _step_slider(self, parent):
        self._label(parent, STEPS[3][2], role='text', size=11, wrap=900, pady=(0, 4))
        self.slider_handle = self.r.slider(parent, from_=0, to=100, default=40, resolution=1,
                                           width=320, on_change=self._on_volume)
        # 注意：这里**不能**用 `slider_handle.layout(...)`：滑块的句柄包的是**内部那个
        # `ttk.Scale`**（不是外框），对它 layout 会把 Scale 从"左滑轨 + 右数值"这一行里
        # 拆出来（首版实拍：滑轨跑到上面、数值掉到下面）。要摆的是**外框**
        # ⇒ 走逃生口直接 pack 原生 master。
        try:
            self.slider_handle.native.master.pack(anchor='w', padx=26, pady=(6, 0))
        except Exception:
            pass
        self._themed.append([self.slider_handle.native.master, 'card'])
        self.volume_label = self._label(parent, '当前音量：40', role='text', size=11, pady=(8, 4))
        self.toggle_handle = self.r.toggle(parent, '开关演示：静音提示', default=False,
                                           command=self._on_toggle)
        self.toggle_handle.layout(Layout.pack(anchor='w', padx=26))
        self.toggle_label = self._label(parent, '开关状态：关', role='muted', size=11, pady=(4, 6))

    def _step_chart(self, parent):
        self._label(parent, STEPS[4][2], role='text', size=11, wrap=900, pady=(0, 6))
        self._button(parent, '换一组数据', self._regen_bars, role='ghost', width=12,
                     pack=Layout.pack(anchor='w', padx=26, pady=(0, 4)))
        self.bars_label = self._label(parent, '当前数据：%s' % self._data_text(0),
                                      role='muted', size=10, pady=(0, 4))
        self._chart_parent = parent
        self.bars_handle = self._make_bars()

    def _step_table(self, parent):
        self._label(parent, STEPS[5][2], role='text', size=11, wrap=900, pady=(0, 6))
        self.table_handle = self.r.table(parent, _TABLE_HEADERS, rows=_TABLE_DATA[0],
                                         height=5, on_select=self._on_row,
                                         column_widths=(150, 200, 150))
        # 同滑块：表格句柄包的是内部的 `ttk.Treeview`，外框（带纵向滚动条）是它的 master
        # ⇒ 摆位与上色都对外框做（逃生口）。
        try:
            self.table_handle.native.master.pack(anchor='w', padx=26, pady=(2, 0))
        except Exception:
            pass
        self._themed.append([self.table_handle.native.master, 'card'])
        self._themed.append([self.table_handle.native, 'tree'])
        self.table_label = self._label(parent, '选中行：（还没有选）', role='muted', size=11,
                                       pady=(10, 6))
        self._button(parent, '换一批数据', self._regen_table, role='ghost', width=12,
                     pack=Layout.pack(anchor='w', padx=26, pady=(0, 8)))

    def _step_theme(self, parent):
        self._label(parent, STEPS[6][2], role='text', size=11, wrap=900, pady=(0, 10))
        row = self._row(parent)
        self._button(row, '浅色主题', lambda: self._set_palette('light'), role='primary',
                     width=10, pack=Layout.pack(side='left', padx=(0, 8), pady=6))
        self._button(row, '深色主题', lambda: self._set_palette('dark'), role='primary',
                     width=10, pack=Layout.pack(side='left', padx=0, pady=6))
        self.theme_label = self._label(parent, '当前主题：浅色', role='hi', size=11, bold=True,
                                       pady=(10, 6))
        self._label(parent, '换主题改的是「角色 → 颜色」这张表，控件本身一个都不用重建。',
                    role='muted', size=10, wrap=900, pady=(0, 6))

    def _step_done(self, parent):
        self._label(parent, STEPS[7][2], role='text', size=11, wrap=900, pady=(0, 6))
        self._label(parent, '这一版不依赖 PySide6：只用 Tkinter\n'
                            '和 ck1.0 自带的中立渲染层。',
                    role='hi', size=11, bold=True, wrap=900, pady=(0, 12))
        row = self._row(parent)
        self._button(row, '重新开始', lambda: self.goto(0), role='ghost', width=10,
                     pack=Layout.pack(side='left', padx=(0, 8), pady=6))
        self._button(row, '退出引导', self.app.close, role='primary', width=10,
                     pack=Layout.pack(side='left', padx=0, pady=6))
        self._label(parent, '想继续探索：运行 python main.py 看完整演示，\n'
                            'python launcher.py 挑入口。',
                    role='muted', size=10, wrap=900, pady=(12, 6))

    # ------------------------------------------------------------------ #
    # 交互回调
    # ------------------------------------------------------------------ #
    def _on_click(self):
        self.click_count += 1
        self.click_label.set_text('回调已经跑了 %d 次 —— 按钮的 command 就是回调函数。'
                                  % self.click_count)
        self._set_status('按钮回调触发：第 %d 次' % self.click_count)
        if self.click_count == 1:
            self.app.show_toast('按钮回调跑起来了', kind='success')

    def _on_typed(self, value):
        self.echo_label.set_text('实时回显：%s' % (value if value else '（还没有输入）'))
        self._set_status('输入框内容长度：%d' % len(value or ''))

    def _fill_sample(self):
        self.input_handle.value.set('张三')
        self._set_status('已把「张三」写进输入框（set() 也会触发回显）')

    def _on_volume(self, value):
        self.volume_label.set_text('当前音量：%d' % int(round(value)))
        self._set_status('滑块拖动中：音量 %d' % int(round(value)))

    def _on_toggle(self, value):
        self.toggle_label.set_text('开关状态：%s' % ('开' if value else '关'))
        self._set_status('开关被切成「%s」' % ('开' if value else '关'))

    def _regen_bars(self):
        self.bars_variant = (self.bars_variant + 1) % len(_BAR_DATA)
        if self.bars_handle is not None and self.bars_handle.exists():
            self.bars_handle.destroy()
        self.bars_handle = self._make_bars()
        self.bars_label.set_text('当前数据：%s' % self._data_text(self.bars_variant))
        self._set_status('图表已换成第 %d 组数据' % (self.bars_variant + 1))

    def _regen_table(self):
        self.table_variant = (self.table_variant + 1) % len(_TABLE_DATA)
        self.table_handle.set_rows(_TABLE_DATA[self.table_variant])
        self._set_status('表格已换成第 %d 批数据' % (self.table_variant + 1))

    def _on_row(self, values, _row_id):
        text = ' ｜ '.join(str(v) for v in values) if values else '（空行）'
        self.table_label.set_text('选中行：%s' % text)
        self._set_status('表格选中：%s' % text)

    def _finish(self):
        if self.step < _STEP_COUNT - 1:
            self.goto(_STEP_COUNT - 1)
        else:
            self.app.show_toast('引导完成，感谢使用 ck1.0', kind='success')
            self._set_status('引导完成：想继续探索就运行 python main.py')

    # ------------------------------------------------------------------ #
    # 步骤切换与进度
    # ------------------------------------------------------------------ #
    def step_delta(self, delta):
        self.goto(self.step + int(delta))

    def goto(self, index):
        """切到第 `index` 步（0 基）。越界会被夹到 [0, 7]，不抛异常。"""
        index = max(0, min(_STEP_COUNT - 1, int(index)))
        self.step = index
        for i, frame in enumerate(self._step_frames):
            if i == index:
                frame.native.pack(fill='both', expand=True)
            else:
                frame.native.pack_forget()
        # 首 / 末步禁用对应按钮（中立 set_enabled 只挡用户交互，不动值）
        self.prev_handle.set_enabled(index > 0)
        self.next_handle.set_enabled(index < _STEP_COUNT - 1)
        self.progress_handle.update(index + 1)
        self.progress_text.set_text('第 %d / %d 步 · %s' % (index + 1, _STEP_COUNT,
                                                            STEPS[index][0]))
        self._paint_nav()
        self._set_status('第 %d 步：%s —— %s' % (index + 1, STEPS[index][0], STEPS[index][1]))

    # ------------------------------------------------------------------ #
    # 主题：角色 → 颜色，一处改、全局生效
    # ------------------------------------------------------------------ #
    def _set_palette(self, name):
        self.palette_name = name if name in _PALETTES else 'light'
        self._apply_palette()
        self.theme_label.set_text('当前主题：%s' % self.palette['name'])
        self._set_status('主题已切换为「%s」，界面立刻生效，不用重启窗口' % self.palette['name'])
        self.app.show_toast('已切换到%s主题' % self.palette['name'], kind='success')

    def _apply_palette(self):
        self.palette = _PALETTES[self.palette_name]
        p = self.palette
        # 窗口骨架（Btk 建的原生容器）不由 _themed 管理，这里单独刷一遍
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
        """按角色给**原生**控件上色（逃生口）。

        为什么要按 `winfo_class()` 分派：同一个角色落到 Tk 的 Frame / Label / Button /
        Entry 上要设的选项各不相同（Frame 只有 `bg`，Label 还有 `fg`，Button 还要按下态）；
       中立契约里没有这些东西 —— 这正是 登记的视觉缺口。
        """
        bg, fg, abg, afg = self._role_colors(role)
        try:
            cls = native.winfo_class()
        except Exception:
            return                                  # 控件已销毁（例如图表重建）
        try:
            if cls in ('Frame', 'Toplevel', 'Canvas', 'Labelframe'):
                native.configure(bg=bg)
            elif cls == 'Label':
                native.configure(bg=bg, fg=fg if fg is not None else self.palette['fg'])
            elif cls == 'Button':
                native.configure(bg=bg, fg=fg, activebackground=abg or bg,
                                 activeforeground=afg or fg, relief='flat', bd=0)
            elif cls == 'Entry':
                native.configure(bg=bg, fg=fg, insertbackground=fg,
                                 relief='flat', highlightthickness=1,
                                 highlightbackground=self.palette['border'],
                                 highlightcolor=self.palette['accent'])
            elif cls == 'Scrollbar':
                native.configure(bg=self.palette['border'], troughcolor=self.palette['nav_bg'],
                                 activebackground=self.palette['accent'], bd=0)
            # ttk 控件（Treeview / Scale / Combobox）不吃 bg/fg ⇒ 交给 _paint_ttk
        except Exception:
            pass

    def _paint_ttk(self):
        """ttk 控件（表格是唯一的 ttk 大头）靠 `ttk.Style` 上色。

        `Btk` 建窗口时就持有一个 `ttk.Style()`（`app._ttk_style`），直接用它的单例；
        这样不必在引导里再 `import tkinter.ttk`，与 `main.py` 的既有写法一致。
        """
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

    # ------------------------------------------------------------------ #
    # 自检（给 --selftest 用；不进 mainloop）
    # ------------------------------------------------------------------ #
    def selfcheck(self):
        """把"用户真的动手"会走的回调各跑一遍。

        为什么放进 `--selftest`：只把控件建出来，回调里的拼写错误要等用户点下去才暴露；
        这里逐条调用一遍，`--selftest` 才真的能证明"每一步都能用"。
        仍然**不进 mainloop**，只做同步调用 + `root.update()`。
        """
        self._on_click()
        self._on_typed('测试')
        self._fill_sample()
        self._on_volume(66.6)
        self._on_toggle(True)
        self._regen_bars()
        self._regen_table()
        self._on_row(('标签 label', '显示一行文字', '只看不点'), 'i001')
        self.step_delta(1)
        self.step_delta(-1)
        self._set_palette('dark')
        self._set_palette('light')
        self._finish()

    # ------------------------------------------------------------------ #
    # 小工具：创建控件并登记配色
    # ------------------------------------------------------------------ #
    def _label(self, parent, text, role='text', size=11, bold=False, wrap=None,
               padx=26, pady=(0, 6), side='top'):
        handle = self.r.label(parent, text, family=_FONT, size=size, bold=bold)
        native = handle.native
        native.configure(justify='left', anchor='w')
        if wrap:
            native.configure(wraplength=wrap)       # 中立契约无 wraplength
        handle.layout(Layout.pack(side=side, anchor='w', padx=padx, pady=pady,
                                  fill=('x' if wrap else None)))
        self._themed.append([native, role])
        return handle

    def _button(self, parent, text, command, role='primary', width=12, size=11,
                bold=True, pack=None):
        handle = self.r.button(parent, text, command=command, family=_FONT, size=size,
                               bold=bold, width=width, height=1)
        native = handle.native
        # 逃生口：扁平化 + 手型光标（中立契约只给文字/字体/宽度，见 / launcher.py 范例）
        native.configure(cursor='hand2', pady=4)
        handle.layout(pack if pack is not None else Layout.pack(anchor='w', padx=26, pady=6))
        self._themed.append([native, role])
        return handle

    def _row(self, parent, padx=26, pady=(0, 6)):
        """一行水平摆放的容器（把 side='left' 的控件与上面的纵向流隔开）。"""
        row = self.r.container(parent, Layout.pack(anchor='w', padx=padx, pady=pady))
        self._themed.append([row.native, 'card'])
        return row

    def _make_bars(self):
        data = _BAR_DATA[self.bars_variant]
        handle = self.r.bars(self._chart_parent, data, canvas_width=620, canvas_height=190,
                             label_rotation=0, show_bg_stripes=True)
        if handle is not None:
            # 柱状图句柄包的是**外层滚动容器** ⇒ `layout()` 摆的就是它自己，这里安全
            # （与滑块/表格不同：那两者的句柄包的是内部控件）。
            handle.layout(Layout.pack(anchor='w', padx=26, pady=(0, 6)))
        return handle

    @staticmethod
    def _data_text(variant):
        return ' · '.join(str(v) for v in _BAR_DATA[variant % len(_BAR_DATA)])

    def _set_status(self, text):
        self.set_status(text)


# ---------------------------------------------------------------------- #
# 入口
# ---------------------------------------------------------------------- #
def _run_selftest():
    """只构建完整 UI（不进 mainloop）：建窗 -> 逐个回调走一遍 -> `update()` 渲染。

   结束时**必须** `close()`：要求 backend root 进程内唯一，只销毁 Tk 窗口而不释放
    Renderer 会留下失效的单例登记，同一进程里再建窗口就会撞上那句看不懂的英文 TclError。
    """
    guide = GuideTk()
    try:
        guide.app.root.update()                 # 真的建完并渲染一遍（不进事件循环）
        # 再把 8 个步骤、两套主题、以及每个交互回调都走一遍：
        # 这几条最容易在"没人点"的情况下悄悄坏掉。
        guide.selfcheck()
        for index in range(_STEP_COUNT):
            guide.goto(index)
        guide.goto(0)
        guide.app.root.update()
        print('SELFTEST OK')
    finally:
        guide.app.close()


def _largest_window(grabber, windows):
    """在标题匹配的窗口里挑**面积最大**的那个，返回 `(hwnd, title)` 或 `None`。

    为什么需要挑：引导弹出的 Toast 气泡也是一个 Toplevel，而 Tk **让它沿用同一个标题**
    ⇒ `find_windows(_WINDOW_MARK)` 会同时命中「主窗口」和「气泡」两个 HWND，枚举顺序还
    不稳定（实测：只取 `windows[0]` 时真的抓到了那块 196x47 的气泡，主窗口反而没抓到）。
    主窗口一定是其中面积最大的那个。
    """
    import ctypes                                     # 标准库；只在截图这一支用到
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
    """真窗口冒烟：建窗 -> update -> 截图 -> 释放 backend root。

    截图复用仓库现成的 `_grab_window.py`（PrintWindow，抓的是窗口自己的像素，
    桌面遮挡不影响结果）。截不到只打印一行中文说明，**不**让冒烟失败。
    """
    shot_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_guide_tk_shot.png')
    # 先导入截图工具：它在导入期调用 SetProcessDPIAware()，必须在 Tk 建窗前生效，
    # 否则窗口按系统缩放建好后进程才变 DPI 感知，截出来的尺寸会与窗口不一致。
    grabber = None
    try:
        import _grab_window as grabber
    except Exception as exc:                                    # 缺 Pillow / 文件不在场
        print('提示：无法导入截图工具 _grab_window.py（%s），本次跳过截图。' % exc)

    guide = GuideTk()
    try:
        guide.app.root.update()
        import time
        time.sleep(2)                                           # 留出窗口真正上屏的时间
        guide.app.root.update()
        if grabber is not None:
            try:
                windows = grabber.find_windows(_WINDOW_MARK)
                target = _largest_window(grabber, windows)
                if target is not None:
                    hwnd, title = target
                    ok, rect, _img = grabber.grab(hwnd, shot_path)
                    print('已截图：%s（窗口 %r，PrintWindow=%s，矩形 %s）'
                          % (shot_path, title, bool(ok), rect))
                else:
                    print('未找到标题含「%s」的可见窗口，本次跳过截图。' % _WINDOW_MARK)
            except Exception as exc:
                print('截图失败（已忽略，不影响冒烟结论）：%s' % exc)
        print('REAL SMOKE OK')
    finally:
        guide.app.close()


def main():
    argv = sys.argv[1:]
    if '--selftest' in argv:
        _run_selftest()
        return 0
    if '--real-smoke' in argv:
        _run_real_smoke()
        return 0
    guide = GuideTk()
    guide.app.run()                                 # 拥有事件循环，直到用户关窗
    return 0


if __name__ == '__main__':
    sys.exit(main())
