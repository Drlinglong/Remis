# -*- coding: utf-8 -*-
#
# 功能: 智能解析 Paratranz 词典文本，自动合并重复条目（忽略大小写），并生成结构化 JSON 文件。
#
import json
import re
from datetime import datetime
import pytz

def is_variant_line(line):
    """判断某一行是否是变体行。"""
    if re.search(r'[\u4e00-\u9fff]', line):
        return False
    if re.search(r'[a-zA-Z]', line):
        return True
    return False

def parse_glossary_to_json(input_text, game_prefix='stellaris'):
    """
    将词汇表文本解析为词条列表，并智能合并重复项（忽略大小写）。
    """
    pos_map = {"名词": "Noun", "形容词": "Adjective", "动词": "Verb"}
    entries_raw = re.split(r'\s+(?:创建于|修改于) \d{4}/\d{2}/\d{2}[\s\S]*?评论\s+\d+\s*', input_text)
    
    processed_entries = {}

    for block in entries_raw:
        if not block.strip():
            continue

        lines = [line.strip() for line in block.strip().split('\n') if line.strip()]
        if not lines:
            continue

        original_word = lines.pop(0)
        # 使用小写作为唯一的key，来实现大小写不敏感的去重
        entry_key = original_word.lower()

        if entry_key in processed_entries:
            # 发现重复，合并备注信息
            existing_entry = processed_entries[entry_key]
            new_remarks = []
            
            pos_found = False
            for line in lines:
                if line in pos_map: pos_found = True; continue
                if pos_found: pos_found = False; continue
                if not is_variant_line(line): new_remarks.append(line)
            
            if new_remarks:
                new_remark_str = "\n".join(new_remarks)
                if 'remarks' not in existing_entry['metadata']:
                    existing_entry['metadata']['remarks'] = ""
                if new_remark_str not in existing_entry['metadata']['remarks']:
                    existing_entry['metadata']['remarks'] += f"\n---\n[来源合并备注]:\n{new_remark_str}"
            continue

        # 如果不是重复条目，正常创建
        entry_data = {'translations': {"en": original_word}}
        clean_id = re.sub(r'[\s\W]+', '_', original_word.lower()).strip('_')
        entry_data['id'] = f"{game_prefix}_{clean_id}"
        entry_data['metadata'] = {}
        remarks_list = []
        found_pos, found_zh = False, False

        for line in lines:
            if not found_pos and line in pos_map:
                entry_data['metadata']['part_of_speech'] = pos_map[line]
                found_pos = True
                continue
            if found_pos and not found_zh:
                entry_data['translations']['zh-CN'] = line
                found_zh = True
                continue
            if not found_pos and is_variant_line(line):
                variants = [v.strip() for v in line.split(',') if v.strip()]
                if 'variants' not in entry_data:
                    entry_data['variants'] = {"en": variants}
                continue
            remarks_list.append(line)

        if remarks_list:
            entry_data['metadata']['remarks'] = "\n".join(remarks_list)
        
        processed_entries[entry_key] = entry_data

    return list(processed_entries.values())


def main():
    """主函数"""
    # 在这里切换你的项目前缀: 'stellaris' 或 'victoria3'
    CURRENT_GAME_PREFIX = 'stellaris'
    
    input_filename = 'input.txt'
    output_filename = 'glossary.json'
    try:
        with open(input_filename, 'r', encoding='utf-8') as f:
            raw_text = f.read()
            
        entries_list = parse_glossary_to_json(raw_text, game_prefix=CURRENT_GAME_PREFIX)

        # 更新元数据
        aest = pytz.timezone('Australia/Sydney')
        last_updated_time = datetime.now(aest).isoformat()
        metadata = {
            "description": f"{CURRENT_GAME_PREFIX.capitalize()} 游戏及Mod社区汉化词典",
            "sources": [
                "数据源自多个社区汉化项目，如Paratranz等" # 通用备注
            ],
            "last_updated": last_updated_time
        }
        
        final_output_data = {"metadata": metadata, "entries": entries_list}
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(final_output_data, f, ensure_ascii=False, indent=2)

        print(f"处理完成！智能去重后，词典已成功写入 '{output_filename}' 文件。")
        print(f"总共生成了 {len(entries_list)} 个独立词条。")

    except FileNotFoundError:
        print(f"错误：找不到输入文件 '{input_filename}'。")
    except Exception as e:
        print(f"处理过程中发生错误: {e}")

if __name__ == "__main__":
    main()