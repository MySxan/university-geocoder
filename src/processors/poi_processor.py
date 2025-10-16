import math
import time


def process_poi_data(
    poi: dict,
    school_name: str,
    parse_campus_name_func,
    final_universities_data_map: dict,
    processed_pois_map: dict,
    rejected_pois: list,
) -> bool:
    """
    处理单个POI数据
    """
    poi_id = poi.get("id")
    poi_title = poi.get("title", "")
    
    if not poi_id or not poi_title:
        return False

    # 解析校区名称
    campus_name_processed = parse_campus_name_func(poi, school_name)

    if campus_name_processed == "REJECT":
        rejected_pois.append(poi)
        print(f"    [❌] {poi.get('title')}")
        return False

    # --- 联合去重逻辑 ---
    current_prefix_ratio = len(school_name) / len(poi_title)
    previous_global_match = processed_pois_map.get(poi_id)

    # 1. 全局检查：是否应归属此学校
    if (
        previous_global_match
        and current_prefix_ratio <= previous_global_match["prefix_ratio"]
    ):
        print(
            f"    [🌐] {poi_title} (ID: {poi_id}) 已分配给更优匹配 "
            f"{previous_global_match['school_name']} "
            f"(占比 {previous_global_match['prefix_ratio']:.2f})"
        )
        return False

    # 2. 校内检查：是否是同名校区中更具代表性的一个
    current_school_data = final_universities_data_map[school_name]
    local_campus_map = current_school_data["_campus_map_temp"]
    existing_local_entry = local_campus_map.get(campus_name_processed)
    current_poi_title_len = len(poi_title)

    if (
        existing_local_entry
        and current_poi_title_len >= existing_local_entry["title_len"]
    ):
        print(
            f"    [⏭️] {poi_title} → {campus_name_processed} "
            f"(校内已有更优匹配 {existing_local_entry['poi_title']})"
        )
        return False

    # --- 执行添加或转移 ---
    if previous_global_match:  # 从其他学校转移过来
        prev_school_name = previous_global_match["school_name"]
        prev_school_output = final_universities_data_map.get(prev_school_name)
        if prev_school_output:
            prev_school_output["campuses"] = [
                c
                for c in prev_school_output["campuses"]
                if c.get("id") != poi_id
            ]
            print(
                f"    [🔄] {poi_title}: {prev_school_name} "
                f"(占比 {previous_global_match['prefix_ratio']:.2f}) → "
                f"{school_name} (占比 {current_prefix_ratio:.2f})"
            )

    if existing_local_entry:  # 替换校内已有的POI
        old_poi_id = existing_local_entry["poi_id"]
        current_school_data["campuses"] = [
            c
            for c in current_school_data["campuses"]
            if c.get("id") != old_poi_id
        ]
        print(
            f"    [🔄] {poi_title} 替换了校内同校区名的POI "
            f"{existing_local_entry['poi_title']}"
        )

    # 构建校区数据
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

    # 更新全局和校内追踪信息
    processed_pois_map[poi_id] = {
        "school_name": school_name,
        "prefix_ratio": current_prefix_ratio,
    }
    local_campus_map[campus_name_processed] = {
        "poi_id": poi_id,
        "title_len": current_poi_title_len,
        "poi_title": poi_title,
    }
    
    print(f"    [✅] {poi_title} → {campus_name_processed} (ID: {poi_id})")
    return True


def fetch_school_campuses(
    school_name: str,
    api_request_func,
    api_path: str,
    api_key: str,
    api_sk: str,
    page_size: int = 20,
) -> list[dict]:
    """
    获取学校的所有校区POI数据（分页）
    """
    all_pois = []
    page_index = 1
    total_pages = 1

    while page_index <= total_pages:
        print(f"  - 正在请求第 {page_index}/{total_pages} 页...")
        
        params = {
            "keyword": school_name,
            "key": api_key,
            "filter": "category=大学",
            "get_ad": 1,
            "page_size": page_size,
            "page_index": page_index,
            "added_fields": "category_code",
        }
        
        response_data = api_request_func(api_path, params, api_sk)
        time.sleep(0.2)  # 避免QPS限制

        if response_data:
            if page_index == 1:
                count = response_data.get("count", 0)
                total_pages = math.ceil(count / page_size)

            all_pois.extend(response_data.get("data", []))
        else:
            print(f"  - API请求失败或无数据，跳过此学校的后续请求。")
            break
        
        page_index += 1
    
    return all_pois
