import os
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

# --- API配置 ---
TENCENT_MAP_KEY = os.getenv("TENCENT_MAP_KEY")
TENCENT_MAP_SK = os.getenv("TENCENT_MAP_SK")

# --- 文件配置 ---
# 输入文件
EXCEL_FILE = "univ_moe.xls"
SUPP_JSON_FILE = "univ_supp.json"

# 输出文件
OUTPUT_JSON_FILE = "universities.json"
REJECTED_CSV_FILE = "rejected_pois.csv"
NO_DETAILS_CSV_FILE = "universities_without_details.csv"
NO_CAMPUSES_CSV_FILE = "universities_with_no_campuses.csv"
LOG_FILE_PREFIX = "run_log"

# --- API参数配置 ---
PAGE_SIZE = 20
