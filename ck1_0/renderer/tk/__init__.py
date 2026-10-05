"""ck1_0.renderer.tk —— Tk 后端包。

公共出口：`TkRenderer`。

为什么本包用**惰性**导出（PEP 562）
    `renderer.py` 需要在模块顶层 `import tkinter`（允许）。若本文件
    直接 `from .renderer import TkRenderer`，则**任何**子模块访问都会连带拉起
    tkinter —— 包括 `from ck1_0.renderer.tk import draw`。而 `draw.py` 的模块
    docstring 明文承诺：

        「为什么本模块**不 import tkinter** …… 不 import 就不会在缺 tkinter 的
         环境里 import 失败，`python -c "from ck1_0.renderer.tk import draw"`
         与 `--help` 之类都不受影响。」

    惰性导出把这条既有承诺原样保住：只有真正取用 `TkRenderer` 时才导入 tkinter。
   这与根 `__init__.py` 的 处理是同一手法。
"""

__all__ = ["TkRenderer"]


def __getattr__(name):
    """按 PEP 562 惰性解析 `TkRenderer`（首次访问时才导入 tkinter）。"""
    if name == "TkRenderer":
        from .renderer import TkRenderer

        globals()["TkRenderer"] = TkRenderer
        return TkRenderer
    raise AttributeError(
        "module {!r} has no attribute {!r}".format(__name__, name)
    )


def __dir__():
    """让 `dir(ck1_0.renderer.tk)` 也列出尚未解析的惰性出口。"""
    return sorted(set(globals()) | set(__all__))
