# scripts/utils/post_process_validator.py
# ---------------------------------------------------------------
"""
后处理验证器 - 检查AI翻译后的文本格式是否符合游戏要求 (已重构)

这个模块负责在AI翻译完成后，对翻译结果进行格式验证，
确保所有游戏特定的语法结构都被正确保留。

核心设计：
- 纯粹的规则引擎，由外部Python模块驱动。
- BaseGameValidator 是通用引擎，不包含任何游戏专属逻辑。
- 子类 (e.g., Victoria3Validator) 仅负责提供其对应的Python规则文件路径。
- 所有检查逻辑都由通用的“工人”方法实现。
"""

import re
import logging
import importlib.util
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum

# 导入国际化支持
try:
    from . import i18n
    from ..utils import punctuation_handler
    from ..app_settings import LANGUAGES, GAME_PROFILES, GAME_ID_ALIASES
except ImportError:
    i18n = None
    punctuation_handler = None
    LANGUAGES = {}


class ValidationLevel(Enum):
    """验证级别枚举"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ValidationResult:
    """验证结果数据类"""
    is_valid: bool
    level: ValidationLevel
    message: str
    details: Optional[str] = None
    line_number: Optional[int] = None
    text_sample: Optional[str] = None
    key: Optional[str] = None  # Added key field


class BaseGameValidator:
    """
    游戏验证器基类 (重构为纯粹的规则引擎)。
    它从一个Python模块文件中加载所有验证规则，并根据这些规则动态地执行检查。
    """
    
    def __init__(self, rules_module_or_dict):
        """
        构造函数。

        Args:
            rules_module_or_dict: 包含RULES字典的Python模块对象，直接传入 RULES 字典。
        """
        self.logger = logging.getLogger(__name__)
        
        if isinstance(rules_module_or_dict, dict):
            self.config = rules_module_or_dict
        else:
            self.config = getattr(rules_module_or_dict, 'RULES', {})
            
        self.rules = self.config.get("rules", [])
        self.game_name = self.config.get("game_name", "Unknown Game")

        # 将字符串函数名映射到实际的“工人”检查方法
        self.check_map = {
            "banned_chars": self._check_banned_chars,
            "formatting_tags": self._check_formatting_tags,
            "mismatched_tags": self._check_mismatched_tags,
            "informational_pattern": self._check_informational_pattern,
            "variable_parity": self._check_variable_parity,
        }

    def _get_i18n_message(self, message_key: str, **kwargs) -> str:
        """
        获取国际化消息。如果失败，则直接返回消息键本身。
        这样可以消除对 fallback_messages 的依赖。
        """
        if not message_key:
            return ""
        try:
            if i18n and getattr(i18n, '_language_loaded', False):
                return i18n.t(message_key, **kwargs)
        except Exception:
            pass
        return message_key

    # --- "工人"检查方法 ---

    def _check_banned_chars(self, text: str, rule: Dict, line_number: Optional[int], **kwargs) -> List[ValidationResult]:
        """
        工人方法：根据'pattern'查找，并检查其捕获组内是否包含不允许的非ASCII字符。
        """
        results = []
        pattern = rule.get("pattern")
        params = rule.get("params", {})
        capture_group = params.get("capture_group", 1)

        if not pattern:
            return results

        try:
            matches = re.finditer(pattern, text)
            for match in matches:
                if len(match.groups()) >= capture_group:
                    content_to_check = match.group(capture_group)
                    # [FIX] Allow '£' (hex \xa3) character as it is used for icons in PDS games (HOI4, etc.)
                    banned_chars = re.findall(r'[^\x00-\x7F\xa3]', content_to_check)
                    if banned_chars:
                        details_str = "".join(sorted(list(set(banned_chars))))
                        # [FIX] Pass 'key' as content_to_check so i18n strings expecting {key} (like validation_vic3_tag_key_chinese) work.
                        message = self._get_i18n_message(rule["message_key"], key=content_to_check)
                        details_key = params.get("details_key", "validation_generic_banned_chars_found")
                        details = self._get_i18n_message(details_key, match_text=match.group(0), banned_chars=details_str, key_content=content_to_check, found_text=match.group(0))
                        results.append(ValidationResult(
                            is_valid=False,
                            level=ValidationLevel(rule["level"]),
                            message=message,
                            details=details,
                            line_number=line_number,
                            text_sample=text[:100]
                        ))
        except re.error as e:
            self.logger.warning(self._get_i18n_message("validator_error_regex_error", rule_name=rule['name'], e=e, pattern=pattern))
        return results

    def _check_formatting_tags(self, text: str, rule: Dict, line_number: Optional[int], **kwargs) -> List[ValidationResult]:
        """
        工人方法：检查格式化标签，如V3的 #tag。
        它从 rule['params'] 中动态读取所有配置。
        支持从 kwargs 动态传入 valid_tags 列表以覆盖规则文件中的设置。
        """
        results = []
        pattern = rule.get("pattern")
        params = rule.get("params", {})

        # 核心改造：优先使用动态传入的标签列表
        dynamic_tags = kwargs.get("dynamic_valid_tags")
        if dynamic_tags is not None:
            valid_tags = set(tag.lower() for tag in dynamic_tags)
        else:
            valid_tags = set(tag.lower() for tag in params.get("valid_tags", []))

        no_space_required_tags = set(tag.lower() for tag in params.get("no_space_required_tags", []))

        if not pattern or not valid_tags:
            return results

        try:
            matches = re.finditer(pattern, text)
            for match in matches:
                tag_found = match.group(1)
                normalized_tag = tag_found.lower()
                if normalized_tag not in valid_tags:
                    message = self._get_i18n_message(params["unknown_tag_error_key"], key=tag_found)
                    details = self._get_i18n_message(params["unsupported_formatting_details_key"], found_text=match.group(0))
                    results.append(ValidationResult(is_valid=False, level=ValidationLevel(rule["level"]), message=message, details=details, line_number=line_number, text_sample=text[:100]))
                elif normalized_tag not in no_space_required_tags:
                    next_char_pos = match.end()
                    if next_char_pos < len(text) and text[next_char_pos] not in (' ', '#', '!', ';'):
                        message = self._get_i18n_message(rule["message_key"], key=tag_found)
                        details = self._get_i18n_message(params["missing_space_details_key"], found_text=match.group(0))
                        results.append(ValidationResult(is_valid=False, level=ValidationLevel(rule["level"]), message=message, details=details, line_number=line_number, text_sample=text[:100]))
        except re.error as e:
            self.logger.warning(self._get_i18n_message("validator_error_regex_error", rule_name=rule['name'], e=e, pattern=pattern))
        return results

    def _check_mismatched_tags(self, text: str, rule: Dict, line_number: Optional[int], **kwargs) -> List[ValidationResult]:
        """
        工人方法：一个强大的通用方法，用于检查所有游戏中不成对的标签。
        它从 rule['params'] 中读取 start_tag_pattern 和 end_tag_string。
        """
        results = []
        params = rule.get("params", {})
        start_tag_pattern = params.get("start_tag_pattern")
        end_tag_string = params.get("end_tag_string")

        if not start_tag_pattern or not end_tag_string:
            return results

        try:
            start_tags_count = len(re.findall(start_tag_pattern, text))
            end_tags_count = text.count(end_tag_string)
            if start_tags_count != end_tags_count:
                message = self._get_i18n_message(rule["message_key"])
                details_key = params.get("details_key", "validation_generic_tags_count")
                details = self._get_i18n_message(details_key, start_count=start_tags_count, end_count=end_tags_count)
                results.append(ValidationResult(is_valid=False, level=ValidationLevel(rule["level"]), message=message, details=details, line_number=line_number, text_sample=text[:100]))
        except re.error as e:
            self.logger.warning(self._get_i18n_message("validator_error_regex_error", rule_name=rule['name'], e=e, pattern=start_tag_pattern))
        return results
        
    def _check_informational_pattern(self, text: str, rule: Dict, line_number: Optional[int], **kwargs) -> List[ValidationResult]:
        """
        工人方法：检查一个模式是否存在，并发出一个信息性（非错误）的提示。
        """
        results = []
        pattern = rule.get("pattern")
        if not pattern: return results
        if re.search(pattern, text):
            message = self._get_i18n_message(rule["message_key"])
            details = self._get_i18n_message(rule.get("params", {}).get("details_key", ""))
            results.append(ValidationResult(is_valid=True, level=ValidationLevel(rule["level"]), message=message, details=details, line_number=line_number, text_sample=text[:100]))
        return results

    def _check_variable_parity(self, text: str, rule: Dict, line_number: Optional[int], source_text: Optional[str] = None, **kwargs) -> List[ValidationResult]:
        """
        工人方法：检查变量在原文和译文中的数量是否一致（绝对一致性校验/Parity Check）。
        需要 rule['params']['patterns'] 提供一个正则表达式列表。
        """
        results = []
        if not source_text:
            return results
            
        params = rule.get("params", {})
        patterns = params.get("patterns", [])
        
        if not patterns:
            return results
            
        from collections import Counter
            
        for pattern in patterns:
            try:
                # 寻找原文和译文中的所有匹配项
                source_vars = re.findall(pattern, source_text)
                target_vars = re.findall(pattern, text)
                
                if not source_vars and not target_vars:
                    continue
                    
                source_counts = Counter(source_vars)
                target_counts = Counter(target_vars)
                
                # 检查所有在原文中出现的变量
                for var, count in source_counts.items():
                    target_count = target_counts.get(var, 0)
                    if target_count != count:
                        # 发现不匹配！
                        message_key = rule.get("message_key", "validation_variable_parity_mismatch")
                        message = self._get_i18n_message(message_key, var=var)
                        
                        if message == message_key:
                            message = f"变量数量不一致 (Variable parity mismatch): {var}"
                            
                        details_key = params.get("details_key", "validation_generic_parity_mismatch")
                        details = self._get_i18n_message(details_key, var=var, source_count=count, target_count=target_count)
                        if details == details_key:
                            details = f"原文含有 {count} 个，译文含有 {target_count} 个 (Expected {count}, found {target_count})"
                            
                        results.append(ValidationResult(
                            is_valid=False,
                            level=ValidationLevel(rule["level"]),
                            message=message,
                            details=details,
                            line_number=line_number,
                            text_sample=text[:100]
                        ))
                
                # 检查是否在译文中凭空多出了原文没有的变量（LLM幻觉）
                for var, count in target_counts.items():
                    if var not in source_counts:
                        message_key = rule.get("message_key", "validation_variable_parity_mismatch")
                        message = self._get_i18n_message(message_key, var=var)
                        
                        if message == message_key:
                            message = f"多出未知变量 (Unexpected extra variable): {var}"
                            
                        details_key = params.get("details_key", "validation_generic_parity_mismatch")
                        details = self._get_i18n_message(details_key, var=var, source_count=0, target_count=count)
                        if details == details_key:
                            details = f"原文含有 0 个，译文含有 {count} 个 (Expected 0, found {count})"
                            
                        results.append(ValidationResult(
                            is_valid=False,
                            level=ValidationLevel(rule["level"]),
                            message=message,
                            details=details,
                            line_number=line_number,
                            text_sample=text[:100]
                        ))
            except re.error as e:
                self.logger.warning(self._get_i18n_message("validator_error_regex_error", rule_name=rule.get('name', 'N/A'), e=e, pattern=pattern))
                
        return results


    def _check_residual_punctuation(self, text: str, line_number: Optional[int], source_lang: Optional[Dict] = None, target_lang: Optional[str] = None) -> List[ValidationResult]:
        """
        工人方法：检查翻译后的文本中是否还残留着源语言的标点符号。
        这是一个内置的基础检查，适用于所有游戏。
        """
        results = []

        # 如果没有动态传入 source_lang，则尝试从配置中获取，最后回退到中文
        if source_lang and source_lang.get("code"):
            source_lang_code = source_lang.get("code")
        else:
            source_lang_code = self.config.get("source_language_code", "zh-CN")

        if not punctuation_handler or not source_lang_code:
            return results

        analysis = punctuation_handler.analyze_punctuation(text, source_lang_code)

        if analysis.get("found"):
            # --- [精细化过滤] ---
            # 如果提供了目标语言，且找到的标点符号实际上也存在于目标语言的合法集合中，则不应报错
            if target_lang:
                target_punctuation_map = punctuation_handler.get_source_language_punctuation(target_lang)
                if target_punctuation_map:
                    # 只保留那些不在目标语言合法集合中的标点
                    filtered_details = {p: v for p, v in analysis['details'].items() if p not in target_punctuation_map}
                    if not filtered_details:
                        return results # 所有发现的标点在目标语言中都是合法的
                    
                    analysis['details'] = filtered_details
                    analysis['total'] = sum(v['count'] for v in filtered_details.values())

            # 找到了真正的残留标点符号
            found_punctuations = ", ".join(analysis.get("details", {}).keys())
            message = self._get_i18n_message("validation_residual_punctuation_found")
            details = self._get_i18n_message(
                "validation_residual_punctuation_details",
                punctuations=found_punctuations
            )
            results.append(ValidationResult(
                is_valid=False,
                level=ValidationLevel.WARNING,
                message=message,
                details=details,
                line_number=line_number,
                text_sample=text[:100]
            ))
        return results

    def _check_key_format(self, key: str, line_number: Optional[int]) -> List[ValidationResult]:
        """
        检查键名格式。
        目前只检查是否包含空格或非法字符。
        """
        results = []
        if not key:
            return results
            
        # 简单的键名检查：只允许字母、数字、下划线、点、冒号(某些游戏允许?)
        # 通常P社键名是 alphanumeric + underscore + dot
        if not re.match(r'^[a-zA-Z0-9_\.]+$', key):
             # 暂时只作为 Warning，因为有些Mod可能有奇怪的键名
            message = "Invalid key format"
            details = f"Key '{key}' contains invalid characters. Expected alphanumeric, underscore, or dot."
            results.append(ValidationResult(
                is_valid=False,
                level=ValidationLevel.WARNING,
                message=message,
                details=details,
                line_number=line_number,
                text_sample=key,
                key=key
            ))
        return results

    def validate_text(self, text: str, line_number: Optional[int] = None, source_lang: Optional[Dict] = None, source_text: Optional[str] = None, target_lang: Optional[str] = None, **kwargs) -> List[ValidationResult]:
        """
        纯粹的规则执行引擎。
        它遍历加载自Python模块的规则，并根据 rule['check_function'] 的值，
        从 self.check_map 中动态调用相应的“工人”检查方法。
        增加了内置的标点符号检查。
        现在可以接受并传递 **kwargs 和 source_text 给工人方法。
        """
        all_results = []
        if not self.rules and not self.config: # 如果规则加载失败，则直接返回
            return all_results

        for rule in self.rules:
            check_function_name = rule.get("check_function")
            checker = self.check_map.get(check_function_name)
            if checker:
                try:
                    # 将 kwargs 和 source_text 传递给工人方法
                    results = checker(text, rule, line_number, source_text=source_text, target_lang=target_lang, **kwargs)
                    all_results.extend(results)
                except Exception as e:
                    self.logger.error(self._get_i18n_message("validator_error_executing_rule", rule_name=rule.get('name', 'N/A'), e=e))
            else:
                self.logger.warning(self._get_i18n_message("validator_warning_unknown_check_function", rule_name=rule.get('name', 'N/A'), check_function_name=check_function_name))

        # --- 内置基础检查 ---
        # 传递 target_lang 给标点符号检查
        punctuation_results = self._check_residual_punctuation(text, line_number, source_lang, target_lang=target_lang)
        all_results.extend(punctuation_results)

        return all_results
    
    def validate_entry(self, key: str, value: str, line_number: Optional[int] = None, source_lang: Optional[Dict] = None, source_value: Optional[str] = None, target_lang: Optional[str] = None, **kwargs) -> List[ValidationResult]:
        """
        验证单个键值对。
        先验证键，再验证值。
        """
        results = []
        
        # 1. 验证键
        key_results = self._check_key_format(key, line_number)
        results.extend(key_results)
        
        # 2. 验证值，将 source_value 作为 source_text 传递
        value_results = self.validate_text(value, line_number, source_lang, source_text=source_value, target_lang=target_lang, **kwargs)
        # 为值验证结果添加 key 信息
        for res in value_results:
            res.key = key
        results.extend(value_results)
        
        return results

    def _log_validation_result(self, result: ValidationResult):
        """记录验证结果到日志"""
        log_level = getattr(self.logger, result.level.value, self.logger.info)
        message = f"[{self.game_name}] {result.message}"
        if result.key:
            message = f"[Key: {result.key}] " + message
        if result.details:
            message += f" - {self._get_i18n_message('validation_details')}: {result.details}"
        log_level(message)

# --- 静态导入规则模块 ---
try:
    from scripts.config.validators import vic3_rules, stellaris_rules, eu4_rules, hoi4_rules, ck3_rules, eu5_rules
except ImportError:
    # 兼容直接运行此文件作为脚本时的导入路径
    try:
        from ..config.validators import vic3_rules, stellaris_rules, eu4_rules, hoi4_rules, ck3_rules, eu5_rules
    except ImportError:
        vic3_rules = stellaris_rules = eu4_rules = hoi4_rules = ck3_rules = eu5_rules = None

# --- 子类定义 ---
class Victoria3Validator(BaseGameValidator):
    def __init__(self):
        super().__init__(vic3_rules)

class StellarisValidator(BaseGameValidator):
    def __init__(self):
        super().__init__(stellaris_rules)

class EU4Validator(BaseGameValidator):
    def __init__(self):
        super().__init__(eu4_rules)

class HOI4Validator(BaseGameValidator):
    def __init__(self):
        super().__init__(hoi4_rules)

class CK3Validator(BaseGameValidator):
    def __init__(self):
        super().__init__(ck3_rules)

class EU5Validator(BaseGameValidator):
    def __init__(self):
        super().__init__(eu5_rules)


class PostProcessValidator:
    """后处理验证器主类"""
    def __init__(self):
        self.validators_by_id_str = {
            "victoria3": Victoria3Validator(),
            "stellaris": StellarisValidator(),
            "eu4": EU4Validator(),
            "hoi4": HOI4Validator(),
            "ck3": CK3Validator(),
            "eu5": EU5Validator()
        }

        # 最终的、按数字键（如'1'）索引的验证器字典
        self.validators: Dict[str, BaseGameValidator] = {}
        if GAME_PROFILES:
            for numeric_key, profile in GAME_PROFILES.items():
                game_id_str = profile.get("id")
                if game_id_str and game_id_str in self.validators_by_id_str:
                    self.validators[numeric_key] = self.validators_by_id_str[game_id_str]

        self.logger = logging.getLogger(__name__)
        if i18n and not getattr(i18n, '_language_loaded', False):
            try:
                i18n.load_language()
            except Exception as e:
                self.logger.warning(self._get_i18n_message("validator_warning_cannot_load_i18n", e=e))
    
    def get_validator_by_game_id(self, game_id: str) -> Optional[BaseGameValidator]:
        """根据数字游戏ID（如 "1"）或内部字母ID（如 "victoria3"）查找验证器实例。如果找不到，抛出 ValueError。"""
        from scripts.app_settings import GAME_ID_ALIASES, SupportedGame
        
        # Resolve aliases (e.g., 'vic3' -> 'victoria3')
        original_game_id = game_id
        if GAME_ID_ALIASES and game_id in GAME_ID_ALIASES:
            game_id = GAME_ID_ALIASES[game_id]
            
        validator = self.validators.get(game_id)
        if not validator:
            validator = self.validators_by_id_str.get(game_id)
            
        if not validator:
            # DEFENSIVE PROGRAMMING: Fail Loudly
            supported = [g.value for g in SupportedGame]
            error_msg = f"Unsupported game_id: '{original_game_id}'. Resolved to '{game_id}'. Supported games are: {supported}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
            
        return validator

    def validate_game_text(self, game_id: str, text: str, line_number: Optional[int] = None, source_lang: Optional[Dict] = None, source_text: Optional[str] = None, target_lang: Optional[str] = None, dynamic_valid_tags: Optional[List[str]] = None) -> List[ValidationResult]:
        """验证指定游戏的文本格式"""
        try:
            validator = self.get_validator_by_game_id(game_id)
        except ValueError as e:
            self.logger.error(self._get_i18n_message("validation_unknown_game", game_id=game_id))
            raise e
            
        # 将 dynamic_valid_tags 和 source_text 通过 kwargs 传递下去
        results = validator.validate_text(text, line_number, source_lang, source_text=source_text, target_lang=target_lang, dynamic_valid_tags=dynamic_valid_tags)
        for result in results:
            validator._log_validation_result(result)
        return results
    
    def validate_entry(self, game_id: str, key: str, value: str, line_number: Optional[int] = None, source_lang: Optional[Dict] = None, source_value: Optional[str] = None, target_lang: Optional[str] = None, dynamic_valid_tags: Optional[List[str]] = None) -> List[ValidationResult]:
        """验证单个键值对"""
        try:
            validator = self.get_validator_by_game_id(game_id)
        except ValueError as e:
            self.logger.error(self._get_i18n_message("validation_unknown_game", game_id=game_id))
            raise e
            
        results = validator.validate_entry(key, value, line_number, source_lang, source_value=source_value, target_lang=target_lang, dynamic_valid_tags=dynamic_valid_tags)
        for result in results:
            validator._log_validation_result(result)
        return results

    def validate_batch(self, game_id: str, texts: List[str], start_line: int = 1, source_lang: Optional[Dict] = None, source_texts: Optional[List[str]] = None, target_lang: Optional[str] = None, dynamic_valid_tags: Optional[List[str]] = None) -> Dict[int, List[ValidationResult]]:
        """批量验证文本"""
        batch_results = {}
        try:
            validator = self.get_validator_by_game_id(game_id)
        except ValueError as e:
            self.logger.error(self._get_i18n_message("validation_unknown_game", game_id=game_id))
            raise e
            
        for i, text in enumerate(texts):
            line_number = start_line + i
            src_text = source_texts[i] if source_texts and i < len(source_texts) else None
            # 将 dynamic_valid_tags 和 source_text 通过 kwargs 传递下去
            results = validator.validate_text(text, line_number, source_lang, source_text=src_text, target_lang=target_lang, dynamic_valid_tags=dynamic_valid_tags)
            if results:
                batch_results[line_number] = results
        self.log_validation_summary(batch_results, validator.game_name)
        return batch_results

    def get_validation_summary(self, batch_results: Dict[int, List[ValidationResult]]) -> Dict[str, int]:
        """获取验证结果摘要"""
        summary = {"errors": 0, "warnings": 0, "info": 0}
        for line_results in batch_results.values():
            for result in line_results:
                level_str = result.level.value + "s"
                if level_str in summary:
                    summary[level_str] += 1
        return summary
    
    def log_validation_summary(self, batch_results: Dict[int, List[ValidationResult]], game_name: str = ""):
        """记录验证结果摘要到日志"""
        summary = self.get_validation_summary(batch_results)
        errors, warnings = summary.get("errors", 0), summary.get("warnings", 0)
        if errors > 0:
            self.logger.error(self._get_i18n_message("validation_summary_errors", game_name=game_name, errors=errors, warnings=warnings))
        elif warnings > 0:
            self.logger.warning(self._get_i18n_message("validation_summary_warnings", game_name=game_name, warnings=warnings))
        else:
            self.logger.info(self._get_i18n_message("validation_summary_success", game_name=game_name))

    def _get_i18n_message(self, message_key: str, **kwargs) -> str:
        """PostProcessValidator也需要一个i18n消息获取器"""
        if not message_key: return ""
        try:
            if i18n and getattr(i18n, '_language_loaded', False):
                return i18n.t(message_key, **kwargs)
        except Exception:
            pass
        return message_key

def validate_text(game_id: str, text: str, line_number: Optional[int] = None, source_lang: Optional[Dict] = None, source_text: Optional[str] = None, target_lang: Optional[str] = None, dynamic_valid_tags: Optional[List[str]] = None) -> List[ValidationResult]:
    validator = PostProcessValidator()
    return validator.validate_game_text(game_id, text, line_number, source_lang=source_lang, source_text=source_text, target_lang=target_lang, dynamic_valid_tags=dynamic_valid_tags)

def validate_entry(game_id: str, key: str, value: str, line_number: Optional[int] = None, source_lang: Optional[Dict] = None, source_value: Optional[str] = None, target_lang: Optional[str] = None, dynamic_valid_tags: Optional[List[str]] = None) -> List[ValidationResult]:
    validator = PostProcessValidator()
    return validator.validate_entry(game_id, key, value, line_number, source_lang=source_lang, source_value=source_value, target_lang=target_lang, dynamic_valid_tags=dynamic_valid_tags)

def validate_batch(game_id: str, texts: List[str], start_line: int = 1, source_lang: Optional[Dict] = None, source_texts: Optional[List[str]] = None, target_lang: Optional[str] = None, dynamic_valid_tags: Optional[List[str]] = None) -> Dict[int, List[ValidationResult]]:
    validator = PostProcessValidator()
    return validator.validate_batch(game_id, texts, start_line, source_lang=source_lang, source_texts=source_texts, target_lang=target_lang, dynamic_valid_tags=dynamic_valid_tags)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    try:
        main_validator = PostProcessValidator()
        print("\n--- Testing Stellaris Validator ---")
        main_validator.validate_game_text("2", "This has mismatched §Ycolor§!", 2)
        main_validator.validate_game_text("2", "This has a bad variable $中文变量$ inside.", 3)
        print("\n--- Testing Victoria 3 Validator ---")
        # Test with dynamic tags
        main_validator.validate_game_text("1", "This has #custom_tag now.", 4, dynamic_valid_tags=["custom_tag"])
        main_validator.validate_game_text("1", "This has a [中文概念].", 5)
        # Test Parity Match Check
        res = main_validator.validate_game_text("1", "Translation without variable.", source_text="This has a $pop$ variable.", line_number=6)
        print(f"Parity Check (expected fail): {res[0].message if res else 'Passed (error!)'} - {res[0].details if res else ''}")
        res2 = main_validator.validate_game_text("1", "Translation with $pop$ extra $pop$.", source_text="This has a $pop$ variable.", line_number=7)
        print(f"Parity Check (extra var): {res2[0].message if res2 else 'Passed (error!)'} - {res2[0].details if res2 else ''}")

        print("\n--- Testing CK3 Validator (New Rule) ---")
        main_validator.validate_game_text("5", "This contains a #totally_fake_command that should be caught.", 6)
        # Test dynamic tag override for CK3
        main_validator.validate_game_text("5", "This #totally_fake_command is now valid.", 7, dynamic_valid_tags=["totally_fake_command"])
        
        print("\n--- Testing Key Validation ---")
        main_validator.validate_entry("1", "valid_key", "Valid value")
        main_validator.validate_entry("1", "invalid key with spaces", "Value")
        
    except Exception as e:
        print(f"An error occurred during testing: {e}")
        print("Please ensure all Python rule files are present and correctly formatted.")
