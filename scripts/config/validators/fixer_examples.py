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
        "ck3": (
            "Error Type: Variable Parity (CK3 uses [Concept] and $var$)\n"
            "  [Bad] Source: Open [Character.GetFirstName]. | Target: 打开角色面板。\n"
            "  [Fixed] 打开 [Character.GetFirstName]。"
        ),
        "st": (
            "Error Type: Variable Parity (Stellaris uses $var$)\n"
            "  [Bad] Source: The $PLANET$ orbits. | Target: 星球在轨道上。\n"
            "  [Fixed] $PLANET$ 在轨道上。"
        )
    },
    "FORMATTING_TAG": {
        "default": (
            "Error Type: Formatting Tags (Tags must be matched correctly)\n"
            "  [Bad] Source: Click §Yhere§!. | Target: 点击 §Y这里。\n"
            "  [Fixed] 点击 §Y这里§!。"
        ),
        "ck3": (
            "Error Type: Concept Tags (CK3 uses #color ... #! and @icon tags)\n"
            "  [Bad] Source: Earn #P Prestige#!. | Target: 获得 #P 威望。\n"
            "  [Fixed] 获得 #P 威望#!。"
        ),
        "eu4": (
            "Error Type: Formatting Tags (EU4 uses §Y, §G, §R colors)\n"
            "  [Bad] Source: Is §Ggood§!. | Target: 是§G很好。\n"
            "  [Fixed] 是§G很好§!。"
        )
    },
    "BANNED_CHARS": {
         "default": (
             "Error Type: Invalid/Banned Characters (Some fonts or engines don't support certain characters)\n"
             "  [Bad] Source: Test | Target: 测试・测试\n"
             "  [Fixed] 测试·测试"
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
