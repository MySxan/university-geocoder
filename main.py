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
RETRY_DELAY = 1  # 重试前的等待时间（秒）

# 输入文件配置
EXCEL_FILE = "univ_moe.xls"
SUPP_JSON_FILE = "univ_supp.json"

# 输出文件配置
OUTPUT_JSON_FILE = "universities.json"
REJECTED_CSV_FILE = "rejected_pois.csv"
NO_DETAILS_CSV_FILE = "universities_without_details.csv"
NO_CAMPUSES_CSV_FILE = "universities_with_no_campuses.csv"
LOG_FILE_PREFIX = "run_log"


class QuotaExceededError(Exception):
    """当API每日调用量达到上限时抛出的自定义异常。"""

    pass


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
                message = response_data.get("message")
                print(f"  - API返回错误: status={status}, message={message}")
                if status == 121:
                    raise QuotaExceededError(message)
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


def post_process_name(name: str) -> str | None:
    """对校区名称进行后处理"""
    if not name:
        return None

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

    # 4. 将“XX主校区YY”替换为“XX校区YY”
    processed_name = re.sub(r"(.+)主校区", r"\1校区", processed_name).strip()

    return processed_name if processed_name else None


def is_valid_campus_name(name: str | None) -> bool:
    """检查名称是否符合校区名定义"""
    if not name:
        return True
    # 非附属
    if "附属" in name or "医院" in name:
        return False
    # 以特定词结尾
    valid_endings = ["校区", "园区", "院区", "校园", "学校", "分校", "院"]
    for ending in valid_endings:
        if name.endswith(ending):
            return True
    return False


def is_location_substring(text: str | None, poi: dict) -> bool:
    """检查文本是否是省、市、区之一的子字符串。"""
    if not text:
        return False
    poi_province = poi.get("province", "")
    poi_city = poi.get("city", "")
    poi_district = poi.get("district", "")

    return (
        (poi_province and text in poi_province)
        or (poi_city and text in poi_city)
        or (poi_district and text in poi_district)
    )


def extract_bracketed_content(text: str) -> str:
    """
    提取文本中括号内的内容，并返回去除括号后的内容。
    """
    text = text.strip()
    if not text:
        return ""
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    return text.strip()


def parse_campus_name(poi: dict, school_name: str):
    """
    根据新的复杂规则解析POI标题以提取校区名称。
    """
    poi_title = poi.get("title", "")

    # 1. 灵活的前缀匹配
    pattern_str = (
        re.escape(school_name).replace(r"（", r"[\(（]").replace(r"）", r"[\)）]")
    )
    pattern = re.compile(f"^{pattern_str}")
    match = pattern.match(poi_title)

    if not match:
        return "REJECT"

    if match.end() == len(poi_title):
        return None

    remaining_title = poi_title[match.end() :].strip()

    if (not remaining_title) or (remaining_title in ["主校区", "校本部"]):
        return None

    # 2. 将剩余部分分割为带括号和不带括号的片段
    parts = [p for p in re.split(r"(\([^)]+\))", remaining_title) if p]

    # 3. 从后向前遍历片段，寻找第一个有效的“锚点”
    for i in range(len(parts) - 1, -1, -1):
        current_part = parts[i]
        # 提取片段内容（无论是否在括号内）
        content = extract_bracketed_content(current_part)

        post_processed_content = post_process_name(content)

        # 检查此片段是否为有效锚点
        is_campus_name = is_valid_campus_name(post_processed_content)
        is_loc_substr = is_location_substring(post_processed_content, poi)
        is_anchor = is_campus_name or is_loc_substr

        if is_anchor:
            # 4. 如果找到锚点，拼接从开头到此锚点的所有部分
            final_name_parts = []
            for j in range(i + 1):
                final_name_parts.append(extract_bracketed_content(parts[j]))

            final_name = "".join(final_name_parts)

            # 如果最终拼接的名称本身不符合规则（通常是因为靠行政区划匹配上的）
            # 则为其补上“校区”后缀
            if (
                not is_valid_campus_name(post_process_name(final_name))
                and is_loc_substr
            ):
                final_name += "校区"

            return post_process_name(final_name)

    return "REJECT"


def process_university_data(excel_path: str):
    """
    主函数，执行从读取文件、合并数据、API请求到输出结果的完整流程。
    """
    if not MY_KEY or not MY_SK:
        print("错误：无法从 .env 文件中加载 TENCENT_MAP_KEY 或 TENCENT_MAP_SK。")
        print("请确保项目根目录下存在 .env 文件，并且其中包含正确的Key和SK。")
        return

    # 1. 读取Excel文件
    try:
        print(f"正在读取Excel文件: {excel_path}")
        df_temp = pd.read_excel(excel_path, header=None)
        header_row_index = -1
        for i, row in df_temp.iterrows():
            if not isinstance(i, int):
                continue
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

    # 清理学校名称
    def clean_name(name):
        if isinstance(name, str):
            if name.startswith("民办"):
                name = name[2:]
            # 去掉“市”，但不去掉“城市”或“都市”
            name = re.sub(r"(?<![城都])市", "", name)
        return name

    df["name"] = df["name"].apply(clean_name)

    # 初始化结果和报告列表
    universities_list = df.to_dict("records")
    rejected_pois = []
    final_universities_data_map = {}  # 使用map以方便查找
    schools_without_details = []
    processed_pois_map = {}  # 存储更详细的匹配信息
    quota_exceeded = False  # 用于标记配额是否耗尽

    print(f"成功读取并清理了 {len(universities_list)} 所学校。开始处理...")

    try:  # 包裹主循环以便捕获配额异常
        # 4. 遍历每所学校
        for index, school_from_xls in enumerate(universities_list):
            school_name = school_from_xls.get("name")
            if not school_name:
                print(
                    f"\n[{index + 1}/{len(universities_list)}] 学校名称为空，跳过此条记录。"
                )
                continue
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
                "natureOfRunning",
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
            final_universities_data_map[school_name] = school_output  # 存入map

            page_index = 1
            total_pages = 1

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
                        poi_title = poi.get("title", "")
                        if not poi_id or not poi_title:
                            continue

                        campus_name_processed = parse_campus_name(poi, school_name)

                        if campus_name_processed == "REJECT":
                            rejected_pois.append(poi)
                            print(f"    [❌] {poi.get('title')}")
                            continue

                        # --- 最长前缀占比匹配核心逻辑 ---
                        current_prefix_ratio = len(school_name) / len(poi_title)
                        previous_match = processed_pois_map.get(poi_id)

                        if (
                            not previous_match
                            or current_prefix_ratio > previous_match["prefix_ratio"]
                        ):
                            current_school_data = final_universities_data_map[
                                school_name
                            ]
                            existing_campus_names = {
                                c["name"] for c in current_school_data["campuses"]
                            }

                            if previous_match:
                                prev_school_name = previous_match["school_name"]
                                prev_school_output = final_universities_data_map.get(
                                    prev_school_name
                                )
                                if prev_school_output:
                                    prev_school_output["campuses"] = [
                                        c
                                        for c in prev_school_output["campuses"]
                                        if c.get("id") != poi_id
                                    ]
                                    print(
                                        f"    [🔄] {poi_title}: '{prev_school_name}' (占比 {previous_match['prefix_ratio']:.2f}) → '{school_name}' (占比 {current_prefix_ratio:.2f})"
                                    )

                            if campus_name_processed in existing_campus_names:
                                print(
                                    f"    [⏭️] {poi_title} → {campus_name_processed} (校内同名)"
                                )
                                continue

                            location = poi.get("location", {})
                            campus_data = {
                                "id": poi_id,
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
                            current_school_data["campuses"].append(campus_data)

                            processed_pois_map[poi_id] = {
                                "school_name": school_name,
                                "prefix_ratio": current_prefix_ratio,
                            }
                            print(
                                f"    [✅] {poi_title} → {campus_name_processed} (ID: {poi_id})"
                            )

                        else:
                            print(
                                f"    [🌐] {poi_title} (ID: {poi_id}, 已分配给更优匹配 '{previous_match['school_name']}' 占比 {previous_match['prefix_ratio']:.2f})"
                            )
                else:
                    print(f"  - API请求失败或无数据，跳过此学校的后续请求。")
                    break
                page_index += 1

    except QuotaExceededError:
        print("\n因API每日调用量已达上限，处理中断。")
        quota_exceeded = True

    # 5. 写入所有输出文件
    print("\n--- 处理完成，正在生成报告文件 ---")

    final_universities_data = list(
        final_universities_data_map.values()
    )  # 从map转回list
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

    # 写入没有校区的大学CSV文件
    if universities_without_campuses:
        # 确保campuses键存在，即使为空
        for school in universities_without_campuses:
            if "campuses" not in school:
                school["campuses"] = []
        header = universities_without_campuses[0].keys()
        with open(NO_CAMPUSES_CSV_FILE, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            writer.writerows(universities_without_campuses)
        print(
            f"✅ 没有校区的大学列表已写入: {NO_CAMPUSES_CSV_FILE} ({len(universities_without_campuses)} 条)"
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

    # 写入未找到附加信息的学校
    if schools_without_details:
        # 确保ID为字符串格式
        for school in schools_without_details:
            school["id"] = str(int(school["id"]))
        with open(NO_DETAILS_CSV_FILE, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=schools_without_details[0].keys())
            writer.writeheader()
            writer.writerows(schools_without_details)
        print(
            f"✅ 未找到附加信息的学校列表已写入: {NO_DETAILS_CSV_FILE} ({len(schools_without_details)} 条)"
        )

    # 如果是因为配额耗尽而退出，则使用错误码
    if quota_exceeded:
        print("\n脚本因API配额耗尽而终止，已保存当前进度。退出状态码: 1")
        sys.exit(1)


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
