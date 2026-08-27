# launcher.py —— 新手启动器
"""ck0.9 新手启动器：一个窗口三个大按钮，双击即可选择进入演示 / 教程 / 文档。

用法:
    python launcher.py              打开启动器界面
    python launcher.py --tutorial   直接打开新手交互教程
"""
import os
import sys

import tkinter as tk
from gui.main_window import MainWindow
from gui.tutorial import TutorialWindow

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _open_docs():
    """用系统默认程序打开 README.md。"""
    path = os.path.join(_BASE_DIR, 'README.md')
    try:
        os.startfile(path)
    except Exception as e:
        print('无法打开文档:', e)


def _run_demo():
    """关闭启动器并运行完整演示（同一进程）。"""
    app.root.destroy()
    import main
    main._demo()


def main():
    global app
    app = MainWindow("ck0.9 新手启动器", 500, 360)
    app.center_window()

    if '--tutorial' in sys.argv:
        # 直接进入新手教程
        TutorialWindow(app)
        app.run()
        return

    app.label_ck("👋 欢迎使用 ck0.9 GUI 库", tsize=22)

    def _make_button(text, color, command):
        b = tk.Button(app.scrollable_frame, text=text, font=('Microsoft YaHei', 13, 'bold'),
                      bg=color, fg='white', width=28, pady=8, cursor='hand2',
                      activebackground=color, activeforeground='white',
                      relief='flat', command=command)
        b.pack(pady=7)
        return b

    _make_button("🚀 运行完整演示", '#2196f3', _run_demo)
    _make_button("🎓 新手交互教程（推荐）", '#4caf50',
                 lambda: TutorialWindow(app))
    _make_button("📖 打开使用文档", '#ff9800', _open_docs)

    tk.Label(app.scrollable_frame,
             text='第一次接触 Python？点「新手交互教程」就行，全程鼠标点击，不用写代码。',
             fg='#888', font=('Microsoft YaHei', 9), wraplength=420).pack(pady=(10, 2))

    app.run()


if __name__ == '__main__':
    main()
