# launcher.py —— 新手启动器
"""ck1.0 新手启动器：一个窗口四个大按钮，双击即可选择进入演示 / 教程 / 文档 / 图片检查器。

用法:
    python launcher.py              打开启动器界面
    python launcher.py --tutorial   直接打开新手交互教程
"""
import os
import subprocess
import sys

from ck1_0.renderer.base import Layout
from gui.main_window import MainWindow
from gui.widgets import _content_parent, _renderer_of
from gui.tutorial import TutorialWindow

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _open_docs():
    """用系统默认程序打开 README.md。"""
    path = os.path.join(_BASE_DIR, 'README.md')
    try:
        os.startfile(path)
    except Exception as e:
        print('无法打开文档:', e)


def _make_launcher_button(app, text, color, command):
    """启动器的一个**带样式按钮**（中立化；**也是 的回归守卫锚点**）。

    控件本身走 renderer 的中立 `button(...)`；中立契约**没有** `bg`/`fg`/`relief`/`cursor`/
    `active*`/`pady` 这些参数 ⇒ 用**契约允许的逃生口** `handle.native.configure(...)` 补齐，
    **外观与首版逐字相同**（是否给中立 `button()` 补这些视觉参数 = 候选）。

    ⚠️ （人眼发现，勿再犯）**：中立 `button()` 的 `color` 参数映射的是 **`fg`（文字色）**、
    **不是背景色**。首版把启动器的**背景色**传进了 `color=`，随后又被逃生口的 `fg='white'` 覆盖
    ⇒ **白字落默认灰底、几乎看不见**（用户看到的就是「启动器看着是空的」）。
    故这里：中立参数**只给字体/尺寸/宽度**，背景/前景/active/relief/pady/cursor **全走逃生口**。
    """
    _r = _renderer_of(app)
    _b = _r.button(_content_parent(app), text, command=command,
                   family='Microsoft YaHei', size=13, bold=True, width=28)
    _b.native.configure(bg=color, fg='white', pady=8, cursor='hand2', activebackground=color,
                        activeforeground='white', relief='flat')
    _b.layout(Layout.pack(pady=7))
    return _b


def _release_window():
    """关闭启动器窗口，并**释放**它的 backend root。

    **为什么不能只写 `app.root.destroy()`**（首版的写法）：（早期签字「backend
    root 进程内唯一」）要求 —— 想在同一进程里**再建**一个窗口，必须先把旧窗口的 Renderer
   释放掉。只销毁 Tk root 会留下**失效的单例登记**，下一个 `MainWindow()` 会撞上 的
    既定快速失败（底层 `TclError`，对新手是一句看不懂的英文报错）。

    **本函数留在 `launcher.py` 是为了保住那两处调用点的语义位置**；实现改走**公开**的
    `Btk.close()`（这条纪律此前只有私有入口 `app._renderer.destroy()`）。
    `close()` 转发 `Renderer.destroy()` 且**幂等**（重复调用静默返回），行为与改前逐字相同。
    """
    app.close()


def _run_demo():
    """关闭启动器并运行完整演示（同一进程）。"""
    _release_window()
    import main
    main._demo()


def _run_apng_tool():
    """关闭启动器并打开「图片 / 伪装图检查器」（同一进程）。"""
    _release_window()
    import apng_tool
    apng_tool.run_gui()


def _run_guide(script):
    """关闭启动器并**另起一个进程**跑某个新手引导。

    **为什么用子进程**（而不是像 `_run_demo` 那样同进程 `import`）：三个引导是**三份独立脚本**
    （`guide_tk.py` / `guide_hybrid.py` / `guide_qt.py`），其中两份要拉起 Qt 事件循环、
    与 Tk 的 mainloop 属于**不同**的进程级框架 ⇒ 各自独占一个进程最稳（也避免"引导崩了把
    启动器一起带走"）。启动器先关掉自己（释放 backend root），再把控制权交给子进程。
    """
    _release_window()
    subprocess.Popen([sys.executable, os.path.join(_BASE_DIR, script)], cwd=_BASE_DIR)


def _section(title):
    """启动器里的分组小标题（中立 `label` + 逃生口补 `bg`）。"""
    _r = _renderer_of(app)
    _lbl = _r.label(_content_parent(app), title, color='#666',
                    family='Microsoft YaHei', size=10, bold=True)
    _lbl.native.configure(bg='#ffffff')
    _lbl.layout(Layout.pack(anchor='w', padx=14, pady=(12, 0)))


def main():
    global app
    app = MainWindow("ck1.0 新手启动器", 560, 520)
    app.center_window()

    if '--tutorial' in sys.argv:
        # 直接进入新手教程
        TutorialWindow(app)
        app.run()
        return

    app.label_ck("欢迎使用 ck1.0 GUI 库", tsize=22)

    def _make_button(text, color, command):
        return _make_launcher_button(app, text, color, command)

    # **引导放在最前面**：它们是"从零上手"的主入口，且窗口在 150% DPI 下装不下 7 个按钮
    # ⇒ 把最该被看见的三个放在**首屏可见区**，
    # 其余四个往下排（内容区可滚动，都够得着）。
    _section('新手引导（三个版本，任选一个）')
    # 文案里**不再用彩色 emoji**（Microsoft YaHei 没有这些字形，会显示成豆腐块方框）
    _make_button("新手引导 · Tk 轻量级", '#00897b', lambda: _run_guide('guide_tk.py'))
    _make_button("新手引导 · Tk + PySide6 混合", '#3949ab',
                 lambda: _run_guide('guide_hybrid.py'))
    _make_button("新手引导 · 纯 PySide6（高级）", '#d81b60',
                 lambda: _run_guide('guide_qt.py'))

    _section('开始使用')
    _make_button("运行完整演示", '#2196f3', _run_demo)
    _make_button("新手交互教程（推荐）", '#4caf50',
                 lambda: TutorialWindow(app))
    _make_button("打开使用文档", '#ff9800', _open_docs)
    _make_button("图片检查器（识别伪装图）", '#8e24aa', _run_apng_tool)

    # 同上：中立 `label(...)` + 逃生口补 `wraplength`（中立契约没有它 —— 属 的同族缺口）。
    _r = _renderer_of(app)
    _hint = _r.label(_content_parent(app),
                     '第一次接触 Python？点「新手交互教程」就行，全程鼠标点击，不用写代码。\n'
                     '想直接上手项目？点「新手引导」任选一版：Tk 版最省资源；'
                     '混合版与纯 PySide6 版更漂亮，但需要先装 PySide6。',
                     color='#888', family='Microsoft YaHei', size=9)
    _hint.native.configure(wraplength=460)
    _hint.layout(Layout.pack(pady=(12, 2)))

    app.run()


if __name__ == '__main__':
    main()
