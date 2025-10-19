import os
import sys
import json
import csv
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# ===== 配置 =====
RANKINGS_CSV = "merged_rankings.csv"
CACHE_FILE = "google_places_cache.json"
OUTPUT_JSON_FILE = "universities_global.json"
CHECKPOINT_FILE = "processing_checkpoint.json"  # 断点续传文件
LOG_FILE_PREFIX = "dedupe_log"

GOOGLE_MAPS_KEY = os.getenv("GOOGLE_MAPS_KEY")

# Google Places API (New) 参数
PLACES_API_NEW = "https://places.googleapis.com/v1"
REQUEST_DELAY = 0.05  # API请求间隔（秒）
MAX_RETRIES = 3


# ===== 检查点管理 =====
class CheckpointManager:
    """管理处理进度的检查点"""
    
    def __init__(self, checkpoint_file: str):
        self.checkpoint_file = checkpoint_file
        self.checkpoint = self._load_checkpoint()
    
    def _load_checkpoint(self) -> dict:
        """加载检查点"""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                    checkpoint = json.load(f)
                print(f"✅ 加载检查点: {self.checkpoint_file}")
                print(f"   - 已处理: {checkpoint.get('processed_count', 0)} 条")
                print(f"   - 成功: {checkpoint.get('success_count', 0)} 条")
                print(f"   - 已查询的大学: {len(checkpoint.get('processed_names', []))} 个")
                return checkpoint
            except Exception as e:
                print(f"⚠️ 加载检查点失败: {e}")
                return self._create_empty_checkpoint()
        return self._create_empty_checkpoint()
    
    @staticmethod
    def _create_empty_checkpoint() -> dict:
        """创建空检查点"""
        return {
            "processed_count": 0,      # 已处理的总数
            "success_count": 0,        # 成功查询的数量
            "failed_count": 0,         # 失败的数量
            "processed_names": [],     # 已处理的大学名称列表
            "failed_names": [],        # 失败的大学名称列表
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
        }
    
    def save_checkpoint(self, processed_count: int, success_count: int, 
                       failed_count: int, processed_names: list, failed_names: list):
        """保存检查点"""
        self.checkpoint = {
            "processed_count": processed_count,
            "success_count": success_count,
            "failed_count": failed_count,
            "processed_names": processed_names,
            "failed_names": failed_names,
            "last_updated": datetime.now().isoformat(),
        }
        
        with open(self.checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(self.checkpoint, f, ensure_ascii=False, indent=2)
    
    def get_processed_names(self) -> set:
        """获取已处理的大学名称集合"""
        return set(self.checkpoint.get("processed_names", []))
    
    def get_failed_names(self) -> set:
        """获取失败的大学名称集合"""
        return set(self.checkpoint.get("failed_names", []))
    
    def is_completed(self, total_count: int) -> bool:
        """检查是否已完成所有处理"""
        return self.checkpoint.get("processed_count", 0) >= total_count


# ===== 日志工具 =====
class Logger(object):
    """将控制台输出同时写入文件。"""

    def __init__(self, filename="default.log"):
        self.terminal = sys.stdout
        self.log = open(filename, "w", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

    def flush(self):
        pass


# ===== 缓存管理 =====
class CacheManager:
    """管理本地缓存"""
    
    def __init__(self, cache_file: str):
        self.cache_file = cache_file
        self.cache = self._load_cache()
    
    def _load_cache(self) -> dict:
        """加载缓存"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    cache = json.load(f)
                print(f"✅ 加载缓存: {self.cache_file} ({len(cache)} 条)")
                return cache
            except Exception as e:
                print(f"⚠️ 加载缓存失败: {e}")
                return {}
        return {}
    
    def save_cache(self):
        """保存缓存"""
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)
        print(f"✅ 缓存已保存: {self.cache_file} ({len(self.cache)} 条)")
    
    def get(self, key: str):
        """获取缓存"""
        return self.cache.get(key)
    
    def set(self, key: str, value):
        """设置缓存"""
        self.cache[key] = value
    
    def has(self, key: str) -> bool:
        """检查缓存是否存在"""
        return key in self.cache


# ===== Google Places API (New) =====
class GooglePlacesAPI:
    """Google Places API (New) 封装"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
        }
    
    def autocomplete(self, query: str, latitude: float | None = None, longitude: float | None = None) -> dict | None:
        """
        Places API (New) Autocomplete 请求 - 获取 placeId
        
        Args:
            query: 查询字符串（学校名称）
            latitude: 纬度（用于位置偏向）
            longitude: 经度（用于位置偏向）
        
        Returns:
            包含 placeId 的响应字典，或 None 如果失败
        """
        url = f"{PLACES_API_NEW}/places:autocomplete"
        
        payload: dict = {
            "input": query,
        }
        
        # 添加位置偏向（如果提供了坐标）
        if latitude is not None and longitude is not None:
            payload["locationBias"] = {
                "circle": {
                    "center": {
                        "latitude": latitude,
                        "longitude": longitude,
                    },
                    "radius": 50000.0  # 50km 搜索半径
                }
            }
        
        headers = self.headers.copy()
        # 使用正确的 FieldMask 格式（不需要指定 placePrediction 路径）
        headers["X-Goog-FieldMask"] = "suggestions"
        
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.post(url, json=payload, headers=headers, timeout=15)
                response.raise_for_status()
                
                result = response.json()
                
                # 检查是否有预测结果
                suggestions = result.get("suggestions", [])
                if suggestions:
                    first_suggestion = suggestions[0]
                    place_prediction = first_suggestion.get("placePrediction", {})
                    place_id = place_prediction.get("placeId")
                    
                    if place_id:
                        return {
                            "placeId": place_id,
                            "displayName": place_prediction.get("displayName", "")
                        }
                
                return None
                    
            except requests.exceptions.Timeout:
                print(f"  - 请求超时（尝试 {attempt + 1}/{MAX_RETRIES}）")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
            except requests.exceptions.RequestException as e:
                # 添加更详细的错误信息用于调试
                try:
                    if hasattr(e, 'response') and e.response is not None:
                        error_detail = e.response.json()
                        print(f"  - API 错误: {error_detail.get('error', {}).get('message', str(e))}")
                    else:
                        print(f"  - 请求失败: {str(e)}")
                except:
                    print(f"  - 请求失败: {str(e)}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
        
        return None
    
    def place_details(self, place_id: str) -> dict | None:
        """
        Places API (New) Place Details 请求 - 获取详细信息
        
        Args:
            place_id: Google Maps place_id
        
        Returns:
            包含地点详细信息的字典，或 None 如果失败
        """
        url = f"{PLACES_API_NEW}/places/{place_id}"
        
        params = {
            "fields": "id,displayName,formattedAddress,websiteUri,location,addressComponents"
        }
        
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.get(url, params=params, headers=self.headers, timeout=15)
                response.raise_for_status()
                
                result = response.json()
                
                # 提取国家信息
                country = ""
                address_components = result.get("addressComponents", [])
                for component in address_components:
                    if "country" in component.get("types", []):
                        country = component.get("longText", "")
                        break
                
                return {
                    "id": result.get("id", place_id),
                    "displayName": result.get("displayName", {}).get("text", ""),
                    "formattedAddress": result.get("formattedAddress", ""),
                    "websiteUri": result.get("websiteUri", ""),
                    "location": result.get("location", {}),
                    "country": country,
                }
                    
            except requests.exceptions.Timeout:
                print(f"  - 请求超时（尝试 {attempt + 1}/{MAX_RETRIES}）")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
            except requests.exceptions.RequestException as e:
                print(f"  - 请求失败: {str(e)}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
        
        return None


# ===== 数据处理 =====
def read_rankings_csv(csv_file: str) -> list[dict]:
    """
    读取排名CSV文件
    
    Args:
        csv_file: CSV文件路径
    
    Returns:
        大学列表
    """
    universities = []
    
    try:
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                universities.append(row)
        
        print(f"✅ 已读取 {len(universities)} 所大学")
        return universities
    except Exception as e:
        print(f"❌ 读取CSV失败: {e}")
        return []


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


def main():
    """主程序 - 支持断点续传"""
    # 设置日志
    log_filename = f"{LOG_FILE_PREFIX}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    sys.stdout = Logger(log_filename)
    
    print(f"日志将记录到文件: {log_filename}")
    print("=" * 60)
    
    # 检查API密钥
    if not GOOGLE_MAPS_KEY:
        print("❌ 错误: 未设置 GOOGLE_MAPS_KEY 环境变量")
        print("请在 .env 文件中设置: GOOGLE_MAPS_KEY=your_api_key")
        return
    
    # 1. 读取CSV
    print("\n[1/6] 读取排名CSV...")
    universities = read_rankings_csv(RANKINGS_CSV)
    if not universities:
        print("❌ 无法读取大学数据")
        return
    
    # 2. 初始化检查点和缓存
    print("\n[2/6] 加载检查点和缓存...")
    checkpoint = CheckpointManager(CHECKPOINT_FILE)
    cache = CacheManager(CACHE_FILE)
    api = GooglePlacesAPI(GOOGLE_MAPS_KEY)
    
    # 获取已处理的大学名称
    processed_names = checkpoint.get_processed_names()
    failed_names = checkpoint.get_failed_names()
    
    print(f"  - 总大学数: {len(universities)}")
    print(f"  - 已处理: {len(processed_names)}")
    print(f"  - 失败: {len(failed_names)}")
    print(f"  - 待处理: {len(universities) - len(processed_names)}")
    
    # 检查是否已完成
    if checkpoint.is_completed(len(universities)):
        print("\n✅ 所有数据已处理，跳转到去重步骤...")
    else:
        # 3. 继续批量查询
        print(f"\n[3/6] 查询Google Places API...")
        print(f"继续处理剩余 {len(universities) - len(processed_names)} 所大学")
        
        all_results = []
        success_count = checkpoint.checkpoint.get("success_count", 0)
        failed_count = checkpoint.checkpoint.get("failed_count", 0)
        processed_list = list(processed_names)
        failed_list = list(failed_names)
        
        try:
            for idx, university in enumerate(universities, 1):
                name = university.get("Name", "").strip()
                
                # 跳过已处理的大学
                if name in processed_names:
                    # 如果在缓存中，加载结果
                    cached = cache.get(name)
                    if cached:
                        all_results.append(cached)
                    continue
                
                print(f"\n  [{idx}/{len(universities)}]", end=" ")
                
                country = university.get("Country", "")
                result = query_university(api, cache, university, country)
                
                if result:
                    all_results.append(result)
                    success_count += 1
                    processed_list.append(name)
                else:
                    failed_count += 1
                    failed_list.append(name)
                    processed_list.append(name)
                
                # 定期保存检查点（每10条或处理完成时）
                if idx % 10 == 0:
                    print(f"\n  已处理 {idx}/{len(universities)} 条")
                    cache.save_cache()
                    checkpoint.save_checkpoint(idx, success_count, failed_count, 
                                              processed_list, failed_list)
                    print(f"  💾 检查点已保存")
        
        except KeyboardInterrupt:
            print("\n\n⚠️ 处理被中断!")
            print("✅ 检查点已保存，下次运行时会继续...")
            cache.save_cache()
            checkpoint.save_checkpoint(len(processed_list), success_count, failed_count,
                                      processed_list, failed_list)
            return
        except Exception as e:
            print(f"\n\n❌ 发生错误: {e}")
            print("✅ 检查点已保存，下次运行时会继续...")
            cache.save_cache()
            checkpoint.save_checkpoint(len(processed_list), success_count, failed_count,
                                      processed_list, failed_list)
            raise
        
        # 最后保存一次缓存和检查点
        cache.save_cache()
        checkpoint.save_checkpoint(len(universities), success_count, failed_count,
                                  processed_list, failed_list)
    
    # 4. 重新加载所有缓存的结果用于去重
    print("\n[4/6] 重新加载所有缓存结果...")
    all_results = []
    for university in universities:
        name = university.get("Name", "").strip()
        cached = cache.get(name)
        if cached:
            all_results.append(cached)
    
    print(f"✅ 已加载 {len(all_results)} 条缓存结果")
    
    # 5. 去重
    print("\n[5/6] 按place_id去重...")
    deduplicated = deduplicate_by_place_id(all_results)
    print(f"✅ 原始结果: {len(all_results)} 条")
    print(f"✅ 去重后: {len(deduplicated)} 条")
    
    # 统计重复情况
    duplicates = {pid: info for pid, info in deduplicated.items() if info["count"] > 1}
    if duplicates:
        print(f"⚠️ 发现 {len(duplicates)} 个重复地点:")
        for place_id, info in list(duplicates.items())[:5]:
            print(f"   - {list(info['csv_names'])[0]}: {info['count']} 次")
    
    # 6. 输出结果
    print("\n[6/6] 生成输出JSON...")
    output = build_output_json(deduplicated, universities)
    
    with open(OUTPUT_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 结果已保存: {OUTPUT_JSON_FILE} ({len(output)} 条)")
    
    # 7. 生成辅助输出文件
    print("\n[7/7] 生成辅助文件...")
    
    # 收集被拒绝的大学（缓存中为 None 的）
    rejected_universities = []
    no_website_universities = []
    
    for university in universities:
        name = university.get("Name", "").strip()
        cached = cache.get(name)
        
        # 检查是否被拒绝（查询失败）
        if cached is None:
            rejected_universities.append(university)
        # 检查是否没有网站
        elif cached and not cached.get("website"):
            no_website_universities.append(university)
    
    # 输出被拒绝的大学
    if rejected_universities:
        rejected_csv_file = "rejected_pois_global.csv"
        try:
            with open(rejected_csv_file, "w", newline="", encoding="utf-8") as f:
                if rejected_universities:
                    writer = csv.DictWriter(f, fieldnames=rejected_universities[0].keys())
                    writer.writeheader()
                    writer.writerows(rejected_universities)
            print(f"✅ 被拒绝的大学已保存: {rejected_csv_file} ({len(rejected_universities)} 条)")
        except Exception as e:
            print(f"❌ 保存被拒绝大学失败: {e}")
    
    # 输出没有网站的大学
    if no_website_universities:
        no_website_csv_file = "universities_with_no_website.csv"
        try:
            with open(no_website_csv_file, "w", newline="", encoding="utf-8") as f:
                if no_website_universities:
                    writer = csv.DictWriter(f, fieldnames=no_website_universities[0].keys())
                    writer.writeheader()
                    writer.writerows(no_website_universities)
            print(f"✅ 没有网站的大学已保存: {no_website_csv_file} ({len(no_website_universities)} 条)")
        except Exception as e:
            print(f"❌ 保存没有网站大学失败: {e}")
    
    print("\n" + "=" * 60)
    print("✅ 处理完成!")
    print(f"  - 输入: {len(universities)} 所大学")
    print(f"  - 成功查询: {len(all_results)} 条")
    print(f"  - 查询失败（被拒绝）: {len(rejected_universities)} 条")
    print(f"  - 没有网站: {len(no_website_universities)} 条")
    print(f"  - 去重后: {len(output)} 条")
    if len(all_results) > 0:
        print(f"  - 去重率: {(1 - len(output)/len(all_results))*100:.1f}%")
    print("\n💡 输出文件:")
    print(f"  - {OUTPUT_JSON_FILE} - 最终输出")
    print(f"  - rejected_pois_global.csv - 查询失败的大学")
    print(f"  - universities_with_no_website.csv - 没有网站的大学")


if __name__ == "__main__":
    main()
