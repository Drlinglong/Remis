from enum import Enum
from pydantic import BaseModel, Field, field_validator
from typing import Optional

class LanguageCode(str, Enum):
    """ISO 639-1 代码 - 这是数据库存储的唯一合法格式"""
    EN = "en"
    ZH_CN = "zh-CN"
    FR = "fr"
    DE = "de"
    ES = "es"
    JA = "ja"
    KO = "ko"
    PL = "pl"
    PT_BR = "pt-BR"
    RU = "ru"
    TR = "tr"
    CUSTOM = "custom"

    @classmethod
    def from_str(cls, value: str):
        """
        强力清洗器：能把 'English', 'english', 'l_english' 统统自动转成 'en'。
        """
        if not value:
            raise ValueError("语言代码不能为空")
            
        value = value.lower().strip()
        # 别名映射表
        mapping = {
            # English
            "english": cls.EN, "l_english": cls.EN, "en_us": cls.EN, "en": cls.EN,
            # Chinese
            "chinese": cls.ZH_CN, "simp_chinese": cls.ZH_CN, "l_simp_chinese": cls.ZH_CN, "zh": cls.ZH_CN, "zh_cn": cls.ZH_CN, "zh-cn": cls.ZH_CN,
            # French
            "french": cls.FR, "l_french": cls.FR, "fr": cls.FR,
            # German
            "german": cls.DE, "l_german": cls.DE, "de": cls.DE,
            # Spanish
            "spanish": cls.ES, "l_spanish": cls.ES, "es": cls.ES,
            # Japanese
            "japanese": cls.JA, "l_japanese": cls.JA, "ja": cls.JA,
            # Korean
            "korean": cls.KO, "l_korean": cls.KO, "ko": cls.KO,
            # Polish
            "polish": cls.PL, "l_polish": cls.PL, "pl": cls.PL,
            # Portuguese
            "braz_por": cls.PT_BR, "l_braz_por": cls.PT_BR, "pt": cls.PT_BR, "pt_br": cls.PT_BR, "pt-br": cls.PT_BR, "portuguese": cls.PT_BR,
            # Russian
            "russian": cls.RU, "l_russian": cls.RU, "ru": cls.RU,
            # Turkish
            "turkish": cls.TR, "l_turkish": cls.TR, "tr": cls.TR,
        }
        
        if value in mapping:
            return mapping[value]
            
        # 兜底：尝试直接匹配枚举值
        try:
            return cls(value)
        except ValueError:
            # 再次尝试匹配 value (case-insensitive check against enum values)
            for member in cls:
                if member.value.lower() == value:
                    return member
            raise ValueError(f"不支持的语言代码: {value}")
            
    def to_paradox(self) -> str:
        """
        转换为 P社游戏使用的语言字符串 (e.g. 'en' -> 'english', 'zh-CN' -> 'simp_chinese')
        """
        mapping = {
            self.EN: "english",
            self.ZH_CN: "simp_chinese",
            self.FR: "french",
            self.DE: "german",
            self.ES: "spanish",
            self.JA: "japanese",
            self.KO: "korean",
            self.PL: "polish",
            self.PT_BR: "braz_por",
            self.RU: "russian",
            self.TR: "turkish"
        }
        return mapping.get(self, "english") # Default to english

class GameType(str, Enum):
    """
    Standard Game IDs (ISO-like internal IDs)
    """
    STELLARIS = "stellaris"
    HOI4 = "hoi4"
    VIC3 = "vic3"
    CK3 = "ck3"
    EU4 = "eu4"
    
    @classmethod
    def from_str(cls, value: str):
        if not value: return cls.STELLARIS
        value = value.lower().strip()
        mapping = {
            "stellaris": cls.STELLARIS,
            "hearts of iron iv": cls.HOI4, "hoi4": cls.HOI4,
            "victoria 3": cls.VIC3, "victoria3": cls.VIC3, "vic3": cls.VIC3,
            "crusader kings iii": cls.CK3, "ck3": cls.CK3,
            "europa universalis iv": cls.EU4, "eu4": cls.EU4
        }
        return mapping.get(value, cls.STELLARIS)
        
    def to_paradox(self) -> str:
        """
        Usually Paradox just uses lowercase internal IDs too, but sometimes full names for display?
        The folder structure usually matches the internal ID or specific mod paths.
        Here we map to the 'Standard ID' expected by our Frontend Selects (e.g. 'vic3').
        """
        return self.value

class ProjectID(str):
    """
    类型别名：明确指示这个字符串必须是文件夹名 (ID)，绝不能是显示名称。
    """
    pass
