import csv
import json


def write_universities_json(universities: list[dict], output_file: str):
    """
    将大学数据写入JSON文件
    """
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(universities, f, ensure_ascii=False, indent=4)
    print(f"✅ 数据已写入: {output_file} ({len(universities)} 条)")


def write_csv(data_list: list[dict], output_file: str, description: str = "数据"):
    """
    将数据写入CSV文件
    """
    if not data_list:
        return
    
    # 获取所有可能的字段
    header = sorted(list(set(key for item in data_list for key in item.keys())))
    
    with open(output_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(data_list)
    
    print(f"✅ {description}已写入: {output_file} ({len(data_list)} 条)")


def prepare_output_data(universities_data_map: dict) -> tuple[list[dict], list[dict]]:
    """
    准备输出数据，分离有校区和无校区的大学
    """
    final_universities_data = list(universities_data_map.values())
    
    # 清理临时的校内map
    for school in final_universities_data:
        if "_campus_map_temp" in school:
            del school["_campus_map_temp"]
    
    universities_with_campuses = []
    universities_without_campuses = []
    
    for school in final_universities_data:
        if school.get("campuses"):
            universities_with_campuses.append(school)
        else:
            universities_without_campuses.append(school)
    
    return universities_with_campuses, universities_without_campuses
