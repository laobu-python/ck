# gui/dialogs.py
# 本模块收口：**不再 import tkinter** —— 六个方法全部改走 Renderer 的中立 API
# （`message`/`toast`、`ask_input`/`ask_save_path`、`ask_open_path`、
# `button` + `container`/`Layout`）。这也是「`grep -c "import tkinter" gui/*.py = 0`」
# 终态判据在**本文件**上的达成（下一个目标文件 = `gui/theme.py` 之后剩余的 `gui/*.py`）。

try:                                    # 脚本模式：cwd = 项目根，gui 为顶层包
    from ck1_0.core.theme import Theme
except ImportError:                     # 包模式：本文件即 ck1_0.gui.dialogs
    from ..core.theme import Theme


# gui 包**内部**的依赖用相对导入即可（脚本模式下 `gui` 是顶层包、包模式下是 `ck1_0.gui`）。
# 本模块改走 Renderer 的中立对话框 API，不再自己建 Tk 控件（`_renderer_of` 取宿主 Renderer）。
try:                                    # 脚本模式：cwd = 项目根
    from ck1_0.renderer.base import Layout
except ImportError:                     # 包模式：本文件即 ck1_0.gui.dialogs
    from ..renderer.base import Layout

from .widgets import _content_parent, _renderer_of      # noqa: E402


class DialogMixin:
    def __init__(self, theme=None):
        # minimal initializer for compatibility in multiple inheritance
        if not hasattr(self, 'scrollable_frame'):
            self.scrollable_frame = None
        if not hasattr(self, 'root'):
            self.root = None
        # 语义 token 表：优先沿用宿主已有的 theme（Btk 先于本 mixin 建立），否则用基线主题
        if theme is not None:
            self.theme = theme
        elif not hasattr(self, 'theme'):
            self.theme = Theme.light()

    def create_file_dialog(self, button_text="选择文件", file_types=(("所有文件", "*.*"),)):
        """创建一个「点一下选文件」的按钮，返回**中立句柄**（首版返回 `tk.Button`）。

       点击后弹系统文件选择框（`title='选择文件'` 与首版的硬编码标题逐字相同），
       选中时**打印路径**（首版的友好输出保留），返回值仍只从内部闭包给出。
        """
        # ：控件与对话框都改走 renderer（`ask_open_path`）；摆放参数与首版逐字相同。
        renderer = _renderer_of(self)

        def select_file():
            filename = renderer.ask_open_path(title="选择文件", filetypes=file_types)
            if filename:
                print(f"选择的文件: {filename}")
                return filename
            return None

        handle = renderer.button(_content_parent(self), button_text, command=select_file)
        handle.layout(Layout.pack(pady=self.theme.dialog_button_y))
        return handle

    def ask_save_path(self, title='保存文件', defaultextension='.csv',
                      filetypes=(('CSV 文件', '*.csv'), ('所有文件', '*.*'))):
        """弹出「保存文件」对话框，返回用户选择的路径；取消返回 None。

        参数:
            title (str): 对话框标题
            defaultextension (str): 默认扩展名（如 '.csv' / '.json'）
            filetypes (tuple): 可选文件类型

        返回:
            str 或 None
        """
        # ：改走 renderer 的中立对话框 API（同步语义由 backend 负责）。
        # 首版的「无 root ⇒ 返回 `None`」**保留**（`接口合同` 的冻结哨兵）。
        # **契约差异（承接，已登记）**：取消时首版通常得到空串、中立层**归一化为
        # `None`**（两者都是假值 ⇒ 调用方的 `if not path: return None` 行为不变）。
        if not hasattr(self, 'root') or not self.root:
            return None
        return _renderer_of(self).ask_save_path(title=title, defaultextension=defaultextension,
                                               filetypes=filetypes)

    def create_message_box(self, title, message, msg_type="info"):
        """创建一个「点一下弹消息框」的按钮，返回**中立句柄**（首版返回 `tk.Button`）。

        按钮文本仍由 token `dialog_message_button_template` 决定；点击时转发给 renderer 的
       中立 `message(...)`（**未知 `msg_type` 不动作**，与首版逐字同口径）。
        """
        # ：控件与对话框都改走 renderer；摆放用中立 `Layout.pack`，
        # 参数与首版的 `btn.pack(pady=self.theme.dialog_button_y)` 逐字相同。
        renderer = _renderer_of(self)

        def show_message():
            renderer.message(title, message, kind=msg_type)

        handle = renderer.button(
            _content_parent(self),
            self.theme.dialog_message_button_template.format(msg_type=msg_type),
            command=show_message)
        handle.layout(Layout.pack(pady=self.theme.dialog_button_y))
        return handle

    def show_message(self, title, message, msg_type="info"):
        """立即弹出消息框（**同步模态**）。未知 `msg_type` ⇒ **不动作**（首版语义，冻结）。

：转发给 renderer 的中立 `message(...)` —— 映射与「未知 kind 无动作」规则
        都在 backend（Tk `messagebox.showinfo/showwarning/showerror`）。
        """
        _renderer_of(self).message(title, message, kind=msg_type)

    def show_toast(self, message, duration=2000, kind='info'):
        """在窗口底部居中显示一条非阻塞提示（Toast），到时自动消失。

        参数:
            message (str): 提示文本
            duration (int): 显示时长（毫秒）
            kind (str): 'info' / 'success' / 'warning' / 'error'，决定背景颜色
        """
        # ：改走 renderer 的中立 `toast(...)`—— 颜色/字体/内边距/底距/时长
        # 全在 backend 取 token；**未知 `kind` 回退 `info`**（首版明文，两端一致）。
        # 「无 root ⇒ 只打印」这条首版语义**保留**。
        # **视觉差异（登记，入 目视清单）**：首版把气泡放在**主窗口**底部居中
        # （`root.winfo_rootx/rooty` + 窗口宽高），中立层放在**屏幕**底部居中
        # （实现，`winfo_screenwidth/height`）—— 窗口不全屏时位置不同，属 已定的
        # backend 口径，本批显式列出。
        if not hasattr(self, 'root') or not self.root:
            print(message)
            return
        _renderer_of(self).toast(message, duration_ms=duration, kind=kind)

    def ask_input(self, title='输入', prompt='请输入:', default=''):
        """弹出模态输入对话框，返回用户输入的内容；取消或关闭时返回 None。

        参数:
            title (str): 对话框标题
            prompt (str): 提示文字
            default (str): 输入框默认值

        返回:
            str 或 None
        """
        # ：改走 renderer 的中立对话框 API（：同步模态由 backend 用**局部
        # 事件循环**实现，Tk 侧即 `simpledialog.askstring`）。同样保留「无 root ⇒ `None`」。
        # **视觉差异（登记，入 目视清单）**：首版是**自建** Toplevel（中文
        # 「确定/取消」按钮、Entry 宽度取 token `dialog_input_entry_width`、`grab_set` +
        # `wait_window`）；中立层改用**系统原生**输入框 ⇒ 按钮文案与尺寸不再由 token 决定
        # （`dialog_input_*` 那 6 个 token 在 Tk 侧就此失去消费者）。
        if not hasattr(self, 'root') or not self.root:
            return None
        return _renderer_of(self).ask_input(title=title, prompt=prompt, default=default)