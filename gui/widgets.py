# gui/widgets.py
import tkinter as tk

try:                                    # 脚本模式：cwd = 项目根，gui 为顶层包
    from ck1_0.core.theme import Theme
    from ck1_0.renderer.base import Layout, NotSupportedError, Renderer, RendererError
except ImportError:                     # 包模式：本文件即 ck1_0.gui.widgets
    from ..core.theme import Theme
    from ..renderer.base import Layout, NotSupportedError, Renderer, RendererError


def _renderer_of(host):
    """取宿主正在用的 Renderer。

    先看宿主自己的 `_renderer`（`Btk` 持有），否则退回进程单例 `Renderer.current()`
    （`_DemoCtx` 这类只转发属性的宿主也走这一支）。取不到就**说人话**地报错，不静默。
    """
    r = getattr(host, '_renderer', None) or Renderer.current()
    if r is None:
        raise RendererError(
            '这里需要一个正在运行的 Renderer 才能创建控件：请先构造 MainWindow/Btk'
            '（或经 ck1_0.renderer.select 选择 backend），再调用本方法。')
    return r


def _content_parent(host):
    """取 facade 的**中立父容器 Handle**。

    ① 宿主已登记 `_content`（`Btk` 在 `__init__` 里把既有 `scrollable_frame` 包好）⇒ 直接用；
    ② 否则把宿主的原生 `scrollable_frame` **现包一次**（同一机制，供只有原生容器的宿主）；
    ③ 都没有 ⇒ 报错说人话。
    """
    h = getattr(host, '_content', None)
    if h is not None:
        return h
    frame = getattr(host, 'scrollable_frame', None)
    if frame is None:
        raise RendererError('宿主既没有中立内容容器 `_content`，也没有 `scrollable_frame`，'
                            '无法确定控件该放在哪里。')
    return type(_renderer_of(host).root)(frame)


class WidgetMixin:
    def __init__(self):
        # minimal initializer to be safe when used in multiple inheritance
        # 不要覆盖已有属性，仅确保属性存在占位值
        if not hasattr(self, 'scrollable_frame'):
            self.scrollable_frame = None
        if not hasattr(self, 'root'):
            self.root = None
        # 语义 token 表：优先沿用宿主已有的 theme（Btk 先于本 mixin 建立），否则用基线主题
        if not hasattr(self, 'theme'):
            self.theme = Theme.light()

    def buttonx(self, btname='button', widthx=15, heightx=2, ifzf=True, wstr1='点按钮 ', wstr2='已经点击 ', commandname=None, feedback_id=None):
        # 改走 renderer。**本方法的说明书**：「`ifzf` 组合留应用层＝
        # `button` + `schedule`」—— 反馈标签用 `label` + `LabelHandle.set_text`，
        # 1000ms 复位用 `schedule`（中立定时器，替代首版的 `root.after`）。
        # **裁决的次序照旧**：改文案 → 排定复位 → **立即**调用 `commandname()`。
        r = _renderer_of(self)
        parent = _content_parent(self)

        # 懒初始化计数器和标签字典（安全兼容多重继承）
        if not hasattr(self, '_button_counter'):
            self._button_counter = 0
        if not hasattr(self, '_feedback_labels'):
            self._feedback_labels = {}

        # 生成唯一 ID
        if feedback_id is None:
            btn_id = f"btn_{self._button_counter}"
            self._button_counter += 1
        else:
            btn_id = str(feedback_id)

        if ifzf:
            # 获取或创建该按钮对应的反馈标签（只创建一次）
            if btn_id not in self._feedback_labels:
                label = r.label(parent, wstr1)
                # `label()` 自带 `pady=label_y`；反馈标签按 `feedback_y` 重排
                label.layout(Layout.pack(pady=self.theme.feedback_y))
                self._feedback_labels[btn_id] = label
            feedback_label = self._feedback_labels[btn_id]

            def bclick():
                feedback_label.set_text(wstr2)
                r.schedule(self.theme.feedback_reset_ms,
                           lambda: feedback_label.set_text(wstr1))
                if commandname:
                    commandname()
        else:
            # 不需要反馈提示
            def bclick():
                if commandname:
                    commandname()

        # 创建并返回按钮（`button()` 不自带布局 ⇒ 按 `button_y` 排一次）
        b = r.button(parent, btname, command=bclick, width=widthx, height=heightx)
        b.layout(Layout.pack(pady=self.theme.button_y))
        return b

    def input_box(self, hint='请输入', wbox=30, hbox=10, pbox=10, ipbox=0, tzt='Microsoft YaHei', tsize=15, tblod=True):
        # 改走 renderer：占位符/焦点语义由中立层给（已与首版逐行对齐）。
        # 参数映射：`wbox→width` · `tzt/tsize/tblod→family/size/bold` · `pbox→pady`（经再布局兑现）。
        # `hbox` 在首版本就**未用于几何**（接口合同），照旧忽略。
        # `ipbox`（Tk 的 `ipady` 内边距）在**中立层没有对应能力**（`Layout` 只有 padx/pady）⇒
        # 传非默认值时**显式拒绝**，并在错误里说清替代做法。
        if ipbox:
            raise NotSupportedError(
                'input_box: 参数 ipbox（输入框内部上下留白）在本版的中立层没有对应能力，'
                '无法在 Tk/Qt 上给出同一语义；请改用默认值 0，或用 layout 的 pady 调外部间距。')
        r = _renderer_of(self)
        self.entry = r.input(_content_parent(self), hint=hint, width=wbox,
                             family=tzt, size=tsize, bold=tblod)
        if pbox != self.theme.input_y:
            self.entry.layout(Layout.pack(pady=pbox))
        return self.entry

    def label_ck(self, label_text, tcolor='#000000', tzt='Microsoft YaHei', tsize=20, tblod=True):
        # 改走 renderer：结构/字体/pady 全由中立层给（`compound="top"` 与
        # `pady=theme.label_y` 与首版逐字一致）；`tsize/tblod` **显式透传** ⇒
        # 的"标题仍 20/粗体"在这里生效（正文 label 的 12/非粗体默认不受影响）。
        # 返回**中立句柄**（不再是 `tk.Label`）；需要原生控件时用逃生口 `.native`。
        return _renderer_of(self).label(_content_parent(self), label_text, color=tcolor,
                                        family=tzt, size=tsize, bold=tblod)