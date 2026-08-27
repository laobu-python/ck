# ck0.9 GUI 库（简要说明）

> 当前版本：**ck0.9**（基于 tkinter 的轻量级 GUI 组件库）
> 包名（import 用）：**ck0_09**

基于 tkinter 的轻量级 GUI 组件库，提供若干 mixin 与实用控件，便于快速构建桌面应用。

主要特性
- 可滚动内容容器与响应式布局
- 工具栏（toolbar）、状态栏（status bar）和可搜索列表（searchable list）
- 图片与 GIF 支持（基于 Pillow，可选依赖）
- 多种便捷控件：占位文本框、复选框、单选组、进度条、工具提示、实时时钟、条形图可视化等
- 新增智能组件：可过滤下拉框、滑块、数字微调框、现代开关、智能表格、智能表单、选项卡
- 智能增强：搜索列表键盘导航与动态更新、Toast 非阻塞提示、输入对话框、快捷键、窗口居中/置顶

安装与导入（包名 `ck0_09`）
1. 在项目根目录（`ck0.9` 文件夹）执行：

`ash
pip install -e .
`

2. 之后在任何目录都可以导入使用：

`ash
python
from ck0_09 import MainWindow

app = MainWindow("我的程序", 600, 400)
app.label_ck("你好", tsize=20)
app.run()
`

3. 卸载：`pip uninstall ck0_09`

> 说明：项目文件夹名是 `ck0.9`（含小数点，不能直接 import），
> 通过 `pyproject.toml` 将可导入的包名映射为 `ck0_09`。

快速开始
1. （可选）安装依赖：

`ash
pip install pillow
`

2. 运行演示：

`ash
python main.py
`

3. 新手引导（零基础友好）：
- 双击 `3-新手启动器.bat`：一个窗口三个大按钮，选择进入演示 / 教程 / 文档
- 双击 `2-新手交互教程.bat`：分页交互式教程，每页一个可操作的组件，无需写代码
- 打开 `新手教程.md`：零基础入门文档，含 3 个复制就能跑的示例
- 双击 `4-新手教程文档.bat`：直接打开新手教程文档

主要接口（简要）
- `MainWindow(name, width, height)`：主窗口类，包含 Btk 与多个 mixin。
- `app.create_toolbar(items)`：创建工具栏，`items` 格式示例：
  - `(text, command, 'button')` 或
  - `(text, None, 'menu', [(label, cmd), ...])`。
- `app.create_status_bar(initial_text)`：创建状态栏，返回 `(label_widget, set_status_function)`。
- `app.create_searchable_list(items, height, on_select)`：创建可搜索列表，返回 `(container, search_var, listbox)`。
- `app.photo(path)` / `app.gif(path)`：显示图片或 GIF（需要 Pillow）。

注意
- 已尽力兼容多重继承场景，mixin 的 `__init__` 做了最小安全初始化。
- 若遇到 Pillow 未安装导致的错误，请执行 `pip install pillow`。

详细函数说明（示例为最小用法，所有示例假定有 `app = MainWindow('标题', 800, 600)`）：

- Btk / MainWindow:
  - run()
	- 说明：启动主循环。
	- 示例：`app.run()`

- WidgetMixin (gui/widgets.py):
  - buttonx(btname='button', widthx=15, heightx=2, ifzf=True, wstr1='点按钮 ', wstr2='已经点击 ', commandname=None, feedback_id=None)
	- 说明：创建一个按钮并可显示反馈标签。
	- 示例：`app.buttonx('提交', commandname=lambda: print('提交'))`
  - input_box(hint='请输入', wbox=30, hbox=10, pbox=10, ipbox=0, tzt='Microsoft YaHei', tsize=15, tblod=True)
	- 说明：创建文本输入框（Entry）。
	- 示例：`entry = app.input_box('搜索')`
  - label_ck(label_text, tcolor='#000000', tzt='Microsoft YaHei', tsize=20, tblod=True)
	- 说明：创建标题/标签。
	- 示例：`app.label_ck('标题', tsize=18)`

- DialogMixin (gui/dialogs.py):
  - create_file_dialog(button_text='选择文件', file_types=(('所有文件', '*.*'),))
	- 说明：在界面中创建一个按钮，点击弹出文件选择对话框。
	- 示例：`app.create_file_dialog()`
  - create_message_box(title, message, msg_type='info')
	- 说明：创建一个按钮，点击显示消息框（info/warning/error）。
	- 示例：`app.create_message_box('提示', '完成', 'info')`
  - show_message(title, message, msg_type='info')
	- 说明：立即弹出消息框（可在代码中直接调用）。

- MediaMixin (gui/media.py) — 依赖：Pillow
  - 说明：用于显示静态图片与 GIF 动画。必须安装 Pillow：`pip install pillow`。
  - photo(photo_path, text='', tcolor='#000000', tzt='Microsoft YaHei', tsize=20, tblod=True)
	- 示例：`app.photo('img.png')`
  - gif(gif_path, text='', tcolor='#000000', tzt='Microsoft YaHei', tsize=20, tblod=True)
	- 示例：`app.gif('anim.gif')`
  - clear_media()
	- 说明：清理当前显示的图片或 GIF。

- AdvancedWidgetMixin (gui/advanced_widgets.py):
  - create_text_area(width=50, height=10, placeholder='请输入文本...')
	- 示例：`ta = app.create_text_area(60, 8)`
  - create_checkbox(text='复选框', default=False, command=None)
	- 示例：`var, cb = app.create_checkbox('启用')`
  - create_radio_group(options, default=0)
	- 示例：`var, rbs = app.create_radio_group(['选项1','选项2'])`
  - create_progress_bar(max_value=100, width=300)
	- 返回：更新函数 `update_progress(value)`；示例：`update = app.create_progress_bar(); update(50)`
  - create_menu(menu_items)
	- 示例：`app.create_menu([('文件',[('退出', app.root.quit)])])`
  - create_tooltip(widget, text)
	- 示例：`app.create_tooltip(btn, '这是按钮')`
  - create_clock()
	- 示例：`clock = app.create_clock()`
  - create_toolbar(items)
	- 说明：在窗口顶端创建工具栏；见上方 items 格式说明。
	- 示例：`app.create_toolbar([('关于', lambda: print('about'))])`
  - create_status_bar(initial_text='Ready')
	- 返回 `(label_widget, set_status)`；示例：`label, set_status = app.create_status_bar('就绪')`
  - create_searchable_list(items, height=8, on_select=None)
	- 返回 `(container, search_var, listbox)`；示例：`cont, sv, lb = app.create_searchable_list(['a','b'], on_select=lambda v: print(v))`
  - create_scrollable_canvas(...) / create_scrollable_visualization_canvas(...)
	- 说明：创建带滚动的画布容器，适合自定义绘制或复杂可视化。
  - scrollable_labels(data, ...)、scrollable_bars(data, ...)
	- 说明：分别用于创建滚动标签列表与柱状图可视化（使用 canvas 绘制）。

示例：在项目根运行 `python main.py` 会启动带 toolbar/statusbar/searchable list 的演示窗口。

如果你希望我把此 README 再补充为更详细的 API 文档（每个参数含义与返回值示例），我可以继续扩展。

---

## 详细 API 参考
下面按 Mixin/类列出主要函数，包含参数类型、默认值与返回值说明（表格中类型为 Python 类型提示的近似描述）。

注意：所有方法均在 mixin 被混入到 MainWindow（或 Btk）实例后使用，表中的 parent/返回值通常为 tkinter 对象。

### MainWindow / Btk
| 方法 | 参数 (name: type = default) | 返回值 | 说明 |
|---|---:|---|---|
| __init__ | (name: str='窗口', sizex: int=800, sizey: int=800) | MainWindow 实例 | 创建主窗口并初始化 mixin 与容器 |
| run | () | None | 进入主循环（tk.mainloop） |

### WidgetMixin (gui/widgets.py)
| 方法 | 参数 | 返回值 | 说明 |
|---|---|---|---|
| buttonx | btname: str='button', widthx: int=15, heightx: int=2, ifzf: bool=True, wstr1: str='点按钮 ', wstr2: str='已经点击 ', commandname: callable=None, feedback_id: any=None | tk.Button | 创建按钮并可显示反馈标签（若 ifzf=True） |
| input_box | hint: str='请输入', wbox: int=30, hbox: int=10, pbox: int=10, ipbox: int=0, tzt: str='Microsoft YaHei', tsize: int=15, tblod: bool=True | tk.Entry | 创建 Entry 输入框并返回控件 |
| label_ck | label_text: str, tcolor: str='#000000', tzt: str='Microsoft YaHei', tsize: int=20, tblod: bool=True | tk.Label | 创建并返回标签（标题） |

### DialogMixin (gui/dialogs.py)
| 方法 | 参数 | 返回值 | 说明 |
|---|---|---|---|
| create_file_dialog | button_text: str='选择文件', file_types: tuple=(('所有文件','*.*'),) | tk.Button | 创建一个按钮，点击弹出文件选择对话框，返回按钮。实际选中文件通过 filedialog 返回。 |
| create_message_box | title: str, message: str, msg_type: str='info' | tk.Button | 创建按钮，点击显示 messagebox（info/warning/error）。|
| show_message | title: str, message: str, msg_type: str='info' | None | 立即弹出消息框（可在逻辑中直接调用）。|

### MediaMixin (gui/media.py) — 依赖：Pillow
| 方法 | 参数 | 返回值 | 说明 |
|---|---|---|---|
| __init__ | () | None | 初始化媒体相关状态（frames、photo_img 等）。|
| photo | photo_path: str, text: str='', tcolor: str='#000000', tzt: str='Microsoft YaHei', tsize: int=20, tblod: bool=True | None | 在 scrollable_frame 或 root 上创建 Label 并显示静态图片（需 Pillow）。|
| gif | gif_path: str, text: str='', tcolor: str='#000000', tzt: str='Microsoft YaHei', tsize: int=20, tblod: bool=True | None | 加载 GIF，按 frame 播放（需 Pillow）。|
| clear_media | () | None | 清理并销毁当前图片/GIF，释放引用。|

### AdvancedWidgetMixin (gui/advanced_widgets.py)
| 方法 | 参数 | 返回值 | 说明 |
|---|---|---|---|
| __init__ | () | None | minimal init（若无 root/scrollable_frame/main_canvas 则提供占位属性）。|
| create_text_area | width: int=50, height: int=10, placeholder: str='请输入文本...' | tk.Text | 返回多行 Text 控件（含占位符行为）。|
| create_checkbox | text: str='复选框', default: bool=False, command: callable=None | (tk.BooleanVar, tk.Checkbutton) | 返回变量和 Checkbutton 控件。|
| create_radio_group | options: list, default: int=0 | (tk.IntVar, list[tk.Radiobutton]) | 返回 IntVar 与 Radiobutton 列表。|
| create_progress_bar | max_value: int=100, width: int=300 | callable update_progress(value) | 返回更新函数，传入进度值更新显示。|
| create_menu | menu_items: list[tuple] | None | 在 root 上设置顶层菜单（menubar）。|
| create_tooltip | widget: tk.Widget, text: str | None | 为 widget 添加鼠标悬停提示（Tooltip）。|
| create_clock | () | tk.Label | 创建并返回实时更新的时钟 Label。|
| create_scrollable_canvas | width: int=500, height: int=300, bg_color: str='#f0f0f0' | (tk.Frame, tk.Frame) | 返回 (outer_container, scroll_frame)，用于放置可滚动内容。|
| create_scrollable_visualization_canvas | width: int=800, height: int=120, bg_color: str='#2d3748' | (tk.Frame, tk.Frame) | 返回横向可滚动的容器（适合宽图表）。|
| scrollable_labels | data: list, bg_color: str='#fff', label_bg: str='#fff', label_fg: str='black', heightx: int=100 | tk.Frame | 返回包含滚动标签列表的容器。|
| scrollable_bars | data: list, canvas_width: int=800, canvas_height: int=120, bg_color: str='#2d3748', min_bar_width: int=20, padding: int=10, label_rotation: int=0, show_bg_stripes: bool=True | tk.Frame or None | 创建并返回条形图容器；空数据返回 None。|
| create_toolbar | items: list=None | tk.Frame | 在 toolbar_container 或 scrollable_frame 创建工具栏，items 参见上文格式。|
| create_status_bar | initial_text: str='Ready' | (tk.Label, callable set_status) | 创建状态栏并返回用于更新文本的函数。|
| create_searchable_list | items: list, height: int=8, on_select: callable=None | (tk.Frame, tk.StringVar, tk.Listbox) | 创建搜索框 + 可过滤 Listbox，on_select 回调参数为选中项字符串。|
| pack_vertical / pack_in_grid / center_widget | ... | tk.Frame | 若干布局辅助函数，返回容器。|

---

## 新增组件与智能增强（2026-08 更新）

### 新增组件（AdvancedWidgetMixin）
| 方法 | 参数 | 返回值 | 说明 |
|---|---|---|---|
| create_combo_box | options: list, default=None, width: int=25, editable: bool=True, on_select=None | (tk.StringVar, ttk.Combobox) | 下拉选择框；可输入，输入时自动过滤候选项并弹出下拉（智能补全） |
| create_slider | from_: int=0, to: int=100, default=None, resolution: float=1, width: int=300, label: str='', on_change=None, show_value: bool=True | (tk.DoubleVar, ttk.Scale) | 滑块，右侧实时显示数值，按分辨率自动吸附 |
| create_spinbox | from_: int=0, to: int=100, default=None, step=1, width: int=10, command=None | (tk.DoubleVar, ttk.Spinbox) | 数字微调框 |
| create_toggle_switch | text: str='开关', default: bool=False, command=None, width: int=56, height: int=28, on_color/off_color: str | (tk.BooleanVar, tk.Canvas) | 现代风格开关按钮，点击切换 |
| create_table | headers: list, rows: list=None, height: int=10, select_mode='browse', on_select=None, column_widths=None | (tk.Frame, ttk.Treeview) | 可滚动表格；列宽按内容智能估算；on_select 回调参数为 (行数据, 行id) |
| create_form | fields: list, width: int=40 | (tk.Frame, get_values, set_values) | 智能表单：按字段描述自动生成控件，get_values()/set_values(dict) 读写全部字段 |
| create_notebook | tabs: list[(标题, 内容)], height: int=280, width: int=600 | (ttk.Notebook, dict) | 选项卡容器；内容可为控件 / 可调用对象 / 控件列表 / None |

### create_form 字段格式
`(key, label, kind, *args)`，kind 支持：
- `'entry'` : 文本框 → `(key, label, 'entry', 默认值)`
- `'combo'` : 下拉框 → `(key, label, 'combo', [选项...], 默认值)`
- `'check'` : 复选框 → `(key, label, 'check', 默认bool)`
- `'spin'`  : 数字微调 → `(key, label, 'spin', 最小, 最大, 默认值)`
- `'slider'`: 滑块 → `(key, label, 'slider', 最小, 最大, 默认值)`
- `'text'`  : 多行文本 → `(key, label, 'text', 行数, 默认文本)`

示例：
```python
container, get, setv = app.create_form([
    ("name", "姓名", "entry", "张三"),
    ("age", "年龄", "spin", 0, 120, 25),
    ("gender", "性别", "combo", ["男", "女"], "男"),
])
print(get())            # {'name': '张三', 'age': 25.0, 'gender': '男'}
setv({"name": "李四"})  # 批量赋值
```

### 智能增强
| 方法 | 说明 |
|---|---|
| create_searchable_list | 新增：搜索框灰色占位符；键盘 ↑/↓ 移动选择、Enter 触发回调；`listbox.set_items(新列表)` 动态更新数据 |
| input_box | 占位符变灰色提示，聚焦自动清空、失焦为空自动恢复 |
| create_tooltip | 新增 delay_ms 悬停延迟（默认 400ms），提示跟随鼠标移动 |
| scrollable_bars | 新增 bar_colors 参数自定义柱状颜色；data 默认值不再使用可变对象 |
| show_toast | (DialogMixin) 窗口底部非阻塞 Toast 提示，自动消失；kind: info/success/warning/error |
| ask_input | (DialogMixin) 模态输入对话框，返回输入内容或 None |
| ask_save_path | (DialogMixin) 弹出保存文件对话框，返回路径或 None |
| center_window / add_shortcut / set_always_on_top | (Btk) 窗口居中、注册快捷键（如 '<Control-s>'）、置顶切换 |
| MainWindow | 已接入 ThemeMixin：`app.set_theme('clam')` / `app.configure_font()` 可直接使用 |

### 数据导出（CSV / JSON / 剪贴板）
| 方法 | 说明 |
|---|---|
| export_table_csv(tree, file_path=None) | 将表格内容导出为 CSV；不传路径时弹保存对话框；返回路径或 None |
| save_data_csv(rows, headers=None, file_path=None) | 将任意二维数据导出为 CSV |
| save_data_json(data, file_path=None) | 将 dict/list 导出为 JSON（中文可读、格式化输出） |
| copy_table_clipboard(tree) | 将表格内容复制到剪贴板（制表符分隔，可直接粘贴进 Excel） |

说明：CSV 默认使用 `utf-8-sig` 编码，Excel 直接打开中文不乱码；
底层写入函数 `write_csv` / `write_json` 位于 `utils/helpers.py`，可直接调用。

示例：
```python
_, table = app.create_table(headers=["姓名", "分数"], rows=[("小明", 92)])
app.export_table_csv(table)                    # 弹出保存对话框
app.save_data_json({"姓名": "小明", "分数": 92})
app.copy_table_clipboard(table)                # 复制到剪贴板
```

### 新手引导系统
| 入口 | 说明 |
|---|---|
| `python launcher.py` | 新手启动器：演示 / 教程 / 文档三个大按钮 |
| `python launcher.py --tutorial` | 直接打开交互式新手教程 |
| `app.show_tutorial()` | (MainWindow) 打开分页交互教程窗口（每页一个可操作组件，无需写代码） |
| `1-运行完整演示.bat` / `2-新手交互教程.bat` / `3-新手启动器.bat` / `4-新手教程文档.bat` | 双击即用，无需命令行 |
| `新手教程.md` | 零基础入门文档：安装 Python → 运行 → 3 个复制就能跑的示例 → FAQ |

---

如果你希望我把这些表格导出为独立的 markdown 文件、或生成 HTML 文档（使用 MkDocs/Sphinx），我可以继续自动化生成。告诉我你希望的格式。 
