# main.py
from gui.main_window import MainWindow
import tkinter as tk
from tkinter import messagebox


def _demo():
    app = MainWindow("现代化 GUI 演示", 900, 760)
    app.center_window()

    # 标题标签
    app.label_ck("📊 数据可视化面板", tsize=24)

    # 工具栏：主题切换与关于
    def set_theme(theme_name):
        try:
            if getattr(app, '_ttk_style', None):
                app._ttk_style.theme_use(theme_name)
        except Exception:
            pass

    def show_about():
        messagebox.showinfo("关于", "演示：工具栏、状态栏、搜索列表、图表与新增组件\nPowered by tkinter")

    toolbar_items = [
        ("主题", None, 'menu', [("默认", lambda: set_theme('default')), ("clam", lambda: set_theme('clam'))]),
        ("关于", show_about, 'button')
    ]
    app.create_toolbar(toolbar_items)

    # 状态栏
    status_widget, set_status = app.create_status_bar("就绪")

    # 可搜索列表示例（支持键盘 ↑/↓/Enter 与 set_items 动态更新）
    items = [f"用户 {i}" for i in range(1, 31)]

    def on_select(item):
        set_status(f"已选择: {item}")

    container, search_var, listbox = app.create_searchable_list(items, height=8, on_select=on_select)
    container.pack(pady=10, padx=10, fill='x')

    # 一个简单的可视化示例
    bars = app.scrollable_bars(
        data=[30, 60, 90, 45, 75, 20],
        canvas_width=600,
        canvas_height=200,
        label_rotation=0,
        show_bg_stripes=True
    )
    if bars:
        bars.pack(pady=10)

    # ================= 新增组件演示 =================

    # 快捷键：Ctrl+S 弹提示
    app.add_shortcut('<Control-s>', lambda: set_status("快捷键 Ctrl+S 已触发"))

    # 非阻塞 Toast 提示
    def on_toast():
        app.show_toast("保存成功！", kind="success")

    app.buttonx("弹出 Toast 提示", commandname=on_toast)

    # 可过滤下拉框（输入即自动补全）
    combo_var, combo = app.create_combo_box(
        ["苹果", "香蕉", "樱桃", "葡萄", "橘子", "西瓜"],
        default="苹果",
        on_select=lambda v: set_status(f"下拉选择了: {v}")
    )

    # 滑块（实时数值）与数字微调框
    slider_var, slider = app.create_slider(0, 100, default=40, label="音量",
                                           on_change=lambda v: set_status(f"音量: {v:g}"))
    spin_var, spin = app.create_spinbox(0, 100, default=10, step=5)

    # 现代开关
    toggle_var, toggle = app.create_toggle_switch("夜间模式", default=False,
                                                  command=lambda v: set_status(f"夜间模式: {'开' if v else '关'}"))

    # 智能表格
    table_container, tree = app.create_table(
        headers=["姓名", "年龄", "城市"],
        rows=[("张三", 25, "北京"), ("李四", 30, "上海"), ("王五", 22, "广州"), ("赵六", 28, "深圳")],
        on_select=lambda row, i: set_status(f"表格选中: {row}")
    )

    def export_table():
        path = app.export_table_csv(tree)
        if path:
            set_status(f"已导出: {path}")

    def copy_table():
        app.copy_table_clipboard(tree)
        set_status("表格已复制到剪贴板，可直接粘贴进 Excel")

    app.buttonx("导出表格 CSV", commandname=export_table)
    app.buttonx("复制到剪贴板", commandname=copy_table)

    # 新手引导入口
    app.buttonx("🎓 新手交互教程", commandname=lambda: app.show_tutorial())

    # 智能表单：一行描述自动生成整个表单
    form_container, get_values, set_values = app.create_form([
        ("name", "姓名", "entry", "张三"),
        ("age", "年龄", "spin", 0, 120, 25),
        ("gender", "性别", "combo", ["男", "女"], "男"),
        ("agree", "同意条款", "check", True),
        ("remark", "备注", "text", 3, "默认备注内容"),
    ])

    def submit_form():
        set_status(f"表单: {get_values()}")

    def reset_form():
        set_values({"name": "李四", "age": 30, "remark": "已重置"})
        set_status("表单已重置")

    app.buttonx("读取表单", commandname=submit_form)
    app.buttonx("重置表单", commandname=reset_form)

    # 选项卡容器
    def fill_chart_tab(tab):
        tk.Label(tab, text="这是图表选项卡").pack(pady=10)
        tk.Button(tab, text="点我", command=lambda: set_status("选项卡里的按钮")).pack()

    notebook, tabs = app.create_notebook([
        ("文字", lambda f: tk.Label(f, text="选项卡一内容：文字").pack(pady=8)),
        ("按钮", lambda f: (tk.Label(f, text="选项卡二").pack(pady=8), tk.Button(f, text="按钮").pack())),
        ("图表", fill_chart_tab),
    ])

    # 动态更新搜索列表数据（展示 set_items）
    def update_list():
        listbox.set_items([f"动态项 {i}" for i in range(1, 11)])
        set_status("搜索列表已动态更新")

    app.buttonx("更新列表", commandname=update_list)

    # 输入对话框
    def ask_name():
        name = app.ask_input("输入姓名", "请输入你的名字:", "张三")
        set_status(f"输入结果: {name}")

    app.buttonx("输入对话框", commandname=ask_name)

    app.run()


if __name__ == "__main__":
    _demo()
