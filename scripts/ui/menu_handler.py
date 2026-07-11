# scripts/ui/menu_handler.py
# ---------------------------------------------------------------
"""
这个模块包含了所有与用户界面（菜单显示、用户输入等）相关的函数。
将UI逻辑与核心工作流分离开来，可以提高代码的模块化和可维护性。
"""
import os
import sys
import json
import logging
import re
import importlib.util
from typing import Optional, Dict, List

from scripts.utils import i18n
from scripts.app_settings import (
    LANGUAGES,
    GAME_PROFILES,
    SOURCE_DIR,
    API_PROVIDERS,
    PROJECT_INFO,
)
from scripts.core.archive_manager import archive_manager


def display_version_info():
    """显示项目版本信息"""
    print(f"📦 版本version: {PROJECT_INFO['version']}")
    print(f"📅 最后更新last update: {PROJECT_INFO['last_update']}")
    print(f"{PROJECT_INFO['copyright']}")
    print("=" * 60)

def preflight_checks():
    """
    执行开机自检，验证系统环境和项目结构

    Returns:
        bool: 检查是否通过
    """
    print(i18n.t("preflight_checking_environment"))

    checks_passed = True
    error_messages = []

    # 1. 检查项目结构
    required_dirs = ["scripts", "data", "source_mod"]
    required_files = ["scripts/main.py", "scripts/app_settings.py", "data/lang/zh_CN.json", "data/lang/en_US.json"]

    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            error_messages.append(i18n.t("preflight_error_missing_dir", dir_path=dir_path))
            checks_passed = False

    for file_path in required_files:
        if not os.path.exists(file_path):
            error_messages.append(i18n.t("preflight_error_missing_file", file_path=file_path))
            checks_passed = False

    # 2. 检查依赖库
    required_libraries = {
        "openai": "api_lib_openai",
        "google.genai": "api_lib_gemini",
        "dashscope": "api_lib_qwen",
        "requests": "api_lib_ollama"
    }

    available_libraries = []
    for lib_name, lib_key in required_libraries.items():
        try:
            if lib_name == "google.genai":
                import google.genai
            else:
                importlib.import_module(lib_name)
            available_libraries.append(i18n.t(lib_key))
        except ImportError:
            pass

    if not available_libraries:
        error_messages.append(i18n.t("preflight_error_no_api_libs"))
        checks_passed = False

    # 3. 检查API密钥
    api_keys = [
        "OPENAI_API_KEY", 
        "GEMINI_API_KEY", 
        "DASHSCOPE_API_KEY",
        "DEEPSEEK_API_KEY",
        "XAI_API_KEY",
        "SILICONFLOW_API_KEY",
        "MODELSCOPE_API_KEY"
    ]
    available_keys = [key for key in api_keys if os.getenv(key)]

    # 4. 专项检查 Ollama
    # 已经在上面的库检查中检测了 requests，这里主要看是否可以用
    ollama_ready = "requests" in sys.modules or importlib.util.find_spec("requests") is not None

    # 只要有任何一个 Key 或者 Ollama 可用，就认为 API 环节通过
    if not available_keys and not ollama_ready:
        error_messages.append(i18n.t("preflight_error_no_api_keys"))
        checks_passed = False

    # 4. 检查source_mod目录内容
    mod_count = 0
    if os.path.exists("source_mod"):
        mod_dirs = [d for d in os.listdir("source_mod") if os.path.isdir(os.path.join("source_mod", d))]
        mod_count = len(mod_dirs)
        if mod_count == 0:
            error_messages.append(i18n.t("preflight_error_source_mod_empty"))
            checks_passed = False
    else:
        error_messages.append(i18n.t("preflight_error_source_mod_missing"))
        checks_passed = False

    # 5. 初始化数据库
    if not archive_manager.initialize_database():
        # The function already logs the detailed error
        checks_passed = False

    # 显示检查结果
    if checks_passed:
        lib_names = ", ".join(available_libraries)
        key_count = len(available_keys)
        print(i18n.t("preflight_success_header") + " " + i18n.t('preflight_success', libs=lib_names, keys=key_count, mods=mod_count))
    else:
        print(i18n.t("preflight_failed_header"))
        for msg in error_messages:
            print(f"   - {msg}")
        print(f"\n{i18n.t('preflight_retry_prompt')}")

    return checks_passed

def select_api_provider():
    """【新】显示API供应商列表并让用户选择。"""
    logging.info(i18n.t("select_api_provider_prompt"))

    provider_options = list(API_PROVIDERS.keys())

    for i, key in enumerate(provider_options):
        if key == "qwen":
            logging.info(f"  [{i + 1}] {key.capitalize()} - {i18n.t('qwen_china_hint')}")
        elif key == "deepseek":
            logging.info(f"  [{i + 1}] {key.capitalize()} - {i18n.t('deepseek_china_hint')}")
        else:
            logging.info(f"  [{i + 1}] {key.capitalize()}")

    while True:
        try:
            choice = int(input(i18n.t("enter_choice_prompt"))) - 1
            if 0 <= choice < len(provider_options):
                return provider_options[choice]
            else:
                logging.warning(i18n.t("invalid_input_number"))
        except ValueError:
            logging.warning(i18n.t("invalid_input_not_number"))

def gather_mod_context(mod_name):
    """
    Reads the mod name from its metadata and prompts the user for additional context.
    """
    logging.info(i18n.t("getting_mod_context"))
    mod_official_name = mod_name
    meta_path = os.path.join(SOURCE_DIR, mod_name, '.metadata', 'metadata.json')
    descriptor_path = os.path.join(SOURCE_DIR, mod_name, 'descriptor.mod')

    try:
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta_data = json.load(f)
                if 'name' in meta_data and meta_data['name']:
                    mod_official_name = meta_data['name']
        elif os.path.exists(descriptor_path):
            with open(descriptor_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip().startswith('name='):
                        match = re.search(r'"(.*)"', line)
                        if match:
                            mod_official_name = match.group(1)
                        break

        logging.info(i18n.t("mod_name_identified", name=mod_official_name))
        extra_context = input(i18n.t("prompt_for_extra_context")).strip()

        final_context = mod_official_name
        if extra_context:
            final_context += f" ({extra_context})"

        logging.info(i18n.t("final_context_is", context=final_context))
        return final_context

    except Exception as e:
        logging.exception(i18n.t("error_getting_context", error=e))
        return mod_name

def select_interface_language():
    """选择界面语言"""
    print("🌍 请选择界面语言 / Please select interface language")
    print("=" * 60)
    print("1. English")
    print("2. 中文 (简体)")
    print("=" * 60)

    while True:
        choice = input("请输入选择 (1 或 2) / Enter choice (1 or 2): ").strip()
        if choice == "1":
            return "en_US"
        elif choice == "2":
            return "zh_CN"
        else:
            print("❌ 无效选择，请重新输入 / Invalid choice, please try again")

def select_game_profile():
    """Displays a menu for the user to select a game profile."""
    logging.info(i18n.t("select_game_profile_prompt"))
    profiles = list(GAME_PROFILES.values())
    for i, profile in enumerate(profiles):
        logging.info(f"  [{i + 1}] {profile['name']}")

    while True:
        try:
            choice = int(input(i18n.t("enter_choice_prompt"))) - 1
            if 0 <= choice < len(profiles):
                return profiles[choice]
            else:
                logging.warning(i18n.t("invalid_input_number"))
        except ValueError:
            logging.warning(i18n.t("invalid_input_not_number"))

def select_language(prompt_key, game_profile, source_lang=None):
    """
    显示基于所选游戏配置文件的语言选择菜单。
    现在支持多选和“套壳”模式。
    """
    logging.info(i18n.t(prompt_key))

    supported_langs = [LANGUAGES[key] for key in game_profile['supported_language_keys']]

    # 如果提供了源语言，则在目标语言选择中将其过滤掉
    if source_lang:
        display_options = [lang for lang in supported_langs if lang['key'] != source_lang['key']]
    else:
        display_options = supported_langs

    # --- 显示菜单 ---
    is_target_selection = bool(source_lang)

    if is_target_selection:
        logging.info(f"  [0] {i18n.t('target_option_all_dynamic', count=len(display_options))}")

    for i, lang in enumerate(display_options, 1):
        logging.info(f"  [{i}] {lang['name']}")

    if is_target_selection:
        logging.info(f"  [99] {i18n.t('target_option_custom')}")


    while True:
        try:
            choice_str = input(i18n.t("enter_choice_prompt")).strip()
            choice = int(choice_str)

            if is_target_selection:
                if choice == 0:
                    logging.info(i18n.t("select_language_all_selected", count=len(display_options)))
                    return display_options
                elif 1 <= choice <= len(display_options):
                    selected = display_options[choice - 1]
                    logging.info(i18n.t("select_language_single_selected", name=selected['name']))
                    return [selected]
                elif choice == 99:
                    shell_config = handle_shell_language_selection(game_profile)
                    return [shell_config] if shell_config else None
                else:
                    logging.warning(i18n.t("error_invalid_list_number"))
            else:  # 源语言选择
                if 1 <= choice <= len(display_options):
                    selected = display_options[choice - 1]
                    logging.info(i18n.t("select_language_single_selected", name=selected['name']))
                    return selected
                else:
                    logging.warning(i18n.t("error_invalid_list_number"))
        except ValueError:
            logging.warning(i18n.t("error_invalid_not_number"))

def handle_shell_language_selection(game_profile):
    """
    处理“套壳”语言选择
    """
    logging.info(i18n.t("shell_mode_entering"))
    custom_name = input(i18n.t("shell_mode_prompt_name")).strip()
    if not custom_name:
        logging.warning(i18n.t("shell_mode_error_name_empty"))
        return None

    logging.info(i18n.t("shell_mode_prompt_shell_lang"))

    supported_langs = [LANGUAGES[key] for key in game_profile['supported_language_keys']]
    for i, lang in enumerate(supported_langs, 1):
        logging.info(f"  [{i}] {lang['name']}")

    while True:
        try:
            choice = int(input(i18n.t("shell_mode_prompt_choice"))) - 1
            if 0 <= choice < len(supported_langs):
                shell_lang = supported_langs[choice]

                shell_lang_config = {
                    "is_shell": True,
                    "name": i18n.t("shell_mode_display_name", custom_name=custom_name, shell_name=shell_lang['name']),
                    "custom_name": custom_name,
                    "key": shell_lang['key'],
                    "folder_prefix": shell_lang['folder_prefix'],
                    "code": shell_lang['code']
                }
                logging.info(i18n.t("shell_mode_confirm_selection", custom_name=custom_name, shell_name=shell_lang['name']))
                return shell_lang_config
            else:
                logging.warning(i18n.t("error_invalid_list_number"))
        except ValueError:
            logging.warning(i18n.t("error_invalid_not_number"))

def select_glossaries_from_db(game_profile):
    """
    新的函数：从数据库获取词典并让用户选择。
    """
    from scripts.core.glossary_manager import glossary_manager

    logging.info(i18n.t("cli_select_glossary_prompt"))
    print(f"  [1] {i18n.t('cli_select_glossary_yes')}")
    print(f"  [2] {i18n.t('cli_select_glossary_no')}")

    enable_choice = ""
    while enable_choice not in ["1", "2"]:
        enable_choice = input(i18n.t("enter_choice_prompt")).strip()
        if enable_choice not in ["1", "2"]:
            logging.warning(i18n.t("invalid_input_number"))

    if enable_choice == "2":
        # User wants main glossary only. Find it and return its ID.
        import asyncio
        all_glossaries = asyncio.run(glossary_manager.get_available_glossaries(game_profile['id']))
        main_glossary = next((g for g in all_glossaries if g['is_main']), None)
        if main_glossary:
            return [main_glossary['glossary_id']]
        else:
            return None # No main glossary exists anyway

    logging.info(i18n.t("cli_glossary_loading_all"))
    import asyncio
    available_glossaries = asyncio.run(glossary_manager.get_available_glossaries(game_profile['id']))

    if not available_glossaries:
        logging.warning(i18n.t("no_glossaries_available"))
        return None

    main_glossary = next((g for g in available_glossaries if g['is_main']), None)
    aux_glossaries = [g for g in available_glossaries if not g['is_main']]

    logging.info(i18n.t("cli_glossary_available", game_name=game_profile['name']))
    if main_glossary:
        logging.info(f"  -> {main_glossary['name']} {i18n.t('cli_glossary_main_suffix')}")

    for i, g in enumerate(aux_glossaries, 1):
        logging.info(f"  [{i}] {g['name']} - {g.get('description', '')}")

    selected_ids = set()
    if main_glossary:
        selected_ids.add(main_glossary['glossary_id'])

    while True:
        raw_input = input(i18n.t("cli_glossary_select_prompt")).strip()
        if not raw_input:
            break

        try:
            choices = [int(i.strip()) for i in raw_input.split(',')]
            valid_choices = True
            temp_ids = set()
            for choice in choices:
                if 1 <= choice <= len(aux_glossaries):
                    temp_ids.add(aux_glossaries[choice - 1]['glossary_id'])
                else:
                    logging.warning(i18n.t("cli_glossary_not_found", glossary_index=choice))
                    valid_choices = False
                    break
            if valid_choices:
                selected_ids.update(temp_ids)
                break
        except ValueError:
            logging.warning(i18n.t("cli_glossary_invalid_input"))

    if selected_ids:
        # For logging purposes, get the names of selected glossaries
        selected_names = [g['name'] for g in available_glossaries if g['glossary_id'] in selected_ids]
        logging.info(i18n.t("cli_glossary_selected", glossary_names=", ".join(selected_names)))

    return list(selected_ids) if selected_ids else None


def select_fuzzy_matching_mode():
    """
    选择术语模糊匹配模式
    """
    logging.info(i18n.t("fuzzy_matching_mode_prompt"))
    logging.info(i18n.t("fuzzy_matching_strict"))
    logging.info(i18n.t("fuzzy_matching_loose"))
    logging.info(i18n.t("fuzzy_matching_hint"))

    while True:
        choice = input(i18n.t("enter_fuzzy_choice")).strip()

        if choice == "1":
            return "strict"
        elif choice == "2":
            return "loose"
        else:
            logging.warning(i18n.t("invalid_fuzzy_choice"))

def prompt_for_manual_workshop_id() -> Optional[str]:
    """提示用户手动输入创意工坊ID。"""
    logging.info(f"\n--- {i18n.t('prompt_workshop_id_title')} ---")
    logging.info(f"{i18n.t('prompt_workshop_id_desc')}")
    logging.info(f"{i18n.t('prompt_workshop_id_skip')}")
    workshop_id = input(i18n.t("prompt_workshop_id_enter")).strip()
    return workshop_id if workshop_id else None


def show_project_overview(mod_name, api_provider, game_profile, source_lang, target_languages, selected_glossary_ids, cleanup_choice, fuzzy_mode, workshop_id_info: Dict):
    """
    显示工程总览并等待用户确认
    """
    from scripts.core.glossary_manager import glossary_manager
    logging.info(i18n.t("project_overview_title"))

    logging.info(i18n.t("project_overview_mod", mod_name=mod_name))
    logging.info(i18n.t("project_overview_api", provider=api_provider.capitalize()))
    logging.info(i18n.t("project_overview_game", game_name=game_profile['name']))
    logging.info(i18n.t("project_overview_source", source_lang=source_lang['name']))

    if len(target_languages) == 1:
        target_lang_info = target_languages[0]['name']
    else:
        target_lang_info = i18n.t("target_languages_multiple", count=len(target_languages))
    logging.info(i18n.t("project_overview_target", target_lang=target_lang_info))

    # Glossary status
    if selected_glossary_ids:
        import asyncio
        all_glossaries = asyncio.run(glossary_manager.get_available_glossaries(game_profile['id']))
        selected_names = [g['name'] for g in all_glossaries if g['glossary_id'] in selected_glossary_ids]
        glossary_status = ", ".join(selected_names)
    else:
        glossary_status = i18n.t("glossary_status_none")
    logging.info(i18n.t("project_overview_glossary", glossary_status=glossary_status))

    # Workshop ID status
    status = workshop_id_info['status']
    if status == 'manual':
        workshop_id_status_text = i18n.t("overview_workshop_id_manual", id=workshop_id_info['id'])
    elif status == 'auto':
        workshop_id_status_text = i18n.t("overview_workshop_id_auto")
    else: # not_found
        workshop_id_status_text = i18n.t("overview_workshop_id_disabled")
    logging.info(i18n.t("project_overview_workshop_id", status=workshop_id_status_text))

    fuzzy_status = i18n.t("fuzzy_matching_status_enabled") if fuzzy_mode == 'loose' else i18n.t("fuzzy_matching_status_disabled")
    logging.info(i18n.t("project_overview_fuzzy_matching", fuzzy_status=fuzzy_status))

    cleanup_status = i18n.t("cleanup_status_yes") if cleanup_choice else i18n.t("cleanup_status_no")
    logging.info(i18n.t("project_overview_cleanup", cleanup_status=cleanup_status))

    while True:
        choice = input(i18n.t("confirm_translation_start")).strip().upper()
        if choice == 'Y':
            logging.info(i18n.t("translation_confirmed"))
            return True
        elif choice == 'N':
            logging.info(i18n.t("returning_to_language_selection"))
            return False
        else:
            logging.warning(i18n.t("invalid_confirm_choice"))

def handle_custom_language_selection():
    """
    处理自定义语言选择
    """
    logging.info(i18n.t("entering_custom_mode"))
    custom_name = input(i18n.t("prompt_custom_lang_name"))
    custom_key = input(i18n.t("prompt_custom_lang_key"))
    custom_prefix = input(i18n.t("prompt_custom_lang_prefix"))

    if custom_name.lower() == "cancel":
        logging.info(i18n.t("custom_language_selection_cancelled"))
        return None

    if not custom_key or not custom_prefix:
        logging.warning(i18n.t("custom_language_selection_incomplete"))
        return None

    custom_lang = {
        "code": "custom", "key": custom_key,
        "name": custom_name, "folder_prefix": custom_prefix
    }
    logging.info(i18n.t("custom_language_selected", name=custom_name, key=custom_key, prefix=custom_prefix))
    return custom_lang

def ask_cleanup_choice(mod_name):
    """
    询问用户是否清理源文件
    """
    logging.info(i18n.t("ask_cleanup_prompt", mod_name=mod_name))
    while True:
        choice = input(i18n.t("enter_cleanup_choice")).strip().upper()
        if choice == 'Y':
            logging.info(i18n.t("cleanup_confirmed"))
            return True
        elif choice == 'N':
            logging.info(i18n.t("cleanup_cancelled"))
            return False
        else:
            logging.warning(i18n.t("invalid_cleanup_choice"))
