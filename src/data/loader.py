import json
import os
import re

import pandas as pd


def load_university_data(file_path: str) -> list[dict]:
    """
    从Excel或CSV文件加载大学数据
    """
    print(f"正在读取文件: {file_path}")
    file_ext = os.path.splitext(file_path)[1].lower()
    
    try:
        # 读取文件以查找表头
        if file_ext in [".xls", ".xlsx"]:
            df_temp = pd.read_excel(file_path, header=None)
        elif file_ext == ".csv":
            df_temp = pd.read_csv(file_path, header=None, encoding="utf-8-sig")
        else:
            print(f"错误：不支持的文件格式 {file_ext}，仅支持 .xls / .xlsx / .csv")
            return []
        
        # 查找包含"学校名称"的表头行
        header_row_index = -1
        for i, row in df_temp.iterrows():
            if not isinstance(i, int):
                continue
            if "学校名称" in str(row.values):
                header_row_index = i
                break

        if header_row_index == -1:
            print('错误：在文件中找不到包含"学校名称"的表头行。')
            return []
        
        print(f"检测到表头在第 {header_row_index + 1} 行。")
        
        # 使用正确的表头重新读取
        if file_ext in [".xls", ".xlsx"]:
            df = pd.read_excel(file_path, header=header_row_index)
        else:
            df = pd.read_csv(file_path, header=header_row_index, encoding="utf-8-sig")

    except Exception as e:
        print(f"读取文件时出错: {e}")
        return []

    # 清理和重命名列
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
    df["name"] = df["name"].apply(clean_school_name)

    universities_list = df.to_dict("records")
    print(f"成功读取并清理了 {len(universities_list)} 所学校。")
    
    return universities_list


def clean_school_name(name):
    """
    清理学校名称
    
    Args:
        name: 原始学校名称
    
    Returns:
        清理后的学校名称
    """
    if isinstance(name, str):
        if name.startswith("民办"):
            name = name[2:]
        # 去掉"市"，但不去掉"城市"或"都市"
        name = re.sub(r"(?<![城都])市", "", name)
    return name


def load_supplementary_data(file_path: str) -> dict:
    """
    加载附加数据（985、211等信息）
    """
    supp_data_map = {}
    
    try:
        print(f"正在加载附加数据文件: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            supp_list = json.load(f)
            supp_data_map = {item["name"]: item for item in supp_list}
        print(f"成功加载 {len(supp_data_map)} 条附加数据用于合并。")
    except Exception as e:
        print(f"加载 '{file_path}' 时出错: {e}，将跳过数据合并步骤。")
    
    return supp_data_map


def merge_supplementary_data(school: dict, supp_data_map: dict) -> dict:
    """
    合并学校的附加数据
    """
    school_name = school.get("name")
    
    school_output = {
        "id": school.get("id"),
        "name": school_name,
        "affiliation": school.get("affiliation"),
        "type": school.get("type"),
    }
    
    # 需要合并的字段
    fields_to_merge = [
        "majorCategory",
        "natureOfRunning",
        "is985",
        "is211",
        "isDoubleFirstClass",
    ]
    
    found_details = False
    
    if school_name in supp_data_map:
        details = supp_data_map[school_name]
        for field in fields_to_merge:
            if field in details:
                school_output[field] = details[field]
        found_details = True
    else:
        for field in fields_to_merge:
            school_output[field] = None
    
    school_output["campuses"] = []
    school_output["_campus_map_temp"] = {}  # 临时的校内去重辅助map
    
    return school_output, found_details  # type: ignore
