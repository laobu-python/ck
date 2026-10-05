"""ck1_0.renderer.qt —— Qt 后端包。

公共出口：`QtRenderer`。

为什么本包用**惰性**导出（PEP 562）
    Qt 后端是**可选依赖**（`pyproject.toml` 的 `qt` extra，`PySide6>=6.9`）。若本文件
    直接 `from .renderer import QtRenderer`，则**任何**对本包的访问都会连带
    `import PySide6` —— 于是一个**未装 Qt 的默认安装**连 `import ck1_0.renderer.qt`
    都会失败。惰性导出把"可选依赖"落到实处：只有真正取用 `QtRenderer` 时才导入 PySide6。

    这与 `ck1_0/renderer/tk/__init__.py`（为保住 `draw.py` 的"不拉 tkinter"承诺）以及
   根 `__init__.py` 的 处理是**同一手法**（早期设计记录）。
"""

__all__ = ["QtRenderer"]


def __getattr__(name):
    """按 PEP 562 惰性解析 `QtRenderer`（首次访问时才导入 PySide6）。"""
    if name == "QtRenderer":
        from .renderer import QtRenderer

        globals()["QtRenderer"] = QtRenderer
        return QtRenderer
    raise AttributeError(
        "module {!r} has no attribute {!r}".format(__name__, name)
    )


def __dir__():
    """让 `dir(ck1_0.renderer.qt)` 也列出尚未解析的惰性出口。"""
    return sorted(set(globals()) | set(__all__))
