"""
Data Loading Module for Global Universities

Load university ranking data from CSV
"""

import csv


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
