import os
import sys
from datetime import datetime

from src.config import (
    TENCENT_MAP_KEY,
    TENCENT_MAP_SK,
    EXCEL_FILE,
    SUPP_JSON_FILE,
    OUTPUT_JSON_FILE,
    REJECTED_CSV_FILE,
    NO_DETAILS_CSV_FILE,
    NO_CAMPUSES_CSV_FILE,
    LOG_FILE_PREFIX,
    PAGE_SIZE,
)
from src.api import request_tencent_api, QuotaExceededError, API_PATH
from src.parsers import parse_campus_name
from src.data import load_university_data, load_supplementary_data, merge_supplementary_data
from src.output import write_universities_json, write_csv, prepare_output_data
from src.processors import process_poi_data, fetch_school_campuses
from src.utils import Logger


def process_university_data(excel_path: str):
    """
    主函数，执行从读取文件、合并数据、API请求到输出结果的完整流程。
    """
    # 检查API密钥
    if not TENCENT_MAP_KEY or not TENCENT_MAP_SK:
        print("错误：无法从 .env 文件中加载 TENCENT_MAP_KEY 或 TENCENT_MAP_SK。")
        print("请确保项目根目录下存在 .env 文件，并且其中包含正确的Key和SK。")
        return

    # 1. 读取大学数据
    universities_list = load_university_data(excel_path)
    if not universities_list:
        return

    # 2. 加载附加数据
    supp_data_map = load_supplementary_data(SUPP_JSON_FILE)

    # 3. 初始化结果和报告数据
    rejected_pois = []
    final_universities_data_map = {}
    schools_without_details = []
    processed_pois_map = {}  # 存储更详细的匹配信息
    quota_exceeded = False  # 用于标记配额是否耗尽

    print(f"开始处理...")

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

            # 合并附加数据
            school_output, found_details = merge_supplementary_data(
                school_from_xls, supp_data_map
            )
            
            if not found_details:
                print(f"  - 在 {SUPP_JSON_FILE} 中未找到匹配项。")
                schools_without_details.append(school_from_xls)
            
            final_universities_data_map[school_name] = school_output

            # 获取学校的所有校区POI
            all_pois = fetch_school_campuses(
                school_name,
                request_tencent_api,
                API_PATH,
                TENCENT_MAP_KEY,
                TENCENT_MAP_SK,
                PAGE_SIZE,
            )

            # 处理每个POI
            for poi in all_pois:
                process_poi_data(
                    poi,
                    school_name,
                    parse_campus_name,
                    final_universities_data_map,
                    processed_pois_map,
                    rejected_pois,
                )

    except QuotaExceededError:
        print("\n因API每日调用量已达上限，处理中断。")
        quota_exceeded = True

    # 5. 准备输出数据
    print("\n--- 处理完成，正在生成报告文件 ---")
    
    universities_with_campuses, universities_without_campuses = prepare_output_data(
        final_universities_data_map
    )

    # 6. 写入输出文件
    # 写入有校区的大学
    write_universities_json(universities_with_campuses, OUTPUT_JSON_FILE)

    # 写入没有校区的大学
    if universities_without_campuses:
        for school in universities_without_campuses:
            if "campuses" not in school:
                school["campuses"] = []
        write_csv(
            universities_without_campuses,
            NO_CAMPUSES_CSV_FILE,
            "没有校区的大学列表"
        )

    # 写入被拒绝的POI
    if rejected_pois:
        write_csv(rejected_pois, REJECTED_CSV_FILE, "被拒绝的POI列表")

    # 写入未找到附加信息的学校
    if schools_without_details:
        for school in schools_without_details:
            school["id"] = str(int(school["id"]))
        write_csv(
            schools_without_details,
            NO_DETAILS_CSV_FILE,
            "未找到附加信息的学校列表"
        )

    # 如果是因为配额耗尽而退出，则使用错误码
    if quota_exceeded:
        print("\n脚本因API配额耗尽而终止，已保存当前进度。退出状态码: 1")
        sys.exit(1)


def main():
    """主入口函数"""
    # 设置日志记录
    log_filename = f"{LOG_FILE_PREFIX}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    sys.stdout = Logger(log_filename)

    print(f"日志将记录到文件: {log_filename}")
    print("-" * 50)

    if not os.path.exists(EXCEL_FILE):
        print("-" * 50)
        print(f"错误: 输入文件 '{EXCEL_FILE}' 不存在。")
        print("请将您的Excel文件与此脚本放在同一目录下，")
        print("并确保配置文件中的 'EXCEL_FILE' 变量值正确。")
        print("-" * 50)
    else:
        process_university_data(EXCEL_FILE)


if __name__ == "__main__":
    main()
