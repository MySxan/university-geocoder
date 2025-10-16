# 全国高校地理信息汇总

**中文** | [English](README_en.md)

This project is a variant of [cn-university-geocoder](https://github.com/Naptie/cn-university-geocoder),
extended for global universities with multi-map API support.  
一个用于批量查询并收集全国高校地理信息的 Python 工具。基于腾讯地图 API，融合教育部数据和补充信息，导出结构化结果以便后续使用。

## 功能特性

- 从 Excel 读取高校列表，并与详细 JSON 数据合并
- 调用腾讯地图 API 获取校区地理坐标（支持 QPS 限流与重试）
- 清洗与去重校区名称
- 输出 JSON 和 CSV 报告（包括错误与缺失数据报告）
- 全流程日志记录，便于追溯

## 环境要求

- Python 3.8+
- 依赖见 `requirements.txt`

## 环境搭建

1. **克隆本仓库：**

   ```bash
   git clone <repo-url>
   cd cn-university-geocoder
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

4. **在项目根目录准备 `.env` 文件，填写腾讯地图 API 密钥：**

   ```env
   TENCENT_MAP_KEY="your_key"
   TENCENT_MAP_SK="your_secret_key"
   ```

## 使用方法

运行主脚本：

```bash
python main.py
```

- 日志将输出到带时间戳的日志文件（如 `run_log_YYYYMMDD_HHMMSS.log`）。
- 结果文件包括：
  - `universities.json`：带校区地理信息的高校
  - `universities_with_no_campuses.csv`：未找到校区的高校
  - `rejected_pois.csv`：被名称规则拒绝的 POI
  - `universities_without_details.csv`：补充 JSON 缺失详细信息的高校

## 文件结构

- `main.py` — 主处理脚本
- `requirements.txt` — Python 依赖
- `univ_moe.xls` — 输入 Excel 文件
- `univ_supp.json` — 补充高校详细信息

## 注意事项

- 本脚本专为中国高校数据与腾讯地图 API 设计。
- 请确保输入文件为最新，API 配额充足以获得最佳效果。

## 许可证

[Mozilla 公共许可证 2.0](LICENSE)
