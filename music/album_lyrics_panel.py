import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageDraw, ImageFilter
import io
import requests
import threading
import math
import random
import time


class AlbumLyricsPanel:
    def __init__(self, parent, lyrics_manager, theme_manager=None):
        self.parent = parent
        self.lyrics_manager = lyrics_manager
        self.theme_manager = theme_manager  # 添加主题管理器参数

        # 存储引用
        self.bg_image_ref = None
        self.album_image_ref = None
        self.song_text_ref = None
        self.artist_text_ref = None
        self.lyric_text_refs = []
        self._last_highlighted_lyric = None
        self.current_lyrics = []
        self.track_info = None

        # 歌词滚动相关
        self.all_lyrics_data = []
        self.current_highlight_index = -1
        self.display_start_index = 0

        # 旋转相关属性
        self.is_rotating = False
        self.rotation_angle = 0
        self.rotation_speed = 1
        self.original_album_image = None
        self.rotation_job = None

        # 频谱相关属性
        self.spectrum_bars = []
        self.spectrum_data = [0.1, 0.3, 0.6, 0.8, 0.9, 0.7, 0.5, 0.3]  # 初始频谱数据
        self.spectrum_animation_id = None

        # 如果没有主题管理器，使用默认主题
        if theme_manager is None:
            # 默认主题系统（向后兼容）
            self.themes = {
                "dark": {"bg": "#1a1a1a", "text": "white", "accent": "#3498DB", "secondary": "#bdc3c7"},
                "light": {"bg": "#f8f9fa", "text": "#2c3e50", "accent": "#e74c3c", "secondary": "#7f8c8d"},
                "purple": {"bg": "#2d1b69", "text": "#e0d6ff", "accent": "#9b59b6", "secondary": "#a29bfe"},
                "sunset": {"bg": "#ff6b6b", "text": "#2c2c54", "accent": "#ff9ff3", "secondary": "#feca57"}
            }
            self.current_theme = "dark"
        else:
            self.themes = None  # 使用主题管理器的主题
            self.current_theme = "light"

        # 创建UI
        self.create_panel()
        self.parent.after(100, lambda: self._set_default_album_display())

    def get_current_theme_colors(self):
        """获取当前主题颜色"""
        if self.theme_manager:
            return self.theme_manager.get_current_theme()
        else:
            return self.themes[self.current_theme]

    def create_panel(self):
        """创建专辑和歌词面板"""
        # 获取当前背景色
        current_theme = self.get_current_theme_colors()
        bg_color = current_theme["bg"]

        # 创建专辑背景画布
        self.album_canvas = tk.Canvas(self.parent, bg=bg_color, highlightthickness=0)
        self.album_canvas.pack(fill=tk.BOTH, expand=True)

        # 不需要任何框架，所有内容都直接在画布上绘制
        self.album_image_ref = None
        self.song_text_ref = None
        self.artist_text_ref = None
        self.lyric_text_refs = []

        # 延迟创建频谱显示，确保画布已渲染
        self.album_canvas.pack(fill=tk.BOTH, expand=True)
        self.parent.after(500, self.create_spectrum)

    def start_rotation(self):
        """开始旋转专辑图"""
        print(f"尝试开始旋转 - 旋转状态: {self.is_rotating}, 是否有图片: {self.original_album_image is not None}")

        if not self.original_album_image:
            print("无法开始旋转: 没有原始专辑图片")
            return

        self.is_rotating = True
        print("专辑图旋转开始")
        self._rotate_album_image()

    def stop_rotation(self):
        """停止旋转专辑图"""
        print("专辑图旋转停止")
        self.is_rotating = False
        if hasattr(self, 'rotation_job') and self.rotation_job:
            self.album_canvas.after_cancel(self.rotation_job)
            self.rotation_job = None

    def _rotate_album_image(self):
        """旋转专辑图"""
        if not self.is_rotating:
            print("旋转已停止，退出旋转循环")
            return

        if not self.original_album_image:
            print("无法旋转: 没有原始专辑图片")
            self.is_rotating = False
            return

        try:
            # 更新旋转角度
            self.rotation_angle = (self.rotation_angle + self.rotation_speed) % 360

            # 旋转图片
            rotated_img = self.original_album_image.rotate(
                -self.rotation_angle,  # 负号表示顺时针旋转
                resample=Image.BICUBIC,
                expand=True
            )

            # 重新创建圆形专辑图
            self._update_rotated_album_art(rotated_img)

            # 继续动画
            self.rotation_job = self.album_canvas.after(50, self._rotate_album_image)

        except Exception as e:
            print(f"旋转专辑图失败: {e}")
            self.is_rotating = False

    def _update_rotated_album_art(self, rotated_img):
        """更新旋转后的专辑图"""
        try:
            size = 200
            # 调整图片尺寸
            img = rotated_img.resize((size, size), Image.Resampling.LANCZOS)

            # 创建圆形遮罩
            mask = Image.new('L', (size, size), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, size, size), fill=255)

            if img.mode != 'RGBA':
                img = img.convert('RGBA')

            circular_img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            circular_img.putalpha(mask)
            circular_img.paste(img, (0, 0), mask)

            # 添加边框
            bordered_size = size + 10
            bordered_img = Image.new('RGBA', (bordered_size, bordered_size), (0, 0, 0, 0))
            border_mask = Image.new('L', (bordered_size, bordered_size), 0)
            border_draw = ImageDraw.Draw(border_mask)
            border_draw.ellipse((0, 0, bordered_size, bordered_size), fill=255)

            border_img = Image.new('RGBA', (bordered_size, bordered_size), (255, 255, 255, 255))
            border_img.putalpha(border_mask)

            bordered_img.paste(border_img, (0, 0), border_img)
            bordered_img.paste(circular_img, (5, 5), circular_img)

            # 更新画布
            album_photo = ImageTk.PhotoImage(bordered_img)
            self.album_canvas.itemconfig(self.album_image_ref, image=album_photo)
            self.album_canvas.album_image = album_photo  # 保持引用

        except Exception as e:
            print(f"更新旋转专辑图失败: {e}")

    def load_album_image(self, image_url, track_info):
        """加载专辑图片"""
        print(f"开始加载专辑图片: {image_url}")

        # 重置歌词相关状态
        self._reset_lyrics_state()

        self.track_info = track_info  # 保存歌曲信息
        threading.Thread(target=self._load_image_thread,
                         args=(image_url,),
                         daemon=True).start()

    def _reset_lyrics_state(self):
        """重置歌词显示状态"""
        # 停止可能正在运行的滚动动画
        if hasattr(self, '_current_animation') and self._current_animation:
            self.parent.after_cancel(self._current_animation)
            self._current_animation = None

        # 清除歌词管理器中的数据
        if hasattr(self.lyrics_manager, 'lyrics'):
            self.lyrics_manager.lyrics.clear()
        if hasattr(self.lyrics_manager, 'translated_lyrics'):
            self.lyrics_manager.translated_lyrics.clear()

        # 重置歌词数据
        self.all_lyrics_data = []
        self.current_highlight_index = -1
        self.display_start_index = 0

        # 清除画布上的歌词显示
        self._clear_lyrics()

        print("歌词状态已重置")

    def _load_image_thread(self, image_url):
        """在后台线程中加载图片"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(image_url, timeout=10, headers=headers)
            if response.status_code == 200:
                image_data = response.content
                original_image = Image.open(io.BytesIO(image_data))

                print(f"专辑图片加载成功，尺寸: {original_image.size}")

                # 在主线程中更新UI
                self.parent.after(0, lambda: self._update_album_display(original_image))
            else:
                print(f"专辑图片加载失败，状态码: {response.status_code}")
                self.parent.after(0, self._set_default_album_display)
        except Exception as e:
            print(f"加载专辑图片失败: {e}")
            self.parent.after(0, self._set_default_album_display)

    def _update_album_display(self, original_image):
        """更新专辑显示"""
        print("开始更新专辑显示")

        # 提取颜色并应用动态主题
        self.extract_colors_from_album(original_image)

        # 创建模糊背景
        self._create_blur_background(original_image)

        # 创建圆形专辑图
        self._create_circular_album_art(original_image)

        # 绘制歌曲信息
        self._draw_song_info()

    def _create_blur_background(self, original_image):
        """创建模糊背景 - 不删除频谱"""
        try:
            # 获取画布尺寸
            canvas_width = self.album_canvas.winfo_width()
            canvas_height = self.album_canvas.winfo_height()

            # 如果画布还未显示，使用默认尺寸
            if canvas_width <= 1 or canvas_height <= 1:
                canvas_width, canvas_height = 550, 600

            # 调整图片尺寸以适应画布
            bg_image = original_image.resize((canvas_width, canvas_height), Image.Resampling.LANCZOS)

            # 应用高斯模糊
            bg_image = bg_image.filter(ImageFilter.GaussianBlur(radius=15))

            # 添加深色覆盖层以增强文字可读性
            overlay = Image.new('RGBA', (canvas_width, canvas_height), (0, 0, 0, 128))
            bg_image = Image.alpha_composite(bg_image.convert('RGBA'), overlay)

            # 转换为PhotoImage
            bg_photo = ImageTk.PhotoImage(bg_image)

            # 更新背景 - 只删除背景图片，不删除其他元素
            if self.bg_image_ref:
                self.album_canvas.delete(self.bg_image_ref)

            # 将背景放在最底层
            self.bg_image_ref = self.album_canvas.create_image(0, 0, image=bg_photo, anchor=tk.NW)
            self.album_canvas.bg_image = bg_photo  # 保持引用

            # 确保背景在最底层
            self.album_canvas.tag_lower(self.bg_image_ref)

        except Exception as e:
            print(f"创建模糊背景失败: {e}")

    def _create_circular_album_art(self, original_image):
        """创建完美圆形专辑图 - 确保保存原始图片用于旋转"""
        try:
            print("创建圆形专辑图")

            # 重要：保存原始图片用于旋转
            self.original_album_image = original_image.copy()
            print(f"保存原始专辑图片，尺寸: {self.original_album_image.size}")

            # 圆形专辑图尺寸
            size = 200

            # 调整图片尺寸为正方形
            img = original_image.resize((size, size), Image.Resampling.LANCZOS)

            # 创建圆形遮罩
            mask = Image.new('L', (size, size), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, size, size), fill=255)

            # 应用圆形遮罩
            if img.mode != 'RGBA':
                img = img.convert('RGBA')

            circular_img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            circular_img.putalpha(mask)
            circular_img.paste(img, (0, 0), mask)

            # 添加白色边框
            bordered_size = size + 10
            bordered_img = Image.new('RGBA', (bordered_size, bordered_size), (0, 0, 0, 0))

            # 创建圆形边框
            border_mask = Image.new('L', (bordered_size, bordered_size), 0)
            border_draw = ImageDraw.Draw(border_mask)
            border_draw.ellipse((0, 0, bordered_size, bordered_size), fill=255)

            # 创建白色边框图像
            border_img = Image.new('RGBA', (bordered_size, bordered_size), (255, 255, 255, 255))
            border_img.putalpha(border_mask)

            # 组合边框和专辑图
            bordered_img.paste(border_img, (0, 0), border_img)
            bordered_img.paste(circular_img, (5, 5), circular_img)

            # 转换为PhotoImage
            album_photo = ImageTk.PhotoImage(bordered_img)

            # 在画布上创建图像
            if self.album_image_ref:
                self.album_canvas.delete(self.album_image_ref)

            # 获取画布中心位置
            canvas_width = self.album_canvas.winfo_width()
            canvas_height = self.album_canvas.winfo_height()

            if canvas_width <= 1:
                canvas_width = 550
            if canvas_height <= 1:
                canvas_height = 600

            self.album_image_ref = self.album_canvas.create_image(
                canvas_width // 2,
                canvas_height * 0.35,
                image=album_photo,
                anchor=tk.CENTER
            )
            self.album_canvas.album_image = album_photo  # 保持引用

            print("圆形专辑图创建完成")

        except Exception as e:
            print(f"创建圆形专辑图失败: {e}")


    def _set_default_album_display(self, track_info=None):
        """设置默认专辑显示 - 使用music.jpg作为默认背景"""
        try:
            print("设置默认专辑显示")

            # 重置歌词状态
            self._reset_lyrics_state()

            # 获取画布实际尺寸
            canvas_width = self.album_canvas.winfo_width()
            canvas_height = self.album_canvas.winfo_height()

            # 如果画布还未显示，使用默认尺寸
            if canvas_width <= 1 or canvas_height <= 1:
                canvas_width, canvas_height = 550, 600

            # 尝试加载music.jpg作为默认背景
            try:
                # 从项目根目录加载music.jpg
                default_bg_image = Image.open("music.jpg")
                # 调整尺寸以适应画布
                bg_image = default_bg_image.resize((canvas_width, canvas_height), Image.Resampling.LANCZOS)
                # 应用模糊效果
                bg_image = bg_image.filter(ImageFilter.GaussianBlur(radius=10))
                # 添加深色覆盖层
                overlay = Image.new('RGBA', (canvas_width, canvas_height), (0, 0, 0, 150))
                bg_image = Image.alpha_composite(bg_image.convert('RGBA'), overlay)
                print("成功加载默认背景图片 music.jpg")

            except Exception as e:
                print(f"加载默认背景图片失败，使用纯色背景: {e}")
                # 如果加载失败，使用纯色背景
                bg_image = Image.new('RGB', (canvas_width, canvas_height), color='#2C3E50')

            bg_photo = ImageTk.PhotoImage(bg_image)

            if self.bg_image_ref:
                self.album_canvas.delete(self.bg_image_ref)

            self.bg_image_ref = self.album_canvas.create_image(0, 0, image=bg_photo, anchor=tk.NW)
            self.album_canvas.bg_image = bg_photo

            # 创建默认圆形专辑图（使用music.jpg或默认图标）
            self._create_default_circular_album()

            # 绘制歌曲信息
            if track_info:
                self.track_info = track_info
                self._draw_song_info()
            elif hasattr(self, 'track_info') and self.track_info:
                self._draw_song_info()
            else:
                self._draw_default_song_info()

            print("默认专辑显示设置完成")

        except Exception as e:
            print(f"设置默认专辑显示失败: {e}")

    def _draw_song_info(self, theme=None):
        """在画布上绘制歌曲信息 - 确保在频谱上方"""
        if theme is None:
            theme = self.get_current_theme_colors()

        # 清除之前的文字
        if self.song_text_ref:
            self.album_canvas.delete(self.song_text_ref)
        if self.artist_text_ref:
            self.album_canvas.delete(self.artist_text_ref)

        # 检查是否有有效的歌曲信息
        if not hasattr(self, 'track_info') or not self.track_info:
            self._draw_default_song_info(theme)
            return

        canvas_width = self.album_canvas.winfo_width()
        if canvas_width <= 1:
            canvas_width = 550

        # 安全地获取歌曲信息
        song_name = self.track_info.get('name', '未知歌曲') if self.track_info else '未知歌曲'
        artist_list = self.track_info.get('artist', []) if self.track_info else []

        if isinstance(artist_list, list) and artist_list:
            artist_str = ', '.join(artist_list)
        else:
            artist_str = '未知歌手'

        # 绘制歌曲名称
        self.song_text_ref = self.album_canvas.create_text(
            canvas_width // 2,
            20,
            text=song_name,
            font=("Microsoft YaHei", 16, "bold"),
            fill=theme["text"],  # 使用主题文字颜色
            anchor=tk.CENTER,
            width=canvas_width - 40
        )

        # 绘制歌手信息
        self.artist_text_ref = self.album_canvas.create_text(
            canvas_width // 2,
            45,
            text=artist_str,
            font=("Microsoft YaHei", 12),
            fill=theme["secondary_text"],  # 使用主题次要颜色
            anchor=tk.CENTER,
            width=canvas_width - 40
        )

        # 确保文字在最上层
        if self.song_text_ref:
            self.album_canvas.tag_raise(self.song_text_ref)
        if self.artist_text_ref:
            self.album_canvas.tag_raise(self.artist_text_ref)

    def _draw_default_song_info(self, theme=None):
        """绘制默认歌曲信息"""
        if theme is None:
            theme = self.get_current_theme_colors()

        # 清除之前的文字
        if self.song_text_ref:
            self.album_canvas.delete(self.song_text_ref)
        if self.artist_text_ref:
            self.album_canvas.delete(self.artist_text_ref)

        canvas_width = self.album_canvas.winfo_width()
        if canvas_width <= 1:
            canvas_width = 550

        # 绘制默认歌曲名称
        self.song_text_ref = self.album_canvas.create_text(
            canvas_width // 2,
            20,
            text="暂无歌曲",
            font=("Microsoft YaHei", 16, "bold"),
            fill=theme["text"],  # 使用主题文字颜色
            anchor=tk.CENTER
        )

        # 绘制默认歌手信息
        self.artist_text_ref = self.album_canvas.create_text(
            canvas_width // 2,
            45,
            text="请选择歌曲播放",
            font=("Microsoft YaHei", 12),
            fill=theme["secondary_text"],
            anchor=tk.CENTER
        )

    def _create_default_circular_album(self):
        """创建默认圆形专辑图 - 使用music.jpg或默认图标"""
        try:
            print("创建默认圆形专辑图")
            size = 200

            # 尝试使用music.jpg创建专辑图
            try:
                # 加载music.jpg
                default_img = Image.open("music.jpg")
                # 调整尺寸为正方形
                default_img = default_img.resize((size, size), Image.Resampling.LANCZOS)
                print("使用music.jpg创建默认专辑图")

            except Exception as e:
                print(f"加载music.jpg失败，使用默认图标: {e}")
                # 如果加载失败，创建默认的灰色专辑图
                default_img = Image.new('RGBA', (size, size), (52, 73, 94, 255))
                # 添加音乐图标
                draw = ImageDraw.Draw(default_img)
                center = size // 2
                radius = 40
                draw.ellipse([center - radius, center - radius, center + radius, center + radius],
                             outline='white', width=3)

            # 重要：保存默认图片用于旋转
            self.original_album_image = default_img.copy()
            print("保存默认专辑图片用于旋转")

            # 创建圆形遮罩
            mask = Image.new('L', (size, size), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, size, size), fill=255)

            circular_img = Image.new('RGBA', (size, size))
            circular_img.putalpha(mask)
            circular_img.paste(default_img, (0, 0), mask)

            # 添加白色边框
            bordered_size = size + 10
            bordered_img = Image.new('RGBA', (bordered_size, bordered_size), (0, 0, 0, 0))
            border_mask = Image.new('L', (bordered_size, bordered_size), 0)
            border_draw = ImageDraw.Draw(border_mask)
            border_draw.ellipse((0, 0, bordered_size, bordered_size), fill=255)

            border_img = Image.new('RGBA', (bordered_size, bordered_size), (255, 255, 255, 255))
            border_img.putalpha(border_mask)

            bordered_img.paste(border_img, (0, 0), border_img)
            bordered_img.paste(circular_img, (5, 5), circular_img)

            album_photo = ImageTk.PhotoImage(bordered_img)

            # 在画布上创建默认专辑图
            if self.album_image_ref:
                self.album_canvas.delete(self.album_image_ref)

            canvas_width = self.album_canvas.winfo_width()
            canvas_height = self.album_canvas.winfo_height()

            if canvas_width <= 1:
                canvas_width = 550
            if canvas_height <= 1:
                canvas_height = 600

            self.album_image_ref = self.album_canvas.create_image(
                canvas_width // 2,
                canvas_height * 0.35,
                image=album_photo,
                anchor=tk.CENTER
            )
            self.album_canvas.album_image = album_photo

            print("默认圆形专辑图创建完成")

        except Exception as e:
            print(f"创建默认圆形专辑图失败: {e}")

    def update_lyrics(self, lyric_result):
        """更新歌词显示"""
        try:
            self.lyrics_manager.parse_lrc(lyric_result.get('lyric', ''))
            self.lyrics_manager.parse_translated_lrc(lyric_result.get('tlyric', ''))

            # 存储所有歌词数据
            self.all_lyrics_data = []
            for time_stamp in sorted(self.lyrics_manager.lyrics.keys()):
                lyric = self.lyrics_manager.lyrics[time_stamp]
                translated = self.lyrics_manager.translated_lyrics.get(time_stamp, "")
                self.all_lyrics_data.append((time_stamp, lyric, translated))

            # 重置滚动状态
            self.current_highlight_index = -1
            self.display_start_index = 0

            # 更新歌词显示
            self._draw_lyrics()

            lyrics_count = len(self.lyrics_manager.lyrics)
            translated_count = len(self.lyrics_manager.translated_lyrics)
            print(f"歌词更新完成: {lyrics_count}行歌词, {translated_count}行翻译")

        except Exception as e:
            print(f"更新歌词失败: {e}")
            self._draw_lyrics_error("歌词加载失败")

    def _draw_lyrics(self, theme=None):
        """在画布上绘制歌词"""
        if theme is None:
            theme = self.get_current_theme_colors()

        # 清除之前的歌词
        self._clear_lyrics()

        if not hasattr(self, 'all_lyrics_data') or not self.all_lyrics_data:
            self._draw_no_lyrics(theme)
            return

        canvas_width = self.album_canvas.winfo_width()
        canvas_height = self.album_canvas.winfo_height()

        if canvas_width <= 1:
            canvas_width = 550
        if canvas_height <= 1:
            canvas_height = 600

        # 确保显示起始索引在有效范围内
        if self.display_start_index < 0:
            self.display_start_index = 0
        elif self.display_start_index >= len(self.all_lyrics_data):
            self.display_start_index = max(0, len(self.all_lyrics_data) - 1)

        # 歌词起始位置（专辑图下方）
        start_y = canvas_height * 0.75
        line_height = 25

        # 计算显示的行数
        max_lines = min(8, len(self.all_lyrics_data) - self.display_start_index)

        # 绘制歌词
        for i in range(max_lines):
            index = self.display_start_index + i
            if index >= len(self.all_lyrics_data):
                break

            try:
                time_stamp, lyric, translated = self.all_lyrics_data[index]
                y_pos = start_y + (i * line_height)

                # 判断是否需要高亮
                is_highlight = (index == self.current_highlight_index)

                # 主歌词 - 居中显示
                if lyric and lyric.strip():
                    color = theme["accent"] if is_highlight else theme["text"]
                    font_size = 14 if is_highlight else 11
                    font_weight = "bold" if is_highlight else "normal"

                    lyric_ref = self.album_canvas.create_text(
                        canvas_width // 2,
                        y_pos,
                        text=lyric.strip(),
                        font=("Microsoft YaHei", font_size, font_weight),
                        fill=color,
                        anchor=tk.CENTER
                    )
                    self.lyric_text_refs.append(lyric_ref)

                # 翻译歌词 - 居中显示
                if translated and translated.strip():
                    y_pos += 15
                    color = theme["accent"] if is_highlight else theme["secondary_text"]
                    font_size = 11 if is_highlight else 9
                    font_weight = "bold" if is_highlight else "normal"

                    trans_ref = self.album_canvas.create_text(
                        canvas_width // 2,
                        y_pos,
                        text=translated.strip(),
                        font=("Microsoft YaHei", font_size, font_weight),
                        fill=color,
                        anchor=tk.CENTER
                    )
                    self.lyric_text_refs.append(trans_ref)

            except Exception as e:
                print(f"绘制第{index}行歌词时出错: {e}")
                continue

    def _draw_no_lyrics(self, theme=None):
        """绘制无歌词提示"""
        if theme is None:
            theme = self.get_current_theme_colors()

        canvas_width = self.album_canvas.winfo_width()
        canvas_height = self.album_canvas.winfo_height()

        if canvas_width <= 1 or canvas_height <= 1:
            canvas_width, canvas_height = 550, 600

        no_lyrics_ref = self.album_canvas.create_text(
            canvas_width // 2,
            canvas_height * 0.68,
            text="暂无歌词",
            font=("Microsoft YaHei", 12),
            fill=theme["secondary_text"],  # 使用主题的次要颜色
            anchor=tk.CENTER
        )
        self.lyric_text_refs.append(no_lyrics_ref)

    def highlight_current_lyric(self, position, current_lyric_var=None):
        """高亮当前播放的歌词并自动滚动"""
        try:
            if not hasattr(self, 'all_lyrics_data') or not self.all_lyrics_data:
                return

            current_lyric, translated_lyric = self.lyrics_manager.get_current_lyric(position)

            # 更新进度条歌词显示
            if current_lyric_var:
                self._update_progress_lyric(current_lyric_var, current_lyric, translated_lyric)

            # 找到当前歌词的索引
            current_index = -1
            for i, (time_stamp, lyric, translated) in enumerate(self.all_lyrics_data):
                if lyric == current_lyric:
                    current_index = i
                    break

            # 如果找到了当前歌词且索引发生变化
            if current_index != -1 and current_index != self.current_highlight_index:
                self.current_highlight_index = current_index

                # 使用平滑滚动，但只在有多行歌词时使用
                if len(self.all_lyrics_data) > 1:
                    self._smooth_scroll_to_lyric(current_index)
                else:
                    # 只有一行歌词时直接显示
                    self.display_start_index = 0
                    self._draw_lyrics()

        except Exception as e:
            print(f"高亮歌词时发生错误: {e}")

    def _smooth_scroll_to_lyric(self, target_index):
        """平滑滚动到指定歌词"""
        # 检查目标索引是否有效
        if target_index < 0 or target_index >= len(self.all_lyrics_data):
            print(f"无效的目标索引: {target_index}, 歌词数据长度: {len(self.all_lyrics_data)}")
            return

        start_index = self.display_start_index
        steps = 15  # 滚动步数

        def animate_scroll(step):
            # 检查歌词数据是否仍然有效
            if not hasattr(self, 'all_lyrics_data') or not self.all_lyrics_data:
                print("歌词数据已清空，停止滚动动画")
                return

            if step <= steps:
                try:
                    # 使用缓动函数
                    progress = step / steps
                    # 立方缓出效果
                    ease = 1 - (1 - progress) ** 3

                    # 计算目标显示起始位置（让当前歌词在显示区域中间）
                    target_display_index = max(0, target_index - 2)
                    new_index = start_index + (target_display_index - start_index) * ease
                    self.display_start_index = int(new_index)

                    # 确保显示索引在有效范围内
                    if self.display_start_index < 0:
                        self.display_start_index = 0
                    elif self.display_start_index >= len(self.all_lyrics_data):
                        self.display_start_index = max(0, len(self.all_lyrics_data) - 1)

                    self._draw_lyrics()

                    # 继续下一帧动画
                    self.parent.after(20, lambda: animate_scroll(step + 1))

                except Exception as e:
                    print(f"滚动动画出错: {e}")
                    # 出错时停止动画
                    return

        animate_scroll(1)

    def _update_progress_lyric(self, current_lyric_var, current_lyric, translated_lyric):
        """更新进度条上方的歌词显示"""
        try:
            lyric_text = ""
            if current_lyric and current_lyric.strip():
                lyric_text = current_lyric.strip()
                if translated_lyric and translated_lyric.strip():
                    lyric_text += f"  |  {translated_lyric.strip()}"

            current_lyric_var.set(lyric_text if lyric_text else "暂无歌词")

        except Exception as e:
            print(f"更新进度条歌词失败: {e}")
            current_lyric_var.set("")

    def _clear_lyrics(self):
        """清除画布上的歌词"""
        for ref in self.lyric_text_refs:
            self.album_canvas.delete(ref)
        self.lyric_text_refs.clear()

    def _draw_lyrics_error(self, message, theme=None):
        """绘制歌词错误信息"""
        if theme is None:
            theme = self.get_current_theme_colors()

        self._clear_lyrics()

        canvas_width = self.album_canvas.winfo_width()
        canvas_height = self.album_canvas.winfo_height()

        if canvas_width <= 1:
            canvas_width = 550

        error_ref = self.album_canvas.create_text(
            canvas_width // 2,
            canvas_height * 0.6,
            text=message,
            font=("Microsoft YaHei", 12),
            fill=theme["accent"],
            anchor=tk.CENTER
        )
        self.lyric_text_refs.append(error_ref)

    def clear_lyrics_highlight(self):
        """清除歌词高亮"""
        self.current_highlight_index = -1
        self.display_start_index = 0
        if hasattr(self, 'all_lyrics_data') and self.all_lyrics_data:
            self._draw_lyrics()

    def create_spectrum(self):
        """创建更真实的频谱显示"""
        self._clear_spectrum()

        canvas_width = self.album_canvas.winfo_width()
        canvas_height = self.album_canvas.winfo_height()

        if canvas_width <= 1:
            canvas_width = 550
        if canvas_height <= 1:
            canvas_height = 600

        # 频谱位置（专辑图下方）
        spectrum_x = canvas_width // 2
        spectrum_y = canvas_height * 0.60
        bar_width = 6
        bar_spacing = 3
        max_height = 50
        bar_count = 16

        # 创建频谱柱 - 使用更丰富的渐变色
        colors = [
            "#1ABC9C",  # 青绿色 - 超低频
            "#3498DB",  # 蓝色 - 低频
            "#2980B9",  # 深蓝 - 低频
            "#27AE60",  # 绿色 - 中低频
            "#2ECC71",  # 亮绿 - 中低频
            "#F1C40F",  # 黄色 - 中频
            "#F39C12",  # 橙色 - 中频
            "#E67E22",  # 橙红 - 中高频
            "#D35400",  # 深橙 - 中高频
            "#E74C3C",  # 红色 - 高频
            "#C0392B",  # 深红 - 高频
            "#9B59B6",  # 紫色 - 超高频
            "#8E44AD",  # 深紫 - 超高频
            "#34495E",  # 深蓝灰 - 极高频
            "#2C3E50",  # 蓝黑 - 极高频
            "#16A085"  # 深青 - 特殊频段
        ]

        for i in range(bar_count):
            # 彩虹色渐变效果
            hue = i / bar_count
            # 使用HSV到RGB的转换获得更平滑的渐变
            r = int(255 * (1 - hue))
            g = int(255 * hue)
            b = int(255 * (0.5 + 0.5 * math.sin(hue * math.pi)))
            color = f"#{r:02x}{g:02x}{b:02x}"

            # 或者使用预定义颜色
            color_index = min(int(i / bar_count * len(colors)), len(colors) - 1)
            color = colors[color_index]

            x = spectrum_x - (bar_width + bar_spacing) * bar_count / 2 + (bar_width + bar_spacing) * i

            # 创建圆角矩形效果
            bar_id = self.album_canvas.create_rectangle(
                x, spectrum_y,
                x + bar_width, spectrum_y,
                fill=color,
                outline="",  # 去掉边框
                width=0
            )
            self.spectrum_bars.append(bar_id)

    def update_spectrum(self, spectrum_data=None):
        """更新频谱显示 - 更真实的音乐响应"""
        if not self.spectrum_bars:
            return

        # 模拟真实音乐频谱
        if spectrum_data is None:

            # 更真实的频谱算法
            current_time = time.time()

            # 多频率合成
            base_freq = (math.sin(current_time * 1.5) + 1) * 0.2  # 基础频率
            mid_freq = (math.sin(current_time * 8) + 1) * 0.3  # 中频
            high_freq = (math.sin(current_time * 15) + 1) * 0.2  # 高频

            # 生成更真实的频谱数据
            new_spectrum = []
            for i in range(len(self.spectrum_bars)):
                # 低频部分（左侧）- 强烈的节奏感
                if i < 3:
                    height = base_freq + random.uniform(0.15, 0.4)
                    # 添加低频共振
                    resonance = math.sin(current_time * 4 + i * 0.8) * 0.2
                    height += resonance

                # 中低频部分
                elif i < 6:
                    height = 0.5 + random.uniform(0.1, 0.35)
                    wave = math.sin(current_time * 10 + i * 1.2) * 0.25
                    height += wave

                # 中频部分 - 最活跃
                elif i < 10:
                    height = mid_freq + random.uniform(0.2, 0.5)
                    modulation = math.sin(current_time * 12 + i * 0.7) * 0.3
                    height += modulation

                # 中高频部分
                elif i < 13:
                    height = 0.4 + random.uniform(0.1, 0.4)
                    harmonic = math.sin(current_time * 18 + i * 0.9) * 0.2
                    height += harmonic

                # 高频部分 - 细腻变化
                else:
                    height = high_freq + random.uniform(0.05, 0.25)
                    subtle = math.sin(current_time * 25 + i) * 0.15
                    height += subtle

                # 添加随机峰值模拟真实音乐
                if random.random() < 0.1:  # 10%几率出现峰值
                    height += random.uniform(0.1, 0.3)

                # 确保在合理范围内
                height = max(0.1, min(1.0, height))
                new_spectrum.append(height)

            self.spectrum_data = new_spectrum
        else:
            self.spectrum_data = spectrum_data

        canvas_height = self.album_canvas.winfo_height()
        if canvas_height <= 1:
            canvas_height = 600

        spectrum_y = canvas_height * 0.60
        max_height = 50

        # 平滑过渡效果
        smoothing_factor = 0.3  # 平滑系数

        # 更新每个频谱柱的高度
        for i, bar_id in enumerate(self.spectrum_bars):
            if i < len(self.spectrum_data):
                target_height = self.spectrum_data[i] * max_height

                # 获取当前高度
                coords = self.album_canvas.coords(bar_id)
                if coords and len(coords) >= 4:
                    current_height = spectrum_y - coords[1]

                    # 平滑过渡到目标高度
                    smoothed_height = (current_height * (1 - smoothing_factor) +
                                       target_height * smoothing_factor)

                    self.album_canvas.coords(
                        bar_id,
                        coords[0], spectrum_y - smoothed_height,
                        coords[2], spectrum_y
                    )

        # 继续动画
        if self.is_rotating:
            self.spectrum_animation_id = self.album_canvas.after(80, self.update_spectrum)

    def _clear_spectrum(self):
        """清除频谱显示"""
        for bar_id in self.spectrum_bars:
            self.album_canvas.delete(bar_id)
        self.spectrum_bars.clear()

        if self.spectrum_animation_id:
            self.album_canvas.after_cancel(self.spectrum_animation_id)

    def create_advanced_spectrum(self):
        """创建高级圆形频谱"""
        self._clear_spectrum()

        canvas_width = self.album_canvas.winfo_width()
        canvas_height = self.album_canvas.winfo_height()

        if canvas_width <= 1:
            canvas_width = 550
        if canvas_height <= 1:
            canvas_height = 600

        # 圆形频谱参数
        center_x = canvas_width // 2
        center_y = canvas_height * 0.35
        inner_radius = 110  # 内半径
        outer_radius = 160  # 外半径
        bar_count = 48  # 更多频谱柱

        # 创建圆形频谱
        for i in range(bar_count):
            angle = 2 * math.pi * i / bar_count

            # 计算内外点坐标
            inner_x = center_x + inner_radius * math.cos(angle)
            inner_y = center_y + inner_radius * math.sin(angle)
            outer_x = center_x + outer_radius * math.cos(angle)
            outer_y = center_y + outer_radius * math.sin(angle)

            # 彩虹色渐变
            hue = i / bar_count
            color = self.hsv_to_rgb(hue, 0.9, 0.9)

            bar_id = self.album_canvas.create_line(
                inner_x, inner_y, outer_x, outer_y,
                width=4,
                fill=color,
                capstyle=tk.ROUND
            )
            self.spectrum_bars.append(bar_id)

    def update_advanced_spectrum(self):
        """更新圆形频谱"""
        if not self.spectrum_bars:
            return

        # 获取画布尺寸
        canvas_width = self.album_canvas.winfo_width()
        canvas_height = self.album_canvas.winfo_height()

        current_time = time.time()

        for i, bar_id in enumerate(self.spectrum_bars):
            # 简单动态效果
            pulse = (math.sin(current_time * 6 + i * 0.5) + 1) * 10

            # 获取当前坐标
            coords = self.album_canvas.coords(bar_id)
            if coords and len(coords) >= 4:
                start_x, start_y = coords[0], coords[1]

                # 计算角度和新的终点
                center_x = canvas_width // 2
                center_y = canvas_height * 0.35

                angle = math.atan2(start_y - center_y, start_x - center_x)
                new_length = 25 + pulse

                end_x = center_x + (120 + new_length) * math.cos(angle)
                end_y = center_y + (120 + new_length) * math.sin(angle)

                # 更新坐标
                self.album_canvas.coords(bar_id, start_x, start_y, end_x, end_y)

        if self.is_rotating:
            self.spectrum_animation_id = self.album_canvas.after(100, self.update_advanced_spectrum)

    def create_waterfall_spectrum(self):
        """创建瀑布流式频谱（频谱条从上往下流动）"""
        self._clear_spectrum()

        canvas_width = self.album_canvas.winfo_width()
        canvas_height = self.album_canvas.winfo_height()

        if canvas_width <= 1:
            canvas_width = 550
        if canvas_height <= 1:
            canvas_height = 600

        # 瀑布流参数
        self.waterfall_data = []  # 存储历史频谱数据
        self.max_waterfall_lines = 20  # 最大显示行数

        bar_width = 6
        bar_spacing = 3
        bar_count = 16
        spectrum_top_y = canvas_height * 0.45
        spectrum_height = canvas_height * 0.2

        # 创建颜色映射
        self.waterfall_colors = []
        for i in range(bar_count):
            hue = i / bar_count
            color = self.hsv_to_rgb(hue, 0.8, 0.9)
            self.waterfall_colors.append(color)

    def update_waterfall_spectrum(self):
        """更新瀑布流频谱"""
        if not hasattr(self, 'waterfall_data'):
            return

        # 获取画布尺寸
        canvas_width = self.album_canvas.winfo_width()
        canvas_height = self.album_canvas.winfo_height()

        if canvas_width <= 1:
            canvas_width = 550
        if canvas_height <= 1:
            canvas_height = 600

        current_time = time.time()

        # 生成新的频谱数据
        new_line = []
        for i in range(len(self.waterfall_colors)):
            if i < 4:
                height = 0.3 + random.uniform(0.1, 0.3) + math.sin(current_time * 8 + i) * 0.1
            elif i < 8:
                height = 0.4 + random.uniform(0.1, 0.4) + math.sin(current_time * 12 + i * 0.5) * 0.15
            else:
                height = 0.2 + random.uniform(0, 0.3) + math.sin(current_time * 20 + i) * 0.08

            height = max(0.1, min(1.0, height))
            new_line.append(height)

        # 添加到历史数据
        self.waterfall_data.insert(0, new_line)

        # 限制历史数据数量
        if len(self.waterfall_data) > self.max_waterfall_lines:
            self.waterfall_data = self.waterfall_data[:self.max_waterfall_lines]

        # 清除旧的频谱显示
        for bar_id in self.spectrum_bars:
            self.album_canvas.delete(bar_id)
        self.spectrum_bars.clear()

        # 绘制瀑布流
        spectrum_top_y = canvas_height * 0.45
        spectrum_height = canvas_height * 0.2
        line_height = spectrum_height / self.max_waterfall_lines

        bar_width = 8
        bar_spacing = 2
        bar_count = len(self.waterfall_colors)
        spectrum_center_x = canvas_width // 2

        for line_index, spectrum_line in enumerate(self.waterfall_data):
            y_top = spectrum_top_y + line_index * line_height
            y_bottom = y_top + line_height

            # 计算透明度（越往下越透明）
            alpha_factor = 1.0 - (line_index / self.max_waterfall_lines) * 0.8

            for i, height in enumerate(spectrum_line):
                total_width = bar_count * (bar_width + bar_spacing) - bar_spacing
                x_left = spectrum_center_x - total_width // 2 + i * (bar_width + bar_spacing)
                x_right = x_left + bar_width

                # 计算实际高度
                bar_height = height * line_height

                # 创建频谱条
                bar_id = self.album_canvas.create_rectangle(
                    x_left, y_bottom - bar_height,
                    x_right, y_bottom,
                    fill=self.waterfall_colors[i],
                    outline="",
                    width=0
                )
                self.spectrum_bars.append(bar_id)

        # 继续动画
        if self.is_rotating:
            self.spectrum_animation_id = self.album_canvas.after(120, self.update_waterfall_spectrum)

    def hsv_to_rgb(self, h, s, v):
        """HSV转RGB颜色"""
        if s == 0.0:
            r = g = b = v
        else:
            i = int(h * 6.0)
            f = (h * 6.0) - i
            p = v * (1.0 - s)
            q = v * (1.0 - s * f)
            t = v * (1.0 - s * (1.0 - f))
            i = i % 6
            if i == 0:
                r, g, b = v, t, p
            elif i == 1:
                r, g, b = q, v, p
            elif i == 2:
                r, g, b = p, v, t
            elif i == 3:
                r, g, b = p, q, v
            elif i == 4:
                r, g, b = t, p, v
            elif i == 5:
                r, g, b = v, p, q

        # 转换为16进制颜色代码
        return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))

    def change_theme(self, theme_name):
        """切换主题"""
        if self.theme_manager:
            theme = self.theme_manager.get_theme(theme_name)
            if theme:
                # 更新画布背景
                self.album_canvas.configure(bg=theme["bg"])

                # 更新文字颜色
                if self.song_text_ref:
                    self.album_canvas.itemconfig(self.song_text_ref, fill=theme["text"])
                if self.artist_text_ref:
                    self.album_canvas.itemconfig(self.artist_text_ref, fill=theme["secondary_text"])

                # 更新歌词颜色
                self._update_lyrics_colors(theme)

    def _update_lyrics_colors(self, theme):
        """更新歌词颜色 - 重新绘制所有歌词"""
        # 清除现有歌词
        self._clear_lyrics()

        # 如果有歌词数据，重新绘制
        if hasattr(self, 'all_lyrics_data') and self.all_lyrics_data:
            self._draw_lyrics(theme)
        else:
            self._draw_no_lyrics(theme)

        # 重新绘制歌曲信息
        if hasattr(self, 'track_info') and self.track_info:
            self._draw_song_info(theme)
        else:
            self._draw_default_song_info(theme)

    def extract_colors_from_album(self, image):
        """从专辑图提取主题色"""
        try:
            # 缩小图片以加快处理速度
            small_img = image.resize((100, 100), Image.Resampling.LANCZOS)

            # 转换为RGB
            if small_img.mode != 'RGB':
                small_img = small_img.convert('RGB')

            # 获取主要颜色
            colors = small_img.getcolors(10000)  # 获取所有颜色
            if colors:
                colors.sort(reverse=True)  # 按出现频率排序
                dominant_color = colors[0][1]  # 获取最主要的颜色

                # 转换为十六进制
                hex_color = '#{:02x}{:02x}{:02x}'.format(*dominant_color)

                # 根据主色生成主题
                self._generate_theme_from_color(hex_color)

        except Exception as e:
            print(f"提取颜色失败: {e}")

    def _generate_theme_from_color(self, hex_color):
        """根据主色生成主题"""
        # 简单的颜色转换逻辑
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)

        # 计算亮度
        brightness = (r * 299 + g * 587 + b * 114) / 1000

        if brightness > 128:
            # 亮色主题
            text_color = "#2c3e50"
            bg_color = self._adjust_brightness(hex_color, 0.9)
        else:
            # 暗色主题
            text_color = "#ecf0f1"
            bg_color = self._adjust_brightness(hex_color, 0.3)

        # 创建临时主题
        dynamic_theme = {
            "bg": bg_color,
            "text": text_color,
            "accent": hex_color,
            "secondary": self._adjust_brightness(hex_color, 0.7)
        }

        # 应用动态主题
        self._apply_dynamic_theme(dynamic_theme)

    def _adjust_brightness(self, hex_color, factor):
        """调整颜色亮度"""
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)

        r = min(255, int(r * factor))
        g = min(255, int(g * factor))
        b = min(255, int(b * factor))

        return f'#{r:02x}{g:02x}{b:02x}'

    def _apply_dynamic_theme(self, dynamic_theme):
        """应用动态主题（占位方法）"""
        # 这里可以添加动态主题的应用逻辑
        pass