# scripts/config/validators/fixer_examples.py
from typing import Set, List

# 针对各游戏引擎的修复 Prompt 少样本示例字典
# 结构: ERROR_CATEGORY -> { "default": "...", "game_id": "..." }

FIXER_EXAMPLES = {
    "VARIABLE_PARITY": {
        "default": (
            "Error Type: Variable Parity (Variables like $var$ or [Concept] were lost or hallucinated)\n"
            "  [Bad] Source: The $pop$ grew. | Target: 人口增长了。\n"
            "  [Fixed] 人口 $pop$ 增长了。"
        ),
        "vic3": (
            "Error Type: Variable Parity (Victoria 3 uses [Concept('key', 'text')], [SCOPE...], $var$, and @icon!)\n"
            "  [Bad] Source: Has [Concept('concept_radicals', 'Radicals')]. | Target: 有激进派。\n"
            "  [Fixed] 有 [Concept('concept_radicals', '激进派')]。"
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
            "  [Bad] Source: Gain [GetTrait('brave').GetName(GetPlayer)]. | Target: 获得勇敢特质。\n"
            "  [Fixed] 获得 [GetTrait('brave').GetName(GetPlayer)]。"
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
            "  [Fixed] 一个 #variable 数量#!的 #tooltippable;tooltip:<GUI_TOOLTIP>物品#!。"
        ),
        "stellaris": (
            "Error Type: Formatting Tags (Stellaris uses §Y, §R, §G, etc. and closes with §!)\n"
            "  [Bad] Source: Effect: §G+10%§! yield. | Target: 效果：§G+10% 产出。\n"
            "  [Fixed] 效果：§G+10%§! 产出。"
        ),
        "eu4": (
            "Error Type: Formatting Tags (EU4 uses §Y, §R, §G, etc. and closes with §!)\n"
            "  [Bad] Source: Gain §G10§! power. | Target: 获得 10 力量。\n"
            "  [Fixed] 获得 §G10§! 力量。"
        ),
        "hoi4": (
            "Error Type: Formatting Tags (HOI4 uses §Y, §R, §G, etc. and closes with §!)\n"
            "  [Bad] Source: Attack: §R+5%§!. | Target: 攻击：§R+5%。\n"
            "  [Fixed] 攻击：§R+5%§!。"
        ),
        "ck3": (
            "Error Type: Formatting Tags (CK3 uses #color ... #!)\n"
            "  [Bad] Source: Earn #P Prestige#!. | Target: 获得 #P 威望。\n"
            "  [Fixed] 获得 #P 威望#!。"
        ),
        "eu5": (
            "Error Type: Formatting Tags (EU5 uses #tag ... #!)\n"
            "  [Bad] Source: The #bold text#! matters. | Target: 这个#bold文本 很重要。\n"
            "  [Fixed] 这个 #bold 文本#!很重要。"
        )
    },
    "BANNED_CHARS": {
        "default": (
             "Error Type: Banned Characters in Code Blocks (Never translate strings inside formatting tags, [brackets], or $vars$ to Chinese)\n"
             "  [Bad] Source: [GetName] | Target: [获取名字]\n"
             "  [Fixed] [GetName]"
         )
    }
}

def get_examples_for_game(game_id: str, error_categories: Set[str]) -> List[str]:
    """
    根据给定的报错类别集合和 game_id 提取对应的动态 Few-Shot 示例
    """
    examples = []
    
    for category in error_categories:
        if category in FIXER_EXAMPLES:
            cat_dict = FIXER_EXAMPLES[category]
            # 优先匹配具体游戏，没有则取默认
            example_str = cat_dict.get(game_id)
            if not example_str:
                example_str = cat_dict.get("default")
            
            if example_str:
                examples.append(example_str)
                
    return examples
