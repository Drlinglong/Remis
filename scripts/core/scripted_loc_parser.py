from __future__ import annotations

# ---------------------------------------------------------------
#  scripts/core/scripted_loc_parser.py
# ---------------------------------------------------------------
# @Last Modified: 2025-08-18
# ---------------------------------------------------------------
"""
模块: scripted_loc_parser.py

核心功能:
一个专用的解析器，用于处理《欧陆风云4》中独特的“脚本化本地化”(scripted localization)文件。

目标游戏与格式:
本解析器 **仅为《欧陆风云4》(EU4)** 设计，专门处理其 `customizable_localization` 目录下的 `.txt` 文件。
其核心功能是提取和重组使用 `add_custom_loc = "..."` 命令格式的文本行。

架构上下文:
《欧陆风云4》采用了一套独特的双文件夹本地化系统：
1.  `/localization`       : 存放常规的静态本地化文件。
2.  `/customizable_localization`: 存放由游戏脚本动态调用的文本。

本模块 (`scripted_loc_parser.py`) 负责处理上述的第二种，即“脚本化本地化”部分。
所有常规的本地化文件（包括EU4的 `/localization` 文件夹以及其他所有支持的游戏）均由更通用的 `loc_parser.py` 负责处理。

重要提示:
**本解析器不适用于**其他P社游戏，如《群星》(Stellaris)、《钢铁雄心4》(Hearts of Iron IV)、《十字军之王3》(Crusader Kings III)或《维多利亚3》(Victoria 3)。这些游戏不使用此旧版的脚本化本地化机制。
"""
"""
Obsługa plików customizable_localization/*.txt (scripted loc).

•  znajdź linie     add_custom_loc = "Tekst"
•  zbierz do listy  -> zwracamy texts_to_translate i mapę pozycji
•  po tłumaczeniu   -> wstawiamy translated_text na pierwotne miejsce
"""
import re, pathlib
from typing import List, Tuple

_ADD_RE = re.compile(r'^(?P<prefix>\s*add_custom_loc\s*=\s*)"(?P<text>[^"]*)"', re.M)

def extract_texts(path: pathlib.Path) -> Tuple[List[str], List[Tuple[int, str]]]:
    """Zwraca (lista_tekstów, mapa_pozycji)"""
    src = path.read_text(encoding='utf-8', errors='ignore').splitlines(keepends=True)
    texts, positions = [], []
    for i, line in enumerate(src):
        m = _ADD_RE.match(line)
        if m:
            texts.append(m.group('text'))
            positions.append((i, m.group('prefix')))
    return texts, positions, src

def inject_texts(src_lines: List[str],
                 positions: List[Tuple[int, str]],
                 translated: List[str]) -> List[str]:
    for (i, prefix), new in zip(positions, translated):
        safe = new.replace('"', '\\"')
        src_lines[i] = f'{prefix}"{safe}"\n'
    return src_lines
