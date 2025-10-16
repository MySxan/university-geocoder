import hashlib
import os
import time
from urllib.parse import urlencode

import requests


# API相关配置
API_HOST = "https://apis.map.qq.com"
API_PATH = "/ws/place/v1/suggestion"
MAX_RETRIES = 10  # QPS超限时的最大重试次数
RETRY_DELAY = 1  # 重试前的等待时间（秒）


class QuotaExceededError(Exception):
    """当API每日调用量达到上限时抛出的自定义异常。"""
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
