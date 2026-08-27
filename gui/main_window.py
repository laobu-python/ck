# gui/main_window.py
from .window import Btk
from .widgets import WidgetMixin
from .media import MediaMixin
from .dialogs import DialogMixin
from .advanced_widgets import AdvancedWidgetMixin
from .theme import ThemeMixin

class MainWindow(Btk, WidgetMixin, MediaMixin, DialogMixin, AdvancedWidgetMixin, ThemeMixin):
    def __init__(self, name='窗口', sizex=800, sizey=800):
        # 初始化 Btk (即 Tk 窗口)
        super().__init__(name, sizex, sizey)

        # 统一初始化 mixin：以安全方式调用每个 mixin 的 __init__（若存在）
        self._init_mixins([WidgetMixin, MediaMixin, DialogMixin, AdvancedWidgetMixin, ThemeMixin])

    def _init_mixins(self, mixin_list):
        """按顺序初始化传入的 mixin 类的 __init__ 方法（若存在）。

        这样可以在多重继承场景下保持初始化一致性，且对缺失或不同签名的 __init__ 做容错。
        """
        for mixin in mixin_list:
            init = getattr(mixin, '__init__', None)
            if not init:
                continue
            try:
                # 以 mixin.__init__(self) 的形式调用
                init(self)
            except TypeError:
                # 如果签名不同，尝试不传参数（有些 mixin 可能定义了 no-arg init）
                try:
                    init()
                except Exception:
                    # 忽略初始化错误，避免阻塞窗口创建
                    pass
            except Exception:
                # 忽略其它初始化异常
                pass

    def show_tutorial(self):
        """打开「新手交互教程」窗口（分页讲解常用组件，无需写代码）。

        适合第一次接触本库（甚至第一次接触 Python）的用户。
        """
        from .tutorial import TutorialWindow
        TutorialWindow(self)
