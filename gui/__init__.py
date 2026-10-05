"""gui 包入口，导出 `MainWindow` 作为公共接口。

**惰性导出（PEP 562）—— 关闭 （前半）**

原实现是 `from .main_window import MainWindow`，它在**包导入期**就拉起
`gui.main_window` → `gui.window` → 顶层 `import tkinter`。后果：**任何** `import gui.*`
都会连带要求 tkinter —— 连完全不碰图形界面的 `gui.theme` 也一样
（机器证据：`开发期探针 gui_migration` 的「阻断 tkinter 的子进程」探针）。

这与 的要求不对称：要求"缺少 PySide6 时 Tk-only 安装/启动不受影响"，
对称地也就要求 gui 包**不阻碍 Qt 启动** —— 只用 Qt 的环境 import 本包时不应被 tkinter 拖累。

手法与既有的两处惰性导出**完全一致**（照抄范式，不发明新机制）：
  * 仓库根 `__init__.py` 的 `_LAZY_EXPORTS`；
  * `ck1_0/renderer/tk/__init__.py`（同为 PEP 562 `__getattr__`）。

新手友好：`from gui import MainWindow` / `import gui; gui.MainWindow` / `dir(gui)` 的
**可观察行为全部不变**，只是"什么时候 import tkinter"推迟到真正用到窗口的那一刻。
"""

__all__ = ["MainWindow"]


def __getattr__(name):
    """按 PEP 562 **惰性**解析 `MainWindow`（首次访问时才导入 `gui.main_window`）。

    语义等价于原来的 `from .main_window import MainWindow`：先导入子模块，再取其属性；
    解析结果**缓存进模块全局**，后续访问不再经过本函数；未登记的名字抛 `AttributeError`
    （而不是 `KeyError`/`NameError`）。
    """
    if name == "MainWindow":
        from .main_window import MainWindow

        globals()["MainWindow"] = MainWindow
        return MainWindow
    raise AttributeError(
        "module {!r} has no attribute {!r}".format(__name__, name)
    )


def __dir__():
    """让 `dir(gui)` 也列出**尚未解析**的惰性名（与根 `__init__.py` 同口径）。"""
    return sorted(set(globals()) | set(__all__))
