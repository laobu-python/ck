"""components —— ck1.0 的**额外功能模块**容器。

边界（本包存在的理由）
    `renderer/` 负责"画"（backend 中立控件抽象），`core/` 负责"令牌与内核"；
    那些**既不是控件抽象、也不属于 GUI renderer**的功能模块放在这里 ——
    典型如 APNG 解析（数据服务）。它们**不得**导入 `tkinter` / PySide6，
    也不得反向依赖 `renderer`。

    ```text
    ck1_0.core       令牌 / 内核         （无 backend 依赖）
    ck1_0.renderer   控件抽象 + 两后端   （tk / qt）
    ck1_0.components 额外功能模块         （无 backend 依赖；数据服务）
    ```

当前成员
    `ck1_0.components.apng` —— APNG 解析（`parser.py`）与句柄（`handle.py`）。
    旧路径 `utils.apng` / `gui.apng_handle` 保留为 **deprecated 别名**（一个版本周期）。

惰性导出（PEP 562）
    `import ck1_0.components` 本身**不**导入任何子模块；`components.apng` /
    `components.ApngHandle` 在首次属性访问时才导入，避免把 Pillow/解析逻辑
    变成包导入的副作用。
"""

__all__ = ["apng", "ApngHandle"]

# 名字 -> 相对子模块名（PEP 562 惰性解析）
_LAZY = {
    "apng": ".apng",
    "ApngHandle": ".apng",
}


def __getattr__(name):
    """惰性解析 `apng` / `ApngHandle`（未登记的名字抛 `AttributeError`）。"""
    from importlib import import_module

    try:
        target = _LAZY[name]
    except KeyError:
        raise AttributeError(
            "module {!r} has no attribute {!r}".format(__name__, name)
        ) from None

    module = import_module(target, __name__)
    value = module if name == "apng" else module.ApngHandle
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(_LAZY))
