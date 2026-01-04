# -*- coding: utf-8 -*-
#
# 功能: 验证 glossary.json 文件，并将详细的验证报告保存到 validation_report.txt。
#
import json
from collections import defaultdict

def validate_glossary(input_path='glossary.json', output_path='validation_report.txt'):
    """
    读取并验证词典文件，将报告写入文本文件。
    """
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"错误: 找不到词典文件 '{input_path}'。请先运行 parser.py 生成它。")
        return
    except json.JSONDecodeError:
        print(f"错误: '{input_path}' 文件格式不正确，无法解析。")
        return

    entries = data.get('entries', [])
    report_lines = []

    report_lines.append(f"--- 开始验证 '{input_path}' ({len(entries)} 个条目) ---\n")

    if not entries:
        report_lines.append("词典中没有任何条目，无需验证。")
        write_report(output_path, report_lines)
        return

    # 数据收集
    seen_ids = defaultdict(list)
    en_to_zh_map = defaultdict(list)
    zh_to_en_map = defaultdict(list)

    for entry in entries:
        entry_id = entry.get('id')
        en_term = entry.get('translations', {}).get('en')
        zh_term = entry.get('translations', {}).get('zh-CN')

        if not all([entry_id, en_term, zh_term]):
            report_lines.append(f"警告: 发现残缺条目，缺少id或翻译: {entry}")
            continue

        seen_ids[entry_id].append(en_term)
        en_to_zh_map[en_term.lower()].append(zh_term) # 冲突检查时也忽略大小写
        zh_to_en_map[zh_term].append(en_term)

    # 分析并生成报告
    found_issues = False

    # 1. 检查ID冲突
    report_lines.append("--- 1. 检查ID冲突 ---")
    id_conflicts = {id: terms for id, terms in seen_ids.items() if len(terms) > 1}
    if id_conflicts:
        found_issues = True
        report_lines.append("错误: 发现以下ID被多个词条共用，这会导致数据覆盖！")
        for id, terms in id_conflicts.items():
            report_lines.append(f"  - ID: '{id}'")
            report_lines.append(f"    - 对应词条: {terms}")
    else:
        report_lines.append("恭喜！未发现ID冲突。")
    report_lines.append("-" * 20)

    # 2. 检查翻译冲突
    report_lines.append("--- 2. 检查翻译冲突 ---")
    translation_conflicts = {en: list(set(zh_list)) for en, zh_list in en_to_zh_map.items() if len(set(zh_list)) > 1}
    if translation_conflicts:
        found_issues = True
        report_lines.append("错误: 发现同一个英文原文有多个不同的中文翻译！请统一。")
        for en, zh_list in translation_conflicts.items():
            report_lines.append(f"  - 英文: '{en}'")
            report_lines.append(f"    - 存在翻译: {zh_list}")
    else:
        report_lines.append("恭喜！未发现直接的翻译冲突。")
    report_lines.append("-" * 20)
    
    # 3. 检查潜在的同义词问题
    report_lines.append("--- 3. 检查潜在的同义词问题 ---")
    potential_issues = {zh: list(set(en_list)) for zh, en_list in zh_to_en_map.items() if len(set(en_list)) > 1}
    if potential_issues:
        found_issues = True
        report_lines.append("注意: 发现同一个中文词被用于翻译多个不同的英文原文。这不一定是错，但建议审查。")
        for zh, en_list in potential_issues.items():
            report_lines.append(f"  - 中文: '{zh}'")
            report_lines.append(f"    - 用于翻译: {en_list}")
    else:
        report_lines.append("未发现明显的同义词问题。")
    report_lines.append("-" * 20)
    
    # 总结
    report_lines.append("\n--- 验证完毕 ---")
    if not found_issues:
        report_lines.append("太棒了！你的词典文件看起来非常干净，没有发现任何冲突。")
    else:
        report_lines.append("验证发现了一些潜在问题，请根据本报告进行修正。")
    
    # 写入文件
    write_report(output_path, report_lines)

def write_report(path, lines):
    with open(path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
    print(f"验证报告已成功保存到 '{path}'")

if __name__ == "__main__":
    validate_glossary()