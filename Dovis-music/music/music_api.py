import requests
import json
import time
from config import API_BASE_URL
from config import MUSIC_SOURCES, QUALITY_OPTIONS, PLAY_MODES


class MusicAPI:
    def __init__(self):
        self.base_url = API_BASE_URL

    def _make_request_with_retry(self, params, retry_count=3, timeout=15, operation_name="请求"):
        """统一的带重试机制的请求函数"""
        for attempt in range(retry_count):
            try:
                print(f"{operation_name}请求参数 (尝试 {attempt + 1}/{retry_count}): {params}")

                # 添加请求头，模拟浏览器
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }

                # 动态调整超时时间
                current_timeout = timeout + attempt * 5

                response = requests.get(self.base_url, params=params, headers=headers, timeout=current_timeout)
                print(f"响应状态码: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    print(f"解析后的数据: {data}")
                    return data
                else:
                    print(f"请求失败，状态码: {response.status_code}")
                    if attempt < retry_count - 1:
                        wait_time = (attempt + 1) * 2
                        print(f"等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                        continue
                    return {"code": response.status_code, "msg": "请求失败"}

            except requests.exceptions.ConnectionError as e:
                print(f"连接错误 (尝试 {attempt + 1}/{retry_count}): {e}")
                if attempt < retry_count - 1:
                    wait_time = (attempt + 1) * 3
                    print(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                    continue
                return {"code": -1, "msg": f"网络连接失败: {str(e)}"}

            except requests.exceptions.Timeout as e:
                print(f"请求超时 (尝试 {attempt + 1}/{retry_count}): {e}")
                if attempt < retry_count - 1:
                    wait_time = (attempt + 1) * 2
                    print(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                    continue
                return {"code": -1, "msg": "请求超时"}

            except Exception as e:
                print(f"{operation_name}异常 (尝试 {attempt + 1}/{retry_count}): {str(e)}")
                if attempt < retry_count - 1:
                    wait_time = (attempt + 1) * 2
                    print(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                    continue
                return {"code": -1, "msg": f"{operation_name}失败: {str(e)}"}

        # 所有重试都失败
        return {"code": -1, "msg": f"经过 {retry_count} 次重试后仍无法完成{operation_name}"}

    def search(self, keyword, source="网易云音乐", count=20, page=1, retry_count=3):
        """搜索音乐"""
        # 将中文音源名称转换为英文代码
        source_mapping = {v: k for k, v in MUSIC_SOURCES.items()}
        source_code = source_mapping.get(source, "netease")  # 默认网易云音乐

        params = {
            "types": "search",
            "source": source_code,
            "name": keyword,
            "count": count,
            "pages": page
        }

        result = self._make_request_with_retry(params, retry_count, 15, "搜索音乐")

        # 处理搜索结果的特殊格式
        if isinstance(result, list):
            return {"code": 200, "data": result}
        return result

    def get_song_url(self, track_id, source="网易云音乐", quality="Hi-Res", retry_count=3):
        """获取歌曲播放链接"""
        # 将中文音源名称转换为英文代码
        source_mapping = {v: k for k, v in MUSIC_SOURCES.items()}
        # 将中文音质名称转换为数字代码
        quality_mapping = {v: k for k, v in QUALITY_OPTIONS.items()}

        # 转换参数
        source_code = source_mapping.get(source, "netease")  # 默认网易云音乐
        quality_code = quality_mapping.get(quality, "999")  # 默认Hi-Res

        params = {
            "types": "url",
            "source": source_code,
            "id": track_id,
            "br": quality_code
        }

        result = self._make_request_with_retry(params, retry_count, 10, "获取播放链接")

        # 如果成功获取到URL，检查音频文件可访问性
        if result and 'url' in result and result['url']:
            url = result['url']

            # 检测文件格式
            file_format = "未知"
            if '.flac' in url.lower():
                file_format = "FLAC"
            elif '.mp3' in url.lower():
                file_format = "MP3"
            elif '.wav' in url.lower():
                file_format = "WAV"

            print(f"检测到音频格式: {file_format}, 音质: {quality}")
            result['format'] = file_format

            # 检查文件是否可访问
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            try:
                head_response = requests.head(url, timeout=5, headers=headers)
                if head_response.status_code == 200:
                    print("音频文件可访问")
                else:
                    print(f"音频文件访问异常: {head_response.status_code}")
            except Exception as head_e:
                print(f"音频文件访问检查失败: {str(head_e)}")

        return result

    def get_album_pic(self, pic_id, source="netease", size=300, retry_count=3):
        """获取专辑图片"""
        params = {
            "types": "pic",
            "source": source,
            "id": pic_id,
            "size": size
        }

        return self._make_request_with_retry(params, retry_count, 10, "获取专辑图片")

    def get_lyrics(self, lyric_id, source="netease", retry_count=3):
        """获取歌词"""
        params = {
            "types": "lyric",
            "source": source,
            "id": lyric_id
        }

        return self._make_request_with_retry(params, retry_count, 10, "获取歌词")