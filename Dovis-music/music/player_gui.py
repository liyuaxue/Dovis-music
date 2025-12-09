import tkinter as tk
from tkinter import ttk, messagebox
import threading
from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageFilter
import io,os
import requests
import json
from typing import Optional, Dict, Any, List
from music_api import MusicAPI
from audio_player import AudioPlayer
from lyrics_manager import LyricsManager
from album_lyrics_panel import AlbumLyricsPanel
from left_panel import LeftPanel
from config import THEMES, THEME_NAMES, DEFAULT_THEME, MUSIC_SOURCES, QUALITY_OPTIONS, PLAY_MODES
from circular_button import CircularButton
from config_manager import ConfigManager
from logger_config import setup_logger
from cache_manager import CacheManager
from control_bar_ui import ControlBarUI
from search_ui import SearchUI
from playback_service import PlaybackService


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
        self.logger = setup_logger("DovisMusic", log_file="logs/dovis_music.log")
        self.logger.info("初始化音乐播放器...")
        
        self.config = ConfigManager()
        self.cache_manager = CacheManager()
        
        self.current_playlist_item = None
        self.current_playlist_index = -1
        self._playback_finished_triggered = False
        self._is_seeking = False
        
        default_search_count = str(self.config.get_search_count())
        self.search_count_var = tk.StringVar(value=default_search_count)
        self.current_lyric_var = None
        self.current_lyric_label = None

        self.root = root
        self.root.title("Dovis-music")
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        window_width = min(1200, int(screen_width * 0.9))
        window_height = min(900, int(screen_height * 0.9))
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.root.minsize(800, 600)
        self.root.bind("<Configure>", self._on_window_resize)
        self._last_width = window_width
        self._last_height = window_height
        self.root.configure(bg="#f0f0f0")

        self.theme_manager = ThemeManager()
        saved_theme = self.config.get_theme()
        if saved_theme:
            self.theme_manager.set_theme(saved_theme)

        self.api = MusicAPI()
        self.player = AudioPlayer()
        self.lyrics_manager = LyricsManager()

        self.search_results = []
        self.current_track = None
        self.playlist = []
        self.current_index = 0
        self.favorites_file = "favorites.json"
        self.favorites = self.load_favorites()
        self.search_results_frame = None
        self.search_results_visible = False
        self.player.update_callback = self.on_position_update
        
        saved_volume = self.config.get_volume()
        if saved_volume:
            self.player.set_volume(saved_volume)

        self.current_song_var = tk.StringVar(value="")
        self.current_artist_var = tk.StringVar(value="")
        self.playback_info_var = tk.StringVar(value="准备就绪")
        self.format_var = tk.StringVar(value="格式: 未知")
        self.current_time_var = tk.StringVar(value="00:00")
        self.total_time_var = tk.StringVar(value="00:00")
        self.progress_var = tk.DoubleVar()
        
        saved_volume = self.config.get_volume()
        volume_percent = int(saved_volume * 100) if saved_volume else 70
        self.volume_var = tk.DoubleVar(value=volume_percent)
        self.current_lyric_var = tk.StringVar(value="")
        
        saved_quality = self.config.get_quality()
        quality_name = QUALITY_OPTIONS.get(saved_quality, "Hi-Res")
        self.quality_var = tk.StringVar(value=quality_name)
        
        saved_play_mode = self.config.get_play_mode()
        mode_name = PLAY_MODES.get(saved_play_mode, "顺序播放")
        self.mode_var = tk.StringVar(value=mode_name)
        
        saved_spectrum_mode = self.config.get_spectrum_mode()
        self.spectrum_mode_var = tk.StringVar(value=saved_spectrum_mode)
        
        saved_theme_key = self.config.get_theme()
        saved_theme_name = self.theme_manager.theme_names.get(saved_theme_key, self.theme_manager.theme_names[DEFAULT_THEME])
        self.theme_var = tk.StringVar(value=saved_theme_name)
        
        saved_source = self.config.get_source()
        source_name = MUSIC_SOURCES.get(saved_source, "网易云音乐")
        self.source_var = tk.StringVar(value=source_name)
        self.search_var = tk.StringVar()
        self.album_lyrics_panel = None
        self.playback_service = None

        self.create_ui()
        
        theme_to_apply = saved_theme if saved_theme else "light"
        self.root.after(100, lambda: self.apply_theme(theme_to_apply))
        self.root.after(1000, self.auto_search_hot_songs)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.logger.info("音乐播放器初始化完成")

    def clear_favorites(self):
        """清空收藏夹"""
        if not self.favorites:
            messagebox.showinfo("提示", "收藏夹已经是空的")
            return

        if messagebox.askyesno("确认清空", "确定要清空收藏夹吗？此操作不可恢复！"):
            self.favorites.clear()
            self.save_favorites()
            messagebox.showinfo("成功", "收藏夹已清空")
            self.logger.info("收藏夹已清空")

    def show_favorites(self):
        """显示收藏夹"""
        # 重新加载收藏列表
        self.favorites = self.load_favorites()

        if not self.favorites:
            self._show_playback_info("收藏夹为空")
            return

        # 将收藏歌曲显示到播放列表
        self._update_playlist_with_tracks(self.favorites, "收藏夹")

    def load_favorites(self) -> List[Dict[str, Any]]:
        """加载收藏列表"""
        try:
            if os.path.exists(self.favorites_file):
                with open(self.favorites_file, 'r', encoding='utf-8') as f:
                    favorites_data = json.load(f)
                    self.logger.info(f"成功加载收藏列表，共 {len(favorites_data)} 首歌曲")
                    return favorites_data
            else:
                self.logger.debug("收藏文件不存在，创建空列表")
                return []
        except (IOError, OSError, json.JSONDecodeError) as e:
            self.logger.error(f"加载收藏列表失败: {e}", exc_info=True)
            return []

    def save_favorites(self) -> bool:
        """保存收藏列表"""
        try:
            with open(self.favorites_file, 'w', encoding='utf-8') as f:
                json.dump(self.favorites, f, ensure_ascii=False, indent=2)
            self.logger.info(f"成功保存收藏列表，共 {len(self.favorites)} 首歌曲")
            return True
        except (IOError, OSError) as e:
            self.logger.error(f"保存收藏列表失败: {e}", exc_info=True)
            return False
    
    def _on_window_resize(self, event):
        """窗口大小变化处理"""
        if event.widget != self.root:
            return
        
        current_width = self.root.winfo_width()
        current_height = self.root.winfo_height()
        
        if current_width != self._last_width or current_height != self._last_height:
            self._last_width = current_width
            self._last_height = current_height
            
            if hasattr(self, 'album_lyrics_panel') and self.album_lyrics_panel:
                self.root.after(100, self._refresh_album_display)
    
    def _refresh_album_display(self):
        """刷新专辑显示以适应新窗口大小"""
        try:
            if hasattr(self, 'album_lyrics_panel') and self.album_lyrics_panel:
                if hasattr(self.album_lyrics_panel, '_set_default_album_display'):
                    if self.current_track:
                        self.album_lyrics_panel._set_default_album_display(self.current_track)
                    else:
                        self.album_lyrics_panel._set_default_album_display()
        except Exception as e:
            self.logger.error(f"刷新专辑显示失败: {e}", exc_info=True)
    
    def on_closing(self):
        """窗口关闭时的处理"""
        try:
            # 保存当前所有配置
            self.config.set_theme(self.theme_manager.current_theme, auto_save=False)
            self.config.set_volume(self.player.volume, auto_save=False)
            
            # 保存音源（从中文名称转换为键）
            source_name = self.source_var.get()
            source_mapping = {v: k for k, v in MUSIC_SOURCES.items()}
            source_key = source_mapping.get(source_name, "netease")
            self.config.set_source(source_key, auto_save=False)
            
            # 保存音质（从中文名称转换为键）
            quality_name = self.quality_var.get()
            quality_mapping = {v: k for k, v in QUALITY_OPTIONS.items()}
            quality_key = quality_mapping.get(quality_name, "999")
            self.config.set_quality(quality_key, auto_save=False)
            
            # 保存播放模式（从中文名称转换为键）
            mode_name = self.mode_var.get()
            mode_mapping = {v: k for k, v in PLAY_MODES.items()}
            mode_key = mode_mapping.get(mode_name, "order")
            self.config.set_play_mode(mode_key, auto_save=False)
            
            # 保存搜索数量
            try:
                search_count = int(self.search_count_var.get())
                self.config.set_search_count(search_count, auto_save=False)
            except (ValueError, AttributeError, tk.TclError):
                pass
            
            # 保存频谱模式
            spectrum_mode = self.spectrum_mode_var.get()
            self.config.set_spectrum_mode(spectrum_mode, auto_save=False)
            
            # 一次性保存所有配置
            self.config.save_config()
            self.logger.info("配置已保存")
            
            # 停止播放
            self.player.stop()
            
            # 清理资源
            self.player.cleanup()
            
            # 关闭窗口
            self.root.destroy()
        except Exception as e:
            self.logger.error(f"关闭窗口时出错: {e}", exc_info=True)
            self.root.destroy()

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
            if count < 1 or count > 200:
                self.logger.warning(f"搜索数量超出范围: {count}，使用默认值50")
                count = 50
        except (ValueError, AttributeError, tk.TclError) as e:
            self.logger.error(f"解析搜索数量失败: {e}，使用默认值50")
            count = 50

        # 在新线程中执行搜索
        threading.Thread(target=self._search_and_display_thread, args=(keyword, list_name, count), daemon=True).start()

    def _search_and_display_thread(self, keyword, list_name, count=50):
        """搜索并显示线程"""
        try:
            result = self.api.search(keyword, source="网易云音乐", count=count)

            # 处理搜索结果
            tracks = []
            if isinstance(result, list):
                # 直接返回列表的情况
                tracks = result
                self.logger.debug(f"收到列表格式结果，包含 {len(tracks)} 首歌曲")
            elif isinstance(result, dict):
                # 字典格式
                if result.get("code") == 200:
                    if "data" in result and result["data"]:
                        tracks = result["data"] if isinstance(result["data"], list) else []
                    else:
                        self.logger.warning(f"搜索 '{keyword}' 返回成功但data为空")
                else:
                    error_msg = result.get("msg", "未知错误")
                    self.logger.warning(f"搜索 '{keyword}' 失败: code={result.get('code')}, msg={error_msg}")
            else:
                self.logger.warning(f"搜索 '{keyword}' 返回了意外的格式: {type(result)}")

            if tracks:
                # 在主线程中更新播放列表
                self.root.after(0, lambda: self._update_playlist_with_tracks(tracks, list_name))
            else:
                self.root.after(0, lambda: self._show_playback_info(f"加载{list_name}失败：未找到歌曲"))

        except Exception as e:
            self.logger.error(f"加载{list_name}失败: {e}", exc_info=True)
            self.root.after(0, lambda: self._show_playback_info(f"加载{list_name}失败"))

    def _update_playlist_with_tracks(self, tracks, list_name):
        """用指定歌曲更新播放列表"""
        try:
            # 更新播放列表标题
            if hasattr(self.left_panel, 'update_playlist_title'):
                self.left_panel.update_playlist_title(list_name)
            
            # 清空当前播放列表
            self.left_panel.clear_playlist_tree()
            self.playlist.clear()

            # 添加歌曲到播放列表
            for track in tracks:
                self.add_to_playlist(track)

            # 显示成功信息
            song_count = len(tracks)
            self._show_playback_info(f"已加载 {song_count} 首{list_name}歌曲")
            self.logger.info(f"成功添加 {song_count} 首{list_name}歌曲到播放列表")
        except Exception as e:
            self.logger.error(f"更新播放列表失败: {e}", exc_info=True)
            self._show_playback_info("播放列表更新失败")

    def auto_search_hot_songs(self):
        """自动搜索热门歌曲并添加到播放列表"""
        self.logger.info("正在自动搜索热门歌曲...")
        self._show_playback_info("正在加载热门歌曲...")

        # 在新线程中执行搜索
        threading.Thread(target=self._auto_search_thread, daemon=True).start()

    def _auto_search_thread(self,count =50):
        """自动搜索线程"""
        try:
            # 使用多个热门关键词来获取更多歌曲
            hot_keywords = ["热门歌曲", "抖音热歌", "流行音乐", "华语金曲"]

            all_tracks = []

            for keyword in hot_keywords:
                try:
                    self.logger.debug(f"搜索热门关键词: {keyword}")
                    result = self.api.search(keyword, source="网易云音乐", count=count)

                    # 调试：记录返回结果类型
                    self.logger.debug(f"搜索结果类型: {type(result)}, 内容: {str(result)[:200]}")

                    # 处理搜索结果
                    tracks = []
                    if isinstance(result, list):
                        # 直接返回列表的情况
                        tracks = result
                        self.logger.debug(f"收到列表格式结果，包含 {len(tracks)} 首歌曲")
                    elif isinstance(result, dict):
                        # 字典格式
                        if result.get("code") == 200:
                            if "data" in result and result["data"]:
                                tracks = result["data"] if isinstance(result["data"], list) else []
                            else:
                                self.logger.warning(f"关键词 '{keyword}' 返回成功但data为空")
                        else:
                            error_msg = result.get("msg", "未知错误")
                            self.logger.warning(f"关键词 '{keyword}' 搜索失败: code={result.get('code')}, msg={error_msg}")
                    else:
                        self.logger.warning(f"关键词 '{keyword}' 返回了意外的格式: {type(result)}")

                    if tracks:
                        for track in tracks:
                            if isinstance(track, dict):
                                track_id = track.get('id')
                                if track_id and not any(t.get('id') == track_id for t in all_tracks):
                                    all_tracks.append(track)

                        self.logger.debug(f"关键词 '{keyword}' 找到 {len(tracks)} 首歌曲，去重后总数为 {len(all_tracks)}")

                        if len(all_tracks) >= count:
                            break
                    else:
                        self.logger.debug(f"关键词 '{keyword}' 未找到歌曲")

                    # 短暂延迟，避免请求过于频繁
                    import time
                    time.sleep(0.5)

                except Exception as e:
                    self.logger.error(f"搜索关键词 '{keyword}' 时出错: {e}", exc_info=True)
                    continue

            # 限制最多100首
            final_tracks = all_tracks[:100]

            # 在主线程中更新UI
            self.root.after(0, lambda: self._update_playlist_with_tracks(final_tracks, "热门"))

        except Exception as e:
            self.logger.error(f"自动搜索热门歌曲失败: {e}", exc_info=True)
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

        # 初始化搜索UI模块
        self.search_ui = SearchUI(
            parent=main_frame,
            theme_manager=self.theme_manager,
            api=self.api,
            logger=self.logger,
            add_to_playlist_callback=self.add_to_playlist,
            play_track_callback=self.play_track,
            add_to_favorites_callback=self._add_to_favorites_from_search,
            show_playback_info_callback=self._show_playback_info,
            root=self.root,
            on_theme_change_callback=self.on_theme_change,
            on_spectrum_mode_change_callback=self.on_spectrum_mode_change
        )
        # 同步搜索数量变量
        self.search_ui.search_count_var = self.search_count_var
        self.search_ui.source_var = self.source_var
        self.search_ui.search_var = self.search_var
        self.search_ui.theme_var = self.theme_var
        self.search_ui.spectrum_mode_var = self.spectrum_mode_var
        
        # 创建搜索栏
        self.search_ui.create_search_bar(main_frame)

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

        # 初始化控制栏UI模块
        self.control_bar_ui = ControlBarUI(
            parent=main_frame,
            theme_manager=self.theme_manager,
            logger=self.logger,
            on_volume_change_callback=self.on_volume_change,
            on_progress_change_callback=self.on_progress_change,
            toggle_play_callback=self.toggle_play,
            stop_play_callback=self.stop_play,
            previous_track_callback=self.previous_track,
            next_track_callback=self.next_track,
            add_current_to_favorites_callback=self.add_current_to_favorites,
            on_theme_change_callback=self.on_theme_change,
            on_spectrum_mode_change_callback=self.on_spectrum_mode_change
        )
        # 同步变量引用
        self.control_bar_ui.current_song_var = self.current_song_var
        self.control_bar_ui.current_artist_var = self.current_artist_var
        self.control_bar_ui.playback_info_var = self.playback_info_var
        self.control_bar_ui.format_var = self.format_var
        self.control_bar_ui.current_time_var = self.current_time_var
        self.control_bar_ui.total_time_var = self.total_time_var
        self.control_bar_ui.progress_var = self.progress_var
        self.control_bar_ui.volume_var = self.volume_var
        self.control_bar_ui.current_lyric_var = self.current_lyric_var
        self.control_bar_ui.quality_var = self.quality_var
        self.control_bar_ui.mode_var = self.mode_var
        
        # 创建控制栏
        self.control_bar_ui.create_control_bar(main_frame)

        # 保存按钮引用以便后续使用
        self.play_btn = self.control_bar_ui.play_btn
        self.prev_btn = self.control_bar_ui.prev_btn
        self.next_btn = self.control_bar_ui.next_btn
        self.stop_btn = self.control_bar_ui.stop_btn
        self.favorite_btn = self.control_bar_ui.favorite_btn
        self.progress_bar = self.control_bar_ui.progress_bar
        self.current_lyric_label = self.control_bar_ui.current_lyric_label
        self.playback_canvas = self.control_bar_ui.playback_canvas
        self.playback_text_id = self.control_bar_ui.playback_text_id
        self.playback_animation_id = self.control_bar_ui.playback_animation_id
        self.control_frame = self.control_bar_ui.control_frame
        
        # 初始化播放服务（需要在UI创建后，因为需要album_lyrics_panel）
        self.playback_service = PlaybackService(
            api=self.api,
            player=self.player,
            cache_manager=self.cache_manager,
            lyrics_manager=self.lyrics_manager,
            album_lyrics_panel=self.album_lyrics_panel,
            logger=self.logger,
            root=self.root,
            on_position_update_callback=self.on_position_update,
            on_playback_finished_callback=self.on_playback_finished,
            update_ui_callback=self._update_ui_callback
        )

    # create_search_bar 方法已移至 SearchUI 模块

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

    # create_control_bar 方法已移至 ControlBarUI 模块

    # 滚动文本相关方法已移至 ControlBarUI 模块

    def on_theme_change(self, event):
        """切换主题"""
        theme_name_cn = self.theme_var.get()
        theme_key = self.theme_manager.get_theme_key_by_name(theme_name_cn)

        if self.theme_manager.set_theme(theme_key):
            self.apply_theme(theme_key)
            # 保存主题配置
            self.config.set_theme(theme_key)
            self.logger.info(f"主题已更改为: {theme_name_cn} ({theme_key})")

    def on_spectrum_mode_change(self, event):
        """切换频谱显示模式"""
        mode = self.spectrum_mode_var.get()

        # 保存频谱模式配置
        self.config.set_spectrum_mode(mode)
        self.logger.info(f"频谱模式已更改为: {mode}")

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
    
    def _add_to_favorites_from_search(self, track):
        """从搜索UI添加歌曲到收藏"""
        # 检查是否已经收藏
        track_id = track.get('id')
        if any(fav.get('id') == track_id for fav in self.favorites):
            self._show_playback_info("该歌曲已在收藏夹中")
            return

        # 添加到收藏
        self.favorites.append(track)
        self.save_favorites()
        self._show_playback_info(f"已收藏: {track.get('name', '未知歌曲')}")
    
    def _update_ui_callback(self, update_type, value):
        """UI更新回调，用于PlaybackService"""
        if update_type == 'info':
            self._show_playback_info(value)
        elif update_type == 'format':
            self._show_format_info(value)
        elif update_type == 'play_state':
            if value:
                self.play_btn.config(text="⏸")
            else:
                self.play_btn.config(text="⏵")
    
    def _update_song_info_callback(self, track):
        """更新歌曲信息回调"""
        artist_list = track.get('artist', [])
        if isinstance(artist_list, list) and artist_list:
            artist_str = ', '.join(artist_list)
        else:
            artist_str = '未知歌手'
        self.current_song_var.set(track.get('name', '未知歌曲'))
        self.current_artist_var.set(artist_str)

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

        # 更新进度条（如果用户没有在拖动）
        if not self._is_seeking:
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
        try:
            # 设置拖动标志，防止位置更新干扰
            self._is_seeking = True
            
            position = self.progress_var.get()
            
            # 执行跳转
            success = self.player.seek(position)
            
            if success:
                self.logger.debug(f"跳转到位置: {position:.2f}秒")
            else:
                self.logger.warning(f"跳转失败: {position:.2f}秒")
                # 如果跳转失败，恢复进度条位置
                if hasattr(self.player, 'position'):
                    self.progress_var.set(self.player.position)
        except Exception as e:
            self.logger.error(f"进度条拖动处理失败: {e}", exc_info=True)
        finally:
            # 延迟重置标志，确保seek操作完成
            self.root.after(100, lambda: setattr(self, '_is_seeking', False))

    def on_volume_change(self, event):
        """音量调整"""
        volume = self.volume_var.get() / 100.0
        self.player.set_volume(volume)
        # 保存音量配置
        self.config.set_volume(volume)
        self.logger.debug(f"音量已设置为: {volume:.2f}")

    def on_playback_finished(self):
        """播放完成回调"""
        # 防止重复触发
        if hasattr(self, '_playback_finished_triggered') and self._playback_finished_triggered:
            return

        self._playback_finished_triggered = True

        self.logger.info("播放完成")
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
        except (AttributeError, tk.TclError) as e:
            self.logger.debug(f"检查事件位置失败: {e}")
            return False

    def _hide_search_results_dropdown(self):
        """隐藏搜索结果下拉框"""
        if self.search_results_frame and self.search_results_visible:
            try:
                # 解绑所有事件
                self.search_results_frame.unbind("<MouseWheel>")
                self.root.unbind("<Button-1>")
                self.search_results_frame.destroy()
            except (AttributeError, tk.TclError) as e:
                self.logger.debug(f"隐藏搜索结果下拉框时出错: {e}")
            self.search_results_frame = None
            self.search_results_visible = False

    def _search_thread(self, keyword):
        try:
            source = self.source_var.get()
            # 获取搜索数量
            try:
                count = int(self.search_count_var.get())
                if count < 1 or count > 200:
                    count = 50
            except (ValueError, AttributeError, tk.TclError) as e:
                self.logger.error(f"解析搜索数量失败: {e}，使用默认值50")
                count = 50

            result = self.api.search(keyword, source=source, count=count)

            self.logger.debug(f"搜索结果: {result}")

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
            self.logger.debug("频谱不存在，重新创建...")
            self._create_spectrum_by_mode()

    def play_track(self, track):
        """播放指定曲目 - 使用PlaybackService"""
        try:
            # 先停止当前播放和动画
            self._playback_finished_triggered = False
            
            # 更新当前曲目
            self.current_track = track

            # 获取播放参数（将中文名称转换为API键）
            source_name = self.source_var.get()
            source_mapping = {v: k for k, v in MUSIC_SOURCES.items()}
            source = source_mapping.get(source_name, "netease")
            
            quality_name = self.quality_var.get()
            quality_mapping = {v: k for k, v in QUALITY_OPTIONS.items()}
            quality = quality_mapping.get(quality_name, "999")

            # 使用PlaybackService播放
            if self.playback_service:
                self.playback_service.play_track(
                    track=track,
                    source=source,
                    quality=quality,
                    clear_highlight_callback=self._clear_playlist_highlight,
                    highlight_callback=self._highlight_current_playlist_item,
                    set_play_state_callback=self.set_play_state,
                    create_spectrum_callback=self._create_spectrum_by_mode,
                    start_spectrum_animation_callback=self._start_spectrum_animation,
                    update_song_info_callback=self._update_song_info_callback,
                    current_track_ref=[self.current_track]  # 使用列表以便修改
                )
            else:
                # 如果PlaybackService未初始化，使用旧方法（向后兼容）
                self.logger.warning("PlaybackService未初始化，使用旧方法播放")
                self._play_track_legacy(track)

        except Exception as e:
            error_msg = f"播放失败: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            messagebox.showerror("错误", error_msg)
            self._show_playback_info("播放异常")
    
    def _play_track_legacy(self, track):
        """旧版播放方法（向后兼容）"""
        # 如果PlaybackService未初始化，记录错误并提示用户
        self.logger.error("PlaybackService未初始化，无法播放")
        self._show_playback_info("播放服务未初始化，请重启程序")
        messagebox.showerror("错误", "播放服务未初始化，请重启程序")

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
            self.logger.error(f"播放默认音频失败: {e}", exc_info=True)
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

                    self.logger.info("默认音频开始播放")
                else:
                    self.root.after(0, lambda: self._show_playback_info("默认音频播放失败"))
            else:
                self.root.after(0, lambda: self._show_playback_info("默认音频加载失败"))

        except Exception as e:
            self.logger.error(f"播放默认音频线程失败: {e}", exc_info=True)
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
            self.logger.debug(f"歌曲已存在: {track.get('name')}")
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
        self.logger.debug(f"设置播放状态: {is_playing}")
        try:
            if is_playing:
                # 延迟一点启动，确保专辑图片已经加载
                self.root.after(200, self._delayed_start_animation)
            else:
                # 立即停止
                self._stop_animation()
        except Exception as e:
            self.logger.error(f"设置播放状态时出错: {e}", exc_info=True)

    def _delayed_start_animation(self):
        """延迟启动动画，确保专辑图片已准备好"""
        self.logger.debug("延迟启动动画")
        if hasattr(self.album_lyrics_panel, 'start_rotation'):
            self.album_lyrics_panel.start_rotation()
        if hasattr(self.album_lyrics_panel, 'update_spectrum'):
            self.album_lyrics_panel.update_spectrum()

    def _stop_animation(self):
        """停止动画"""
        self.logger.debug("停止动画")
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
                    self.logger.error(f"停止频谱动画时出错: {e}", exc_info=True)

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

            # 更新控制栏UI的ttk样式
            if hasattr(self, 'control_bar_ui'):
                self.control_bar_ui.update_theme(theme)

            # 更新搜索UI的ttk样式
            if hasattr(self, 'search_ui'):
                self.search_ui._update_combobox_styles()

            # 更新ttk组件样式（Combobox和Scale）
            self._update_ttk_styles(theme)

            # 强制刷新UI
            self.root.update_idletasks()

            self.logger.info(f"已切换到 {self.theme_manager.theme_names[theme_name]} 主题")

        except Exception as e:
            self.logger.error(f"切换主题时出错: {e}", exc_info=True)

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
                    except (AttributeError, tk.TclError) as e:
                        self.logger.debug(f"更新框架背景失败: {e}")

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
                    except (AttributeError, tk.TclError) as e:
                        self.logger.debug(f"更新标签样式失败: {e}")

            # 特别更新歌词显示标签
            self._update_lyric_display(theme)

        except Exception as e:
            self.logger.error(f"更新控制栏时出错: {e}", exc_info=True)

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
            self.logger.error(f"更新歌词显示时出错: {e}", exc_info=True)

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
        except (AttributeError, tk.TclError) as e:
            self.logger.debug(f"递归应用主题失败: {e}")

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
            self.logger.error(f"更新按钮样式时出错: {e}", exc_info=True)

    def _update_canvas_backgrounds(self, theme):
        """更新Canvas组件的背景色"""
        try:
            # 更新所有圆形按钮的画布背景
            buttons = [self.play_btn, self.prev_btn, self.next_btn, self.stop_btn, self.favorite_btn]
            for button in buttons:
                if hasattr(button, 'canvas'):
                    button.canvas.configure(bg=theme["secondary_bg"])
        except Exception as e:
            self.logger.error(f"更新画布背景时出错: {e}", exc_info=True)
    
    def _update_ttk_styles(self, theme):
        """更新所有ttk组件样式（Combobox和Scale）"""
        try:
            style = ttk.Style()
            
            # 更新Combobox样式
            style.configure("TCombobox",
                           fieldbackground=theme.get("tertiary_bg", theme["secondary_bg"]),
                           background=theme.get("tertiary_bg", theme["secondary_bg"]),
                           foreground=theme["text"],
                           borderwidth=1,
                           relief=tk.FLAT,
                           padding=5)
            style.map("TCombobox",
                     fieldbackground=[("readonly", theme.get("tertiary_bg", theme["secondary_bg"]))],
                     background=[("readonly", theme.get("tertiary_bg", theme["secondary_bg"]))],
                     foreground=[("readonly", theme["text"])])
            
            # 更新Scale（进度条和音量滑块）样式
            style.configure("TScale",
                           background=theme["secondary_bg"],
                           troughcolor=theme.get("progress_bg", theme["tertiary_bg"]),
                           sliderthickness=12,
                           sliderrelief=tk.FLAT,
                           borderwidth=0)
            style.map("TScale",
                     background=[("active", theme["secondary_bg"])],
                     troughcolor=[("active", theme.get("progress_bg", theme["tertiary_bg"]))])
            
            style.configure("Horizontal.TScale",
                           background=theme["secondary_bg"],
                           troughcolor=theme.get("progress_bg", theme["tertiary_bg"]),
                           sliderthickness=10,
                           sliderrelief=tk.FLAT,
                           borderwidth=0)
            style.map("Horizontal.TScale",
                     background=[("active", theme["secondary_bg"])],
                     troughcolor=[("active", theme.get("progress_bg", theme["tertiary_bg"]))])
            
        except Exception as e:
            self.logger.error(f"更新ttk样式时出错: {e}", exc_info=True)

