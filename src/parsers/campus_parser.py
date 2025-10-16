import re


def post_process_name(name: str) -> str | None:
    """
    对校区名称进行后处理
    """
    if not name:
        return None

    # 1. trim
    processed_name = name.strip()
    # 2. 去除"-"和"&"
    processed_name = processed_name.replace("-", "").replace("&", "")
    # 3. 去除结尾的特定方位和期数字样
    suffixes_to_remove = [
        "西区",
        "东区",
        "北区",
        "南区",
        "中区",
        "一期",
        "二期",
        "三期",
        "四期",
        "五期",
        "六期",
        "七期",
        "八期",
        "九期",
        "十期",
    ]
    for suffix in suffixes_to_remove:
        if processed_name.endswith(suffix):
            processed_name = processed_name[: -len(suffix)]

    # 4. 将"XX主校区YY"替换为"XX校区YY"
    processed_name = re.sub(r"(.+)主校区", r"\1校区", processed_name).strip()

    return processed_name if processed_name else None


def is_valid_campus_name(name: str | None) -> bool:
    """
    检查名称是否符合校区名定义
    """
    if name is None:
        return True
    if not name:
        return False
    # 非附属
    if "附属" in name or "医院" in name:
        return False
    # 以特定词结尾
    valid_endings = ["校区", "园区", "院区", "校园", "学校", "分校", "院"]
    for ending in valid_endings:
        if name.endswith(ending):
            return True
    return False


def is_location_substring(text: str | None, poi: dict) -> bool:
    """
    检查文本是否是省、市、区之一的子字符串。
    """
    if not text:
        return False
    poi_province = poi.get("province", "")
    poi_city = poi.get("city", "")
    poi_district = poi.get("district", "")

    return (
        (poi_province and text in poi_province)
        or (poi_city and text in poi_city)
        or (poi_district and text in poi_district)
    )


def extract_bracketed_content(text: str) -> str:
    """
    提取文本中括号内的内容，并返回去除括号后的内容。
    """
    text = text.strip()
    if not text:
        return ""
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    return text.strip()


def parse_campus_name(poi: dict, school_name: str):
    """
    根据规则解析POI标题以提取校区名称。
    """
    poi_title = poi.get("title", "")

    # 1. 灵活的前缀匹配
    pattern_str = (
        re.escape(school_name).replace(r"（", r"[\(（]").replace(r"）", r"[\)）]")
    )
    pattern = re.compile(f"^{pattern_str}")
    match = pattern.match(poi_title)

    if not match:
        return "REJECT"

    if match.end() == len(poi_title):
        return None

    remaining_title = poi_title[match.end() :].strip()

    if (not remaining_title) or (remaining_title in ["主校区", "校本部"]):
        return None

    # 2. 将剩余部分分割为带括号和不带括号的片段
    parts = [p for p in re.split(r"(\([^)]+\))", remaining_title) if p]

    # 3. 从后向前遍历片段，寻找第一个有效的"锚点"
    for i in range(len(parts) - 1, -1, -1):
        current_part = parts[i]
        # 提取片段内容（无论是否在括号内）
        content = extract_bracketed_content(current_part)

        post_processed_content = post_process_name(content)

        # 检查此片段是否为有效锚点
        is_campus_name = is_valid_campus_name(post_processed_content)
        is_loc_substr = is_location_substring(post_processed_content, poi)
        is_anchor = is_campus_name or is_loc_substr

        if is_anchor:
            # 4. 如果找到锚点，拼接从开头到此锚点的所有部分
            final_name_parts = []
            for j in range(i + 1):
                final_name_parts.append(extract_bracketed_content(parts[j]))

            final_name = "".join(final_name_parts)

            # 如果最终拼接的名称本身不符合规则（通常是因为靠行政区划匹配上的）
            # 则为其补上"校区"后缀
            if (
                not is_valid_campus_name(post_process_name(final_name))
                and is_loc_substr
            ):
                final_name += "校区"

            return post_process_name(final_name)

    return "REJECT"
