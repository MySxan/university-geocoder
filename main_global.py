"""
Global University Geocoder - Main Entry Point

Batch geocoding of global universities using Google Places API (New).
Supports checkpoint resumption and local caching for efficient processing.
"""

import sys
import json
import csv
import time
from datetime import datetime

from src.config_global import (
    RANKINGS_CSV,
    CACHE_FILE,
    OUTPUT_JSON_FILE,
    CHECKPOINT_FILE,
    LOG_FILE_PREFIX,
    GOOGLE_MAPS_KEY,
    PLACES_API_NEW,
    MAX_RETRIES,
    REQUEST_DELAY,
    REJECTED_POIS_CSV,
    NO_WEBSITE_CSV,
)
from src.api.google_places import GooglePlacesAPI, CacheManager
from src.data.loader_global import read_rankings_csv
from src.utils.checkpoint import Logger, CheckpointManager
from src.processors.query_processor import query_university, deduplicate_by_place_id
from src.output.writer_global import (
    build_output_json,
    write_output_json,
    write_rejected_universities_csv,
    write_no_website_universities_csv,
)


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
    api = GooglePlacesAPI(GOOGLE_MAPS_KEY, PLACES_API_NEW, MAX_RETRIES, REQUEST_DELAY)
    
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
    write_output_json(output, OUTPUT_JSON_FILE)
    
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
    write_rejected_universities_csv(rejected_universities, REJECTED_POIS_CSV)
    
    # 输出没有网站的大学
    write_no_website_universities_csv(no_website_universities, NO_WEBSITE_CSV)
    
    # 输出统计信息
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
    print(f"  - {REJECTED_POIS_CSV} - 查询失败的大学")
    print(f"  - {NO_WEBSITE_CSV} - 没有网站的大学")


if __name__ == "__main__":
    main()
