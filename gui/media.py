"""media.py —— MediaMixin：提供图片与 GIF 显示支持

依赖：Pillow 库（pip install pillow），仅在调用 photo()/gif() 时才需要。
未安装 Pillow 时，库的其余部分仍可正常使用。
"""
import tkinter as tk

try:
    from PIL import Image, ImageTk, ImageSequence
    _PIL_AVAILABLE = True
except ImportError:
    Image = ImageTk = ImageSequence = None
    _PIL_AVAILABLE = False


class MediaMixin:
    def __init__(self):
        # 初始化媒体相关状态
        self.photo_img = None
        self.frames = []
        self.delay = 100
        self.gif_label = None
        self.label = None
        self.now_pafl = None
        self.current_frame = 0

    def clear_media(self):
        """清理当前显示的媒体（图像或 GIF）。"""
        try:
            if getattr(self, 'gif_label', None):
                self.gif_label.destroy()
                self.gif_label = None
            if getattr(self, 'label', None):
                self.label.destroy()
                self.label = None
            # 清理引用，允许 GC
            self.photo_img = None
            self.frames = []
            self.now_pafl = None
            self.current_frame = 0
        except Exception:
            pass

    def animate_gif(self):
        """内部方法：循环播放 GIF 帧。"""
        if not getattr(self, 'frames', None):
            return
        try:
            frame = self.frames[self.current_frame]
            if self.gif_label:
                self.gif_label.config(image=frame)
                self.gif_label.image = frame
            self.current_frame = (self.current_frame + 1) % len(self.frames)
            # 使用 after 调度下一帧
            if hasattr(self, 'root') and self.root:
                self.root.after(self.delay, self.animate_gif)
        except Exception:
            # 如果播放出现异常，停止动画并清理
            self.current_frame = 0
            return

    def _need_pillow(self):
        """Pillow 未安装时给出友好提示，返回 False 表示不可用。"""
        if _PIL_AVAILABLE:
            return True
        print("错误：显示图片/GIF 需要 Pillow 库，请先执行 pip install pillow")
        if hasattr(self, 'root') and self.root:
            show = getattr(self, 'show_message', None)
            if show:
                self.root.after(0, lambda: show("缺少依赖", "请先安装 Pillow：pip install pillow", "error"))
        return False

    def photo(self, photo_path='', text='', tcolor='#000000', tzt='Microsoft YaHei', tsize=20, tblod=True):
        """显示静态图片（支持常见图片格式）。"""
        self.clear_media()
        if not self._need_pillow():
            return
        try:
            pil_image = Image.open(photo_path)
            self.photo_img = ImageTk.PhotoImage(pil_image)
            parent = getattr(self, 'scrollable_frame', None)
            if parent is None:
                parent = getattr(self, 'root', None)
            self.label = tk.Label(parent, text=text, image=self.photo_img, compound="top")
            self.label.pack()
            self.label.config(fg=tcolor, font=(tzt, tsize, "bold" if tblod else ''))
            self.label.image = self.photo_img
            self.now_pafl = self.label
        except FileNotFoundError:
            print("错误：找不到图片文件！请检查文件名和路径。")
            if hasattr(self, 'root') and self.root:
                self.root.after(0, lambda: self.show_message("错误", "图片文件不存在！", "error"))
        except Exception as e:
            print(f"处理图片时发生未知错误: {e}")
            if hasattr(self, 'root') and self.root:
                self.root.after(0, lambda: self.show_message("错误", f"无法加载图片：{type(e).__name__}", "error"))

    def gif(self, gif_path='', text='', tcolor='#000000', tzt='Microsoft YaHei', tsize=20, tblod=True):
        """加载并播放 GIF 动画。"""
        self.clear_media()
        if not self._need_pillow():
            return
        try:
            gif = Image.open(gif_path)
            self.frames = []
            for frame in ImageSequence.Iterator(gif):
                # 将帧转换为 RGBA 再转为 PhotoImage
                photo_frame = ImageTk.PhotoImage(frame.copy().convert('RGBA'))
                self.frames.append(photo_frame)
            self.delay = max(50, int(gif.info.get('duration', 100)))
            parent = getattr(self, 'scrollable_frame', None)
            if parent is None:
                parent = getattr(self, 'root', None)
            self.gif_label = tk.Label(parent, text=text, compound="top")
            self.gif_label.pack()
            self.gif_label.config(fg=tcolor, font=(tzt, tsize, "bold" if tblod else ''))
            self.now_pafl = self.gif_label
            self.current_frame = 0
            # 启动动画
            self.animate_gif()
        except FileNotFoundError:
            print(f"错误：找不到GIF文件 '{gif_path}'。")
            if hasattr(self, 'root') and self.root:
                self.root.after(0, lambda: self.show_message("错误", "GIF 文件不存在，请检查路径！", "error"))
        except Exception as e:
            print(f"设置GIF标签时出错: {e}")
            if hasattr(self, 'root') and self.root:
                self.root.after(0, lambda: self.show_message("错误", f"GIF 加载失败：{type(e).__name__}", "error"))
