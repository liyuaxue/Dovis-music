import re
import time


class LyricsManager:
    def __init__(self):
        self.lyrics = {}  # 改为字典存储，key为时间戳
        self.translated_lyrics = {}  # 改为字典存储
        self.current_index = 0

    def parse_lrc(self, lrc_text):
        """解析LRC歌词"""
        self.lyrics = {}
        self.translated_lyrics = {}

        if not lrc_text:
            print("无歌词内容")
            return

        print(f"解析歌词，长度: {len(lrc_text)}")

        # 正则匹配时间标签和歌词
        pattern = r'\[(\d+):(\d+)\.(\d+)\](.*)'

        for line in lrc_text.split('\n'):
            match = re.match(pattern, line.strip())
            if match:
                minutes = int(match.group(1))
                seconds = int(match.group(2))
                milliseconds = int(match.group(3))
                text = match.group(4).strip()

                total_seconds = minutes * 60 + seconds + milliseconds / 100.0

                if text and not text.startswith('['):
                    self.lyrics[total_seconds] = text

        print(f"解析到 {len(self.lyrics)} 行歌词")

    def parse_translated_lrc(self, lrc_text):
        """解析翻译歌词"""
        if not lrc_text:
            return

        pattern = r'\[(\d+):(\d+)\.(\d+)\](.*)'

        for line in lrc_text.split('\n'):
            match = re.match(pattern, line.strip())
            if match:
                minutes = int(match.group(1))
                seconds = int(match.group(2))
                milliseconds = int(match.group(3))
                text = match.group(4).strip()

                total_seconds = minutes * 60 + seconds + milliseconds / 100.0

                if text and not text.startswith('['):
                    self.translated_lyrics[total_seconds] = text

    def get_current_lyric(self, current_time):
        """获取当前时间对应的歌词"""
        if not self.lyrics:
            return "", ""

        current_lyric = ""
        current_translated = ""

        # 找到最后一个时间小于等于当前时间的歌词
        sorted_times = sorted(self.lyrics.keys())
        for time_stamp in sorted_times:
            if time_stamp <= current_time:
                current_lyric = self.lyrics[time_stamp]

                # 查找对应的翻译歌词
                if time_stamp in self.translated_lyrics:
                    current_translated = self.translated_lyrics[time_stamp]
                else:
                    # 如果没有精确匹配，找时间最接近的翻译
                    closest_time = None
                    min_diff = float('inf')
                    for trans_time in self.translated_lyrics.keys():
                        diff = abs(trans_time - time_stamp)
                        if diff < min_diff and diff < 2.0:  # 时间差小于2秒
                            min_diff = diff
                            closest_time = trans_time

                    if closest_time is not None:
                        current_translated = self.translated_lyrics[closest_time]
            else:
                break

        return current_lyric, current_translated

    def get_all_lyrics(self):
        """获取所有歌词用于显示"""
        return self.lyrics, self.translated_lyrics