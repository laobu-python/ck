"""apng.py —— **deprecated 别名**（迁移；一个版本周期后移除）

实现已迁至 `ck1_0/components/apng/parser.py`（唯一一份实现）。
本模块只做**一层转发**：`from utils import apng` / `import utils.apng` 仍然可用，
但会发出 `DeprecationWarning`。

迁移背景与边界见 `ck1_0/components/README.md`。

**只转发冻结的 15 个公开名**（不用 `import *`）：`import *` 会把 `parser.py` 里
`import hashlib/json/os/struct` 这类辅助名一并泄出，也会让"少转发一个名字"这类漏项在
探针里**不可见**（牙齿 实测）。冻结清单与 `开发期探针 base_contract` 的
同源。
"""

import warnings as _warnings

_warnings.warn(
    "utils.apng 已迁移至 ck1_0.components.apng.parser；"
    "本别名只保留一个版本周期，请改用 from ck1_0.components.apng import parser",
    DeprecationWarning,
    stacklevel=2,
)

from ck1_0.components.apng.parser import (          # noqa: E402
    APNG_DISGUISE_KEYS,
    DIFF_PIXEL_THRESHOLD,
    PNG_SIGNATURE,
    analyze,
    format_report,
    frame_diffs,
    frame_stats,
    inspect_text,
    is_disguised,
    parse_bytes,
    parse_png,
    pil_available,
    read_bytes,
    save_frames,
    to_json,
)

__all__ = [
    "APNG_DISGUISE_KEYS",
    "DIFF_PIXEL_THRESHOLD",
    "PNG_SIGNATURE",
    "analyze",
    "format_report",
    "frame_diffs",
    "frame_stats",
    "inspect_text",
    "is_disguised",
    "parse_bytes",
    "parse_png",
    "pil_available",
    "read_bytes",
    "save_frames",
    "to_json",
]

