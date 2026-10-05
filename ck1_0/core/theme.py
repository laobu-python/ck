"""theme.py —— ck1.0 语义 token 表（Theme）

本模块是 `接口合同` 第 10 节《硬编码视觉与时序清单》的唯一落点：把散落在
`gui/*.py` 里的颜色、字体、尺寸、间距、时序常量集中成一组**语义 token**。

命名规则 / Naming rule
    token 名 = `接口合同` 第 10 节 "Semantic token" 列的点号分隔名，去掉最前面的
    类别段（`color.` / `font.` / `space.` / `timing.` / `size.` 等），再把 `.` 换成 `_`。
    例：`color.toggle.on_color` → `toggle_on`；`font.default_family` → `default_family`；
    `space.label_y` → `label_y`；`timing.feedback_reset_ms` → `feedback_reset_ms`。
    类别段保留在族名里（`toast_*`、`progress_*`、`media_*`、`bars_*`、`tutorial_*` …）。

基线值 / Baseline values
    **所有默认值都逐字等于当前源码里的硬编码值**（已逐个对照 `接口合同` 第 10 节与源码行
    核对）。这里不做任何"顺手改进"：颜色不归一化、字体不改写、尺寸不四舍五入。
    重构期间"默认值即视觉合同"，改动任何基线值都会造成视觉回归。

聚合 token / Aggregate tokens
    `bars_geometry` 与 `form_grid_spacing` 是聚合字典，由同一批标量 token 派生
    （见 `Theme._sync_aggregates`），避免同一个数字出现两份。

可变 token / Mutable tokens
    `data_export_titles`（以及聚合字典）这类**可变容器**在写入实例属性时会做浅拷贝
    （见 `_isolate`）：每个 Theme 实例都持有自己的副本，改一个实例的内容不会污染
    模块级 `_DEFAULTS`，也不会影响其它实例。token 容器只有一层，故浅拷贝足够。

未覆盖项 / Not covered here
   源码里还有若干视觉细节没有出现在 AGENTS  中（例如 bars 的字体除数 2.5、
    tutorial 报错标签的 `fg='red'`）。按 规则这些值**保持原样、不在本表中新增
    token**，只在交付说明里登记，等 AGENTS  更新后再纳入。

用法 / Usage
    theme = Theme()                      # 等于 Theme.light()
    theme = Theme(toggle_on='#00ff00')   # 局部覆盖
    theme = Theme.light().with_overrides(label_y=12)
    theme = Theme.dark()                 # 预留：目前无组件消费
"""
import copy


# --------------------------------------------------------------------------- #
# 基线 token 表（顺序 = 交付说明里的分组顺序）
# --------------------------------------------------------------------------- #
_DEFAULTS = {
    # ---------------- 颜色 / Colors ---------------- #
    'default_color': '#000000',                 # text.default_color      (window.py 75-80)
    'placeholder_color': 'grey',                # input.placeholder_color (widgets.py 53-59)
    'input_text_color': 'black',                # input.text_color        (widgets.py 53-59)
    'toast_info': '#2196f3',                    # color.toast.info        (dialogs.py 63-75)
    'toast_success': '#4caf50',                 # color.toast.success     (dialogs.py 63-75)
    'toast_warning': '#ff9800',                 # color.toast.warning     (dialogs.py 63-75)
    'toast_error': '#f44336',                   # color.toast.error       (dialogs.py 63-75)
    'toast_text_color': 'white',                # text.inverse            (dialogs.py 77-82)
    'progress_background': 'white',             # color.progress.background (advanced_widgets 232-281)
    'progress_track': 'lightgray',              # color.progress.track    (advanced_widgets 232-281)
    'progress_fill': 'green',                   # color.progress.fill     (advanced_widgets 232-281)
    'tooltip_background': 'lightyellow',        # color.tooltip.background (advanced_widgets 314-367)
    'scroll_background': '#f0f0f0',             # color.scroll_background (advanced_widgets 399-442)
    'toggle_on': '#4caf50',                     # color.toggle.on_color   (advanced_widgets 704-751)
    'toggle_off': '#bdbdbd',                    # color.toggle.off_color  (advanced_widgets 704-751)
    'toggle_knob': 'white',                     # color.toggle.knob       (advanced_widgets 704-751)
    'toggle_outline': '#999',                   # color.toggle.outline    (advanced_widgets 704-751)
    'media_frame_default': '#c62828',           # color.media.default_frame   (media.py 388-455)
    'media_frame_animation': '#2e7d32',         # color.media.animation_frame (media.py 388-455)
    'media_metadata_color': '#666',             # color.media.metadata    (media.py 388-455)
    'media_caption_color': '#000000',           # media.caption_*         (media.py 120-153,212-266,282)
    'viz_background': '#2d3748',                # color.viz_background    (advanced_widgets 1037-1081)
    'labels_background': '#ffffff',             # color.labels.background (advanced_widgets 1083-1118)
    'labels_label_background': '#ffffff',       # color.labels.label_bg   (advanced_widgets 1083-1118)
    'labels_label_color': 'black',              # color.labels.label_fg   (advanced_widgets 1083-1118)
    'bars_background': '#2d3748',               # color.bars.background   (advanced_widgets 1120-1203)
    'bars_stripe': '#333',                      # color.bars.stripe       (advanced_widgets 1120-1203)
    'bars_stripe_light': 'gray50',              # color.bars.stripe_light (advanced_widgets 1120-1203)
    'bars_text_color': 'white',                 # color.bars.text         (advanced_widgets 1120-1203)
    'bars_outline': 'white',                    # color.bars.outline      (advanced_widgets 1120-1203)
    'tutorial_progress_color': '#888',          # color.tutorial.progress (tutorial.py 52-55)
    'tutorial_card_background': 'white',        # color.tutorial.card     (tutorial.py 58-68)
    'tutorial_title_background': 'white',       # color.tutorial.*        (tutorial.py 58-68)
    'tutorial_demo_background': 'white',        # color.tutorial.demo     (tutorial.py 166-252)
    'tutorial_desc_color': '#444',              # color.tutorial.*        (tutorial.py 58-68)
    'tutorial_demo_label_color': '#555',        # color.tutorial.demo     (tutorial.py 229-252)
    'toast_overrideredirect': True,             # toast.window_flags      (dialogs.py 77-82)
    'toast_topmost': True,                      # toast.window_flags      (dialogs.py 77-82)

    # ---------------- 字体 / Fonts ---------------- #
    'default_family': 'Microsoft YaHei',        # font.default_family     (window.py 75-80)
    'title_size': 20,                           # font.title_size         (window.py 75-80)
    'title_weight': 'bold',                     # font.title_weight       (window.py 75-80)
    # — label body-text default; distinct from title_size (heading)
    'label_default_size': 12,                   # label.default_size      （非既有硬编码，稍后登记）
    # — label body-text default; distinct from title_weight (heading)
    'label_default_bold': False,                # label.default_bold      （非既有硬编码，稍后登记）
    'input': ('Microsoft YaHei', 15, 'bold'),   # font.input              (widgets.py 53-59)
    'clock': ('Arial', 18),                     # font.clock              (advanced_widgets 369-397)
    'report': ('Consolas', 10),                 # font.report             (media.py 339-373)
    'labels': ('Arial', 10),                    # font.labels             (advanced_widgets 1083-1118)
    'toast': ('Microsoft YaHei', 10),           # font.toast              (dialogs.py 77-82)
    'media_frame': ('Microsoft YaHei', 9, 'bold'),      # font.media_frame (media.py 388-455)
    'media_frame_metadata': ('Microsoft YaHei', 9),     # font.media_frame (media.py 388-455)
    'media_caption_family': 'Microsoft YaHei',  # media.caption_*         (media.py 120-153,212-266,282)
    'media_caption_size': 20,                   # media.caption_*         (media.py 120-153,212-266,282)
    'media_caption_weight': 'bold',             # media.caption_*         (media.py 120-153,212-266,282)
    'media_caption_compound': 'top',            # media.caption_*         (media.py 120-153,212-266,282)
    'bars_font_family': 'Arial',                # font.bars               (advanced_widgets 1120-1203)
    'bars_font_min': 6,                         # font.bars               (advanced_widgets 1120-1203)
    'bars_font_max': 12,                        # font.bars               (advanced_widgets 1120-1203)
    'tutorial_title': ('Microsoft YaHei', 16, 'bold'),  # font.tutorial.title (tutorial.py 58-68)
    'tutorial_desc': ('Microsoft YaHei', 10),           # font.tutorial.desc  (tutorial.py 58-68)
    'tutorial_progress': ('Microsoft YaHei', 9),        # font.tutorial.progress (tutorial.py 52-55)
    'tutorial_demo_label': ('Microsoft YaHei', 10),     # font.tutorial.demo  (tutorial.py 166-252)

    # ---------------- 间距 / Spacing ---------------- #
    'label_y': 10,                              # space.label_y           (window.py 75-80)
    'button_y': 10,                             # space.button_y          (widgets.py 33,49-50)
    'feedback_y': 5,                            # space.feedback_y        (widgets.py 33,49-50)
    'input_y': 10,                              # space.input_y           (widgets.py 53-59)
    'input_ipady': 0,                           # space.input_y           (widgets.py 53-59, ipady=0)
    'checkbox_y': 5,                            # space.checkbox_y        (advanced_widgets 166-192)
    'radio_y': 10,                              # space.radio_y           (advanced_widgets 194-230)
    'clock_y': 10,                              # space.clock_y           (advanced_widgets 369-397)
    'dialog_button_y': 5,                       # space.dialog_button_y   (dialogs.py 22,51-52)
    'toast_padx': 16,                           # space.toast_*           (dialogs.py 77-82)
    'toast_pady': 8,                            # space.toast_*           (dialogs.py 77-82)
    'toast_bottom_offset': 40,                  # toast.bottom_offset     (dialogs.py 89)
    'combo_pady': 5,                            # combo.spacing           (advanced_widgets 584-627)
    'combo_padx': 5,                            # combo.spacing           (advanced_widgets 584-627)
    'spin_pady': 5,                             # spin.spacing            (advanced_widgets 678-702)
    'spin_padx': 5,                             # spin.spacing            (advanced_widgets 678-702)
    'slider_pady': 5,                           # slider.*_spacing        (advanced_widgets 629-676)
    'slider_label_padx': (10, 5),               # slider.label/value_spacing (advanced_widgets 629-676)
    'slider_value_padx': (5, 10),               # slider.label/value_spacing (advanced_widgets 629-676)
    'slider_value_width': 8,                    # slider.*_spacing        (advanced_widgets 629-676)
    'form_grid_label_padx': (10, 5),            # form.grid_spacing       (advanced_widgets 814-916)
    'form_grid_cell_padx': (5, 10),             # form.grid_spacing       (advanced_widgets 814-916)
    'form_grid_pady': 3,                        # form.grid_spacing       (advanced_widgets 814-916)
    'form_pady': 5,                             # form.grid_spacing       (advanced_widgets 814-916)
    'notebook_pady': 5,                         # notebook.spacing        (advanced_widgets 918-957)
    'notebook_content_pady': 4,                 # notebook.spacing        (advanced_widgets 918-957)
    'labels_label_padx': 10,                    # labels.spacing          (advanced_widgets 1083-1118)
    'labels_label_pady': 5,                     # labels.spacing          (advanced_widgets 1083-1118)
    'bars_padding': 10,                         # bars.geometry           (advanced_widgets 1120-1203)
    'bars_spacing': 5,                          # bars.geometry           (advanced_widgets 1120-1203)
    'bars_label_band': 25,                      # bars.geometry           (advanced_widgets 1120-1203)
    'bars_height_reserve': 15,                  # bars.geometry           (advanced_widgets 1120-1203)
    'layout_pack_vertical': (10, 10),           # layout.pack_vertical    (advanced_widgets 1204-1277)
    'layout_grid': (5, 5),                      # layout.grid             (advanced_widgets 1204-1277)
    'layout_center': 10,                        # layout.center           (advanced_widgets 1204-1277)
    'tutorial_progress_padx': 12,               # tutorial.progress_*     (tutorial.py 52-55)
    'tutorial_progress_pady': (12, 2),          # tutorial.progress_*     (tutorial.py 52-55)
    'tutorial_card_padx': 12,                   # tutorial.card_*         (tutorial.py 58-68)
    'tutorial_card_pady': 6,                    # tutorial.card_*         (tutorial.py 58-68)
    'tutorial_card_relief': 'groove',           # color.tutorial.card     (tutorial.py 58-68)
    'tutorial_card_borderwidth': 1,             # color.tutorial.card     (tutorial.py 58-68)
    'tutorial_title_pady': (14, 6),             # tutorial.card_*         (tutorial.py 58-68)
    'tutorial_desc_padx': 18,                   # tutorial.card_*         (tutorial.py 58-68)
    'tutorial_desc_pady': 2,                    # tutorial.card_*         (tutorial.py 58-68)
    'tutorial_demo_padx': 18,                   # tutorial.card_*         (tutorial.py 58-68)
    'tutorial_demo_pady': 10,                   # tutorial.card_*         (tutorial.py 58-68)
    'tutorial_navigation_pady': 10,             # tutorial.navigation_*   (tutorial.py 71-77)
    'tutorial_nav_padx': 6,                     # tutorial.navigation_*   (tutorial.py 71-77)
    'tutorial_demo_button_pady': 6,             # tutorial.demo_*         (tutorial.py 166-252)
    'list_container_pady': 5,                   # list.spacing            (advanced_widgets 478-582)
    'list_padx': 5,                             # list.spacing            (advanced_widgets 478-582)
    'list_pady': 2,                             # list.spacing            (advanced_widgets 478-582)
    'toolbar_item_padx': 2,                     # toolbar.item_spacing    (advanced_widgets 444-464)
    'toolbar_item_pady': 2,                     # toolbar.item_spacing    (advanced_widgets 444-464)
    'tooltip_padx': 4,                          # tooltip.border/padding  (advanced_widgets 314-367)
    'tooltip_pady': 2,                          # tooltip.border/padding  (advanced_widgets 314-367)
    'tooltip_offset': (12, 12),                 # tooltip.offset          (advanced_widgets 314-367)
    'table_container_pady': 5,                  # table.default_*         (advanced_widgets 753-812)
    'dialog_input_label_padx': 12,              # dialog.input_*          (dialogs.py 106-131)
    'dialog_input_label_pady': (12, 4),         # dialog.input_*          (dialogs.py 106-131)
    'dialog_input_entry_padx': 12,              # dialog.input_*          (dialogs.py 106-131)
    'dialog_input_entry_pady': 4,               # dialog.input_*          (dialogs.py 106-131)
    'dialog_input_buttons_pady': 8,             # dialog.input_*          (dialogs.py 106-131)
    'dialog_button_padx': 6,                    # dialog.input_*          (dialogs.py 106-131)
    'input_text_area_pady': 10,                 # input.text_area_*       (advanced_widgets 95-164)
    'toggle_frame_pady': 5,                     # color/space toggle.*    (advanced_widgets 704-751)
    'toggle_canvas_padx': 5,                    # space toggle.*          (advanced_widgets 704-751)

    # ---------------- 尺寸 / Sizes ---------------- #
    'button_default_width': 15,                 # button.default_width    (widgets.py 13)
    'button_default_height': 2,                 # button.default_height   (widgets.py 13)
    'input_default_width': 30,                  # input.default_width     (widgets.py 53-59)
    'progress_default_width': 300,              # progress.default_width  (advanced_widgets 232-281)
    'progress_default_height': 20,              # progress.default_height (advanced_widgets 232-281)
    # 裁决（设计记录）：宽/高拆为**独立** token，便于只自定义其一。
    # 原成对 token `toggle_default_size` 已移除（零消费者，且成对值无法表达"只传 width"）。
    'toggle_default_width': 56,                 # toggle.default_width    (advanced_widgets 704-751)
    'toggle_default_height': 28,                # toggle.default_height   (advanced_widgets 704-751)
    # ：Qt `toggle` 的 QSS **字面量** token 化。
    # 这两个值**没有首版出处**（首版的开关是 Tk 自绘轨道，无边框/圆角概念），
    # 是 Qt 实现引入的视觉常量；token 化后由 `qt/handles.py` 消费，可集中调参、也可目视签收。
    'toggle_border_width': 1,                   # toggle.border_width     (qt/handles.py QSS； ③)
    'toggle_radius': 3,                         # toggle.radius           (qt/handles.py QSS； ③)
    'table_default_height': 10,                 # table.default_*         (advanced_widgets 753-812)
    'table_select_mode': 'browse',              # table.default_*         (advanced_widgets 753-812)
    'table_column_width_min': 80,               # table.column_width.*    (advanced_widgets 753-812)
    'table_column_width_max': 400,              # table.column_width.*    (advanced_widgets 753-812)
    'table_title_width_factor': 14,             # table.column_width.*    (advanced_widgets 753-812)
    'table_row_width_factor': 11,               # table.column_width.*    (advanced_widgets 753-812)
    'table_row_width_extra': 18,                # table.column_width.*    (advanced_widgets 753-812)
    'table_anchor': 'w',                        # table.anchor            (advanced_widgets 753-812)
    'notebook_default_size': (600, 280),        # notebook.default_size   (advanced_widgets 918-957) (width, height)
    'viz_default_size': (800, 120),             # viz.default_size        (advanced_widgets 1037-1081) (width, height)
    'viz_border': 0,                            # viz.border              (advanced_widgets 1037-1081)
    'labels_default_width': 500,                # labels.default_*        (advanced_widgets 1083-1118)
    'labels_default_height': 100,               # labels.default_*        (advanced_widgets 1083-1118)
    'bars_default_width': 800,                  # bars.default_*          (advanced_widgets 1120-1203)
    'bars_default_height': 120,                 # bars.default_*          (advanced_widgets 1120-1203)
    'bars_min_bar_width': 20,                   # bars.default_*          (advanced_widgets 1120-1203)
    'scroll_default_width': 500,                # scroll.canvas_default_* (advanced_widgets 399-442)
    'scroll_default_height': 300,               # scroll.canvas_default_* (advanced_widgets 399-442)
    'scroll_border': 0,                         # scroll.border           (advanced_widgets 399-442)
    'list_default_height': 8,                   # list.default_height     (advanced_widgets 478-582)
    'list_scroll_width': 400,                   # list.scroll_width       (advanced_widgets 478-582)
    'list_row_height': 20,                      # list.row_height         (advanced_widgets 478-582)
    'combo_default_width': 25,                  # combo.default_width     (advanced_widgets 584-627)
    'spin_default_from': 0,                     # spin.default_*          (advanced_widgets 678-702)
    'spin_default_to': 100,                     # spin.default_*          (advanced_widgets 678-702)
    'spin_default_step': 1,                     # spin.default_*          (advanced_widgets 678-702)
    'spin_default_width': 10,                   # spin.default_*          (advanced_widgets 678-702)
    'slider_default_from': 0,                   # slider.default_*        (advanced_widgets 629-676)
    'slider_default_to': 100,                   # slider.default_*        (advanced_widgets 629-676)
    'slider_default_resolution': 1,             # slider.default_*        (advanced_widgets 629-676)
    'slider_default_width': 300,                # slider.default_*        (advanced_widgets 629-676)
    'form_default_width': 40,                   # form.default_width      (advanced_widgets 814-916)
    'form_text_lines': 4,                       # form.text_lines         (advanced_widgets 814-916)
    'input_text_area_width': 50,                # input.text_area_*       (advanced_widgets 95-164)
    'input_text_area_height': 10,               # input.text_area_*       (advanced_widgets 95-164)
    'tutorial_window_size': (700, 480),         # tutorial.window_*       (tutorial.py 43-45) (width, height)
    'tutorial_nav_button_width': 10,            # tutorial.navigation_*   (tutorial.py 71-77)
    'tutorial_nav_close_width': 8,              # tutorial.navigation_*   (tutorial.py 71-77)
    'tutorial_desc_wraplength': 640,            # tutorial.card_*         (tutorial.py 58-68)
    'tutorial_demo_progress_width': 420,        # tutorial.demo_*         (tutorial.py 186-194)
    'dialog_input_entry_width': 32,             # dialog.input_*          (dialogs.py 106-131)
    'dialog_button_width': 8,                   # dialog.button_width     (dialogs.py 106-131)
    'checkbox_default': False,                  # control.checkbox_default (advanced_widgets 166-192)
    'radio_default': 0,                         # control.radio_default   (advanced_widgets 194-230)
    'radio_anchor': 'w',                        # control.radio_default   (advanced_widgets 194-230)
    'menu_tearoff': 0,                          # menu.tearoff            (advanced_widgets 283-312)
    'toolbar_menu_tearoff': 0,                  # toolbar.menu_tearoff    (advanced_widgets 444-464)
    'status_borderwidth': 1,                    # status.border/relief    (advanced_widgets 466-476)
    'tooltip_borderwidth': 1,                   # tooltip.border/padding  (advanced_widgets 314-367)

    # ---------------- 时序 / Timing ---------------- #
    'feedback_reset_ms': 1000,                  # timing.feedback_reset_ms        (widgets.py 39)
    'toast_default_duration_ms': 2000,          # toast.default_duration_ms       (dialogs.py 63-75)
    'clock_ms': 1000,                           # timing.clock_ms                 (advanced_widgets 369-397)
    'media_default_frame_delay_ms': 100,        # media.default_frame_delay_ms    (media.py 49)
    'media_min_frame_delay_ms': 20,             # media.min_frame_delay_ms        (media.py 197-207)
    'tooltip_delay_ms': 400,                    # tooltip.delay_ms                (advanced_widgets 314-367)

    # ---------------- 几何 / Geometry ---------------- #
    'layout_main_scrollbar_side': 'right',      # layout.main_scrollbar   (window.py 25,33-34)
    'layout_main_scrollbar_fill': 'y',          # layout.main_scrollbar   (window.py 25,33-34)
    'layout_main_scrollbar_orient': 'vertical',  # layout.main_scrollbar  (window.py 25,33-34)
    'layout_main_canvas_side': 'left',          # layout.main_scrollbar   (window.py 25,33-34)
    'layout_main_canvas_fill': 'both',          # layout.main_scrollbar   (window.py 25,33-34)
    'layout_main_canvas_expand': True,          # layout.main_scrollbar   (window.py 25,33-34)
    'slider_orient': 'horizontal',              # slider.default_*        (advanced_widgets 629-676)

    # ---------------- 文本与杂项 / Text & misc ---------------- #
    'default_title': 'Tkinter App',             # window.default_title    (window.py 8,11)
    'default_size': (800, 600),                 # window.default_size     (window.py 8,11)
    'feedback_initial_text': '点按钮 ',          # feedback.initial_text   (widgets.py 13)
    'feedback_active_text': '已经点击 ',          # feedback.active_text    (widgets.py 13)
    'list_placeholder': '输入关键字过滤…',        # list.placeholder        (advanced_widgets 478-582)
    'status_default_text': 'Ready',             # status.default_text     (advanced_widgets 466-476)
    'status_relief': 'sunken',                  # status.border/relief    (advanced_widgets 466-476)
    'status_anchor': 'w',                       # status.anchor           (advanced_widgets 466-476)
    'tooltip_relief': 'solid',                  # tooltip.border/padding  (advanced_widgets 314-367)
    'clock_color': 'black',                     # color.clock             (advanced_widgets 369-397)
    'clock_format': '%Y-%m-%d %H:%M:%S',        # clock.format            (advanced_widgets 369-397)
    'dialog_message_button_template': '显示{msg_type}消息',   # dialog.message_button_template (dialogs.py 22,51-52)
    'media_export_dialog_title': '选择拆帧输出目录',           # media.export_dialog_title      (media.py 478-480)
    'media_report_window_size': (820, 560),     # media.report_window_*   (media.py 339-373) (width, height)
    'media_thumb_width': 240,                   # media.thumb_width       (media.py 402)
    'media_report_button_padx': (8, 4),         # media.report_buttons    (media.py 339-373)
    'media_report_button_pady': 6,              # media.report_buttons    (media.py 339-373)
    'media_frame_grid_padx': 8,                 # media.frame_grid        (media.py 388-455)
    'media_frame_grid_pady': 8,                 # media.frame_grid        (media.py 388-455)
    'data_export_titles': {                     # data.export_titles      (advanced_widgets 959-1035)
        'csv_table': '导出表格为 CSV',
        'csv_data': '导出数据为 CSV',
        'json_data': '导出数据为 JSON',
    },
    'clipboard_separator': '\t',                # clipboard.separator     (advanced_widgets 959-1035)
    'clipboard_line_separator': '\n',           # clipboard.line_separator (advanced_widgets 959-1035)
    'tutorial_window_title': '新手交互教程',   # tutorial.window_*       (tutorial.py 43-45)
    'tutorial_window_transient': True,          # tutorial.window_*       (tutorial.py 43-45)
    'tutorial_prev_text': '← 上一步',            # tutorial.navigation_*   (tutorial.py 71-77)
    'tutorial_next_text': '下一步 →',            # tutorial.navigation_*   (tutorial.py 71-77)
    'tutorial_done_text': '完成',                # tutorial.progress_text  (tutorial.py 229-252)
    'tutorial_progress_text': '第 {i} / {n} 页',  # tutorial.progress_text  (tutorial.py 229-252)
    'tutorial_nav_state_normal': 'normal',      # tutorial.navigation_state (tutorial.py 229-252)
    'tutorial_nav_state_disabled': 'disabled',  # tutorial.navigation_state (tutorial.py 229-252)
}

# 由标量 token 派生的聚合 token（不放进 _DEFAULTS，避免同一个数字存两份）
_AGGREGATE_KEYS = ('bars_geometry', 'form_grid_spacing')

# 允许出现在 overrides 里的全部 token 名：基线 token + 聚合 token
_ALL_TOKEN_KEYS = frozenset(_DEFAULTS) | frozenset(_AGGREGATE_KEYS)


def _isolate(value):
    """返回不与入参共享可变容器的等值对象（浅拷贝）。

    `_DEFAULTS` 里的 `data_export_titles` 是**模块级 dict**；若把它直接赋给实例属性，
    所有 Theme 实例会共享同一个 dict —— 改一个实例的内容会污染基线默认表，
   并影响此后创建的每一个实例（复审观察项）。

    浅拷贝足够：token 容器只有一层（`data_export_titles` 是 `str -> str`，
    `bars_geometry` / `form_grid_spacing` 是 `str -> 标量`），容器内的值本身都不可变。
    不可变值（int/str/bool/None/tuple…）经 `copy.copy` 原样返回，不产生额外开销。

    参数:
        value: 任意 token 值。

    返回:
        与 `value` 等值、但不与之共享可变容器的对象。
    """
    return copy.copy(value)


class Theme:
    """ck1.0 语义 token 容器。

    所有 token 都是实例属性（无嵌套命名空间），可以直接 `theme.toggle_on` 读取。
   基线值见模块级 `_DEFAULTS`，逐字等于 `接口合同` 第 10 节的当前硬编码值。

    `bars_geometry` / `form_grid_spacing` 是聚合字典，由同名的标量 token 派生：

        bars_geometry      = {'min_bar_width', 'padding', 'spacing', 'label_band', 'height_reserve'}
        form_grid_spacing  = {'label_padx', 'cell_padx', 'pady'}

    可变 token（`data_export_titles` 与上面两个聚合字典）在赋值时会浅拷贝，因此
    实例之间、实例与模块级 `_DEFAULTS` 之间都**不共享容器**（详见 `_isolate`）。

    未知 token 快速失败：构造函数只接受 `_DEFAULTS` 与 `_AGGREGATE_KEYS` 里的名字，
    其他名字一律抛 `KeyError`（不做静默忽略、不做拼写纠正），以免 token 拼写错误被掩盖。
    """

    def __init__(self, **overrides):
        """用基线值初始化，再套用 `overrides`。

        参数:
            **overrides: token 名 → 新值；未给出的 token 使用 `_DEFAULTS` 的基线值。
                名字必须是 `_DEFAULTS` 或 `_AGGREGATE_KEYS` 中的已知 token。

        返回:
            None（实例构造完成）。

        异常:
            KeyError: 传入了未知 token 名；错误信息里包含全部未知名字。
        """
        unknown = [key for key in overrides if key not in _ALL_TOKEN_KEYS]
        if unknown:
            raise KeyError(
                '未知主题 token: %s（可用的名字见 ck1_0/core/theme.py 的 _DEFAULTS / _AGGREGATE_KEYS）'
                % ', '.join(sorted(unknown))
            )
        for name, value in _DEFAULTS.items():
            setattr(self, name, _isolate(value))
        for name, value in overrides.items():
            setattr(self, name, _isolate(value))
        # 若调用方没有显式给出聚合 token，则按标量重建，保证两者不漂移
        if not any(key in overrides for key in _AGGREGATE_KEYS):
            self._sync_aggregates()

    def _sync_aggregates(self):
        """按当前标量 token 重建 `bars_geometry` / `form_grid_spacing`。"""
        self.bars_geometry = {
            'min_bar_width': self.bars_min_bar_width,
            'padding': self.bars_padding,
            'spacing': self.bars_spacing,
            'label_band': self.bars_label_band,
            'height_reserve': self.bars_height_reserve,
        }
        self.form_grid_spacing = {
            'label_padx': self.form_grid_label_padx,
            'cell_padx': self.form_grid_cell_padx,
            'pady': self.form_grid_pady,
        }

    @classmethod
    def light(cls):
        """返回基线（浅色）主题，等价于 `Theme()`。

        返回:
            Theme
        """
        return cls()

    @classmethod
    def dark(cls):
        """返回一个最小可用的深色主题（预留，当前没有组件消费）。

       只覆盖文字色 token：AGENTS  没有登记“通用背景面”token，因此本主题不提供
        background（未登记的名字会被构造函数拒绝），避免出现 Section 10 之外的 token。
        基线视觉值不参与其中，因此不会影响既有 Tk 外观。

        返回:
            Theme
        """
        return cls(
            default_color='#e0e0e0',
            input_text_color='#e0e0e0',
            placeholder_color='#9e9e9e',
        )

    def with_overrides(self, **kw):
        """基于当前主题派生一个新主题（不修改自身）。

        参数:
            **kw: 要覆盖的 token；未给出的 token 沿用当前值。

        返回:
            Theme：新实例。
        """
        base = {k: v for k, v in self.__dict__.items() if k not in _AGGREGATE_KEYS}
        base.update(kw)
        return Theme(**base)
