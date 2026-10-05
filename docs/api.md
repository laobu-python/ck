# API 参考（自动导出） - ck1.0 GUI

下面列出库中主要类和方法的参数、默认值与返回值说明（便于在文档站点中查看）。

## MainWindow / Btk
### __init__(name: str='窗口', sizex: int=800, sizey: int=800)
- 返回：MainWindow 实例
- 说明：创建主窗口并初始化 mixin 与容器。

### run()
- 返回：None
- 说明：进入主循环（tk.mainloop）。

## WidgetMixin (gui/widgets.py)
### buttonx(btname: str='button', widthx: int=15, heightx: int=2, ifzf: bool=True, wstr1: str='点按钮 ', wstr2: str='已经点击 ', commandname: callable=None, feedback_id: any=None)
- 返回：tk.Button
- 说明：创建按钮并可显示反馈标签（若 ifzf=True）。

### input_box(hint: str='请输入', wbox: int=30, hbox: int=10, pbox: int=10, ipbox: int=0, tzt: str='Microsoft YaHei', tsize: int=15, tblod: bool=True)
- 返回：tk.Entry
- 说明：创建 Entry 输入框并返回控件。

### label_ck(label_text: str, tcolor: str='#000000', tzt: str='Microsoft YaHei', tsize: int=20, tblod: bool=True)
- 返回：tk.Label
- 说明：创建并返回标签（标题）。

## DialogMixin (gui/dialogs.py)
### create_file_dialog(button_text: str='选择文件', file_types: tuple=(('所有文件','*.*'),))
- 返回：tk.Button
- 说明：创建一个按钮，点击弹出文件选择对话框，返回按钮。实际选中文件通过 filedialog 返回。

### create_message_box(title: str, message: str, msg_type: str='info')
- 返回：tk.Button
- 说明：创建按钮，点击显示 messagebox（info/warning/error）。

### show_message(title: str, message: str, msg_type: str='info')
- 返回：None
- 说明：立即弹出消息框（可在逻辑中直接调用）。

## MediaMixin (gui/media.py) — 依赖：Pillow
### __init__()
- 返回：None
- 说明：初始化媒体相关状态（frames、photo_img 等）。

### photo(photo_path: str, text: str='', tcolor: str='#000000', tzt: str='Microsoft YaHei', tsize: int=20, tblod: bool=True)
- 返回：None
- 说明：在 scrollable_frame 或 root 上创建 Label 并显示静态图片（需 Pillow）。

### gif(gif_path: str, text: str='', tcolor: str='#000000', tzt: str='Microsoft YaHei', tsize: int=20, tblod: bool=True)
- 返回：None
- 说明：加载 GIF，按 frame 播放（需 Pillow）。

### clear_media()
- 返回：None
- 说明：清理并销毁当前图片/GIF，释放引用。

## AdvancedWidgetMixin (gui/advanced_widgets.py)
（此节列出常用方法，详见源码）

- create_text_area(width: int=50, height: int=10, placeholder: str='请输入文本...') -> tk.Text
- create_checkbox(text: str='复选框', default: bool=False, command: callable=None) -> (tk.BooleanVar, tk.Checkbutton)
- create_radio_group(options: list, default: int=0) -> (tk.IntVar, list[tk.Radiobutton])
- create_progress_bar(max_value: int=100, width: int=300) -> callable update_progress(value)
- create_menu(menu_items: list[tuple]) -> None
- create_tooltip(widget: tk.Widget, text: str) -> None
- create_clock() -> tk.Label
- create_scrollable_canvas(width: int=500, height: int=300, bg_color: str='#f0f0f0') -> (tk.Frame, tk.Frame)
- create_scrollable_visualization_canvas(width: int=800, height: int=120, bg_color: str='#2d3748') -> (tk.Frame, tk.Frame)
- scrollable_labels(data: list, bg_color: str='#fff', label_bg: str='#fff', label_fg: str='black', heightx: int=100) -> tk.Frame
- scrollable_bars(data: list, canvas_width: int=800, canvas_height: int=120, bg_color: str='#2d3748', min_bar_width: int=20, padding: int=10, label_rotation: int=0, show_bg_stripes: bool=True) -> tk.Frame or None
- create_toolbar(items: list=None) -> tk.Frame
- create_status_bar(initial_text: str='Ready') -> (tk.Label, callable set_status)
- create_searchable_list(items: list, height: int=8, on_select: callable=None) -> (tk.Frame, tk.StringVar, tk.Listbox)

---

此文档为项目内快速参考，若需生成更完整的 HTML 文档，请使用 MkDocs 或 Sphinx（项目已包含示例配置）。

## MediaMixin 新增接口（ck1.0）

### photo(photo_path: str='', text: str='', tcolor: str='#000000', tzt: str='Microsoft YaHei', tsize: int=20, tblod: bool=True, frame: int=0, warn_animated: bool=True)
- 返回：tk.Label 或 None
- 说明：显示静态图片。`frame` 指定显示第几帧（0 = 默认图 / 封面；None = 按文件默认解析）；
  多帧文件会在控制台提示帧数。旧调用（不传 frame）行为不变。

### animation(path: str='', text: str='', tcolor: str='#000000', tzt: str='Microsoft YaHei', tsize: int=20, tblod: bool=True, start: int=0, max_frames: int=None, max_loops: int=None, on_frame: callable=None, frame_delay: int=None)
- 返回：int（实际加载的帧数）
- 说明：播放 GIF / APNG / 动态 WebP。逐帧使用各自延时；`start` 可跳过封面帧（APNG 传 1 即直接播隐藏图）；
  `max_loops` 限制播放轮数；`on_frame(帧号, 总帧数)` 为每帧回调；`frame_delay` 可强制统一帧间隔。

### gif(gif_path: str='', text: str='', tcolor: str='#000000', tzt: str='Microsoft YaHei', tsize: int=20, tblod: bool=True, **kwargs)
- 返回：int（帧数）
- 说明：旧接口保留，内部转发到 `animation()`；因此现在也能播 APNG，额外参数透传。

### stop_animation()
- 返回：None
- 说明：停止动画播放（控件保留）。

### apng_info(path: str=None, deep: bool=True, max_frames: int=None)
- 返回：dict（见 `ck1_0.components.apng.parser.analyze`）
- 说明：分析图片结构；`path` 省略时用最近一次 photo()/animation() 加载的文件。

### apng_report(path: str=None, deep: bool=True, max_frames: int=None)
- 返回：str
- 说明：返回中文文本报告（`ck1_0.components.apng.parser.format_report`）。

### is_disguised_image(path: str=None, deep: bool=True)
- 返回：bool
- 说明：是否属于“默认图与动画帧不一致”的伪装 APNG（“查看原图”式骗图）。

### show_image_report(path: str=None, deep: bool=True, max_frames: int=None, title: str='图片结构检查报告')
- 返回：str（报告文本）
- 说明：弹出报告窗口（只读文本 + 滚动条 + 复制报告 / 拆帧导出按钮）。

### show_frames(path: str=None, columns: int=3, thumb_width: int=240, labels: bool=True, parent=None, max_frames: int=None)
- 返回：tk.Frame 或 None
- 说明：逐帧平铺预览；默认图 / 封面用红字标注，动画帧用绿字标注。

### export_frames(path: str=None, outdir: str=None, include_default: bool=True, prefix: str='frame')
- 返回：list[str]
- 说明：拆帧导出为独立 PNG；`outdir` 为空时弹出目录选择框。

## ck1_0/components/apng/parser.py（块级检查器，不需要 Pillow）

> 路径变更**：本模块原为 `utils/apng.py`，已迁入 `ck1_0/components/apng/parser.py`；
> `utils.apng` 保留为 deprecated 别名（一个版本周期）。

| 函数 | 说明 |
|---|---|
| `parse_png(path)` / `parse_bytes(data)` | 解析 PNG/APNG 块结构（acTL / fcTL / fdAT / tEXt 等） |
| `analyze(path, deep=True, max_frames=None)` | 综合报告：结构 + 逐帧明细 + 帧间差异 + 结论 |
| `format_report(info)` | 报告转中文文本 |
| `is_disguised(path, deep=True)` | 伪装判定 |
| `frame_stats(path)` / `frame_diffs(path)` | 逐帧统计 / 帧间差异（需要 Pillow） |
| `save_frames(path, outdir, include_default=True)` | 拆帧导出（需要 Pillow） |
| `inspect_text(text)` | 分析被另存为文本的图片副本（尽力而为） |
| `to_json(info)` | 报告转 JSON 文本 |
| `pil_available()` | Pillow 是否可用 |

> `ChatBarApngDisguise` 一类的聊天软件伪装标记可通过 `APNG_DISGUISE_KEYS` 扩展。
