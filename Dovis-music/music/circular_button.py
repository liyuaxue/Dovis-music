import tkinter as tk


class CircularButton:
    def __init__(self, parent, text, command,
                 normal_bg="#34495E", normal_fg="#BDC3C7",
                 hover_bg="#3498DB", hover_fg="white",
                 click_bg="#2980B9", click_fg="white",
                 size=50, font_size=16):
        self.command = command
        self.normal_bg = normal_bg
        self.normal_fg = normal_fg
        self.hover_bg = hover_bg
        self.hover_fg = hover_fg
        self.click_bg = click_bg
        self.click_fg = click_fg
        self.size = size

        self.canvas = tk.Canvas(parent, width=size, height=size, bg="#2C3E50",
                                highlightthickness=0, relief='flat')

        # 绘制填充圆形
        self.circle = self.canvas.create_oval(
            2, 2, size - 2, size - 2,
            fill=normal_bg, outline=normal_bg, width=0
        )

        # 绘制文本 - 使用anchor="center"确保文本居中，特别是对emoji字符
        self.text_item = self.canvas.create_text(
            size // 2, size // 2,
            text=text,
            fill=normal_fg,
            font=("Segoe UI Emoji", font_size, "bold"),
            anchor="center"
        )

        # 绑定事件
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Enter>", self._on_enter)
        self.canvas.bind("<Leave>", self._on_leave)

    def _on_click(self, event):
        self.command()
        self.canvas.itemconfig(self.circle, fill=self.click_bg)
        self.canvas.itemconfig(self.text_item, fill=self.click_fg)
        self.canvas.after(100, self._on_enter)

    def _on_enter(self, event=None):
        self.canvas.itemconfig(self.circle, fill=self.hover_bg)
        self.canvas.itemconfig(self.text_item, fill=self.hover_fg)

    def _on_leave(self, event):
        self.canvas.itemconfig(self.circle, fill=self.normal_bg)
        self.canvas.itemconfig(self.text_item, fill=self.normal_fg)

    def pack(self, **kwargs):
        self.canvas.pack(**kwargs)

    def grid(self, **kwargs):
        self.canvas.grid(**kwargs)

    def place(self, **kwargs):
        self.canvas.place(**kwargs)

    def config(self, **kwargs):
        """配置按钮属性"""
        # 更新颜色配置
        if 'normal_bg' in kwargs:
            self.normal_bg = kwargs['normal_bg']
        if 'normal_fg' in kwargs:
            self.normal_fg = kwargs['normal_fg']
        if 'hover_bg' in kwargs:
            self.hover_bg = kwargs['hover_bg']
        if 'hover_fg' in kwargs:
            self.hover_fg = kwargs['hover_fg']
        if 'click_bg' in kwargs:
            self.click_bg = kwargs['click_bg']
        if 'click_fg' in kwargs:
            self.click_fg = kwargs['click_fg']

        # 更新文本
        if 'text' in kwargs:
            self.canvas.itemconfig(self.text_item, text=kwargs['text'])

        # 更新状态
        if 'state' in kwargs:
            if kwargs['state'] == 'disabled':
                self.canvas.itemconfig(self.circle, fill="#7F8C8D")
                self.canvas.itemconfig(self.text_item, fill="#BDC3C7")
                self.canvas.unbind("<Button-1>")
                self.canvas.unbind("<Enter>")
                self.canvas.unbind("<Leave>")
            else:
                self.canvas.itemconfig(self.circle, fill=self.normal_bg)
                self.canvas.itemconfig(self.text_item, fill=self.normal_fg)
                self.canvas.bind("<Button-1>", self._on_click)
                self.canvas.bind("<Enter>", self._on_enter)
                self.canvas.bind("<Leave>", self._on_leave)

        # 立即应用颜色更改
        self._update_appearance()

    def _update_appearance(self):
        """更新按钮外观"""
        # 获取当前鼠标状态来决定显示哪种颜色
        x, y = self.canvas.winfo_pointerxy()
        widget_x = self.canvas.winfo_rootx()
        widget_y = self.canvas.winfo_rooty()
        widget_width = self.canvas.winfo_width()
        widget_height = self.canvas.winfo_height()

        # 检查鼠标是否在按钮上
        if (widget_x <= x <= widget_x + widget_width and
                widget_y <= y <= widget_y + widget_height):
            # 鼠标在按钮上，显示悬停状态
            self.canvas.itemconfig(self.circle, fill=self.hover_bg)
            self.canvas.itemconfig(self.text_item, fill=self.hover_fg)
        else:
            # 鼠标不在按钮上，显示正常状态
            self.canvas.itemconfig(self.circle, fill=self.normal_bg)
            self.canvas.itemconfig(self.text_item, fill=self.normal_fg)

    def configure(self, **kwargs):
        """configure 方法的别名，用于兼容性"""
        return self.config(**kwargs)