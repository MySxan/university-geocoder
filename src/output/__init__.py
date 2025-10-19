"""
输出模块
"""

from .writer import (
    write_universities_json,
    write_csv,
    prepare_output_data,
)
from .writer_global import (
    build_output_json,
    write_output_json,
    write_rejected_universities_csv,
    write_no_website_universities_csv,
)

__all__ = [
    "write_universities_json",
    "write_csv",
    "prepare_output_data",
    "build_output_json",
    "write_output_json",
    "write_rejected_universities_csv",
    "write_no_website_universities_csv",
]
