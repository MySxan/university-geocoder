import time
import requests


class GooglePlacesAPI:
    """Google Places API (New) 封装"""
    
    def __init__(self, api_key: str, places_api_url: str = "https://places.googleapis.com/v1", 
                 max_retries: int = 3, request_delay: float = 0.05):
        """
        Initialize Google Places API wrapper
        
        Args:
            api_key: Google Maps API key
            places_api_url: Base URL for Places API (New)
            max_retries: Maximum retry attempts for failed requests
            request_delay: Delay between requests (seconds)
        """
        self.api_key = api_key
        self.places_api_url = places_api_url
        self.max_retries = max_retries
        self.request_delay = request_delay
        self.session = requests.Session()
        self.headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
        }
    
    def autocomplete(self, query: str, latitude: float | None = None, 
                     longitude: float | None = None) -> dict | None:
        """
        Places API (New) Autocomplete 请求 - 获取 placeId
        
        Args:
            query: 查询字符串（学校名称）
            latitude: 纬度（用于位置偏向）
            longitude: 经度（用于位置偏向）
        
        Returns:
            包含 placeId 的响应字典，或 None 如果失败
        """
        url = f"{self.places_api_url}/places:autocomplete"
        
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
        
        for attempt in range(self.max_retries):
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
                print(f"  - 请求超时（尝试 {attempt + 1}/{self.max_retries}）")
                if attempt < self.max_retries - 1:
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
                if attempt < self.max_retries - 1:
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
        url = f"{self.places_api_url}/places/{place_id}"
        
        params = {
            "fields": "id,displayName,formattedAddress,websiteUri,location,addressComponents"
        }
        
        for attempt in range(self.max_retries):
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
                print(f"  - 请求超时（尝试 {attempt + 1}/{self.max_retries}）")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
            except requests.exceptions.RequestException as e:
                print(f"  - 请求失败: {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
        
        return None


class CacheManager:
    """管理本地缓存"""
    
    def __init__(self, cache_file: str):
        """
        Initialize cache manager
        
        Args:
            cache_file: Path to cache file (JSON format)
        """
        import json
        import os
        
        self.cache_file = cache_file
        self.cache = self._load_cache()
        self.json = json
        self.os = os
    
    def _load_cache(self) -> dict:
        """加载缓存"""
        import json
        import os
        
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
            self.json.dump(self.cache, f, ensure_ascii=False, indent=2)
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
