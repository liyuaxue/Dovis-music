import requests
import json
import time
import hashlib
import threading
from collections import OrderedDict
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from config import API_BASE_URL
from config import MUSIC_SOURCES, QUALITY_OPTIONS, PLAY_MODES


class APICache:
    """API响应缓存管理器"""
    
    def __init__(self, max_size: int = 100, ttl_seconds: int = 300):
        """
        初始化缓存
        
        Args:
            max_size: 最大缓存条目数
            ttl_seconds: 缓存过期时间（秒），默认5分钟
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.RLock()
    
    def _generate_key(self, params: Dict[str, Any]) -> str:
        """生成缓存键"""
        # 对参数进行排序以确保一致性
        sorted_params = json.dumps(params, sort_keys=True)
        return hashlib.md5(sorted_params.encode('utf-8')).hexdigest()
    
    def get(self, params: Dict[str, Any]) -> Optional[Any]:
        """获取缓存"""
        with self._lock:
            key = self._generate_key(params)
            if key in self._cache:
                data, timestamp = self._cache[key]
                # 检查是否过期
                if time.time() - timestamp < self.ttl_seconds:
                    # 移动到末尾（LRU）
                    self._cache.move_to_end(key)
                    return data
                else:
                    # 过期，删除
                    del self._cache[key]
            return None
    
    def set(self, params: Dict[str, Any], data: Any) -> None:
        """设置缓存"""
        with self._lock:
            key = self._generate_key(params)
            # 如果已存在，先删除
            if key in self._cache:
                del self._cache[key]
            # 添加新条目
            self._cache[key] = (data, time.time())
            # 如果超过最大大小，删除最旧的
            while len(self._cache) > self.max_size:
                self._cache.popitem(last=False)
    
    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()
    
    def invalidate(self, params: Dict[str, Any]) -> None:
        """使特定缓存失效"""
        with self._lock:
            key = self._generate_key(params)
            if key in self._cache:
                del self._cache[key]


class RequestDeduplicator:
    """请求去重器 - 避免同时发起相同的请求"""
    
    def __init__(self):
        self._pending_requests: Dict[str, threading.Event] = {}
        self._pending_results: Dict[str, Any] = {}
        self._lock = threading.RLock()
    
    def _generate_key(self, params: Dict[str, Any]) -> str:
        """生成请求键"""
        sorted_params = json.dumps(params, sort_keys=True)
        return hashlib.md5(sorted_params.encode('utf-8')).hexdigest()
    
    def wait_or_execute(self, params: Dict[str, Any], execute_func) -> Any:
        """
        等待正在进行的相同请求，或执行新请求
        
        Args:
            params: 请求参数
            execute_func: 执行函数，返回请求结果
            
        Returns:
            请求结果
        """
        key = self._generate_key(params)
        
        with self._lock:
            # 检查是否有正在进行的相同请求
            if key in self._pending_requests:
                event = self._pending_requests[key]
                # 等待其他请求完成
                event.wait(timeout=30)  # 最多等待30秒
                # 检查是否有结果
                if key in self._pending_results:
                    return self._pending_results.pop(key)
                return None
            
            # 创建新请求
            event = threading.Event()
            self._pending_requests[key] = event
        
        try:
            # 执行请求
            result = execute_func()
            
            # 保存结果
            with self._lock:
                self._pending_results[key] = result
                event.set()  # 通知等待的线程
                # 延迟删除，给其他线程时间获取结果
                threading.Timer(1.0, lambda: self._cleanup(key)).start()
            
            return result
        except Exception as e:
            # 请求失败，也要通知等待的线程
            with self._lock:
                event.set()
                if key in self._pending_requests:
                    del self._pending_requests[key]
            raise e
    
    def _cleanup(self, key: str) -> None:
        """清理完成的请求"""
        with self._lock:
            if key in self._pending_requests:
                del self._pending_requests[key]
            if key in self._pending_results:
                del self._pending_results[key]


class RateLimiter:
    """请求限流器"""
    
    def __init__(self, max_requests: int = 10, time_window: float = 1.0):
        """
        初始化限流器
        
        Args:
            max_requests: 时间窗口内最大请求数
            time_window: 时间窗口（秒）
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self._request_times = []
        self._lock = threading.Lock()
    
    def acquire(self) -> None:
        """获取请求许可，如果超过限制则等待"""
        with self._lock:
            now = time.time()
            # 移除过期的请求时间
            self._request_times = [t for t in self._request_times if now - t < self.time_window]
            
            # 如果超过限制，等待
            if len(self._request_times) >= self.max_requests:
                # 计算需要等待的时间
                oldest_time = self._request_times[0]
                wait_time = self.time_window - (now - oldest_time) + 0.1
                if wait_time > 0:
                    time.sleep(wait_time)
                    # 重新清理
                    now = time.time()
                    self._request_times = [t for t in self._request_times if now - t < self.time_window]
            
            # 记录本次请求时间
            self._request_times.append(time.time())


class MusicAPI:
    """改进的音乐API客户端 - 支持连接池、缓存、去重、限流等"""
    
    def __init__(self, enable_cache: bool = True, enable_deduplication: bool = True,
                 enable_rate_limit: bool = True, max_concurrent: int = 5):
        """
        初始化API客户端
        
        Args:
            enable_cache: 是否启用响应缓存
            enable_deduplication: 是否启用请求去重
            enable_rate_limit: 是否启用请求限流
            max_concurrent: 最大并发请求数
        """
        self.base_url = API_BASE_URL

        # 创建Session连接池（复用TCP连接）
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',
            'Connection': 'keep-alive'
        })
        
        # 配置连接池
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=max_concurrent,
            pool_maxsize=max_concurrent,
            max_retries=0  # 我们自己处理重试
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        # 初始化缓存
        self.cache = APICache(max_size=200, ttl_seconds=300) if enable_cache else None
        
        # 初始化请求去重器
        self.deduplicator = RequestDeduplicator() if enable_deduplication else None
        
        # 初始化限流器（每秒最多10个请求）
        self.rate_limiter = RateLimiter(max_requests=10, time_window=1.0) if enable_rate_limit else None
        
        # 并发控制
        self.semaphore = threading.Semaphore(max_concurrent)
        
        # API健康状态
        self._api_healthy = True  # 默认认为API可用
        self._last_health_check = 0
        self._health_check_interval = 60  # 60秒检查一次
        self._consecutive_failures = 0  # 连续失败次数
        self._max_consecutive_failures = 3  # 连续失败3次才认为不可用
        
        # 统计信息
        self.stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'failed_requests': 0,
            'retry_count': 0
        }
    
    def _check_api_health(self) -> bool:
        """
        检查API健康状态（非阻塞，仅作为参考）
        
        注意：健康检查失败不会阻止实际请求，因为：
        1. 网络问题可能是暂时的
        2. 重试机制已经可以处理网络问题
        3. 实际请求可能成功，即使健康检查失败
        """
        now = time.time()
        # 如果最近检查过，直接返回缓存的状态
        if now - self._last_health_check < self._health_check_interval:
            return self._api_healthy
        
        # 执行健康检查（简单的搜索请求）
        # 使用较短的超时，避免阻塞太久
        try:
            test_params = {
                "types": "search",
                "source": "netease",
                "name": "test",
                "count": 1,
                "pages": 1
            }
            response = self.session.get(
                self.base_url,
                params=test_params,
                timeout=3  # 缩短超时时间，避免阻塞
            )
            if response.status_code == 200:
                # 成功，重置失败计数
                self._consecutive_failures = 0
                self._api_healthy = True
            else:
                # 非200状态码，增加失败计数
                self._consecutive_failures += 1
                # 只有连续失败多次才认为不可用
                if self._consecutive_failures >= self._max_consecutive_failures:
                    self._api_healthy = False
        except Exception:
            # 异常，增加失败计数
            self._consecutive_failures += 1
            # 只有连续失败多次才认为不可用
            if self._consecutive_failures >= self._max_consecutive_failures:
                self._api_healthy = False
            # 否则保持当前状态
        
        self._last_health_check = now
        return self._api_healthy
    
    def _make_request_with_retry(self, params: Dict[str, Any], retry_count: int = 3,
                                 timeout: int = 15, operation_name: str = "请求",
                                 use_cache: bool = True, use_dedup: bool = True) -> Dict[str, Any]:
        """
        统一的带重试机制的请求函数（改进版）
        
        Args:
            params: 请求参数
            retry_count: 重试次数
            timeout: 超时时间（秒）
            operation_name: 操作名称（用于日志）
            use_cache: 是否使用缓存
            use_dedup: 是否使用请求去重
            
        Returns:
            响应数据
        """
        self.stats['total_requests'] += 1
        
        # 检查缓存
        if use_cache and self.cache:
            cached_result = self.cache.get(params)
            if cached_result is not None:
                self.stats['cache_hits'] += 1
                return cached_result
            self.stats['cache_misses'] += 1
        
        # 请求去重
        if use_dedup and self.deduplicator:
            def execute_request():
                return self._execute_request_with_retry(params, retry_count, timeout, operation_name)
            
            result = self.deduplicator.wait_or_execute(params, execute_request)
            if result is not None:
                # 缓存结果（列表或成功字典都可以缓存）
                if use_cache and self.cache:
                    # 列表表示成功响应，字典需要检查code
                    if isinstance(result, list) or (isinstance(result, dict) and result.get('code') == 200):
                        self.cache.set(params, result)
                return result
        
        # 执行请求
        result = self._execute_request_with_retry(params, retry_count, timeout, operation_name)
        
        # 缓存成功的结果（列表或成功字典都可以缓存）
        if use_cache and self.cache:
            # 列表表示成功响应，字典需要检查code
            if isinstance(result, list) or (isinstance(result, dict) and result.get('code') == 200):
                self.cache.set(params, result)
        
        return result
    
    def _execute_request_with_retry(self, params: Dict[str, Any], retry_count: int,
                                    timeout: int, operation_name: str) -> Dict[str, Any]:
        """执行请求（带重试）"""
        # 限流
        if self.rate_limiter:
            self.rate_limiter.acquire()
        
        with self.semaphore:
            api_healthy = self._check_api_health()
            if not api_healthy:
                pass
            
            for attempt in range(retry_count):
                try:
                    current_timeout = timeout + attempt * 3
                    response = self.session.get(
                        self.base_url,
                        params=params,
                        timeout=current_timeout
                    )

                    if response.status_code == 200:
                        try:
                            data = response.json()
                            return data
                        except json.JSONDecodeError:
                            return {"code": -1, "msg": "响应解析失败"}
                    else:
                        if response.status_code >= 500 and attempt < retry_count - 1:
                            wait_time = self._calculate_backoff(attempt)
                            time.sleep(wait_time)
                            self.stats['retry_count'] += 1
                            continue
                        return {"code": response.status_code, "msg": "请求失败"}

                except requests.exceptions.ConnectionError as e:
                    if attempt < retry_count - 1:
                        wait_time = self._calculate_backoff(attempt)
                        time.sleep(wait_time)
                        self.stats['retry_count'] += 1
                        continue
                    self.stats['failed_requests'] += 1
                    return {"code": -1, "msg": f"网络连接失败: {str(e)}"}

                except requests.exceptions.Timeout as e:
                    if attempt < retry_count - 1:
                        wait_time = self._calculate_backoff(attempt)
                        time.sleep(wait_time)
                        self.stats['retry_count'] += 1
                        continue
                    self.stats['failed_requests'] += 1
                    return {"code": -1, "msg": "请求超时"}

                except Exception as e:
                    if attempt < retry_count - 1:
                        wait_time = self._calculate_backoff(attempt)
                        time.sleep(wait_time)
                        self.stats['retry_count'] += 1
                        continue
                    self.stats['failed_requests'] += 1
                    return {"code": -1, "msg": f"{operation_name}失败: {str(e)}"}

            self.stats['failed_requests'] += 1
            return {"code": -1, "msg": f"经过 {retry_count} 次重试后仍无法完成{operation_name}"}

    def _calculate_backoff(self, attempt: int) -> float:
        """
        计算指数退避等待时间
        
        Args:
            attempt: 当前尝试次数（从0开始）
            
        Returns:
            等待时间（秒）
        """
        # 指数退避：2^attempt 秒，最大30秒
        wait_time = min(2 ** attempt, 30)
        # 添加随机抖动，避免惊群效应
        import random
        jitter = random.uniform(0, 0.3 * wait_time)
        return wait_time + jitter
    
    def search(self, keyword: str, source: str = "网易云音乐", count: int = 20,
               page: int = 1, retry_count: int = 3, use_cache: bool = True) -> Dict[str, Any]:
        """
        搜索音乐（支持缓存）
        
        Args:
            keyword: 搜索关键词
            source: 音乐源
            count: 返回数量
            page: 页码
            retry_count: 重试次数
            use_cache: 是否使用缓存
            
        Returns:
            搜索结果
        """
        # 将中文音源名称转换为英文代码
        source_mapping = {v: k for k, v in MUSIC_SOURCES.items()}
        source_code = source_mapping.get(source, "netease")

        params = {
            "types": "search",
            "source": source_code,
            "name": keyword,
            "count": count,
            "pages": page
        }

        result = self._make_request_with_retry(
            params, retry_count, 15, "搜索音乐",
            use_cache=use_cache, use_dedup=True
        )

        # 处理搜索结果的特殊格式
        if isinstance(result, list):
            return {"code": 200, "data": result}
        return result

    def get_song_url(self, track_id: str, source: str = "网易云音乐", quality: str = "Hi-Res",
                     retry_count: int = 3, use_cache: bool = False) -> Dict[str, Any]:
        """
        获取歌曲播放链接（通常不使用缓存，因为URL可能变化）
        
        Args:
            track_id: 歌曲ID
            source: 音乐源
            quality: 音质
            retry_count: 重试次数
            use_cache: 是否使用缓存（默认False，因为URL可能变化）
            
        Returns:
            播放链接信息
        """
        # 将中文音源名称转换为英文代码
        source_mapping = {v: k for k, v in MUSIC_SOURCES.items()}
        # 将中文音质名称转换为数字代码
        quality_mapping = {v: k for k, v in QUALITY_OPTIONS.items()}

        # 转换参数
        source_code = source_mapping.get(source, "netease")
        quality_code = quality_mapping.get(quality, "999")

        params = {
            "types": "url",
            "source": source_code,
            "id": track_id,
            "br": quality_code
        }

        result = self._make_request_with_retry(
            params, retry_count, 10, "获取播放链接",
            use_cache=use_cache, use_dedup=True
        )

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

            result['format'] = file_format

            # 检查文件是否可访问（使用HEAD请求，更快）
            try:
                head_response = self.session.head(url, timeout=5)
                if head_response.status_code == 200:
                    pass  # 文件可访问
                else:
                    pass  # 文件访问异常，但不影响返回结果
            except Exception:
                pass  # 检查失败不影响返回结果

        return result

    def get_album_pic(self, pic_id: str, source: str = "netease", size: int = 300,
                      retry_count: int = 3, use_cache: bool = True) -> Dict[str, Any]:
        """
        获取专辑图片（支持缓存）
        
        Args:
            pic_id: 图片ID
            source: 音乐源
            size: 图片大小
            retry_count: 重试次数
            use_cache: 是否使用缓存
            
        Returns:
            图片信息
        """
        params = {
            "types": "pic",
            "source": source,
            "id": pic_id,
            "size": size
        }

        return self._make_request_with_retry(
            params, retry_count, 10, "获取专辑图片",
            use_cache=use_cache, use_dedup=True
        )

    def get_lyrics(self, lyric_id: str, source: str = "netease", retry_count: int = 3,
                   use_cache: bool = True) -> Dict[str, Any]:
        """
        获取歌词（支持缓存）
        
        Args:
            lyric_id: 歌词ID
            source: 音乐源
            retry_count: 重试次数
            use_cache: 是否使用缓存
            
        Returns:
            歌词信息
        """
        params = {
            "types": "lyric",
            "source": source,
            "id": lyric_id
        }

        return self._make_request_with_retry(
            params, retry_count, 10, "获取歌词",
            use_cache=use_cache, use_dedup=True
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取API统计信息"""
        cache_hit_rate = 0.0
        if self.stats['total_requests'] > 0:
            cache_hit_rate = self.stats['cache_hits'] / (
                self.stats['cache_hits'] + self.stats['cache_misses']
            ) if (self.stats['cache_hits'] + self.stats['cache_misses']) > 0 else 0.0
        
        return {
            **self.stats,
            'cache_hit_rate': f"{cache_hit_rate * 100:.2f}%",
            'api_healthy': self._api_healthy,
            'cache_enabled': self.cache is not None,
            'deduplication_enabled': self.deduplicator is not None,
            'rate_limit_enabled': self.rate_limiter is not None
        }
    
    def clear_cache(self) -> None:
        """清空API响应缓存"""
        if self.cache:
            self.cache.clear()
    
    def __del__(self):
        """清理资源"""
        if hasattr(self, 'session'):
            self.session.close()
