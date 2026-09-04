# scripts/config/validators/fixer_examples.py
from typing import Iterable, List, Set

from scripts.utils.game_format_contract import format_structure_signature, normalize_game_id

# 针对各游戏引擎的修复 Prompt 少样本示例字典
# 结构: ERROR_CATEGORY -> { "default": "...", "game_id": "..." }

FIXER_EXAMPLES = {
    "VARIABLE_PARITY": {
        "default": (
            "Error Type: Variable Parity (Protected variables or code tokens were lost or hallucinated)\n"
            "  [Bad] Source: The $pop$ grew. | Target: 人口增长了。\n"
            "  [Fixed] 人口 $pop$ 增长了。"
        ),
        "vic3": (
            "Error Type: Variable Parity (Victoria 3 uses [Concept('key', 'text')], [SCOPE...], $var$, and @icon!)\n"
            "  [Bad] Source: Has [Concept('concept_radicals', 'Radicals')]. | Target: 有激进派。\n"
            "  [Fixed] 有 [Concept('concept_radicals', 'Radicals')]。"
        ),
        "stellaris": (
            "Error Type: Variable Parity (Stellaris uses [brackets], $vars$, and £icons£)\n"
            "  [Bad] Source: Gain £energy£ $VAL$. | Target: 获得能量。\n"
            "  [Fixed] 获得 £energy£ $VAL$。"
        ),
        "eu4": (
            "Error Type: Variable Parity (EU4 uses [brackets], $vars$, £icons£, and @flags)\n"
            "  [Bad] Source: To @FRA $VAL$ ducats. | Target: 给法兰西金币。\n"
            "  [Fixed] 给 @FRA $VAL$ 杜卡特。"
        ),
        "hoi4": (
            "Error Type: Variable Parity (HOI4 uses [?vars|format], [brackets], $vars$, £icons, and @flags)\n"
            "  [Bad] Source: Cost: £political_power [?cost|R]. | Target: 消耗：政治点数。\n"
            "  [Fixed] 消耗：£political_power [?cost|R]。"
        ),
        "ck3": (
            "Error Type: Variable Parity (CK3 uses [Concept], [GetTrait...], $vars$, and @icon!)\n"
            "  [Bad] Source: Respect [Concept('faith', 'religion')|E]. | Target: 尊重宗教。\n"
            "  [Fixed] 尊重 [Concept('faith', '宗教')|E]。"
        ),
        "eu5": (
            "Error Type: Variable Parity (EU5 uses [brackets], $vars$, and @icon!)\n"
            "  [Bad] Source: Needs @money! $VAL$. | Target: 需要钱。\n"
            "  [Fixed] 需要 @money! $VAL$。"
        )
    },
    "FORMATTING_TAG": {
        "default": (
            "Error Type: Formatting Tags (Tags must be matched correctly)\n"
            "  [Bad] Source: Click §Yhere§!. | Target: 点击 §Y这里。\n"
            "  [Fixed] 点击 §Y这里§!。"
        ),
        "vic3": (
            "Error Type: Formatting Tags (Victoria 3 uses #color and closes with #!, or uses #tooltippable;tooltip:<...>)\n"
            "  [Bad] Source: A #variable number#! of #tooltippable;tooltip:<GUI_TOOLTIP>items#!. | Target: 一个变量数量的物品。\n"
            "  [Fixed] 一个 #variable 数量#!的 #tooltippable;tooltip:<GUI_TOOLTIP>物品#!。\n"
            "  [Exact identity] #BOLD Important#! must remain #BOLD 重要#!; never rewrite it as #bold or #b.\n"
            "  [Forbidden] #blue Text#! -> #b lue 文本#! and #italic Text#! -> #b 文本#!."
        ),
        "stellaris": (
            "Error Type: Formatting Tags (Stellaris uses §Y, §R, §G, etc. and closes with §!)\n"
            "  [Bad] Source: Effect: §G+10%§! yield. | Target: 效果：§G+10% 产出。\n"
            "  [Fixed] 效果：§G+10%§! 产出。\n"
            "  [Exact identity] §YImportant§! must remain §Y重要§!, not §R重要§!."
        ),
        "eu4": (
            "Error Type: Formatting Tags (EU4 uses §Y, §R, §G, etc. and closes with §!)\n"
            "  [Bad] Source: Gain §G10§! power. | Target: 获得 10 力量。\n"
            "  [Fixed] 获得 §G10§! 力量。"
        ),
        "hoi4": (
            "Error Type: Formatting Tags (HOI4 uses §Y, §R, §G, etc. and closes with §!)\n"
            "  [Bad] Source: Attack: §R+5%§!. | Target: 攻击：§R+5%。\n"
            "  [Fixed] 攻击：§R+5%§!。\n"
            "  [Exact identity] §YImportant§! must remain §Y重要§!, and @GER/£army_xp£ must remain exact."
        ),
        "ck3": (
            "Error Type: Formatting Tags (CK3 uses #color ... #!)\n"
            "  [Bad] Source: Earn #P Prestige#!. | Target: 获得 #P 威望。\n"
            "  [Fixed] 获得 #P 威望#!。\n"
            "  [Exact identity] #BOLD Important#! must remain #BOLD 重要#!, not #bold 重要#!."
        ),
        "eu5": (
            "Error Type: Formatting Tags (EU5 uses #tag ... #!)\n"
            "  [Bad] Source: The #bold text#! matters. | Target: 这个#bold文本 很重要。\n"
            "  [Fixed] 这个 #bold 文本#!很重要。\n"
            "  [Exact identity] #BOLD Important#! must remain #BOLD 重要#!, not #bold or #b."
        )
    },
    "BANNED_CHARS": {
        "default": (
            "Error Type: Banned Characters in Code Identifiers (Preserve code identifiers and non-translatable parameters; translate player-visible text according to the game's syntax)\n"
            "  [Bad] Source: [GetName] | Target: [获取名字]\n"
            "  [Fixed] [GetName]"
        )
    }
}

FIXER_EXAMPLE_ORDER = (
    "VARIABLE_PARITY",
    "FORMATTING_TAG",
    "BANNED_CHARS",
)

GAME_SPECIFIC_REPAIR_RULES = {
    "vic3": (
        "**VICTORIA 3 CONCEPTS**: Keep the entire [Concept(...)] token exactly as it appears "
        "in the Source, including every argument. Do not translate its player-visible label."
    ),
    "ck3": (
        "**CRUSADER KINGS III CONCEPTS**: Keep the first [Concept('key', 'label')|E] argument "
        "and all syntax unchanged, but translate the second player-visible label into the target language."
    ),
    "hoi4": (
        "**HEARTS OF IRON IV COLOR TAGS**: Color tags start with the section sign '§' and a "
        "single letter (for example §Y or §g), and close with §!. Restore corrupted forms such as "
        "%g to §g from the Source, and preserve every color code. Preserve [ROOT.GetName], "
        "[?variable|format], $KEY$, £icon£, and @TAG exactly."
    ),
    "stellaris": (
        "**STELLARIS FORMAT STRUCTURE**: Preserve every § opener and §! closer exactly, "
        "including case and order. Translate only visible text; preserve [Root.GetName], "
        "$VALUE|Y$, and £minerals£. A changed occurrence count requires semantic review, not an automatic rewrite."
    ),
    "eu5": (
        "**EUROPA UNIVERSALIS V FORMAT STRUCTURE**: Preserve #tag ... #!, [scope/function], "
        "$VALUE$, and @icon! exactly. Translate visible text inside a tag; do not change its raw opener."
    ),
}

def get_examples_for_game(game_id: str, error_categories: Set[str]) -> List[str]:
    """
    根据给定的报错类别集合和 game_id 提取对应的动态 Few-Shot 示例
    """
    examples = []
    
    for category in FIXER_EXAMPLE_ORDER:
        if category not in error_categories:
            continue
        if category in FIXER_EXAMPLES:
            cat_dict = FIXER_EXAMPLES[category]
            # 优先匹配具体游戏，没有则取默认
            example_str = cat_dict.get(game_id)
            if not example_str:
                example_str = cat_dict.get("default")
            
            if example_str:
                examples.append(example_str)
                
    return examples


def get_structure_examples_for_game(game_id: str, source_texts: Iterable[str]) -> List[str]:
    """Build targeted examples from the actual format openers in a batch.

    The source strings remain visible in the repair payload.  These examples
    only teach the model the observed delimiter family and raw opener identity;
    they never replace a semantic token with an alias or placeholder.
    """
    normalized_game_id = normalize_game_id(game_id)
    observed_openers = []
    has_nested = False
    has_unbalanced_source = False
    for source in source_texts:
        signature = format_structure_signature(source or "", normalized_game_id)
        observed_openers.extend(signature["format_openers"])
        has_nested = has_nested or signature["has_nested_formatting"]
        has_unbalanced_source = has_unbalanced_source or not signature["balanced"]

    examples: List[str] = []
    unique_openers = list(dict.fromkeys(observed_openers))
    if normalized_game_id in {"victoria3", "ck3"}:
        for opener in unique_openers[:4]:
            if opener.startswith("#"):
                examples.append(
                    f"Observed exact identity: Source {opener} Important#! -> Target {opener} 重要#!; keep the opener raw."
                )
        if not unique_openers:
            examples.append(
                "Hash-format identity: #BOLD Important#! -> #BOLD 重要#!; #blue must never become #b lue."
            )
    elif normalized_game_id in {"hoi4", "stellaris"}:
        for opener in unique_openers[:4]:
            if opener.startswith("§"):
                examples.append(
                    f"Observed exact identity: Source {opener}Important§! -> Target {opener}重要§!; keep the opener raw."
                )
        if not unique_openers:
            examples.append(
                "Section-format identity: §YImportant§! -> §Y重要§!; never change §Y to §R or another code."
            )

    if has_nested:
        examples.append(
            "Nested structure: #b #i Important#!#! or §Y§RImportant§!§! must keep opener/closer order and nesting."
        )
    if has_unbalanced_source:
        examples.append(
            "Source-side anomaly: if the Source is unbalanced, preserve the source structure and do not invent a target close marker."
        )
    return examples


def get_repair_rules_for_game(game_id: str) -> List[str]:
    """Return only the repair rules that apply to the selected game."""
    rule = GAME_SPECIFIC_REPAIR_RULES.get(game_id)
    return [rule] if rule else []
