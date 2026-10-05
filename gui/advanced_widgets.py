# gui/advanced_widgets.py

import tkinter as tk
from tkinter import ttk

# 兼容两种运行方式：作为包导入（相对路径）或直接从项目根目录运行（绝对路径）
try:
    from ..utils.helpers import write_csv, write_json
except ImportError:
    from utils.helpers import write_csv, write_json

try:                                    # 脚本模式：cwd = 项目根，gui 为顶层包
    from ck1_0.core.theme import Theme
except ImportError:                     # 包模式：本文件即 ck1_0.gui.advanced_widgets
    from ..core.theme import Theme

# gui 包**内部**的依赖用相对导入即可（两种模式都成立：脚本模式下 `gui` 是顶层包、
# 包模式下是 `ck1_0.gui`）。在 `gui/widgets.py` 落地的两个取用助手在此复用。
from .widgets import _content_parent, _renderer_of      # noqa: E402


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
    if not getattr(root, '_ck10_wheel_bound', False):
        root._ck10_wheel_bound = True
        root.bind_all("<MouseWheel>", lambda e: _dispatch_mousewheel(root, e))


class _ThemeColorDefault(str):
    """toggle 的缺省颜色哨兵：把“调用方未显式传入”与“显式传入同一颜色字符串”区分开。

    它继承 `str` 且 `__repr__` 与普通字符串完全一致，因此 `inspect.signature()` 显示的
    默认值仍是原始字面量 `'#4caf50'` / `'#bdbdbd'`（公开签名逐字兼容）；绘制前用
    `isinstance` 判定，命中哨兵时改读 `Theme.toggle_on/off`，而调用方显式传入的任何
    颜色（包括原字面量）都原样使用，不会被主题改写。
    """
    __slots__ = ()

    def __repr__(self):
        return repr(str(self))


_THEME_ON_COLOR = _ThemeColorDefault('#4caf50')
_THEME_OFF_COLOR = _ThemeColorDefault('#bdbdbd')


def _as_native(widget):
    """把「原生控件或中立句柄」统一成 backend 原生控件。

    gui facade 返回**中立句柄**，而本模块的三个 layout helper（稍后才重写）
    仍用 Tk 的 `pack`/`grid`。与其去改调用方（`_smoke_test.py` 等），不如让 helper
    **同时收两种**：鸭子类型判定（有 `.native` 就是句柄）⇒ 既有调用点一行不用改，
   新手传句柄也直接可用。（这三个 helper 重写后本函数自然被取代。）
    """
    return getattr(widget, 'native', widget)


def _as_handle(renderer, widget):
    """把「中立句柄或原生控件」统一成**中立句柄**（`_as_native` 的**反向**）。

    两个 layout helper 改走 renderer 的中立布局助手，而它们要收 `Handle`；
   首版的调用点（以及新手代码）传的常常是**原生控件** ⇒ 用鸭子类型现包成句柄
    （判据是"有没有 `.native`"，与 `_as_native` 对称；`None` 原样返回，由调用方跳过）。
    与 `create_notebook` 里包页控件的手法同一套。
    """
    if widget is None or hasattr(widget, 'native'):
        return widget
    return type(renderer.root)(widget)


def _table_rows_and_headers(tree):
    """读回表格的「数据行 + 列名」——**两种入参都收**。

    ① **中立句柄**（`TableHandle`；起 `create_table` 的返回）：数据行走契约里的
       `get_rows()`；列名在 base 契约里**没有公开访问口** ⇒ 过渡期读句柄的**私有** `_headers`
       （Tk/Qt 两侧同名字段，已登记；将来 base 加了公开访问口即改用它）。
    ② **首版兼容**：原生 `ttk.Treeview`（用户自建 / 旧代码）⇒ `get_children()` + `tree['columns']`。

    判定用**鸭子类型**（有 `get_rows` 就是句柄），本函数**不** import tkinter、**不**建控件。
    """
    if hasattr(tree, 'get_rows'):
        return ([tuple(r) for r in tree.get_rows()],
                list(getattr(tree, '_headers', None) or []))
    return ([tuple(tree.item(i, 'values')) for i in tree.get_children()],
            list(tree['columns']))


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

    def __init__(self, theme=None):
        # 语义 token 表：显式传入 > 宿主已有 theme > 基线主题
        # （不覆盖 root / scrollable_frame / main_canvas 等宿主状态）
        if theme is not None:
            self.theme = theme
        elif not hasattr(self, 'theme'):
            self.theme = Theme.light()
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
            TextAreaHandle: **中立**句柄（`.value` 为 neutral `Value`，读写经它；
               原生控件经逃生口 `.native`）。首版返回的是 `tk.Text`。

        功能说明:
            - 初始显示灰色占位文本
            - 获得焦点且内容为占位符时清空并设为黑色
            - 失去焦点且内容为空时恢复占位符
        """
        # 改走 renderer（`renderer.text_area` 的结构/占位符/焦点语义已与首版逐行对齐：
        # `Frame`(pady=input_text_area_pady) + `Text` + 垂直 `Scrollbar` + 双向接线）。
        # `_update_scrollregion()` **保留**：=(B′) 保留了原生画布骨架 ⇒ 滚动区仍需更新
        # （材料曾建议删除该方法，其前提是"滚动区改由 handle 表达"；该前提已随 =(B′) 不成立）。
        handle = _renderer_of(self).text_area(_content_parent(self), placeholder,
                                              width=width, height=height)
        self._update_scrollregion()
        return handle

    def create_checkbox(self, text="复选框", default=False, command=None):
        """
        创建一个复选框（Checkbutton）

        参数:
            text (str): 显示在复选框旁边的标签文本
            default (bool): 初始选中状态，默认为 False
            command (callable): 当复选框状态改变时调用的函数

        返回:
            tuple: (neutral `Value`, `CheckboxHandle`)
                - 第一个元素是中立可观察值（`.get()`/`.set()`），首版是 `tk.BooleanVar`
                - 第二个元素是中立句柄，首版是 `tk.Checkbutton`
        """
        # 改走 renderer（token：pady=checkbox_y、default→checkbox_default；`command` 仍是
        # **无参**回调，且按只在**用户真的改了值**时触发）。
        # 返回**元组形状不变**，但两个元素都中立化：`(neutral Value, CheckboxHandle)`。
        handle = _renderer_of(self).checkbox(_content_parent(self), text,
                                             default=default, command=command)
        self._update_scrollregion()
        return handle.value, handle

    def create_radio_group(self, options, default=0):
        """
        创建一组互斥的单选按钮（Radiobutton Group）

        参数:
            options (list of str): 单选按钮的选项文本列表
            default (int): 默认选中的选项索引（从 0 开始）

        返回:
            tuple: (neutral `Value`, `RadioGroupHandle`)
                - 第一个元素是中立可观察值，其值为**选中项索引**（首版是 `tk.IntVar`）
                - 第二个元素是中立句柄（`.options` 给出选项），首版是 `[Radiobutton]`
        """
        # 改走 renderer（token：pady=radio_y、anchor=radio_anchor；**无回调**，与首版同）。
        # 返回元组形状不变，两个元素都中立化：`(neutral Value, RadioGroupHandle)`；
        # 句柄的 `.options` 给出选项（首版的 `[Radiobutton]` 列表是 Tk 专属细节）。
        handle = _renderer_of(self).radio_group(_content_parent(self), options, default=default)
        self._update_scrollregion()
        return handle.value, handle

    def create_progress_bar(self, max_value=100, width=300):
        """
        创建一个自定义的图形化进度条（基于 Canvas）

        参数:
            max_value (int): 进度条的最大值，默认为 100
            width (int): 进度条的像素宽度，默认为 300

        返回:
            callable: `update(value)` —— 中立句柄的 `update`（形状与首版的闭包一致）
                - 调用并传入当前进度值（0 ~ max_value）即可更新；夹取语义与首版逐字相同
                - 需要句柄本身（如 `destroy()`）时请改用 `Renderer.progress` 直接取 `ProgressHandle`
        """
        # 改走 renderer：首版返回的**闭包**被中立化为 `ProgressHandle.update(value)`
        # （夹取语义逐行复刻：`max_value<=0` 时非零视为满、结果夹到 `[0, width]`）。
        # **返回形状不变**：仍是"一个收 value 的可调用对象"，故 `update(50)` 这类既有用法一字不改。
        handle = _renderer_of(self).progress(_content_parent(self), max_value, width=width)
        self._update_scrollregion()
        return handle.update

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
        # 改走 renderer（token：`menu_tearoff`；**重复调用=替换**且旧菜单栏显式回收 ——
        # 首版的 `root.config(menu=…)` 会漏掉旧栏）。窗口级部件：按 base 契约用**显式**
        # `parent` 表达"这个菜单栏属于哪个窗口"（首版用 `self.root`，中立层即 root 句柄）。
        # `menu_items` 的形状 `(菜单名, [(标签, 无参回调), …])` **逐字不变**。
        # 返回 `None` 与首版一致（接口合同 「当前无显式返回」）；需要句柄时（例如之后
        # 要改菜单）请直接用 `renderer.menu_bar(renderer.root, items)`。
        renderer = _renderer_of(self)
        renderer.menu_bar(renderer.root, menu_items)

    def create_tooltip(self, widget, text, delay_ms=400):
        """
        为控件添加鼠标悬停提示（Tooltip）

        参数:
            widget: 目标控件。**两种写法都收**（新手友好，且与首版兼容）：
                - 中立句柄（`buttonx` / `label_ck` 等 facade 的返回值）
                - 原生控件（例如 `app.root`，或任意句柄的 `.native`）
            text (str): 提示文本内容
            delay_ms (int): 悬停多少毫秒后显示（默认 400），0 表示立即显示
        """
        # 改走 renderer（token：`tooltip_background`/`tooltip_relief`/`tooltip_borderwidth`/
        # `tooltip_padx`/`tooltip_pady`/`tooltip_offset`/`tooltip_delay_ms`；悬停延迟显示、
        # 移开立即隐藏，显式 `show()` 不受延迟影响）。
        # 为什么既收句柄又收原生控件：首版的入参就是**原生**控件（`_smoke_test.py` 传
        # `app.root`），而中立层只收句柄 ⇒ 有 `.native` 的按句柄走，否则就地把它包成句柄
        # （与 `_content_parent` 同一手法 `type(renderer.root)(原生)`：零契约改动、两后端通用）。
        # 返回 `None` 与首版一致（接口合同 「当前无显式返回」）；需要句柄时（例如
        # 之后要 `show()`/`destroy()`）请直接用 `renderer.tooltip(handle, text, …)`。
        renderer = _renderer_of(self)
        target = widget if hasattr(widget, 'native') else type(renderer.root)(widget)
        renderer.tooltip(target, text, delay_ms=delay_ms)

    def create_clock(self):
        """
        创建一个实时更新的数字时钟标签

        返回:
            ClockHandle: 时钟句柄（`.native` 仍是那个 Label），显示格式为 "YYYY-MM-DD HH:MM:SS"。
                **首版的缺陷已补**：`cancel()` 可停表（幂等）、`destroy()` 自动停表 ——
               首版返回的 `tk.Label` **没有任何** after_cancel 手段（定时器会一直空转）。
        """
        # 改走 renderer（base 一次实现，两后端共用；token 5/5：`clock` 字体族/字号 ·
        # `clock_color` · `clock_ms` · `clock_format` · `clock_y`）。父容器按 =(B′) 取
        # **既有**内容 Frame 的中立句柄；`_update_scrollregion()` 仍然调用（同上）。
        # 注：`clock(parent)` 的 parent 是必填 —— 这是早期已签字的 「显式 parent」放宽，
        # 由本 facade 提供（首版的 `create_clock(self)` 无参，签名一字未改）。
        renderer = _renderer_of(self)
        handle = renderer.clock(_content_parent(self))
        self._update_scrollregion()
        return handle

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
        # 改走 renderer（token：`scroll_default_width` / `scroll_default_height` /
        # `scroll_background` / canvas 边框 `scroll_border`；**滚轮与 scrollregion 归 backend** ——
        # 见的偏差登记：中立层用**每个实例自带**的 `<MouseWheel>`，不再是首版的全局
        # `bind_all` 分发，避免多个可滚动画布互相覆盖）。返回**仍是 2 元组**（首版形状不变），
        # 两个元素都中立化：外层容器句柄 + 内容容器句柄（`.content`）。
        # 注：首版这里的 `_ensure_global_mousewheel(self.root)` **已移除** —— 窗口构造时
        # （`gui/window.py`）就注册过全局分发器，本层画布又自带绑定；那一次调用是幂等的重复注册。
        handle = _renderer_of(self).scrollable(_content_parent(self), width=width, height=height,
                                               background=bg_color)
        # 更新滚动区域
        self._update_scrollregion()
        # 返回容器与可滚动内容容器（都是中立句柄）
        return handle, handle.content

    def create_toolbar(self, items=None):
        """创建一个简单的工具栏，items 为 [(text, command, kind)]，kind 可为 'button' 或 'menu'。"""
        # 改走 renderer（token：`toolbar_item_padx` / `toolbar_item_pady` / 菜单 `toolbar_menu_tearoff`）。
        # 父容器与首版 **逐字同口径**：`toolbar_container`（窗口级；缺席时退回内容容器），
        # 按「显式 parent」把它包成中立句柄（与 `_content` / `create_tooltip` 同一手法）。
        # `items` 的**宽容形状**保持不变：首版允许只给 `(text,)` / `(text, cmd)`，而中立层要求
        # 4 元组 ⇒ 这里先按首版的默认值补齐（`kind='button'`、缺省命令 `None`）再传。
        renderer = _renderer_of(self)
        parent = getattr(self, 'toolbar_container', self.scrollable_frame)
        if not hasattr(parent, 'native'):
            parent = type(renderer.root)(parent)
        normalized = [(it[0], it[1] if len(it) > 1 else None,
                       it[2] if len(it) > 2 else 'button',
                       it[3] if len(it) > 3 else None) for it in (items or [])]
        handle = renderer.toolbar(parent, normalized)
        self._update_scrollregion()
        return handle

    def create_status_bar(self, initial_text='Ready'):
        """创建一个状态栏并返回更新函数 set_status(text)。"""
        # 改走 renderer（token：`status_borderwidth` / `status_relief` / `status_anchor` / `fill=x`）。
        # 父容器与首版 **逐字同口径**：`statusbar_container`（窗口级；缺席时退回内容容器），
        # 按「显式 parent」包成中立句柄（与 `create_toolbar` 同一手法）。
        # 返回**仍是 2 元组**（首版形状不变）：状态栏句柄 + 它的 `set_status`（调用形状同首版）。
        renderer = _renderer_of(self)
        parent = getattr(self, 'statusbar_container', self.scrollable_frame)
        if not hasattr(parent, 'native'):
            parent = type(renderer.root)(parent)
        handle = renderer.status_bar(parent, initial_text)
        if not initial_text:
            # **首版兼容 shim**：首版把空串/`None` 原样交给 Tk（显示为空），而中立层的契约是
            # 「空/`None` ⇒ token `status_default_text`」（`parity` 的 已固化该语义）。
            # 这里补一次显式置空，让 facade 的可观察行为与首版 **逐字一致**；token 兜底只在
            # 直接调用 `renderer.status_bar(parent)` 时生效（facade 的默认值 `'Ready'` 本就等于该 token）。
            handle.set_status('')
        self._update_scrollregion()
        return handle, handle.set_status

    def create_searchable_list(self, items, height=8, on_select=None, placeholder='输入关键字过滤…'):
        """创建一个可搜索的列表：上方为搜索框，下方为带滚动的 Listbox。

        增强功能:
            - 实时过滤（不区分大小写）
            - 搜索框带灰色占位符，聚焦自动清空、失焦自动恢复（**占位符不算过滤词**）
            - 键盘 ↑/↓ 移动选择，Enter 触发 on_select（键位语义在适配层定义）
            - listbox.set_items(new_items) 动态更新数据（无需重建列表）

       返回 `(container, search_var, listbox)` —— **三元组形状与首版一致**，但元素已中立化:
            - container:  组合**句柄**；摆放用它自己的 `handle.layout(Layout.pack(…))`
            - search_var: `handle.value` —— **过滤关键字**的中立 `Value`（`.get()` / `.set()`）
            - listbox:    **同一个句柄** —— `set_items()` / `.selection` / `.native`（原生 Listbox）
       注：首版的 ①container 与 ③listbox 是**两个** Tk 对象（Frame 与 Listbox），
        中立层只有一个组合句柄 ⇒ ①与③**同源**。
        """
        # 改走 renderer（中立能力：Up/Down/Enter 键位由**适配层**定义并安装，
        # base 只承诺 `on_select` 与 `set_items`）。过滤为**实时 + 不区分大小写**的子串匹配，
        # 且 Entry 里的**占位符不算过滤词**（中性化，与 `input` 同法）。
        # token：`list_container_pady` / `list_padx` / `list_pady` / `list_default_height` /
        # `list_scroll_width` / `list_placeholder`（占位符默认值逐字保留）。
        handle = _renderer_of(self).searchable_list(_content_parent(self), items, height=height,
                                                    on_select=on_select, placeholder=placeholder)
        self._update_scrollregion()
        return handle, handle.value, handle

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
            (neutral `Value`, `ComboHandle`): 变量与下拉框句柄（首版是 `(tk.StringVar, ttk.Combobox)`）
        """
        # 改走 renderer（token：`width→combo_default_width`、`pady/padx→combo_pady/combo_padx`）。
        # 首版语义保留：`default=None ⇒ ''`、`editable=False ⇒ 只读`、选择时 `on_select(当前值)`；
        # **"输入时过滤候选"已由适配层实现（Tk 显式过滤 / Qt `QCompleter`，人类裁定 = 乙）**。
        # `value` 是**活值**（Tk 侧本轮按裁定「甲」补上 `<KeyRelease>` 同步，与 Qt 对齐）。
        handle = _renderer_of(self).combo(_content_parent(self), options, default=default,
                                          width=width, editable=editable, on_select=on_select)
        # 更新滚动区域
        self._update_scrollregion()
        # 返回变量与下拉框（都中立化）
        return handle.value, handle

    def create_slider(self, from_=0, to=100, default=None, resolution=1, width=300,
                      label='', on_change=None, show_value=True):
        """
        创建一个带实时数值显示的滑块（Slider）

        参数:
            from_/to (int): 最小值 / 最大值
            default: 默认值（None ⇒ `from_`）
            resolution (float): 数值步进精度（如 0.5）
            width (int): 滑块像素宽度
            label (str): 滑块左侧说明文字
            on_change (callable): 数值变化回调，参数为当前值
            show_value (bool): 是否在右侧实时显示数值

        返回:
            (neutral `Value`, `SliderHandle`): 变量与滑块句柄（首版是 `(tk.DoubleVar, ttk.Scale)`）
        """
        # 改走 renderer（token：`slider_default_from/to/resolution/width`、`slider_pady`、
        # `slider_label_padx`、`slider_value_padx`、`slider_value_width`、`slider_orient`）。
        # 首版的语义逐条保留（已与首版对齐）：`default=None ⇒ from_`、按 `resolution`
        # **吸附**（避免浮点毛刺）、`show_value` 控制右侧数值标签、`on_change(当前值)`。
        handle = _renderer_of(self).slider(_content_parent(self), from_=from_, to=to,
                                           default=default, resolution=resolution, width=width,
                                           label=label, on_change=on_change, show_value=show_value)
        # 更新滚动区域
        self._update_scrollregion()
        # 返回变量与滑块（都中立化）
        return handle.value, handle

    def create_spinbox(self, from_=0, to=100, default=None, step=1, width=10, command=None):
        """
        创建一个数字微调框（Spinbox）

        参数:
            from_/to (int): 最小值 / 最大值
            default: 默认值（None ⇒ `from_`）
            step (int/float): 步长
            width (int): 字符宽度
            command (callable): 数值变化回调，参数为当前值

        返回:
            (neutral `Value`, `SpinboxHandle`): 变量与微调框句柄（首版是 `(tk.DoubleVar, ttk.Spinbox)`）
        """
        # 改走 renderer（token：`spin_default_from/to/step/width`、`spin_pady`、`spin_padx`）。
        # 首版的语义保留：`default=None ⇒ from_`、`command(当前值)`（由适配层包成"收值"形状）。
        handle = _renderer_of(self).spinbox(_content_parent(self), from_=from_, to=to,
                                            default=default, step=step, width=width,
                                            command=command)
        # 更新滚动区域
        self._update_scrollregion()
        # 返回变量与微调框（都中立化）
        return handle.value, handle

    def create_toggle_switch(self, text='开关', default=False, command=None,
                             width=56, height=28,
                             on_color=_THEME_ON_COLOR, off_color=_THEME_OFF_COLOR):
        """
        创建一个现代风格的开关按钮（Canvas 绘制，点击切换）

        参数:
            text (str): 开关右侧的文字
            default (bool): 初始状态
            command (callable): 切换回调，参数为布尔值
            width/height (int): 开关轨道的像素尺寸
            on_color/off_color (str): 开/关时的轨道颜色（缺省哨兵 ⇒ 取 `Theme` 的
                `toggle_on`/`toggle_off`；**显式传入 ⇒ 原样使用**）

        返回:
            (neutral `Value`, `ToggleHandle`): 状态变量与开关句柄（首版是 `(tk.BooleanVar, tk.Canvas)`）
        """
        # 改走 renderer（token：`toggle_default_width/height`、`toggle_frame_pady`、
        # `toggle_canvas_padx`、`toggle_on/off`、`toggle_knob`、`toggle_outline`）。
        # 颜色哨兵翻译：**缺省哨兵 ⇒ 传 `None`**（中立层用 `None` 表达"取 token"），
        # **显式颜色逐字透传** —— 与首版的 `isinstance(..., _ThemeColorDefault)` 判定等价。
        # ：`text=''` 时中立层**仍然创建标签**（内容为空），
        # 而首版的 `if text:` 会**跳过**标签 ⇒ 空串时多出一个空标签；已登记，不回退契约。
        handle = _renderer_of(self).toggle(
            _content_parent(self), text, default=default, command=command,
            width=width, height=height,
            on_color=None if isinstance(on_color, _ThemeColorDefault) else on_color,
            off_color=None if isinstance(off_color, _ThemeColorDefault) else off_color)
        # 更新滚动区域
        self._update_scrollregion()
        # 返回变量与开关句柄（都中立化）
        return handle.value, handle

    def create_table(self, headers, rows=None, height=10, select_mode='browse',
                     on_select=None, column_widths=None):
        """
        创建一个可滚动的数据表格（基于 ttk.Treeview）

        参数:
            headers (list): 列标题
            rows (list): 行数据（每行是 tuple/list）
            height (int): 可视行数
            select_mode (str): 'browse' / 'extended'
            on_select (callable): 选中回调 `on_select(行值 tuple, row_id)`
            column_widths (list): 各列宽度；None 时**按标题/内容估算**（算法留 backend）

        返回:
            (neutral, neutral): 首版是 `(tk.Frame 容器, ttk.Treeview)`；中立层**只有一个组合句柄**
                （`TableHandle`，其 `.native` 就是 `ttk.Treeview`）⇒ 两个元素**同源**（同 的
                ①与③）。数据操作用 `set_rows()` / `get_rows()` / `.selection`；摆放用 `handle.layout(...)`。
        """
        # 改走 renderer（token：`table_container_pady`、`table_default_height`、`table_select_mode`、
        # `table_anchor`、`table_column_width_min/max`、`table_title_width_factor`、
        # `table_row_width_factor`、`table_row_width_extra`）。
        # `on_select` 的第二个实参 `row_id` 是 **backend 专属标识**（Tk = Treeview item id
        # `str`；Qt = 行索引 `int`），对调用方**不透明**、跨后端**不保证可解析**；契约只冻结
        # "回调收 `(values_tuple, row_id)`"这一形状。
        handle = _renderer_of(self).table(_content_parent(self), headers, rows=rows,
                                          height=height, select_mode=select_mode,
                                          on_select=on_select, column_widths=column_widths)
        # 更新滚动区域
        self._update_scrollregion()
        # 返回容器与表格（中立层同源为同一个句柄）
        return handle, handle

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
            (`FormHandle`, get_values, set_values): 首版是 `(tk.Frame, 闭包, 闭包)`；
           中立层返回**组合句柄 + 它的两个绑定方法**（调用形状与首版一致：
            `get_values() -> dict`、`set_values(dict) -> None`，只设已存在的 key）。
        """
        # 改走 renderer（token：`form_pady`、`form_default_width`、`form_grid_label_padx`、
        # `form_grid_cell_padx`、`form_grid_pady`、`form_text_lines`）。
        # **kind → 控件的映射属于 facade**（裁定：`form.kind_mapping` **不落地为 Theme
        # token** —— 它是"用户面 kind 名 → 适配层控件"的 **API 语义**映射，不是视觉/时序常量；
        # 放进 Theme 会让"主题"承担无关职责）。
        # **未知 kind / 格式错误的字段**：首版是"打印一句人话 + 跳过该字段"，而 renderer 的
        # `form` 对未识别的 kind 会落进 `else`（建一个 Entry）⇒ 必须在**这里先过滤**，否则
        # `get_values()` 会多出一个本该不存在的 key。**注意**：首版跳过时**标签已经建出来了**
        # （留下一个空标签 + 空单元），本层是整条字段都不建 —— 视觉上的差异已登记（见批报告）。
        _known = ('entry', 'combo', 'check', 'spin', 'slider', 'text')
        _normalized = []
        for _field in fields:
            if len(_field) < 3:
                print('create_form: 跳过格式错误的字段 %r' % (_field,))
                continue
            _key, _kind = _field[0], _field[2]
            if _kind not in _known:
                print("create_form: 未知控件类型 '%s'，已跳过字段 %s" % (_kind, _key))
                continue
            _normalized.append(tuple(_field))
        handle = _renderer_of(self).form(_content_parent(self), _normalized, width=width)
        # 更新滚动区域
        self._update_scrollregion()
        # 返回容器句柄与读写函数（绑定方法，调用形状同首版）
        return handle, handle.get_values, handle.set_values

    def create_notebook(self, tabs, height=280, width=600):
        """
        创建一个选项卡容器（Notebook）

        参数:
            tabs (list): [(标题, 内容)]，内容可以是：
                - tkinter 控件：直接放入该选项卡
                - 可调用对象：以**页句柄**（中立 `Handle`）为参数调用，用于填充内容
                - list/tuple：其中的控件会依次 pack 进选项卡
                - None：空选项卡
            height/width (int): 选项卡区域的像素尺寸

        返回:
            (`NotebookHandle`, dict): 选项卡句柄与 **{标题: 页句柄}** 映射
                （首版是 `(ttk.Notebook, {标题: tk.Frame})`；页句柄的 `.native` 就是原生页 Frame）。
                切换页签用 `handle.select(标题)`（未知标题**显式拒绝**，不静默）。
        """
        # 改走 renderer（token：`notebook_pady`、内容页 `notebook_content_pady`、
        # `notebook_default_size`）。
        # content callable 收到的**是 `Handle`**（不是 `tk.Frame`）—— 应用层 callable 需随之
        # 改写（`main.py` 的直建控件消除属；本批先做过渡期适配）。
        renderer = _renderer_of(self)
        # **首版兼容归一化**：首版的 `tabs` 允许直接给**原生控件**（单控件 / list 里逐项），
        # 而中立层的 `notebook` 内容**只收句柄**（`child.native.pack()`）⇒ 这里把原生控件现包成
        # 句柄（`_as_native` 的反向；与 `create_tooltip` 的鸭子类型同一手法）。
        _as_handle = lambda _w: _w if hasattr(_w, 'native') else type(renderer.root)(_w)
        _norm = []
        for _t, _c in tabs:
            if _c is None or callable(_c):
                _norm.append((_t, _c))
            elif isinstance(_c, (list, tuple)):
                _norm.append((_t, [_as_handle(_w) for _w in _c if _w is not None]))
            else:
                _norm.append((_t, _as_handle(_c)))
        handle = renderer.notebook(_content_parent(self), _norm, height=height, width=width)
        # {标题: 页句柄}：`NotebookHandle` **没有**公开的"按标题取页"访问口 ⇒ 原生页 frame 只能经
        # 句柄的**私有**属性 `_frames` 取（已登记）；句柄用 `type(renderer.root)(原生页)` 现包 ——
        # 与 `_content`（=(B′) /）同一手法。
        _pages = {}
        _frames = getattr(handle, '_frames', None) or []
        for _title, _frame in zip(getattr(handle, 'tabs', []) or [], _frames):
            _pages[_title] = type(renderer.root)(_frame)
        # 更新滚动区域
        self._update_scrollregion()
        return handle, _pages

    def export_table_csv(self, tree, file_path=None, headers=None):
        """将表格（create_table 返回的 ttk.Treeview）内容导出为 CSV 文件。

        参数:
            tree: `create_table` 返回的**中立句柄**（`TableHandle`）；为兼容首版，
                  传**原生 `ttk.Treeview`** 也可以（两条路径产出的文件逐字节相同）
            file_path (str): 保存路径；None 时弹出保存对话框
            headers (list): 表头；None 时使用表格列标题

        返回:
            str: 保存的路径；用户取消或失败返回 None
        """
        # ：不再直接读 Treeview —— 经 `_table_rows_and_headers` 走**中立句柄**的
        # `get_rows()`（首版直传 Treeview 的写法仍被兼容，见该 helper 的说明）。
        rows, _cols = _table_rows_and_headers(tree)
        if headers is None:
            headers = _cols
        if file_path is None:
            ask = getattr(self, 'ask_save_path', None)
            file_path = ask(title=self.theme.data_export_titles['csv_table']) if ask else None
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
            file_path = ask(title=self.theme.data_export_titles['csv_data']) if ask else None
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
            file_path = ask(title=self.theme.data_export_titles['json_data'], defaultextension='.json',
                            filetypes=(('JSON 文件', '*.json'), ('所有文件', '*.*'))) if ask else None
        if not file_path:
            return None
        write_json(file_path, data)
        return file_path

    def copy_table_clipboard(self, tree):
        """将表格内容复制到剪贴板（制表符分隔，可直接粘贴进 Excel）。

        参数:
            tree: `create_table` 返回的**中立句柄**（`TableHandle`）；为兼容首版，
                 传**原生 `ttk.Treeview`** 也可以

        返回:
            str: 复制到剪贴板的文本（空表 ⇒ 空串，且**不**动剪贴板，与首版一致）
        """
        # ：读表走中立 helper；写剪贴板走 renderer 的中立 API
        # （`set_clipboard_text`，不再是 `self.root.clipboard_clear/append` 这类 Tk 直呼）。
        # 首版的「空表不覆盖剪贴板」这条**保留**（`if text:`）。
        rows, _cols = _table_rows_and_headers(tree)
        text = self.theme.clipboard_line_separator.join(
            self.theme.clipboard_separator.join(str(v) for v in row) for row in rows)
        if text:
            _renderer_of(self).set_clipboard_text(text)
        return text

    def create_scrollable_visualization_canvas(self, width=800, height=120, bg_color='#2d3748'):
        """
        创建一个**水平**可滚动的可视化画布（用于图表/图形）

        参数:
            width/height (int): 可视区域像素尺寸
            bg_color (str): 背景色

        返回:
            (`ScrollableHandle`, 内容句柄): 首版是 `(外层 Frame, 内容 Frame)`；中立层的外层是
            可滚动容器句柄（`.native` = 外层 Frame），第二个元素是它的 `.content`（放绘图控件用）。
        """
        # 改走 renderer（token：`viz_background` / `viz_default_size` / `viz_border`）。：绘制
        # （渐变 RGB、旋转标签、条纹 stipple 等）**全归 backend**（`renderer/tk/draw.py`），facade
        # 只给数据与视觉参数。
        handle = _renderer_of(self).visualization_canvas(_content_parent(self), width=width,
                                                         height=height, background=bg_color)
        # 更新滚动区域
        self._update_scrollregion()
        return handle, handle.content

    def scrollable_labels(self, data=None, bg_color='#ffffff', label_bg='#ffffff', label_fg='black', heightx=100):
        """
        创建一个可滚动标签列表

        参数:
            data (list): 标签文本列表（空/None ⇒ `["默认标签"]`）
            bg_color (str): 画布背景色
            label_bg/label_fg (str): 每个标签的背景/前景色
            heightx (int): 可视高度（像素）

        返回:
            `Handle`: 外层容器句柄（`.native` = 原生 Frame）；首版直接返回 `tk.Frame`。
        """
        # 改走 renderer（token：`labels_background`、`labels_label_background`、`labels_label_color`、
        # `labels`（字体）、`labels_label_padx` / `labels_label_pady`、`labels_default_width/height`）。
        # 首版的"空数据 ⇒ 默认标签"语义在**这里**显式保留（显式传空列表也要回落）。
        # 注：本方法此前经 `create_scrollable_canvas` + `_as_native` 过渡 —— **本批起不再需要**。
        # `_as_native` 的剩余调用者只剩 `pack_in_grid`（第 1 刀后：
        # `pack_vertical`/`center_widget` 已改走 renderer 的中立布局助手 + 反向的 `_as_handle`）。
        if not data:
            data = ['默认标签']
        handle = _renderer_of(self).labels(_content_parent(self), data, background=bg_color,
                                           label_background=label_bg, label_color=label_fg,
                                           height=heightx)
        # 更新滚动区域
        self._update_scrollregion()
        return handle

    def scrollable_bars(self, data=None, canvas_width=800, canvas_height=120, bg_color='#2d3748',
                        min_bar_width=20, padding=10, label_rotation=0, show_bg_stripes=True,
                        bar_colors=None):
        """
        创建一个可横向滚动的柱状图

        参数:
            data (list): 数值列表；**空/None ⇒ 返回 `None`**（首版的"无数据"哨兵语义，冻结）
            canvas_width/canvas_height (int): 画布像素尺寸
            bg_color (str): 画布背景色
            min_bar_width (int): 每根柱子的最小宽度
            padding (int): 柱间与两端留白
            label_rotation (int): 数值标签旋转角度
            show_bg_stripes (bool): 是否画背景条纹
            bar_colors (list | None): 自定义调色板；None ⇒ 按索引生成渐变

        返回:
            `Handle | None`: 外层容器句柄（`.native` = 原生 Frame）；空数据返回 `None`。
        """
        # 改走 renderer（token：`bars_background`、`bars_stripe`、`bars_stripe_light`、
        # `bars_text_color`、`bars_outline`、`bars_font_family/min/max`、`bars_padding`、
        # `bars_spacing`、`bars_label_band`、`bars_height_reserve`、`bars_default_width/height`、
        # `bars_min_bar_width`、`bars_geometry`）。
        # 渐变 RGB 公式、旋转标签、条纹 stipple 等绘制**全归 backend**（`renderer/tk/draw.py`），
        # facade 只把**数据 + 视觉参数**透传过去。
        # **"空数据 ⇒ None"** 是首版的冻结语义 ⇒ 在 facade 先短路（此时**不**调
        # `_update_scrollregion`，与首版的 `return None` 位置一致）。
        if not data:
            return None
        handle = _renderer_of(self).bars(_content_parent(self), data,
                                         canvas_width=canvas_width,
                                         canvas_height=canvas_height, background=bg_color,
                                         min_bar_width=min_bar_width, padding=padding,
                                         label_rotation=label_rotation,
                                         show_bg_stripes=show_bg_stripes, bar_colors=bar_colors)
        # 更新滚动区域
        self._update_scrollregion()
        return handle

    def pack_vertical(self, *widgets, padx=10, pady=10):
        """
        将多个控件垂直排列在一个容器中

        参数:
            *widgets: 要排列的控件（**中立句柄或原生控件都收** —— 首版的调用点不用改）
            padx (int): 容器左右内边距
            pady (int): 控件之间的垂直间距

        返回:
            `Handle`: 新容器句柄（`.native` = 原生 Frame）；首版直接返回 `tk.Frame`。
        """
        # 改走 renderer 的中立布局助手（`Renderer.pack_vertical`；/ 已签）。
        # （本批显式列出）**：首版的实现是**裸** `pack()`（没给 `in_=container`）⇒
        # 控件其实仍由 `scrollable_frame` 管理，返回的容器实测 **1×1 空容器**；中立助手按
        # 契约把几何**真的**交给新容器 ⇒ 容器随内容撑开。**不回退契约**，视觉确认待。
        renderer = _renderer_of(self)
        box = renderer.pack_vertical(_content_parent(self),
                                     *[_as_handle(renderer, w) for w in widgets],
                                     padx=padx, pady=pady)
        # 更新滚动区域
        self._update_scrollregion()
        return box

    def pack_in_grid(self, widgets_2d, padx=5, pady=5, col_weights=None):
        """
        将二维控件列表以网格方式排列

        参数:
            widgets_2d (list of lists): 二维控件（**中立句柄或原生控件都收**）
            padx/pady (int): 网格单元的内外边距
            col_weights (list of int): 各列的伸缩权重（可选；不给 ⇒ **各列等权 = 1**）

        返回:
            `Handle`: 网格容器句柄（`.native` = 原生 Frame）；首版返回 `tk.Frame`。
        """
        # 第 2 刀：改走 renderer 的中立 `pack_in_grid(...)`（**裁定 (2)** 使它
        # 的 `col_weights` 真正生效 —— 修前中立层会静默丢弃，而首版那一支是正确的）。
        # **`_as_native` 在本文件里到此彻底消失**（三处过渡期适配全部由 `_as_handle` 取代）。
        renderer = _renderer_of(self)
        rows = list(widgets_2d or [])
        cols = max((len(r) for r in rows), default=0)
        if col_weights:
            _weights = list(col_weights)
        else:
            _weights = [1] * cols          # 首版：不给权重 ⇒ **各列等权 1**（不是"不设置"）
        box = renderer.pack_in_grid(
            _content_parent(self),
            [[_as_handle(renderer, w) for w in row] for row in rows],
            padx=padx, pady=pady, col_weights=_weights)
        # 注：`padx`/`pady` 在首版既用作**容器自身**的 `pack` 间距、又用作**单元**间距；
        # 中立契约里它们是**子项间距**，容器自身按 `Layout.pack(fill='x')` 摆 —— 差异已登记
        # （`设计记录` / 目视清单）。
        self._update_scrollregion()
        return box

    def center_widget(self, widget, pady=10):
        """
        将单个控件在其容器中水平居中

        参数:
            widget: 要居中的控件（**中立句柄或原生控件都收**）
            pady (int): 上下间距

        返回:
            `Handle`: 新容器句柄（`.native` = 原生 Frame）；`widget` 为 `None` ⇒ 返回 `None`
            （首版语义，冻结）。首版直接返回 `tk.Frame`。
        """
        # 同 `pack_vertical`：改走 `Renderer.center_widget`；的"空容器 quirk"
        # 在这里一并修正（首版实测 168×1、子控件数 0）。`None` ⇒ `None` 且**不**更新滚动区。
        if widget is None:
            return None
        renderer = _renderer_of(self)
        box = renderer.center_widget(_content_parent(self),
                                     _as_handle(renderer, widget), pady=pady)
        # 更新滚动区域
        self._update_scrollregion()
        return box