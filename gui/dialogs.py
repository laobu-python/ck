# gui/dialogs.py
import tkinter as tk
from tkinter import filedialog, messagebox

class DialogMixin:
    def __init__(self):
        # minimal initializer for compatibility in multiple inheritance
        if not hasattr(self, 'scrollable_frame'):
            self.scrollable_frame = None
        if not hasattr(self, 'root'):
            self.root = None

    def create_file_dialog(self, button_text="选择文件", file_types=(("所有文件", "*.*"),)):
        parent = self.scrollable_frame
        def select_file():
            filename = filedialog.askopenfilename(title="选择文件", filetypes=file_types)
            if filename:
                print(f"选择的文件: {filename}")
                return filename
            return None
        btn = tk.Button(parent, text=button_text, command=select_file)
        btn.pack(pady=5)
        return btn

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
        if not hasattr(self, 'root') or not self.root:
            return None
        return filedialog.asksaveasfilename(title=title, defaultextension=defaultextension,
                                            filetypes=filetypes)

    def create_message_box(self, title, message, msg_type="info"):
        parent = self.scrollable_frame
        def show_message():
            if msg_type == "info":
                messagebox.showinfo(title, message)
            elif msg_type == "warning":
                messagebox.showwarning(title, message)
            elif msg_type == "error":
                messagebox.showerror(title, message)
        btn = tk.Button(parent, text=f"显示{msg_type}消息", command=show_message)
        btn.pack(pady=5)
        return btn

    def show_message(self, title, message, msg_type="info"):
        if msg_type == "info":
            messagebox.showinfo(title, message)
        elif msg_type == "warning":
            messagebox.showwarning(title, message)
        elif msg_type == "error":
            messagebox.showerror(title, message)

    def show_toast(self, message, duration=2000, kind='info'):
        """在窗口底部居中显示一条非阻塞提示（Toast），到时自动消失。

        参数:
            message (str): 提示文本
            duration (int): 显示时长（毫秒）
            kind (str): 'info' / 'success' / 'warning' / 'error'，决定背景颜色
        """
        if not hasattr(self, 'root') or not self.root:
            print(message)
            return
        colors = {'info': '#2196f3', 'success': '#4caf50', 'warning': '#ff9800', 'error': '#f44336'}
        color = colors.get(kind, colors['info'])

        toast = tk.Toplevel(self.root)
        toast.overrideredirect(True)
        toast.attributes('-topmost', True)
        label = tk.Label(toast, text=message, bg=color, fg='white',
                         font=('Microsoft YaHei', 10), padx=16, pady=8)
        label.pack()

        # 定位在主窗口底部居中
        self.root.update_idletasks()
        rx, ry = self.root.winfo_rootx(), self.root.winfo_rooty()
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        tw, th = label.winfo_reqwidth(), label.winfo_reqheight()
        toast.wm_geometry(f"+{rx + (rw - tw) // 2}+{ry + rh - th - 40}")

        self.root.after(duration, toast.destroy)

    def ask_input(self, title='输入', prompt='请输入:', default=''):
        """弹出模态输入对话框，返回用户输入的内容；取消或关闭时返回 None。

        参数:
            title (str): 对话框标题
            prompt (str): 提示文字
            default (str): 输入框默认值

        返回:
            str 或 None
        """
        if not hasattr(self, 'root') or not self.root:
            return None
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.resizable(False, False)

        result = {'value': None}

        tk.Label(dialog, text=prompt, padx=12, pady=(12, 4)).pack()
        var = tk.StringVar(value=default)
        entry = tk.Entry(dialog, textvariable=var, width=32)
        entry.pack(padx=12, pady=4)
        entry.focus_set()
        entry.select_range(0, 'end')

        btns = tk.Frame(dialog)
        btns.pack(pady=8)

        def _ok():
            result['value'] = var.get()
            dialog.destroy()

        def _cancel():
            dialog.destroy()

        tk.Button(btns, text='确定', width=8, command=_ok).pack(side='left', padx=6)
        tk.Button(btns, text='取消', width=8, command=_cancel).pack(side='left', padx=6)
        dialog.bind('<Return>', lambda e: _ok())
        dialog.bind('<Escape>', lambda e: _cancel())

        dialog.grab_set()
        self.root.wait_window(dialog)
        return result['value']