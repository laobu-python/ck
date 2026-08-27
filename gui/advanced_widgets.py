# gui/advanced_widgets.py

import tkinter as tk
from tkinter import ttk
import datetime

# 兼容两种运行方式：作为包导入（相对路径）或直接从项目根目录运行（绝对路径）
try:
    from ..utils.helpers import write_csv, write_json
except ImportError:
    from utils.helpers import write_csv, write_json


def _dispatch_mousewheel(root, event):
    """全局滚轮处理器：滚动鼠标指针正下方的 Canvas（自动选择水平/垂直方向）。

    替代原先每个画布各自 bind_all/unbind_all 的做法——
    那种方式下，多个可滚动画布会互相覆盖全局绑定，
    unbind_all 还会把所有画布的滚轮绑定一并移除，导致滚动失效。
    """
    try:
        widget = root.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if isinstance(widget, (ttk.Treeview, tk.Listbox, tk.Text)):
                break  # 这些控件自带滚动，交给它们自己处理
            if isinstance(widget, tk.Canvas):
                step = int(-1 * (event.delta / 120))
                try:
                    _x_first, x_last = widget.xview()
                    if float(x_last) < 1.0:
                        # 内容超出可视宽度（如横向图表）→ 水平滚动
                        widget.xview_scroll(step, "units")
                    else:
                        widget.yview_scroll(step, "units")
                except Exception:
                    try:
                        widget.yview_scroll(step, "units")
                    except Exception:
                        pass
                break
            widget = getattr(widget, 'master', None)
    except Exception:
        pass


def _ensure_global_mousewheel(root):
    """确保全局滚轮处理器已注册（由任意一个可滚动画布调用，只注册一次）。"""
    if not getattr(root, '_ck8_wheel_bound', False):
        root._ck8_wheel_bound = True
        root.bind_all("<MouseWheel>", lambda e: _dispatch_mousewheel(root, e))


class AdvancedWidgetMixin:
    """
    高级 GUI 组件混入类（Mixin Class）

    本类提供一系列用于构建复杂 Tkinter 界面的高级组件创建方法，
    包括带占位符的文本框、复选框、单选组、进度条、菜单、工具提示、
    实时时钟、可滚动画布、柱状图可视化等。

    使用前提：
        - 必须被混入一个拥有以下属性的主类中：
            * self.root: tkinter.Tk 或 Toplevel 实例
            * self.scrollable_frame: 可滚动区域内的主容器 Frame（通常嵌套在 Canvas 内）
            * self.main_canvas: 主画布（用于更新 scrollregion）
        - 所有组件将自动添加到 self.scrollable_frame 中，并调用 self._update_scrollregion()
          来确保滚动区域正确更新。
    """

    def _update_scrollregion(self):
        """
        更新主画布的滚动区域以包含所有子控件

        此方法强制 Tkinter 刷新布局信息，然后重新设置 Canvas 的 scrollregion，
        使得滚动条能正确反映内容的实际尺寸。
        若没有 root / main_canvas（如独立小工具中使用），则静默跳过。
        """
        if not getattr(self, 'root', None) or not getattr(self, 'main_canvas', None):
            return
        # 强制立即处理所有挂起的几何管理任务
        self.root.update_idletasks()
        # 更新主画布的可滚动区域为其内部所有内容的边界框
        self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))

    def __init__(self):
        # minimal initializer for mixin compatibility in multiple inheritance
        # 不覆盖已有属性；仅在未定义时提供占位属性
        if not hasattr(self, 'root'):
            self.root = None
        if not hasattr(self, 'scrollable_frame'):
            self.scrollable_frame = None
        if not hasattr(self, 'main_canvas'):
            self.main_canvas = None

    def create_text_area(self, width=50, height=10, placeholder="请输入文本..."):
        """
        创建一个带有占位符功能的多行文本输入框（Text Widget）

        参数:
            width (int): 文本框的字符宽度，默认为 50
            height (int): 文本框的行高，默认为 10
            placeholder (str): 占位提示文本，默认为 "请输入文本..."

        返回:
            tk.Text: 创建的 Text 控件实例，可用于后续读写操作

        功能说明:
            - 初始显示灰色占位文本
            - 获得焦点且内容为占位符时清空并设为黑色
            - 失去焦点且内容为空时恢复占位符
        """
        # 获取父容器（通常是可滚动区域内的 Frame）
        parent = self.scrollable_frame
        # 创建一个 Frame 容器来包裹 Text 和 Scrollbar
        frame = tk.Frame(parent)
        # 将容器垂直居中放置，并留出上下间距
        frame.pack(pady=10)

        # 创建 Text 控件
        text_area = tk.Text(frame, width=width, height=height)
        # 创建垂直滚动条
        scrollbar = tk.Scrollbar(frame)

        # 将 Text 放在左侧，允许水平和垂直填充并可扩展
        text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # 将 Scrollbar 放在右侧，垂直填充
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 设置 Text 的 yscrollcommand 为 Scrollbar 的 set 方法
        text_area.config(yscrollcommand=scrollbar.set)
        # 设置 Scrollbar 的 command 为 Text 的 yview 方法
        scrollbar.config(command=text_area.yview)

        def add_placeholder():
            """在 Text 控件中插入占位符文本并设为灰色"""
            # 在第一行第一列插入占位符
            text_area.insert("1.0", placeholder)
            # 设置文字颜色为灰色
            text_area.config(fg='grey')

        def on_focus_in(event):
            """当 Text 获得焦点时触发"""
            # 如果当前内容等于占位符，则清空并设为黑色
            if text_area.get("1.0", "end-1c") == placeholder:
                text_area.delete("1.0", "end")
                text_area.config(fg='black')

        def on_focus_out(event):
            """当 Text 失去焦点时触发"""
            # 如果内容为空，则重新添加占位符
            if text_area.get("1.0", "end-1c") == '':
                add_placeholder()

        # 初始化时添加占位符
        add_placeholder()
        # 绑定获得焦点事件
        text_area.bind("<FocusIn>", on_focus_in)
        # 绑定失去焦点事件
        text_area.bind("<FocusOut>", on_focus_out)

        # 更新滚动区域以包含新控件
        self._update_scrollregion()
        # 返回 Text 控件供外部使用
        return text_area

    def create_checkbox(self, text="复选框", default=False, command=None):
        """
        创建一个复选框（Checkbutton）

        参数:
            text (str): 显示在复选框旁边的标签文本
            default (bool): 初始选中状态，默认为 False
            command (callable): 当复选框状态改变时调用的函数

        返回:
            tuple: (tk.BooleanVar, tk.Checkbutton)
                - 第一个元素是关联的变量，可用于读取/设置状态
                - 第二个元素是 Checkbutton 控件本身
        """
        # 获取父容器
        parent = self.scrollable_frame
        # 创建 BooleanVar 变量并设置初始值
        var = tk.BooleanVar(value=default)
        # 创建 Checkbutton 并关联变量和命令
        checkbox = tk.Checkbutton(parent, text=text, variable=var, command=command)
        # 垂直居中放置，上下留出间距
        checkbox.pack(pady=5)

        # 更新滚动区域
        self._update_scrollregion()
        # 返回变量和控件
        return var, checkbox

    def create_radio_group(self, options, default=0):
        """
        创建一组互斥的单选按钮（Radiobutton Group）

        参数:
            options (list of str): 单选按钮的选项文本列表
            default (int): 默认选中的选项索引（从 0 开始）

        返回:
            tuple: (tk.IntVar, list of tk.Radiobutton)
                - 第一个元素是关联的整型变量，值为选中项的索引
                - 第二个元素是 Radiobutton 控件列表
        """
        # 获取父容器
        parent = self.scrollable_frame
        # 创建一个 Frame 容器来包裹所有 Radiobutton
        frame = tk.Frame(parent)
        # 垂直居中放置容器
        frame.pack(pady=10)

        # 创建 IntVar 变量并设置默认值
        var = tk.IntVar(value=default)
        # 初始化 Radiobutton 列表
        radio_buttons = []

        # 遍历选项列表，为每个选项创建一个 Radiobutton
        for i, option in enumerate(options):
            rb = tk.Radiobutton(frame, text=option, variable=var, value=i)
            # 左对齐排列
            rb.pack(anchor=tk.W)
            # 添加到列表
            radio_buttons.append(rb)

        # 更新滚动区域
        self._update_scrollregion()
        # 返回变量和控件列表
        return var, radio_buttons

    def create_progress_bar(self, max_value=100, width=300):
        """
        创建一个自定义的图形化进度条（基于 Canvas）

        参数:
            max_value (int): 进度条的最大值，默认为 100
            width (int): 进度条的像素宽度，默认为 300

        返回:
            function: update_progress(value)
                - 调用此函数并传入当前进度值（0 ~ max_value）即可更新进度条显示
        """
        # 获取父容器
        parent = self.scrollable_frame
        # 创建 Frame 容器
        frame = tk.Frame(parent)
        # 垂直居中放置
        frame.pack(pady=10)

        # 创建 Canvas 作为进度条背景
        canvas = tk.Canvas(frame, width=width, height=20, bg='white')
        # 显示 Canvas
        canvas.pack()

        # 绘制灰色背景矩形（整个进度条区域）
        canvas.create_rectangle(0, 0, width, 20, fill='lightgray', outline='')
        # 绘制绿色前景矩形（表示已完成部分），初始宽度为 0
        progress_rect = canvas.create_rectangle(0, 0, 0, 20, fill='green', outline='')

        def update_progress(value):
            """
            更新进度条显示

            参数:
                value (float or int): 当前进度值，应在 [0, max_value] 范围内
            """
            if max_value <= 0:
                # 防止 max_value=0 时除零；非零值视为已满
                progress_width = width if value > 0 else 0
            else:
                progress_width = (value / max_value) * width
            # 限制在 [0, width] 范围内，避免越界
            progress_width = max(0, min(width, progress_width))
            # 更新绿色矩形的右边界坐标
            canvas.coords(progress_rect, 0, 0, progress_width, 20)

        # 更新滚动区域
        self._update_scrollregion()
        # 返回更新函数供外部调用
        return update_progress

    def create_menu(self, menu_items):
        """
        创建一个顶部菜单栏（Menubar）

        参数:
            menu_items (list of tuples): 菜单项定义
                - 每个元素为 (menu_name, submenu_items)
                - submenu_items 是 [(label, command), ...] 的列表

        示例:
            menu_items = [
                ("文件", [("新建", new_file), ("退出", root.quit)]),
                ("帮助", [("关于", show_about)])
            ]
        """
        # 创建顶层菜单栏
        menubar = tk.Menu(self.root)
        # 将菜单栏设置为 root 的菜单
        self.root.config(menu=menubar)

        # 遍历每个顶级菜单
        for menu_name, submenu_items in menu_items:
            # 创建下拉子菜单（不可撕离）
            menu = tk.Menu(menubar, tearoff=0)
            # 将子菜单添加到菜单栏
            menubar.add_cascade(label=menu_name, menu=menu)
            # 遍历子菜单项
            for sub_name, command in submenu_items:
                # 添加菜单命令项
                menu.add_command(label=sub_name, command=command)

    def create_tooltip(self, widget, text, delay_ms=400):
        """
        为任意 Tkinter 控件添加鼠标悬停提示（Tooltip）

        参数:
            widget (tk.Widget): 需要添加提示的控件
            text (str): 提示文本内容
            delay_ms (int): 悬停多少毫秒后显示（默认 400），0 表示立即显示
        """
        tip = None
        after_id = None

        def _show():
            nonlocal tip
            if tip is not None:
                return
            tip = tk.Toplevel(widget)
            tip.wm_overrideredirect(True)  # 去掉窗口边框和标题栏
            tip.wm_geometry(f"+{widget.winfo_pointerx() + 12}+{widget.winfo_pointery() + 12}")
            label = tk.Label(tip, text=text, background="lightyellow", relief="solid",
                             borderwidth=1, padx=4, pady=2)
            label.pack()

        def _schedule(event):
            """鼠标进入：延迟 delay_ms 后显示。"""
            nonlocal after_id
            if after_id is not None:
                widget.after_cancel(after_id)
            after_id = widget.after(delay_ms, _show) if delay_ms > 0 else 0
            if delay_ms <= 0:
                _show()

        def _move(event=None):
            """鼠标移动时让提示跟随光标。"""
            if tip is not None:
                tip.wm_geometry(f"+{widget.winfo_pointerx() + 12}+{widget.winfo_pointery() + 12}")

        def _hide(event=None):
            """鼠标离开：取消延时并销毁提示。"""
            nonlocal tip, after_id
            if after_id is not None:
                try:
                    widget.after_cancel(after_id)
                except Exception:
                    pass
                after_id = None
            if tip is not None:
                tip.destroy()
                tip = None

        # 绑定鼠标进入、移动和离开事件
        widget.bind("<Enter>", _schedule)
        widget.bind("<Motion>", _move)
        widget.bind("<Leave>", _hide)

    def create_clock(self):
        """
        创建一个实时更新的数字时钟标签

        返回:
            tk.Label: 时钟标签控件，显示格式为 "YYYY-MM-DD HH:MM:SS"
        """
        # 获取父容器
        parent = self.scrollable_frame
        # 创建 Label 控件，设置字体和颜色
        clock_label = tk.Label(parent, font=('Arial', 18), fg='black')
        # 垂直居中放置
        clock_label.pack(pady=10)

        def update_clock():
            """每秒更新一次时钟显示"""
            # 获取当前时间并格式化为字符串
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # 更新 Label 的文本
            clock_label.config(text=current_time)
            # 1000 毫秒后再次调用自己（递归定时）
            self.root.after(1000, update_clock)

        # 立即启动第一次更新
        update_clock()
        # 更新滚动区域
        self._update_scrollregion()
        # 返回 Label 控件
        return clock_label

    def create_scrollable_canvas(self, width=500, height=300, bg_color='#f0f0f0'):
        """
        创建一个带垂直滚动条的可滚动 Canvas 区域

        参数:
            width (int): Canvas 的可视宽度（像素）
            height (int): Canvas 的可视高度（像素）
            bg_color (str): 背景颜色（支持十六进制或名称）

        返回:
            tuple: (outer_container, scroll_frame)
                - outer_container: 外层 Frame，用于布局
                - scroll_frame: 内部可放置子控件的 Frame（会随内容自动扩展）
        """
        # 创建外层容器 Frame，并固定其尺寸
        outer_container = tk.Frame(self.scrollable_frame, width=width, height=height, bg=bg_color)
        outer_container.pack_propagate(False)  # 防止子控件撑大容器

        # 创建 Canvas
        canvas = tk.Canvas(outer_container, width=width, height=height, bg=bg_color, highlightthickness=0)
        # 创建垂直滚动条
        scrollbar = tk.Scrollbar(outer_container, orient="vertical", command=canvas.yview)
        # 配置 Canvas 的 yscrollcommand
        canvas.configure(yscrollcommand=scrollbar.set)

        # 创建内部可滚动的 Frame
        scroll_frame = tk.Frame(canvas, bg=bg_color)
        # 将 scroll_frame 嵌入 Canvas 中（锚点为左上角）
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")

        # 放置滚动条和 Canvas
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # 当 scroll_frame 内容变化时，自动更新 Canvas 的 scrollregion
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # 滚轮滚动由全局处理器按鼠标位置分发，这里只需确保处理器已注册一次
        _ensure_global_mousewheel(self.root)

        # 更新滚动区域
        self._update_scrollregion()
        # 返回容器和可滚动 Frame
        return outer_container, scroll_frame

    def create_toolbar(self, items=None):
        """创建一个简单的工具栏，items 为 [(text, command, kind)]，kind 可为 'button' 或 'menu'。"""
        items = items or []
        parent = getattr(self, 'toolbar_container', self.scrollable_frame)
        toolbar = tk.Frame(parent)
        toolbar.pack(fill='x')
        for it in items:
            text, cmd = it[0], it[1] if len(it) > 1 else None
            kind = it[2] if len(it) > 2 else 'button'
            if kind == 'menu':
                mb = tk.Menubutton(toolbar, text=text)
                menu = tk.Menu(mb, tearoff=0)
                for label, action in (it[3] if len(it) > 3 else []):
                    menu.add_command(label=label, command=action)
                mb.config(menu=menu)
                mb.pack(side='left', padx=2, pady=2)
            else:
                b = ttk.Button(toolbar, text=text, command=cmd) if hasattr(ttk, 'Button') else tk.Button(toolbar, text=text, command=cmd)
                b.pack(side='left', padx=2, pady=2)
        self._update_scrollregion()
        return toolbar

    def create_status_bar(self, initial_text='Ready'):
        """创建一个状态栏并返回更新函数 set_status(text)。"""
        parent = getattr(self, 'statusbar_container', self.scrollable_frame)
        status = tk.Label(parent, text=initial_text, bd=1, relief='sunken', anchor='w')
        status.pack(fill='x')

        def set_status(text):
            status.config(text=text)

        self._update_scrollregion()
        return status, set_status

    def create_searchable_list(self, items, height=8, on_select=None, placeholder='输入关键字过滤…'):
        """创建一个可搜索的列表：上方为搜索框，下方为带滚动的 Listbox。

        增强功能:
            - 实时过滤（不区分大小写）
            - 搜索框带灰色占位符，聚焦自动清空、失焦自动恢复
            - 键盘 ↑/↓ 移动选择，Enter 触发 on_select
            - listbox.set_items(new_items) 动态更新数据（无需重建列表）

        返回 (container, search_var, listbox)
        """
        parent = self.scrollable_frame
        container = tk.Frame(parent)
        container.pack(pady=5, fill='x')

        current_items = list(items)

        search_var = tk.StringVar()
        # 用 tk.Entry 以便支持灰色占位符（ttk.Entry 不接受 fg 选项）
        entry = tk.Entry(container, textvariable=search_var)
        entry.pack(fill='x', padx=5, pady=2)
        entry.insert(0, placeholder)
        entry.config(fg='grey')

        def _entry_focus_in(_e):
            if entry.get() == placeholder:
                entry.delete(0, 'end')
                entry.config(fg='black')

        def _entry_focus_out(_e):
            if not entry.get():
                entry.insert(0, placeholder)
                entry.config(fg='grey')

        entry.bind('<FocusIn>', _entry_focus_in)
        entry.bind('<FocusOut>', _entry_focus_out)

        list_container, list_frame = self.create_scrollable_canvas(width=400, height=height * 20)
        # 关键：将可滚动列表容器放入外层 container，否则 Listbox 永远不会显示
        list_container.pack(fill='x', padx=5, pady=2)
        listbox = tk.Listbox(list_frame, height=height)
        listbox.pack(fill='both', expand=True, padx=5, pady=2)

        def refresh():
            """按关键字重新填充列表。"""
            listbox.delete(0, 'end')
            q = search_var.get().lower()
            if q == placeholder.lower():
                q = ''  # 占位符不参与过滤
            for it in current_items:
                if q in str(it).lower():
                    listbox.insert('end', it)

        def set_items(new_items):
            """动态更新列表数据（便捷入口，挂在返回的 listbox 上）。"""
            nonlocal current_items
            current_items = list(new_items)
            refresh()

        listbox.set_items = set_items

        def _filter(*_):
            refresh()

        def _on_select(evt):
            if on_select:
                sel = listbox.curselection()
                if sel:
                    on_select(listbox.get(sel[0]))

        def _on_key(event):
            """键盘导航：↑/↓ 移动选中项，Enter 确认。"""
            sel = listbox.curselection()
            keysym = event.keysym
            if keysym == 'Down':
                nxt = (sel[0] + 1) if sel else 0
                if nxt < listbox.size():
                    listbox.selection_clear(0, 'end')
                    listbox.selection_set(nxt)
                    listbox.activate(nxt)
                    listbox.see(nxt)
                return 'break'
            if keysym == 'Up':
                nxt = (sel[0] - 1) if sel else listbox.size() - 1
                if nxt >= 0:
                    listbox.selection_clear(0, 'end')
                    listbox.selection_set(nxt)
                    listbox.activate(nxt)
                    listbox.see(nxt)
                return 'break'
            if keysym == 'Return':
                if sel and on_select:
                    on_select(listbox.get(sel[0]))
                return 'break'
            return None

        search_var.trace_add('write', _filter)
        listbox.bind('<<ListboxSelect>>', _on_select)
        listbox.bind('<Down>', _on_key)
        listbox.bind('<Up>', _on_key)
        listbox.bind('<Return>', _on_key)
        refresh()

        self._update_scrollregion()
        return container, search_var, listbox

    def create_combo_box(self, options, default=None, width=25, editable=True, on_select=None):
        """
        创建一个支持输入、自动过滤补全的下拉选择框（Combobox）

        参数:
            options (list): 候选项列表
            default: 默认选中值（须在 options 中；None 表示留空）
            width (int): 控件字符宽度
            editable (bool): 是否允许直接输入自定义值（False 则只能选择）
            on_select (callable): 选中回调，参数为当前值字符串

        返回:
            (tk.StringVar, ttk.Combobox): 变量与下拉框控件
        """
        parent = self.scrollable_frame
        frame = tk.Frame(parent)
        frame.pack(pady=5, fill='x')

        var = tk.StringVar(value='' if default is None else str(default))
        combobox = ttk.Combobox(frame, textvariable=var, values=list(options),
                                width=width, state='normal' if editable else 'readonly')
        combobox.pack(fill='x', padx=5)

        def _autocomplete(event=None):
            """输入时按关键字过滤候选项，并弹出下拉列表（智能补全）。"""
            typed = var.get()
            if typed:
                matches = [str(o) for o in options if typed.lower() in str(o).lower()]
                combobox['values'] = matches if matches else list(options)
            else:
                combobox['values'] = list(options)
            if editable:
                combobox.event_generate('<Down>')  # 弹出下拉

        def _selected(event=None):
            if on_select:
                on_select(var.get())

        if editable:
            combobox.bind('<KeyRelease>', _autocomplete)
        combobox.bind('<<ComboboxSelected>>', _selected)

        self._update_scrollregion()
        return var, combobox

    def create_slider(self, from_=0, to=100, default=None, resolution=1, width=300,
                      label='', on_change=None, show_value=True):
        """
        创建一个带实时数值显示的滑块（Slider）

        参数:
            from_/to (int): 最小值 / 最大值
            default: 默认值
            resolution (float): 数值步进精度（如 0.5）
            width (int): 滑块像素宽度
            label (str): 滑块左侧说明文字
            on_change (callable): 数值变化回调，参数为当前值
            show_value (bool): 是否在右侧实时显示数值

        返回:
            (tk.DoubleVar, ttk.Scale): 变量与滑块控件
        """
        parent = self.scrollable_frame
        frame = tk.Frame(parent)
        frame.pack(pady=5, fill='x')

        if label:
            tk.Label(frame, text=label).pack(side='left', padx=(10, 5))

        var = tk.DoubleVar(value=from_ if default is None else default)

        value_label = None
        if show_value:
            value_label = tk.Label(frame, text=f"{var.get():g}", width=8, anchor='e')
            value_label.pack(side='right', padx=(5, 10))

        def _on_change(event=None):
            # 按分辨率吸附数值，避免浮点毛刺
            if resolution > 0:
                snapped = round(var.get() / resolution) * resolution
                var.set(snapped)
            value = var.get()
            if show_value and value_label is not None:
                value_label.config(text=f"{value:g}")
            if on_change:
                on_change(value)

        scale = ttk.Scale(frame, from_=from_, to=to, variable=var,
                          orient='horizontal', length=width, command=_on_change)
        scale.pack(side='left', fill='x', expand=True, padx=5)

        self._update_scrollregion()
        return var, scale

    def create_spinbox(self, from_=0, to=100, default=None, step=1, width=10, command=None):
        """
        创建一个数字微调框（Spinbox）

        参数:
            from_/to (int): 最小值 / 最大值
            default: 默认值
            step (int/float): 步长
            width (int): 字符宽度
            command (callable): 数值变化回调，参数为当前值

        返回:
            (tk.DoubleVar, ttk.Spinbox): 变量与微调框控件
        """
        parent = self.scrollable_frame
        frame = tk.Frame(parent)
        frame.pack(pady=5, fill='x')

        var = tk.DoubleVar(value=from_ if default is None else default)
        spinbox = ttk.Spinbox(frame, from_=from_, to=to, increment=step, textvariable=var,
                              width=width, command=lambda: command and command(var.get()))
        spinbox.pack(side='left', padx=5)

        self._update_scrollregion()
        return var, spinbox

    def create_toggle_switch(self, text='开关', default=False, command=None,
                             width=56, height=28, on_color='#4caf50', off_color='#bdbdbd'):
        """
        创建一个现代风格的开关按钮（Canvas 绘制，点击切换）

        参数:
            text (str): 开关右侧的文字
            default (bool): 初始状态
            command (callable): 切换回调，参数为布尔值
            width/height (int): 开关轨道的像素尺寸
            on_color/off_color (str): 开/关时的轨道颜色

        返回:
            (tk.BooleanVar, tk.Canvas): 状态变量与开关画布
        """
        parent = self.scrollable_frame
        frame = tk.Frame(parent)
        frame.pack(pady=5)

        var = tk.BooleanVar(value=default)
        knob_r = height // 2 - 3
        canvas = tk.Canvas(frame, width=width, height=height, bg=frame['bg'], highlightthickness=0)
        canvas.pack(side='left', padx=5)
        if text:
            tk.Label(frame, text=text).pack(side='left')

        def _draw():
            """重绘轨道与圆形滑块。"""
            canvas.delete('all')
            track = on_color if var.get() else off_color
            r = height // 2
            canvas.create_rectangle(knob_r, 2, width - knob_r, height - 2, fill=track, outline='')
            canvas.create_oval(0, 0, height, height, fill=track, outline='')
            canvas.create_oval(width - height, 0, width, height, fill=track, outline='')
            cx = (width - knob_r - 3) if var.get() else (knob_r + 3)
            canvas.create_oval(cx - knob_r, 3, cx + knob_r, height - 3, fill='white', outline='#999')

        def _toggle(event=None):
            var.set(not var.get())
            _draw()
            if command:
                command(var.get())

        canvas.bind('<Button-1>', _toggle)
        _draw()

        self._update_scrollregion()
        return var, canvas

    def create_table(self, headers, rows=None, height=10, select_mode='browse',
                     on_select=None, column_widths=None):
        """
        创建一个可滚动的数据表格（基于 ttk.Treeview）

        参数:
            headers (list): 列标题列表
            rows (list of tuple/list): 初始数据行
            height (int): 表格可视行数
            select_mode (str): 'browse'（单选，默认）/ 'extended'（多选）
            on_select (callable): 选中回调，参数为 (行数据tuple, 行id)
            column_widths (list of int): 各列像素宽度（可选，默认按内容智能估算）

        返回:
            (tk.Frame, ttk.Treeview): 外层容器与表格控件
        """
        parent = self.scrollable_frame
        container = tk.Frame(parent)
        container.pack(pady=5, fill='x')

        cols = list(headers) if headers else []
        tree = ttk.Treeview(container, columns=cols, show='headings', height=height,
                            selectmode=select_mode)
        vsb = ttk.Scrollbar(container, orient='vertical', command=tree.yview)
        hsb = ttk.Scrollbar(container, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        data_rows = list(rows) if rows else []
        for i, col in enumerate(cols):
            tree.heading(col, text=col)
            if column_widths and i < len(column_widths):
                tree.column(col, width=column_widths[i], anchor='w')
            else:
                # 智能默认宽度：按标题与内容长度估算，并限制最大 400px
                w = max(len(str(col)) * 14, 80)
                for row in data_rows:
                    if i < len(row):
                        w = max(w, len(str(row[i])) * 11 + 18)
                tree.column(col, width=min(w, 400), anchor='w')

        tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        for row in data_rows:
            tree.insert('', 'end', values=tuple(row))

        def _on_select(event=None):
            if on_select:
                sel = tree.selection()
                if sel:
                    values = tree.item(sel[0], 'values')
                    on_select(tuple(values), sel[0])

        tree.bind('<<TreeviewSelect>>', _on_select)

        self._update_scrollregion()
        return container, tree

    def create_form(self, fields, width=40):
        """
        创建一个智能表单：按字段描述自动生成「标签 + 控件」，并返回读写函数。

        参数:
            fields (list): 字段描述列表，每项为 (key, label, kind, *args)：
                kind 支持:
                  'entry'  : 文本框    -> (key, label, 'entry', 默认值)
                  'combo'  : 下拉框    -> (key, label, 'combo', [选项...], 默认值)
                  'check'  : 复选框    -> (key, label, 'check', 默认bool)
                  'spin'   : 数字微调  -> (key, label, 'spin', 最小值, 最大值, 默认值)
                  'slider' : 滑块      -> (key, label, 'slider', 最小, 最大, 默认值)
                  'text'   : 多行文本  -> (key, label, 'text', 行数, 默认文本)
            width (int): 输入控件的字符宽度

        返回:
            (tk.Frame, get_values, set_values)
                get_values() -> dict: 读取所有字段当前值（key 为字段名）
                set_values(dict) -> None: 批量设置字段值（key 须匹配）
        """
        parent = self.scrollable_frame
        container = tk.Frame(parent)
        container.pack(pady=5, fill='x')
        container.grid_columnconfigure(1, weight=1)

        widgets = {}
        row = 0
        for field in fields:
            if len(field) < 3:
                print(f"create_form: 跳过格式错误的字段 {field}")
                continue
            key, label, kind = field[0], field[1], field[2]
            args = field[3:]

            tk.Label(container, text=label, anchor='w').grid(row=row, column=0, sticky='w', padx=(10, 5), pady=3)
            cell = tk.Frame(container)
            cell.grid(row=row, column=1, sticky='ew', padx=(5, 10), pady=3)

            if kind == 'entry':
                default = args[0] if args else ''
                v = tk.StringVar(value=default)
                tk.Entry(cell, textvariable=v, width=width).pack(fill='x')
                widgets[key] = ('entry', v)
            elif kind == 'combo':
                options = list(args[0]) if args else []
                default = args[1] if len(args) > 1 else ''
                v = tk.StringVar(value=default)
                ttk.Combobox(cell, textvariable=v, values=options, state='readonly',
                             width=width).pack(fill='x')
                widgets[key] = ('combo', v)
            elif kind == 'check':
                default = bool(args[0]) if args else False
                v = tk.BooleanVar(value=default)
                tk.Checkbutton(cell, text='', variable=v).pack(anchor='w')
                widgets[key] = ('check', v)
            elif kind == 'spin':
                frm = float(args[0]) if args else 0
                to = float(args[1]) if len(args) > 1 else 100
                default = args[2] if len(args) > 2 else frm
                v = tk.DoubleVar(value=default)
                ttk.Spinbox(cell, from_=frm, to=to, textvariable=v, width=width).pack(fill='x')
                widgets[key] = ('spin', v)
            elif kind == 'slider':
                frm = float(args[0]) if args else 0
                to = float(args[1]) if len(args) > 1 else 100
                default = args[2] if len(args) > 2 else frm
                v = tk.DoubleVar(value=default)
                ttk.Scale(cell, from_=frm, to=to, variable=v, orient='horizontal').pack(fill='x')
                widgets[key] = ('slider', v)
            elif kind == 'text':
                lines = int(args[0]) if args else 4
                default = args[1] if len(args) > 1 else ''
                t = tk.Text(cell, width=width, height=lines)
                if default:
                    t.insert('1.0', default)
                t.pack(fill='x')
                widgets[key] = ('text', t)
            else:
                print(f"create_form: 未知控件类型 '{kind}'，已跳过字段 {key}")
                row += 1
                continue
            row += 1

        def get_values():
            """读取表单所有字段，返回 {key: 值}。"""
            result = {}
            for key, (kind, w) in widgets.items():
                result[key] = w.get('1.0', 'end-1c') if kind == 'text' else w.get()
            return result

        def set_values(data):
            """按 key 批量设置字段值。"""
            for key, (kind, w) in widgets.items():
                if key not in data:
                    continue
                if kind == 'text':
                    w.delete('1.0', 'end')
                    w.insert('1.0', str(data[key]))
                else:
                    w.set(data[key])

        self._update_scrollregion()
        return container, get_values, set_values

    def create_notebook(self, tabs, height=280, width=600):
        """
        创建一个选项卡容器（Notebook）

        参数:
            tabs (list): [(标题, 内容)]，内容可以是：
                - tkinter 控件：直接放入该选项卡
                - 可调用对象：以选项卡 Frame 为参数调用，用于填充内容
                - list/tuple：其中的控件会依次 pack 进选项卡
                - None：空选项卡
            height/width (int): 选项卡区域的像素尺寸

        返回:
            (ttk.Notebook, dict): 笔记本控件与 {标题: 选项卡Frame} 映射
        """
        parent = self.scrollable_frame
        container = tk.Frame(parent)
        container.pack(pady=5, fill='x')

        notebook = ttk.Notebook(container, height=height, width=width)
        notebook.pack(fill='both', expand=True)

        frames = {}
        for title, content in tabs:
            tab = tk.Frame(notebook)
            notebook.add(tab, text=title)
            frames[title] = tab
            if content is None:
                continue
            if callable(content):
                content(tab)
            elif isinstance(content, (list, tuple)):
                for w in content:
                    if w is not None:
                        w.pack(pady=4, fill='x')
            else:
                content.pack(pady=4, fill='x', expand=True)

        self._update_scrollregion()
        return notebook, frames

    def export_table_csv(self, tree, file_path=None, headers=None):
        """将表格（create_table 返回的 ttk.Treeview）内容导出为 CSV 文件。

        参数:
            tree (ttk.Treeview): create_table 返回的表格控件
            file_path (str): 保存路径；None 时弹出保存对话框
            headers (list): 表头；None 时使用表格列标题

        返回:
            str: 保存的路径；用户取消或失败返回 None
        """
        rows = [tuple(tree.item(item, 'values')) for item in tree.get_children()]
        if headers is None:
            headers = list(tree['columns'])
        if file_path is None:
            ask = getattr(self, 'ask_save_path', None)
            file_path = ask(title='导出表格为 CSV') if ask else None
        if not file_path:
            return None
        write_csv(file_path, rows, headers=headers)
        return file_path

    def save_data_csv(self, rows, headers=None, file_path=None):
        """将任意二维数据导出为 CSV 文件。

        参数:
            rows (list): 数据行列表，每行是 list/tuple
            headers (list): 表头（可选）
            file_path (str): 保存路径；None 时弹出保存对话框

        返回:
            str: 保存的路径；用户取消或失败返回 None
        """
        if file_path is None:
            ask = getattr(self, 'ask_save_path', None)
            file_path = ask(title='导出数据为 CSV') if ask else None
        if not file_path:
            return None
        write_csv(file_path, rows, headers=headers)
        return file_path

    def save_data_json(self, data, file_path=None):
        """将 dict / list 数据导出为 JSON 文件（中文保持可读）。

        参数:
            data: 要保存的数据
            file_path (str): 保存路径；None 时弹出保存对话框

        返回:
            str: 保存的路径；用户取消或失败返回 None
        """
        if file_path is None:
            ask = getattr(self, 'ask_save_path', None)
            file_path = ask(title='导出数据为 JSON', defaultextension='.json',
                            filetypes=(('JSON 文件', '*.json'), ('所有文件', '*.*'))) if ask else None
        if not file_path:
            return None
        write_json(file_path, data)
        return file_path

    def copy_table_clipboard(self, tree):
        """将表格内容复制到剪贴板（制表符分隔，可直接粘贴进 Excel）。

        参数:
            tree (ttk.Treeview): create_table 返回的表格控件

        返回:
            str: 复制到剪贴板的文本
        """
        rows = []
        for item in tree.get_children():
            rows.append('\t'.join(str(v) for v in tree.item(item, 'values')))
        text = '\n'.join(rows)
        if text and getattr(self, 'root', None):
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        return text

    def create_scrollable_visualization_canvas(self, width=800, height=120, bg_color='#2d3748'):
        """
        创建一个带水平滚动条的可视化 Canvas 区域（适用于宽图表）

        参数:
            width (int): Canvas 的可视宽度（像素）
            height (int): Canvas 的可视高度（像素）
            bg_color (str): 背景色（深色主题推荐）

        返回:
            tuple: (outer_container, content_frame)
                - outer_container: 外层 Frame
                - content_frame: 内部可绘制内容的 Frame
        """
        # 创建外层容器
        outer_container = tk.Frame(self.scrollable_frame, width=width, height=height, bg=bg_color)
        outer_container.pack_propagate(False)

        # 创建 Canvas
        canvas = tk.Canvas(outer_container, width=width, height=height, bg=bg_color, highlightthickness=0)
        # 创建水平滚动条
        scrollbar = tk.Scrollbar(outer_container, orient="horizontal", command=canvas.xview)
        # 配置 xscrollcommand
        canvas.configure(xscrollcommand=scrollbar.set)

        # 创建内容 Frame
        content_frame = tk.Frame(canvas, bg=bg_color)
        canvas.create_window((0, 0), window=content_frame, anchor="nw")

        # 放置 Canvas 和滚动条
        canvas.pack(side="top", fill="x", expand=True)
        scrollbar.pack(side="bottom", fill="x")

        # 自动更新水平滚动区域
        def on_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        content_frame.bind("<Configure>", on_configure)

        # 滚轮滚动由全局处理器按鼠标位置分发（横向画布会自动水平滚动）
        _ensure_global_mousewheel(self.root)

        # 更新滚动区域
        self._update_scrollregion()
        # 返回容器和内容 Frame
        return outer_container, content_frame

    def scrollable_labels(self, data=None, bg_color='#ffffff', label_bg='#ffffff', label_fg='black', heightx=100):
        """
        创建一个可垂直滚动的标签列表

        参数:
            data (list): 要显示的文本数据列表
            bg_color (str): 滚动区域背景色
            label_bg (str): 每个标签的背景色
            label_fg (str): 每个标签的前景色（文字颜色）
            heightx (int): 滚动区域的固定高度（像素）

        返回:
            tk.Frame: 包含滚动标签的外层容器
        """
        # 处理默认数据
        if not data:
            data = ["默认标签"]

        # 创建可滚动 Canvas
        container, scroll_frame = self.create_scrollable_canvas(width=500, height=heightx, bg_color=bg_color)

        # 为每个数据项创建一个 Label
        for i in range(len(data)):
            label = tk.Label(
                scroll_frame,
                text=f" {i + 1}. {data[i]}",
                bg=label_bg,
                fg=label_fg,
                font=('Arial', 10)
            )
            label.pack(pady=5, padx=10, anchor='w')  # 左对齐

        # 更新滚动区域
        self._update_scrollregion()
        # 返回容器
        return container

    def scrollable_bars(
            self,
            data=None,
            canvas_width=800,
            canvas_height=120,
            bg_color='#2d3748',
            min_bar_width=20,
            padding=10,
            label_rotation=0,
            show_bg_stripes=True,
            bar_colors=None
    ):
        if not data:
            return None

        container, viz_frame = self.create_scrollable_visualization_canvas(
            width=canvas_width, height=canvas_height, bg_color=bg_color
        )
        canvas = container.winfo_children()[0]  # 获取 Canvas

        max_value = max(data) if data else 1
        count = len(data)
        available_width = canvas_width - 2 * padding
        ideal_width = (available_width - (count - 1) * 5) / count
        bar_width = max(min_bar_width, ideal_width)
        spacing = 5
        total_width = count * bar_width + (count - 1) * spacing
        offset_x = padding

        # ✅ 关键修复 1: 扩展 scrollregion 高度，包含文字
        canvas.configure(scrollregion=(0, 0, total_width + 2 * padding, canvas_height))

        for i, value in enumerate(data):
            x_start = offset_x + i * (bar_width + spacing)
            x_end = x_start + bar_width
            # 底部预留 label_band 高度给数值标签，避免标签/条纹超出可视区域被裁掉
            label_band = 25
            y_bottom = canvas_height - label_band
            normalized_height = (value / max_value) * (canvas_height - label_band - 15)
            y_top = y_bottom - normalized_height

            # 颜色计算：支持自定义调色板，未提供时按索引自动生成渐变
            if bar_colors:
                color = bar_colors[i % len(bar_colors)]
            else:
                r = min(255, max(0, 50 + i * 10))
                g = min(255, max(0, 150 - i * 5))
                b = min(255, max(0, 200 - i * 8))
                color = f'#{r:02x}{g:02x}{b:02x}'

            # 绘制柱子
            canvas.create_rectangle(x_start, y_bottom, x_end, y_top, fill=color, outline='white')

            # 动态字体大小
            font_size = max(6, min(12, int(bar_width / 2.5)))
            # 数值标签位于画布底部预留区内（画布内，不会被裁切）
            label_y = canvas_height - 10

            if show_bg_stripes:
                canvas.create_rectangle(x_start, label_y - 3, x_end, label_y + 8, fill='#333', stipple='gray50')

            angle = label_rotation
            if angle != 0:
                canvas.create_text(
                    x_start + bar_width // 2, label_y,
                    text=f"{value}",
                    fill='white',
                    font=('Arial', font_size),
                    anchor='center',
                    angle=angle
                )
            else:
                # ✅ 关键修复 3: 使用 anchor='s'（底部对齐）
                canvas.create_text(
                    x_start + bar_width // 2,
                    label_y,
                    text=f"{value}",
                    fill='white',
                    font=('Arial', font_size),
                    anchor='s'  # 文字底部在 label_y
                )

        self._update_scrollregion()
        return container
    def pack_vertical(self, *widgets, padx=10, pady=10):
        """
        将多个控件垂直排列在一个容器中

        参数:
            *widgets: 任意数量的 Tkinter 控件
            padx (int): 容器左右内边距
            pady (int): 控件之间的垂直间距

        返回:
            tk.Frame: 包含这些控件的垂直容器
        """
        container = tk.Frame(self.scrollable_frame)
        container.pack(pady=pady, fill=tk.X, padx=padx // 2)

        for widget in widgets:
            if widget is not None:
                widget.pack(pady=pady // 2)

        self._update_scrollregion()
        return container

    def pack_in_grid(self, widgets_2d, padx=5, pady=5, col_weights=None):
        """
        将二维控件列表以网格方式排列

        参数:
            widgets_2d (list of lists): 二维控件矩阵
            padx/pady (int): 网格单元的内外边距
            col_weights (list of int): 各列的伸缩权重（可选）

        返回:
            tk.Frame: 网格容器
        """
        container = tk.Frame(self.scrollable_frame)
        container.pack(pady=pady, padx=padx)

        rows = len(widgets_2d)
        cols = max(len(row) for row in widgets_2d) if rows > 0 else 0

        # 设置列权重（用于响应式布局）
        if col_weights:
            for i, weight in enumerate(col_weights):
                container.grid_columnconfigure(i, weight=weight)
        else:
            for i in range(cols):
                container.grid_columnconfigure(i, weight=1)

        # 放置每个控件
        for r, row in enumerate(widgets_2d):
            for c, widget in enumerate(row):
                if widget is not None:
                    widget.grid(in_=container, row=r, column=c, padx=padx, pady=pady, sticky="nsew")

        self._update_scrollregion()
        return container

    def center_widget(self, widget, pady=10):
        """
        将单个控件在其容器中水平居中

        参数:
            widget (tk.Widget): 要居中的控件
            pady (int): 上下间距

        返回:
            tk.Frame: 包含该控件的居中容器；若 widget 为 None 则返回 None
        """
        if widget is not None:
            container = tk.Frame(self.scrollable_frame)
            container.pack(pady=pady, fill=tk.X)
            widget.pack()  # 默认居中
            self._update_scrollregion()
            return container
        return None