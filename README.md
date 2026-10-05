# ck1.0 GUI 库（简要说明）

> **正式版 v1.0**（2026-10-05）｜ 可导入的包名：**`ck1_0`** ｜ 文件夹：`ck1.0`
>
> 版本变更与本次发布说明见 **`RELEASE-v1.0.md`**。
>
> **零配置可用**：只要电脑上装了 Python，双击一个 `.bat` 就能看到窗口。

基于 tkinter 的轻量级 GUI 组件库，并提供**可选的 PySide6（Qt）后端**。库的目标是
**新手友好**：API 保持稳定、默认值开箱即用、出错时说人话（中文提示，不甩一串英文报错）。

## 主要特性

- 可滚动内容容器与响应式布局
- 工具栏（toolbar）、状态栏（status bar）和可搜索列表（searchable list）
- 图片 / GIF / **APNG** 支持（基于 Pillow，可选依赖），含“查看原图”式伪装图识别、逐帧预览与拆帧导出
- 多种便捷控件：占位文本框、复选框、单选组、进度条、工具提示、实时时钟、条形图可视化等
- 智能组件：可过滤下拉框、滑块、数字微调框、现代开关、智能表格、智能表单、选项卡
- 智能增强：搜索列表键盘导航与动态更新、Toast 非阻塞提示、输入对话框、快捷键、窗口居中/置顶
- **双后端**：同一份调用代码，Tk 与 PySide6(Qt) 都能跑（见「双后端」一节）
- **三个版本的新手引导**：Tk 轻量级 / Tk + PySide6 混合 / 纯 PySide6

## 安装与导入（包名 `ck1_0`）

1. 在项目根目录（`ck1.0` 文件夹）执行：

```bash
pip install -e .
```

2. 之后在任何目录都可以导入使用：

```python
from ck1_0 import MainWindow

app = MainWindow("我的程序", 600, 400)
app.label_ck("你好", tsize=20)
app.run()
```

3. 卸载：`pip uninstall ck1_0`

> 说明：文件夹名是 `ck1.0`（含小数点，不能直接 import），
> 通过 `pyproject.toml` 把可导入的包名映射为 `ck1_0`。

## 三种运行方式

| 方式 | 怎么做 |
|---|---|
| 最省事 | 双击任意一个 `.bat`（见下表） |
| 命令行 | 先进到 `ck1.0` 文件夹，然后 `python main.py` |
| 安装后用 | `pip install -e .` 之后，在任意目录 `from ck1_0 import MainWindow` |

### 9 个 bat（双击即用）

| 文件 | 作用 |
|---|---|
| `1-运行完整演示.bat` | 完整演示窗口（工具栏 / 状态栏 / 搜索列表 / 图表 / 表格 / 表单） |
| `2-新手交互教程.bat` | 分页交互式教程：每页介绍一个组件，全鼠标操作、不用写代码 |
| `3-新手启动器.bat` | **新手启动器**：一个窗口 7 个入口 —— 三个新手引导（排在最前）+ 演示 / 教程 / 文档 / 图片检查器 |
| `4-新手教程文档.bat` | 打开 `新手教程.md`（零基础入门文档） |
| `5-图片检查器.bat` | 图片结构检查器（识别“查看原图”式伪装 APNG） |
| `6-新手引导-Tk.bat` | **新手引导 · Tk 轻量级**：只要装了 Python 就能跑，最省资源 |
| `7-新手引导-混合.bat` | **新手引导 · Tk + PySide6 混合**：Tk 管窗口，真 Qt 面板嵌在里面 |
| `8-新手引导-PySide6.bat` | **新手引导 · 纯 PySide6（高级）**：深色渐变 + 圆角卡片 + QtCharts 图表 |
| `cd_venv_cmd.bat` | 打开一个已经切到本目录的命令行窗口（方便敲 `python main.py`） |

> bat 会自动挑解释器：先找项目里的 `.venv311` / `.venv`，再找作者机器上已知的
> 一个装了 PySide6 的虚拟环境，最后回落到系统的 `python`。选中的解释器会打印出来；
> 启动失败时窗口**不会一闪而过**，会停下来告诉你怎么装依赖。

## 三个版本的新手引导

三份引导都是 **8 步**，内容一样，只是“外壳”不同，按电脑情况任选一版：

| 版本 | 入口 | 依赖 | 特点 |
|---|---|---|---|
| Tk 轻量级 | `guide_tk.py` / `6-新手引导-Tk.bat` | 只要 Python | 不 import PySide6；顶部步骤导航条 + 内容区 + 底部「← 上一步 / 下一步 → / 完成」+ 进度条 |
| Tk + PySide6 混合 | `guide_hybrid.py` / `7-新手引导-混合.bat` | Python + PySide6 | Tk 负责外壳与导航，**真 Qt 面板**（QSS + QtCharts）嵌在 Tk 窗口里；两套框架在同一进程里真的通信 |
| 纯 PySide6 | `guide_qt.py` / `8-新手引导-PySide6.bat` | Python + PySide6 | 不 import tkinter；深色渐变 QSS + 圆角卡片 + QtCharts 环形图 + 步骤导航 |

共同约定：

- 文案全中文，界面里只用字体安全的符号（`←` `→` `↑` `↓` `·` `｜` `①`），**不用彩色 emoji**
  （`Microsoft YaHei` 没有这些字形，会显示成豆腐块方框）。
- 缺依赖时**打印一句中文说明**并正常退出，**不抛 traceback**。
- 三份都支持 `--selftest`（只建界面、不进事件循环、打印 `SELFTEST OK`）与
  `--real-smoke`（真平台建窗口 + `PrintWindow` 截图 + 打印 `REAL SMOKE OK`）。

```bash
python guide_tk.py --selftest        # 自检，不开窗口
python guide_hybrid.py --selftest
python guide_qt.py --selftest
```

> `--real-smoke` 用 `_grab_window.py`（按窗口标题抓“窗口自己”的像素，抓完存成 png）。

## 主要接口（简要）

- `MainWindow(name, width, height)`：主窗口类，包含 Btk 与多个 mixin。
- `app.create_toolbar(items)`：创建工具栏，`items` 格式示例：
  - `(text, command, 'button')` 或
  - `(text, None, 'menu', [(label, cmd), ...])`。
- `app.create_status_bar(initial_text)`：创建状态栏，返回 `(label_widget, set_status_function)`。
- `app.create_searchable_list(items, height, on_select)`：创建可搜索列表，返回 `(container, search_var, listbox)`。
- `app.photo(path)` / `app.gif(path)`：显示图片或 GIF（需要 Pillow）。

> 下面所有示例都假定有 `app = MainWindow('标题', 800, 600)`。

## 详细 API 参考

### MainWindow / Btk

| 方法 | 参数 | 返回值 | 说明 |
|---|---|---|---|
| `__init__` | `name: str='窗口', sizex: int=800, sizey: int=800` | MainWindow 实例 | 创建主窗口并初始化 mixin 与容器 |
| `run` | — | None | 进入主循环 |
| `center_window` | — | None | 窗口居中 |
| `add_shortcut` | `sequence: str, callback` | None | 注册快捷键，**backend 中立写法**（如 `'Ctrl+S'`；Tk 专属的 `'<Control-s>'` 会被明确拒绝） |
| `set_always_on_top` | `flag: bool=True` | None | 置顶开关 |
| `close` | — | None | 关闭窗口并**释放** backend root（幂等，可重复调用） |

### WidgetMixin（`gui/widgets.py`）

| 方法 | 参数 | 返回值 | 说明 |
|---|---|---|---|
| `buttonx` | `btname='button', widthx=15, heightx=2, ifzf=True, wstr1='点按钮 ', wstr2='已经点击 ', commandname=None, feedback_id=None` | 按钮句柄 | 创建按钮并可显示反馈标签（`ifzf=True` 时点击先显示 `wstr2`、1 秒后恢复 `wstr1`，随后立即调用 `commandname()`） |
| `input_box` | `hint='请输入', wbox=30, hbox=10, pbox=10, ipbox=0, tzt='Microsoft YaHei', tsize=15, tblod=True` | 输入框句柄 | 灰色占位符；聚焦清空、失焦为空时恢复 |
| `label_ck` | `label_text, tcolor='#000000', tzt='Microsoft YaHei', tsize=20, tblod=True` | 标签句柄 | 创建标题 / 标签 |

### DialogMixin（`gui/dialogs.py`）

| 方法 | 参数 | 返回值 | 说明 |
|---|---|---|---|
| `create_file_dialog` | `button_text='选择文件', file_types=(('所有文件','*.*'),)` | 按钮句柄 | 点击弹出文件选择对话框 |
| `create_message_box` | `title, message, msg_type='info'` | 按钮句柄 | 点击显示消息框（info/warning/error） |
| `show_message` | `title, message, msg_type='info'` | None | 立即弹出消息框 |
| `show_toast` | `message, duration=2000, kind='info'` | None | **非阻塞** Toast 提示，自动消失；kind = info/success/warning/error |
| `ask_input` | `title='输入', prompt='请输入:', default=''` | `str | None` | 模态输入对话框 |
| `ask_save_path` | `title='保存文件', defaultextension='.csv', filetypes=...` | `str | None` | 保存文件对话框；取消返回 `None` |

### MediaMixin（`gui/media.py`）— 依赖 Pillow

| 方法 | 参数 | 返回值 | 说明 |
|---|---|---|---|
| `photo` | `photo_path='', text='', tcolor='#000000', tzt='Microsoft YaHei', tsize=20, tblod=True, frame=0, warn_animated=True` | 媒体句柄 / None | 显示**指定帧**静态图片；`frame=0` 是默认图 / 封面 |
| `animation` | `path='', ..., start=0, max_frames=None, max_loops=None, on_frame=None, frame_delay=None` | `int`（加载帧数） | 播放 GIF / APNG / 动态 WebP；每帧回调 `on_frame(frame_index, total_frames)` |
| `gif` | `gif_path='', ..., **kwargs` | `int` | 兼容旧入口，内部转发到 `animation` |
| `stop_animation` | — | None | 停止播放（控件保留） |
| `apng_info` / `apng_report` | `path=None, deep=True, max_frames=None` | `dict` / `str` | 结构化报告 / 中文文本报告 |
| `is_disguised_image` | `path=None, deep=True` | `bool` | 一键判断“查看原图”式伪装 |
| `show_image_report` | `path=None, ..., title='图片结构检查报告'` | `str` | 弹出报告窗口（可复制、可拆帧导出） |
| `show_frames` | `path=None, columns=3, thumb_width=240, ...` | 预览容器 / None | 逐帧平铺预览，红字标注“默认图 / 封面”、绿字标注动画帧 |
| `export_frames` | `path=None, outdir=None, include_default=True, prefix='frame'` | `list[str]` | 拆帧导出 PNG |
| `clear_media` | — | None | 清理当前图片/GIF，并取消动画回调 |

### AdvancedWidgetMixin（`gui/advanced_widgets.py`）

| 方法 | 参数 | 返回值 | 说明 |
|---|---|---|---|
| `create_text_area` | `width=50, height=10, placeholder='请输入文本...'` | 多行文本框句柄 | 带滚动条与占位符 |
| `create_checkbox` | `text='复选框', default=False, command=None` | `(变量, 控件)` | 状态改变时调用无参数 `command` |
| `create_radio_group` | `options, default=0` | `(变量, [控件...])` | 变量值为选中索引 |
| `create_progress_bar` | `max_value=100, width=300` | `update_progress(value)` | 返回更新函数，值会夹到 `[0, max_value]` |
| `create_menu` | `menu_items` | None | 顶层菜单栏；`[(菜单名, [(标签, 命令), ...]), ...]` |
| `create_tooltip` | `widget, text, delay_ms=400` | None | 悬停提示，跟随鼠标移动 |
| `create_clock` | — | 标签句柄 | 每秒更新的时钟 |
| `create_scrollable_canvas` | `width=500, height=300, bg_color='#f0f0f0'` | `(外层容器, 内容容器)` | 垂直滚动容器 |
| `create_scrollable_visualization_canvas` | `width=800, height=120, bg_color='#2d3748'` | `(外层容器, 内容容器)` | 横向滚动容器（适合宽图表） |
| `scrollable_labels` | `data=None, bg_color='#ffffff', label_bg='#ffffff', label_fg='black', heightx=100` | 滚动容器句柄 | 滚动标签列表；空数据回落为 `['默认标签']` |
| `scrollable_bars` | `data=None, canvas_width=800, canvas_height=120, bg_color='#2d3748', min_bar_width=20, padding=10, label_rotation=0, show_bg_stripes=True, bar_colors=None` | 滚动容器句柄 / None | 可横向滚动的柱状图；**空数据返回 `None`** |
| `create_toolbar` | `items=None` | 容器句柄 | 见上方 `items` 格式 |
| `create_status_bar` | `initial_text='Ready'` | `(标签, set_status)` | `set_status(text)` 更新状态栏 |
| `create_searchable_list` | `items, height=8, on_select=None, placeholder='输入关键字过滤…'` | `(容器, 变量, 列表控件)` | 实时过滤；键盘 ↑/↓ 选择、Enter 触发；`列表控件.set_items(新列表)` 动态更新 |
| `create_combo_box` | `options, default=None, width=25, editable=True, on_select=None` | `(变量, 控件)` | 输入即自动补全；选择时回调当前值 |
| `create_slider` | `from_=0, to=100, default=None, resolution=1, width=300, label='', on_change=None, show_value=True` | `(变量, 控件)` | 右侧实时显示数值，按分辨率吸附 |
| `create_spinbox` | `from_=0, to=100, default=None, step=1, width=10, command=None` | `(变量, 控件)` | 数字微调框 |
| `create_toggle_switch` | `text='开关', default=False, command=None, width=56, height=28, on_color='#4caf50', off_color='#bdbdbd'` | `(变量, 控件)` | 现代风格开关；回调收 `bool` |
| `create_table` | `headers, rows=None, height=10, select_mode='browse', on_select=None, column_widths=None` | `(容器, 表格控件)` | 列宽按内容智能估算（最宽 400）；回调 `on_select(行数据, 行 id)` |
| `create_form` | `fields, width=40` | `(容器, get_values, set_values)` | 一行描述自动生成整个表单 |
| `create_notebook` | `tabs, height=280, width=600` | `(选项卡控件, {标题: 页容器})` | `tabs = [(标题, 内容), ...]` |
| `export_table_csv` | `tree, file_path=None, headers=None` | `str | None` | 导出表格为 CSV；不传路径时弹保存对话框 |
| `save_data_csv` | `rows, headers=None, file_path=None` | `str | None` | 导出任意二维数据 |
| `save_data_json` | `data, file_path=None` | `str | None` | 导出 dict/list（中文可读、格式化） |
| `copy_table_clipboard` | `tree` | `str` | 制表符分隔，可直接粘贴进 Excel |
| `pack_vertical` / `pack_in_grid` / `center_widget` | — | 容器句柄 | 布局辅助函数 |

### create_form 字段格式

`(key, label, kind, *args)`，kind 支持：

- `'entry'` : 文本框 → `(key, label, 'entry', 默认值)`
- `'combo'` : 下拉框 → `(key, label, 'combo', [选项...], 默认值)`
- `'check'` : 复选框 → `(key, label, 'check', 默认bool)`
- `'spin'`  : 数字微调 → `(key, label, 'spin', 最小, 最大, 默认值)`
- `'slider'`: 滑块 → `(key, label, 'slider', 最小, 最大, 默认值)`
- `'text'`  : 多行文本 → `(key, label, 'text', 行数, 默认文本)`

```python
container, get, setv = app.create_form([
    ("name", "姓名", "entry", "张三"),
    ("age", "年龄", "spin", 0, 120, 25),
    ("gender", "性别", "combo", ["男", "女"], "男"),
])
print(get())            # {'name': '张三', 'age': 25.0, 'gender': '男'}
setv({"name": "李四"})  # 批量赋值（可以只传部分字段）
```

### 智能增强一览

| 方法 | 说明 |
|---|---|
| `create_searchable_list` | 搜索框灰色占位符；键盘 ↑/↓ 移动选择、Enter 触发回调；`set_items(新列表)` 动态更新 |
| `input_box` | 占位符变灰色提示，聚焦自动清空、失焦为空自动恢复 |
| `create_tooltip` | `delay_ms` 悬停延迟（默认 400ms），提示跟随鼠标移动 |
| `scrollable_bars` | `bar_colors` 自定义柱状颜色 |
| `show_toast` | 窗口底部非阻塞提示，自动消失 |
| `ask_input` / `ask_save_path` | 系统原生输入 / 保存对话框 |
| `center_window` / `add_shortcut` / `set_always_on_top` | 窗口居中、注册快捷键、置顶切换 |
| `MainWindow` | 已接入 ThemeMixin：`app.set_theme('clam')` / `app.configure_font()` 可直接使用 |

### 数据导出（CSV / JSON / 剪贴板）

CSV 默认使用 `utf-8-sig` 编码，**Excel 直接打开中文不乱码**；底层写入函数
`write_csv` / `write_json` 位于 `utils/helpers.py`，可直接调用。

```python
_, table = app.create_table(headers=["姓名", "分数"], rows=[("小明", 92)])
app.export_table_csv(table)                    # 弹出保存对话框
app.save_data_json({"姓名": "小明", "分数": 92})
app.copy_table_clipboard(table)                # 复制到剪贴板
```

## 双后端（Tk / PySide6）

库内部把“控件意图”和“某个 GUI 框架怎么实现”分开了：`ck1_0/core` 放主题令牌，
`ck1_0/renderer` 放 backend 中立的渲染层（`tk` / `qt` 两套实现），`gui/` 是应用侧门面。
所以同一份业务代码可以跑在两个后端上：

```python
from ck1_0.renderer.select import select, current_backend

select('tk')          # 或 select('qt')；必须在建窗口**之前**调用
print(current_backend())
```

没装 PySide6 时 `select('qt')` 会给出明确的中文提示，而不是抛一串英文 traceback。
Qt 后端需要时再装：

```bash
pip install "PySide6>=6.9"
```

## 动图 / APNG 与“查看原图”式伪装图识别

> 典型场景：一张 `.png`，用 PS、系统照片查看器、聊天列表缩略图打开是 A 图；
> 拖进 Edge / Chrome 却变成 B 图。它通常不是被“色阶 / 透明通道”藏了东西，
> 而是 **APNG（动态 PNG）**——IDAT 是“默认图 / 封面”，真正的图放在动画帧里。

### 一张 APNG 的真实结构

```
IHDR → acTL → tEXt(伪装标记) → IDAT(默认图/封面) → fcTL+fdAT(动画帧1) → fcTL+fdAT(动画帧2) → IEND
```

- **acTL**：声明动画帧数与循环次数（`num_plays = 0` 表示无限循环）
- **第一个 fcTL 出现在 IDAT 之后** ⇒ IDAT 不属于动画，是“默认图 / 封面”
  - 不支持 APNG 的解码器（PS、照片查看器、聊天缩略图）只解析 IDAT → 看到封面
  - 支持 APNG 的解码器（浏览器、APNG 查看器）会播放动画 → 露出隐藏帧
- **tEXt 元数据**：例如 `ChatBarApngDisguise = 1;STATIC;1`，这是聊天软件
  “在聊天栏里按静态图显示”的标记，属于典型的伪装指纹
- 有的文件还会写 **1x1 的空补丁帧** 来拖时间，所以“动画”看起来是静止的

### 块级检查器 `ck1_0/components/apng/parser.py`（不装 Pillow 也能用）

| 函数 | 说明 |
|---|---|
| `analyze(path, deep=True, max_frames=None)` | 结构 + 逐帧 + 差异 + 结论的综合报告（dict） |
| `format_report(info)` | 把报告格式化成中文文本 |
| `is_disguised(path, deep=True)` | 是否为“默认图与动画帧不一致”的伪装 APNG |
| `parse_png(path)` / `parse_bytes(data)` | 只做块级解析（不需要 Pillow） |
| `inspect_text(text)` | 分析“被记事本另存过的文本副本”（尽力而为） |
| `save_frames(path, outdir, include_default=True)` | 拆帧导出 |
| `to_json(info)` | 报告转 JSON |
| `pil_available()` | 是否可用 Pillow |

```python
from ck1_0.components.apng import parser as apng

info = apng.analyze(r'D:\pics\2345.png')
print(apng.format_report(info))
print('是伪装图吗:', apng.is_disguised(r'D:\pics\2345.png'))
apng.save_frames(r'D:\pics\2345.png', r'D:\pics\frames')
```

> 兼容说明：`utils/apng.py` 与 `gui/apng_handle.py` 保留为 **deprecated 别名**
> （一层转发 + `DeprecationWarning`），旧代码仍可运行，请改用上面的新路径。

```python
from ck1_0 import MainWindow

app = MainWindow('看图', 900, 760)
path = r'D:\pics\2345.png'

app.photo(path, text='默认图/封面（= PS 里看到的那张）', frame=0)
app.show_frames(path)                        # 封面帧与隐藏帧一起看
print(app.apng_report(path))                 # 结构报告
app.animation(path, start=1, max_loops=3)    # 只播动画帧（隐藏图）
app.show_image_report(path)                  # 报告窗口
app.run()
```

### 现成小工具 `apng_tool.py`

```bash
python apng_tool.py 图片.png            # 控制台打印检查报告
python apng_tool.py 图片.png --json      # JSON 输出
python apng_tool.py 图片.png --frames    # 顺便拆帧到 <图片名>_frames/
python apng_tool.py                      # 图形界面（等同 --gui）
```

图形界面里可以：打开图片 → 显示默认图 → 显示隐藏帧 → 播放动画 → 逐帧预览
→ 拆帧导出 → 复制报告。也可以双击 `5-图片检查器.bat`，或从启动器点「图片检查器」。

### 真实样本实测（2345.png）

```
APNG    : 是（acTL：动画帧 2 帧，循环 0 次 / 0 表示无限）
默认图  : 有（IDAT 不属于动画 → 非 APNG 查看器只会看到它）
元数据  : ChatBarApngDisguise = 1;STATIC;1  <== 伪装标记
帧控制  : 动画帧 1: 905x1280 延时 100ms
          动画帧 2: 1x1 偏移(0,0) 延时 100ms      <- 空补丁帧
逐帧    : 帧0 默认图/封面(暗) | 帧1 隐藏图(亮) | 帧2 = 帧1
结论    : 帧0 vs 帧1 有 94.49% 像素不同 → 典型的“查看原图”式变脸伪装
```

## 自检（装没装好，一跑就知道）

```bash
python -c "import ck1_0; print(ck1_0.__version__)"   # 期望输出 1.0
python _smoke_test.py                                # 组件冒烟测试（会开一个窗口）
python _smoke_apng.py                                # APNG / 媒体能力冒烟测试
python _smoke_no_pil.py                              # 模拟“没装 Pillow”时的降级行为
python guide_tk.py --selftest                        # 三个引导各自自检（只建界面，不开窗口）
python guide_hybrid.py --selftest
python guide_qt.py --selftest
```

## 常见问题

| 问题 | 解决办法 |
|---|---|
| 提示 `'python' 不是内部或外部命令` | Python 没装好：重装并勾选 **Add Python to PATH** |
| 双击 bat 窗口一闪而过 | 最近的版本会停下来显示原因；若仍闪，请在命令行里跑同一条命令看报错 |
| 提示找不到 `gui` 模块 | 必须在 **`ck1.0` 文件夹里**运行（双击 bat 最省事） |
| 图片 / GIF 功能报错 | 命令行执行 `pip install pillow` |
| 引导 7 / 8 打不开 | 需要 PySide6：`pip install PySide6`（引导 6 不需要） |
| 界面里出现方框字符 | 说明该字体缺这个字形；本库界面文案已只用字体安全符号，遇到请提 issue |
| 报 `cannot import name '_imaging' from 'PIL'` | **不是 Pillow 版本旧**，而是解释器与 Pillow 的 ABI 不匹配（例如常规版 Python 却装了自由线程版 `cp314t` 的轮子）。用匹配的解释器运行（如 `py -3.14t 脚本.py`），或给该解释器单独装一份：`python.exe -m pip install --force-reinstall Pillow` |
| 查自己用的是哪个解释器 | `python -c "import sys, sysconfig; print(sys.version); print(sysconfig.get_config_var('EXT_SUFFIX'))"` |
| 想卸载 / 删除 | 直接删除整个 `ck1.0` 文件夹即可，不会污染系统 |

## 想学更多

- `新手教程.md` —— 零基础入门文档（安装 Python → 运行 → 3 个复制就能跑的示例 → FAQ）
- `docs/api.md` / `docs/index.md` —— 另一份 API 说明
- `launcher.py` —— 启动器源码（很简短，适合当第一个阅读的代码）
- `apng_tool.py` —— 图片检查器源码（一个完整的“小应用”示例）
- `ck1_0/components/apng/parser.py` —— APNG 结构与伪装识别（只依赖标准库，适合阅读）
- `gui/` —— 应用侧 facade；`ck1_0/renderer/` —— backend 中立的渲染层（Tk / Qt 两套实现）

## 本版说明（ck1.0）

- 包名 `ck1_0`、版本 **1.0**，文件夹 `ck1.0`；用法与 `ck0.10` 一致，**API 没有变形**。
- 面向用户发布：**只带**库代码、启动器、三个新手引导、演示、教程与文档，
  不带任何开发期的报告 / 验收脚本 / 计划文件。
- 界面文案里不再使用彩色 emoji（`Microsoft YaHei` 无字形 ⇒ 会变成豆腐块方框），
  统一改成字体安全的写法（如 `1. 欢迎`、`← 上一步`）。
