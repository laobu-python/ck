# `ck1_0/components/` —— 额外功能模块容器（边界说明）

> 本目录是**额外功能模块**的容器：放**不依赖任何 backend** 的数据服务 / 算法（设计约定："创建 components/（额外功能模块容器）+ 迁 APNG"）。

## 1. 这里放什么

**既不是 backend 中立控件抽象、也不属于 GUI renderer** 的功能模块。判据：

| 放进 `components/` | 不放进 `components/` |
|---|---|
| 纯数据服务（解析、校验、格式转换、报告） | 任何创建控件 / 事件循环 / 定时器的代码 → `renderer/` + `gui/` |
| 无 `tkinter` / PySide6 依赖，可单独在命令行使用 | 需要 backend 才能工作的东西 |
| 可被 `gui/*.py` 与 `renderer/*` 共同复用的算法 | 只服务某一个 GUI 页面的胶水代码 |

依赖方向（**单向，不得反向**）：

```text
gui/*.py ──► renderer/*（backend 中立控件）──► core/*（令牌 / 内核）
    │
    └────► components/*（功能模块 / 数据服务，无 backend 依赖）
```

`components/` 允许导入 `core/`；**禁止**导入 `gui/`、`renderer/`、`tkinter`、PySide6。

## 2. 当前成员

| 模块 | 职责 | 来源 |
|---|---|---|
| `components/apng/parser.py` | APNG 块级解析、伪装图判定、逐帧差异、拆帧导出、中文/JSON 报告 | 由 `utils/apng.py` **迁入** |
| `components/apng/handle.py` | `ApngHandle`：只做委托（播放/停止/导出/报告/逐帧预览交给宿主） | 由 `gui/apng_handle.py` **迁入** |
| `components/apng/__init__.py` | 导出 `ApngHandle` + `parser` 子模块 | 新增 |

## 3. 旧路径与迁移窗口

| 旧路径 | 现状 | 移除时机 |
|---|---|---|
| `utils.apng` | **deprecated 别名**，转发到 `components.apng.parser` 的同一份实现，导入时发 `DeprecationWarning` | 一个版本周期后 |
| `gui.apng_handle` | **deprecated 别名**，转发到 `components.apng.handle.ApngHandle` | 一个版本周期后 |

- `utils/` 目录**保留**（其中仍有 `helpers.py`：`write_csv`/`write_json` 等导出业务），故**不**做整目录合并。
- 别名**只有一层转发**，不含第二份实现（避免"两份 APNG 解析"这种最坏情况）。

## 4. 验收（可机核）

`开发期探针 apng_paths`（`run_all` 第 10 项）断言：

1. `import ck1_0.components` / `import ck1_0.components.apng` 生效（**源码树布局**，即命名空间包）；
2. `from ck1_0.components.apng import ApngHandle` 生效，且 `ApngHandle` 与 `parser` 均在 `__all__`；
3. 公开 API 面**逐名对齐**迁移前的 `utils.apng`（`analyze` / `format_report` / `is_disguised` / `save_frames` / `inspect_text` / `pil_available` / `parse_bytes` / `to_json` / `PNG_SIGNATURE` / …）；
4. 旧路径 `utils.apng` / `gui.apng_handle` 仍可导入，且**是同一对象**（`is` 同一性，而非"值相等"）；
5. 旧路径导入时**确实**发出 `DeprecationWarning`；
6. `components/` 内**没有** `tkinter` / PySide6 / `gui` / `renderer` 的导入（静态 grep + AST 双查）。
