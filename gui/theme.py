"""ThemeMixin: 简单封装 ttk.Style 和主题/字体配置。"""
import tkinter as tk
from tkinter import ttk


class ThemeMixin:
    def __init__(self):
        # 初始化 ttk 样式
        try:
            self._ttk_style = ttk.Style()
        except Exception:
            self._ttk_style = None

    def set_theme(self, theme_name='clam'):
        """尝试设置 ttk 主题（若可用）。"""
        if self._ttk_style:
            try:
                self._ttk_style.theme_use(theme_name)
            except Exception:
                pass

    def configure_font(self, default_family='Segoe UI', size=10):
        """注册并配置全局默认字体（尽可能在跨平台下兼容）。"""
        try:
            default_font = (default_family, size)
            # 为常用小部件设置默认字体
            if self._ttk_style:
                self._ttk_style.configure('.', font=default_font)
        except Exception:
            pass
