import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# ===== 文件配置 =====
RANKINGS_CSV = "merged_rankings.csv"
CACHE_FILE = "google_places_cache.json"
OUTPUT_JSON_FILE = "universities_global.json"
CHECKPOINT_FILE = "processing_checkpoint.json"  # 断点续传文件
LOG_FILE_PREFIX = "dedupe_log"

# ===== API 配置 =====
GOOGLE_MAPS_KEY = os.getenv("GOOGLE_MAPS_KEY")

# Google Places API (New) 参数
PLACES_API_NEW = "https://places.googleapis.com/v1"
REQUEST_DELAY = 0.05  # API请求间隔（秒）
MAX_RETRIES = 3

# ===== 输出文件配置 =====
REJECTED_POIS_CSV = "rejected_pois_global.csv"
NO_WEBSITE_CSV = "universities_with_no_website.csv"
