import time
from src.api.google_places import GooglePlacesAPI, CacheManager
from src.config_global import REQUEST_DELAY


def query_university(api: GooglePlacesAPI, cache: CacheManager, 
                     university: dict, country: str | None = None) -> dict | None:
    """
    查询单个大学的Google Places信息
    
    使用两步流程：
    1. Autocomplete 获取 placeId
    2. Place Details 获取详细信息
    
    Args:
        api: GooglePlacesAPI实例
        cache: CacheManager实例
        university: 大学数据字典（包含 Name, Country, 排名等字段）
        country: 国家代码（用于限制搜索）
    
    Returns:
        查询结果（包含 CSV 原始数据的引用）
    """
    name = university.get("Name", "").strip()
    if not name:
        return None
    
    # 检查缓存
    cache_key = name
    if cache.has(cache_key):
        cached = cache.get(cache_key)
        if cached:
            print(f"  ✓ {name} (来自缓存)")
        return cached
    
    # 第一步：使用 Autocomplete 获取 placeId
    print(f"  查询: {name}")
    time.sleep(REQUEST_DELAY)
    
    # 获取坐标用于位置偏向（如果有）
    latitude = None
    longitude = None
    try:
        lat_str = university.get("Latitude", "")
        lon_str = university.get("Longitude", "")
        if lat_str and lon_str:
            latitude = float(lat_str)
            longitude = float(lon_str)
    except (ValueError, TypeError):
        pass
    
    # 构建查询字符串：格式为 "University Name, Country"
    if country:
        query_string = f"{name}, {country}"
    else:
        query_string = name
    
    # 调用 Autocomplete API
    autocomplete_result = api.autocomplete(query_string, latitude, longitude)
    
    if not autocomplete_result:
        print(f"    ✗ 未找到结果 (Autocomplete)")
        cache.set(cache_key, None)
        return None
    
    place_id = autocomplete_result.get("placeId")
    if not place_id:
        print(f"    ✗ 未获取到 placeId")
        cache.set(cache_key, None)
        return None
    
    # 第二步：使用 Place Details 获取详细信息
    time.sleep(REQUEST_DELAY)
    details_result = api.place_details(place_id)
    
    if not details_result:
        print(f"    ✗ 获取详细信息失败")
        cache.set(cache_key, None)
        return None
    
    # 构建完整结果（包含 CSV 原始数据引用）
    place_result = {
        "place_id": place_id,
        "id": details_result.get("id", place_id),
        "csv_name": name,  # 保存 CSV 原始名称
        "api_name": details_result.get("displayName", name),  # API 返回的名称
        "formatted_address": details_result.get("formattedAddress", ""),
        "website": details_result.get("websiteUri", ""),
        "location": details_result.get("location", {}),
        "country": details_result.get("country", country or ""),
        "csv_data": university,  # 保存整个 CSV 行数据
    }
    
    print(f"    ✓ 找到: {place_result['api_name']}")
    
    # 缓存结果
    cache.set(cache_key, place_result)
    
    return place_result


def deduplicate_by_place_id(results: list[dict]) -> dict[str, dict]:
    """
    按place_id去重，并合并排名信息
    
    Args:
        results: 查询结果列表
    
    Returns:
        按place_id分组的去重结果
    """
    deduplicated = {}
    
    for result in results:
        if not result:
            continue
        
        place_id = result.get("place_id")
        if not place_id:
            continue
        
        if place_id not in deduplicated:
            deduplicated[place_id] = {
                "place_id": place_id,
                "csv_data_list": [],  # 保存所有匹配的 CSV 数据（用于合并排名）
                "csv_names": set(),  # CSV 中不同的名称
                "locations": set(),  # 不同位置
                "original_data": result,  # 保存第一个匹配的完整数据
                "count": 0,  # 出现次数
            }
        
        # 保存 CSV 数据用于后续排名合并
        csv_data = result.get("csv_data", {})
        if csv_data:
            deduplicated[place_id]["csv_data_list"].append(csv_data)
        
        # 累计 CSV 名称信息
        csv_name = result.get("csv_name")
        if csv_name:
            deduplicated[place_id]["csv_names"].add(csv_name)
        
        # 地理位置 - 从新 API 的 location 字段提取
        location = result.get("location", {})
        if location:
            lat = location.get("latitude")
            lng = location.get("longitude")
            if lat and lng:
                deduplicated[place_id]["locations"].add((lat, lng))
        
        deduplicated[place_id]["count"] += 1
    
    return deduplicated
