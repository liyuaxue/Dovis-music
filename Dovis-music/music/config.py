# API配置
API_BASE_URL = "https://music-api.gdstudio.xyz/api.php"

# 音乐源配置
MUSIC_SOURCES = {
    "netease": "网易云音乐",
    "kuwo": "酷我音乐",
    "joox": "JOOX音乐",
    "tencent": "QQ音乐",
    "kugou": "酷狗音乐",
    "migu": "咪咕音乐"
}

# 音质选项
QUALITY_OPTIONS = {
    "128": "标准",
    "192": "高清",
    "320": "超清",
    "740": "无损",
    "999": "Hi-Res"
}

# 播放模式
PLAY_MODES = {
    "order": "顺序播放",
    "random": "随机播放",
    "single": "单曲循环"
}

# 默认配置
DEFAULT_CONFIG = {
    "source": "netease",
    "quality": "999",
    "play_mode": "order",
    "search_count": 20,
    "spectrum_mode": "圆形"
}

# 主题配置
THEMES = {
    "dark": {
        "bg": "#1a1a1a",
        "secondary_bg": "#2C3E50",
        "tertiary_bg": "#34495E",
        "text": "white",
        "secondary_text": "#bdc3c7",
        "accent": "#3498DB",
        "button_bg": "#34495E",
        "button_hover": "#5D6D7E",
        "progress_bg": "#34495E",
        "progress_fg": "#3498DB"
    },
    "light": {
        "bg": "#f8f9fa",
        "secondary_bg": "#e9ecef",
        "tertiary_bg": "#dee2e6",
        "text": "#2c3e50",
        "secondary_text": "#6c757d",
        "accent": "#e74c3c",
        "button_bg": "#dee2e6",
        "button_hover": "#adb5bd",
        "progress_bg": "#dee2e6",
        "progress_fg": "#e74c3c"
    },
    "purple": {
        "bg": "#2d1b69",
        "secondary_bg": "#3d2a7a",
        "tertiary_bg": "#4d3a8a",
        "text": "#e0d6ff",
        "secondary_text": "#a29bfe",
        "accent": "#9b59b6",
        "button_bg": "#4d3a8a",
        "button_hover": "#6d5aaa",
        "progress_bg": "#4d3a8a",
        "progress_fg": "#9b59b6"
    },
    "sunset": {
        "bg": "#ff6b6b",
        "secondary_bg": "#ff9ff3",
        "tertiary_bg": "#feca57",
        "text": "#2c2c54",
        "secondary_text": "#706fd3",
        "accent": "#2c2c54",
        "button_bg": "#feca57",
        "button_hover": "#ff9f43",
        "progress_bg": "#feca57",
        "progress_fg": "#ff6b6b"
    },
    "forest": {
        "bg": "#1b4332",
        "secondary_bg": "#2d6a4f",
        "tertiary_bg": "#40916c",
        "text": "#d8f3dc",
        "secondary_text": "#b7e4c7",
        "accent": "#52b788",
        "button_bg": "#40916c",
        "button_hover": "#52b788",
        "progress_bg": "#40916c",
        "progress_fg": "#52b788"
    },
    "ocean": {
        "bg": "#023e8a",
        "secondary_bg": "#0077b6",
        "tertiary_bg": "#0096c7",
        "text": "#caf0f8",
        "secondary_text": "#90e0ef",
        "accent": "#00b4d8",
        "button_bg": "#0096c7",
        "button_hover": "#00b4d8",
        "progress_bg": "#0096c7",
        "progress_fg": "#00b4d8"
    },
    "midnight": {
        "bg": "#0d1b2a",
        "secondary_bg": "#1b263b",
        "tertiary_bg": "#415a77",
        "text": "#e0e1dd",
        "secondary_text": "#778da9",
        "accent": "#415a77",
        "button_bg": "#415a77",
        "button_hover": "#778da9",
        "progress_bg": "#415a77",
        "progress_fg": "#778da9"
    },
    "coffee": {
        "bg": "#3c2f2f",
        "secondary_bg": "#4a3f3f",
        "tertiary_bg": "#5d4e4e",
        "text": "#f5f5f5",
        "secondary_text": "#d9b99b",
        "accent": "#d9b99b",
        "button_bg": "#5d4e4e",
        "button_hover": "#8c6d4e",
        "progress_bg": "#5d4e4e",
        "progress_fg": "#d9b99b"
    },
    "rose": {
        "bg": "#f8d7da",
        "secondary_bg": "#f1b0b7",
        "tertiary_bg": "#ea8c95",
        "text": "#721c24",
        "secondary_text": "#856084",
        "accent": "#c44569",
        "button_bg": "#ea8c95",
        "button_hover": "#f1b0b7",
        "progress_bg": "#ea8c95",
        "progress_fg": "#c44569"
    },
    "cyber": {
        "bg": "#0f0f23",
        "secondary_bg": "#1a1a2e",
        "tertiary_bg": "#16213e",
        "text": "#00ff9d",
        "secondary_text": "#00b8ff",
        "accent": "#ff2e63",
        "button_bg": "#16213e",
        "button_hover": "#0f3460",
        "progress_bg": "#16213e",
        "progress_fg": "#ff2e63"
    }
}

# 主题名称映射（中文显示）
THEME_NAMES = {
    "dark": "深色",
    "light": "浅色",
    "purple": "紫色",
    "sunset": "日落",
    "forest": "森林",
    "ocean": "海洋",
    "midnight": "午夜",
    "coffee": "咖啡",
    "rose": "玫瑰",
    "cyber": "赛博"
}

# 默认主题
DEFAULT_THEME = "light"