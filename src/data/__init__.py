"""
数据模块
"""

from .loader import (
    load_university_data,
    load_supplementary_data,
    merge_supplementary_data,
    clean_school_name,
)
from .loader_global import read_rankings_csv

__all__ = [
    "load_university_data",
    "load_supplementary_data",
    "merge_supplementary_data",
    "clean_school_name",
    "read_rankings_csv",
]
