# API 参考（自动导出） - ck0.9 GUI

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
