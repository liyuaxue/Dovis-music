import tkinter as tk
from tkinter import ttk
from config import THEMES, DEFAULT_THEME
import os
import json


class LeftPanel:
    def __init__(self, parent, music_player):
        self.parent = parent
        self.music_player = music_player

        # 先初始化变量
        self.playlist_count_var = tk.StringVar(value="0 首")

        # 初始化主题
        self.theme_manager = music_player.theme_manager
        self.current_theme = self.theme_manager.get_current_theme()

        # 创建左面板主框架
        self.main_frame = tk.Frame(parent, bg=self.current_theme["bg"])

        # 创建组件区域
        self.create_components_section()

        # 播放列表区域
        self.create_playlist_section()

    def create_components_section(self):
        """创建多个小组件区域"""
        components_container = tk.Frame(self.main_frame, bg=self.current_theme["bg"], height=140)
        components_container.pack(fill=tk.X, pady=(0, 10))
        components_container.pack_propagate(False)

        # 组件标题
        components_label = tk.Label(components_container, text="🎵 音乐库",
                                    font=("Microsoft YaHei", 12, "bold"),
                                    bg=self.current_theme["secondary_bg"],
                                    fg=self.current_theme["text"])
        components_label.pack(fill=tk.X, padx=10, pady=5)

        # 组件按钮框架
        buttons_frame = tk.Frame(components_container, bg=self.current_theme["secondary_bg"])
        buttons_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 创建多个组件按钮
        components_data = [
            {"text": "📋 播放列表", "command": self.show_playlist, "keyword": ""},
            {"text": "❤️ 收藏夹", "command": self.show_favorites, "keyword": "收藏歌曲"},
            {"text": "🔥 热歌榜", "command": self.show_hot_songs, "keyword": "热歌榜"},
            {"text": "🚀 飙升榜", "command": self.show_rising_songs, "keyword": "飙升榜"},
            {"text": "🎵 新歌榜", "command": self.show_new_songs, "keyword": "新歌榜"},
            {"text": "🏆 经典榜", "command": self.show_classic_songs, "keyword": "经典老歌"}
        ]

        # 创建2行3列的按钮布局
        for i, comp_data in enumerate(components_data):
            row = i // 3
            col = i % 3

            btn = tk.Button(buttons_frame, text=comp_data["text"],
                            command=comp_data["command"],
                            bg=self.current_theme["button_bg"],
                            fg=self.current_theme["text"],
                            font=("Microsoft YaHei", 9),
                            relief="flat",
                            cursor="hand2",
                            padx=10,
                            pady=8)
            btn.grid(row=row, column=col, padx=5, pady=3, sticky="ew")

            # 存储关键词信息
            btn.keyword = comp_data["keyword"]

            # 设置列权重使按钮均匀分布
            buttons_frame.columnconfigure(col, weight=1)

    def create_playlist_section(self):
        """创建播放列表区域"""
        playlist_container = tk.Frame(self.main_frame, bg=self.current_theme["bg"])
        playlist_container.pack(fill=tk.BOTH, expand=True)

        # 播放列表标题栏
        playlist_header = tk.Frame(playlist_container, bg=self.current_theme["secondary_bg"], height=35)
        playlist_header.pack(fill=tk.X, pady=(0, 5))
        playlist_header.pack_propagate(False)

        playlist_label = tk.Label(playlist_header, text="🎵 播放列表",
                                  font=("Microsoft YaHei", 12, "bold"),
                                  bg=self.current_theme["secondary_bg"],
                                  fg=self.current_theme["text"])
        playlist_label.pack(side=tk.LEFT, padx=15, pady=8)

        # 歌曲计数
        self.playlist_count_label = tk.Label(playlist_header, textvariable=self.playlist_count_var,
                                             font=("Microsoft YaHei", 10),
                                             bg=self.current_theme["secondary_bg"],
                                             fg=self.current_theme["secondary_text"])
        self.playlist_count_label.pack(side=tk.LEFT, padx=10, pady=8)

        # 收藏播放列表按钮
        clear_fav_btn = tk.Button(playlist_header, text="⭐ 收藏列表",
                                  command=self.music_player.add_playlist_to_favorites,
                                  bg="#27ae60", fg="white",
                                  font=("Microsoft YaHei", 9),
                                  relief="flat", padx=10, cursor="hand2")
        clear_fav_btn.pack(side=tk.LEFT, padx=3)

        # 清空收藏按钮
        clear_fav_btn = tk.Button(playlist_header, text="🗑️ 清空收藏夹",
                                       command=self.music_player.clear_favorites,
                                       bg="#e74c3c", fg="white",
                                       font=("Microsoft YaHei", 9),
                                       relief="flat", padx=10, cursor="hand2")
        clear_fav_btn.pack(side=tk.LEFT, padx=3)

        # 清除播放列表按钮
        clear_playlist_btn = tk.Button(playlist_header, text="🗑️ 清空列表",
                                       command=self.music_player.clear_playlist,
                                       bg="#e74c3c", fg="white",
                                       font=("Microsoft YaHei", 9),
                                       relief="flat", padx=10, cursor="hand2")
        clear_playlist_btn.pack(side=tk.RIGHT, padx=3)

        # 播放列表框架
        playlist_frame = tk.Frame(playlist_container, bg=self.current_theme["bg"])
        playlist_frame.pack(fill=tk.BOTH, expand=True)

        # 创建树形视图显示播放列表
        columns = ("#", "歌曲", "歌手", "专辑")
        self.playlist_tree = ttk.Treeview(playlist_frame, columns=columns,
                                          show="headings", height=12,
                                          style="Treeview")

        # 配置列宽和锚点
        self.playlist_tree.column("#", width=30, anchor=tk.CENTER)
        self.playlist_tree.column("歌曲", width=120, anchor=tk.W)
        self.playlist_tree.column("歌手", width=80, anchor=tk.W)
        self.playlist_tree.column("专辑", width=100, anchor=tk.W)

        for col in columns:
            self.playlist_tree.heading(col, text=col)

        # 滚动条
        scrollbar = ttk.Scrollbar(playlist_frame, orient=tk.VERTICAL,
                                  command=self.playlist_tree.yview)
        self.playlist_tree.configure(yscrollcommand=scrollbar.set)

        self.playlist_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 2))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(2, 0))

        # 绑定双击事件
        self.playlist_tree.bind("<Double-1>", self.music_player.on_playlist_double_click)

    def show_playlist(self):
        """显示播放列表"""
        # 清空播放列表显示当前播放列表内容
        self.music_player.auto_search_hot_songs()

    def show_favorites(self):
        """显示收藏夹"""
        self.music_player.show_favorites()

    def show_hot_songs(self):
        """显示热歌榜"""
        self.music_player.search_and_display("热歌榜", "热歌榜")

    def show_rising_songs(self):
        """显示飙升榜"""
        self.music_player.search_and_display("飙升榜", "飙升榜")

    def show_new_songs(self):
        """显示新歌榜"""
        self.music_player.search_and_display("新歌榜", "新歌榜")

    def show_classic_songs(self):
        """显示经典榜"""
        self.music_player.search_and_display("经典老歌", "经典榜")

    def pack(self, **kwargs):
        """打包显示左面板"""
        self.main_frame.pack(**kwargs)

    def grid(self, **kwargs):
        """网格布局左面板"""
        self.main_frame.grid(**kwargs)

    def place(self, **kwargs):
        """位置布局左面板"""
        self.main_frame.place(**kwargs)

    def update_playlist_count(self, count):
        """更新播放列表计数"""
        self.playlist_count_var.set(f"{count} 首")

    def clear_playlist_tree(self):
        """清空播放列表树"""
        for item in self.playlist_tree.get_children():
            self.playlist_tree.delete(item)

    def insert_playlist_item(self, values, tags=()):
        """插入播放列表项"""
        return self.playlist_tree.insert("", "end", values=values, tags=tags)

    def get_playlist_selection(self):
        """获取播放列表选中项"""
        return self.playlist_tree.selection()

    def playlist_item_values(self, item):
        """获取播放列表项的值"""
        return self.playlist_tree.item(item, "values")

    def playlist_item_tags(self, item):
        """获取播放列表项的标签"""
        return self.playlist_tree.item(item, "tags")

    def set_playlist_selection(self, item):
        """设置播放列表选中项"""
        self.playlist_tree.selection_set(item)

    def set_playlist_focus(self, item):
        """设置播放列表焦点"""
        self.playlist_tree.focus(item)

    def see_playlist_item(self, item):
        """滚动到播放列表项"""
        self.playlist_tree.see(item)

    def configure_playlist_tag(self, tag, **kwargs):
        """配置播放列表标签样式"""
        self.playlist_tree.tag_configure(tag, **kwargs)

    def set_playlist_item_tags(self, item, tags):
        """设置播放列表项标签"""
        self.playlist_tree.item(item, tags=tags)

    def clear_playlist_selection(self):
        """清除播放列表选中状态"""
        self.playlist_tree.selection_remove(self.playlist_tree.selection())

    def apply_theme(self, theme_name):
        """应用主题"""
        theme = self.theme_manager.get_theme(theme_name)
        if not theme:
            return

        self.current_theme = theme

        # 更新主框架背景
        self.main_frame.configure(bg=theme["bg"])

        # 更新所有子组件的颜色
        self._update_colors(theme)

    def _update_colors(self, theme):
        """更新所有组件的颜色"""
        try:
            # 更新容器背景
            for widget in self.main_frame.winfo_children():
                if isinstance(widget, tk.Frame):
                    try:
                        widget.configure(bg=theme["bg"])
                    except:
                        pass

            # 更新组件按钮颜色
            components_container = self.main_frame.winfo_children()[0]
            for widget in components_container.winfo_children():
                if isinstance(widget, tk.Frame):
                    for btn in widget.winfo_children():
                        if isinstance(btn, tk.Button):
                            btn.configure(bg=theme["button_bg"], fg=theme["text"])

            # 更新标题栏背景
            try:
                playlist_container = self.main_frame.winfo_children()[1]
                playlist_header = playlist_container.winfo_children()[0]
                playlist_header.configure(bg=theme["secondary_bg"])
            except:
                pass

            # 更新标签颜色
            try:
                self.playlist_count_label.configure(
                    bg=theme["secondary_bg"],
                    fg=theme["secondary_text"]
                )
            except:
                pass

        except Exception as e:
            print(f"更新左面板颜色时出错: {e}")