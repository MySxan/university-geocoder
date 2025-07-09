import csv
import hashlib
import json
import math
import os
import re
import sys
import time
from datetime import datetime
from urllib.parse import urlencode

import pandas as pd
import requests
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

# --- 全局配置 ---
# 从环境变量中获取Key和SK
# 请在项目根目录创建 .env 文件，并填入以下内容:
# TENCENT_MAP_KEY="你的Key"
# TENCENT_MAP_SK="你的Secret Key"
MY_KEY = os.getenv("TENCENT_MAP_KEY")
MY_SK = os.getenv("TENCENT_MAP_SK")


# API相关配置
API_HOST = "https://apis.map.qq.com"
API_PATH = "/ws/place/v1/suggestion"
PAGE_SIZE = 20
MAX_RETRIES = 10  # QPS超限时的最大重试次数
RETRY_DELAY = 2  # 重试前的等待时间（秒）

# 输入/输出文件配置
EXCEL_FILE = "univ_moe.xls"
SUPP_JSON_FILE = "univ_supp.json"
OUTPUT_JSON_FILE = "universities.json"
REJECTED_CSV_FILE = "rejected_pois.csv"
NO_POI_CSV_FILE = "universities_with_no_poi.csv"
NO_DETAILS_CSV_FILE = "universities_without_details.csv"
NO_CAMPUSES_JSON_FILE = "universities_with_no_campuses.json"
LOG_FILE_PREFIX = "run_log"


# --- 日志记录类 ---
class Logger(object):
    """
    将控制台输出同时写入文件。
    """

    def __init__(self, filename="default.log"):
        self.terminal = sys.stdout
        # 使用 'w' 模式，每次运行创建新的日志文件
        self.log = open(filename, "w", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

    def flush(self):
        # 这个 flush 方法是为 Python 3 兼容性所必需的。
        pass


def request_tencent_api(path: str, params: dict, sk: str):
    """
    一个用于请求腾讯地图Web API的代理函数，可自动处理签名和QPS超限重试。
    """
    for attempt in range(MAX_RETRIES):
        # 签名计算
        sorted_params = sorted(params.items())
        qs_for_sig = "&".join([f"{k}={v}" for k, v in sorted_params])
        string_to_sign = f"{path}?{qs_for_sig}{sk}"
        sig = hashlib.md5(string_to_sign.encode("utf-8")).hexdigest()

        # 构造最终请求URL
        encoded_params = urlencode(params)
        final_url = f"{API_HOST}{path}?{encoded_params}&sig={sig}"

        try:
            response = requests.get(final_url, timeout=15)
            response.raise_for_status()
            response_data = response.json()

            # 检查API返回的状态码
            status = response_data.get("status")
            if status == 0:
                return response_data  # 请求成功
            elif status == 120:
                print(
                    f"  - 触发QPS限制 (status 120)，将在 {RETRY_DELAY} 秒后重试... (第 {attempt + 1}/{MAX_RETRIES} 次)"
                )
                time.sleep(RETRY_DELAY)
                continue  # 进入下一次重试
            else:
                print(
                    f"  - API返回错误: status={status}, message={response_data.get('message')}"
                )
                return None

        except requests.exceptions.Timeout:
            print(f"  - 请求超时: {final_url}")
        except requests.exceptions.HTTPError as e:
            print(f"  - HTTP错误: {e.response.status_code} for url: {final_url}")
        except requests.exceptions.RequestException as e:
            print(f"  - 请求发生严重错误: {e}")

        # 如果不是因为QPS限制导致的失败，则稍作等待后重试
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY)

    print(f"  - 重试 {MAX_RETRIES} 次后仍然失败，放弃请求。")
    return None


def post_process_name(name: str) -> str:
    """对校区名称进行后处理"""
    if not name:
        return name

    # 1. trim
    processed_name = name.strip()
    # 2. 去除“-”和“&”
    processed_name = processed_name.replace("-", "").replace("&", "")
    # 3. 去除结尾的特定方位和期数字样
    suffixes_to_remove = [
        "西区",
        "东区",
        "北区",
        "南区",
        "中区",
        "一期",
        "二期",
        "三期",
        "四期",
        "五期",
        "六期",
        "七期",
        "八期",
        "九期",
        "十期",
    ]
    for suffix in suffixes_to_remove:
        if processed_name.endswith(suffix):
            processed_name = processed_name[: -len(suffix)]
            break  # 只移除一个
    # 4. 将“XX主校区YY”替换为“XX校区YY”
    processed_name = re.sub(r"(.+)主校区", r"\1校区", processed_name)

    return processed_name.strip()


def is_valid_campus_name(name: str) -> bool:
    """检查名称是否符合校区名定义"""
    if not name:
        return False
    # 非附属
    if "附属" in name or "医院" in name:
        return False
    # 以特定词结尾
    valid_endings = ["校区", "园区", "院区", "校园", "学校", "分校", "院"]
    for ending in valid_endings:
        if name.endswith(ending):
            return True
    return False


def check_and_get_name(part: str, poi_address: str):
    """
    辅助函数：检查一个部分是否是有效校区名，或能否通过地址辅助成为校区名
    """
    processed_part = post_process_name(part)
    if is_valid_campus_name(processed_part):
        return processed_part

    # 如果名称是地址的子串，则加上“校区”
    if processed_part and poi_address and processed_part in poi_address:
        return f"{processed_part}校区"

    return None


def parse_campus_name(poi: dict, school_name: str):
    """
    根据规则解析POI标题以提取校区名称。
    返回后处理过的校区名，如果无匹配则返回None。
    """
    poi_title = poi.get("title", "")
    poi_address = poi.get("address", "")

    # 通过灵活的正则表达式匹配学校名，忽略括号差异
    pattern_str = (
        re.escape(school_name).replace(r"（", r"[\(（]").replace(r"）", r"[\)）]")
    )
    pattern = re.compile(f"^{pattern_str}")
    match = pattern.match(poi_title)

    # 如果完全匹配（包括括号差异），也视为null校区
    if match and match.end() == len(poi_title):
        return None

    if not match:
        return "REJECT"

    remaining_title = poi_title[match.end() :].strip()
    if not remaining_title:
        return None

    if remaining_title in ["主校区", "校本部"]:
        return None

    # 括号解析 B_0(B_1)...(B_n)
    parts_in_parentheses = re.findall(r"\(([^)]+)\)", remaining_title)
    # 从后往前检查括号内容 (B_n -> B_1)
    for part in reversed(parts_in_parentheses):
        campus_name = check_and_get_name(part, poi_address)
        if campus_name is not None:
            return campus_name

    # 检查第一个括号前的内容
    b0_part = remaining_title.split("(", 1)[0].strip()
    if b0_part:
        campus_name = check_and_get_name(b0_part, poi_address)
        if campus_name is not None:
            return campus_name

    # 如果没有括号，检查整个剩余部分
    if not parts_in_parentheses:
        campus_name = check_and_get_name(remaining_title, poi_address)
        if campus_name is not None:
            return campus_name

    return "REJECT"


def process_university_data(excel_path: str):
    """
    主函数，执行从读取文件、合并数据、API请求到输出结果的完整流程。
    """
    if not MY_KEY or not MY_SK:
        print("错误：无法从 .env 文件中加载 TENCENT_MAP_KEY 或 TENCENT_MAP_SK。")
        print("请确保项目根目录下存在 .env 文件，并且其中包含正确的Key和SK。")
        return

    # 1. 读取Excel文件 (重写逻辑以处理复杂表头)
    try:
        print(f"正在读取Excel文件: {excel_path}")
        df_temp = pd.read_excel(excel_path, header=None)
        header_row_index = -1
        for i, row in df_temp.iterrows():
            if "学校名称" in str(row.values):
                header_row_index = i
                break
        if header_row_index == -1:
            print("错误：在Excel文件中找不到包含“学校名称”的表头行。")
            return
        print(f"检测到表头在第 {header_row_index + 1} 行。")
        df = pd.read_excel(excel_path, header=header_row_index)
    except Exception as e:
        print(f"读取Excel文件时出错: {e}")
        return

    # 2. 加载用于合并的附加JSON数据
    supp_data_map = {}
    try:
        print(f"正在加载附加数据文件: {SUPP_JSON_FILE}")
        with open(SUPP_JSON_FILE, "r", encoding="utf-8") as f:
            supp_list = json.load(f)
            supp_data_map = {item["name"]: item for item in supp_list}
        print(f"成功加载 {len(supp_data_map)} 条附加数据用于合并。")
    except Exception as e:
        print(f"加载 '{SUPP_JSON_FILE}' 时出错: {e}，将跳过数据合并步骤。")

    # 3. 清理和重命名列
    column_mapping = {
        "学校标识码": "id",
        "学校名称": "name",
        "主管部门": "affiliation",
        "办学层次": "type",
    }
    # 只保留需要的列
    df = df[list(column_mapping.keys())].rename(columns=column_mapping)
    df.dropna(subset=["name"], inplace=True)

    # 清理ID列，确保为字符串格式的整数
    df.dropna(subset=["id"], inplace=True)
    df["id"] = df["id"].astype(float).astype(int).astype(str)

    # 清理学校名称，去掉“民办”前缀
    df["name"] = df["name"].apply(
        lambda name: (
            name[2:] if isinstance(name, str) and name.startswith("民办") else name
        )
    )

    # 初始化结果和报告列表
    universities_list = df.to_dict("records")
    rejected_pois = []
    final_universities_data = []
    schools_with_no_poi = []
    schools_without_details = []
    processed_poi_ids = set()

    print(f"成功读取并清理了 {len(universities_list)} 所学校。开始处理...")

    # 4. 遍历每所学校
    for index, school_from_xls in enumerate(universities_list):
        school_name = school_from_xls.get("name")
        print(f"\n[{index + 1}/{len(universities_list)}] 正在查询: {school_name}")

        school_output = {
            "id": school_from_xls.get("id"),
            "name": school_name,
            "affiliation": school_from_xls.get("affiliation"),
            "type": school_from_xls.get("type"),
        }

        # 合并附加数据
        fields_to_merge = [
            "majorCategory",
            "type",
            "is985",
            "is211",
            "isDoubleFirstClass",
        ]
        if school_name in supp_data_map:
            details = supp_data_map[school_name]
            for field in fields_to_merge:
                if field in details:
                    school_output[field] = details[field]
        else:
            print(f"  - 在 {SUPP_JSON_FILE} 中未找到匹配项。")
            for field in fields_to_merge:
                school_output[field] = None
            schools_without_details.append(school_from_xls)

        school_output["campuses"] = []
        processed_campus_names = set()  # 用于校区去重
        page_index = 1
        total_pages = 1
        found_poi = False

        # 处理分页API请求
        while page_index <= total_pages:
            print(f"  - 正在请求第 {page_index}/{total_pages} 页...")
            params = {
                "keyword": school_name,
                "key": MY_KEY,
                "filter": "category=大学",
                "get_ad": 1,
                "page_size": PAGE_SIZE,
                "page_index": page_index,
                "added_fields": "category_code",
            }
            response_data = request_tencent_api(API_PATH, params, MY_SK)
            time.sleep(0.2)

            if response_data:
                if page_index == 1:
                    count = response_data.get("count", 0)
                    total_pages = math.ceil(count / PAGE_SIZE)

                for poi in response_data.get("data", []):
                    poi_id = poi.get("id")

                    if poi_id and poi_id in processed_poi_ids:
                        print(
                            f"    [🌐] {poi.get('title')} (ID: {poi_id} 已在全局保存)"
                        )
                        continue

                    campus_name_processed = parse_campus_name(poi, school_name)

                    if campus_name_processed != "REJECT":
                        # 检查校区名是否已存在
                        if campus_name_processed not in processed_campus_names:
                            processed_campus_names.add(campus_name_processed)
                            processed_poi_ids.add(poi_id)  # 添加到全局ID集合
                            location = poi.get("location", {})
                            campus_data = {
                                "id": poi.get("id"),
                                "name": campus_name_processed,
                                "address": poi.get("address"),
                                "province": poi.get("province"),
                                "city": poi.get("city"),
                                "district": poi.get("district"),
                                "location": {
                                    "type": "Point",
                                    "coordinates": [
                                        location.get("lng"),
                                        location.get("lat"),
                                    ],
                                },
                            }
                            school_output["campuses"].append(campus_data)
                            found_poi = True
                            print(
                                f"    [✅] {poi.get('title')} (ID: {poi.get('id')}) -> {campus_name_processed}"
                            )
                        else:
                            print(
                                f"    [⏭️] {poi.get('title')} -> {campus_name_processed} (本校内同名)"
                            )
                    else:
                        rejected_pois.append(poi)
                        print(f"    [❌] {poi.get('title')}")
            else:
                print(f"  - API请求失败或无数据，跳过此学校的后续请求。")
                break
            page_index += 1

        if not found_poi:
            print("  - 未找到相关POI。")
            schools_with_no_poi.append(school_from_xls)

        final_universities_data.append(school_output)

    # 5. 写入所有输出文件
    print("\n--- 处理完成，正在生成报告文件 ---")

    universities_with_campuses = []
    universities_without_campuses = []
    for school in final_universities_data:
        if school.get("campuses"):
            universities_with_campuses.append(school)
        else:
            universities_without_campuses.append(school)

    # 写入主JSON文件 (有校区)
    with open(OUTPUT_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(universities_with_campuses, f, ensure_ascii=False, indent=4)
    print(
        f"✅ 有校区的大学数据已写入: {OUTPUT_JSON_FILE} ({len(universities_with_campuses)} 条)"
    )

    # 写入没有校区的大学JSON文件
    if universities_without_campuses:
        with open(NO_CAMPUSES_JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(universities_without_campuses, f, ensure_ascii=False, indent=4)
        print(
            f"✅ 没有校区的大学列表已写入: {NO_CAMPUSES_JSON_FILE} ({len(universities_without_campuses)} 条)"
        )

    # 写入被拒绝的POI
    if rejected_pois:
        header = sorted(list(set(key for poi in rejected_pois for key in poi.keys())))
        with open(REJECTED_CSV_FILE, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            writer.writerows(rejected_pois)
        print(
            f"✅ 被拒绝的POI列表已写入: {REJECTED_CSV_FILE} ({len(rejected_pois)} 条)"
        )

    # 写入未找到POI的学校
    if schools_with_no_poi:
        with open(NO_POI_CSV_FILE, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=schools_with_no_poi[0].keys())
            writer.writeheader()
            writer.writerows(schools_with_no_poi)
        print(
            f"✅ API未返回任何POI的学校列表已写入: {NO_POI_CSV_FILE} ({len(schools_with_no_poi)} 条)"
        )

    # 写入未找到附加信息的学校
    if schools_without_details:
        with open(NO_DETAILS_CSV_FILE, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=schools_without_details[0].keys())
            writer.writeheader()
            writer.writerows(schools_without_details)
        print(
            f"✅ 未找到附加信息的学校列表已写入: {NO_DETAILS_CSV_FILE} ({len(schools_without_details)} 条)"
        )


# --- 脚本入口 ---
if __name__ == "__main__":
    # --- 设置日志记录 ---
    log_filename = f"{LOG_FILE_PREFIX}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    sys.stdout = Logger(log_filename)

    print(f"日志将记录到文件: {log_filename}")
    print("-" * 50)

    if not os.path.exists(EXCEL_FILE):
        print("-" * 50)
        print(f"错误: 输入文件 '{EXCEL_FILE}' 不存在。")
        print("请将您的Excel文件与此脚本放在同一目录下，")
        print("并确保脚本中的 'EXCEL_FILE' 变量值正确。")
        print("-" * 50)
    else:
        process_university_data(EXCEL_FILE)
