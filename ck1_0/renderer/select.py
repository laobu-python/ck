"""backend 选择 API —— **最小骨架**。

本模块只提供「选哪个 backend」的**状态与校验**，**不含任何 renderer 实现**。
早期的交付物是 Tk/Qt 的 button/toggle；本版将在此基础上扩展
（登记真实实现、按 backend 分发、以及各 backend 的配置项）。

约定 / 不变量
-------------
* **进程全局**：选择结果保存在本模块的模块级状态里，全进程唯一。它**不是**
  ``Renderer`` 实例状态，也不随任何实例销毁而重置。
* **必须在任何 ``Renderer`` 构造之前完成选择**：``Renderer`` 是进程内单例，
  其构造**不接受** backend 参数，因此「选后端」只能发生在构造之前；一旦晚于构造
  就再无意义。本骨架**不做**运行时强制（尚无实现可供校验），仅以本条文档约定。
* **默认是 ``None``**（从未选择）：首版/1/2 的代码路径完全不经过本模块，
  行为不受影响。
* **失败不改变状态**：``select()`` 校验失败时，保持原有选择不变。
* **导入期零依赖**：本模块**不在导入期**引入 tkinter / PySide6。仅在 ``select()``
  做依赖检查时**惰性**导入（见 ``_check_dependency``）。

用法::

    from ck1_0.renderer.select import select, current_backend, get_renderer_class

    select('tk')                        # 或 select(Backend.TK)
    assert current_backend() is Backend.TK
    cls = get_renderer_class()          # 早期恒为 None（尚无实现）
"""

from __future__ import annotations

from enum import Enum
from importlib import import_module
from typing import Dict, Optional, Tuple, Type

from .base import NotSupportedError, Renderer, RendererError

# `__all__` 只列本模块**自有**的选择 API（登记）。
# `RendererError` / `NotSupportedError` 是本模块从 `.base` 导入**使用**的异常，
# 其公共出口（canonical home）是 `ck1_0.renderer.base`。此处刻意**不**列入
# `__all__`，以免同一个异常出现两个公共来源；捕获时请从 `.base` 导入。
__all__ = ["Backend", "select", "current_backend", "get_renderer_class"]


class Backend(str, Enum):
    """可选的 renderer backend。

    同时继承 ``str``，因此 ``Backend.TK == 'tk'`` 成立，便于直接比较与序列化。
    取值**区分大小写**：``'TK'`` 不是合法取值。
    """

    TK = "tk"
    QT = "qt"


# --------------------------------------------------------------------------- #
# 模块级状态
# --------------------------------------------------------------------------- #
# None == 从未选择过任何 backend（即默认状态）。
_selected: Optional[Backend] = None

# 解析**相对**子模块名时的锚点。
#
# 必须是**包**名而不是本模块的 `__name__`：`import_module(".tk", anchor)` 会把
# `name` 直接**追加**到 `anchor` 之后。本模块的 `__name__` 是
# `'ck1_0.renderer.select'`（一个模块，不是包），用它当锚点会把 `".tk"` 解析成
# `ck1_0.renderer.select.tk` → `ModuleNotFoundError`；用 `__package__`
# （`'ck1_0.renderer'`）才会正确解析为 `ck1_0.renderer.tk`。
#
# （`__init__.py` 里没有这个问题：那里 `__name__` 就是包名 `'ck1_0'`。
#  该陷阱只在**普通模块**中出现，勿照搬。）
_PACKAGE = __package__ or __name__.rpartition(".")[0]


# backend -> (需要检查的顶层依赖模块名, 缺依赖时的可操作提示)
_DEPENDENCIES: Dict[Backend, Tuple[str, str]] = {
    Backend.TK: (
        "tkinter",
        "本 Python 未内置 tkinter（部分 Linux 发行版需另装 python3-tk）",
    ),
    Backend.QT: (
        "PySide6",
        '请安装可选依赖 qt extra：pip install "ck1_0[qt]"',
    ),
}

# backend -> (子模块名, 该子模块内的 Renderer 子类名)
#
# 子模块名可以是**相对**名（`".tk"`，以本模块所属的包 `ck1_0.renderer` 为锚点解析）
# 或**绝对**名（`"ck1_0.renderer.tk"`），二者等价。
#
# 两个后端**均已登记**（关闭）：
# * `tk` —— `TkRenderer`：button/toggle 真实实现，其余 35 个抽象方法抛
#     `NotSupportedError`；
# * `qt` —— `QtRenderer`：同样只做 button/toggle。
# 两个实现模块都**惰性导入**（各自的包 `__init__` 用 PEP 562 `__getattr__`），
# 因此 `get_renderer_class()` 只在被调用时才拉起对应 backend（tk 拉 tkinter、qt 拉 PySide6）；
# 未装可选依赖时由 `select()` 的依赖检查先行拦截（`NotSupportedError`）。
_IMPLEMENTATIONS: Dict[Backend, Tuple[str, str]] = {
    Backend.TK: (".tk", "TkRenderer"),
    Backend.QT: (".qt", "QtRenderer"),
}


# --------------------------------------------------------------------------- #
# 内部校验
# --------------------------------------------------------------------------- #
def _coerce(backend):
    """把 ``Backend | str`` 规范化为 ``Backend``；取值未知时抛 ``RendererError``。"""
    if isinstance(backend, Backend):
        return backend
    if isinstance(backend, str):
        try:
            return Backend(backend)
        except ValueError:
            pass
    known = ", ".join(repr(member.value) for member in Backend)
    raise RendererError(
        "未知 backend {!r}；可用取值：{}".format(backend, known)
    )


def _check_dependency(backend):
    """检查 ``backend`` 的运行期依赖是否可用；缺失则抛 ``NotSupportedError``。

    本模块**唯一**会导入 tkinter / PySide6 的位置，且只在 ``select()`` 调用时执行。
    """
    module_name, hint = _DEPENDENCIES[backend]
    try:
        import_module(module_name)
    except ImportError as exc:
        raise NotSupportedError(
            "backend {!r} 不可用：缺少依赖模块 {!r}。{}".format(
                backend.value, module_name, hint
            )
        ) from exc


# --------------------------------------------------------------------------- #
# 公共 API
# --------------------------------------------------------------------------- #
def select(backend: "Backend | str") -> None:
    """选择当前进程使用的 backend。

    参数:
        backend: ``Backend`` 成员，或其字符串取值（``'tk'`` / ``'qt'``）。
            取值区分大小写。

    异常:
        RendererError: 取值未知（不属于 ``Backend``）。
        NotSupportedError: 取值合法，但其依赖不可用（例如选了 ``'qt'``
            却没有 PySide6）。本异常是 ``RendererError`` 的子类。

    状态与副作用:
        * 全部校验通过后才写入模块级状态；**任一校验失败都保持原选择不变**。
        * **进程全局**：改变的是整个进程的选择，不是某个 ``Renderer`` 实例的。
        * 必须**在任何 ``Renderer`` 构造之前**调用（``Renderer`` 是进程内单例，
          其构造不接受 backend 参数）。
        * 可重复调用，后一次覆盖前一次。
        * 为做依赖检查，本函数会**惰性导入**该 backend 的依赖模块
          （``'tk'`` ⇒ ``tkinter``，``'qt'`` ⇒ ``PySide6``）。因此成功调用
          ``select('tk')`` 之后，``sys.modules`` 中会出现 ``tkinter`` —— 这是
          预期行为，本模块的契约只要求**导入本模块本身**不拉起任何 backend 依赖。
    """
    global _selected

    resolved = _coerce(backend)
    _check_dependency(resolved)
    _selected = resolved


def current_backend() -> Optional[Backend]:
    """返回当前选择；**从未选择过**时返回 ``None``。"""
    return _selected


def get_renderer_class() -> Optional[Type[Renderer]]:
    """返回所选 backend 的 ``Renderer`` 子类。

    返回 ``None`` 的**两种**情形（调用方须区分 ``None`` 与"报错"）：
        * 从未选择过 backend（此时 ``current_backend()`` 也是 ``None``）；
        * 已选择，但该 backend **不在** ``_IMPLEMENTATIONS`` 中（起 `tk`/`qt`
          均有实现，故当前**不会**由本情形返回 ``None``；保留该分支以备将来新增 backend）。

    异常:
        RendererError: 登记项存在但**无法解析**。三种情形**统一**为本异常，既不泄漏
            ``ImportError``/``AttributeError``，也不静默降级为 ``None``：
            ① 子模块无法导入（``ImportError``）；② 子模块内不存在该属性名；③ 取到的对象不是
            ``Renderer`` 子类。集成错误必须在构造 ``Renderer`` 之前当场暴露。

    实现注记:
        子模块名按 `_PACKAGE`（本模块所属**包**，即 ``ck1_0.renderer``）为锚点解析，
        因此 ``_IMPLEMENTATIONS`` 中既可用相对名 ``".tk"``，也可用绝对名。
    """
    if _selected is None:
        return None

    entry = _IMPLEMENTATIONS.get(_selected)
    if entry is None:
        return None

    module_name, class_name = entry
    try:
        module = import_module(module_name, _PACKAGE)
        cls = getattr(module, class_name)
    except (ImportError, AttributeError) as exc:
        raise RendererError(
            "backend {!r} 的实现登记项 {}.{} 无法解析：{}: {}".format(
                _selected.value, module_name, class_name,
                type(exc).__name__, exc,
            )
        ) from exc

    if not (isinstance(cls, type) and issubclass(cls, Renderer)):
        raise RendererError(
            "backend {!r} 的实现登记项 {}.{} 不是 Renderer 子类".format(
                _selected.value, module_name, class_name
            )
        )
    return cls
