"""
数据模块
"""

from .loader import (
    load_university_data,
    load_supplementary_data,
    merge_supplementary_data,
    clean_school_name,
)

__all__ = [
    "load_university_data",
    "load_supplementary_data",
    "merge_supplementary_data",
    "clean_school_name",
]
