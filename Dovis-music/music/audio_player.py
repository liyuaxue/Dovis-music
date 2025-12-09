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
        self.audio_data = None
        self.sample_rate = None
        self.temp_dir = tempfile.gettempdir()
        self.temp_file = None
        self._stop_event = threading.Event()
        self._play_thread = None
        self._stream = None
        self._playback_position = 0
        self._volume_lock = threading.Lock()
        self._import_audio_libraries()

    def _import_audio_libraries(self):
        """导入音频处理库"""
        self.has_soundfile = False
        self.has_sounddevice = False
        self.has_pygame = False

        try:
            import pygame
            from pygame import mixer
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
            self.mixer = mixer
            self.has_pygame = True
            print("✓ 成功导入 pygame mixer")
        except ImportError as e:
            print(f"✗ Pygame导入失败: {e}")

        try:
            import soundfile as sf
            import sounddevice as sd
            self.sf = sf
            self.sd = sd
            self.CallbackStop = sd.CallbackStop
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
            audio_data, sample_rate = self.sf.read(file_path)
            print(f"FLAC音频信息: 采样率={sample_rate}Hz, 形状={audio_data.shape}, 类型={audio_data.dtype}")

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
        """使用sounddevice流式播放FLAC（支持实时音量调整）"""
        try:
            print("使用sounddevice播放FLAC...")

            if not hasattr(self, '_playback_position') or self._playback_position < 0:
                self._playback_position = 0
            
            if hasattr(self, 'position') and self.position > 0 and self.sample_rate > 0:
                calculated_position = int(self.position * self.sample_rate)
                if calculated_position < len(self._original_audio_data):
                    self._playback_position = calculated_position
                    print(f"从保存的位置继续播放: {self.position:.2f}秒 (样本: {self._playback_position})")

            def audio_callback(outdata, frames, time_info, status):
                if status:
                    print(f"音频流状态: {status}")

                if self._stop_event.is_set() or not self.is_playing:
                    outdata.fill(0)
                    raise self.CallbackStop

                with self._volume_lock:
                    current_volume = self.volume

                remaining_samples = len(self._original_audio_data) - self._playback_position
                if remaining_samples <= 0:
                    outdata.fill(0)
                    raise self.CallbackStop

                frames_to_read = min(frames, remaining_samples)
                audio_chunk = self._original_audio_data[
                    self._playback_position:self._playback_position + frames_to_read
                ]

                if audio_chunk.ndim == 1:
                    audio_chunk = audio_chunk.reshape(-1, 1)
                
                if audio_chunk.shape[0] < frames:
                    padding = np.zeros((frames - audio_chunk.shape[0], audio_chunk.shape[1]), 
                                     dtype=audio_chunk.dtype)
                    audio_chunk = np.vstack([audio_chunk, padding])

                volume_adjusted = audio_chunk * current_volume
                if outdata.dtype == np.float32:
                    volume_adjusted = np.clip(volume_adjusted, -1.0, 1.0).astype(np.float32)
                else:
                    volume_adjusted = volume_adjusted.astype(outdata.dtype)
                outdata[:] = volume_adjusted
                self._playback_position += frames_to_read

                if self._playback_position >= len(self._original_audio_data):
                    raise self.CallbackStop

            try:
                output_dtype = np.float32
                if self._original_audio_data.dtype != np.float32:
                    pass
                
                self._stream = self.sd.OutputStream(
                    samplerate=self.sample_rate,
                    channels=self._original_audio_data.shape[1],
                    callback=audio_callback,
                    dtype=output_dtype,
                    blocksize=4096
                )
                
                self.is_playing = True
                self._stream.start()

                def update_position():
                    while self.is_playing and not self._stop_event.is_set():
                        if not self.is_paused:
                            if hasattr(self, '_playback_position') and self.sample_rate > 0:
                                current_time = self._playback_position / self.sample_rate
                                self.position = min(current_time, self.duration)
                            else:
                                self.position = min(self.position + 0.1, self.duration)

                            if self.update_callback:
                                self.update_callback(self.position)

                            if hasattr(self, '_playback_position') and \
                               self._playback_position >= len(self._original_audio_data):
                                break

                        time.sleep(0.1)

                    self.is_playing = False
                    if self.update_callback:
                        self.update_callback(-1)
                    print("FLAC播放完成")

                position_thread = threading.Thread(target=update_position, daemon=True)
                position_thread.start()

                print("✓ FLAC播放开始（流式播放，支持实时音量调整）")
                return True

            except Exception as stream_error:
                print(f"✗ 创建音频流失败: {stream_error}")
                return self._play_flac_simple()

        except Exception as e:
            print(f"✗ FLAC播放失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _play_flac_simple(self):
        """简单的FLAC播放方式（回退方案）"""
        try:
            print("使用简单方式播放FLAC...")
            if hasattr(self, '_original_audio_data') and self._original_audio_data is not None:
                start_sample = 0
                if hasattr(self, '_playback_position') and self._playback_position > 0:
                    start_sample = self._playback_position
                elif hasattr(self, 'position') and self.position > 0 and self.sample_rate > 0:
                    start_sample = int(self.position * self.sample_rate)
                
                if start_sample > 0 and start_sample < len(self._original_audio_data):
                    audio_to_play = self._original_audio_data[start_sample:] * self.volume
                    start_time_offset = start_sample / self.sample_rate
                    print(f"从位置 {start_time_offset:.2f}秒开始播放（简单模式）")
                else:
                    audio_to_play = self._original_audio_data * self.volume
                    start_time_offset = 0
                
                self.sd.play(audio_to_play, self.sample_rate)
                self.is_playing = True
                
                def update_position():
                    start_time = time.time() - start_time_offset
                    while self.is_playing and not self._stop_event.is_set():
                        if not self.is_paused:
                            current_time = time.time() - start_time
                            self.position = min(current_time, self.duration)
                            if self.sample_rate > 0:
                                self._playback_position = int(self.position * self.sample_rate)
                            if self.update_callback:
                                self.update_callback(self.position)
                            if current_time >= self.duration:
                                break
                        time.sleep(0.1)
                    self.is_playing = False
                    if self.update_callback:
                        self.update_callback(-1)
                    print("FLAC播放完成")
                
                threading.Thread(target=update_position, daemon=True).start()
                print("✓ FLAC播放开始（简单模式）")
                return True
            return False
        except Exception as e:
            print(f"✗ 简单播放失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _play_mp3_with_pygame(self):
        """使用pygame播放MP3"""
        try:
            print("使用pygame播放MP3...")
            self.mixer.music.play()
            self.is_playing = True
            self.mixer.music.set_volume(self.volume)

            def update_position():
                start_time = time.time()
                while self.is_playing and not self._stop_event.is_set():
                    if not self.is_paused:
                        current_time = time.time() - start_time
                        self.position = min(current_time, self.duration)

                        if self.update_callback:
                            self.update_callback(self.position)

                        if not self.mixer.music.get_busy() and not self.is_paused:
                            break

                    time.sleep(0.1)

                self.is_playing = False
                if self.update_callback:
                    self.update_callback(-1)
                print("MP3播放完成")

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
            file_size = self._download_audio(url, self.temp_file)

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
                if self._stream is not None:
                    self._stream.stop()
                else:
                    self.sd.stop()
            elif self.current_format == 'mp3':
                self.mixer.music.pause()

            self.is_paused = True
            print("⏸ 音乐暂停")

    def unpause(self):
        """继续播放"""
        if self.is_playing and self.is_paused:
            if self.current_format == 'flac':
                if self._stream is not None:
                    self._stream.start()
                else:
                    current_pos = self.position
                    self.stop()
                    self.position = current_pos
                    self.play()
            elif self.current_format == 'mp3':
                self.mixer.music.unpause()

            self.is_paused = False
            print("▶ 继续播放")

    def stop(self):
        """停止播放"""
        self._stop_event.set()

        if self.current_format == 'flac' and self.has_sounddevice:
            try:
                if self._stream is not None:
                    self._stream.stop()
                    self._stream.close()
                    self._stream = None
                else:
                    self.sd.stop()
            except Exception as e:
                print(f"停止FLAC播放时出错: {e}")
        elif self.current_format == 'mp3' and self.has_pygame:
            try:
                self.mixer.music.stop()
            except:
                pass

        if self._play_thread and self._play_thread.is_alive():
            self._play_thread.join(timeout=1.0)

        self.is_playing = False
        self.is_paused = False
        self.position = 0
        self._playback_position = 0
        print("⏹ 音乐停止")

    def set_volume(self, volume):
        """设置音量 0.0-1.0"""
        with self._volume_lock:
            self.volume = max(0.0, min(1.0, volume))

        if self.current_format == 'mp3' and self.has_pygame and self.is_playing:
            self.mixer.music.set_volume(self.volume)
            print(f"✓ MP3音量已设置: {self.volume}")
        elif self.current_format == 'flac' and self.has_sounddevice:
            if self._stream is not None:
                print(f"✓ FLAC音量已设置（流式播放）: {self.volume}")
            elif self.is_playing:
                self._apply_volume_to_audio_data()
            else:
                print(f"✓ FLAC音量已设置（待播放时应用）: {self.volume}")

        print(f"音量设置为: {self.volume}")

    def _apply_volume_to_audio_data(self):
        """将音量设置应用到FLAC音频数据"""
        if self.audio_data is not None:
            try:
                if not hasattr(self, '_original_audio_data'):
                    self._original_audio_data = self.audio_data.copy()

                adjusted_audio = self._original_audio_data * self.volume
                self.audio_data = adjusted_audio
                print(f"✓ FLAC音量已应用: {self.volume}")

            except Exception as e:
                print(f"✗ FLAC音量应用失败: {e}")

    def seek(self, position):
        """跳转到指定位置"""
        if not self.current_url:
            return False
        
        target_position = max(0.0, min(float(position), self.duration))
        
        if self.current_format == 'flac' and self.has_sounddevice:
            if hasattr(self, '_original_audio_data') and self._original_audio_data is not None:
                target_sample_position = int(target_position * self.sample_rate)
                target_sample_position = max(0, min(target_sample_position, len(self._original_audio_data)))
                
                was_playing = self.is_playing
                was_paused = self.is_paused
                self.stop()
                self._playback_position = target_sample_position
                self.position = target_position
                
                if was_playing or was_paused:
                    self.play()
                    if was_paused:
                        self.pause()
                
                print(f"✓ FLAC跳转到: {target_position:.2f}秒 (样本位置: {target_sample_position})")
                return True
            else:
                print("✗ FLAC音频数据不可用，无法跳转")
                return False
                
        elif self.current_format == 'mp3' and self.has_pygame:
            was_playing = self.is_playing
            was_paused = self.is_paused
            self.stop()
            self.position = target_position
            
            if self.temp_file and os.path.exists(self.temp_file):
                if self._load_mp3_with_pygame(self.temp_file):
                    if was_playing or was_paused:
                        self.play()
                        if was_paused:
                            self.pause()
                    
                    print(f"⚠ MP3跳转: {target_position:.2f}秒 (pygame限制：会从头播放，无法精确跳转)")
                    print("   提示：使用FLAC格式可获得精确的seek支持")
                    return True
                else:
                    print("✗ MP3重新加载失败")
                    return False
            else:
                print("✗ MP3文件不存在，无法跳转")
                return False
        else:
            print(f"✗ 不支持的格式或播放器未就绪: {self.current_format}")
            return False

    def load_file(self, file_path):
        """加载本地音频文件"""
        try:
            self.stop()
            self.cleanup()

            if not os.path.exists(file_path):
                print(f"✗ 文件不存在: {file_path}")
                return False

            file_ext = os.path.splitext(file_path)[1].lower().replace('.', '')
            if not file_ext:
                file_ext = 'mp3'

            self.current_format = file_ext
            self.temp_file = file_path

            print(f"开始处理本地音频: {file_path}")
            print(f"文件格式: {file_ext}")

            if file_ext == 'flac':
                if self.has_soundfile and self._load_flac_with_soundfile(self.temp_file):
                    self.current_url = f"file://{file_path}"
                    return True
                else:
                    print("✗ FLAC加载失败")
                    return False

            elif file_ext == 'mp3':
                if self.has_pygame and self._load_mp3_with_pygame(self.temp_file):
                    self.current_url = f"file://{file_path}"
                    return True
                else:
                    print("✗ MP3加载失败")
                    return False

            elif file_ext == 'wav':
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
            audio_data, sample_rate = self.sf.read(file_path)
            print(f"WAV音频信息: 采样率={sample_rate}Hz, 形状={audio_data.shape}, 类型={audio_data.dtype}")

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
        max_retries = 3
        retry_delay = 0.2
        
        if self.temp_file and os.path.exists(self.temp_file):
            if self.temp_file.startswith(tempfile.gettempdir()):
                for attempt in range(max_retries):
                    try:
                        time.sleep(retry_delay * (attempt + 1))  # 递增延迟
                        os.remove(self.temp_file)
                        print(f"🗑️ 临时文件已清理: {self.temp_file}")
                        break
                    except (OSError, PermissionError) as e:
                        if attempt == max_retries - 1:
                            print(f"清理临时文件失败 (已重试{max_retries}次): {e}")
                        else:
                            print(f"清理临时文件失败，{retry_delay * (attempt + 2)}秒后重试: {e}")
            self.temp_file = None

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