from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class FileTask:
    """文件任务数据结构"""
    filename: str
    root: str
    original_lines: List[str]
    texts_to_translate: List[str]
    key_map: Dict[str, Any]
    is_custom_loc: bool
    target_lang: Dict[str, Any]
    source_lang: Dict[str, Any]
    game_profile: Dict[str, Any]
    mod_context: str
    provider_name: str
    output_folder_name: str
    source_dir: str
    dest_dir: str
    client: Any  # API客户端
    mod_name: str  # 添加mod_name字段
    loc_root: str = "" # Localization root path (e.g. mod/main_menu/localization)


@dataclass
class BatchTask:
    """批次任务数据结构"""
    file_task: FileTask
    batch_index: int
    start_index: int
    end_index: int
    texts: List[str]
    translated_texts: Optional[List[str]] = field(default=None, init=False)
    failed: bool = field(default=False, init=False)
    fell_back_to_source: bool = field(default=False, init=False)
    warnings: List[Dict[str, Any]] = field(default_factory=list, init=False)
