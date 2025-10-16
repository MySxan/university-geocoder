"""
解析器模块
"""

from .campus_parser import (
    parse_campus_name,
    post_process_name,
    is_valid_campus_name,
    is_location_substring,
    extract_bracketed_content,
)

__all__ = [
    "parse_campus_name",
    "post_process_name",
    "is_valid_campus_name",
    "is_location_substring",
    "extract_bracketed_content",
]
