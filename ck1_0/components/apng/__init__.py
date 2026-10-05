"""apng —— APNG 解析 / 伪装图识别 / 拆帧导出的功能模块（从 `utils/apng.py` 迁入）。

分工
    `parser.py`  纯数据服务：块级解析（**只用标准库**）、逐帧差异与拆帧（需 Pillow）、
                 中文报告与 JSON 输出。不导入 `tkinter`、不导入 `renderer`。
    `handle.py`  `ApngHandle`：只做**委托**（播放/停止/导出/报告/预览交给宿主方法），
                 自身不解析、不渲染、不排定 `after`。

对外用法
    ```python
    from ck1_0.components.apng import ApngHandle, parser

    info = parser.analyze(r'D:\\pics\\2345.png')
    print(parser.format_report(info))
    ```
    `parser` 亦可 `from ck1_0.components.apng import parser`，
    或 `from ck1_0.components.apng.parser import analyze, format_report`。

旧路径
    `utils.apng`（原模块）与 `gui.apng_handle`（原句柄模块）保留为 **deprecated 别名**，
    一个版本周期后移除；它们转发到本模块的同一份实现。
"""

from .handle import ApngHandle
from . import parser

__all__ = ["ApngHandle", "parser"]
