# scripts/core/proofreading_tracker.py
import os
import logging
import csv
from typing import List, Dict, Any
from scripts.app_settings import DEST_DIR, LANGUAGES
from scripts.utils import i18n


class ProofreadingTracker:
    """
    校对进度追踪器
    
    用于追踪和记录翻译文件的校对进度，生成校对进度表格
    """
    
    def __init__(self, mod_name: str, output_folder_name: str, target_lang_code: str = "zh-CN"):
        """
        初始化校对进度追踪器
        
        Args:
            mod_name: Mod名称
            output_folder_name: 输出文件夹名称
            target_lang_code: 目标语言代码（用于确定输出路径）
        """
        self.mod_name = mod_name
        self.output_folder_name = output_folder_name
        self.target_lang_code = target_lang_code
        
        # 文件数据列表
        self.files_data = []
        
        # 设置输出路径
        from scripts.app_settings import DEST_DIR
        self.output_root = os.path.join(DEST_DIR, output_folder_name)
        
        # CSV 文件名：中英混合，方便不同语言的用户识别
        # 中文+英文: 校对进度表 Proofreading Progress
        self.csv_filename = "校对进度表 Proofreading Progress.csv"
        
    def add_file_info(self, file_info: Dict[str, Any]):
        """
        添加文件信息到追踪列表
        
        Args:
            file_info: 包含文件信息的字典
        """
        self.files_data.append(file_info)
        
    def generate_csv_content(self, include_header: bool = True) -> str:
        """
        生成CSV格式的校对进度表格内容

        Args:
            include_header: 是否写入表头。若用于向已有 CSV 追加数据时，可设置为 False。

        Returns:
            str: CSV格式的校对进度表格内容
        """
        if not self.files_data:
            logging.warning(i18n.t("no_file_data_for_proofreading"))
            return ""
            
        # 按文件路径排序，确保表格有序
        sorted_files = sorted(self.files_data, key=lambda x: x.get('source_path', ''))
        
        # 使用csv模块生成标准CSV格式
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_ALL)
        
        # CSV 表头采用“中文 + English”形式，便于跨语言团队协作
        headers = [
            "状态 Status",
            "源文件 Source File",
            "本地化文件 Localized File",
            "已译行 Translated Lines",
            "校对进度 Proofreading Progress",  # 校对进度记录列
            "备注 Notes"
        ]

        # 若需要，写入标题行
        if include_header:
            writer.writerow(headers)
        
        # 添加数据行
        for file_info in sorted_files:
            source_path = file_info.get('source_path', '')
            dest_path = file_info.get('dest_path', '')
            translated_lines = file_info.get('translated_lines', 0)
            
            # 生成相对路径显示
            source_rel_path = self._get_relative_path_display(source_path)
            dest_rel_path = self._get_relative_path_display(dest_path)
            
            # 清理路径中的换行符
            source_rel_path_clean = source_rel_path.replace('\n', ' ').replace('\r', ' ')
            dest_rel_path_clean = dest_rel_path.replace('\n', ' ').replace('\r', ' ')
            
            # 写入CSV行：状态、源文件、本地化文件、翻译行数、校对进度、备注
            writer.writerow([
                file_info.get('status', ""),  # 状态
                source_rel_path_clean,        # 源文件
                dest_rel_path_clean,          # 本地化文件
                str(translated_lines),        # 翻译行数
                file_info.get('proofreading_progress', ""),  # 校对进度 (contains validation summary)
                file_info.get('proofreading_notes', "")      # 备注 (contains validation details)
            ])
        
        csv_content = output.getvalue()
        output.close()
        
        return csv_content
        
    def save_proofreading_progress(self) -> bool:
        """
        保存校对进度表格到CSV文件
        
        Returns:
            bool: 是否成功保存
        """
        try:
            # 确保输出目录存在
            os.makedirs(self.output_root, exist_ok=True)

            # 校验输出文件是否已存在，存在则改为追加模式
            output_file_path = os.path.join(self.output_root, self.csv_filename)
            file_exists = os.path.exists(output_file_path)

            # 生成CSV内容，若文件已存在则不再写入表头
            csv_content = self.generate_csv_content(include_header=not file_exists)
            if not csv_content:
                return False

            # 使用UTF-8 BOM编码保存，Excel 等软件能正确显示中文
            mode = "a" if file_exists else "w"
            with open(output_file_path, mode, encoding="utf-8-sig", newline='') as f:
                f.write(csv_content)

            logging.info(i18n.t("proofreading_table_generated", path=output_file_path))
            return True
            
        except Exception as e:
            logging.error(i18n.t("proofreading_table_generation_fail", error=str(e)))
            return False
            
    def _get_relative_path_display(self, full_path: str) -> str:
        """
        获取相对路径显示格式
        
        Args:
            full_path: 完整文件路径
            
        Returns:
            str: 相对路径显示字符串
        """
        if not full_path:
            return ""
            
        try:
            # 尝试相对于输出根目录的路径
            if full_path.startswith(self.output_root):
                rel_path = os.path.relpath(full_path, self.output_root)
                return rel_path
                
            # 如果是绝对路径，尝试相对于工作目录
            if os.path.isabs(full_path):
                rel_path = os.path.relpath(full_path, os.getcwd())
                return rel_path
                
            # 如果已经是相对路径，直接返回
            return full_path
            
        except Exception:
            # 如果路径处理失败，返回文件名
            return os.path.basename(full_path)
            
    def _get_current_time(self) -> str:
        """
        获取当前时间字符串
        
        Returns:
            str: 格式化的当前时间
        """
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def create_proofreading_tracker(mod_name: str, output_folder_name: str, target_lang_code: str = "zh-CN") -> ProofreadingTracker:
    """
    创建校对进度追踪器的工厂函数
    
    Args:
        mod_name: Mod名称
        output_folder_name: 输出文件夹名称
        target_lang_code: 目标语言代码，用于生成对应语言的表格
        
    Returns:
        ProofreadingTracker: 校对进度追踪器实例
    """
    return ProofreadingTracker(mod_name, output_folder_name, target_lang_code)
