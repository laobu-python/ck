"""renderer/base.py —— backend-neutral Renderer 抽象契约（早期）

本模块**只定义契约**：不导入 `tkinter`、不导入 `PySide6`、不创建任何控件、
不含视觉硬编码（颜色/字体/**像素**一律经 `Theme` token 取得）、
**公开 API** 不使用未审核的万能 `**kwargs`。
（`设计约定` 的"不使用未审核的万能 `**kwargs`"针对的是**公共 API 逃生口**；
本模块唯一一处 `**kwargs` 是 `__init_subclass__` 内私有 `_guarded` 的**透明转发**，
用于包装子类任意 `__init__` 签名，不在任何公开签名上 —— 见 `Renderer` 类文档。）

设计原则（见 `接口合同`）
    1. 面向新手，**简单易用**优先，不为抽象而抽象；
    2. 不破坏 `接口合同` 的首版合同（签名、中文默认文本、回调形状、`None` 语义）；
    3. 能快速失败就快速失败（显式异常，见下方异常层级）。

五条核心语义
    生命周期   Renderer 拥有 backend root；进程内**只允许一个存活实例**。
               登记发生在 `Renderer.__init__`（即子类建立 backend root **之前**），
               子类**无法**通过漏调钩子绕过（见 `Renderer` 类文档）。
    parent     **显式**传入，不设隐式"当前容器"栈。首版的
               `self.scrollable_frame` / `toolbar_container` / `statusbar_container`
               属实现内部细节，**不进入本层**。
    返回句柄   backend-neutral `Handle`；`Handle.native` 是**显式**逃生口。
    变量绑定   neutral `Value`（`get/set/on_change`）；8 种回调形状**冻结不变**。
    事件循环   `run()` / `update()` / `schedule()`；`post()` 为跨线程预留原语。

线程规则（硬性）
    **除 `Renderer.post()` 外，所有 Renderer API 与所有回调都必须在 UI 线程调用。**
    违反该规则属调用方错误（本层不做运行期检测）。`post()` 是唯一可从任意线程调用的入口。

`None` 的既有含义（取消 / 缺 Pillow / 文件失败 / 无数据）**冻结不变**，不得改成空对象。
注意反向约束：首版里**不是** `None` 的失败哨兵同样不得改成 `None`
（例如 `animation` 的"返回 0 帧"语义）。
"""

import functools
import sys
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

try:                                    # 脚本模式：cwd = 项目根
    from ck1_0.core.theme import Theme
except ImportError:                     # 包模式：本文件即 ck1_0.renderer.base
    from ..core.theme import Theme


# --------------------------------------------------------------------------- #
# 进程级单例槽位
# --------------------------------------------------------------------------- #
# 为什么不放在本模块的模块全局（也不放在类的类属性）：
#   同一个文件可能被以两个不同模块名导入（如 `ck1_0.renderer.base` 与 `renderer.base`），
#   那样会得到两份模块全局、甚至两个 `Renderer` 类对象 —— 单例状态随之分裂，
#   于是能并存两个存活 backend root。`sys` 是进程内唯一的模块对象，把槽位挂在它上面
#   才能真正做到"进程内唯一"，且不随双路径导入而分裂。
_SLOT = '_ck1_0_renderer_current'


def _slot_get() -> Optional['Renderer']:
    """读取进程级槽位。"""
    return getattr(sys, _SLOT, None)


def _slot_set(value: Optional['Renderer']) -> None:
    """写入进程级槽位。"""
    setattr(sys, _SLOT, value)


def _live_current() -> Optional['Renderer']:
    """返回当前**存活**实例。

    **仅当 `is_alive()` 诚实返回 `False`** 时才自动释放槽位并返回 `None`。
    "诚实"有可判定标准，即 `Renderer.is_alive()` 文档给出的**实现中立定义**
    （"root 对象当前是否仍然存在/可用"），而非"窗口是否可见/已 map"等可观察状态


    `is_alive()` 自身抛异常时**不得**改动槽位，异常原样向上传播（快速失败）——
    否则一个后端 bug（属性未初始化、backend 查询失败）会被静默吞掉，
   随后允许第二个 backend root 建立，与「双 root 是真 bug，不应被静默掩盖」正面冲突。
    """
    cur = _slot_get()
    if cur is None:
        return None
    if cur.is_alive():                   # 此处抛异常则向上传播，槽位保持不变
        return cur
    if _slot_get() is cur:               # 诚实返回 False ⇒ 才算真死，可释放
        _slot_set(None)
    return None


def _best_effort_destroy(inst: 'Renderer') -> None:
    """构造失败路径的**尽力**回收。

    构造以失败告终时，实例已被丢弃，但它可能已经建立了 backend root
    （尤其是遗漏 `super().__init__()` 的写法）。此时调用 `_destroy_root()` 回收。

    **调用前提**：调用方必须先确认「槽位就是 `inst`」或「槽位为空」，
    即**进程内不存在别的存活实例**。若槽位属于另一个存活实例，则 `inst` 必然
   从未登记、也从未建立任何资源（校验先于任何 root 创建就抛出），此时调用
    释放钩子只会空转 —— 更糟的是，若该钩子按进程级单例写（Qt：
    `QApplication.instance().quit()`），它会拆掉**活跃实例**的 root。

    本函数**刻意吞掉清理异常**（唯一的受控沉默）：调用方随后会 `raise` 原始异常，
    原始异常必须胜出 —— 清理自身失败不得把它替换掉。
    因此这里只捕获 `Exception`，`BaseException`（`KeyboardInterrupt` 等）照旧传播。
    """
    try:
        inst._destroy_root()
    except Exception:                    # noqa: BLE001 —— 见 docstring：受控沉默
        pass


# --------------------------------------------------------------------------- #
# 异常层级
# --------------------------------------------------------------------------- #
class RendererError(Exception):
    """Renderer 相关错误的基类。"""


class NotSupportedError(RendererError):
    """当前 backend 不支持该能力。

    用于**显式边界**：可选能力未实现时必须抛本异常，**不得**静默 no-op。
    """


class RendererClosedError(RendererError):
    """在已销毁的 `Renderer` 或已失效的 `Handle` 上继续操作。

    触发点：`Renderer.is_alive()` 为假时调用任何 API；或 `parent`/自身 `destroy()` 之后。
    """


class InvalidParentError(RendererError):
    """`parent` 非法：为 `None`，或不是 `Handle`。

    **不含**"parent 属于另一个 Renderer"这一情形：`Handle` 不暴露 Renderer 反向引用，
    base **无法**检测归属，故不承诺。跨 Renderer 的陈旧句柄由 `Handle.exists()` 兜底 ——
    保证任一时刻只有一个存活 Renderer，旧 Renderer 销毁后其句柄 `exists()` 为 `False`，
    于是 `_validate_parent()` 抛 `RendererClosedError`（见 `Renderer._validate_parent`）。
    """


# --------------------------------------------------------------------------- #
# 布局
# --------------------------------------------------------------------------- #
class Layout:
    """一次性的布局**意图**描述。

    这里用 `pack` / `grid` 命名是描述**几何意图**（顺序流 / 网格），
    不是承诺 Tk 的布局系统：`side` / `sticky` / `anchor` 的取值由 backend 自行解释并映射
    （Tk 用 `pack`/`grid`，Qt 用 `QLayout`/`QGridLayout`）。
    backend 只实现自己支持的形式；不支持时必须抛 `NotSupportedError`。

    参数:
        kind (str): `'pack'` 或 `'grid'`。
        side (str): 顺序流方向，`'top'/'bottom'/'left'/'right'`。
        fill (str | None): 伸展填充方向，如 `'x'/'both'`。
        expand (bool): 是否占用剩余空间。
        anchor (str | None): 锚点。
        padx, pady: 间距（**像素**；调用方一般应来自 `Theme` token 而非字面量）。
        row, column, rowspan, columnspan (int): 网格位置与跨度。
        sticky (str | None): 网格锚点串，如 `'nsew'`。
        into (Handle | None): **目标容器**（权属由 backend 决定）。见下。

   目标容器 `into`（**只保证"请求接管几何"；权属由 backend 决定**）
        `into is None`（默认）表示"在主体**当前所属**的容器内重排自身"。

        `into` 非 `None` 时表示"请求 `into` **接管主体的几何管理**"，
        典型机制是 Tk 的 `w.pack(in_=into, ...)` / `w.grid(in_=into, ...)`（`-in` 选项）
        与 Qt 的 `target.layout().addWidget(w)`。

        **唯一保证**：几何管理被交给 `into`。

        **权属（parent / 所有权 / 生命周期）不进本层契约 —— 由 backend 决定。**
       实测两个真实后端**恰好相反**（两处均为真机取证）：

        | 命题 | Tk `-in` | Qt `layout().addWidget()` |
        |---|---|---|
        | 主体的 parent 是否改变 | **否**（`winfo_parent()` 不变） | **是**（`parent()` 变为 `into` 的宿主；原 parent 的 `children()` 变空） |
        | 所有权是否转移 | **否**（仍归原 parent） | **是**（Qt 的父子所有权随 `parent()` 走） |
        | 原 parent 销毁 ⇒ 主体失效 | **是** | **否**（主体仍可用） |
        | `into` 销毁 ⇒ 主体失效 | **否**（只是 `winfo_manager()` 变空） | **是**（立即成为已删除的 C++ 对象，访问抛 `RuntimeError`） |

        根因：Qt 的布局要求"被布局管理的控件必须是宿主控件的子对象"，
        `addWidget()` 因此**必然**调用 `setParent`；想"不改 parent"就只能不用布局，
        那样 `into` 就沦为无操作。所以**不存在**既接管几何又不 reparent 的统一机制。

        **因此调用方不得假定 `into` 前后的权属与生命周期**，必须用
        `Handle.exists()` 探测句柄是否仍然有效；**不得**假定"容器销毁后句柄仍可用"，
        也不得假定"原 parent 销毁后句柄已失效"。构造 `Layout` 时的 `into` 句柄同样
        只表示"几何目标"，不构成任何所有权承诺。

        **前置条件**：`into` 必须是主体 parent 本身或其后代（Tk 硬性要求；实测越界即
        `TclError: can't pack … inside …`）。`Handle` 不暴露 parent，base **无法校验**，
        故由 backend 在应用时抛 `NotSupportedError`。

        **与首版的差异**：首版的 `pack_vertical` 与 `center_widget`
        **连几何都未交给新容器** —— `gui/advanced_widgets.py:1278` / `:1332` 是裸
        `pack()`，控件仍由 `scrollable_frame` 管理，返回的容器实测为 `1×1` 空容器
        （`children == []`）；只有 `pack_in_grid:1313` 用 `grid(in_=container)` 交了几何。
       本层取的是**文档所述意图**（"把控件排列到新容器中"），与首版字面行为
        **不同**：按本契约实现后容器会按内容撑开（实测：同一组控件下首版容器为 `1×1`，
        改用 `-in` 接管后随内容显著撑开；具体尺寸取决于内容，不作固定断言）。该差异已登记为
        **本版迁移项**。

        为什么必须有它：没有 `into`，"把一组已存在的控件纳入某个新容器的几何管理"
       这一首版语义（`接口合同` 的 `pack_vertical` / `pack_in_grid` /
        `center_widget`）在 「禁止隐式当前容器」下**无法表达** —— `Handle.layout()`
        只能重排自身，无法说明"交给哪个容器管理"。

    返回:
        新的 `Layout` 实例（不可变语义：构造后调用方不应再改字段）。

    线程 / 同步:
        纯数据对象，无线程与事件循环语义，构造即返回。

    所有权 / 释放:
        无 backend 资源，无需释放。

    逃生口 / 异常:
        无逃生口；字段取值非法时**不在构造期校验**，由 backend 应用时抛 `NotSupportedError`。
    """

    __slots__ = ('kind', 'side', 'fill', 'expand', 'anchor', 'padx', 'pady',
                 'row', 'column', 'rowspan', 'columnspan', 'sticky', 'into')

    def __init__(self, kind='pack', side='top', fill=None, expand=False, anchor=None,
                 padx=0, pady=0, row=0, column=0, rowspan=1, columnspan=1, sticky=None,
                 into=None):
        self.kind = kind
        self.side = side
        self.fill = fill
        self.expand = expand
        self.anchor = anchor
        self.padx = padx
        self.pady = pady
        self.row = row
        self.column = column
        self.rowspan = rowspan
        self.columnspan = columnspan
        self.sticky = sticky
        self.into = into

    @classmethod
    def pack(cls, side='top', fill=None, expand=False, anchor=None, padx=0, pady=0,
             into=None):
        """顺序流布局意图。参数与语义见 `Layout` 类文档（含 `into`）。"""
        return cls('pack', side=side, fill=fill, expand=expand, anchor=anchor,
                   padx=padx, pady=pady, into=into)

    @classmethod
    def grid(cls, row=0, column=0, rowspan=1, columnspan=1, sticky=None, padx=0, pady=0,
             into=None):
        """网格布局意图。参数与语义见 `Layout` 类文档（含 `into`）。"""
        return cls('grid', row=row, column=column, rowspan=rowspan,
                   columnspan=columnspan, sticky=sticky, padx=padx, pady=pady, into=into)

    def __repr__(self):
        return '<Layout %s%s>' % (self.kind, '' if self.into is None else ' into=…')


# --------------------------------------------------------------------------- #
# 变量绑定
# --------------------------------------------------------------------------- #
class Value(ABC):
    """backend-neutral 的可观察值，替代 `tk.BooleanVar/IntVar/DoubleVar/StringVar`。

    回调时机：**值已变更之后**触发，回调参数为该 `Value` 的新值；回调在 **UI 线程**同步执行。
   组件级回调形状另见 `接口合同` （冻结不变）。

    参数 / 返回 / 异常:
        由子类方法定义（见下）。
    所有权 / 释放:
        `Value` 归创建它的控件句柄所有；控件销毁后 `get/set` 抛 `RendererClosedError`。
    """

    @abstractmethod
    def get(self) -> Any:
        """读取当前值。

        参数: 无。
        返回: 当前值（类型由控件决定：`bool` / `float` / `str` / `int`）。
        回调: 不触发回调。
        同步性: 同步返回。
        所有权: 无新增所有权。
        释放: 无需释放。
        逃生口: 无（backend 原生变量经 `Handle.native` 获取）。
        异常: 控件已销毁时抛 `RendererClosedError`。
        """

    @abstractmethod
    def set(self, value: Any) -> None:
        """写入新值。

        参数:
            value (Any): 新值；backend 负责必要的类型转换。
        返回: `None`。
        回调: 已注册的 `on_change` 回调在 **UI 线程**同步触发（值变更之后）。
        同步性: 同步返回。
        所有权: 无新增所有权。
        释放: 无需释放。
        逃生口: 无。
        异常: 控件已销毁时抛 `RendererClosedError`。
        """

    @abstractmethod
    def on_change(self, callback: Callable[[Any], None]) -> Callable[[], None]:
        """注册变更回调。

        参数:
            callback (Callable[[Any], None]): 接收**新值**；在 **UI 线程**同步调用。
        返回: 取消订阅的可调用对象（幂等，可重复调用）。
        回调: 同上。
        同步性: 注册同步完成；回调在值变更时同步触发。
        所有权: 回调归本 `Value` 持有，直到退订或控件销毁。
        释放: 调用返回的退订函数，或销毁所属控件。
        逃生口: 无。
        异常: 控件已销毁时抛 `RendererClosedError`。
        """


# --------------------------------------------------------------------------- #
# 句柄
# --------------------------------------------------------------------------- #
class Handle(ABC):
    """backend-neutral 控件句柄。

    所有权：句柄归其 `parent` 所有；`parent` 销毁后本句柄自动失效，
    此后调用任何方法抛 `RendererClosedError`。`destroy()` 幂等。

    **例外**：句柄曾经由 `Layout.into` 被其它容器**接管几何**时，
    权属**由 backend 决定** —— Tk 的 `-in` **不改** parent（仍归原 parent 所有），
    Qt 的 `layout().addWidget()` **会** `setParent`（权属转移给新宿主，`into` 销毁
    即连带销毁本句柄）。因此**不得**用"原 parent 是否存活"推断本句柄是否有效，
   请用 `exists()` 探测（详见 `Layout` 类文档的实测对照表与）。

    回调：所有回调均在 **UI 线程**同步执行。
    """

    @property
    @abstractmethod
    def native(self) -> object:
        """**逃生口**：返回 backend 专属对象（Tk widget / QWidget）。

        参数: 无。
        返回: backend 原生对象，标注为 `object` —— 本抽象层不依赖其类型。
        回调: 无。
        同步性: 同步返回。
        所有权: 返回对象**仍归本句柄/其 parent 所有**，调用方不得擅自销毁。
        释放: 随本句柄 `destroy()` 或 parent 销毁释放。
        逃生口: 本属性即逃生口；使用它意味着放弃可移植性，仅用于过渡期兼容既有调用点。
        异常: 句柄已失效时抛 `RendererClosedError`。
        """

    @abstractmethod
    def destroy(self) -> None:
        """销毁自身及其子树。

        参数: 无。
        返回: `None`。
        回调: 不触发业务回调；backend 可自行清理其定时器/绑定。
        同步性: 同步返回。
        所有权: 释放自身及子树；其后的句柄操作抛 `RendererClosedError`。
        释放: 本方法即释放责任方；**幂等**。
        逃生口: 无。
        异常: 无（已销毁时静默返回，不抛异常）。
        """

    @abstractmethod
    def exists(self) -> bool:
        """句柄是否仍然有效 —— **底层对象当前是否仍然存在/可用**。

       本方法是（指定的）**唯一**权属/可用性探测手段。

        参数: 无。
        返回: `bool` —— **底层对象当前是否仍然存在 / 可用**，由 backend 判定
            （Tk：`winfo_exists()`；Qt：C++ 对象尚未被删除）。
            **不得**把它定义为"原 parent 仍存活"：Qt 上 `Layout.into` 的
            `addWidget()` 会 reparent，**原 parent 销毁后本句柄仍可能可用** ——
            按"parent 存活"判定会给出**假阴性**；反之 `into` 被销毁后本句柄已成为
            已删除的 C++ 对象，按该定义又可能给出**假阳性**。两个方向都会让调用方
            的探测失效。
            对**未经过 `Layout.into`** 的句柄，"parent 销毁 ⇒ 本句柄失效"仍然成立，
            但那是**推论**而非本方法的定义（见 `Layout` 类文档）。
        回调: 无。
        同步性: 同步返回。
        所有权: 只读查询，无所有权变更。
        释放: 无需释放。
        逃生口: 无。
        异常: 无（探测本身不应抛异常；底层查询失败时应返回 `False`）。
            **与 `Renderer.is_alive()` 的异常策略相反是有意的**：`exists()` 不承载
            （base 只在一个地方消费它，且误判不会放行第二个 root），故"查询失败
           即视为不存在"；`is_alive()` 承载，必须让异常上抛（见其文档）。
        """

    @property
    def outer(self) -> "Handle":
        """该控件在布局中的**入列单位**（默认就是它自己）。

        **为什么需要它**：有些中立控件是**复合控件** ——
        真实结构是「外层容器（一行/一框）里放若干原生部件」，典型是 `slider`
        （外层 Frame 里放 `ttk.Scale`/`QSlider` + 标签 + 数值标签）与 `table`
        （外层 Frame 里放 Treeview/QTableWidget + 滚动条）。这些句柄的 `native` 指向
        **内部**部件（契约早已冻结这一点，不改），于是调用方对它 `layout(...)` 只会搬走
        内部部件、标签留在原地 —— 三个新手引导的**两拨独立实现**都撞到了这个坑
        （Tk 侧用 `native.master`、Qt 侧用 `native.parentWidget()` 各绕一次）。
        本属性把"入列单位"收进契约：**要对复合控件排队，用 `h.outer.layout(...)`**。

        参数: 无。
        返回: `Handle` —— **外层容器**的句柄（可直接 `layout(...)`，也可作为其它工厂的 `parent`）。
            非复合控件返回**自身**（`h.outer is h`，自反）。
        回调: 无。
        同步性: 同步返回。
        所有权: 外层容器**本来就归原 `parent` 所有** —— 本属性只是多一个句柄指向它，
            **不转移所有权、不 reparent**（口径不变）。
        释放: 与原句柄同寿命（随原 `parent` 销毁而失效）。
        逃生口: 无（它存在的意义正是把"跨后端各绕一次"的逃生口收进契约）。
        异常: 无（返回句柄本身不查询底层；后续对该句柄的操作才可能抛 `RendererClosedError`）。
        """
        return self

    @abstractmethod
    def layout(self, layout: Layout) -> None:
        """（重新）应用布局；`layout.into` 非 `None` 时请求该容器**接管几何管理**。

        参数:
            layout (Layout): 布局意图由 backend 映射到自身布局系统。
                `layout.into is None` ⇒ 在本句柄**当前所属**容器内重排自身；
                `layout.into` 是 `Handle` ⇒ 请求该容器接管几何（Tk `-in` 选项／
                Qt `layout().addWidget()`）。语义见 `Layout` 类文档。
        返回: `None`。
        回调: 无。
        同步性: 同步返回（几何可能延迟到下一次事件循环生效）。
       所有权: **不由本层承诺 —— 由 backend 决定**。`layout.into` 只保证
            "请求接管几何"；是否伴随 parent/所有权的变化取决于 backend 机制：
            Tk 的 `-in` **不改**控件树（权属不变，退出后句柄仍属原 parent）；
            Qt 的 `addWidget()` **必然** `setParent`（权属转移到 `into` 的宿主控件，
            `into` 销毁 ⇒ 本句柄失效）。
            **调用方不得假定 `into` 前后的权属与生命周期**，必须用 `Handle.exists()`
            探测本句柄是否仍然有效（详见 `Layout` 类文档的实测对照表）。
        释放: 无需释放（但见上：某些 backend 下 `into` 的销毁会**连带**使本句柄失效）。
        逃生口: 无。
        异常: 本句柄已失效抛 `RendererClosedError`；`layout.into` 非 `None` 且不是
            `Handle` 时抛 `InvalidParentError`，`layout.into` 已失效时抛
            `RendererClosedError`；backend 不支持该布局形式，或该 `into` 与主体不同源
            （不满足"`into` 是主体 parent 本身或其后代"）而无法接管几何时抛
            `NotSupportedError`。
        """

    @abstractmethod
    def set_enabled(self, enabled: bool) -> None:
        """启用 / 禁用交互。

        参数:
            enabled (bool): `False` 时**用户交互**被禁用；程序化 API（如 `value.set()`）仍可用。
       返回: `None`。**不得**改变控件的值；是否置灰由 backend 决定。
        回调: 无。
        同步性: 同步返回。
        所有权: 无所有权变更。
        释放: 无需释放。
        逃生口: 无。
        异常: 句柄已失效抛 `RendererClosedError`。
        """


class ValueHandle(Handle):
    """携带单个 `Value` 的控件的公共句柄。"""

    @property
    @abstractmethod
    def value(self) -> Value:
        """该控件的绑定值。

        参数: 无。
        返回: `Value`（neutral；backend 原生变量经 `Handle.native` 获取）。
        回调: 无。
        同步性: 同步返回。
        所有权: `Value` 归本句柄所有，随本句柄销毁而失效。
        释放: 随本句柄 `destroy()` 释放。
        逃生口: 无（原生变量经 `Handle.native`）。
        异常: 句柄已失效抛 `RendererClosedError`。
        """


class InputHandle(ValueHandle):
    """单行输入框（对应 `WidgetMixin.input_box`）。"""

    @abstractmethod
    def set_placeholder(self, hint: str) -> None:
        """设置占位提示文本（灰色提示，聚焦时清空）。

        参数:
            hint (str): 提示文本。
        返回: `None`。
        回调: 无。
        同步性: 同步返回。
        所有权: 无所有权变更。
        释放: 无需释放。
        逃生口: 无。
        异常: 句柄已失效抛 `RendererClosedError`。
        """


class TextAreaHandle(ValueHandle):
    """多行文本框（对应 `create_text_area`）。"""


class CheckboxHandle(ValueHandle):
    """复选框（对应 `create_checkbox`；`command` 为**无参**回调）。"""


class RadioGroupHandle(ValueHandle):
    """单选组（对应 `create_radio_group`）。"""

    @property
    @abstractmethod
    def options(self) -> Sequence[Any]:
        """选项列表；`value` 为选中索引。

        参数: 无。
        返回: `Sequence[Any]`（只读）。
        回调: 无。
        同步性: 同步返回。
        所有权: 无所有权变更。
        释放: 无需释放。
        逃生口: 无。
        异常: 句柄已失效抛 `RendererClosedError`。
        """


class ProgressHandle(Handle):
    """进度条句柄（把原 `create_progress_bar` 返回的**闭包**中性化）。"""

    @abstractmethod
    def update(self, value: float) -> None:
        """更新进度。

        参数:
            value (float): 进度值；实现须夹到 `[0, max_value]`。
        返回: `None`。
        回调: 无。
        同步性: 同步返回。
        所有权: 无所有权变更。
        释放: 无需释放。
        逃生口: 无。
        异常: 句柄已失效抛 `RendererClosedError`。
        """


class ComboHandle(ValueHandle):
    """可编辑下拉框（对应 `create_combo_box`）。"""


class SliderHandle(ValueHandle):
    """滑块（对应 `create_slider`）。"""


class SpinboxHandle(ValueHandle):
    """数字微调框（对应 `create_spinbox`）。"""


class ToggleHandle(ValueHandle):
    """开关（对应 `create_toggle_switch`；`command` 参数为 `bool`）。

    `value` 语义（`Value` 子类，类型为 `bool`）：
        `value.get()` 返回当前开关状态；`value.set(v)` 写入新状态。

   视觉与回调：
        * **`value.set(v)` 必须更新控件视觉**（Tk 适配层即重绘 Canvas）—— 写入值与
          显示状态**不得脱节**；
        * **`command(bool)` 在"用户点击"与"程序化 `value.set()`"两条路径上都会触发**，
          参数为变更**之后**的新值；两条路径**语义等价**（都会更新视觉并触发回调）。
        * `Value.on_change` 的触发条件见 `Value` 类文档（值变更之后、UI 线程同步）。

       顺序 / 去重 / 同值：
        * **顺序**：同一次值变更中先触发 `on_change`，**再**触发 `command`
          （`Value` 是下层，组件级回调后置；这样独立的 `Value` 实现无需知道 `command`）。
        * **去重**：每一次可见的值变更，`command` **恰好触发一次** —— 点击路径内部若
          通过 `value.set()` 实现，**不得**再额外直调 `command`。
        * **同值**：`value.set(v)` 且 `v` 与当前值相同时**不触发**任何回调、也不重绘
          （与 `Value` 文档"值**已变更**之后触发"一致；注：Qt `setChecked(同值)` 不发信号、
          Tk `BooleanVar.set(同值)` 会发 trace，两后端天然不同，故必须在契约层固定）。
    """

    @abstractmethod
    def set_text(self, text: str) -> None:
        """更新开关右侧的标签文本（**新增**）。

        参数:
            text (str): 新文本；**空串合法**，表示显示为空字符串（标签仍然存在）。
        返回: `None`。
        回调: 无 —— 只改文本，**不改值**，因此不触发 `command`，也不触发 `on_change`。
        同步性: 同步返回。
        所有权: 无所有权变更。
        释放: 无需释放。
        逃生口: 无。
        异常: 句柄已失效抛 `RendererClosedError`。
        """


class ListHandle(Handle):
    """可搜索列表句柄（把原 listbox 的**动态 `set_items`** 中性化）。"""

    @abstractmethod
    def set_items(self, items: Sequence[str]) -> None:
        """整批替换数据源。

        参数:
            items (Sequence[str]): 新数据；实现须按当前过滤词刷新显示。
        返回: `None`。
        回调: 不触发 `on_select`。
        同步性: 同步返回。
        所有权: 无所有权变更。
        释放: 无需释放。
        逃生口: 无。
        异常: 句柄已失效抛 `RendererClosedError`。
        """

    @property
    @abstractmethod
    def value(self) -> Value:
        """过滤关键字（字符串）。

        参数: 无。
        返回: `Value`（`str`）。
        回调: 变更回调在 **UI 线程**同步触发。
        同步性: 同步返回。
        所有权: `Value` 归本句柄所有。
        释放: 随本句柄 `destroy()` 释放。
        逃生口: 无。
        异常: 句柄已失效抛 `RendererClosedError`。
        """

    @property
    @abstractmethod
    def selection(self) -> Optional[str]:
        """当前选中项。

        参数: 无。
        返回: `str`；无选中返回 `None`（"无数据"语义，冻结）。
        回调: 无。
        同步性: 同步返回。
        所有权: 只读查询。
        释放: 无需释放。
        逃生口: 无。
        异常: 句柄已失效抛 `RendererClosedError`。
        """


class TableHandle(Handle):
    """表格句柄（把原 `(Frame, Treeview)` 组合返回值中性化）。"""

    @abstractmethod
    def set_rows(self, rows: Sequence[Sequence[Any]]) -> None:
        """整批替换数据行。

        参数:
            rows (Sequence[Sequence[Any]]): 新数据行。
        返回: `None`。
        回调: 不触发 `on_select`。
        同步性: 同步返回。
        所有权: 无所有权变更。
        释放: 无需释放。
        逃生口: 无。
        异常: 句柄已失效抛 `RendererClosedError`。
        """

    @abstractmethod
    def get_rows(self) -> List[Tuple[Any, ...]]:
        """读回全部数据行。

        参数: 无。
        返回: `List[Tuple[Any, ...]]`（每行是 tuple）。
        回调: 无。
        同步性: 同步返回。
        所有权: 只读查询，返回的是副本语义。
        释放: 无需释放。
        逃生口: 无。
        异常: 句柄已失效抛 `RendererClosedError`。
        """

    @property
    @abstractmethod
    def selection(self) -> List[Tuple[Any, ...]]:
        """当前选中行。

        参数: 无。
        返回: `List[Tuple[Any, ...]]`；无选中返回空列表（"无数据"语义，冻结）。
        回调: 无。
        同步性: 同步返回。
        所有权: 只读查询。
        释放: 无需释放。
        逃生口: 无。
        异常: 句柄已失效抛 `RendererClosedError`。
        """


class FormHandle(Handle):
    """智能表单句柄（把原 `(Frame, get_values, set_values)` 三返回值中性化）。"""

    @abstractmethod
    def get_values(self) -> Dict[str, Any]:
        """读取全部字段。

        参数: 无。
        返回: `Dict[str, Any]`（`{key: value}`）。
        回调: 无。
        同步性: 同步返回。
        所有权: 只读查询。
        释放: 无需释放。
        逃生口: 无。
        异常: 句柄已失效抛 `RendererClosedError`。
        """

    @abstractmethod
    def set_values(self, data: Mapping[str, Any]) -> None:
        """批量写入字段值。

        参数:
            data (Mapping[str, Any]): **只设置已存在的 key**，未知 key 忽略。
        返回: `None`。
        回调: 不触发字段回调。
        同步性: 同步返回。
        所有权: 无所有权变更。
        释放: 无需释放。
        逃生口: 无。
        异常: 句柄已失效抛 `RendererClosedError`。
        """


class NotebookHandle(Handle):
    """选项卡句柄（把原 `(Notebook, {title: Frame})` 中性化）。"""

    @abstractmethod
    def tabs(self) -> List[str]:
        """按顺序返回页签标题。

        参数: 无。
        返回: `List[str]`。
        回调: 无。
        同步性: 同步返回。
        所有权: 只读查询。
        释放: 无需释放。
        逃生口: 无。
        异常: 句柄已失效抛 `RendererClosedError`。
        """

    @abstractmethod
    def select(self, title: str) -> None:
        """切换到指定页签。

        参数:
            title (str): 页签标题，必须存在。
        返回: `None`。
        回调: backend 可触发其页签变更回调（**UI 线程**同步）。
        同步性: 同步返回。
        所有权: 无所有权变更。
        释放: 无需释放。
        逃生口: 无。
        异常: 标题不存在抛 `RendererError`；句柄已失效抛 `RendererClosedError`。
        """


class StatusBarHandle(Handle):
    """状态栏句柄（把原 `(Label, set_status)` 中性化）。"""

    @abstractmethod
    def set_status(self, text: str) -> None:
        """更新状态文本。

        参数:
            text (str): 新状态文本。
        返回: `None`。
        回调: 无。
        同步性: 同步返回。
        所有权: 无所有权变更。
        释放: 无需释放。
        逃生口: 无。
        异常: 句柄已失效抛 `RendererClosedError`。
        """


class ScrollableHandle(Handle):
    """可滚动区域句柄（对应 `create_scrollable_canvas` / 可视化画布）。"""

    @property
    @abstractmethod
    def content(self) -> Handle:
        """内部可放控件的内容容器。

        参数: 无。
        返回: `Handle`（可作为其它工厂的显式 `parent`）。
        回调: 无。
        同步性: 同步返回。
        所有权: 归本句柄所有，随本句柄销毁而失效。
        释放: 随本句柄 `destroy()` 释放。
        逃生口: 无。
        异常: 句柄已失效抛 `RendererClosedError`。
        """


class TooltipHandle(Handle):
    """提示气泡句柄。"""

    @abstractmethod
    def show(self) -> None:
        """立即显示。

        参数: 无。
        返回: `None`。
        回调: 无。
        同步性: 同步返回。
        所有权: 无所有权变更。
        释放: 随本句柄 `destroy()` 释放。
        逃生口: 无。
        异常: 句柄已失效抛 `RendererClosedError`。
        """

    @abstractmethod
    def hide(self) -> None:
        """立即隐藏（幂等）。

        参数: 无。
        返回: `None`。
        回调: 无。
        同步性: 同步返回。
        所有权: 无所有权变更。
        释放: 无需释放。
        逃生口: 无。
        异常: 句柄已失效抛 `RendererClosedError`。
        """


class ClockHandle(ValueHandle):
    """时钟句柄。

   兼容：仍以"时钟 label 的句柄"形式返回（不改变首版的返回语义），
    同时提供 `cancel()` 补掉「原 `create_clock` 没有 after_cancel」的缺陷。
    """

    @abstractmethod
    def cancel(self) -> None:
        """停止每秒刷新（幂等）。

        参数: 无。
        返回: `None`。
        回调: 无。
        同步性: 同步返回。
        所有权: 无所有权变更。
        释放: 释放 backend 定时器；此后句柄仍存在但不再刷新。
        逃生口: 无。
        异常: 无（已取消时静默返回）。
        """


class LabelHandle(Handle):
    """文本标签句柄（对应 `label`）——  按人类裁定 (a) 新增**。

    为什么需要它：`label()` 原先返回裸 `Handle`，于是"改一段已经显示出来的文本"**没有任何中立手段**
    （`Handle` 只有 `native`/`destroy`/`exists`/`layout`/`set_enabled`），
   而首版有两处代码必须改文本：`create_clock`（每秒写时间）与 `widgets.buttonx`
    （反馈标签写"已经点击 "）。的 `sheet` 同款教训：能力缺失必须补在中立层，否则只能各后端写一遍。**

    新手友好：`h.set_text("你好")` 一行即可改文案，不需要知道 Tk `config(text=…)` 或 Qt `setText(…)`。
    """

    @abstractmethod
    def set_text(self, text: str) -> None:
        """更新标签文本（**唯一**的中立改文本入口）。

        参数:
            text (str): 新文本；空串合法（显示为空）。
        返回: `None`。
        回调: 无（本方法只改显示；若需要"值变化"语义，请用 `Value`/`ValueHandle` 家族）。
        同步性: 同步返回。
        所有权: 无所有权变更。
        释放: 无需释放。
        逃生口: `handle.native`（backend 原生 label 控件）。
        异常: 句柄已失效抛 `RendererClosedError`。
        """


class _ClockTextValue(Value):
    """时钟文本值（只读）：`get()` 给当前时间文本；`set()` **明确拒绝**（不静默）。

    新手友好：`clock(...).value.get()` 就能读到 "2026-10-03 12:34:56"，无需知道定时器细节。
    """

    def __init__(self, formatter):
        self._fmt = formatter
        self._text = ""
        self._callbacks = []

    def get(self):
        return self._text

    def set(self, value):
        raise NotSupportedError(
            "时钟文本是**只读**的（时间由定时器驱动）；如需自定义显示请改用 label + schedule")

    def on_change(self, callback):
        self._callbacks.append(callback)

        def _off():
            if callback in self._callbacks:
                self._callbacks.remove(callback)
        return _off

    def _update(self, text):
        self._text = text
        for cb in list(self._callbacks):
            cb(text)


class _NeutralClockHandle(ClockHandle):
    """时钟句柄（**base 一次实现**，两 backend 共用； (b)）。

    只用中立原语：`label()` 建控件 + `schedule()` 每秒推进 + `LabelHandle.set_text()` 写文本。
   补掉首版 `create_clock` 的缺陷：**没有 `after_cancel`** ⇒ 本类提供 `cancel()`（幂等），
    并在 `destroy()` 时自动停表（不留空转的定时器）。
    """

    def __init__(self, renderer, label_handle, period_ms, formatter):
        self._renderer = renderer
        self._label = label_handle
        self._period = max(1, int(period_ms))
        self._fmt = formatter
        self._cancelled = False
        self._timer = None
        self._value = _ClockTextValue(formatter)
        self._tick()                            # 立即写第一帧（首版同：先显示再排下一拍）

    # ---------------- 内部 ----------------
    def _tick(self):
        if self._cancelled or not self._label.exists():
            return
        import datetime as _dt
        text = _dt.datetime.now().strftime(self._fmt)
        self._label.set_text(text)
        self._value._update(text)
        if not self._cancelled:
            self._timer = self._renderer.schedule(self._period, self._tick)

    # ---------------- ClockHandle / ValueHandle / Handle ----------------
    @property
    def value(self):
        """当前时间文本（只读 `Value`）。"""
        return self._value

    def cancel(self):
        """停止每秒刷新（**幂等**）；此后 `value.get()` 保留最后一次文本，控件仍在。"""
        self._cancelled = True
        if self._timer is not None:
            try:
                self._timer.cancel()
            except Exception:                   # noqa: BLE001 —— 幂等
                pass
            self._timer = None

    @property
    def native(self):
        return self._label.native

    def exists(self) -> bool:
        return self._label.exists()

    def destroy(self) -> None:
        """停止刷新并销毁时钟控件（幂等）。"""
        self.cancel()
        self._label.destroy()

    def layout(self, layout) -> None:
        self._label.layout(layout)

    def set_enabled(self, enabled: bool) -> None:
        self._label.set_enabled(enabled)


class MediaHandle(Handle):
    """静态图片句柄（对应 `photo`）。"""


class AnimationHandle(MediaHandle):
    """动画句柄（对应 `gif` / `animation`）。

    **失败哨兵**：首版的 `animation(...) -> int` 在失败 / 无 Pillow 时返回 `0`。
    本层把返回句柄中性化，但**保留该哨兵语义**：失败时返回的句柄 `frame_count == 0`，
    且 **`animation` 永不返回 `None`**。
    """

    @property
    @abstractmethod
    def frame_count(self) -> int:
        """实际加载的帧数。

        参数: 无。
       返回: `int`；失败或无 Pillow 时为 `0`（对应首版的 `0` 哨兵，冻结）。
        回调: 无。
        同步性: 同步返回。
        所有权: 只读查询。
        释放: 无需释放。
        逃生口: 无。
        异常: 句柄已失效抛 `RendererClosedError`。
        """

    @abstractmethod
    def stop(self) -> None:
        """停止播放但保留控件（幂等）。

        参数: 无。
        返回: `None`。
        回调: 不再触发 `on_frame`。
        同步性: 同步返回。
        所有权: 无所有权变更。
        释放: 释放 backend 定时器。
        逃生口: 无。
        异常: 无（已停止时静默返回）。
        """


class TimerHandle(ABC):
    """定时器句柄（`Renderer.schedule` 的返回值）。"""

    @abstractmethod
    def cancel(self) -> None:
        """取消定时器（幂等，对已触发的定时器调用安全）。

        参数: 无。
        返回: `None`。
        回调: 被取消的回调不会再执行。
        同步性: 同步返回。
        所有权: 无所有权变更。
        释放: 释放 backend 定时器资源。
        逃生口: 无。
        异常: 无。
        """

    @abstractmethod
    def is_active(self) -> bool:
        """该定时器是否**仍处于已排定（尚未触发）状态**。

        参数: 无。
        返回: `bool` —— 定时器当前是否已排定且尚未触发/取消（Tk：
            `after_info()` 仍能查到该 id；Qt：`QTimer.isActive()`）。
            **不得**定义为"回调是否已经跑过"等副作用推断：`schedule(..., 0)`
            的定时器可能已排定但尚未派发。
        回调: 无。
        同步性: 同步返回。
        所有权: 只读查询。
        释放: 无需释放。
        逃生口: 无。
       异常: 无。**不承载 （base 的控制流不消费本方法），故查询失败可返回
            `False`；这与 `Renderer.is_alive()` 的"必须上抛"策略不同是有意的
            （后者承载，见其文档）。
        """


# --------------------------------------------------------------------------- #
# Renderer 抽象契约
# --------------------------------------------------------------------------- #
class Renderer(ABC):
    """backend-neutral 渲染器契约。

    用法（UI 线程）::

        r = Renderer()                     # 进程内唯一；已有存活实例则抛 RendererError
        root = r.root
        r.label(root, '你好', layout=Layout.pack(pady=10))
        r.run()                            # 进入事件循环

    生命周期 / 单例（强制，不可绕过）
        * 子类 `__init__` **必须先调用 `super().__init__(theme)`**，再建立 backend root。
          单例的校验与登记就在 `super().__init__()` 内完成，因此**第 2 个实例会在分配
          backend root 之前**抛 `RendererError`，不会泄漏孤儿 root。
        * 子类**无需**（也不应）自行登记；但**漏调 `super().__init__()` 会被当场发现**：
          `__init_subclass__` 包装后的构造在**正常返回**时会校验单例槽位确实登记为
         本实例，否则抛 `RendererError`—— 不存在静默绕过 的路径。
        * **构造失败 ⇒ 不占槽位，且尽力回收**：`__init_subclass__` 会包装子类
          `__init__`，构造过程中抛出的异常会在**确认进程内没有别的存活实例**（槽位为空
          或就是本实例）时**先尽力 `self._destroy_root()` 回收**半构造实例可能已建立的
          backend root，**再**清空单例槽位，**最后**原样重抛。因此失败的构造既不留
          "幽灵实例"、不会永久阻塞后续构造，也**不会把孤儿 root 留给下一次构造**。
          此处清理是**尽力而为**（`_best_effort_destroy`）：清理自身失败会被忽略，
          以保证**原始异常优先**；相应地，子类 `_destroy_root()` **必须能安全处理
          半构造实例**（见 `_destroy_root()` 文档）。
        * **回收钩子的调用范围**：两条路径**故意不对称**：
          —— **异常路径**：若失败时槽位属于**另一个存活实例**，本实例必然从未登记、
         也从未建立任何资源（校验先于任何 root 创建就抛出，这正是"已存在存活实例
          ⇒ 被拒"的路径），此时**不做**回收调用；
          —— **路径**：本实例走完了整个 `__init__` 才被发现漏调 `super()`，
          因此**可能真的建立了资源**，此时**必须无条件回收**，否则静默泄漏孤儿 root
          （"宁可回收也不泄漏"）。该路径的安全性不靠守卫，而靠 的硬义务：
          合规的 `_destroy_root()` 只释放**本实例自己建立**的资源、**不得**触碰进程级
          共享对象，所以在"槽位属于别的存活实例"时它也不会误伤对方。
          对**不合规** backend，本路径失去兜底 —— 这是明确接受的取舍（登记项）。
        * **释放侧免纪律化**：`destroy()` 是模板方法（子类**不得**覆写，覆写会在类创建期
          抛 `TypeError`），固定执行 `_destroy_root()`，随后**按 `is_alive()` 判定**
          是否 `_release()`，因此槽位释放由 base 保证，而不是子类的义务。
          子类实现 `_destroy_root()`。
         不变量是「**槽位 ⇔ 存活实例**」：`_destroy_root()` 抛异常只说明
          "释放失败"、不说明 root 已不存在，故此时**保留槽位**（否则 base 自己会放行
          第二个 backend root）；半途失败后重试 `destroy()`（幂等）即可释放。
          即便实例仍以其它方式变成死实例，`Renderer.current()` 也会在 `is_alive()`
          **诚实返回 `False`** 时自动释放（自愈，故不会永久锁死）。
        * **覆写防护的范围**（登记项，见 `历史登记`）：上述 `TypeError` 在
          **类创建期**（`__init_subclass__`）生效，正好覆盖"用 `class` 语句声明 `destroy`"
          这一正常写法。类创建**之后**再用 `setattr(cls, 'destroy', ...)` 强行替换属蓄意
          破坏，不在防护范围内 —— Python 无法阻止对类属性的运行时改写；本层只保证
          **声明式**覆写不会静默改变释放纪律。
        * `is_alive()` 自身抛异常时**不会**被吞掉：异常向上传播，槽位保持不变 ——
          这是"快速失败"要求（静默释放会放行第二个 backend root）。
        * 单例状态存放在**进程级槽位**（`sys`）而非模块全局/类属性：这样即使本文件被以
          两个模块名导入，也不会分裂出第二份状态。

    线程
        **除 `post()` 外，所有 API 与回调都必须在 UI 线程调用。**

    parent / 所有权
        除**窗口级操作**与**顶层部件**外，所有**子控件**工厂方法都必须显式传入
        `parent: Handle`；`parent` 为 `None`/类型错误抛 `InvalidParentError`，
        已失效抛 `RendererClosedError`。**工厂方法返回值在创建时**归 `parent` 所有，
        随 `parent` 或自身 `destroy()` 失效 —— 各工厂的 `所有权:` 行均是**创建时**的
        陈述。

        **例外**：句柄此后若经 `Layout.into` 被其它容器**接管几何**，
        权属**由 backend 决定**（Tk 的 `-in` 不改 parent；Qt 的 `addWidget()` 会
        `setParent`，`into` 销毁即连带销毁该句柄）。**不得**用"原 parent 是否存活"
        推断句柄是否有效，请用 `Handle.exists()` —— 它是权属/可用性的**唯一**探测
        手段，其定义为"底层对象当前是否仍然存在/可用"（详见 `Handle` 类文档、
        `Layout` 类文档与）。

        **契约级结论（顶层部件 vs 子控件）**：
        下列方法**不接受** `parent`，因为它们创建的是**顶层部件**、由 `Renderer` 自己拥有，
        而不是挂在某个容器下的子控件 —— `message` / `ask_input` / `ask_save_path` /
        `ask_open_path` / `ask_directory` / `report_window` / `toast`；
        `menu_bar` 设置的是**窗口级**菜单栏，其"父"就是窗口，故以**显式** `parent`
        （通常是 `Renderer.root`）表达，而不是回退到隐式容器。
        其余全部工厂方法（含 `toolbar` / `status_bar`）一律要求显式 `parent`；
       首版的隐式 `scrollable_frame` / `toolbar_container` / `statusbar_container`
        属实现内部细节，**不进入本层**。

    逃生口与异常
        句柄的 backend 原生对象经 `Handle.native`（显式逃生口）获取；
        非法/不支持/已销毁分别抛 `InvalidParentError` / `NotSupportedError` / `RendererClosedError`。
    """

    def __init__(self, theme: Optional[Theme] = None):
        self.theme = theme if theme is not None else Theme.light()
        # 单例校验 + 登记，必须早于子类建立 backend root
        cur = _live_current()
        if cur is not None and cur is not self:
            raise RendererError(
                '已存在存活的 Renderer 实例（backend root 必须进程内唯一）。'
                '请改用 Renderer.current()，或先对旧实例调用 destroy()。'
            )
        _slot_set(self)

    def __init_subclass__(cls):
        """包装子类 `__init__`，保证 单例纪律在**构造期**不可绕过。

        为什么需要它：`Renderer.__init__` 必须在子类建立 backend root **之前**登记单例
        （否则第 2 个实例会泄漏孤儿 root）。若子类构造体在 `super().__init__()` **之后**失败
        （无显示环境 / backend 不可用 / 资源不足），槽位会残留"幽灵实例"并永久阻塞后续构造。
        基类无法知道子类构造体是否跑完，因此只能在**类创建期**接管。

        包装后的 `_guarded` 承担两件事：

        * （失败 ⇒ 不占槽位，且尽力回收）**：构造抛异常时，先尽力
          `self._destroy_root()` 回收半构造实例可能已建立的 backend root，再清空槽位，
          最后原样重抛。清理自身失败会被忽略 —— 原始异常必须胜出。
         回收**附带范围守卫**：仅当槽位就是本实例、或槽位为空（进程内没有别的
          存活实例）时才调用钩子。若槽位属于**另一个存活实例**，本实例必然从未登记、
         也从未建立任何资源（校验先于任何 root 创建就抛出），此时调用按进程级单例
          实现的钩子会拆掉活跃实例的 root。
        * （正常返回 ⇒ 确认已登记）**：构造正常返回后校验槽位确为本实例，
          否则抛 `RendererError`。没有这一步，"子类忘记调用 `super().__init__()`"
          会静默产出一个**未登记的、仍在运行的 backend root** —— 后续构造照样成功，
         于是进程里出现两个 root，正是 要禁止的情形，却不会被发现。

        同时禁止子类覆写 `destroy()` —— 它已改为模板方法，子类应实现 `_destroy_root()`，
        这样 `_release()` 才是 base 的保证而不是子类的义务。

        注：本方法是全模块**唯一**使用 `*args, **kwargs` 转发之处；它是私有基础设施，
        不是 API 逃生口 —— 模块内所有公开 API 签名仍逐一显式、无 `**kwargs`。
        """
        super().__init_subclass__()
        if 'destroy' in cls.__dict__:
            raise TypeError(
                '%s 不得覆写 destroy()：它已是模板方法。请改为实现 _destroy_root()。'
                % cls.__name__
            )
        init = cls.__dict__.get('__init__')
        if init is None or getattr(init, '_ck10_guarded', False):
            return

        @functools.wraps(init)
        def _guarded(self, *args, **kwargs):
            try:
                init(self, *args, **kwargs)
            except BaseException:
                # 构造失败 ⇒ 尽力回收 → 清槽位 → 原样重抛
                # （`raise` 无参 ⇒ 原始异常胜出）。
                #
                # 回收**仅在**「槽位就是本实例」或「槽位为空（进程内没有别的存活
                # 实例）」时进行。若槽位属于**另一个存活实例**，本实例必然从未登记、
                # 也从未建立任何资源 ——  校验先于任何 root 创建就抛出，这正是
                # "已存在存活实例 ⇒ 被拒"这一最常见路径。此时调用释放钩子纯属空转，
                # 且若钩子按进程级单例写（Qt：`QApplication.instance().quit()`）
                # 会拆掉**活跃实例**的 root，而 `current()` 仍返回那个僵尸实例。
                _cur = _slot_get()
                if _cur is self or _cur is None:
                    _best_effort_destroy(self)
                if _cur is self:
                    _slot_set(None)
                raise
            # 正常返回却未登记 ⇒ 子类漏调 super().__init__()。
            if _slot_get() is not self:
                # 此处**不设**槽位守卫：与异常路径不同，本实例走完了整个
                # `__init__` 才被发现漏调 `super()`，因此它**可能真的建立了资源**；
                # 不回收就是静默泄漏孤儿 root（实测 `LIVE roots 1 → 2`）。
                # 安全性由 的硬义务保证：合规的 `_destroy_root()` 只释放
                # **本实例自己建立**的资源、不触碰进程级共享对象，
                # 故"槽位属于别的存活实例"时它也不会误伤对方。
                _best_effort_destroy(self)
                raise RendererError(
                    '%s.__init__ 未调用 super().__init__()，单例槽位未登记。'
                    '子类 __init__ 必须先调用 super().__init__(theme)，再建立 backend root。'
                    % type(self).__name__
                )

        _guarded._ck10_guarded = True
        cls.__init__ = _guarded

    # ------------------------------------------------------------------ #
    # 单例与受保护助手
    # ------------------------------------------------------------------ #
    @classmethod
    def current(cls) -> Optional['Renderer']:
        """返回当前**存活**实例；没有则返回 `None`。

        参数: 无。
        返回: `Renderer | None`；`is_alive()` **诚实返回 `False`** 的实例会被自动释放
            并返回 `None`。
        回调: 无。
        同步性: 同步返回。
        所有权: 只读查询，不转移所有权。
        释放: 会顺带释放已死实例占用的单例槽位。
        逃生口: 无。
        异常: 实例 `is_alive()` 自身抛异常时**不被吞掉** —— 异常原样向上传播，
            且槽位**保持不变**（快速失败：静默释放会放行第二个 backend root）。
        """
        return _live_current()

    def _release(self) -> None:
        """释放进程级单例槽位（幂等）；**仅供** `Renderer.destroy()` 模板方法调用。

       调用条件是 的不变量「**槽位 ⇔ 存活实例**」：只有确认本实例已不存在
        （`not self.is_alive()`）时才可释放。

        注意 `_live_current()` **不经过**本方法 —— 它在诚实测活返回 `False` 时直接
        内联 `_slot_set(None)`：那条路径上并没有"某个实例在释放自己"，只是在清理一个
       已死的槽位。两处清空语义相同、路径不同。
        """
        if _slot_get() is self:
            _slot_set(None)

    def _ensure_alive(self) -> None:
        """本层自用的存活校验：已销毁 → `RendererClosedError`。"""
        if not self.is_alive():
            raise RendererClosedError(
                '%s 已销毁，不能继续调用 Renderer API' % type(self).__name__
            )

    def _validate_parent(self, parent: Handle) -> Handle:
        """校验并返回 `parent`。

        非法（`None` / 非 `Handle`）→ `InvalidParentError`；
        parent 已失效 → `RendererClosedError`。供 backend 与其自身的组合实现复用。

        **不校验归属**：`Handle` 不暴露 Renderer 反向引用，"parent 属于另一个 Renderer"
        无法检测，故 base 不承诺、`InvalidParentError` 文档亦不含该情形。
       跨 Renderer 的陈旧句柄由 `exists()` 兜底 ——  保证任一时刻只有一个存活 Renderer，
        旧 Renderer 销毁后其句柄 `exists()` 为 `False`，于是这里抛 `RendererClosedError`。

        **依赖 `exists()` 的 定义**：本方法是 base 内部**唯一**消费 `exists()` 的地方，
        其正确性依赖 `exists()` 为"**底层对象当前是否仍然存在/可用**"这一**实现中立**语义。
        若某个 backend 把 `exists()` 实现成"原 parent 仍存活"，则在 Qt 上经 `Layout.into`
        reparent 的句柄会对**仍然可用的容器**给出假阴性 ⇒ 本方法会误抛
        `RendererClosedError`，把合法 parent 拒掉（见 `Layout` 类文档与）。
        """
        if parent is None or not isinstance(parent, Handle):
            raise InvalidParentError(
                'parent 必须是显式传入的 Handle，收到 %r' % (parent,)
            )
        if not parent.exists():
            raise RendererClosedError('parent 已失效（已销毁或其祖先已销毁）')
        return parent

    # ------------------------------------------------------------------ #
    # 生命周期
    # ------------------------------------------------------------------ #
    @abstractmethod
    def run(self) -> None:
        """进入事件循环，直到窗口关闭或 `destroy()`。

        参数: 无。
        返回: `None`；`run()` 返回后 `is_alive()` 可能仍为真（窗口被关闭但未销毁）。
        回调: 事件循环期间在 **UI 线程**同步派发全部已注册回调。
        同步性: **阻塞**（直到循环退出）。
        所有权: 无所有权变更。
        释放: 不释放资源；退出后由调用方 `destroy()`。
        逃生口: 无。
        异常: Renderer 已销毁时抛 `RendererClosedError`。
        """

    @abstractmethod
    def update(self) -> None:
        """处理一次待办事件（非阻塞），供脚本与测试使用。

        参数: 无。
        返回: `None`。
        回调: 期间在 **UI 线程**同步派发待办回调。
        同步性: **非阻塞**，处理完当前队列即返回。
        所有权: 无所有权变更。
        释放: 无需释放。
        逃生口: 无。
        异常: Renderer 已销毁时抛 `RendererClosedError`。
        """

    def destroy(self) -> None:
        """销毁 root 与全部子资源（幂等）—— **模板方法，子类不得覆写**。

        参数: 无。
        返回: `None`。
        回调: 不再派发任何回调；待执行的定时器回调必须被丢弃。
        同步性: 同步返回。
        所有权: 释放 root 与全部子句柄；此后对它们的操作抛 `RendererClosedError`。
        释放: 本方法即释放责任方；固定顺序为 ① `self._destroy_root()`（子类实现）
            → ② **按判据**决定是否 `self._release()`：槽位遵守不变量
            "**槽位 ⇔ 存活实例**"，故**仅当 `is_alive()` 表明 root 确已不存在**时
            才释放槽位。子类不得覆写本方法（覆写会在类创建期抛 `TypeError`），
            请实现 `_destroy_root()`。

           为什么不能无条件释放：`_destroy_root()` 抛异常只说明
            "**释放失败**"，**不说明 root 已不存在**。若此时仍清空槽位，
            `Renderer.current()` 会返回 `None` ⇒ 后续构造被放行 ⇒
            **两个 backend root 并存**（禁止），而放行它的正是 base 自己。
            半途失败后：槽位保留 ⇒ `current()` 仍返回该实例、第二次构造被拒绝；
            用户重试 `destroy()`（幂等）成功后释放，或 root 以其它方式消失时由
            `_live_current()` 的诚实测活**自愈** —— **不会永久锁死**。
        逃生口: 无。
        异常: 无（重复调用静默返回）；`_destroy_root()` 的异常原样向上传播；
            判定存活性时 `is_alive()` 自身抛出的异常**不向上传播**（保守保留槽位，
            以免覆盖 `_destroy_root()` 的原始异常）。
        """
        try:
            self._destroy_root()
        finally:
            try:
                gone = not self.is_alive()
            except Exception:          # 判活失败 ⇒ 不确定 ⇒ 保守保留槽位
                gone = False
            if gone:
                self._release()

    @abstractmethod
    def _destroy_root(self) -> None:
        """释放 backend root 与全部子资源（由 `Renderer.destroy()` 模板方法调用）。

        参数: 无。
        返回: `None`。
        回调: 不再派发任何回调；待执行的定时器回调必须被丢弃。
        同步性: 同步返回。
        所有权: 释放 root 与全部子句柄；此后对它们的操作抛 `RendererClosedError`。
        释放: 本方法是真正的释放实现；**不要**在此调用 `_release()`（模板方法已负责）。
            幂等：重复调用须静默返回。

            **只释放本实例自己建立的资源**：本方法可能在实例**从未登记单例、
           也未建立任何资源**时被调用 —— 构造被 拒绝、或子类漏调
            `super().__init__()` 的路径。实现因此**不得**：
              * 触碰**进程级共享对象**（典型：Qt 的 `QApplication.instance()` ——
                对它是进程级单例，`QApplication.instance().quit()` 会拆掉**活跃实例**
                的 root，而 `Renderer.current()` 仍返回那个僵尸实例）；
              * 假定任何资源已经建立（未建立的资源一律按"无需释放"处理）。
            换句话说：**只回收自己造的**，不要"顺手清理全局状态"。

            **必须能安全处理"半构造"实例**：构造失败路径
            （`__init_subclass__` 的 `_guarded`）会在实例**未完成初始化**时调用本方法，
            因此实现**不得**假定所有属性都已就绪 —— 未建立的资源按"无需释放"处理，
            已建立的资源必须释放。此路径下本方法抛出的异常会被忽略（尽力而为）。

            **可能被多次调用**：同一次构造失败在 N 层继承下最多触发 N+1 次
            （每层 `_guarded` 各调用一次），加上正常的 `destroy()` 路径还可能再来一次。
            因此"幂等"是**硬要求**，而不是优化建议。
        逃生口: 无。
        异常: 无（重复调用静默返回）。
        """

    @abstractmethod
    def is_alive(self) -> bool:
        """backend root 是否**仍然存在 / 可用**。

       本方法是 单例纪律的**根基探测**。base 内的消费点共**三处**：
        `_live_current()`（`Renderer.current()` 走它）、`_ensure_alive()`（所有 API
       的存活校验）、以及 `destroy()` 模板方法（据此决定是否释放槽位）。

        参数: 无。
        返回: `bool` —— **backend root 对象当前是否仍然存在 / 可用**
            （Tk：root 的 `winfo_exists()`；Qt：C++ 对象未被删除）。
            **不得**定义为"窗口可见 / 已 map / 未被最小化 / 事件循环正在跑"等
            **可观察状态**：暂时不可见 ≠ root 不存在。按该定义，一次
            `withdraw()`（本项目测试即大量使用，且未 map 时 `winfo_geometry()`
            返回 `1x1+0+0`）就会被判死 ⇒ `Renderer.current()` 在自动释放路径上
            **静默清空槽位** ⇒ 放行第二个 backend root，正是 禁止的情形。
        回调: 无。
        同步性: 同步返回。
        所有权: 只读查询。
        释放: 无需释放。
        逃生口: 无。
        异常: **允许并应当向上抛出** —— `_live_current()` 依赖该异常传播
            （"快速失败"；第 2 轮 的全部修法即"不得把异常 catch 成 `False`"）。
            **不得**把底层查询失败吞成 `False`：那等价于"诚实报告 root 已死"，
            会静默释放单例槽位、放行第二个 root。
            未完成构造的实例返回 `False` 属正常（见 `__init_subclass__`）。
            注意与 `Handle.exists()` 的**异常策略相反**（后者"查询失败返回 `False`"）：
           差异是**有意**的，因为 `exists()` 不承载、`is_alive()` 承载；
            两个策略在各自文档里互相点名。
        """

    # ------------------------------------------------------------------ #
    # 定时与线程
    # ------------------------------------------------------------------ #
    @abstractmethod
    def schedule(self, delay_ms: int, callback: Callable[[], None]) -> TimerHandle:
        """在 UI 线程延迟执行一次 `callback`。

        参数:
            delay_ms (int): 延迟毫秒数。
            callback (Callable[[], None]): **无参**回调。
        返回: `TimerHandle`（含 `cancel()`）。
        回调: 在 **UI 线程**同步执行；`destroy()` 之后不得再执行。
        同步性: 注册同步返回，回调异步触发。
        所有权: 定时器归本 Renderer 所有，随 `destroy()` 释放。
        释放: `TimerHandle.cancel()` 或 `destroy()`。
        逃生口: 无。
        异常: Renderer 已销毁时抛 `RendererClosedError`。
        """

    def post(self, callback: Callable[[], None]) -> None:
        """**可从任意线程**投递 `callback`，它将在 UI 线程执行。

        参数:
            callback (Callable[[], None]): **无参**回调。
        返回: `None`。
        回调: 在 **UI 线程**执行；`destroy()` 之后投递的必须被**静默丢弃**。
        同步性: 投递同步返回，回调异步触发。
        所有权: 回调由本 Renderer 持有直到执行或销毁。
        释放: 随 `destroy()` 丢弃未执行的投递。
        逃生口: 无。
        异常: 尚未实现线程安全队列的 backend 必须抛 `NotSupportedError`（**不得**假装安全）。
        """
        raise NotSupportedError('post 未被该 backend 实现（线程安全队列尚未建立）')

    # ------------------------------------------------------------------ #
    # 窗口
    # ------------------------------------------------------------------ #
    @property
    @abstractmethod
    def root(self) -> Handle:
        """root 容器句柄（所有显式 parent 的最终祖先）。

        参数: 无。
        返回: `Handle`；可直接作为任一工厂的显式 `parent`。
        回调: 无。
        同步性: 同步返回。
        所有权: 归本 Renderer 所有；`destroy()` 后失效。
        释放: 由 `Renderer.destroy()` 释放，调用方不得单独销毁 root。
        逃生口: `root.native` 即 backend 顶层窗口对象。
        异常: Renderer 已销毁时抛 `RendererClosedError`。
        """

    @abstractmethod
    def set_title(self, text: str) -> None:
        """设置窗口标题。

        参数:
            text (str): 标题文本。
        返回: `None`。
        回调: 无。
        同步性: 同步返回。
        所有权: 无所有权变更。
        释放: 无需释放。
        逃生口: 无。
        异常: Renderer 已销毁时抛 `RendererClosedError`。
        """

    @abstractmethod
    def set_size(self, width: int, height: int) -> None:
        """设置窗口几何。

        参数:
            width (int): 宽（像素）。
            height (int): 高（像素）。
        返回: `None`。
        回调: 无。
        同步性: 同步返回。
        所有权: 无所有权变更。
        释放: 无需释放。
        逃生口: 无。
        异常: Renderer 已销毁时抛 `RendererClosedError`。
        """

    @abstractmethod
    def center_window(self) -> None:
        """按屏幕尺寸把窗口居中。

        参数: 无。
        返回: `None`。
        回调: 无。
        同步性: 同步返回（几何可能延迟到下一次事件循环生效）。
        所有权: 无所有权变更。
        释放: 无需释放。
        逃生口: 无。
        异常: Renderer 已销毁时抛 `RendererClosedError`。
        """

    def set_always_on_top(self, flag: bool = True) -> None:
        """置顶开关。

        参数:
            flag (bool): `True` 置顶。
        返回: `None`。
        回调: 无。
        同步性: 同步返回。
        所有权: 无所有权变更。
        释放: 无需释放。
        逃生口: 无。
        异常: 默认实现抛 `NotSupportedError`；Renderer 已销毁时抛 `RendererClosedError`。
        """
        raise NotSupportedError('set_always_on_top 未被该 backend 实现')

    def add_shortcut(self, sequence: str, callback: Callable[[], None]) -> None:
        """注册全局快捷键。

        参数:
            sequence (str): backend 中立的按键描述（如 `'Ctrl+S'`）；Tk 的 `'<Control-s>'`
                属 backend 专属写法，不得直接照搬。
            callback (Callable[[], None]): **无参**回调，在 **UI 线程**同步执行。
        返回: `None`。
        回调: 同上。
        同步性: 注册同步返回；回调在按键时同步触发。
        所有权: 绑定归本 Renderer 所有，随 `destroy()` 释放。
        释放: `destroy()`。
        逃生口: 无。
        异常: 默认实现抛 `NotSupportedError`；Renderer 已销毁时抛 `RendererClosedError`。
        """
        raise NotSupportedError('add_shortcut 未被该 backend 实现')

    # ------------------------------------------------------------------ #
    # 剪贴板 / 菜单栏
    # ------------------------------------------------------------------ #
    @abstractmethod
    def set_clipboard_text(self, text: str) -> None:
        """写入系统剪贴板。

        参数:
            text (str): 要写入的文本。
        返回: `None`。
        回调: 无。
        同步性: 同步返回。
        所有权: 无所有权变更。
        释放: 无需释放。
        逃生口: 无。
        异常: Renderer 已销毁时抛 `RendererClosedError`。
        """

    @abstractmethod
    def get_clipboard_text(self) -> str:
        """读取系统剪贴板。

        参数: 无。
        返回: `str`；无内容返回空串。
        回调: 无。
        同步性: 同步返回。
        所有权: 只读查询。
        释放: 无需释放。
        逃生口: 无。
        异常: Renderer 已销毁时抛 `RendererClosedError`。
        """

    def menu_bar(self, parent: Handle, items: Optional[Sequence[Any]] = None) -> Handle:
        """设置窗口菜单栏（首版的 `create_menu`）。

        参数:
            parent (Handle): **显式**父容器（窗口级菜单请传 `Renderer.root`）。
            items (Sequence[Any] | None): 每项 `(menu_name, [(label, command), ...])`。
        返回: `Handle`（菜单栏句柄）；backend 原生菜单经 `Handle.native` 获取。
        回调: 菜单项的 `command` 为**无参**回调，在 **UI 线程**同步执行。
        同步性: 注册同步返回。
        所有权: 菜单栏归 `parent` 所有，随其销毁而失效。
        释放: 随 `parent` 或自身 `destroy()` 释放。
        逃生口: `handle.native`。
        异常: `InvalidParentError`（parent 非法）、`RendererClosedError`（已销毁）、
            默认实现抛 `NotSupportedError`。
        """
        raise NotSupportedError('menu_bar 未被该 backend 实现')

    # ------------------------------------------------------------------ #
    # 容器与布局（显式 parent）
    # ------------------------------------------------------------------ #
    @abstractmethod
    def container(self, parent: Handle, layout: Optional[Layout] = None,
                  col_weights: Optional[Sequence[int]] = None) -> Handle:
        """创建一个普通容器。

        参数:
            parent (Handle): **显式**父容器。
            layout (Layout | None): 布局意图（描述**该容器在 `parent` 中**如何放置）；
                `None` 表示由实现取默认（Tk 适配层取顺序流）。
            col_weights (Sequence[int] | None): **该容器自身**网格的各列伸缩权重
                （`None` = 各列等权，即"不设置"）。这是**容器属性**而非子项属性：
                在 Tk 上映射为 `container.grid_columnconfigure(i, weight=w)`，Qt 上映射为
                `QGridLayout.setColumnStretch(i, w)`。它**不**影响容器自身在 `parent` 中的
               放置方式。**"容器自身怎么摆"与"容器内部是不是网格"是两件事（修订）**：
                本参数作用于**容器自身的内部网格**，因此**只要给了就设置**（两个现实后端都
                做得到：Tk 的 `grid_columnconfigure` / Qt 的 `QGridLayout` 都可按需建立；
                纯顺序流容器上这些权重是**惰性**的、不影响任何既有布局）。
               只有实现**确实无法设置**时才 **抛 `NotSupportedError`**（不得静默忽略）。
                *（原文"顺序流 layout + `col_weights` ⇒ 允许静默忽略"仍允许——只是两个
               现实后端选择"设置它"而不是"忽略它"；`parity` 的 只要求"不得抛"。）*
        返回: `Handle`；原生容器经 `Handle.native` 获取。
        回调: 无。
        同步性: 同步返回。
        所有权: 句柄归 `parent` 所有，随其销毁而失效。
        释放: 自身 `destroy()` 或 `parent` 销毁。
        逃生口: `handle.native`。
        异常: `InvalidParentError`、`RendererClosedError`；`col_weights` 非 `None`、**且该
           容器走网格**，而 backend 无法设置列权重时抛 `NotSupportedError`（**不得**
            静默忽略；若该容器走顺序流，则 `col_weights` 无意义，允许静默忽略，见上）。
        """

    # ------------------------------------------------------------------ #
    # 基础控件
    # ------------------------------------------------------------------ #
    @abstractmethod
    def label(self, parent: Handle, text: str, color: Optional[str] = None,
              family: Optional[str] = None, size: Optional[int] = None,
              bold: Optional[bool] = None, anchor: Optional[str] = None,
              layout: Optional[Layout] = None) -> LabelHandle:
        """文本标签。

       返回 `LabelHandle`：比裸 `Handle` 多一个中立
        `set_text()`，供"改已显示文本"这类需求使用（首版的 `create_clock`、
        `widgets.buttonx` 的反馈标签都属此类；新手只需 `h.set_text("你好")`）。

        参数:
            parent (Handle): **显式**父容器。
            text (str): 标签文本。
            color (str | None): 文字色；`None` 取 `Theme.default_color`。
            family (str | None): 字体族；`None` 取 `Theme.default_family`。
            size (int | None): 字号；`None` 取 `Theme.label_default_size`（首版 `label_ck` 默认 `tsize=20, tblod=True`；本组 token 为 `12`/`False`，属**有意变更**，已登记）。
            bold (bool | None): 是否加粗；`None` 取 `Theme.label_default_bold`。
            anchor (str | None): 文本锚点；`None` 由实现取默认。
            layout (Layout | None): 布局意图。
        返回: `Handle`。
        回调: 无。
        同步性: 同步返回。
        所有权: 句柄归 `parent` 所有。
        释放: 自身 `destroy()` 或 `parent` 销毁。
        逃生口: `handle.native`。
        异常: `InvalidParentError`、`RendererClosedError`。
        """

    @abstractmethod
    def button(self, parent: Handle, text: str, command: Optional[Callable[[], None]] = None,
               width: Optional[int] = None, height: Optional[int] = None,
               color: Optional[str] = None, family: Optional[str] = None,
               size: Optional[int] = None, bold: Optional[bool] = None,
               layout: Optional[Layout] = None) -> Handle:
        """按钮。

        参数:
            parent (Handle): **显式**父容器。
            text (str): 按钮文本。
            command (Callable[[], None] | None): **无参**回调，在 **UI 线程**同步执行。
            width (int | None): 宽度；`None` 取 `Theme.button_default_width`。
            height (int | None): 高度；`None` 取 `Theme.button_default_height`。
            color (str | None): 文字颜色；`None` 取 `Theme.default_color`（**新增**）。
            family (str | None): 字体族；`None` 取 `Theme.default_family`（**新增**）。
            size (int | None): 字号；`None` 取 `Theme.label_default_size`（**新增**）。
            bold (bool | None): 是否加粗；`None` 取 `Theme.label_default_bold`（**新增**）。
            layout (Layout | None): 布局意图。
        返回: `Handle`。
        回调: `command()` 无参，UI 线程同步。
        同步性: 创建同步返回；回调在点击时同步触发。
        所有权: 句柄归 `parent` 所有。
        释放: 自身 `destroy()` 或 `parent` 销毁。
        逃生口: `handle.native`。
        异常: `InvalidParentError`、`RendererClosedError`。
        """

    @abstractmethod
    def input(self, parent: Handle, hint: str = '请输入', width: Optional[int] = None,
              family: Optional[str] = None, size: Optional[int] = None,
              bold: Optional[bool] = None,
              layout: Optional[Layout] = None) -> InputHandle:
        """单行输入框（带灰色占位提示）。

        参数:
            parent (Handle): **显式**父容器。
            hint (str): 占位提示文本；默认 `'请输入'`（首版 `input_box` 的默认值）。
            width (int | None): 宽度；`None` 取 `Theme` token。
            family (str | None): 字体族；`None` 取 `Theme` token。
            size (int | None): 字号；`None` 取 `Theme` token。
            bold (bool | None): 是否加粗；`None` 取 `Theme` token。
            layout (Layout | None): 布局意图。
        返回: `InputHandle`（`.value` 为 neutral `Value`）。
        回调: 无。
        同步性: 同步返回。
        所有权: 句柄与 `.value` 归 `parent` 所有。
        释放: 自身 `destroy()` 或 `parent` 销毁。
        逃生口: `handle.native`。
        异常: `InvalidParentError`、`RendererClosedError`。
        """

    @abstractmethod
    def text_area(self, parent: Handle, placeholder: str = '请输入文本...',
                  width: Optional[int] = None, height: Optional[int] = None,
                  layout: Optional[Layout] = None) -> TextAreaHandle:
        """带垂直滚动条的多行文本框。

        参数:
            parent (Handle): **显式**父容器。
            placeholder (str): 占位文本；默认 `'请输入文本...'`（首版默认值）。
            width (int | None): 宽度；`None` 取 `Theme` token。
            height (int | None): 行数/高度；`None` 取 `Theme` token。
            layout (Layout | None): 布局意图。
        返回: `TextAreaHandle`（`.value` 为 neutral `Value`）。
        回调: 无。
        同步性: 同步返回。
        所有权: 句柄与 `.value` 归 `parent` 所有。
        释放: 自身 `destroy()` 或 `parent` 销毁。
        逃生口: `handle.native`。
        异常: `InvalidParentError`、`RendererClosedError`。
        """

    # ------------------------------------------------------------------ #
    # 选择 / 数值控件（回调形状冻结）
    # ------------------------------------------------------------------ #
    @abstractmethod
    def checkbox(self, parent: Handle, text: str = '复选框', default: bool = False,
                 command: Optional[Callable[[], None]] = None,
                 layout: Optional[Layout] = None) -> CheckboxHandle:
        """复选框。

        参数:
            parent (Handle): **显式**父容器。
            text (str): 标签文本；默认 `'复选框'`（首版 `create_checkbox` 的默认值）。
            default (bool): 初值。
            command (Callable[[], None] | None): **无参**回调，在 **UI 线程**同步执行。
            layout (Layout | None): 布局意图。
        返回: `CheckboxHandle`（`.value` 为 neutral `Value`）。
        回调: `command()` **无参**。
        同步性: 创建同步返回；回调在状态改变时同步触发。
        所有权: 句柄与 `.value` 归 `parent` 所有。
        释放: 自身 `destroy()` 或 `parent` 销毁。
        逃生口: `handle.native`。
        异常: `InvalidParentError`、`RendererClosedError`。
        """

    @abstractmethod
    def radio_group(self, parent: Handle, options: Sequence[str], default: int = 0,
                    layout: Optional[Layout] = None) -> RadioGroupHandle:
        """单选组。

        参数:
            parent (Handle): **显式**父容器。
            options (Sequence[str]): 选项文本。
            default (int): 默认选中索引。
            layout (Layout | None): 布局意图。
        返回: `RadioGroupHandle`（`.value` 为选中索引）。
        回调: 无。
        同步性: 同步返回。
        所有权: 句柄与 `.value` 归 `parent` 所有。
        释放: 自身 `destroy()` 或 `parent` 销毁。
        逃生口: `handle.native`。
        异常: `InvalidParentError`、`RendererClosedError`。
        """

    @abstractmethod
    def progress(self, parent: Handle, max_value: float = 100,
                 width: Optional[int] = None,
                 layout: Optional[Layout] = None) -> ProgressHandle:
        """进度条（把原闭包返回值中性化为 `ProgressHandle.update(value)`）。

        参数:
            parent (Handle): **显式**父容器。
            max_value (float): 满值；`<= 0` 时 `value > 0` 视为满（首版语义）。
            width (int | None): 宽度；`None` 取 `Theme` token。
            layout (Layout | None): 布局意图。
        返回: `ProgressHandle`。
        回调: 无。
        同步性: 同步返回。
        所有权: 句柄归 `parent` 所有。
        释放: 自身 `destroy()` 或 `parent` 销毁。
        逃生口: `handle.native`。
        异常: `InvalidParentError`、`RendererClosedError`。
        """

    @abstractmethod
    def combo(self, parent: Handle, options: Sequence[str], default: Optional[str] = None,
              width: Optional[int] = None, editable: bool = True,
              on_select: Optional[Callable[[str], None]] = None,
              layout: Optional[Layout] = None) -> ComboHandle:
        """下拉框。

        参数:
            parent (Handle): **显式**父容器。
            options (Sequence[str]): 候选项。
            default (str | None): 初值；`None` 时为空。
            width (int | None): 宽度；`None` 取 `Theme` token。
            editable (bool): `False` 为只读。
            on_select (Callable[[str], None] | None): 收到**当前值字符串**，**UI 线程**同步执行。
            layout (Layout | None): 布局意图。
        返回: `ComboHandle`（`.value` 为 neutral `Value`）。
        回调: `on_select(current_value)`。
        同步性: 创建同步返回；回调在选择时同步触发。
        所有权: 句柄与 `.value` 归 `parent` 所有。
        释放: 自身 `destroy()` 或 `parent` 销毁。
        逃生口: `handle.native`。
        异常: `InvalidParentError`、`RendererClosedError`。
        """

    @abstractmethod
    def slider(self, parent: Handle, from_: float = 0, to: float = 100,
               default: Optional[float] = None, resolution: float = 1,
               width: Optional[int] = None, label: str = '',
               on_change: Optional[Callable[[float], None]] = None, show_value: bool = True,
               layout: Optional[Layout] = None) -> SliderHandle:
        """滑块。

        参数:
            parent (Handle): **显式**父容器。
            from_, to (float): 取值范围。
            default (float | None): 初值；`None` 时取 `from_`。
            resolution (float): 吸附步长。
            width (int | None): 宽度；`None` 取 `Theme` token。
            label (str): 左侧标签文本。
            on_change (Callable[[float], None] | None): 收到**数值**，**UI 线程**同步执行。
            show_value (bool): 是否显示右侧当前值。
            layout (Layout | None): 布局意图。
        返回: `SliderHandle`（`.value` 为 neutral `Value`）。
        回调: `on_change(value)`。
        同步性: 创建同步返回；回调在拖动时同步触发。
        所有权: 句柄与 `.value` 归 `parent` 所有。
        释放: 自身 `destroy()` 或 `parent` 销毁。
        逃生口: `handle.native`。
        异常: `InvalidParentError`、`RendererClosedError`。
        """

    @abstractmethod
    def spinbox(self, parent: Handle, from_: float = 0, to: float = 100,
                default: Optional[float] = None, step: float = 1,
                width: Optional[int] = None,
                command: Optional[Callable[[float], None]] = None,
                layout: Optional[Layout] = None) -> SpinboxHandle:
        """数字微调框。

        参数:
            parent (Handle): **显式**父容器。
            from_, to (float): 取值范围。
            default (float | None): 初值；`None` 时取 `from_`。
            step (float): 步长。
            width (int | None): 宽度；`None` 取 `Theme` token。
            command (Callable[[float], None] | None): 收到 `var.get()` 的值，**UI 线程**同步执行。
            layout (Layout | None): 布局意图。
        返回: `SpinboxHandle`（`.value` 为 neutral `Value`）。
        回调: `command(var.get())`。
        同步性: 创建同步返回；回调在值改变时同步触发。
        所有权: 句柄与 `.value` 归 `parent` 所有。
        释放: 自身 `destroy()` 或 `parent` 销毁。
        逃生口: `handle.native`。
        异常: `InvalidParentError`、`RendererClosedError`。
        """

    @abstractmethod
    def toggle(self, parent: Handle, text: str = '开关', default: bool = False,
               command: Optional[Callable[[bool], None]] = None,
               width: Optional[int] = None, height: Optional[int] = None,
               on_color: Optional[str] = None, off_color: Optional[str] = None,
               layout: Optional[Layout] = None) -> ToggleHandle:
        """开关。

        参数:
            parent (Handle): **显式**父容器。
            text (str): 标签文本；默认 `'开关'`（首版 `create_toggle_switch` 的默认值）；**空串 ⇒ 仍创建标签、内容为空字符串**（**裁决**；注意这与首版的 `if text:`（空串则不建标签）**不同**，属有意变更，已登记）。
            default (bool): 初值。
            command (Callable[[bool], None] | None): 收到 `bool`，**UI 线程**同步执行。
            width (int | None): 宽度；`None` 取 `Theme.toggle_default_width`。
            height (int | None): 高度；`None` 取 `Theme.toggle_default_height`。
            on_color (str | None): 开启色；`None` 取 `Theme.toggle_on`。
            off_color (str | None): 关闭色；`None` 取 `Theme.toggle_off`。
            layout (Layout | None): 布局意图。
        返回: `ToggleHandle`（`.value` 为 neutral `Value`）。
        回调: `command(bool)`。
        同步性: 创建同步返回；回调在切换时同步触发。
        所有权: 句柄与 `.value` 归 `parent` 所有。
        释放: 自身 `destroy()` 或 `parent` 销毁。
        逃生口: `handle.native`。
        异常: `InvalidParentError`、`RendererClosedError`。
        """

    # ------------------------------------------------------------------ #
    # 组合组件
    # ------------------------------------------------------------------ #
    @abstractmethod
    def searchable_list(self, parent: Handle, items: Sequence[str],
                        height: Optional[int] = None,
                        on_select: Optional[Callable[[str], None]] = None,
                        placeholder: str = '输入关键字过滤…',
                        layout: Optional[Layout] = None) -> ListHandle:
        """可搜索列表；支持 `set_items` 动态更新。

        参数:
            parent (Handle): **显式**父容器。
            items (Sequence[str]): 初始数据。
            height (int | None): 可视行数；`None` 取 `Theme` token。
            on_select (Callable[[str], None] | None): 收到选中项，**UI 线程**同步执行。
            placeholder (str): 过滤框占位文本；默认字面量 `'输入关键字过滤…'`，
               与首版 `create_searchable_list` 的默认值**逐字一致**（`接口合同`）。
                实现可自行改用等价 token `Theme.list_placeholder`（值相同）。
            layout (Layout | None): 布局意图。
        返回: `ListHandle`（含 `set_items` / `.value` / `.selection`）。
        回调: `on_select(item)`。
        同步性: 创建同步返回；回调在选中时同步触发。
        所有权: 句柄归 `parent` 所有。
        释放: 自身 `destroy()` 或 `parent` 销毁。
        逃生口: `handle.native`。
        异常: `InvalidParentError`、`RendererClosedError`。
        """

    @abstractmethod
    def table(self, parent: Handle, headers: Sequence[str],
              rows: Optional[Sequence[Sequence[Any]]] = None,
              height: Optional[int] = None, select_mode: str = 'browse',
              on_select: Optional[Callable[[Tuple[Any, ...], Any], None]] = None,
              column_widths: Optional[Sequence[int]] = None,
              layout: Optional[Layout] = None) -> TableHandle:
        """表格。

        参数:
            parent (Handle): **显式**父容器。
            headers (Sequence[str]): 列标题。
            rows (Sequence[Sequence[Any]] | None): 初始数据行。
            height (int | None): 可视行数；`None` 取 `Theme` token。
            select_mode (str): `'browse'`（单选）/ `'extended'`（多选）。
            on_select (Callable[[Tuple[Any, ...], Any], None] | None): 收到 `(行值 tuple, row_id)`；
                **`row_id` 是 backend 专属的不可解析标识**（Tk 是字符串 id，Qt 无等价物），
                base 标注为不透明 `Any`，调用方**不得**假定其类型或可解析性。**UI 线程**同步执行。
            column_widths (Sequence[int] | None): 各列宽度；`None` 时按内容估算。
            layout (Layout | None): 布局意图。
        返回: `TableHandle`（含 `set_rows` / `get_rows` / `.selection`）。
        回调: `on_select(tuple(row_values), row_id)`；`row_id` 不透明。
        同步性: 创建同步返回；回调在选中时同步触发。
        所有权: 句柄归 `parent` 所有。
        释放: 自身 `destroy()` 或 `parent` 销毁。
        逃生口: `handle.native`。
        异常: `InvalidParentError`、`RendererClosedError`。
        """

    @abstractmethod
    def form(self, parent: Handle, fields: Sequence[Any], width: Optional[int] = None,
             layout: Optional[Layout] = None) -> FormHandle:
        """智能表单。

        参数:
            parent (Handle): **显式**父容器。
            fields (Sequence[Any]): 每项 `(key, label, kind, *args)`；`kind` 见首版。
            width (int | None): 控件宽度；`None` 取 `Theme` token。
            layout (Layout | None): 布局意图。
        返回: `FormHandle`（含 `get_values` / `set_values`）。
        回调: 无。
        同步性: 同步返回。
        所有权: 句柄归 `parent` 所有。
        释放: 自身 `destroy()` 或 `parent` 销毁。
        逃生口: `handle.native`。
        异常: `InvalidParentError`、`RendererClosedError`。
        """

    @abstractmethod
    def notebook(self, parent: Handle, tabs: Sequence[Any],
                 height: Optional[int] = None, width: Optional[int] = None,
                 layout: Optional[Layout] = None) -> NotebookHandle:
        """选项卡。

        参数:
            parent (Handle): **显式**父容器。
            tabs (Sequence[Any]): 每项 `(title, content)`；`content` 可为 `None`、
               接收**句柄**的 callable、或句柄序列（首版的 callable 收的是 `tk.Frame`，
               属 Tk 泄漏，见）。
            height (int | None): 高度；`None` 取 `Theme` token。
            width (int | None): 宽度；`None` 取 `Theme` token。
            layout (Layout | None): 布局意图。
        返回: `NotebookHandle`（含 `tabs()` / `select()`）。
        回调: 无。
        同步性: 同步返回。
        所有权: 句柄归 `parent` 所有。
        释放: 自身 `destroy()` 或 `parent` 销毁。
        逃生口: `handle.native`。
        异常: `InvalidParentError`、`RendererClosedError`。
        """

    # ------------------------------------------------------------------ #
    # 容器 / 装饰 / 图表
    # ------------------------------------------------------------------ #
    @abstractmethod
    def toolbar(self, parent: Handle, items: Optional[Sequence[Any]] = None) -> Handle:
        """工具栏。

        参数:
            parent (Handle): **显式**父容器（首版的隐式 `toolbar_container`
                不进本层；实现内部可自行决定挂载位置，但**必须**以 `parent` 为准）。
            items (Sequence[Any] | None): 每项 `(text, command, kind[, menu_items])`。
        返回: `Handle`。
        回调: 按钮/菜单项回调为**无参**，在 **UI 线程**同步执行。
        同步性: 注册同步返回。
        所有权: 句柄归 `parent` 所有。
        释放: 自身 `destroy()` 或 `parent` 销毁。
        逃生口: `handle.native`。
        异常: `InvalidParentError`、`RendererClosedError`。
        """

    @abstractmethod
    def status_bar(self, parent: Handle, initial_text: str = 'Ready') -> StatusBarHandle:
        """状态栏。

        参数:
            parent (Handle): **显式**父容器（首版的隐式 `statusbar_container`
                不进本层）。
            initial_text (str): 初始文本；默认 `'Ready'`（首版默认值）。
        返回: `StatusBarHandle`（含 `set_status`）。
        回调: 无。
        同步性: 同步返回。
        所有权: 句柄归 `parent` 所有。
        释放: 自身 `destroy()` 或 `parent` 销毁。
        逃生口: `handle.native`。
        异常: `InvalidParentError`、`RendererClosedError`。
        """

    @abstractmethod
    def scrollable(self, parent: Handle, width: Optional[int] = None,
                   height: Optional[int] = None, background: Optional[str] = None,
                   layout: Optional[Layout] = None) -> ScrollableHandle:
        """垂直可滚动区域。

        参数:
            parent (Handle): **显式**父容器。
            width (int | None): 可视宽度；`None` 取 `Theme` token。
            height (int | None): 可视高度；`None` 取 `Theme` token。
            background (str | None): 背景色；`None` 取 `Theme` token。
            layout (Layout | None): 布局意图。
        返回: `ScrollableHandle`（`.content` 为内容容器）。
        回调: 无。
        同步性: 同步返回。
        所有权: 句柄归 `parent` 所有。
        释放: 自身 `destroy()` 或 `parent` 销毁。
        逃生口: `handle.native`。
        异常: `InvalidParentError`、`RendererClosedError`。
        """

    @abstractmethod
    def visualization_canvas(self, parent: Handle, width: Optional[int] = None,
                             height: Optional[int] = None, background: Optional[str] = None,
                             layout: Optional[Layout] = None) -> ScrollableHandle:
        """水平可滚动可视化画布。

        参数:
            parent (Handle): **显式**父容器。
            width (int | None): 可视宽度；`None` 取 `Theme` token。
            height (int | None): 可视高度；`None` 取 `Theme` token。
            background (str | None): 背景色；`None` 取 `Theme` token。
            layout (Layout | None): 布局意图。
        返回: `ScrollableHandle`（`.content` 为绘图内容容器）。
        回调: 无。
        同步性: 同步返回。
        所有权: 句柄归 `parent` 所有。
        释放: 自身 `destroy()` 或 `parent` 销毁。
        逃生口: `handle.native`。
        异常: `InvalidParentError`、`RendererClosedError`。
        """

    @abstractmethod
    def labels(self, parent: Handle, data: Optional[Sequence[str]] = None,
               background: Optional[str] = None, label_background: Optional[str] = None,
               label_color: Optional[str] = None, height: Optional[int] = None,
               layout: Optional[Layout] = None) -> Handle:
        """可滚动标签列表。

        参数:
            parent (Handle): **显式**父容器。
            data (Sequence[str] | None): 数据；空/`None` 时使用主题里的默认占位标签。
            background (str | None): 画布背景；`None` 取 `Theme.labels_background`。
            label_background (str | None): 标签背景；`None` 取 `Theme.labels_label_background`。
            label_color (str | None): 标签文字色；`None` 取 `Theme.labels_label_color`。
            height (int | None): 高度；`None` 取 `Theme.labels_default_height`。
            layout (Layout | None): 布局意图。
        返回: `Handle`。
        回调: 无。
        同步性: 同步返回。
        所有权: 句柄归 `parent` 所有。
        释放: 自身 `destroy()` 或 `parent` 销毁。
        逃生口: `handle.native`。
        异常: `InvalidParentError`、`RendererClosedError`。
        """

    @abstractmethod
    def bars(self, parent: Handle, data: Optional[Sequence[float]] = None,
             canvas_width: Optional[int] = None, canvas_height: Optional[int] = None,
             background: Optional[str] = None, min_bar_width: Optional[int] = None,
             padding: Optional[int] = None, label_rotation: int = 0,
             show_bg_stripes: bool = True, bar_colors: Optional[Sequence[str]] = None,
             layout: Optional[Layout] = None) -> Optional[Handle]:
        """柱状图。

        参数:
            parent (Handle): **显式**父容器。
            data (Sequence[float] | None): 数据；**空数据返回 `None`**（首版语义，冻结）。
            canvas_width / canvas_height (int | None): 画布尺寸；`None` 取 `Theme` token。
            background (str | None): 背景色；`None` 取 `Theme` token。
            min_bar_width (int | None): 柱最小宽度；`None` 取 `Theme` token。
            padding (int | None): 内边距；`None` 取 `Theme` token。
            label_rotation (int): 数值标签旋转角度。
            show_bg_stripes (bool): 是否绘制背景条纹。
            bar_colors (Sequence[str] | None): 调色板；`None` 时按索引生成渐变。
            layout (Layout | None): 布局意图。
        返回: `Handle`；空 `data` 返回 `None`（"无数据"语义）。
        回调: 无。
        同步性: 同步返回。
        所有权: 句柄归 `parent` 所有。
        释放: 自身 `destroy()` 或 `parent` 销毁。
        逃生口: `handle.native`。
        异常: `InvalidParentError`、`RendererClosedError`。
        """

    def clock(self, parent: Handle, layout: Optional[Layout] = None) -> ClockHandle:
        """每秒刷新的时钟。

        参数:
            parent (Handle): **显式**父容器。首版的 `create_clock(self)` 无参、挂在
               隐式容器上；按显式 parent 规则放宽为必填 `parent`。
            layout (Layout | None): 布局意图。
       返回: `ClockHandle`（含 `cancel()`；不改变首版的"返回时钟 label"语义）。
        回调: 无。
        同步性: 同步返回；刷新由 backend 定时器驱动。
        所有权: 句柄归 `parent` 所有。
        释放: `ClockHandle.cancel()` 或 `destroy()`。
        逃生口: `handle.native`。
        异常: `InvalidParentError`、`RendererClosedError`。

        **实现归属**：本方法**由 base 一次实现** ——
        `label` 建控件 + `schedule` 驱动 + `LabelHandle.set_text` 写文本；两 backend 同时获得，
       三态为 `base-green`。
        **token 消费（5/5）**：`clock`(字体族/字号) · `clock_color` · `clock_ms`(间隔) ·
        `clock_format`(格式) · `clock_y`(纵向间距，作为默认 `Layout.pack(pady=…)`)。
        **新手友好**：`clock(parent)` 零配置即出一个每秒自走的时钟；`handle.cancel()` 停止。
        """
        self._ensure_alive()
        theme = self.theme
        family, size = theme.clock
        label = self.label(parent, "", color=theme.clock_color,
                           family=family, size=size, bold=False)
        # 纵向间距：调用方给了 layout 就用它；否则用 token `clock_y`（首版的 pady）
        label.layout(layout if layout is not None else Layout.pack(pady=theme.clock_y))
        return _NeutralClockHandle(self, label, theme.clock_ms, theme.clock_format)

    def tooltip(self, target: Handle, text: str,
                delay_ms: Optional[int] = None) -> TooltipHandle:
        """给控件挂提示气泡。

        参数:
            target (Handle): **显式**目标控件句柄（tooltip 的"父"）。
            text (str): 提示文本。
            delay_ms (int | None): 延迟毫秒；`None` 取 `Theme` token。
        返回: `TooltipHandle`。
        回调: 无。
        同步性: 注册同步返回。
        所有权: 句柄归 `target` 所有。
        释放: 自身 `destroy()` 或 `target` 销毁。
        逃生口: `handle.native`。
        异常: 默认实现抛 `NotSupportedError`；target 非法抛 `InvalidParentError`。
        """
        raise NotSupportedError('tooltip 未被该 backend 实现')

    # ------------------------------------------------------------------ #
    # 对话框与提示
    # ------------------------------------------------------------------ #
    @abstractmethod
    def message(self, title: str, text: str, kind: str = 'info') -> None:
        """同步消息框。

        参数:
            title (str): 标题。
            text (str): 正文。
            kind (str): `'info'/'warning'/'error'`；未知取值**不动作**（首版语义）。
        返回: `None`。
        回调: 无。
        同步性: **阻塞**直到用户关闭。
        所有权: 无所有权变更。
        释放: 由 backend 自行释放。
        逃生口: 无。
        异常: Renderer 已销毁时抛 `RendererClosedError`。
        """

    @abstractmethod
    def ask_input(self, title: str = '输入', prompt: str = '请输入:',
                  default: str = '') -> Optional[str]:
        """**同步**文本输入框。

        参数:
            title (str): 标题。
            prompt (str): 提示文本。
            default (str): 默认值。
        返回: `str`；取消/关闭返回 `None`（"取消"语义，冻结）。
        回调: 无。
        同步性: **阻塞**直到用户确认或取消；Qt 侧须以局部事件循环实现同步语义。
        所有权: 无所有权变更。
        释放: 由 backend 自行释放。
        逃生口: 无。
        异常: Renderer 已销毁时抛 `RendererClosedError`。
        """

    @abstractmethod
    def ask_save_path(self, title: str = '保存文件', defaultextension: str = '.csv',
                      filetypes: Optional[Sequence[Tuple[str, str]]] = None) -> Optional[str]:
        """**同步**保存路径选择。

        参数:
            title (str): 对话框标题。
            defaultextension (str): 默认扩展名。
            filetypes (Sequence[Tuple[str, str]] | None): `(描述, 通配)` 列表。
       返回: `str`；取消返回 `None`（首版上游也可能返回空串，语义同）。
        回调: 无。
        同步性: **阻塞**直到用户确认或取消。
        所有权: 无所有权变更。
        释放: 由 backend 自行释放。
        逃生口: 无。
        异常: Renderer 已销毁时抛 `RendererClosedError`。
        """

    @abstractmethod
    def ask_open_path(self, title: str = '选择文件',
                      filetypes: Optional[Sequence[Tuple[str, str]]] = None) -> Optional[str]:
        """**同步**文件选择。

        参数:
            title (str): 对话框标题。
            filetypes (Sequence[Tuple[str, str]] | None): `(描述, 通配)` 列表。
        返回: `str`；取消返回 `None`。
        回调: 无。
        同步性: **阻塞**直到用户确认或取消。
        所有权: 无所有权变更。
        释放: 由 backend 自行释放。
        逃生口: 无。
        异常: Renderer 已销毁时抛 `RendererClosedError`。
        """

    @abstractmethod
    def ask_directory(self, title: str = '选择目录') -> Optional[str]:
        """**同步**目录选择。

        参数:
            title (str): 对话框标题。
        返回: `str`；取消返回 `None`。
        回调: 无。
        同步性: **阻塞**直到用户确认或取消。
        所有权: 无所有权变更。
        释放: 由 backend 自行释放。
        逃生口: 无。
        异常: Renderer 已销毁时抛 `RendererClosedError`。
        """

    @abstractmethod
    def report_window(self, title: str, text: str) -> Handle:
        """只读文本报告窗口（首版的 `show_image_report`）。

        只负责**展示**；报告内容由数据层（`utils/apng.py`）生成，不属于 renderer。

        **顶层部件**：与对话框同类，由 `Renderer` 自己拥有，**不接受** `parent`
        （见 `Renderer` 类文档"顶层部件 vs 子控件"结论）。

        参数:
            title (str): 窗口标题。
            text (str): 只读正文。
        返回: `Handle`。
        回调: 无。
        同步性: 同步返回（不阻塞）。
        所有权: 句柄归本 Renderer 所有。
        释放: 自身 `destroy()` 或 `Renderer.destroy()`。
        逃生口: `handle.native`。
        异常: Renderer 已销毁时抛 `RendererClosedError`。
        """

    @abstractmethod
    def toast(self, text: str, duration_ms: Optional[int] = None, kind: str = 'info') -> None:
        """非阻塞浮层提示。

        参数:
            text (str): 提示文本。
            duration_ms (int | None): 持续时间；`None` 取 `Theme` token。
            kind (str): `'info'/'success'/'warning'/'error'`；未知回退 `info`。
        返回: `None`。
        回调: 无。
        同步性: **非阻塞**，立即返回。
        所有权: 浮层由 backend 自行管理。
        释放: 由 backend 在 `duration_ms` 后自行释放。
        逃生口: 无。
        异常: Renderer 已销毁时抛 `RendererClosedError`。
        """

    def file_button(self, parent: Handle, text: str = '选择文件',
                    file_types: Optional[Sequence[Tuple[str, str]]] = None,
                    layout: Optional[Layout] = None) -> Handle:
        """"选择文件"按钮（首版的 `create_file_dialog`）。

        参数:
            parent (Handle): **显式**父容器。
            text (str): 按钮文本。
            file_types (Sequence[Tuple[str, str]] | None): 过滤类型。
            layout (Layout | None): 布局意图。
        返回: `Handle`。
        回调: 点击后在 **UI 线程**同步调用 `ask_open_path`。
        同步性: 创建同步返回；点击回调内部会阻塞于文件对话框。
        所有权: 句柄归 `parent` 所有。
        释放: 自身 `destroy()` 或 `parent` 销毁。
        逃生口: `handle.native`。
        异常: `InvalidParentError`、`RendererClosedError`。

        **实现归属（(b)）**：本方法**由 base 一次实现**（`button` + `ask_open_path`
       两个已抽象的 neutral 原语组合），两个 backend 同时获得；里对应行的三态为
        `base-green`（renderer 不覆盖 + base 体是真实实现）。
        """
        def _pick():
            """点击 ⇒ 调 `ask_open_path`（**阻塞**在文件对话框）；取消 ⇒ 不动作。

           首版的 `create_file_dialog` 把选中路径 `print` 出来并由**内部 callback** 返回，
            外部拿不到；本层保持"只调 `ask_open_path`"的最小语义，返回值**不**外泄，
           需要路径的调用方应直接用 `ask_open_path`（见 报告"边界"一节）。
            """
            self.ask_open_path(filetypes=file_types)

        return self.button(parent, text, command=_pick, layout=layout)

    def message_button(self, parent: Handle, title: str, text: str, kind: str = 'info',
                       layout: Optional[Layout] = None) -> Handle:
        """点击后弹消息框的按钮（首版的 `create_message_box`）。

        参数:
            parent (Handle): **显式**父容器。
            title (str): 消息框标题。
            text (str): 消息正文。
            kind (str): `'info'/'warning'/'error'`。
            layout (Layout | None): 布局意图。
        返回: `Handle`。
        回调: 点击后在 **UI 线程**同步调用 `message()`（阻塞）。
        同步性: 创建同步返回；点击回调阻塞。
        所有权: 句柄归 `parent` 所有。
        释放: 自身 `destroy()` 或 `parent` 销毁。
        逃生口: `handle.native`。
        异常: `InvalidParentError`、`RendererClosedError`。

        **实现归属（(b)）**：本方法**由 base 一次实现**（`button` + `message`），
        按钮文本取 token `dialog_message_button_template`（`'显示{msg_type}消息'`）；
       三态为 `base-green`。
        """
        kind_low = (kind or 'info').lower()
        label = str(self.theme.dialog_message_button_template).format(msg_type=kind_low)
        # 未知 kind：首版的"未知类型无动作"由 `message()` 自身保证（本层不预判、不吞错）
        return self.button(parent, label,
                           command=lambda: self.message(title, text, kind_low),
                           layout=layout)

    # ------------------------------------------------------------------ #
    # 媒体（Pillow 可选）
    # ------------------------------------------------------------------ #
    def photo(self, parent: Handle, path: str, text: str = '',
              color: Optional[str] = None, family: Optional[str] = None,
              size: Optional[int] = None, bold: Optional[bool] = None,
              frame: int = 0, warn_animated: bool = True,
              layout: Optional[Layout] = None) -> Optional[MediaHandle]:
        """显示静态图（可取 APNG/GIF 的某一帧）。

        参数:
            parent (Handle): **显式**父容器。
            path (str): 图片路径。
            text (str): 说明文字。
            color / family / size / bold: 文字样式；`None` 取 `Theme` token。
            frame (int): 显示第几帧。
            warn_animated (bool): 多帧文件是否提示。
            layout (Layout | None): 布局意图。
       返回: `MediaHandle`；**无 Pillow / 文件不存在 / 失败 → `None`**（首版语义，冻结）。
        回调: 无。
        同步性: 同步返回（解码阻塞）。
        所有权: 句柄归 `parent` 所有。
        释放: 自身 `destroy()` 或 `parent` 销毁。
        逃生口: `handle.native`。
        异常: 默认实现抛 `NotSupportedError`；`InvalidParentError`、`RendererClosedError`。
        """
        raise NotSupportedError('photo 未被该 backend 实现')

    def animation(self, parent: Handle, path: str, text: str = '',
                  color: Optional[str] = None, family: Optional[str] = None,
                  size: Optional[int] = None, bold: Optional[bool] = None,
                  start: int = 0, max_frames: Optional[int] = None,
                  max_loops: Optional[int] = None,
                  on_frame: Optional[Callable[[int, int], None]] = None,
                  frame_delay: Optional[int] = None,
                  layout: Optional[Layout] = None) -> AnimationHandle:
        """播放 GIF/APNG/动态 WebP。

        **失败哨兵（冻结）**：首版的 `animation(...)` 返回 `int` 帧数，失败 / 无 Pillow
        返回 `0`。本层把返回句柄中性化，但**不得**把哨兵改成 `None`：
        **本方法永不返回 `None`**；失败时返回的句柄其 `frame_count == 0`。

        参数:
            parent (Handle): **显式**父容器。
            path (str): 动画文件路径。
            text (str): 说明文字。
            color / family / size / bold: 文字样式；`None` 取 `Theme` token。
            start (int): 起始帧。
            max_frames (int | None): 最大帧数；`None` 为不限。
            max_loops (int | None): 最大循环轮数；`None` 为不限。
            on_frame (Callable[[int, int], None] | None): 收到 `(frame_index, total_frames)`，
                **UI 线程**同步执行。
            frame_delay (int | None): 帧延时覆盖；`None` 用文件自带延时。
            layout (Layout | None): 布局意图。
        返回: `AnimationHandle`（**永不 `None`**）；失败时 `frame_count == 0`。
        回调: `on_frame(frame_index, total_frames)`。
        同步性: 注册同步返回；播放由 backend 定时器驱动。
        所有权: 句柄归 `parent` 所有。
        释放: `AnimationHandle.stop()`、自身 `destroy()` 或 `parent` 销毁。
        逃生口: `handle.native`。
        异常: 默认实现抛 `NotSupportedError`；`InvalidParentError`、`RendererClosedError`。
        """
        raise NotSupportedError('animation 未被该 backend 实现')

    def frame_preview(self, parent: Handle, path: str, columns: int = 3,
                      thumb_width: Optional[int] = None, labels: bool = True,
                      max_frames: Optional[int] = None,
                      layout: Optional[Layout] = None) -> Optional[Handle]:
        """逐帧缩略图预览（首版的 `show_frames`）。

        参数:
            parent (Handle): **显式**父容器。
            path (str): 动画文件路径。
            columns (int): 网格列数；**计数**而非像素，属首版语义默认值。
            thumb_width (int | None): 缩略图宽度（**像素**）——像素值不得在 base 硬编码，
                `None` 时必须由实现的 `Theme` token 提供：`Theme.media_thumb_width`
                （已在 `接口合同` 登记为 `media.thumb_width`，值 `240`，
                出处 `gui/media.py:402`）。
            labels (bool): 是否显示帧标签。
            max_frames (int | None): 最大帧数；`None` 为不限。
            layout (Layout | None): 布局意图。
       返回: `Handle`；无路径 / Pillow 缺失 → `None`（首版语义，冻结）。
        回调: 无。
        同步性: 同步返回（解码阻塞）。
        所有权: 句柄归 `parent` 所有。
        释放: 自身 `destroy()` 或 `parent` 销毁。
        逃生口: `handle.native`。
        异常: 默认实现抛 `NotSupportedError`；`InvalidParentError`、`RendererClosedError`。
        """
        raise NotSupportedError('frame_preview 未被该 backend 实现')

    def clear_media(self) -> None:
        """停止动画、取消定时器、销毁媒体控件并清空引用。

        参数: 无。
        返回: `None`。
        回调: 不再触发 `on_frame`。
        同步性: 同步返回。
        所有权: 释放全部媒体句柄（其后操作抛 `RendererClosedError`）。
        释放: 本方法即释放责任方。
        逃生口: 无。
        异常: 默认实现抛 `NotSupportedError`；Renderer 已销毁时抛 `RendererClosedError`。
        """
        raise NotSupportedError('clear_media 未被该 backend 实现')

    # ------------------------------------------------------------------ #
    # 布局辅助（用 base 自身能力实现，证明接口表达力足够）
    # ------------------------------------------------------------------ #
    def pack_vertical(self, parent: Handle, *widgets: Optional[Handle],
                      padx: Optional[int] = None,
                      pady: Optional[int] = None) -> Handle:
        """把若干控件纵向排列在新建的容器中（请求该容器接管其几何），并返回该容器。

        参数:
            parent (Handle): **显式**父容器。
            *widgets (Handle | None): 待排列句柄；`None` 项跳过。
                **前置条件**：每项的 parent 必须就是 `parent`，或 `parent` 的
                **祖先** —— 新容器是 `parent` 的子控件，须落在该项 parent 的子树内
                （Tk 的 `-in` 硬性要求）。base 无法校验（`Handle` 不暴露 parent），
                越界时由 backend 抛 `NotSupportedError`（Tk 适配层即
                `TclError: can't pack … inside …` 的等价包装）。
            padx / pady (int | None): 间距；`None` 时取 `Theme.layout_pack_vertical`。
        返回: `Handle`（新容器）。
        回调: 无。
        同步性: 同步返回。
       所有权: 返回容器归 `parent` 所有。传入句柄的**权属由 backend 决定**：
            本方法只保证"请求返回容器接管其几何"；是否改变 parent/所有权取决于 backend
            （Tk 不改、Qt 必改）。**调用方不得假定**，请用 `Handle.exists()` 探测。
        释放: 返回容器 `destroy()`；传入句柄**是否随之失效由 backend 决定**（Tk：不失效；
            Qt：失效）。**调用方必须先 `exists()` 探测再使用**，不得假定仍然可用。
        逃生口: `handle.native`。
        异常: `InvalidParentError`（parent 非法）、`RendererClosedError`（Renderer/parent
            已销毁）、`NotSupportedError`（backend 无法接管该几何归属，如目标容器与
            主体不同源）。
        """
        self._ensure_alive()
        self._validate_parent(parent)
        box = self.container(parent, Layout.pack(fill='x'))
        for w in widgets:
            if w is not None:
                gapx = padx if padx is not None else self.theme.layout_pack_vertical[0]
                gapy = pady if pady is not None else self.theme.layout_pack_vertical[1]
                w.layout(Layout.pack(side='top', padx=gapx, pady=gapy, into=box))
        return box

    def pack_in_grid(self, parent: Handle, widgets_2d: Sequence[Sequence[Optional[Handle]]],
                     padx: Optional[int] = None, pady: Optional[int] = None,
                     col_weights: Optional[Sequence[int]] = None) -> Handle:
        """把二维控件按网格排列在新建的容器中（请求该容器接管其几何），并返回该容器。

        参数:
            parent (Handle): **显式**父容器。
            widgets_2d (Sequence[Sequence[Handle | None]]): 二维；空合法。
               各项 **前置条件** 同 `pack_vertical`：其 parent 必须就是 `parent`
                或 `parent` 的祖先，否则 backend 抛 `NotSupportedError`。
            padx / pady (int | None): 间距；`None` 时取 `Theme.layout_grid`。
            col_weights (Sequence[int] | None): 列权重；`None` 时各列等权。
                经 `Renderer.container(col_weights=…)` 施加到**返回容器自身**的网格上
                （与首版 `container.grid_columnconfigure(i, weight=w)` 等价）。
                **起真正生效**：容器自身在 `parent` 中仍走顺序流（不变），但内部网格的
                列权重**不再因为"自身不是网格"而被丢弃**（修前实测：`[3,1]` ⇒ `[0,0]`）。
        返回: `Handle`（新容器）。
        回调: 无。
        同步性: 同步返回。
       所有权: 返回容器归 `parent` 所有。传入句柄的**权属由 backend 决定**：
            本方法只保证"请求返回容器接管其几何"；是否改变 parent/所有权取决于 backend
            （Tk 不改、Qt 必改）。**调用方不得假定**，请用 `Handle.exists()` 探测。
        释放: 返回容器 `destroy()`；传入句柄**是否随之失效由 backend 决定**（Tk：不失效；
            Qt：失效）。**调用方必须先 `exists()` 探测再使用**，不得假定仍然可用。
        逃生口: `handle.native`。
        异常: `InvalidParentError`、`RendererClosedError`、`NotSupportedError`（几何归属
            无法接管，或 backend 无法设置 `col_weights`）。
        """
        self._ensure_alive()
        self._validate_parent(parent)
        gapx = padx if padx is not None else self.theme.layout_grid[0]
        gapy = pady if pady is not None else self.theme.layout_grid[1]
        box = self.container(parent, col_weights=col_weights)
        for r, row in enumerate(widgets_2d):
            for c, w in enumerate(row):
                if w is not None:
                    w.layout(Layout.grid(row=r, column=c, sticky='nsew',
                                         padx=gapx, pady=gapy, into=box))
        return box

    def center_widget(self, parent: Handle, widget: Optional[Handle],
                      pady: Optional[int] = None) -> Optional[Handle]:
        """把单个控件水平居中（请求新建的容器接管其几何）。

        参数:
            parent (Handle): **显式**父容器。
            widget (Handle | None): 待居中句柄；`None` 时返回 `None`（首版语义，冻结）。
               其 parent 必须就是 `parent`，或 `parent` 的祖先（**前置条件**，；
                同 `pack_vertical`），否则 backend 抛 `NotSupportedError`。
            pady (int | None): 垂直间距；`None` 时取 `Theme.layout_center`。
        返回: `Handle`（新容器）；`widget` 为 `None` 时返回 `None`。
        回调: 无。
        同步性: 同步返回。
       所有权: 返回容器归 `parent` 所有。`widget` 的**权属由 backend 决定**：
            本方法只保证"请求返回容器接管其几何"；是否改变 parent/所有权取决于 backend
            （Tk 不改、Qt 必改）。**调用方不得假定**，请用 `Handle.exists()` 探测。
        释放: 返回容器 `destroy()`；`widget` **是否随之失效由 backend 决定**（Tk：不失效；
            Qt：失效）。**调用方必须先 `exists()` 探测再使用**，不得假定仍然可用。
        逃生口: `handle.native`。
        异常: `InvalidParentError`、`RendererClosedError`、`NotSupportedError`（几何归属
            无法接管）。
        """
        self._ensure_alive()
        self._validate_parent(parent)
        if widget is None:
            return None
        gap = self.theme.layout_center if pady is None else pady
        box = self.container(parent, Layout.pack(fill='x'))
        widget.layout(Layout.pack(side='top', pady=gap, into=box))
        return box
