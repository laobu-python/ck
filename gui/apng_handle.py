"""apng_handle.py —— **deprecated 别名**（迁移；一个版本周期后移除）

实现已迁至 `ck1_0/components/apng/handle.py`（唯一一份实现）。
本模块只做**一层转发**：`from gui.apng_handle import ApngHandle` 仍然可用，
但会发出 `DeprecationWarning`。

迁移背景与边界见 `ck1_0/components/README.md`。
"""

import warnings as _warnings

_warnings.warn(
    "gui.apng_handle 已迁移至 ck1_0.components.apng.handle；"
    "本别名只保留一个版本周期，请改用 from ck1_0.components.apng import ApngHandle",
    DeprecationWarning,
    stacklevel=2,
)

from ck1_0.components.apng.handle import ApngHandle  # noqa: F401,E402

__all__ = ["ApngHandle"]
