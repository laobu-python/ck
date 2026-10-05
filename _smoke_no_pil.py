# _smoke_no_pil.py — 验证未安装 Pillow 时库仍可导入使用（仅 photo/gif 给出提示）
import sys, traceback

errors = []

def check(name, fn):
    try:
        fn()
        print(f"[OK]   {name}")
    except Exception:
        print(f"[FAIL] {name}")
        traceback.print_exc()
        errors.append(name)

# 确认当前解释器确实没有 PIL
try:
    import PIL
    print("本环境已安装 Pillow，跳过无 PIL 验证")
    sys.exit(0)
except ImportError:
    pass

# 关键：以前这行 import 就会因 PIL 缺失而 ModuleNotFoundError
from gui.main_window import MainWindow

app = MainWindow("nopil", 600, 400)
app.show_message = lambda title, message, msg_type="info": None

check("label_ck", lambda: app.label_ck("标题", tcolor="red"))
check("buttonx", lambda: app.buttonx("按钮"))
check("input_box", lambda: app.input_box("输入"))
check("create_toolbar", lambda: app.create_toolbar([("关于", lambda: None, 'button')]))
check("create_status_bar", lambda: app.create_status_bar("就绪"))
check("create_searchable_list", lambda: app.create_searchable_list(["x", "y"]))
check("scrollable_bars", lambda: app.scrollable_bars(data=[1, 2, 3]))
check("media.photo 无PIL提示", lambda: app.photo("a.png"))
check("media.gif 无PIL提示", lambda: app.gif("a.gif"))
check("create_clock", lambda: app.create_clock())

app.root.update()
app.root.destroy()

print("-" * 40)
print(f"结果: {len(errors)} 个失败 -> {errors}" if errors else "结果: 无 Pillow 环境下全部通过")
sys.exit(1 if errors else 0)
