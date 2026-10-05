"""ThemeMixin：主题令牌 + Tk/ttk 样式适配（本版 Batch）。

本模块在本版后的定位（`设计记录` /）：

* **该交付的**：把"主题令牌"交给 backend 中立的 `ck1_0.core.theme.Theme`（`self.theme`），
 并保证**不在模块顶层 import tkinter** ——  要求"缺少 PySide6 时 Tk-only 安装/启动不受影响"，
  对称地也就要求"**不阻碍 Qt 启动**"：只用 Qt 的环境若 import 本模块，不应被 tkinter 拖累。
* **明确不交付的**：`set_theme` / `configure_font` 是 **Tk/ttk 专属**能力
  （ttk 样式名 `'clam'`/`'default'`、ttk `'.'` 样式字体）。裁定本版 **不**把它们中立化；
 本模块只保证：**ttk 缺席时静默 no-op**（不抛、不影响 Qt 环境），且**签名与首版逐字一致**。

新手友好：外部/业务代码只管用 `self.theme.<token>` 读视觉值，不需要知道 ttk 的存在，
也不需要在 Qt 环境里写 `if tkinter` 之类的判断。
"""

try:                                    # 脚本模式：cwd = 仓库根，`gui` 为顶层包
    from ck1_0.core.theme import Theme
except ImportError:                     # 包模式：本文件即 ck1_0.gui.theme
    from ..core.theme import Theme


def _ttk():
    """**惰性**取 `tkinter.ttk`（/：模块顶层不得 import tkinter）。

    返回 `None` 表示当前环境没有可用的 Tk（例如只装 PySide6）—— 此时本模块仍可导入、可构造，
    `set_theme` / `configure_font` 变为**静默 no-op**（首版的"异常静默忽略"语义在缺席时同样成立）。
    """
    try:
        from tkinter import ttk
        return ttk
    except Exception:                   # noqa: BLE001 —— 缺 Tk / 无显示：视为不可用
        return None


class ThemeMixin:
    """主题令牌 + ttk 样式封装（**签名与首版逐字一致**）。"""

    def __init__(self):
        # 主题令牌：只在**缺失**时提供 —— 与 DialogMixin/MediaMixin/AdvancedWidgetMixin 同口径
        #（"显式传入 > 宿主已有 self.theme > Theme.light()"，**不覆盖**已存在的 theme）。
        if getattr(self, "theme", None) is None:
            self.theme = Theme.light()
        # ttk 样式：**同样只在缺失时**获取；ttk 缺席 ⇒ None（不阻碍非 Tk 环境）。
        #
        # 为什么加这层判断（实测）：原实现**无条件** `self._ttk_style = ttk.Style()`。
        # 组合根 `MainWindow` 的构造顺序是 `Btk.__init__`（已建好样式）→ `_init_mixins`
        # （其中就有本 mixin）⇒ 实测一个 `MainWindow` 期间 `ttk.Style()` 被构造 **2 次**，
        # 前一个被直接丢弃。两者虽等价，但它（a）破坏了"mixin 不覆盖宿主状态"的统一纪律
        #（`theme` 在 `G-4b` 已被断言不被覆盖），(b) 白白多一个 ttk 对象。
        # 判据取 `is None`（而不是 `hasattr`）：宿主若因 ttk 缺席留下 `None`，仍应重新尝试。
        if getattr(self, "_ttk_style", None) is None:
            ttk = _ttk()
            try:
                self._ttk_style = ttk.Style() if ttk is not None else None
            except Exception:           # noqa: BLE001 —— 首版同：取不到就置 None
                self._ttk_style = None

    def set_theme(self, theme_name='clam'):
        """尝试设置 ttk 主题（若可用）。

        （不交付）**：`theme_name` 是 **ttk 专属**样式名，本层不做中立化；
        ttk 不可用时**静默 no-op**（与首版的"异常静默忽略"一致）。
        """
        if self._ttk_style:
            try:
                self._ttk_style.theme_use(theme_name)
            except Exception:
                pass

    def configure_font(self, default_family='Segoe UI', size=10):
        """注册并配置 ttk 全局默认字体（若可用）。

        （不交付）**：同样是 ttk 专属；ttk 不可用时静默 no-op。
        需要"跨后端统一字体"的调用方请改用 `self.theme` 的字体 token（如 `default_family`）。
        """
        try:
            default_font = (default_family, size)
            # 为常用小部件设置默认字体
            if self._ttk_style:
                self._ttk_style.configure('.', font=default_font)
        except Exception:
            pass
