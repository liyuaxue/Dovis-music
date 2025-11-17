import tkinter as tk
from tkinter import ttk, messagebox
import threading
from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageFilter
import io,os
import requests
import json
from music_api import MusicAPI
from audio_player import AudioPlayer
from lyrics_manager import LyricsManager
from album_lyrics_panel import AlbumLyricsPanel
from left_panel import LeftPanel
from config import THEMES, THEME_NAMES, DEFAULT_THEME, MUSIC_SOURCES, QUALITY_OPTIONS, PLAY_MODES
from circular_button import CircularButton
#8888888888888888888888888888888


class ThemeManager:
    def __init__(self):
        self.themes = THEMES
        self.theme_names = THEME_NAMES
        self.current_theme = DEFAULT_THEME

    def get_theme(self, theme_name):
        """获取指定主题"""
        return self.themes.get(theme_name)

    def get_current_theme(self):
        """获取当前主题"""
        return self.themes.get(self.current_theme)

    def set_theme(self, theme_name):
        """设置当前主题"""
        if theme_name in self.themes:
            self.current_theme = theme_name
            return True
        return False

    def get_available_themes(self):
        """获取可用主题列表（中文名）"""
        return list(self.theme_names.values())

    def get_theme_key_by_name(self, chinese_name):
        """通过中文名获取主题键"""
        for key, name in self.theme_names.items():
            if name == chinese_name:
                return key
        return DEFAULT_THEME


class MusicPlayerGUI:
    def __init__(self, root):
        self.current_playlist_item = None  # 当前播放的播放列表项ID
        self.current_playlist_index = -1  # 当前播放的播放列表索引
        self._playback_finished_triggered = False
        self.search_count_var = tk.StringVar(value="50")   # 默认搜索50首

        self.current_lyric_var = None  # 会在create_control_bar中初始化
        self.current_lyric_label = None

        self.root = root
        self.root.title("Dovis-music")
        self.root.geometry("1200x900")
        self.root.configure(bg="#f0f0f0")

        # 初始化主题管理器
        self.theme_manager = ThemeManager()

        # 初始化组件
        self.api = MusicAPI()
        self.player = AudioPlayer()
        self.lyrics_manager = LyricsManager()

        # 音乐数据
        self.search_results = []
        self.current_track = None
        self.playlist = []
        self.current_index = 0

        # 添加收藏功能相关变量
        self.favorites_file = "favorites.json"
        self.favorites = self.load_favorites()

        # 搜索结果框架引用
        self.search_results_frame = None
        self.search_results_visible = False

        # 设置播放器回调
        self.player.update_callback = self.on_position_update

        # 创建UI
        self.create_ui()
        # 应用浅色主题
        self.root.after(100, lambda: self.apply_theme("light"))
        # 初始化完成后自动搜索热门歌曲
        self.root.after(1000, self.auto_search_hot_songs)

    def clear_favorites(self):
        """清空收藏夹"""
        if not self.favorites:
            messagebox.showinfo("提示", "收藏夹已经是空的")
            return

        if messagebox.askyesno("确认清空", "确定要清空收藏夹吗？此操作不可恢复！"):
            self.favorites.clear()
            self.save_favorites()
            messagebox.showinfo("成功", "收藏夹已清空")
            print("收藏夹已清空")

    def show_favorites(self):
        """显示收藏夹"""
        # 重新加载收藏列表
        self.favorites = self.load_favorites()

        if not self.favorites:
            self._show_playback_info("收藏夹为空")
            return

        # 将收藏歌曲显示到播放列表
        self._update_playlist_with_tracks(self.favorites, "收藏夹")

    def load_favorites(self):
        """加载收藏列表"""
        try:
            if os.path.exists(self.favorites_file):
                with open(self.favorites_file, 'r', encoding='utf-8') as f:
                    favorites_data = json.load(f)
                    print(f"成功加载收藏列表，共 {len(favorites_data)} 首歌曲")
                    return favorites_data
            else:
                print("收藏文件不存在，创建空列表")
                return []
        except Exception as e:
            print(f"加载收藏列表失败: {e}")
            return []

    def save_favorites(self):
        """保存收藏列表"""
        try:
            with open(self.favorites_file, 'w', encoding='utf-8') as f:
                json.dump(self.favorites, f, ensure_ascii=False, indent=2)
            print(f"成功保存收藏列表，共 {len(self.favorites)} 首歌曲")
        except Exception as e:
            print(f"保存收藏列表失败: {e}")

    def add_current_to_favorites(self):
        """添加当前歌曲到收藏"""
        if not self.current_track:
            messagebox.showwarning("提示", "没有正在播放的歌曲")
            return

        # 检查是否已经收藏
        track_id = self.current_track.get('id')
        if any(fav.get('id') == track_id for fav in self.favorites):
            messagebox.showinfo("提示", "该歌曲已在收藏夹中")
            return

        # 添加到收藏
        self.favorites.append(self.current_track.copy())  # 使用copy避免引用问题
        self.save_favorites()
        messagebox.showinfo("成功", f"已收藏: {self.current_track.get('name', '未知歌曲')}")

    def search_and_display(self, keyword, list_name):
        """搜索并显示到播放列表"""
        self._show_playback_info(f"正在加载{list_name}...")

        # 获取搜索数量
        try:
            count = int(self.search_count_var.get())
        except:
            count = 50  # 默认值

        # 在新线程中执行搜索
        threading.Thread(target=self._search_and_display_thread, args=(keyword, list_name, count), daemon=True).start()

    def _search_and_display_thread(self, keyword, list_name, count=50):
        """搜索并显示线程"""
        try:
            result = self.api.search(keyword, source="网易云音乐", count=count)

            if result and result.get("code") == 200 and "data" in result and result["data"]:
                tracks = result["data"]

                # 在主线程中更新播放列表
                self.root.after(0, lambda: self._update_playlist_with_tracks(tracks, list_name))
            else:
                self.root.after(0, lambda: self._show_playback_info(f"加载{list_name}失败"))

        except Exception as e:
            print(f"加载{list_name}失败: {e}")
            self.root.after(0, lambda: self._show_playback_info(f"加载{list_name}失败"))

    def _update_playlist_with_tracks(self, tracks, list_name):
        """用指定歌曲更新播放列表"""
        try:
            # 清空当前播放列表
            self.left_panel.clear_playlist_tree()
            self.playlist.clear()

            # 添加歌曲到播放列表
            for track in tracks:
                self.add_to_playlist(track)

            # 显示成功信息
            song_count = len(tracks)
            self._show_playback_info(f"已加载 {song_count} 首{list_name}歌曲")
            print(f"成功添加 {song_count} 首{list_name}歌曲到播放列表")
        except Exception as e:
            print(f"更新播放列表失败: {e}")
            self._show_playback_info("播放列表更新失败")

    def auto_search_hot_songs(self):
        """自动搜索热门歌曲并添加到播放列表"""
        print("正在自动搜索热门歌曲...")
        self._show_playback_info("正在加载热门歌曲...")

        # 在新线程中执行搜索
        threading.Thread(target=self._auto_search_thread, daemon=True).start()

    def _auto_search_thread(self,count =100):
        """自动搜索线程"""
        try:
            # 使用多个热门关键词来获取更多歌曲
            hot_keywords = ["热门歌曲", "抖音热歌", "流行音乐", "华语金曲"]

            all_tracks = []

            for keyword in hot_keywords:
                try:
                    print(f"搜索热门关键词: {keyword}")
                    result = self.api.search(keyword, source="网易云音乐", count= count)

                    if result and result.get("code") == 200 and "data" in result and result["data"]:
                        tracks = result["data"]
                        # 去重处理
                        for track in tracks:
                            track_id = track.get('id')
                            if not any(t.get('id') == track_id for t in all_tracks):
                                all_tracks.append(track)

                        print(f"关键词 '{keyword}' 找到 {len(tracks)} 首歌曲，去重后总数为 {len(all_tracks)}")

                        # 如果已经收集到足够多的歌曲，就停止搜索
                        if len(all_tracks) >= count:
                            break

                    # 短暂延迟，避免请求过于频繁
                    import time
                    time.sleep(0.5)

                except Exception as e:
                    print(f"搜索关键词 '{keyword}' 时出错: {e}")
                    continue

            # 限制最多200首
            final_tracks = all_tracks[:count]

            # 在主线程中更新UI
            self.root.after(0, lambda: self._update_playlist_with_tracks(final_tracks, "热门"))

        except Exception as e:
            print(f"自动搜索热门歌曲失败: {e}")
            self.root.after(0, lambda: self._show_playback_info("热门歌曲加载失败"))

    def create_ui(self):
        # 设置全局样式
        self.style = ttk.Style()

        # 配置Treeview浅色主题
        self.style.theme_use('default')

        # Treeview样式配置 - 初始使用浅色样式
        self.style.configure("Treeview",
                             background="#dee2e6",  # 浅色背景
                             foreground="#2c3e50",  # 深色文字
                             fieldbackground="#dee2e6",  # 浅色字段背景
                             rowheight=25,
                             borderwidth=0,
                             font=("Microsoft YaHei", 10))

        self.style.configure("Treeview.Heading",
                             background="#e9ecef",  # 浅色标题背景
                             foreground="#2c3e50",  # 深色标题文字
                             font=("Microsoft YaHei", 11, "bold"),
                             relief="flat",
                             borderwidth=1)

        # 选中状态样式
        self.style.map("Treeview",
                       background=[('selected', '#e74c3c')],  # 选中项红色背景
                       foreground=[('selected', 'white')])  # 选中项白色文字

        # 滚动条样式
        self.style.configure("Vertical.TScrollbar",
                             background="#dee2e6",
                             darkcolor="#e9ecef",
                             lightcolor="#e9ecef",
                             troughcolor="#e9ecef",
                             bordercolor="#e9ecef",
                             arrowcolor="#2c3e50")

        # 主容器 - 初始使用浅色背景
        main_frame = tk.Frame(self.root, bg="#f8f9fa")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # 先初始化共享的变量
        self.current_song_var = tk.StringVar(value="")
        self.current_artist_var = tk.StringVar(value="")
        self.playback_info_var = tk.StringVar(value="准备就绪")
        self.format_var = tk.StringVar(value="格式: 未知")

        # 顶部搜索栏
        self.create_search_bar(main_frame)

        # 内容区域 - 初始使用浅色背景
        content_frame = tk.Frame(main_frame, bg="#f8f9fa")
        content_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # 左右分栏
        paned_window = ttk.PanedWindow(content_frame, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True)

        # 左侧播放列表和搜索结果
        self.create_left_panel(paned_window)

        # 右侧专辑和歌词
        self.create_right_panel(paned_window)

        # 底部控制栏
        self.create_control_bar(main_frame)

    def create_search_bar(self, parent):
        # 获取当前主题
        current_theme = self.theme_manager.get_current_theme()

        search_frame = tk.Frame(parent, bg=current_theme["bg"])
        search_frame.pack(fill=tk.X, pady=(0, 15))

        # 搜索框容器 - 添加圆角效果
        search_container = tk.Frame(search_frame, bg=current_theme["secondary_bg"], relief=tk.RAISED, bd=1)
        search_container.pack(fill=tk.X, padx=10, pady=5)

        # 搜索源选择
        source_label = tk.Label(search_container, text="🎵 音乐源:", bg=current_theme["secondary_bg"],
                                fg=current_theme["text"],
                                font=("Microsoft YaHei", 10))
        source_label.pack(side=tk.LEFT, padx=(15, 5), pady=8)

        self.source_var = tk.StringVar(value="网易云音乐")
        source_combo = ttk.Combobox(search_container, textvariable=self.source_var,
                                    values=list(MUSIC_SOURCES.values()),
                                    width=12, state="readonly")
        source_combo.pack(side=tk.LEFT, padx=5, pady=8)

        # 搜索数量选择
        count_label = tk.Label(search_container, text="📊 数量:", bg=current_theme["secondary_bg"],
                               fg=current_theme["text"],
                               font=("Microsoft YaHei", 10))
        count_label.pack(side=tk.LEFT, padx=(15, 5), pady=8)

        self.search_count_var = tk.StringVar(value="50")  # 默认50首
        count_combo = ttk.Combobox(search_container, textvariable=self.search_count_var,
                                   values=["10", "20", "30", "50", "100"],
                                   width=8, state="normal")
        count_combo.pack(side=tk.LEFT, padx=5, pady=8)

        # 搜索框
        self.search_var = tk.StringVar()
        search_entry = tk.Entry(search_container, textvariable=self.search_var,
                                width=35, font=("Microsoft YaHei", 11),
                                bg=current_theme["tertiary_bg"], fg=current_theme["text"],
                                insertbackground=current_theme["text"],
                                relief=tk.FLAT, bd=2)
        search_entry.pack(side=tk.LEFT, padx=15, pady=8, fill=tk.X, expand=True)
        search_entry.bind("<Return>", lambda e: self.search_music())

        # 搜索按钮
        search_btn = tk.Button(search_container, text="🔍 搜索", command=self.search_music,
                               bg=current_theme["accent"], fg="white", font=("Microsoft YaHei", 10, "bold"),
                               relief="flat", bd=0, padx=20, cursor="hand2")
        search_btn.pack(side=tk.LEFT, padx=(10, 15), pady=8)

        # 设置选项容器
        options_frame = tk.Frame(search_frame, bg=current_theme["bg"])
        options_frame.pack(fill=tk.X, padx=10, pady=5)

        # 频谱显示（移动到搜索栏）
        spectrum_frame = tk.Frame(options_frame, bg=current_theme["bg"])
        spectrum_frame.pack(side=tk.LEFT, padx=10)

        spectrum_label = tk.Label(spectrum_frame, text="📊 频谱:",
                                  bg=current_theme["bg"], fg=current_theme["text"],
                                  font=("Microsoft YaHei", 9))
        spectrum_label.pack(side=tk.LEFT, padx=(20, 5))

        self.spectrum_mode_var = tk.StringVar(value="圆形")
        spectrum_combo = ttk.Combobox(spectrum_frame,
                                      textvariable=self.spectrum_mode_var,
                                      values=["条形", "圆形", "瀑布流"],
                                      width=8, state="readonly")
        spectrum_combo.pack(side=tk.LEFT, padx=5)
        spectrum_combo.bind("<<ComboboxSelected>>", self.on_spectrum_mode_change)

        # 主题切换（移动到搜索栏）
        theme_frame = tk.Frame(options_frame, bg=current_theme["bg"])
        theme_frame.pack(side=tk.LEFT, padx=10)

        theme_label = tk.Label(theme_frame, text="🎨 主题:",
                               bg=current_theme["bg"], fg=current_theme["text"],
                               font=("Microsoft YaHei", 9))
        theme_label.pack(side=tk.LEFT, padx=(20, 5))

        self.theme_var = tk.StringVar(value=self.theme_manager.theme_names[DEFAULT_THEME])
        theme_combo = ttk.Combobox(theme_frame,
                                   textvariable=self.theme_var,
                                   values=self.theme_manager.get_available_themes(),
                                   width=8, state="readonly")
        theme_combo.pack(side=tk.LEFT, padx=5)
        theme_combo.bind("<<ComboboxSelected>>", self.on_theme_change)

        # 搜索结果下拉框架（初始隐藏）
        self.search_results_frame = tk.Frame(search_frame, bg=current_theme["secondary_bg"])
        # 不立即pack，等搜索时再显示

    def create_left_panel(self, paned_window):
        """创建左侧播放列表和搜索结果面板"""
        # 创建左面板实例
        self.left_panel = LeftPanel(paned_window, self)

        # 添加到paned_window
        paned_window.add(self.left_panel.main_frame, weight=1)

    def create_right_panel(self, paned_window):
        """创建右侧专辑和歌词面板"""
        right_frame = tk.Frame(paned_window, bg="#1a1a1a")
        paned_window.add(right_frame, weight=1)

        # 创建专辑歌词面板
        self.album_lyrics_panel = AlbumLyricsPanel(right_frame, self.lyrics_manager, self.theme_manager)

    def create_control_bar(self, parent):
        # 获取当前主题
        current_theme = self.theme_manager.get_current_theme()

        control_frame = tk.Frame(parent, bg=current_theme["secondary_bg"], height=150)
        control_frame.pack(fill=tk.X, pady=5)
        control_frame.pack_propagate(False)
        self.control_frame = control_frame

        # 顶部：播放信息和歌词显示
        top_frame = tk.Frame(control_frame, bg=current_theme["secondary_bg"])
        top_frame.pack(fill=tk.X, padx=20, pady=(10, 5))
        self.top_frame = top_frame

        # 左侧：播放信息
        info_frame = tk.Frame(top_frame, bg=current_theme["secondary_bg"])
        info_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.info_frame = info_frame

        # 当前播放歌曲信息
        song_label = tk.Label(info_frame, textvariable=self.current_song_var,
                              font=("Microsoft YaHei", 10, "bold"),
                              bg=current_theme["secondary_bg"], fg=current_theme["text"],
                              anchor="w", width=20)
        song_label.pack(fill=tk.X, pady=(0, 2))
        self.song_label = song_label

        artist_label = tk.Label(info_frame, textvariable=self.current_artist_var,
                                font=("Microsoft YaHei", 9),
                                bg=current_theme["secondary_bg"], fg=current_theme["secondary_text"],
                                anchor="w", width=20)
        artist_label.pack(fill=tk.X)
        self.artist_label = artist_label

        # 中央：当前播放歌词显示
        lyric_frame = tk.Frame(top_frame, bg=current_theme["secondary_bg"])
        lyric_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=20)
        self.lyric_frame = lyric_frame

        self.current_lyric_var = tk.StringVar(value="")
        self.current_lyric_label = tk.Label(lyric_frame,
                                            textvariable=self.current_lyric_var,
                                            font=("Microsoft YaHei", 16, "bold"),
                                            bg=current_theme["secondary_bg"],
                                            fg=current_theme["accent"],
                                            wraplength=600,
                                            justify=tk.CENTER,
                                            anchor=tk.CENTER)
        self.current_lyric_label.pack(expand=True, fill=tk.BOTH)

        # 右侧：状态信息
        status_frame = tk.Frame(top_frame, bg=current_theme["secondary_bg"])
        status_frame.pack(side=tk.RIGHT, fill=tk.Y)
        self.status_frame = status_frame

        playback_info_frame = tk.Frame(status_frame, bg=current_theme["secondary_bg"], height=20)
        playback_info_frame.pack(fill=tk.X)
        playback_info_frame.pack_propagate(False)

        # 创建Canvas用于滚动文本
        playback_canvas = tk.Canvas(playback_info_frame,
                                    bg=current_theme["secondary_bg"],
                                    highlightthickness=0,
                                    height=20)
        playback_canvas.pack(fill=tk.X)
        playback_info_frame.bind("<Configure>", self._on_playback_frame_configure)

        # 在Canvas上创建文本
        self.playback_text_id = playback_canvas.create_text(0, 10,
                                                            text="",
                                                            anchor="w",
                                                            font=("Microsoft YaHei", 10),
                                                            fill=current_theme["accent"])
        self.playback_canvas = playback_canvas
        self.playback_animation_id = None

        self.playback_info_var.trace_add("write", self._update_playback_scroll_text)

        format_label = tk.Label(status_frame, textvariable=self.format_var,
                                font=("Microsoft YaHei", 9),
                                bg=current_theme["secondary_bg"], fg=current_theme["secondary_text"],
                                anchor="e", width=15)
        format_label.pack(fill=tk.X, pady=(2, 0))
        self.format_label = format_label

        # 中间：进度条
        progress_frame = tk.Frame(control_frame, bg=current_theme["secondary_bg"])
        progress_frame.pack(fill=tk.X, padx=20, pady=5)

        # 时间显示和进度条
        time_progress_frame = tk.Frame(progress_frame, bg=current_theme["secondary_bg"])
        time_progress_frame.pack(fill=tk.X)

        # 当前时间
        self.current_time_var = tk.StringVar(value="00:00")
        current_time_label = tk.Label(time_progress_frame, textvariable=self.current_time_var,
                                      font=("Microsoft YaHei", 9),
                                      bg=current_theme["secondary_bg"], fg=current_theme["text"],
                                      width=6)
        current_time_label.pack(side=tk.LEFT)

        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Scale(time_progress_frame, from_=0, to=100,
                                      variable=self.progress_var, orient=tk.HORIZONTAL,
                                      length=400)
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.progress_bar.bind("<ButtonRelease-1>", self.on_progress_change)

        # 总时间
        self.total_time_var = tk.StringVar(value="00:00")
        total_time_label = tk.Label(time_progress_frame, textvariable=self.total_time_var,
                                    font=("Microsoft YaHei", 9),
                                    bg=current_theme["secondary_bg"], fg=current_theme["text"],
                                    width=6)
        total_time_label.pack(side=tk.RIGHT)

        # 底部：控制按钮和设置控件
        bottom_frame = tk.Frame(control_frame, bg=current_theme["secondary_bg"])
        bottom_frame.pack(fill=tk.X, padx=20, pady=(5, 10))

        # 控制按钮
        button_frame = tk.Frame(bottom_frame, bg=current_theme["secondary_bg"])
        button_frame.pack(side=tk.LEFT)

        # 超紧凑版本
        self.prev_btn = CircularButton(button_frame, "⏮", self.previous_track,
                                       normal_bg=current_theme["button_bg"],
                                       normal_fg=current_theme["text"],
                                       hover_bg=current_theme["button_hover"],
                                       hover_fg="white",
                                       size=32, font_size=10)
        self.prev_btn.pack(side=tk.LEFT, padx=3)

        self.play_btn = CircularButton(button_frame, "⏵", self.toggle_play,
                                       normal_bg=current_theme["accent"],
                                       normal_fg="white",
                                       hover_bg=current_theme["button_hover"],
                                       hover_fg="white",
                                       size=36, font_size=12)
        self.play_btn.pack(side=tk.LEFT, padx=3)

        self.next_btn = CircularButton(button_frame, "⏭", self.next_track,
                                       normal_bg=current_theme["button_bg"],
                                       normal_fg=current_theme["text"],
                                       hover_bg=current_theme["button_hover"],
                                       hover_fg="white",
                                       size=32, font_size=10)
        self.next_btn.pack(side=tk.LEFT, padx=3)

        self.stop_btn = CircularButton(button_frame, "⏹", self.stop_play,
                                       normal_bg=current_theme["button_bg"],
                                       normal_fg=current_theme["text"],
                                       hover_bg="#E74C3C",
                                       hover_fg="white",
                                       size=32, font_size=10)
        self.stop_btn.pack(side=tk.LEFT, padx=3)

        self.favorite_btn = CircularButton(button_frame, "    ❤️", self.add_current_to_favorites,
                                           normal_bg=current_theme["accent"],
                                           normal_fg="white",
                                           hover_bg=current_theme["button_hover"],
                                           hover_fg="white",
                                           size=36, font_size=16)
        self.favorite_btn.pack(side=tk.LEFT, padx=3)

        # 右侧：设置控件（按照新顺序：音质 -> 模式 -> 频谱 -> 主题）
        settings_frame = tk.Frame(bottom_frame, bg=current_theme["secondary_bg"])
        settings_frame.pack(side=tk.RIGHT)

        # 1. 音质选择
        quality_frame = tk.Frame(settings_frame, bg=current_theme["secondary_bg"])
        quality_frame.pack(side=tk.LEFT, padx=10)

        quality_label = tk.Label(quality_frame, text="🎚️ 音质:",
                                 bg=current_theme["secondary_bg"], fg=current_theme["text"],
                                 font=("Microsoft YaHei", 9))
        quality_label.pack(side=tk.LEFT)

        self.quality_var = tk.StringVar(value="Hi-Res")
        quality_combo = ttk.Combobox(quality_frame,
                                     textvariable=self.quality_var,
                                     values=list(QUALITY_OPTIONS.values()),
                                     width=8, state="readonly")
        quality_combo.pack(side=tk.LEFT, padx=5)

        # 2. 播放模式
        mode_frame = tk.Frame(settings_frame, bg=current_theme["secondary_bg"])
        mode_frame.pack(side=tk.LEFT, padx=10)

        mode_label = tk.Label(mode_frame, text="🔀 模式:",
                              bg=current_theme["secondary_bg"], fg=current_theme["text"],
                              font=("Microsoft YaHei", 9))
        mode_label.pack(side=tk.LEFT)

        self.mode_var = tk.StringVar(value="随机播放")
        mode_combo = ttk.Combobox(mode_frame,
                                  textvariable=self.mode_var,
                                  values=list(PLAY_MODES.values()),
                                  width=8, state="readonly")
        mode_combo.pack(side=tk.LEFT, padx=5)

        # 音量控制（放在最右侧）
        volume_frame = tk.Frame(bottom_frame, bg=current_theme["secondary_bg"])
        volume_frame.pack(side=tk.RIGHT, padx=10)

        volume_label = tk.Label(volume_frame, text="🔊",
                                bg=current_theme["secondary_bg"], fg=current_theme["text"],
                                font=("Arial", 12))
        volume_label.pack(side=tk.LEFT)

        self.volume_var = tk.DoubleVar(value=70)
        volume_scale = ttk.Scale(volume_frame, from_=0, to=100,
                                 variable=self.volume_var, orient=tk.HORIZONTAL,
                                 length=80)
        volume_scale.pack(side=tk.LEFT, padx=5)
        volume_scale.bind("<ButtonRelease-1>", self.on_volume_change)

    def _update_playback_scroll_text(self, *args):
        """更新滚动文本显示"""
        text = self.playback_info_var.get()

        # 取消之前的动画
        if self.playback_animation_id:
            self.playback_canvas.after_cancel(self.playback_animation_id)
            self.playback_animation_id = None

        # 更新文本
        self.playback_canvas.itemconfig(self.playback_text_id, text=text)

        # 检查文本是否需要滚动
        self._check_and_start_scroll(text)

    def _check_and_start_scroll(self, text):
        """检查文本长度并启动滚动动画"""
        # 获取文本宽度
        text_bbox = self.playback_canvas.bbox(self.playback_text_id)
        if not text_bbox:
            return

        text_width = text_bbox[2] - text_bbox[0]
        canvas_width = self.playback_canvas.winfo_width()

        # 如果文本宽度大于画布宽度，启动滚动
        if text_width > canvas_width and canvas_width > 0:
            self._start_text_scroll_animation(text_width, canvas_width)
        else:
            # 文本不需要滚动，居右显示
            self.playback_canvas.coords(self.playback_text_id, canvas_width, 10)
            self.playback_canvas.itemconfig(self.playback_text_id, anchor="e")

    def _start_text_scroll_animation(self, text_width, canvas_width):
        """启动文本滚动动画"""
        start_x = canvas_width + 10  # 从右侧开始
        end_x = -text_width - 10  # 滚动到左侧之外

        def animate(position):
            self.playback_canvas.coords(self.playback_text_id, position, 10)

            if position > end_x:
                # 继续滚动
                self.playback_animation_id = self.playback_canvas.after(20, animate, position - 2)
            else:
                # 滚动完成，重置到右侧
                self.playback_animation_id = self.playback_canvas.after(1000, lambda: animate(start_x))

        # 开始动画
        animate(start_x)

    def _on_playback_frame_configure(self, event):
        """当播放信息框架大小改变时重新检查滚动"""
        text = self.playback_info_var.get()
        self._check_and_start_scroll(text)

    def on_theme_change(self, event):
        """切换主题"""
        theme_name_cn = self.theme_var.get()
        theme_key = self.theme_manager.get_theme_key_by_name(theme_name_cn)

        if self.theme_manager.set_theme(theme_key):
            self.apply_theme(theme_key)

    def on_spectrum_mode_change(self, event):
        """切换频谱显示模式"""
        mode = self.spectrum_mode_var.get()

        # 重新创建频谱
        self._create_spectrum_by_mode()

        # 如果正在播放，重新开始频谱动画
        if self.player.is_playing and not self.player.is_paused:
            self._start_spectrum_animation()

    def seek_relative(self, seconds):
        """相对跳转"""
        if hasattr(self.player, 'position'):
            new_position = max(0, self.player.position + seconds)
            self.player.seek(new_position)

    def seek_absolute(self, position):
        """绝对跳转到指定位置"""
        self.player.seek(position)

    def seek_percentage(self, percentage):
        """按百分比跳转"""
        if hasattr(self.player, 'duration') and self.player.duration > 0:
            position = (percentage / 100) * self.player.duration
            self.player.seek(position)

    def seek_to_end(self):
        """跳转到结尾"""
        if hasattr(self.player, 'duration') and self.player.duration > 0:
            self.player.seek(self.player.duration - 1)

    def add_playlist_to_favorites(self):
        """收藏当前播放列表中的所有歌曲"""
        if not self.playlist:
            messagebox.showwarning("提示", "播放列表为空")
            return

        # 统计新增的收藏数量
        added_count = 0
        already_exists_count = 0

        for track in self.playlist:
            track_id = track.get('id')
            # 检查是否已经收藏
            if not any(fav.get('id') == track_id for fav in self.favorites):
                self.favorites.append(track.copy())  # 使用copy避免引用问题
                added_count += 1
            else:
                already_exists_count += 1

        # 保存收藏列表
        if added_count > 0:
            self.save_favorites()

        # 显示结果信息
        if added_count > 0 and already_exists_count > 0:
            message = f"成功收藏 {added_count} 首歌曲，{already_exists_count} 首已存在收藏夹中"
        elif added_count > 0:
            message = f"成功收藏 {added_count} 首歌曲到收藏夹"
        elif already_exists_count > 0:
            message = f"播放列表中的所有 {already_exists_count} 首歌曲都已存在于收藏夹中"
        else:
            message = "没有新增收藏的歌曲"

        messagebox.showinfo("收藏结果", message)
        self._show_playback_info(f"收藏完成: 新增{added_count}首, 已存在{already_exists_count}首")

    def clear_playlist(self):
        """清除播放列表"""
        if messagebox.askyesno("确认", "确定要清除播放列表吗？"):
            # 清空树形视图
            self.left_panel.clear_playlist_tree()
            # 清空播放列表数据
            self.playlist.clear()
            self.current_index = 0
            # 重置高亮状态
            self.current_playlist_item = None
            self.current_playlist_index = -1
            self.left_panel.update_playlist_count(0)

    def _show_playback_info(self, info_text):
        """显示播放状态信息"""
        self.playback_info_var.set(info_text)

    def _show_format_info(self, format_info):
        """显示音频格式信息"""
        self.format_var.set(f"格式: {format_info}")

    def on_position_update(self, position):
        # 过滤无效的位置值
        if position < 0:
            return

        # 获取音频总时长
        total_duration = self.player.duration if hasattr(self.player, 'duration') and self.player.duration > 0 else 180

        # 动态设置进度条的范围
        current_to = self.progress_bar.cget("to")
        if current_to != total_duration:
            self.progress_bar.configure(to=total_duration)

        # 更新进度条
        self.progress_var.set(position)

        # 更新时间显示
        current_time = self.format_time(position)
        total_time = self.format_time(total_duration)

        self.current_time_var.set(current_time)
        self.total_time_var.set(total_time)

        # 更新歌词高亮
        self.album_lyrics_panel.highlight_current_lyric(position, self.current_lyric_var)

        # 检查是否播放完成 - 添加容差
        if total_duration > 0 and position >= max(0, total_duration - 1.0):
            self.on_playback_finished()

    def format_time(self, seconds):
        """格式化时间显示 MM:SS"""
        if seconds < 0:
            return "00:00"

        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"

    def on_progress_change(self, event):
        """进度条拖动"""
        position = self.progress_var.get()
        self.player.seek(position)

    def on_volume_change(self, event):
        """音量调整"""
        volume = self.volume_var.get() / 100.0
        self.player.set_volume(volume)

    def on_playback_finished(self):
        """播放完成回调"""
        # 防止重复触发
        if hasattr(self, '_playback_finished_triggered') and self._playback_finished_triggered:
            return

        self._playback_finished_triggered = True

        print("播放完成")
        self.play_btn.config(text="⏵")
        self.progress_var.set(0)
        self.current_time_var.set("00:00")
        self.playback_info_var.set("播放完成")

        mode_mapping = {v: k for k, v in PLAY_MODES.items()}
        current_mode = self.mode_var.get()
        mode_code = mode_mapping.get(current_mode, "order")

        # 根据播放模式决定下一步
        if mode_code == "single":
            # 单曲循环，重新播放
            if self.current_track:
                self.root.after(500, lambda: self.play_track(self.current_track))
        elif mode_code == "random":
            # 随机播放下一首
            self.root.after(500, self.next_track)
        else:
            # 顺序播放下一首
            self.root.after(500, self.next_track)

        # 重置触发标志
        self.root.after(1000, lambda: setattr(self, '_playback_finished_triggered', False))

    def search_music(self):
        keyword = self.search_var.get().strip()
        if not keyword:
            messagebox.showwarning("提示", "请输入搜索关键词")
            return

        # 显示搜索结果下拉框
        self._show_search_results_dropdown()

        # 在新线程中执行搜索
        threading.Thread(target=self._search_thread, args=(keyword,), daemon=True).start()

    def _show_search_results_dropdown(self):
        """显示搜索结果下拉框 - 美化版本"""
        # 先隐藏之前的下拉框
        self._hide_search_results_dropdown()

        # 获取当前主题
        current_theme = self.theme_manager.get_current_theme()

        # 创建新的下拉框架
        self.search_results_frame = tk.Toplevel(self.root)
        self.search_results_frame.overrideredirect(True)
        self.search_results_frame.configure(bg=current_theme["secondary_bg"])
        self.search_results_frame.attributes("-topmost", True)

        # 设置圆角效果（通过设置合适的边框和背景）
        self.search_results_frame.configure(relief=tk.RAISED, bd=2)

        # 定位在搜索框下方
        root_x = self.root.winfo_rootx()
        root_y = self.root.winfo_rooty()
        root_width = self.root.winfo_width()

        # 计算合适的位置和大小
        dropdown_width = min(700, root_width - 100)  # 最大700px，最小留边距
        dropdown_height = 350  # 固定高度

        # 定位在窗口中央偏上
        x = root_x + (root_width - dropdown_width) // 2
        y = root_y + 120  # 距离顶部120像素

        self.search_results_frame.geometry(f"{dropdown_width}x{dropdown_height}+{x}+{y}")
        self.search_results_visible = True

        # 绑定点击外部隐藏事件
        self.search_results_frame.bind("<FocusOut>", lambda e: self._hide_search_results_dropdown())
        self.root.bind("<Button-1>", self._on_root_click)

    def _on_root_click(self, event):
        """点击窗口其他位置时隐藏下拉框"""
        if (self.search_results_frame and self.search_results_visible and
                not self._is_event_in_widget(event, self.search_results_frame)):
            self._hide_search_results_dropdown()

    def _is_event_in_widget(self, event, widget):
        """检查事件是否发生在指定widget内"""
        try:
            x = widget.winfo_rootx()
            y = widget.winfo_rooty()
            width = widget.winfo_width()
            height = widget.winfo_height()

            return (x <= event.x_root <= x + width and
                    y <= event.y_root <= y + height)
        except:
            return False

    def _hide_search_results_dropdown(self):
        """隐藏搜索结果下拉框"""
        if self.search_results_frame and self.search_results_visible:
            try:
                # 解绑所有事件
                self.search_results_frame.unbind("<MouseWheel>")
                self.root.unbind("<Button-1>")
                self.search_results_frame.destroy()
            except:
                pass
            self.search_results_frame = None
            self.search_results_visible = False

    def _search_thread(self, keyword):
        try:
            source = self.source_var.get()
            # 获取搜索数量
            try:
                count = int(self.search_count_var.get())
            except:
                count = 50  # 默认值

            result = self.api.search(keyword, source=source, count=count)

            print(f"搜索结果: {result}")

            # 修改判断条件
            if result and result.get("code") == 200 and "data" in result and result["data"]:
                self.search_results = result["data"]
                self.root.after(0, self._update_search_results_dropdown)
            else:
                error_msg = result.get("msg", "未找到相关歌曲") if result else "搜索无结果"
                self.root.after(0, lambda: messagebox.showerror("提示", error_msg))

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("错误", f"搜索失败: {str(e)}"))

    def _update_search_results_dropdown(self):
        """更新搜索结果下拉框 - 确保能显示内容的简化美化版"""
        if not self.search_results_frame or not self.search_results_visible:
            return

        # 清空现有内容
        for widget in self.search_results_frame.winfo_children():
            widget.destroy()

        # 获取主题颜色
        theme = self.theme_manager.get_current_theme()
        bg_color = theme["secondary_bg"]
        text_color = theme["text"]
        accent_color = theme["accent"]

        # 设置下拉框背景
        self.search_results_frame.configure(bg=bg_color)

        # 创建标题栏 - 保持简单
        header_frame = tk.Frame(self.search_results_frame, bg=accent_color, height=35)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        header_label = tk.Label(header_frame, text="🔍 搜索结果",
                                bg=accent_color, fg="white",
                                font=("Microsoft YaHei", 11, "bold"))
        header_label.pack(side=tk.LEFT, padx=15, pady=8)

        count_label = tk.Label(header_frame, text=f"共找到 {len(self.search_results)} 首歌曲",
                               bg=accent_color, fg="white",
                               font=("Microsoft YaHei", 9))
        count_label.pack(side=tk.RIGHT, padx=15, pady=8)

        # 如果没有搜索结果
        if not self.search_results:
            no_results_label = tk.Label(self.search_results_frame, text="🎵 未找到相关歌曲",
                                        bg=bg_color, fg=theme["secondary_text"],
                                        font=("Microsoft YaHei", 12))
            no_results_label.pack(expand=True, fill=tk.BOTH, pady=20)
            return

        # 创建滚动框架 - 使用最可靠的实现
        main_frame = tk.Frame(self.search_results_frame, bg=bg_color)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 创建滚动条
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 创建Canvas用于滚动
        canvas = tk.Canvas(main_frame, bg=bg_color, highlightthickness=0, yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar.config(command=canvas.yview)

        # 创建内部框架
        inner_frame = tk.Frame(canvas, bg=bg_color)
        canvas.create_window((0, 0), window=inner_frame, anchor="nw")

        # 配置滚动区域
        def configure_scrollregion(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        inner_frame.bind("<Configure>", configure_scrollregion)

        # 鼠标滚轮事件处理
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        # 绑定鼠标滚轮到整个下拉框和canvas
        self.search_results_frame.bind("<MouseWheel>", _on_mousewheel)
        canvas.bind("<MouseWheel>", _on_mousewheel)
        inner_frame.bind("<MouseWheel>", _on_mousewheel)

        # 递归绑定鼠标滚轮到所有子组件
        def bind_to_children(widget):
            for child in widget.winfo_children():
                child.bind("<MouseWheel>", _on_mousewheel)
                bind_to_children(child)

        bind_to_children(inner_frame)

        # 添加搜索结果
        for i, track in enumerate(self.search_results):
            # 创建歌曲框架 - 使用grid布局确保按钮固定
            song_frame = tk.Frame(inner_frame, bg=bg_color)
            song_frame.pack(fill=tk.X, padx=10, pady=3)

            # 使用grid布局
            song_frame.columnconfigure(0, weight=1)  # 歌曲信息列可扩展
            song_frame.columnconfigure(1, weight=0)  # 按钮列固定宽度

            # 歌曲信息
            song_name = track.get('name', '未知歌曲')
            artist_list = track.get('artist', [])
            if isinstance(artist_list, list) and artist_list:
                artist_str = ' • '.join(artist_list)
            else:
                artist_str = '未知歌手'

            # 创建信息Canvas用于滚动文本
            info_canvas = tk.Canvas(song_frame,
                                    bg=bg_color,
                                    highlightthickness=0,
                                    height=30,  # 固定高度
                                    width=400)  # 固定宽度，超出部分滚动
            info_canvas.grid(row=0, column=0, sticky="ew", padx=(5, 10), pady=5)

            # 在Canvas上创建文本
            full_text = f"{i + 1:2d}. {song_name} - {artist_str}"
            text_id = info_canvas.create_text(0, 15,
                                              text=full_text,
                                              anchor="w",
                                              font=("Microsoft YaHei", 10),
                                              fill=text_color,
                                              tags="text")

            # 检查文本是否需要滚动
            def check_scroll(canvas=info_canvas, text_id=text_id, full_text=full_text):
                canvas.update_idletasks()
                text_bbox = canvas.bbox(text_id)
                if text_bbox and text_bbox[2] > canvas.winfo_width():
                    # 文本过长，启动滚动动画
                    start_scroll_animation(canvas, text_id, text_bbox[2])
                else:
                    # 文本不需要滚动，正常显示
                    canvas.coords(text_id, 5, 15)

            # 滚动动画函数
            def start_scroll_animation(canvas, text_id, text_width):
                canvas_width = canvas.winfo_width()
                start_x = 5
                end_x = -(text_width - canvas_width + 20)

                def animate(position):
                    canvas.coords(text_id, position, 15)
                    if position > end_x:
                        canvas.after(30, animate, position - 1)
                    else:
                        # 滚动完成后等待2秒再重新开始
                        canvas.after(2000, lambda: animate(start_x))

                # 先正常显示3秒再开始滚动
                canvas.after(3000, lambda: animate(start_x))

            # 延迟检查滚动
            canvas.after(100, check_scroll)

            # 按钮容器 - 使用固定宽度
            btn_frame = tk.Frame(song_frame, bg=bg_color)
            btn_frame.grid(row=0, column=1, sticky="e", padx=5)

            # 播放按钮
            play_btn = tk.Button(btn_frame, text="▶ 播放",
                                 command=lambda t=track: self._play_from_dropdown(t),
                                 bg=accent_color, fg="white",
                                 font=("Microsoft YaHei", 8, "bold"),
                                 relief="flat", bd=0,
                                 width=8,  # 固定宽度
                                 padx=8, pady=3)
            play_btn.pack(side=tk.LEFT, padx=2)

            # 添加按钮
            add_btn = tk.Button(btn_frame, text="➕ 添加",
                                command=lambda t=track: self._add_from_dropdown(t),
                                bg="#27ae60", fg="white",
                                font=("Microsoft YaHei", 8, "bold"),
                                relief="flat", bd=0,
                                width=8,  # 固定宽度
                                padx=8, pady=3)
            add_btn.pack(side=tk.LEFT, padx=2)

            # 收藏按钮 - 修正函数调用
            fav_btn = tk.Button(btn_frame, text="❤️ 收藏",
                                command=lambda t=track: self._add_to_favorites_from_dropdown(t),
                                bg="#e74c3c", fg="white",  # 使用红色区分
                                font=("Microsoft YaHei", 8, "bold"),
                                relief="flat", bd=0,
                                width=8,  # 固定宽度
                                padx=8, pady=3)
            fav_btn.pack(side=tk.LEFT, padx=2)

        # 底部操作栏
        bottom_frame = tk.Frame(self.search_results_frame, bg=bg_color, height=40)
        bottom_frame.pack(fill=tk.X, pady=5)
        bottom_frame.pack_propagate(False)

        # 添加全部按钮
        def add_all():
            for track in self.search_results:
                self._add_from_dropdown(track)
            self._hide_search_results_dropdown()
            self._show_playback_info(f"已添加所有 {len(self.search_results)} 首歌曲")

        add_all_btn = tk.Button(bottom_frame, text="📥 添加全部",
                                command=add_all,
                                bg="#27ae60", fg="white",
                                font=("Microsoft YaHei", 9),
                                relief="flat", bd=0,
                                padx=15, pady=5)
        add_all_btn.pack(side=tk.LEFT, padx=15)

        # 收藏全部按钮 - 修正函数名
        def fav_all():
            for track in self.search_results:
                self._add_to_favorites_from_dropdown(track)
            self._hide_search_results_dropdown()
            self._show_playback_info(f"已收藏所有 {len(self.search_results)} 首歌曲")

        fav_all_btn = tk.Button(bottom_frame, text="❤️ 收藏全部",
                                command=fav_all,
                                bg="#e74c3c", fg="white",  # 使用红色
                                font=("Microsoft YaHei", 9),
                                relief="flat", bd=0,
                                padx=15, pady=5)
        fav_all_btn.pack(side=tk.LEFT, padx=15)

        # 关闭按钮
        close_btn = tk.Button(bottom_frame, text="✕ 关闭",
                              command=self._hide_search_results_dropdown,
                              bg="#95a5a6", fg="white",
                              font=("Microsoft YaHei", 9),
                              relief="flat", bd=0,
                              padx=15, pady=5)
        close_btn.pack(side=tk.RIGHT, padx=15)

        # 更新滚动区域
        self.search_results_frame.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))


    def _add_to_favorites_from_dropdown(self, track):
        """从下拉框添加歌曲到收藏"""
        # 检查是否已经收藏
        track_id = track.get('id')
        if any(fav.get('id') == track_id for fav in self.favorites):
            self._show_playback_info("该歌曲已在收藏夹中")
            return

        # 添加到收藏
        self.favorites.append(track)
        self.save_favorites()
        self._show_playback_info(f"已收藏: {track.get('name', '未知歌曲')}")
        self._hide_search_results_dropdown()

    def _add_from_dropdown(self, track):
        """从下拉框添加歌曲"""

        self.add_to_playlist(track)
        self._hide_search_results_dropdown()
        self._show_playback_info(f"已添加: {track.get('name', '未知歌曲')}")

    def _play_from_dropdown(self, track):
        """从下拉框播放歌曲"""
        self.add_to_playlist(track)
        self.current_index = len(self.playlist) - 1
        self.play_track(track)
        self._hide_search_results_dropdown()

    def on_search_double_click(self, event):
        """双击搜索结果 - 添加到播放列表并立即播放"""
        # 这个功能现在在播放列表中处理

    def on_search_single_click(self, event):
        """单击搜索结果 - 只添加到播放列表"""
        # 这个功能现在在下拉框中处理

    def _highlight_current_playlist_item(self, track):
        """高亮显示当前播放的播放列表项 - 使用新的左面板接口"""
        # 查找当前歌曲在播放列表中的索引
        for i, playlist_track in enumerate(self.playlist):
            if (playlist_track.get('id') == track.get('id') and
                    playlist_track.get('name') == track.get('name')):
                self.current_playlist_index = i
                break

        # 在Treeview中找到对应的item并高亮
        if self.current_playlist_index >= 0:
            children = self.left_panel.playlist_tree.get_children()
            if self.current_playlist_index < len(children):
                item = children[self.current_playlist_index]
                self.current_playlist_item = item

                # 设置高亮样式
                self.left_panel.set_playlist_selection(item)
                self.left_panel.set_playlist_focus(item)
                self.left_panel.see_playlist_item(item)

                # 配置高亮颜色
                self.left_panel.configure_playlist_tag('playing', background='#3498DB', foreground='white')
                self.left_panel.set_playlist_item_tags(item, ('playing',))

    def _clear_playlist_highlight(self):
        """清除播放列表的高亮 - 使用新的左面板接口"""
        if self.current_playlist_item:
            try:
                self.left_panel.clear_playlist_selection()
                self.left_panel.set_playlist_item_tags(self.current_playlist_item, ())
            except tk.TclError:
                pass
        self.current_playlist_item = None

    def _ensure_spectrum_exists(self):
        """确保频谱存在，如果不存在则重新创建"""
        if not hasattr(self.album_lyrics_panel, 'spectrum_bars') or not self.album_lyrics_panel.spectrum_bars:
            print("频谱不存在，重新创建...")
            self._create_spectrum_by_mode()

    def play_track(self, track):
        try:
            # 先停止当前播放和动画
            self._playback_finished_triggered = False
            self.player.stop()
            self.set_play_state(False)  # 停止动画

            self._clear_playlist_highlight()

            # 清除之前的歌词高亮
            if hasattr(self.album_lyrics_panel, 'clear_lyrics_highlight'):
                self.album_lyrics_panel.clear_lyrics_highlight()

            self.current_track = track
            self._highlight_current_playlist_item(track)

            # 更新当前播放信息
            artist_list = track.get('artist', [])
            if isinstance(artist_list, list) and artist_list:
                artist_str = ', '.join(artist_list)
            else:
                artist_str = '未知歌手'

            self.current_song_var.set(track.get('name', '未知歌曲'))
            self.current_artist_var.set(artist_str)

            # 设置默认专辑显示
            if hasattr(self.album_lyrics_panel, '_set_default_album_display'):
                self.root.after(0, lambda: self.album_lyrics_panel._set_default_album_display(track))

            # 根据当前频谱模式创建频谱
            self.root.after(0, self._create_spectrum_by_mode)

            # 获取播放链接
            source = self.source_var.get()
            quality = self.quality_var.get()

            def play_thread():
                try:
                    # 获取播放URL
                    url_result = self.api.get_song_url(track['id'], source=source, quality=quality)
                    print(f"URL获取结果: {url_result}")

                    if url_result and 'url' in url_result:
                        url = url_result['url']
                        file_format = url_result.get('format', '未知')

                        if not url or not url.startswith('http'):
                            self.root.after(0, self.next_track)
                            return

                        # 显示格式信息
                        quality_name = QUALITY_OPTIONS.get(quality, quality)
                        format_info = f"{quality_name}({file_format})"
                        self.root.after(0, lambda: self._show_format_info(format_info))

                        print(f"开始加载音乐URL: {url}, 格式: {file_format}")

                        # 显示加载状态
                        self.root.after(0, lambda: self._show_playback_info("正在加载音频..."))

                        # 加载并播放
                        if self.player.load(url):
                            # 显示加载成功信息
                            status = self.player.get_status()
                            backend = status.get('backend', '未知')
                            final_format = status.get('format', '未知')

                            load_info = f"加载成功 - {backend}"
                            self.root.after(0, lambda: self._show_playback_info(load_info))

                            # 开始播放
                            if self.player.play():
                                # 重要：在这里启动旋转和频谱动画，确保音乐真的在播放
                                self.root.after(0, lambda: self.set_play_state(True))
                                # 显示播放信息
                                play_info = f"正在播放 {quality_name}"
                                self.root.after(0, lambda: self._show_playback_info(play_info))
                                self.root.after(0, lambda: self.play_btn.config(text="⏸"))

                                print("音乐开始播放，启动专辑图旋转和频谱动画")
                            else:
                                self.root.after(0, lambda: messagebox.showerror("错误", "播放启动失败"))
                                self.root.after(0, lambda: self._show_playback_info("播放失败"))
                        else:
                            error_msg = f"音乐加载失败，格式: {file_format}"
                            self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
                            self.root.after(0, lambda: self._show_playback_info("加载失败"))

                    else:
                        error_msg = url_result.get('msg', '无法获取播放链接') if url_result else '获取播放链接失败'
                        self.root.after(0, lambda: messagebox.showerror("错误", f"获取播放链接失败: {error_msg}"))
                        self.root.after(0, lambda: self._show_playback_info("获取链接失败"))

                    # 获取专辑图片
                    if 'pic_id' in track:
                        try:
                            pic_result = self.api.get_album_pic(track['pic_id'], source=source)
                            if pic_result and 'url' in pic_result:
                                # 使用新的专辑面板加载图片
                                self.root.after(0, lambda: self.album_lyrics_panel.load_album_image(
                                    pic_result['url'], track))
                        except Exception as e:
                            print(f"获取专辑图片失败: {e}")
                    self._create_spectrum_by_mode()
                    self._start_spectrum_animation()

                    # 获取歌词
                    lyric_id = track.get('lyric_id', track['id'])
                    try:
                        lyric_result = self.api.get_lyrics(lyric_id, source=source)
                        if lyric_result:
                            # 使用新的专辑面板更新歌词
                            self.root.after(0, lambda: self.album_lyrics_panel.update_lyrics(lyric_result))
                    except Exception as e:
                        print(f"获取歌词失败: {e}")

                except Exception as e:
                    error_msg = f"播放失败: {str(e)}"
                    print(error_msg)
                    self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
                    self.root.after(0, lambda: self._show_playback_info("播放异常"))

            # 启动播放线程
            threading.Thread(target=play_thread, daemon=True).start()

        except Exception as e:
            error_msg = f"播放失败: {str(e)}"
            print(error_msg)
            messagebox.showerror("错误", error_msg)
            self._show_playback_info("播放异常")

    def _create_spectrum_by_mode(self):
        """根据当前模式创建频谱"""
        if not hasattr(self.album_lyrics_panel, '_clear_spectrum'):
            return

        # 清除现有频谱
        self.album_lyrics_panel._clear_spectrum()

        # 获取当前频谱模式
        mode = self.spectrum_mode_var.get()

        # 根据模式创建频谱
        if mode == "条形":
            if hasattr(self.album_lyrics_panel, 'create_spectrum'):
                self.album_lyrics_panel.create_spectrum()
        elif mode == "圆形":
            if hasattr(self.album_lyrics_panel, 'create_advanced_spectrum'):
                self.album_lyrics_panel.create_advanced_spectrum()
        elif mode == "瀑布流":
            if hasattr(self.album_lyrics_panel, 'create_waterfall_spectrum'):
                self.album_lyrics_panel.create_waterfall_spectrum()

    def _start_spectrum_animation(self):
        """启动频谱动画"""
        if not hasattr(self.album_lyrics_panel, 'is_rotating') or not self.album_lyrics_panel.is_rotating:
            return

        # 获取当前频谱模式
        mode = self.spectrum_mode_var.get()

        # 根据模式启动对应的频谱动画
        if mode == "条形":
            if hasattr(self.album_lyrics_panel, 'update_spectrum'):
                self.album_lyrics_panel.update_spectrum()
        elif mode == "圆形":
            if hasattr(self.album_lyrics_panel, 'update_advanced_spectrum'):
                self.album_lyrics_panel.update_advanced_spectrum()
        elif mode == "瀑布流":
            if hasattr(self.album_lyrics_panel, 'update_waterfall_spectrum'):
                self.album_lyrics_panel.update_waterfall_spectrum()

    def toggle_play(self):
        if self.player.is_playing:
            if self.player.is_paused:
                self.player.unpause()
                self.play_btn.config(text="⏸")
                self._show_playback_info("继续播放")
                self.set_play_state(True)
            else:
                self.player.pause()
                self.play_btn.config(text="⏵")
                self._show_playback_info("已暂停")
                self.set_play_state(False)
        else:
            if self.current_track:
                self.play_track(self.current_track)
            elif self.playlist:
                self._play_random_from_playlist()
            else:
                self._show_playback_info("播放列表为空，请先添加歌曲")
                self._play_default_audio()

    def _play_default_audio(self):
        """播放默认音频文件"""
        try:
            import os

            # 默认音频文件路径
            default_audio_path = "temp_audio.mp3"

            # 检查文件是否存在
            if not os.path.exists(default_audio_path):
                print(f"默认音频文件不存在: {default_audio_path}")
                self._show_playback_info("默认音频文件不存在")
                return

            print(f"开始播放默认音频: {default_audio_path}")

            # 创建默认的track信息
            default_track = {
                'id': 'default_audio',
                'name': '默认音频',
                'artist': ['系统'],
                'album': '默认',
                'pic_id': None,
                'lyric_id': None
            }

            # 设置当前track
            self.current_track = default_track

            # 更新UI显示
            self.current_song_var.set("默认音频")
            self.current_artist_var.set("系统")

            # 设置默认专辑显示
            if hasattr(self.album_lyrics_panel, '_set_default_album_display'):
                self.album_lyrics_panel._set_default_album_display(default_track)

            # 清除之前的歌词
            if hasattr(self.album_lyrics_panel, 'clear_lyrics_display'):
                self.album_lyrics_panel.clear_lyrics_display()

            # 在新线程中播放本地文件
            threading.Thread(target=self._play_default_audio_thread,
                             args=(default_audio_path, default_track),
                             daemon=True).start()

        except Exception as e:
            print(f"播放默认音频失败: {e}")
            self._show_playback_info("默认音频播放失败")

    def _play_default_audio_thread(self, audio_path, track_info):
        """在新线程中播放默认音频"""
        try:
            # 显示加载状态
            self.root.after(0, lambda: self._show_playback_info("正在加载默认音频..."))

            # 使用新的load_file方法加载本地文件
            if self.player.load_file(audio_path):
                # 显示加载成功信息
                status = self.player.get_status()
                backend = status.get('backend', '未知')
                file_format = status.get('format', '未知')

                load_info = f"默认音频加载成功 - {backend}"
                self.root.after(0, lambda: self._show_playback_info(load_info))
                self.root.after(0, lambda: self._show_format_info(f"本地({file_format})"))

                # 开始播放
                if self.player.play():
                    # 启动旋转和频谱动画
                    self.root.after(0, lambda: self.set_play_state(True))
                    self.root.after(0, lambda: self.play_btn.config(text="⏸"))
                    self.root.after(0, lambda: self._show_playback_info("正在播放默认音频"))

                    print("默认音频开始播放")
                else:
                    self.root.after(0, lambda: self._show_playback_info("默认音频播放失败"))
            else:
                self.root.after(0, lambda: self._show_playback_info("默认音频加载失败"))

        except Exception as e:
            print(f"播放默认音频线程失败: {e}")
            self.root.after(0, lambda: self._show_playback_info("默认音频播放异常"))

    def _play_random_from_playlist(self):
        """从播放列表中随机选择一首歌曲播放"""
        import random
        if self.playlist:
            # 随机选择一个索引
            random_index = random.randint(0, len(self.playlist) - 1)
            self.current_index = random_index
            track = self.playlist[random_index]
            self.play_track(track)
            self._show_playback_info("随机播放")
        else:
            self._show_playback_info("播放列表为空")

    def stop_play(self):
        self.player.stop()
        self.play_btn.config(text="⏵")
        self.progress_var.set(0)
        self.current_time_var.set("00:00")
        self.total_time_var.set("00:00")
        self._show_playback_info("已停止")
        self.album_lyrics_panel.clear_lyrics_highlight()
        self.set_play_state(False)

    def previous_track(self):
        """上一首 - 根据播放模式"""
        if not self.playlist:
            return

        mode_mapping = {v: k for k, v in PLAY_MODES.items()}
        current_mode = self.mode_var.get()
        mode_code = mode_mapping.get(current_mode, "order")

        if mode_code == "random":
            # 随机播放模式
            import random
            self.current_index = random.randint(0, len(self.playlist) - 1)
        else:
            # 顺序播放或单曲循环模式
            if self.current_index > 0:
                self.current_index -= 1
            else:
                # 如果是第一首，根据模式决定是否循环到最后一首
                if mode_code == "order":
                    self.current_index = 0  # 停留在第一首
                else:  # 单曲循环或列表循环
                    self.current_index = len(self.playlist) - 1  # 循环到最后一首

        track = self.playlist[self.current_index]
        self.play_track(track)

    def next_track(self):
        """下一首 - 根据播放模式"""
        if not self.playlist:
            return

        mode_mapping = {v: k for k, v in PLAY_MODES.items()}
        current_mode = self.mode_var.get()
        mode_code = mode_mapping.get(current_mode, "order")

        if mode_code == "random":
            # 随机播放模式
            import random
            self.current_index = random.randint(0, len(self.playlist) - 1)
        else:
            # 顺序播放或单曲循环模式
            if self.current_index < len(self.playlist) - 1:
                self.current_index += 1
            else:
                # 如果是最后一首，根据模式决定是否循环到第一首
                if mode_code == "order":
                    self.current_index = len(self.playlist) - 1  # 停留在最后一首
                else:  # 单曲循环或列表循环
                    self.current_index = 0  # 循环到第一首

        track = self.playlist[self.current_index]
        self.play_track(track)

    def update_playlist_count(self):
        """更新播放列表计数"""
        count = len(self.playlist)
        self.left_panel.update_playlist_count(count)

    def add_to_playlist(self, track):
        """添加到播放列表 - 使用新的左面板接口"""
        # 检查是否已存在
        track_id = track.get('id')
        if any(t.get('id') == track_id for t in self.playlist):
            print(f"歌曲已存在: {track.get('name')}")
            return

        self.playlist.append(track)

        # 处理艺术家信息
        artist_list = track.get('artist', [])
        if isinstance(artist_list, list) and artist_list:
            artist_str = ', '.join(artist_list)
        else:
            artist_str = '未知歌手'

        # 插入播放列表项
        item = self.left_panel.insert_playlist_item((
            len(self.playlist),
            track.get('name', '未知歌曲'),
            artist_str,
            track.get('album', '未知专辑')
        ))

        # 如果是当前播放的歌曲，立即高亮
        if (self.current_track and
                track.get('id') == self.current_track.get('id') and
                track.get('name') == self.current_track.get('name')):
            self.current_playlist_item = item
            self.left_panel.set_playlist_selection(item)
            self.left_panel.set_playlist_item_tags(item, ('playing',))
            self.left_panel.configure_playlist_tag('playing', background='#3498DB', foreground='white')

        self.left_panel.update_playlist_count(len(self.playlist))

    def on_playlist_double_click(self, event):
        """播放列表双击事件 - 使用新的左面板接口"""
        selection = self.left_panel.get_playlist_selection()
        if selection:
            item = selection[0]
            values = self.left_panel.playlist_item_values(item)
            index = int(values[0]) - 1

            if 0 <= index < len(self.playlist):
                self.current_index = index
                track = self.playlist[index]
                self.play_track(track)

    def set_play_state(self, is_playing):
        """设置播放状态，控制旋转和频谱"""
        print(f"设置播放状态: {is_playing}")
        try:
            if is_playing:
                # 延迟一点启动，确保专辑图片已经加载
                self.root.after(200, self._delayed_start_animation)
            else:
                # 立即停止
                self._stop_animation()
        except Exception as e:
            print(f"设置播放状态时出错: {e}")

    def _delayed_start_animation(self):
        """延迟启动动画，确保专辑图片已准备好"""
        print("延迟启动动画")
        if hasattr(self.album_lyrics_panel, 'start_rotation'):
            self.album_lyrics_panel.start_rotation()
        if hasattr(self.album_lyrics_panel, 'update_spectrum'):
            self.album_lyrics_panel.update_spectrum()

    def _stop_animation(self):
        """停止动画"""
        print("停止动画")
        if hasattr(self.album_lyrics_panel, 'stop_rotation'):
            self.album_lyrics_panel.stop_rotation()
        if (hasattr(self.album_lyrics_panel, 'spectrum_animation_id') and
                hasattr(self.album_lyrics_panel, 'album_canvas')):
            if self.album_lyrics_panel.spectrum_animation_id:
                try:
                    self.album_lyrics_panel.album_canvas.after_cancel(
                        self.album_lyrics_panel.spectrum_animation_id
                    )
                    self.album_lyrics_panel.spectrum_animation_id = None
                except Exception as e:
                    print(f"停止频谱动画时出错: {e}")

    def apply_theme(self, theme_name):
        """应用主题到所有UI组件"""
        theme = self.theme_manager.get_theme(theme_name)
        if not theme:
            return

        try:
            # 应用主题到左面板
            if hasattr(self, 'left_panel'):
                self.left_panel.apply_theme(theme_name)

            # 应用主题到专辑歌词面板
            if hasattr(self, 'album_lyrics_panel') and hasattr(self.album_lyrics_panel, 'change_theme'):
                self.album_lyrics_panel.change_theme(theme_name)

            # 应用主题到主窗口和主要框架
            self._apply_theme_to_widgets(theme)

            # 更新Treeview样式
            self._update_treeview_style(theme)

            # 更新按钮样式
            self._update_button_styles(theme)

            # 更新控制栏背景
            self._update_control_bar(theme)

            # 强制刷新UI
            self.root.update_idletasks()

            print(f"已切换到 {self.theme_manager.theme_names[theme_name]} 主题")

        except Exception as e:
            print(f"切换主题时出错: {e}")

    def _update_control_bar(self, theme):
        """更新控制栏颜色"""
        try:
            if hasattr(self, 'control_frame'):
                self.control_frame.configure(bg=theme["secondary_bg"])

            # 更新控制栏内的所有框架
            control_frames = [
                'top_frame', 'progress_frame', 'time_progress_frame',
                'bottom_frame', 'button_frame', 'right_frame',
                'volume_frame', 'spectrum_frame', 'theme_frame',
                'info_frame', 'lyric_frame', 'status_frame'
            ]

            for frame_name in control_frames:
                if hasattr(self, frame_name):
                    frame = getattr(self, frame_name)
                    try:
                        frame.configure(bg=theme["secondary_bg"])
                    except:
                        pass

            # 更新控制栏内的标签
            control_labels = [
                'volume_label', 'spectrum_label', 'theme_label',
                'song_label', 'artist_label', 'playback_info_label',
                'format_label', 'current_time_label', 'total_time_label'
            ]

            for label_name in control_labels:
                if hasattr(self, label_name):
                    label = getattr(self, label_name)
                    try:
                        label.configure(bg=theme["secondary_bg"], fg=theme["text"])
                    except:
                        pass

            # 特别更新歌词显示标签
            self._update_lyric_display(theme)

        except Exception as e:
            print(f"更新控制栏时出错: {e}")

    def _update_lyric_display(self, theme):
        """更新歌词显示组件的颜色"""
        try:
            # 更新当前播放歌词标签
            if hasattr(self, 'current_lyric_label'):
                self.current_lyric_label.configure(
                    bg=theme["secondary_bg"],
                    fg=theme["accent"]
                )

        except Exception as e:
            print(f"更新歌词显示时出错: {e}")

    def _apply_theme_to_widgets(self, theme):
        """应用主题到各个UI组件"""
        # 主窗口背景
        self.root.configure(bg=theme["bg"])

        # 遍历所有子组件并应用主题
        self._apply_theme_recursive(self.root, theme)

    def _apply_theme_recursive(self, widget, theme):
        """递归应用主题到所有子组件"""
        try:
            widget_type = widget.winfo_class()

            # 根据组件类型应用主题
            if widget_type in ['Frame', 'Labelframe', 'TFrame']:
                try:
                    # 根据widget的用途判断使用哪种背景色
                    widget_path = str(widget)
                    if any(keyword in widget_path for keyword in
                           ['control', 'progress', 'bottom', 'top', 'info', 'lyric', 'status']):
                        widget.configure(bg=theme["secondary_bg"])
                    elif any(keyword in widget_path for keyword in
                             ['search', 'playlist', 'header']):
                        widget.configure(bg=theme["secondary_bg"])
                    else:
                        widget.configure(bg=theme["bg"])
                except tk.TclError:
                    pass

            elif widget_type in ['Label']:
                try:
                    current_text = widget.cget('text')
                    widget_path = str(widget)

                    # 歌词标签特殊处理
                    if (widget == getattr(self, 'current_lyric_label', None) or
                            'lyric' in widget_path.lower()):
                        widget.configure(bg=theme["secondary_bg"], fg=theme["accent"])
                    # 标题标签
                    elif any(icon in current_text for icon in ['🎵', '🔍', '🎚️', '🔀', '📊', '🎨']):
                        widget.configure(bg=theme["secondary_bg"], fg=theme["text"])
                    # 控制栏内的其他标签
                    elif any(keyword in widget_path for keyword in
                             ['control', 'progress', 'bottom', 'top', 'info', 'status']):
                        widget.configure(bg=theme["secondary_bg"], fg=theme["text"])
                    else:
                        # 普通标签
                        widget.configure(bg=theme.get('bg', theme["bg"]), fg=theme["text"])
                except (tk.TclError, AttributeError):
                    pass

            elif widget_type in ['Button']:
                try:
                    current_text = widget.cget('text')
                    if '🔍' in current_text:
                        # 搜索按钮
                        widget.configure(bg=theme["accent"], fg="white")
                    elif '🗑️' in current_text:
                        # 清除按钮
                        widget.configure(bg="#e74c3c", fg="white")  # 保持红色
                    else:
                        # 普通按钮
                        widget.configure(bg=theme["button_bg"], fg=theme["text"])
                except tk.TclError:
                    pass

            elif widget_type in ['Entry']:
                try:
                    widget.configure(bg=theme["tertiary_bg"], fg=theme["text"],
                                     insertbackground=theme["text"])
                except tk.TclError:
                    pass

            elif widget_type in ['Scale']:
                try:
                    widget.configure(troughcolor=theme["progress_bg"])
                except tk.TclError:
                    pass

        except Exception as e:
            # 忽略所有应用主题时的错误
            pass

        # 递归处理子组件
        try:
            for child in widget.winfo_children():
                self._apply_theme_recursive(child, theme)
        except:
            pass

    def _update_treeview_style(self, theme):
        """更新Treeview样式"""
        self.style.configure("Treeview",
                             background=theme["tertiary_bg"],
                             foreground=theme["text"],
                             fieldbackground=theme["tertiary_bg"],
                             rowheight=25,
                             borderwidth=0,
                             font=("Microsoft YaHei", 10))

        self.style.configure("Treeview.Heading",
                             background=theme["secondary_bg"],
                             foreground=theme["text"],
                             font=("Microsoft YaHei", 11, "bold"),
                             relief="flat",
                             borderwidth=1)

        self.style.map("Treeview",
                       background=[('selected', theme["accent"])],
                       foreground=[('selected', 'white')])

        self.style.configure("Vertical.TScrollbar",
                             background=theme["tertiary_bg"],
                             darkcolor=theme["secondary_bg"],
                             lightcolor=theme["secondary_bg"],
                             troughcolor=theme["secondary_bg"],
                             bordercolor=theme["secondary_bg"],
                             arrowcolor=theme["text"])

    def _update_button_styles(self, theme):
        """更新圆形按钮样式"""
        try:
            # 更新播放按钮
            if hasattr(self, 'play_btn'):
                self.play_btn.config(
                    normal_bg=theme["accent"],
                    normal_fg="white",
                    hover_bg=theme["button_hover"],
                    hover_fg="white",
                    click_bg=theme["accent"]
                )

            # 更新其他控制按钮
            control_buttons = ['prev_btn', 'next_btn', 'stop_btn']
            for btn_name in control_buttons:
                if hasattr(self, btn_name):
                    btn = getattr(self, btn_name)
                    btn.config(
                        normal_bg=theme["button_bg"],
                        normal_fg=theme["text"],
                        hover_bg=theme["button_hover"],
                        hover_fg="white",
                        click_bg=theme["button_hover"]
                    )

            # 强制更新画布背景色
            self._update_canvas_backgrounds(theme)

        except Exception as e:
            print(f"更新按钮样式时出错: {e}")

    def _update_canvas_backgrounds(self, theme):
        """更新Canvas组件的背景色"""
        try:
            # 更新所有圆形按钮的画布背景
            buttons = [self.play_btn, self.prev_btn, self.next_btn, self.stop_btn]
            for button in buttons:
                if hasattr(button, 'canvas'):
                    button.canvas.configure(bg=theme["secondary_bg"])
        except Exception as e:
            print(f"更新画布背景时出错: {e}")

