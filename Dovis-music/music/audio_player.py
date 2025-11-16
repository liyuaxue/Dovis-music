import threading
import time
import os
import tempfile
import random
import numpy as np
from typing import Optional, Callable


class AudioPlayer:
    def __init__(self):
        self.current_url = None
        self.is_playing = False
        self.is_paused = False
        self.volume = 0.7
        self.duration = 0
        self.position = 0
        self.update_callback = None
        self.current_format = None

        # 音频数据
        self.audio_data = None
        self.sample_rate = None

        # 使用临时目录
        self.temp_dir = tempfile.gettempdir()
        self.temp_file = None

        # 播放控制
        self._stop_event = threading.Event()
        self._play_thread = None
        self._stream = None

        # 导入音频库
        self._import_audio_libraries()

    def _import_audio_libraries(self):
        """导入音频处理库"""
        self.has_soundfile = False
        self.has_sounddevice = False
        self.has_pygame = False

        # 导入pygame
        try:
            import pygame
            from pygame import mixer
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
            self.mixer = mixer
            self.has_pygame = True
            print("✓ 成功导入 pygame mixer")
        except ImportError as e:
            print(f"✗ Pygame导入失败: {e}")

        # 导入soundfile和sounddevice（用于FLAC）
        try:
            import soundfile as sf
            import sounddevice as sd
            self.sf = sf
            self.sd = sd
            self.has_soundfile = True
            self.has_sounddevice = True
            print("✓ 成功导入 soundfile 和 sounddevice")
        except ImportError as e:
            print(f"✗ 音频库导入失败: {e}")

    def _get_file_extension(self, url):
        """从URL获取文件扩展名"""
        if not url:
            return 'mp3'

        if '.flac' in url.lower():
            return 'flac'
        elif '.mp3' in url.lower():
            return 'mp3'
        elif '.wav' in url.lower():
            return 'wav'
        else:
            return 'mp3'

    def _generate_temp_filename(self, extension):
        """生成唯一的临时文件名"""
        random_id = random.randint(1000, 9999)
        return os.path.join(self.temp_dir, f"gd_music_{random_id}.{extension}")

    def _download_audio(self, url, file_path):
        """下载音频文件"""
        import requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://music.163.com/'
        }

        print(f"开始下载: {url}")
        response = requests.get(url, stream=True, timeout=30, headers=headers)

        if response.status_code != 200:
            raise Exception(f"下载失败，状态码: {response.status_code}")

        total_size = 0
        with open(file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    total_size += len(chunk)

        if total_size < 1024:
            raise Exception("文件大小异常，可能下载失败")

        print(f"下载完成: {total_size} bytes")
        return total_size

    def _load_flac_with_soundfile(self, file_path):
        """使用soundfile加载FLAC文件"""
        try:
            print(f"使用soundfile加载FLAC: {file_path}")

            # 读取FLAC文件
            audio_data, sample_rate = self.sf.read(file_path)

            # 打印音频信息
            print(f"FLAC音频信息: 采样率={sample_rate}Hz, 形状={audio_data.shape}, 类型={audio_data.dtype}")

            # 确保是二维数组 (samples, channels)
            if audio_data.ndim == 1:
                audio_data = audio_data.reshape(-1, 1)
                print("转换为立体声")

            self.audio_data = audio_data
            self.sample_rate = sample_rate
            self.duration = len(audio_data) / sample_rate
            self._original_audio_data = self.audio_data.copy()

            print(f"✓ FLAC加载成功: {self.duration:.2f}秒, {sample_rate}Hz, {audio_data.shape[1]}声道")
            return True

        except Exception as e:
            print(f"✗ FLAC加载失败: {e}")
            return False

    def _load_mp3_with_pygame(self, file_path):
        """使用pygame加载MP3文件"""
        try:
            print(f"使用pygame加载MP3: {file_path}")

            # pygame直接加载MP3
            self.mixer.music.load(file_path)

            # 设置默认时长（实际应该获取真实时长）
            self.duration = 180  # 3分钟

            print(f"✓ MP3加载成功")
            return True

        except Exception as e:
            print(f"✗ MP3加载失败: {e}")
            return False

    def _play_flac_with_sounddevice(self):
        """使用sounddevice播放FLAC"""
        try:
            print("使用sounddevice播放FLAC...")

            # 确保应用当前音量设置
            if hasattr(self, '_original_audio_data') and self.audio_data is not None:
                self.audio_data = self._original_audio_data * self.volume

            # 直接播放
            self.sd.play(self.audio_data, self.sample_rate)
            self.is_playing = True

            # 启动位置更新线程
            def update_position():
                start_time = time.time()
                while self.is_playing and not self._stop_event.is_set():
                    if not self.is_paused:
                        current_time = time.time() - start_time
                        self.position = min(current_time, self.duration)

                        if self.update_callback:
                            self.update_callback(self.position)

                        # 检查是否播放完成
                        if current_time >= self.duration:
                            break

                    time.sleep(0.1)

                # 播放完成
                self.is_playing = False
                if self.update_callback:
                    self.update_callback(-1)
                print("FLAC播放完成")

            # 启动位置更新线程
            position_thread = threading.Thread(target=update_position, daemon=True)
            position_thread.start()

            print("✓ FLAC播放开始")
            return True

        except Exception as e:
            print(f"✗ FLAC播放失败: {e}")
            return False

    def _play_mp3_with_pygame(self):
        """使用pygame播放MP3"""
        try:
            print("使用pygame播放MP3...")

            # 开始播放
            self.mixer.music.play()
            self.is_playing = True

            # 设置音量
            self.mixer.music.set_volume(self.volume)

            # 启动位置更新线程
            def update_position():
                start_time = time.time()
                while self.is_playing and not self._stop_event.is_set():
                    if not self.is_paused:
                        current_time = time.time() - start_time
                        self.position = min(current_time, self.duration)

                        if self.update_callback:
                            self.update_callback(self.position)

                        # 检查是否播放完成
                        if not self.mixer.music.get_busy() and not self.is_paused:
                            break

                    time.sleep(0.1)

                # 播放完成
                self.is_playing = False
                if self.update_callback:
                    self.update_callback(-1)
                print("MP3播放完成")

            # 启动位置更新线程
            position_thread = threading.Thread(target=update_position, daemon=True)
            position_thread.start()

            print("✓ MP3播放开始")
            return True

        except Exception as e:
            print(f"✗ MP3播放失败: {e}")
            return False

    def load(self, url):
        """加载音乐"""
        try:
            self.stop()
            self.cleanup()

            file_ext = self._get_file_extension(url)
            self.current_format = file_ext
            self.temp_file = self._generate_temp_filename(file_ext)

            print(f"开始处理音频: {url}")
            print(f"文件格式: {file_ext}")

            # 下载文件
            file_size = self._download_audio(url, self.temp_file)

            # 根据格式选择加载方法
            if file_ext == 'flac':
                if self.has_soundfile and self._load_flac_with_soundfile(self.temp_file):
                    self.current_url = url
                    return True
                else:
                    print("✗ FLAC加载失败")
                    return False

            elif file_ext == 'mp3':
                if self.has_pygame and self._load_mp3_with_pygame(self.temp_file):
                    self.current_url = url
                    return True
                else:
                    print("✗ MP3加载失败")
                    return False

            else:
                print(f"✗ 不支持的文件格式: {file_ext}")
                return False

        except Exception as e:
            print(f"✗ 加载音乐失败: {e}")
            self.cleanup()
            return False

    def play(self):
        """播放音乐"""
        if not self.current_url:
            return False

        self._stop_event.clear()

        # 根据格式选择播放方法
        if self.current_format == 'flac' and self.has_sounddevice:
            self._play_thread = threading.Thread(target=self._play_flac_with_sounddevice, daemon=True)
        elif self.current_format == 'mp3' and self.has_pygame:
            self._play_thread = threading.Thread(target=self._play_mp3_with_pygame, daemon=True)
        else:
            print("✗ 没有可用的播放方法")
            return False

        self._play_thread.start()
        print("✓ 播放线程启动")
        return True

    def pause(self):
        """暂停播放"""
        if self.is_playing and not self.is_paused:
            if self.current_format == 'flac':
                self.sd.stop()
            elif self.current_format == 'mp3':
                self.mixer.music.pause()

            self.is_paused = True
            print("⏸ 音乐暂停")

    def unpause(self):
        """继续播放"""
        if self.is_playing and self.is_paused:
            if self.current_format == 'flac':
                # 对于FLAC，重新从当前位置播放并应用音量
                current_pos = self.position
                self.stop()
                self.position = current_pos
                self.play()  # 重新播放时会应用音量
            elif self.current_format == 'mp3':
                self.mixer.music.unpause()

            self.is_paused = False
            print("▶ 继续播放")

    def stop(self):
        """停止播放"""
        self._stop_event.set()

        if self.current_format == 'flac' and self.has_sounddevice:
            try:
                self.sd.stop()
            except:
                pass
        elif self.current_format == 'mp3' and self.has_pygame:
            try:
                self.mixer.music.stop()
            except:
                pass

        # 等待播放线程结束
        if self._play_thread and self._play_thread.is_alive():
            self._play_thread.join(timeout=1.0)

        self.is_playing = False
        self.is_paused = False
        self.position = 0
        print("⏹ 音乐停止")

    def set_volume(self, volume):
        """设置音量 0.0-1.0"""
        self.volume = max(0.0, min(1.0, volume))

        # MP3格式的音量控制
        if self.current_format == 'mp3' and self.has_pygame and self.is_playing:
            self.mixer.music.set_volume(self.volume)

        # FLAC格式的音量控制 - 新增这部分
        elif self.current_format == 'flac' and self.has_sounddevice and self.audio_data is not None:
            # 应用音量到音频数据
            self._apply_volume_to_audio_data()

        print(f"音量设置为: {self.volume}")

    def _apply_volume_to_audio_data(self):
        """将音量设置应用到FLAC音频数据"""
        if self.audio_data is not None:
            try:
                # 创建音量调整后的音频数据副本
                # 注意：这会修改原始音频数据，所以需要备份原始数据
                if not hasattr(self, '_original_audio_data'):
                    # 备份原始音频数据
                    self._original_audio_data = self.audio_data.copy()

                # 应用音量增益
                adjusted_audio = self._original_audio_data * self.volume
                self.audio_data = adjusted_audio

                print(f"✓ FLAC音量已应用: {self.volume}")

            except Exception as e:
                print(f"✗ FLAC音量应用失败: {e}")

    def seek(self, position):
        """跳转到指定位置"""
        if self.current_url and self.is_playing:
            was_playing = self.is_playing
            self.stop()

            # 设置新位置
            self.position = max(0, min(position, self.duration))

            # 重新播放
            if was_playing:
                self.play()

    def load_file(self, file_path):
        """加载本地音频文件"""
        try:
            self.stop()
            self.cleanup()

            # 检查文件是否存在
            if not os.path.exists(file_path):
                print(f"✗ 文件不存在: {file_path}")
                return False

            # 获取文件扩展名
            file_ext = os.path.splitext(file_path)[1].lower().replace('.', '')
            if not file_ext:
                file_ext = 'mp3'  # 默认格式

            self.current_format = file_ext
            self.temp_file = file_path  # 直接使用原文件路径，不复制

            print(f"开始处理本地音频: {file_path}")
            print(f"文件格式: {file_ext}")

            # 根据格式选择加载方法
            if file_ext == 'flac':
                if self.has_soundfile and self._load_flac_with_soundfile(self.temp_file):
                    self.current_url = f"file://{file_path}"  # 标记为本地文件
                    return True
                else:
                    print("✗ FLAC加载失败")
                    return False

            elif file_ext == 'mp3':
                if self.has_pygame and self._load_mp3_with_pygame(self.temp_file):
                    self.current_url = f"file://{file_path}"  # 标记为本地文件
                    return True
                else:
                    print("✗ MP3加载失败")
                    return False

            elif file_ext == 'wav':
                # 添加WAV文件支持
                if self.has_soundfile and self._load_wav_with_soundfile(self.temp_file):
                    self.current_url = f"file://{file_path}"
                    return True
                else:
                    print("✗ WAV加载失败")
                    return False

            else:
                print(f"✗ 不支持的文件格式: {file_ext}")
                return False

        except Exception as e:
            print(f"✗ 加载本地文件失败: {e}")
            self.cleanup()
            return False

    def _load_wav_with_soundfile(self, file_path):
        """使用soundfile加载WAV文件"""
        try:
            print(f"使用soundfile加载WAV: {file_path}")

            # 读取WAV文件
            audio_data, sample_rate = self.sf.read(file_path)

            # 打印音频信息
            print(f"WAV音频信息: 采样率={sample_rate}Hz, 形状={audio_data.shape}, 类型={audio_data.dtype}")

            # 确保是二维数组 (samples, channels)
            if audio_data.ndim == 1:
                audio_data = audio_data.reshape(-1, 1)
                print("转换为立体声")

            self.audio_data = audio_data
            self.sample_rate = sample_rate
            self.duration = len(audio_data) / sample_rate
            self._original_audio_data = self.audio_data.copy()

            print(f"✓ WAV加载成功: {self.duration:.2f}秒, {sample_rate}Hz, {audio_data.shape[1]}声道")
            return True

        except Exception as e:
            print(f"✗ WAV加载失败: {e}")
            return False

    def cleanup(self):
        """清理资源"""
        try:
            if (self.temp_file and
                    os.path.exists(self.temp_file) and
                    self.temp_file.startswith(tempfile.gettempdir())):
                time.sleep(0.1)
                os.remove(self.temp_file)
                print(f"🗑️ 临时文件已清理: {self.temp_file}")
            self.temp_file = None
        except Exception as e:
            print(f"清理临时文件失败: {e}")
            self.temp_file = None

        # 清理音频数据
        self.audio_data = None
        self.sample_rate = None


    def __del__(self):
        """析构函数"""
        self.stop()
        self.cleanup()

    def get_status(self):
        """获取播放状态"""
        backend = "sounddevice" if self.current_format == 'flac' else "pygame"
        channels = self.audio_data.shape[1] if self.audio_data is not None else 2

        return {
            "playing": self.is_playing,
            "paused": self.is_paused,
            "volume": self.volume,
            "position": self.position,
            "duration": self.duration,
            "url": self.current_url,
            "format": self.current_format,
            "backend": backend,
            "sample_rate": self.sample_rate,
            "channels": channels
        }