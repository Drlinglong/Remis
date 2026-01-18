# scripts/core/gemini_cli_handler.py
import os
import logging
import tempfile
import subprocess
import time
from typing import Any

from scripts.core.base_handler import BaseApiHandler
from scripts.app_settings import API_PROVIDERS, GEMINI_CLI_MAX_RETRIES
from scripts.utils import i18n
from scripts.core.parallel_processor import BatchTask
from scripts.utils.structured_parser import parse_response
from scripts.core.glossary_manager import glossary_manager
from scripts.app_settings import FALLBACK_FORMAT_PROMPT
from scripts.utils.punctuation_handler import generate_punctuation_prompt
import locale


def robust_decode(byte_string: bytes) -> str:
    """
    一个健壮的、三层防御的解码函数，用于处理来自子进程的未知编码输出。
    """
    # 策略一：乐观尝试UTF-8。使用'utf-8-sig'可以自动处理带BOM的UTF-8文件。
    try:
        return byte_string.decode('utf-8-sig')
    except UnicodeDecodeError:
        pass # 如果失败，则继续尝试下一个策略

    # 策略二：谨慎回退到操作系统的首选本地编码。这是最通用的国际化方案。
    try:
        # locale.getpreferredencoding(False) 会动态获取系统的默认编码
        # 例如，中文系统是 'cp936'，日文系统是 'cp932'
        fallback_encoding = locale.getpreferredencoding(False)
        if fallback_encoding:
            return byte_string.decode(fallback_encoding)
    except (UnicodeDecodeError, TypeError): # TypeError防止fallback_encoding为None
        pass # 如果再次失败，则使用最终方案

    # 策略三：绝不崩溃。使用'replace'错误处理程序来标出错误位置。
    return byte_string.decode('utf-8', errors='replace')


class GeminiCLIHandler(BaseApiHandler):
    """
    Gemini CLI Handler子类。
    特殊之处在于它重写了父类的核心工作流方法 (`translate_batch` 和 `translate_single_text`)，
    因为它依赖于命令行子进程而不是直接的API SDK调用。
    """

    def __init__(self, provider_name: str, model_name: str = None):
        self.model_override = model_name
        super().__init__(provider_name, model_id=model_name)

    def initialize_client(self) -> Any:
        provider_config = self.get_provider_config()
        self.model = self.model_override or provider_config.get("default_model", "gemini-2.5-flash")
        self.cli_path = provider_config.get("cli_path", "gemini")
        self._verify_cli_availability()
        self.logger.info(f"Gemini CLI handler initialized. Path: {self.cli_path}, Model: {self.model}")
        return self

    def _verify_cli_availability(self):
        try:
            # Check version with a short timeout. It should be instant.
            # Added -NoProfile to avoid loading user profile which might be slow
            cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", f"{self.cli_path} --version"]
            kwargs = { "capture_output": True, "text": True, "timeout": 5 }
            if os.name == 'nt':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            result = subprocess.run(cmd, **kwargs)
            
            if result.returncode != 0:
                raise RuntimeError(f"Gemini CLI version check failed: {result.stderr}")
                
            self.logger.info(i18n.t("gemini_cli_available", version=result.stdout.strip()))
            
        except subprocess.TimeoutExpired:
            error_msg = i18n.t("gemini_cli_timeout", default="Gemini CLI check timed out (5s). Please check internet or switch to API mode.")
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)
            
        except FileNotFoundError:
            self.logger.error(i18n.t("gemini_cli_not_found", cli_path=self.cli_path))
            raise
            
        except Exception as e:
            self.logger.exception(f"An unexpected error occurred during Gemini CLI availability check: {e}")
            raise

    def _call_api(self, client: Any, prompt: str) -> str:
        # 因为工作流被重写，此方法永远不会被调用。
        # 提供一个虚拟实现以满足抽象基类的要求。
        self.logger.warning("`_call_api` should not be called on GeminiCLIHandler.")
        pass

    def _build_prompt(self, task: BatchTask) -> str:
        """
        【独有实现】重写prompt构建逻辑，将词典指令前置以提高CLI兼容性。
        """
        chunk = task.texts
        source_lang = task.file_task.source_lang
        target_lang = task.file_task.target_lang
        game_profile = task.file_task.game_profile
        mod_context = task.file_task.mod_context
        batch_num = task.batch_index + 1

        numbered_list = "\n".join(f'{j + 1}. "{txt}"' for j, txt in enumerate(chunk))

        # For Gemini CLI, we prioritize using the English name ('name_en') to prevent encoding issues
        # with the CLI process, while still respecting the override logic for 'is_shell' and 'custom_name'.
        default_lang_name = target_lang.get("name_en", target_lang["name"])
        effective_target_lang_name = target_lang.get("custom_name", default_lang_name) if target_lang.get("is_shell") else default_lang_name

        base_prompt = game_profile["prompt_template"].format(
            source_lang_name=source_lang["name"],
            target_lang_name=effective_target_lang_name,
        )
        context_prompt_part = (
            f"CRITICAL CONTEXT: The mod you are translating is '{mod_context}'. "
            "Use this information to ensure all translations are thematically appropriate.\n"
        )

        glossary_prompt_part = ""
        if glossary_manager.get_glossary_for_translation():
            relevant_terms = glossary_manager.extract_relevant_terms(
                chunk, source_lang["code"], target_lang["code"]
            )
            if relevant_terms:
                glossary_prompt_part = glossary_manager.create_dynamic_glossary_prompt(
                    relevant_terms, source_lang["code"], target_lang["code"]
                ) + "\n\n"
                self.logger.info(i18n.t("batch_translation_glossary_injected", batch_num=batch_num, count=len(relevant_terms)))

        punctuation_prompt = generate_punctuation_prompt(
            source_lang["code"],
            target_lang["code"]
        )

        if "format_prompt" in game_profile:
            format_prompt_part = game_profile["format_prompt"].format(
                chunk_size=len(chunk),
                numbered_list=numbered_list
            )
        else:
            format_prompt_part = FALLBACK_FORMAT_PROMPT.format(
                chunk_size=len(chunk),
                numbered_list=numbered_list
            )

        punctuation_prompt_part = f"\nPUNCTUATION CONVERSION:\n{punctuation_prompt}\n" if punctuation_prompt else ""

        # 将词典指令放在最前面
        prompt = glossary_prompt_part + base_prompt + context_prompt_part + format_prompt_part + punctuation_prompt_part
        return prompt

    def translate_batch(self, task: BatchTask) -> BatchTask:
        """
        【独有实现】重写整个翻译工作流，使用子进程和PowerShell管道与Gemini CLI交互。
        """
        prompt = self._build_prompt(task)
        batch_num = task.batch_index + 1
        start_time = time.time()

        for attempt in range(GEMINI_CLI_MAX_RETRIES):
            try:
                # Use 'utf-8-sig' to write a BOM, which is the most reliable way to signal UTF-8 encoding on Windows.
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8-sig') as f:
                    f.write(prompt)
                    temp_file = f.name

                try:
                    gemini_command = f"{self.cli_path} --model {self.model} --output-format json"
                    # BOM file ensures Get-Content reads correctly; $OutputEncoding ensures the pipe to CLI is UTF-8.
                    full_command = (
                        f"$OutputEncoding = [System.Text.Encoding]::UTF8; "
                        f"Set-ExecutionPolicy RemoteSigned -Scope Process -Force; "
                        f"Get-Content -Path '{temp_file}' -Raw | {gemini_command}"
                    )
                    cmd = ["powershell", "-NoProfile", "-Command", full_command]

                    clean_env = {
                        'PATH': os.environ.get('PATH', ''), 'SYSTEMROOT': os.environ.get('SYSTEMROOT', ''),
                        'TEMP': os.environ.get('TEMP', ''), 'TMP': os.environ.get('TMP', ''),
                        'USERPROFILE': os.environ.get('USERPROFILE', ''), 'APPDATA': os.environ.get('APPDATA', ''),
                        'LOCALAPPDATA': os.environ.get('LOCALAPPDATA', ''), 'PROGRAMDATA': os.environ.get('PROGRAMDATA', ''),
                        'WINDIR': os.environ.get('WINDIR', ''), 'COMSPEC': os.environ.get('COMSPEC', ''),
                        'PATHEXT': os.environ.get('PATHEXT', ''), 'PSModulePath': os.environ.get('PSModulePath', ''),
                        'GEMINI_API_KEY': '',
                    }

                    kwargs = {
                        "capture_output": True, "timeout": 300, "env": clean_env
                    }
                    if os.name == 'nt':
                        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

                    result = subprocess.run(cmd, **kwargs)
                finally:
                    os.unlink(temp_file)

                # 使用我们新的、健壮的解码函数
                stdout_str = robust_decode(result.stdout)
                stderr_str = robust_decode(result.stderr)

                if result.returncode == 0:
                    parsed_model = parse_response(stdout_str)

                    # New success check: model is valid and the translation list length matches.
                    if parsed_model and len(parsed_model.translations) == len(task.texts):
                        task.translated_texts = parsed_model.translations
                        elapsed_time = time.time() - start_time
                        self.logger.info(i18n.t("gemini_cli_batch_success", batch_num=batch_num, attempt=attempt + 1, elapsed_time=elapsed_time))
                        return task
                    else:
                        # Log failure with more context if parsing returned a model but with wrong item count
                        log_msg = f"Expected {len(task.texts)}, got {len(parsed_model.translations) if parsed_model else 'None'}."
                        self.logger.warning(f"Gemini CLI response parsing failed for batch {batch_num}, attempt {attempt + 1}. {log_msg}")
                        raise ValueError("Response parsing failed, triggering retry.")
                else:
                    self.logger.error(f"Gemini CLI call failed for batch {batch_num}, attempt {attempt+1}. Stderr: {stderr_str}")
                    raise RuntimeError(f"Gemini CLI failed with stderr: {stderr_str}")

            except Exception as e:
                self.logger.exception(f"Exception in Gemini CLI batch {batch_num} on attempt {attempt + 1}: {e}")

            if attempt < GEMINI_CLI_MAX_RETRIES - 1:
                delay = (attempt + 1) * 2
                self.logger.warning(i18n.t("retrying_batch", batch_num=batch_num, attempt=attempt + 1, max_retries=GEMINI_CLI_MAX_RETRIES, delay=delay))
                time.sleep(delay)

        self.logger.error(f"Gemini CLI Batch {batch_num} failed after {GEMINI_CLI_MAX_RETRIES} attempts. Falling back to original texts.")
        task.translated_texts = task.texts
        return task

    def translate_single_text(self, text: str, task_description: str, mod_name: str, source_lang: dict, target_lang: dict, mod_context: str, game_profile: dict) -> str:
        """
        【独有实现】重写单文本翻译工作流，以适配Gemini CLI的调用方式。
        """
        if not text:
            return ""

        prompt = self._build_single_text_prompt(text, task_description, mod_name, source_lang, target_lang, mod_context, game_profile)

        try:
            # Use 'utf-8-sig' for BOM to ensure PowerShell reads the file content correctly.
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8-sig') as f:
                f.write(prompt)
                temp_file = f.name

            try:
                # For single text, we don't request JSON output.
                gemini_command = f"{self.cli_path} --model {self.model}"
                # The robust PowerShell command structure is also applied here.
                full_command = (
                    f"$OutputEncoding = [System.Text.Encoding]::UTF8; "
                    f"Set-ExecutionPolicy RemoteSigned -Scope Process -Force; "
                    f"Get-Content -Path '{temp_file}' -Raw | {gemini_command}"
                )
                cmd = ["powershell", "-NoProfile", "-Command", full_command]

                clean_env = {
                    'PATH': os.environ.get('PATH', ''), 'SYSTEMROOT': os.environ.get('SYSTEMROOT', ''),
                    'TEMP': os.environ.get('TEMP', ''), 'TMP': os.environ.get('TMP', ''),
                    'USERPROFILE': os.environ.get('USERPROFILE', ''), 'APPDATA': os.environ.get('APPDATA', ''),
                    'LOCALAPPDATA': os.environ.get('LOCALAPPDATA', ''), 'PROGRAMDATA': os.environ.get('PROGRAMDATA', ''),
                    'WINDIR': os.environ.get('WINDIR', ''), 'COMSPEC': os.environ.get('COMSPEC', ''),
                    'PATHEXT': os.environ.get('PATHEXT', ''), 'PSModulePath': os.environ.get('PSModulePath', ''),
                    'GEMINI_API_KEY': '',
                }

                kwargs = {
                    "capture_output": True, "timeout": 300, "env": clean_env
                }
                if os.name == 'nt':
                    kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

                result = subprocess.run(cmd, **kwargs)
            finally:
                os.unlink(temp_file)

            # 使用我们新的、健壮的解码函数
            stdout_str = robust_decode(result.stdout)
            stderr_str = robust_decode(result.stderr)

            if result.returncode == 0:
                # The output is raw text, just strip it.
                return stdout_str.strip()
            else:
                self.logger.error(f"Gemini CLI single text translation failed. Stderr: {stderr_str}")
                return text # Fallback to original text

        except Exception as e:
            self.logger.exception(f"Exception in Gemini CLI single text translation for '{text[:30]}...': {e}")
            return text # Fallback
