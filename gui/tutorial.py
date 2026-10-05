# gui/tutorial.py —— 新手交互式引导教程
"""新手交互式引导教程（TutorialWindow）

以「一页一个组件」的方式，带纯新手逐个认识 ck1.0 的常用组件。
每一页都包含一个可以真实操作的控件示例，并配一句人话解释，
全程不需要写代码，只需要点击鼠标。
"""
import tkinter as tk
from tkinter import ttk

from .advanced_widgets import AdvancedWidgetMixin, _as_handle
from .widgets import WidgetMixin, _content_parent, _renderer_of

try:                                    # 脚本模式：cwd = 项目根
    from ck1_0.renderer.base import Layout
except ImportError:                     # 包模式：本文件即 ck1_0.gui.tutorial
    from ..renderer.base import Layout

try:                                    # 脚本模式：cwd = 项目根，gui 为顶层包
    from ck1_0.core.theme import Theme
except ImportError:                     # 包模式：本文件即 ck1_0.gui.tutorial
    from ..core.theme import Theme


class _DemoCtx:
    """轻量上下文：让教程页可以调用 ck1.0 的组件方法。

    教程页只需要 root 和 scrollable_frame；
    未定义的属性自动转发给宿主窗口（如 show_toast / ask_save_path）。
    """

    def __init__(self, host, parent):
        self.host = host
        self.root = host.root
        self.scrollable_frame = parent
        # **修 （实测发现）**：`_content_parent(host)` **优先看 `host._content`**，
        # 而本类原本没有该属性 ⇒ `__getattr__` 把它转发给了**宿主窗口**（MainWindow）⇒
        # 教程页的示例控件（`buttonx`/`label_ck`/`input_box`/各 `create_*`）自 起被建到
        # **主窗口**里，而不是教程窗口自己的演示区（`_smoke_test.py` 只测"页面构建不抛"，
        # 所以一直没有暴露）。这里显式把演示区包成中立内容句柄。
        self._content = type(_renderer_of(host).root)(parent)
        self.main_canvas = None

    def __getattr__(self, name):
        return getattr(self.host, name)


class TutorialWindow:
    """分页交互式教程窗口。

    用法:
        TutorialWindow(main_window)  # 传入 MainWindow 实例即可
    """

    def __init__(self, host, theme=None):
        self.host = host
        self.root = host.root
        # 语义 token 表：显式传入 > 宿主已有 theme > 基线主题（不覆盖 root）
        if theme is not None:
            self.theme = theme
        elif getattr(host, 'theme', None) is not None:
            self.theme = host.theme
        else:
            self.theme = Theme.light()

        self.win = tk.Toplevel(self.root)
        self.win.title(self.theme.tutorial_window_title)
        self.win.geometry('%dx%d' % self.theme.tutorial_window_size)
        self.win.transient(self.root)

        self.page_index = 0
        self.pages = self._build_pages()

        # 顶部进度条
        self.progress = ttk.Progressbar(self.win, maximum=len(self.pages), value=1)
        self.progress.pack(fill='x', padx=self.theme.tutorial_progress_padx,
                           pady=self.theme.tutorial_progress_pady)
        self.progress_label = tk.Label(self.win, text='', fg=self.theme.tutorial_progress_color,
                                       font=self.theme.tutorial_progress)
        self.progress_label.pack()

        # 卡片区
        self.card = tk.Frame(self.win, bg=self.theme.tutorial_card_background,
                             relief=self.theme.tutorial_card_relief,
                             bd=self.theme.tutorial_card_borderwidth)
        self.card.pack(fill='both', expand=True, padx=self.theme.tutorial_card_padx,
                       pady=self.theme.tutorial_card_pady)

        self.title_label = tk.Label(self.card, text='', font=self.theme.tutorial_title,
                                    bg=self.theme.tutorial_title_background)
        self.title_label.pack(pady=self.theme.tutorial_title_pady)
        self.desc_label = tk.Label(self.card, text='', font=self.theme.tutorial_desc,
                                   bg=self.theme.tutorial_title_background,
                                   fg=self.theme.tutorial_desc_color, justify='left',
                                   wraplength=self.theme.tutorial_desc_wraplength)
        self.desc_label.pack(padx=self.theme.tutorial_desc_padx, pady=self.theme.tutorial_desc_pady)

        self.demo_area = tk.Frame(self.card, bg=self.theme.tutorial_demo_background)
        self.demo_area.pack(fill='both', expand=True, padx=self.theme.tutorial_demo_padx,
                            pady=self.theme.tutorial_demo_pady)

        # 底部按钮
        btns = tk.Frame(self.win)
        btns.pack(pady=self.theme.tutorial_navigation_pady)
        self.prev_btn = tk.Button(btns, text=self.theme.tutorial_prev_text,
                                  width=self.theme.tutorial_nav_button_width,
                                  command=self.prev_page)
        self.prev_btn.pack(side='left', padx=self.theme.tutorial_nav_padx)
        self.next_btn = tk.Button(btns, text=self.theme.tutorial_next_text,
                                  width=self.theme.tutorial_nav_button_width,
                                  command=self.next_page)
        self.next_btn.pack(side='left', padx=self.theme.tutorial_nav_padx)
        tk.Button(btns, text='关闭', width=self.theme.tutorial_nav_close_width,
                  command=self.win.destroy).pack(side='left', padx=self.theme.tutorial_nav_padx)

        self.show_page(0)

    # ------------------------------------------------------------------
    # 页面定义
    # ------------------------------------------------------------------
    def _build_pages(self):
        W = WidgetMixin
        A = AdvancedWidgetMixin
        return [
            {
                'title': '1. 欢迎',
                'desc': ('欢迎使用 ck1.0 GUI 库！\n\n'
                         '这是一个用 Python 写的小型桌面程序库。\n'
                         '这个教程会「一页一个组件」带你认识常用控件，每一页都可以直接操作。\n\n'
                         '点击右下角的「下一步 →」开始吧！'),
                'build': lambda ctx, f: W.label_ck(ctx, '你好，新手朋友！', tsize=22),
            },
            {
                'title': '2. 按钮',
                'desc': ('按钮是程序里最常见的元素：点击它，程序就执行一个动作。\n'
                         '点一下下面的按钮试试。'),
                'build': self._page_button,
            },
            {
                'title': '3. 输入框',
                'desc': ('输入框用来接收你输入的文字。\n'
                         '灰色的文字是提示，点击输入框会自动清空；\n'
                         '输入后点「读取输入」，程序就能拿到你写的内容。'),
                'build': self._page_input,
            },
            {
                'title': '4. 下拉框与滑块',
                'desc': ('下拉框：点一下弹出选项，也可以直接输入（会自动帮你补全）。\n'
                         '滑块：拖动即可改变数值，右侧实时显示当前值。'),
                'build': self._page_combo_slider,
            },
            {
                'title': '5. 开关与复选框',
                'desc': ('开关（Switch）是移动端风格的开关按钮，点击切换开/关。\n'
                         '复选框（Checkbox）适合「要不要勾选」的场景，可以多选。'),
                'build': self._page_toggle,
            },
            {
                'title': '6. 进度条',
                'desc': ('进度条用来显示任务的完成程度。\n'
                         '点下面的按钮，进度会一点一点前进。'),
                'build': self._page_progress,
            },
            {
                'title': '7. 表格与导出',
                'desc': ('表格用来展示成行成列的数据，列宽会自动适配内容。\n'
                         '点「导出为 CSV」，把表格保存成文件——\n'
                         '保存后可以用 Excel 打开（中文不会乱码哦）。'),
                'build': self._page_table,
            },
            {
                'title': '8. 智能表单',
                'desc': ('表单是「填信息」的界面：姓名、年龄、性别……\n'
                         '只需要一行描述，程序就能自动生成整个表单，还能一键读取所有内容。'),
                'build': self._page_form,
            },
            {
                'title': '9. 完成',
                'desc': ('恭喜！你已经认识了 ck1.0 的主要组件。\n\n'
                         '接下来你可以：\n'
                         '• 关闭本窗口，运行完整演示（main.py）\n'
                         '• 打开「新手教程.md」学习怎么自己改代码\n'
                         '• 直接修改 main.py 里的文字和数字，点运行看看变化'),
                'build': self._page_done,
            },
        ]

    # ---- 各页面的示例内容 ----
    def _page_button(self, ctx, frame):
        def clicked():
            ctx.show_toast('你点击了按钮！', kind='success')

        WidgetMixin.buttonx(ctx, '点我试试', commandname=clicked)
        WidgetMixin.label_ck(ctx, '（点击后按钮下方会短暂变化，并弹出提示）', tsize=11)

    def _page_input(self, ctx, frame):
        entry = WidgetMixin.input_box(ctx, hint='在这里输入点什么…')

        def read():
            # `input_box` 返回中立句柄 ⇒ 取值经中立 `Value`；
            # 顺带修掉首版的占位符污染（未输入时 `get()` 曾返回占位符文本）。
            value = entry.value.get()
            ctx.show_toast(f'你输入了：{value}', kind='info')

        _r = _renderer_of(ctx)
        _r.button(_as_handle(_r, frame), '读取输入', command=read).layout(
            Layout.pack(pady=self.theme.tutorial_demo_button_pady))

    def _page_combo_slider(self, ctx, frame):
        AdvancedWidgetMixin.create_combo_box(
            ctx, ['苹果', '香蕉', '西瓜', '葡萄', '橘子'], default='苹果',
            on_select=lambda v: ctx.show_toast(f'选择了：{v}', kind='success'))

        # 数值标签改走 renderer 的中立 `label(...)`；**改文本用中立的 `set_text()`**
        # （首版是 `val_lbl.config(text=...)`）。
        # 注：中立 `label()` 目前**没有** `background`/`justify` 两个视觉参数（已登记）⇒
        # 配色沿用**契约允许的逃生口** `handle.native` 补一次，**外观与首版逐字相同**。
        _r = _renderer_of(ctx)
        _fam, _size = self.theme.tutorial_demo_label
        val_lbl = _r.label(_as_handle(_r, frame), '音量：30', family=_fam, size=_size)
        val_lbl.native.configure(bg=self.theme.tutorial_demo_background)
        val_lbl.layout(Layout.pack(pady=(8, 0)))
        AdvancedWidgetMixin.create_slider(
            ctx, 0, 100, default=30, label='拖动我',
            on_change=lambda v: val_lbl.set_text(f'音量：{v:g}'))

    def _page_toggle(self, ctx, frame):
        def on_toggle(v):
            ctx.show_toast(f'开关：{"开" if v else "关"}', kind='success' if v else 'info')

        AdvancedWidgetMixin.create_toggle_switch(ctx, '试试这个开关', default=False, command=on_toggle)
        AdvancedWidgetMixin.create_checkbox(ctx, '还有复选框', default=True, command=lambda: None)

    def _page_progress(self, ctx, frame):
        update = AdvancedWidgetMixin.create_progress_bar(
            ctx, max_value=100, width=self.theme.tutorial_demo_progress_width)
        state = {'v': 0}

        def step():
            state['v'] = min(100, state['v'] + 20)
            update(state['v'])

        _r = _renderer_of(ctx)
        _r.button(_as_handle(_r, frame), '前进 20%', command=step).layout(
            Layout.pack(pady=self.theme.tutorial_demo_button_pady))

    def _page_table(self, ctx, frame):
        _, tree = AdvancedWidgetMixin.create_table(
            ctx, headers=['科目', '分数'],
            rows=[('语文', 92), ('数学', 88), ('英语', 95), ('科学', 79)])

        def export():
            path = AdvancedWidgetMixin.export_table_csv(ctx, tree)
            if path:
                ctx.show_toast(f'已导出到：{path}', kind='success')

        _r = _renderer_of(ctx)
        _r.button(_as_handle(_r, frame), '导出为 CSV 文件', command=export).layout(
            Layout.pack(pady=self.theme.tutorial_demo_button_pady))

    def _page_form(self, ctx, frame):
        _, getv, _setv = AdvancedWidgetMixin.create_form(ctx, [
            ('name', '姓名', 'entry', '张三'),
            ('age', '年龄', 'spin', 0, 120, 25),
            ('gender', '性别', 'combo', ['男', '女'], '男'),
        ])

        def read():
            ctx.show_toast(f'表单数据：{getv()}', kind='success')

        _r = _renderer_of(ctx)
        _r.button(_as_handle(_r, frame), '读取表单内容', command=read).layout(
            Layout.pack(pady=self.theme.tutorial_demo_button_pady))

    def _page_done(self, ctx, frame):
        WidgetMixin.label_ck(ctx, '学完啦！', tsize=20)
        # 同上 —— 中立 `label(...)` 拿 `color`/`family`/`size`；`bg`/`justify` 经逃生口补齐。
        _r = _renderer_of(ctx)
        _fam, _size = self.theme.tutorial_demo_label
        _tip = _r.label(_as_handle(_r, frame),
                        '想自己动手写代码？打开「新手教程.md」，\n'
                        '里面有 3 个复制就能跑的入门示例。',
                        color=self.theme.tutorial_demo_label_color,
                        family=_fam, size=_size)
        _tip.native.configure(bg=self.theme.tutorial_demo_background, justify='left')
        _tip.layout(Layout.pack(pady=self.theme.tutorial_demo_button_pady))

    # ------------------------------------------------------------------
    # 翻页逻辑
    # ------------------------------------------------------------------
    def show_page(self, index):
        """显示指定页：清空演示区，重建该页的示例控件。"""
        for w in self.demo_area.winfo_children():
            w.destroy()

        page = self.pages[index]
        self.title_label.config(text=page['title'])
        self.desc_label.config(text=page['desc'])
        self.progress['value'] = index + 1
        self.progress_label.config(
            text=self.theme.tutorial_progress_text.format(i=index + 1, n=len(self.pages)))

        ctx = _DemoCtx(self.host, self.demo_area)
        try:
            page['build'](ctx, self.demo_area)
        except Exception as e:
            # 出错提示也走中立 `label(...)`（`color='red'`；`bg` 经逃生口补齐）。
            _r = _renderer_of(ctx)
            _err = _r.label(_as_handle(_r, self.demo_area),
                            f'（本页示例加载出错：{type(e).__name__}）', color='red')
            _err.native.configure(bg=self.theme.tutorial_demo_background)
            _err.layout(Layout.pack())

        self.page_index = index
        self.prev_btn.config(state=self.theme.tutorial_nav_state_normal if index > 0
                             else self.theme.tutorial_nav_state_disabled)
        if index == len(self.pages) - 1:
            self.next_btn.config(text=self.theme.tutorial_done_text, command=self.win.destroy)
        else:
            self.next_btn.config(text=self.theme.tutorial_next_text, command=self.next_page)

    def next_page(self):
        if self.page_index < len(self.pages) - 1:
            self.show_page(self.page_index + 1)

    def prev_page(self):
        if self.page_index > 0:
            self.show_page(self.page_index - 1)
