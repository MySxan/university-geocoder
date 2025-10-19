import csv
import json


def build_output_json(deduplicated: dict, university_data: list[dict]) -> list[dict]:
    """
    构建输出JSON格式
    
    输出字段: id, name, type, majorCategory, natureOfRunning, QSrank, THErank, LACrank, campuses
    - type: 统一为 "Undergraduate"
    - name: 来自 CSV 的原始名称
    - majorCategory: 根据是否有 LAC 排名确定 (LAC / Comprehensive)
    - QSrank, THErank, LACrank: 来自 CSV 的排名（可能为 null）
    - campuses: 只包含一个对象，字段为 id, name, address, country, website, location
    
    Args:
        deduplicated: 去重后的结果
        university_data: 原始大学数据
    
    Returns:
        标准输出格式的列表
    """
    output = []
    
    # 构建原始数据的映射（用于获取排名等）
    data_map = {}
    for univ in university_data:
        name = univ.get("Name", "").strip()
        if name:
            data_map[name] = univ
    
    # 处理每个去重后的地点
    for place_id, dedup_info in deduplicated.items():
        original_data = dedup_info["original_data"]
        csv_data_list = dedup_info.get("csv_data_list", [])
        csv_name = original_data.get("csv_name", "Unknown University")
        
        # 合并排名信息：从所有匹配的大学中收集排名
        # 优先选择有排名的数据（而不是只用第一条）
        qs_rank: int | str | None = None
        the_rank: int | str | None = None
        lac_rank: int | str | None = None
        
        # 从 csv_data_list 中找第一个有 QS_Rank 的
        for csv_data in csv_data_list:
            qs_rank_str = csv_data.get("QS_Rank", "").strip()
            if qs_rank_str and qs_rank_str != "":
                try:
                    qs_rank = int(qs_rank_str)
                except ValueError:
                    qs_rank = qs_rank_str
                break
        
        # 从 csv_data_list 中找第一个有 THE_Rank 的
        for csv_data in csv_data_list:
            the_rank_str = csv_data.get("THE_Rank", "").strip()
            if the_rank_str and the_rank_str != "":
                try:
                    the_rank = int(float(the_rank_str))
                except ValueError:
                    the_rank = the_rank_str
                break
        
        # 从 csv_data_list 中找第一个有 USNews_Rank 的
        for csv_data in csv_data_list:
            lac_rank_str = csv_data.get("USNews_Rank", "").strip()
            if lac_rank_str and lac_rank_str != "":
                try:
                    lac_rank = int(lac_rank_str)
                except ValueError:
                    lac_rank = lac_rank_str
                break
        
        # 如果没有在 csv_data_list 中找到任何排名，则使用原始数据的排名
        if csv_data_list and (qs_rank is None or the_rank is None or lac_rank is None):
            # 这通常不会发生，因为我们已经遍历了所有数据
            pass
        
        # 根据是否有 LAC 排名确定 majorCategory
        major_category = "LAC" if lac_rank is not None else "Comprehensive"
        
        # 获取 natureOfRunning，优先从 csv_data_list 中选择
        nature_of_running = "Public"
        for csv_data in csv_data_list:
            if csv_data.get("natureOfRunning"):
                nature_of_running = csv_data.get("natureOfRunning")
                break
        
        # 只保留一个campus，包含id、address、country、website等字段
        campuses = []
        
        # 优先使用第一个位置
        if dedup_info["locations"]:
            lat, lng = list(dedup_info["locations"])[0]
            campus_obj = {
                "id": place_id,  # Google Maps place_id
                "name": None,    # campus 名称为 null
                "address": original_data.get("formatted_address", ""),
                "country": original_data.get("country", ""),  # 从 API 响应获取
                "website": original_data.get("website", ""),
                "location": {
                    "type": "Point",
                    "coordinates": [lng, lat]  # GeoJSON格式：[longitude, latitude]
                }
            }
            campuses.append(campus_obj)
        elif original_data.get("location"):
            # 新 API 格式的位置数据
            location = original_data.get("location", {})
            lat = location.get("latitude")
            lng = location.get("longitude")
            if lat and lng:
                campus_obj = {
                    "id": place_id,
                    "name": None,
                    "address": original_data.get("formatted_address", ""),
                    "country": original_data.get("country", ""),
                    "website": original_data.get("website", ""),
                    "location": {
                        "type": "Point",
                        "coordinates": [lng, lat]
                    }
                }
                campuses.append(campus_obj)
        
        # 构建输出项
        output_item = {
            "id": place_id,  # 使用 Google Maps place_id 作为 id
            "name": csv_name,  # 使用 CSV 中的原始名称
            "type": "Undergraduate",  # 统一为 Undergraduate
            "majorCategory": major_category,  # LAC 或 Comprehensive
            "natureOfRunning": nature_of_running,  # 从 CSV 获取
            "QSrank": qs_rank,
            "THErank": the_rank,
            "LACrank": lac_rank,
            "campuses": campuses,
        }
        
        output.append(output_item)
    
    return output


def write_output_json(output_data: list[dict], output_file: str):
    """
    Write output data to JSON file
    
    Args:
        output_data: List of university data dicts
        output_file: Output file path
    """
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f"✅ 结果已保存: {output_file} ({len(output_data)} 条)")


def write_rejected_universities_csv(universities: list[dict], output_file: str):
    """
    Write rejected universities to CSV
    
    Args:
        universities: List of rejected university dicts
        output_file: Output CSV file path
    """
    if not universities:
        return
    
    try:
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=universities[0].keys())
            writer.writeheader()
            writer.writerows(universities)
        print(f"✅ 被拒绝的大学已保存: {output_file} ({len(universities)} 条)")
    except Exception as e:
        print(f"❌ 保存被拒绝大学失败: {e}")


def write_no_website_universities_csv(universities: list[dict], output_file: str):
    """
    Write universities without website to CSV
    
    Args:
        universities: List of university dicts without website
        output_file: Output CSV file path
    """
    if not universities:
        return
    
    try:
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=universities[0].keys())
            writer.writeheader()
            writer.writerows(universities)
        print(f"✅ 没有网站的大学已保存: {output_file} ({len(universities)} 条)")
    except Exception as e:
        print(f"❌ 保存没有网站大学失败: {e}")
