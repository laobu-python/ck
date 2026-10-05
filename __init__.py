# szj
# 2025/12/6
# ck1.0：新增 APNG / 伪装图检查能力（utils.apng），随包一起导出，方便直接使用
#
# ：顶层再导出改为**惰性**（PEP 562）。
# 原实现 `from .gui import MainWindow` 在 `import ck1_0` 时就会拉起 tkinter，
# 使安装态下 `import ck1_0.renderer.base` 间接依赖 Tk，违反「base 不依赖任何
# 具体 backend」的契约。现在改为首次属性访问时才导入对应子模块。
__version__ = "1.0"

__all__ = ["MainWindow", "apng", "__version__"]

# 惰性解析表：名字 -> (相对子模块名, 子模块内的属性名)。
# `attr_name` 为 None 表示"子模块本身"。
#
# 为什么连子模块名也登记：原来的两条 `from .X import Y` 语句除了导入 Y，还会把
# `gui` / `utils` 绑定为包属性；`core` 则是 gui 导入链的副作用（`ck1_0.core.theme`）。
# 惰性化后必须保留这些属性在 `import ck1_0` 之后即可访问的可观察行为，故一并登记。
_LAZY_EXPORTS = {
    "MainWindow": (".gui", "MainWindow"),
    "apng": (".utils", "apng"),
    "gui": (".gui", None),
    "utils": (".utils", None),
    "core": (".core", None),
}


def __getattr__(name):
    """按 PEP 562 惰性解析顶层名。

    映射语义等价于 `from <子模块> import <属性名>`：先导入子模块，再取其属性；
    属性不存在时回退为导入同名**子模块**（与 `from X import Y` 的行为一致 ——
    `ck1_0.apng` 正是这种情形：`utils/__init__.py` 并不导出 `apng`）。
    解析结果**缓存进模块全局**，后续访问不再经过本函数。
    未登记的名字一律抛 `AttributeError`（而非 `KeyError`/`NameError`）。
    """
    from importlib import import_module

    try:
        module_name, attr_name = _LAZY_EXPORTS[name]
    except KeyError:
        raise AttributeError(
            "module {!r} has no attribute {!r}".format(__name__, name)
        ) from None

    module = import_module(module_name, __name__)
    if attr_name is None:
        value = module
    else:
        try:
            value = getattr(module, attr_name)
        except AttributeError:
            value = import_module(
                "{}.{}".format(module_name, attr_name), __name__
            )

    globals()[name] = value
    return value


def __dir__():
    """让 `dir(ck1_0)` 也列出尚未解析的惰性名。"""
    return sorted(set(globals()) | set(_LAZY_EXPORTS))
