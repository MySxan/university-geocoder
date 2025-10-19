import sys
import json
import os
from datetime import datetime


class Logger(object):
    """将控制台输出同时写入文件"""

    def __init__(self, filename="default.log"):
        self.terminal = sys.stdout
        self.log = open(filename, "w", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

    def flush(self):
        pass


class CheckpointManager:
    """管理处理进度的检查点"""
    
    def __init__(self, checkpoint_file: str):
        self.checkpoint_file = checkpoint_file
        self.checkpoint = self._load_checkpoint()
    
    def _load_checkpoint(self) -> dict:
        """加载检查点"""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                    checkpoint = json.load(f)
                print(f"✅ 加载检查点: {self.checkpoint_file}")
                print(f"   - 已处理: {checkpoint.get('processed_count', 0)} 条")
                print(f"   - 成功: {checkpoint.get('success_count', 0)} 条")
                print(f"   - 已查询的大学: {len(checkpoint.get('processed_names', []))} 个")
                return checkpoint
            except Exception as e:
                print(f"⚠️ 加载检查点失败: {e}")
                return self._create_empty_checkpoint()
        return self._create_empty_checkpoint()
    
    @staticmethod
    def _create_empty_checkpoint() -> dict:
        """创建空检查点"""
        return {
            "processed_count": 0,      # 已处理的总数
            "success_count": 0,        # 成功查询的数量
            "failed_count": 0,         # 失败的数量
            "processed_names": [],     # 已处理的大学名称列表
            "failed_names": [],        # 失败的大学名称列表
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
        }
    
    def save_checkpoint(self, processed_count: int, success_count: int, 
                       failed_count: int, processed_names: list, failed_names: list):
        """保存检查点"""
        self.checkpoint = {
            "processed_count": processed_count,
            "success_count": success_count,
            "failed_count": failed_count,
            "processed_names": processed_names,
            "failed_names": failed_names,
            "last_updated": datetime.now().isoformat(),
        }
        
        with open(self.checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(self.checkpoint, f, ensure_ascii=False, indent=2)
    
    def get_processed_names(self) -> set:
        """获取已处理的大学名称集合"""
        return set(self.checkpoint.get("processed_names", []))
    
    def get_failed_names(self) -> set:
        """获取失败的大学名称集合"""
        return set(self.checkpoint.get("failed_names", []))
    
    def is_completed(self, total_count: int) -> bool:
        """检查是否已完成所有处理"""
        return self.checkpoint.get("processed_count", 0) >= total_count
