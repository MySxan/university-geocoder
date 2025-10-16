"""
输出模块
"""

from .writer import (
    write_universities_json,
    write_csv,
    prepare_output_data,
)

__all__ = [
    "write_universities_json",
    "write_csv",
    "prepare_output_data",
]
