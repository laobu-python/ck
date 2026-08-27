# gui/widgets.py
import tkinter as tk

class WidgetMixin:
    def __init__(self):
        # minimal initializer to be safe when used in multiple inheritance
        # 不要覆盖已有属性，仅确保属性存在占位值
        if not hasattr(self, 'scrollable_frame'):
            self.scrollable_frame = None
        if not hasattr(self, 'root'):
            self.root = None

    def buttonx(self, btname='button', widthx=15, heightx=2, ifzf=True, wstr1='点按钮 ', wstr2='已经点击 ', commandname=None, feedback_id=None):
        parent = self.scrollable_frame

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
                label = tk.Label(parent, text=wstr1)
                label.pack(pady=5)
                self._feedback_labels[btn_id] = label
            feedback_label = self._feedback_labels[btn_id]

            def bclick():
                feedback_label.config(text=wstr2)
                self.root.after(1000, lambda: feedback_label.config(text=wstr1))
                if commandname:
                    commandname()
        else:
            # 不需要反馈提示
            def bclick():
                if commandname:
                    commandname()

        # 创建并返回按钮
        b = tk.Button(parent, text=btname, command=bclick, width=widthx, height=heightx)
        b.pack(pady=10)
        return b

    def input_box(self, hint='请输入', wbox=30, hbox=10, pbox=10, ipbox=0, tzt='Microsoft YaHei', tsize=15, tblod=True):
        parent = self.scrollable_frame
        self.entry = tk.Entry(parent, width=wbox, font=(tzt, tsize, "bold" if tblod else ''))
        self.entry.pack(pady=pbox, ipady=ipbox)
        # 智能占位符：灰色提示，聚焦自动清空，失焦为空时自动恢复
        self.entry.insert(0, hint)
        self.entry.config(fg='grey')

        def _focus_in(_e):
            if self.entry.get() == hint:
                self.entry.delete(0, 'end')
                self.entry.config(fg='black')

        def _focus_out(_e):
            if not self.entry.get():
                self.entry.insert(0, hint)
                self.entry.config(fg='grey')

        self.entry.bind('<FocusIn>', _focus_in)
        self.entry.bind('<FocusOut>', _focus_out)
        return self.entry

    def label_ck(self, label_text, tcolor='#000000', tzt='Microsoft YaHei', tsize=20, tblod=True):
        parent = self.scrollable_frame
        label = tk.Label(parent, text=label_text, compound="top")
        label.config(fg=tcolor, font=(tzt, tsize, "bold" if tblod else ''))
        label.pack(pady=10)
        return label