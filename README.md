# 全球高校地理信息汇总

**中文** | [English](README_en.md)

这个项目是 [cn-university-geocoder](https://github.com/Naptie/cn-university-geocoder) 的一个变体，扩展了对全球高校的支持，使用 Google Places API (New)。它是一个用于批量查询并收集全球高校地理信息的 Python 工具。支持中国高校（基于腾讯地图 API）和全球高校（基于 Google Places API），融合多个大学排名数据，导出结构化结果以便后续使用。

## 功能特性

### 中国高校处理 (main.py)

- 从 Excel 读取高校列表，并与详细 JSON 数据合并
- 调用腾讯地图 API 获取校区地理坐标（支持 QPS 限流与重试）
- 清洗与去重校区名称
- 输出 JSON 和 CSV 报告（包括错误与缺失数据报告）

### 全球高校处理 (main_global.py)

- 从 CSV 读取全球高校列表及排名信息（QS、THE、USNews/LAC）
- 调用 Google Places API (New) 获取全球高校地理坐标和详细信息
- Autocomplete（获取 placeId）→ Place Details（获取详细信息）
- 多个高校映射到同一地点时，合并排名信息而非丢弃
- 支持中断后继续处理，避免重复查询
- 本地缓存以避免重复 API 调用，节省配额
- 输出 JSON 和 CSV 报告（包括查询失败和缺失网站数据报告）
- 全流程日志记录，便于追溯

## 环境要求

- Python 3.8+
- 依赖见 `requirements.txt`

## 环境搭建

1. **克隆本仓库：**

   ```bash
   git clone <repo-url>
   cd university-geocoder
   ```

2. **创建并激活虚拟环境（推荐）：**

   - Windows：

     ```bash
     python -m venv venv
     venv\Scripts\activate
     ```

   - macOS/Linux：

     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **安装依赖：**

   ```bash
   pip install -r requirements.txt
   ```

4. **在项目根目录准备 `.env` 文件，填写必要的 API 密钥：**

   ```env
   # 中国高校处理 (main.py) 使用
   TENCENT_MAP_KEY="your_tencent_key"
   TENCENT_MAP_SK="your_tencent_secret_key"

   # 全球高校处理 (main_global.py) 使用
   GOOGLE_MAPS_KEY="your_google_maps_key"
   ```

## 使用方法

### 中国高校数据处理

运行主脚本处理中国高校：

```bash
python main.py
```

- 日志将输出到带时间戳的日志文件（如 `run_log_YYYYMMDD_HHMMSS.log`）
- 结果文件包括：
  - `universities.json`：带校区地理信息的高校
  - `universities_with_no_campuses.csv`：未找到校区的高校
  - `rejected_pois.csv`：被名称规则拒绝的 POI
  - `universities_without_details.csv`：补充 JSON 缺失详细信息的高校

### 全球高校数据处理

运行全球高校处理脚本：

```bash
python main_global.py
```

- 日志将输出到带时间戳的日志文件（如 `dedupe_log_YYYYMMDD_HHMMSS.log`）
- 结果文件包括：
  - `universities_global.json`：带地理信息和排名的全球高校数据
  - `rejected_pois_global.csv`：Google Places API 查询失败的高校
  - `universities_with_no_website.csv`：找到但缺少网站信息的高校
  - `google_places_cache.json`：API 响应缓存（用于断点续传）
  - `processing_checkpoint.json`：处理进度检查点

## 文件结构

### 主脚本

- `main.py` — 中国高校数据处理（基于腾讯地图 API）
- `main_global.py` — 全球高校数据处理（基于 Google Places API）

### 输入数据

- `univ_moe.xls` — 中国教育部高校列表（用于 main.py）
- `univ_supp.json` — 补充高校详细信息（用于 main.py）
- `merged_rankings.csv` — 全球高校排名数据（用于 main_global.py）
  - 包含字段：Name, Country, QS_Rank, THE_Rank, USNews_Rank, Latitude, Longitude 等

### 输出数据

#### main.py 输出

- `universities.json` — 最终高校数据（含校区地理坐标）
- `universities_with_no_campuses.csv` — 未找到校区的高校
- `rejected_pois.csv` — 被规则拒绝的 POI

#### main_global.py 输出

- `universities_global.json` — 最终全球高校数据（含排名和地理坐标）
- `rejected_pois_global.csv` — API 查询失败的高校
- `universities_with_no_website.csv` — 缺少网站信息的高校

### 工作文件

- `requirements.txt` — Python 依赖
- `.env` — 环境变量配置（需自行创建）
- `google_places_cache.json` — Google Places API 响应缓存
- `processing_checkpoint.json` — 处理进度检查点
- `dedupe_log_*.log` — 详细处理日志

## 注意事项

- **中国高校处理 (main.py)**：专为中国高校数据与腾讯地图 API 设计
- **全球高校处理 (main_global.py)**：支持全球范围高校，使用 Google Places API (New)
- 请确保输入数据文件存在且格式正确
- API 配额充足以获得最佳效果
- 首次运行可能较慢（需要调用 API），后续运行会利用本地缓存加速
- 处理中断后，下次运行会自动从检查点继续，避免重复查询

## 许可证

[Mozilla 公共许可证 2.0](LICENSE)
