# _smoke_test.py — 临时冒烟测试：实例化 MainWindow 并调用所有公开方法，不入主循环
import sys, traceback
import tkinter as tk

errors = []

def check(name, fn):
    try:
        fn()
        print(f"[OK]   {name}")
    except Exception:
        print(f"[FAIL] {name}")
        traceback.print_exc()
        errors.append(name)

from gui.main_window import MainWindow

app = MainWindow("smoke", 900, 700)

# 测试中屏蔽弹窗（photo/gif 错误路径会弹 messagebox，阻塞自动化测试）
app.show_message = lambda title, message, msg_type="info": None

# ---- 与 main.py 演示相同的路径 ----
app.label_ck("数据可视化面板", tsize=24)

def set_theme(name):
    if getattr(app, '_ttk_style', None):
        app._ttk_style.theme_use(name)

toolbar_items = [
    ("主题", None, 'menu', [("默认", lambda: set_theme('default')), ("clam", lambda: set_theme('clam'))]),
    ("关于", lambda: None, 'button'),
]
app.create_toolbar(toolbar_items)

status_widget, set_status = app.create_status_bar("就绪")
set_status("已更新")

items = [f"用户 {i}" for i in range(1, 31)]
container, search_var, listbox = app.create_searchable_list(items, height=10, on_select=lambda x: None)
container.pack(pady=10, padx=10, fill='x')

bars = app.scrollable_bars(data=[30, 60, 90, 45, 75, 20], canvas_width=600, canvas_height=200,
                           label_rotation=0, show_bg_stripes=True)
if bars:
    bars.pack(pady=10)

# ---- 之前失败的回归用例 ----
check("label_ck(tcolor=...)", lambda: app.label_ck("红标题", tcolor="#ff0000", tsize=18))
check("progress(max_value=0)", lambda: app.create_progress_bar(max_value=0)(5))
check("progress(负值)", lambda: app.create_progress_bar()(-10))
check("progress(超上限)", lambda: app.create_progress_bar(max_value=50)(999))

# ---- 搜索列表 Listbox 是否真正可见 ----
app.root.update_idletasks()
app.root.update()
def listbox_mapped():
    return bool(listbox.winfo_ismapped())
check("searchable_list.listbox 已显示", listbox_mapped)

# ---- WidgetMixin ----
check("buttonx", lambda: app.buttonx("提交", commandname=lambda: None))
check("input_box", lambda: app.input_box("搜索"))
check("label_ck", lambda: app.label_ck("标题", tsize=18))

# ---- DialogMixin ----
check("create_file_dialog", lambda: app.create_file_dialog())
check("create_message_box", lambda: app.create_message_box("提示", "完成", "info"))

# ---- MediaMixin ----
check("media.photo(不存在文件)", lambda: app.photo("__no_such_file__.png"))
check("media.gif(不存在文件)", lambda: app.gif("__no_such_file__.gif"))
check("media.clear_media", lambda: app.clear_media())

# ---- AdvancedWidgetMixin ----
check("create_text_area", lambda: app.create_text_area(40, 5))
check("create_checkbox", lambda: app.create_checkbox("启用", command=lambda: None))
check("create_radio_group", lambda: app.create_radio_group(["A", "B", "C"]))
check("create_progress_bar", lambda: app.create_progress_bar()(50))
check("create_menu", lambda: app.create_menu([("文件", [("退出", app.root.quit)])]))
check("create_clock", lambda: app.create_clock())
check("create_tooltip", lambda: app.create_tooltip(app.root, "tip"))
check("create_scrollable_canvas", lambda: app.create_scrollable_canvas())
check("create_scrollable_visualization_canvas", lambda: app.create_scrollable_visualization_canvas())
check("scrollable_labels", lambda: app.scrollable_labels(["x", "y", "z"]))
check("scrollable_labels(默认)", lambda: app.scrollable_labels())
check("scrollable_bars(空数据)", lambda: app.scrollable_bars(data=[]))
check("pack_vertical", lambda: app.pack_vertical(app.label_ck("a"), app.label_ck("b")))
check("pack_in_grid", lambda: app.pack_in_grid([[app.label_ck("a"), app.label_ck("b")], [app.label_ck("c")]]))
check("center_widget", lambda: app.center_widget(app.label_ck("c")))

# 处理事件队列，让 after/动画调度至少跑一轮
for _ in range(3):
    app.root.update()
    import time
    time.sleep(0.05)

# ---- 新增组件 ----
check("combo_box 创建", lambda: app.create_combo_box(["苹果", "香蕉"], default="苹果"))
check("combo_box 只读", lambda: app.create_combo_box(["a", "b"], editable=False))
check("slider 创建", lambda: app.create_slider(0, 100, default=50, label="音量"))
check("slider 精度0.5", lambda: app.create_slider(0, 10, default=3, resolution=0.5))
check("spinbox 创建", lambda: app.create_spinbox(0, 100, default=10, step=5))
check("toggle_switch 创建", lambda: app.create_toggle_switch("开关", default=True))
def toggle_test():
    v, c = app.create_toggle_switch("开关")
    v.set(False)
    c.event_generate('<Button-1>')
    app.root.update()
    return v.get()
check("toggle_switch 点击切换", toggle_test)
check("table 创建", lambda: app.create_table(headers=["姓名", "年龄"], rows=[("张三", 25)]))
check("table 空数据", lambda: app.create_table(headers=["a", "b"]))
check("form 创建+读写", lambda: (lambda f: (lambda c, g, s: (s({"name": "李四"}), g()))(*f))(app.create_form([("name", "姓名", "entry", "张三"), ("age", "年龄", "spin", 0, 120), ("gender", "性别", "combo", ["男", "女"]), ("ok", "同意", "check", True), ("note", "备注", "text", 2)])))
check("form 未知类型跳过", lambda: app.create_form([("x", "X", "bad_type")]))
check("notebook 创建", lambda: app.create_notebook([("页1", None), ("页2", lambda f: tk.Label(f, text="x").pack())]))
check("toast 提示", lambda: app.show_toast("测试提示", duration=500, kind="success"))
check("center_window", lambda: app.center_window())
check("add_shortcut", lambda: app.add_shortcut('<Control-x>', lambda: None))
check("set_always_on_top", lambda: app.set_always_on_top(True))
check("set_always_on_top(False)", lambda: app.set_always_on_top(False))
check("theme.set_theme", lambda: app.set_theme('clam'))
check("theme.configure_font", lambda: app.configure_font('Segoe UI', 10))
check("tooltip(延迟)", lambda: app.create_tooltip(app.root, "提示", delay_ms=100))
def set_items_test():
    c, sv, lb = app.create_searchable_list(["a", "b"])
    lb.set_items(["新1", "新2"])
    return lb.size() == 2 and lb.get(0) == "新1"
check("searchable_list.set_items", set_items_test)

# ---- 数据导出 ----
import tempfile, os
def export_csv_test():
    c, t = app.create_table(headers=["姓名", "分数"], rows=[("小明", 92), ("小红", 88)])
    p = os.path.join(tempfile.gettempdir(), "ck8_export_test.csv")
    res = app.export_table_csv(t, file_path=p)
    ok = res == p and os.path.exists(p)
    if os.path.exists(p):
        with open(p, encoding='utf-8-sig') as f:
            content = f.read()
        ok = ok and "小明" in content and "92" in content
        os.remove(p)
    return ok
check("export_table_csv", export_csv_test)
def save_csv_test():
    p = os.path.join(tempfile.gettempdir(), "ck8_save_test.csv")
    res = app.save_data_csv([(1, 2), (3, 4)], headers=["x", "y"], file_path=p)
    ok = res == p and os.path.exists(p)
    if os.path.exists(p):
        os.remove(p)
    return ok
check("save_data_csv", save_csv_test)
def save_json_test():
    p = os.path.join(tempfile.gettempdir(), "ck8_save_test.json")
    res = app.save_data_json({"姓名": "张三", "分数": [1, 2]}, file_path=p)
    ok = res == p and os.path.exists(p)
    if os.path.exists(p):
        with open(p, encoding='utf-8') as f:
            ok = ok and "张三" in f.read()
        os.remove(p)
    return ok
check("save_data_json", save_json_test)
def clipboard_test():
    c, t = app.create_table(headers=["a"], rows=[("x",), ("y",)])
    txt = app.copy_table_clipboard(t)
    return txt == "x\ny"
check("copy_table_clipboard", clipboard_test)

# ---- 新手引导系统 ----
def tutorial_pages_test():
    from gui.tutorial import TutorialWindow
    tw = TutorialWindow(app)
    total = len(tw.pages)
    for _ in range(total - 1):
        tw.next_page()
    tw.win.destroy()
    return total >= 8
check("tutorial 翻页全部页", tutorial_pages_test)
def show_tutorial_test():
    app.show_tutorial()
    app.root.update_idletasks()
    for w in app.root.winfo_children():
        if isinstance(w, tk.Toplevel):
            w.destroy()
    return True
check("MainWindow.show_tutorial", show_tutorial_test)
def launcher_import_test():
    import importlib
    m = importlib.import_module('launcher')
    return hasattr(m, 'main')
check("launcher 可导入", launcher_import_test)
def helpers_test():
    from utils.helpers import write_csv, write_json
    return callable(write_csv) and callable(write_json)
check("utils.helpers 导出函数", helpers_test)

# 处理事件队列，让 after/动画调度至少跑一轮
for _ in range(3):
    app.root.update()
    import time
    time.sleep(0.05)

app.root.destroy()

print("-" * 40)
print(f"结果: {len(errors)} 个失败 -> {errors}" if errors else "结果: 全部通过")
sys.exit(1 if errors else 0)
