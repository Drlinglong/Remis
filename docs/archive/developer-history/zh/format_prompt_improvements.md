# 格式化提示词改进与游戏特定规则

> **文档状态：** historical
>
> **原用途：** 2025 年一轮游戏专用格式提示词改造的实现快照
>
> **Copilot 语料：** excluded
>
> **现行替代：** 当前代码、验证器测试与
> [智能工坊开发契约](../../../zh/developer/agent-workshop-contract.md)

## 概述

本次改进的核心在于为每个游戏配置了专门的 `format_prompt`，并结合 `scripts/config.py` 中的 `GAME_PROFILES` 和 `FALLBACK_FORMAT_PROMPT` 实现了强大的保底机制。这一系列优化旨在显著提高AI翻译的质量和准确性，确保翻译结果完美适配P社游戏的复杂本地化格式要求。

## 改进内容

### 1. 游戏特定的 Format Prompt

在 `scripts/config.py` 的 `GAME_PROFILES` 字典中，每个游戏现在都配置了针对其特点优化的 `format_prompt`。这些提示词基于官方Wiki和游戏机制，确保AI在翻译时严格遵循游戏特有的语法和格式规则。

#### Victoria 3 ⭐ **最新更新**
- **基于官方Wiki的准确本地化格式规则**
- **数据函数、作用域和概念 ([...])**: 最复杂的语法，完全保留包括括号、句点、圆括号和单引号
- **基础和链式函数**: 保留简单函数如 [GetName] 和链式函数如 [SCOPE.GetType.GetFunction]
- **带参数的函数 (...)**: 圆括号内的内部键和作用域名称不翻译，用户面向的文本应翻译
- **函数格式化 (使用 |)**: 保留完整的格式化代码，如 [GetValue|*] (K/M/B格式)、[GetValue|+] (添加符号和颜色)
- **格式化命令 (#key ... #!)**: 保留 #key 和 #! 标签，翻译中间文本
- **简单格式化**: 颜色如 #R text#! (红色)、#gold text#! (金色)，样式如 #b text#! (粗体)
- **特殊工具提示格式化**: #tooltippable;tooltip:<tooltip_key> text_to_display#! 结构
- **文本图标 (@key!)**: 完全保留包括 @ 和 ! 的整个标签
- **内部键和代码引用**: 下划线字符串不翻译
- **换行**: 完全保留 \n

#### Stellaris ⭐ **最新更新**
- **基于官方Wiki的准确本地化格式规则**
- **作用域命令和动态文本 ([...])**: 完全保留，包括作用域、句点和函数
- **转义规则**: 双括号 `[[` 作为单括号 `[` 的转义序列
- **脚本规则**: 反斜杠转义命令 `\\[This.GetName]` 必须保留前导 `\\`
- **变量和图标 ($...$, £...£)**: 完全保留，包括修饰符（使用 `|` 管道符）
- **数字格式化**: 如 `$VALUE|*1$`（格式化为1位小数）
- **颜色格式化**: 如 `$AGE|Y$`（为变量输出着色）
- **图标帧**: 如 `£leader_skill|3£`（选择图标的第3帧）
- **格式化标签 (§...§!)**: 保留标签本身，翻译内部纯文本
- **内部键和代码引用**: 下划线字符串不翻译
- **换行和制表符**: 完全保留 `\n` 和 `\t`

#### Europa Universalis IV ⭐ **最新更新**
- **基于官方Wiki的准确本地化格式规则**
- **方括号 ([...]) - 现代动态文本**：用于获取动态文本，如 [Root.GetAdjective]。必须完全保留，不翻译括号内的任何内容。
- **传统变量 ($...$)**：如 $CAPITAL$, $COUNTRY_ADJ$。必须完全保留。
- **格式化、图标和特殊字符 (§, £, @, ¤)**：
    - **基本颜色格式化 (§...§!)**：如 §RRed Text§!。保留标签，翻译文本。
    - **复杂变量格式化 (也使用 §...§!)**：如 §=Y3$VAL$§! 或 $VAL|%2+$!。必须完全保留整个结构。
    - **图标 (£...£ 和 ¤)**：如 £adm£。必须完全保留。特殊情况：¤ 符号也必须保留。
    - **国家旗帜 (@TAG)**：如 @HAB。必须完全保留。
- **内部键和代码引用**：如 button_text。必须完全保留，不翻译。
- **换行**：完全保留 `\n`。
- **历史术语**：准确保留所有历史、殖民和贸易术语。保持适合早期现代欧洲历史的文艺复兴/启蒙时代语调。

#### Hearts of Iron IV ⭐ **最新更新**
- **基于官方Wiki的准确本地化格式规则**
- **方括号 ([...]) 的两种主要用途**: 命名空间和作用域、格式化变量
- **命名空间和作用域**: 如 [GetDateText] 或 [ROOT.GetNameDefCap]，完全保留不翻译
- **格式化变量**: [?variable|codes] 结构，使用 ? 开头，管道符后的代码定义格式
- **格式代码示例**: [?var|%G0] (百分比、绿色、0位小数)、[?var|*] (SI单位如K/M)、[?var|+] (动态颜色)、[?var|.1] (1位小数)
- **字符串嵌套和变量 ($...$)**: 嵌套其他本地化键或变量，如 $KEY_NAME$ 或 $FOCUS_NAME$
- **转义规则**: 双美元符号 $$ 作为单美元符号 $ 的转义序列
- **颜色标签 (§...§!)**: 保留标签本身，翻译内部纯文本
- **文本图标 (£...)**: 单标签表示图标，如 £GFX_army_experience，支持帧修饰符 £icon_name|1
- **国家旗帜 (@TAG)**: 如 @GER 表示国家旗帜，完全保留
- **本地化格式化器**: 独立的 formatter|token 结构，如 building_state_modifier|dam
- **内部键和代码引用**: 下划线字符串不翻译
- **换行**: 完全保留 \n

#### Crusader Kings III ⭐ **最新更新**
- **基于官方Wiki的准确本地化格式规则**
- **数据函数和链接 ([...])**：用于获取游戏数据中的动态文本。括号内的整个结构必须保留。
    - **作用域和函数**：如 [ROOT.Char.GetLadyLord]。必须完全保留，不翻译任何部分。
    - **函数参数 (使用 |)**：函数末尾的管道符 | 用于应用格式化。必须保留函数和整个参数。
        - 示例：[ROOT.Char.GetLadyLord|U] (首字母大写), [some_value|2] (四舍五入到2位小数), [GetFullName|P] (格式化为正数/绿色)。
    - **链接到游戏概念**：如 [faith|E] 或 [faith|El]。必须保留。
        - 对于替代文本形式，如 [Concept('faith','religion')|E]，必须保留函数结构 [Concept('faith','...')|E]，但用户可见的文本（如 'religion'）应该翻译。
    - **链接到特质/头衔**：如 [GetTrait('trait_name').GetName( CHARACTER.Self )] 或 [GetTitleByKey('title_name').GetName]。必须完全保留。
- **字符串嵌套和变量 ($...$)**：
    - **嵌套其他键**：如 $special_contract_march_short$。必须完全保留。
    - **游戏引擎变量**：显示游戏中的值。如 $VALUE|=+0$。独特的 |=... 格式必须完全保留。
- **文本格式化 (#...#!)**：
    - **基本格式化**：如 #P text#! (正数/绿色), #N text#! (负数/红色), #bold text#!, #italic text#!。保留 #key 和 #! 标签，翻译中间文本。
    - **组合格式化**：格式化可以通过分号 ; 组合。如 #high;bold。必须保留整个组合键。
- **图标 (@icon_name!)**：如 @gold_icon!。必须完全保留。
- **基本字符**：完全保留所有内部换行符 (`\n`) 和转义双引号 (`\\"`)。
- **中世纪术语**：准确保留所有中世纪、封建和王朝术语。保持适合中世纪角色扮演和王朝管理的中世纪、宫廷语调。

### 2. 保底机制

- 新增 `FALLBACK_FORMAT_PROMPT` 常量
- 当游戏配置中没有专门的 `format_prompt` 时自动使用
- 确保系统始终有可用的格式提示模板

### 3. API Handler 更新

所有三个 API handler 都已更新：

- `openai_handler.py`
- `gemini_handler.py`
- `qwen_handler.py`

现在它们会：
1. 优先检查游戏配置中是否有专门的 `format_prompt`
2. 如果有，使用游戏特定的模板
3. 如果没有，自动回退到保底选项

## 技术实现

### 配置结构 (`scripts/config.py`)

在 `scripts/config.py` 中，`GAME_PROFILES` 字典为每个游戏定义了详细的配置，其中包含了游戏特定的 `format_prompt`。同时，`FALLBACK_FORMAT_PROMPT` 作为通用保底选项。

```python
# scripts/config.py 示例
GAME_PROFILES = {
    "1": {
        "id": "victoria3",
        "name": "Victoria 3 (维多利亚3)",
        # ... 其他配置 ...
        "prompt_template": (
            "You are a professional translator specializing in the grand strategy game Victoria 3, "
            "set in the 19th and early 20th centuries. "
            "Translate the following numbered list of texts from {source_lang_name} to {target_lang_name}.\\n"
        ),
        "single_prompt_template": (
            "You are a direct, one-to-one translation engine. "
            "The text you are translating is for a Victoria 3 game mod named '{mod_name}'. "
            "Translate the following {task_description} from {source_lang_name} to {target_lang_name}.\\n"
        ),
        "format_prompt": (
            # ... 详细的Victoria 3格式化规则 ...
            "--- INPUT LIST ---\\n{numbered_list}\\n--- END OF INPUT LIST ---"
        ),
    },
    # ... 其他游戏配置 ...
}

# 保底格式提示模板
FALLBACK_FORMAT_PROMPT = (
    "CRITICAL FORMATTING: Your response MUST be a numbered list with the EXACT same number of items, from 1 to "
    "{chunk_size}. "
    # ... 通用格式化规则 ...
    "--- INPUT LIST ---\\n{numbered_list}\\n--- END OF INPUT LIST ---"
)
```

### 使用逻辑 (API Handler)

在 AI 服务处理器（如 `gemini_handler.py`）中，会根据当前游戏配置智能地选择 `format_prompt`：

```python
# 示例：在API Handler中选择format_prompt
# 优先使用游戏特定的format_prompt，如果没有则使用保底选项
if "format_prompt" in game_profile:
    format_prompt_part = game_profile["format_prompt"].format(
        chunk_size=len(chunk),
        punctuation_prompt=punctuation_prompt if punctuation_prompt else "",
        numbered_list=numbered_list
    )
else:
    # 导入保底选项
    from scripts.config import FALLBACK_FORMAT_PROMPT
    format_prompt_part = FALLBACK_FORMAT_PROMPT.format(
        chunk_size=len(chunk),
        punctuation_prompt=punctuation_prompt if punctuation_prompt else "",
        numbered_list=numbered_list
    )
```

## 优势

1. **提高准确性**: 每个游戏的术语和语调都得到专门优化
2. **降低错误率**: 针对特定游戏的特殊语法和格式要求
3. **保持兼容性**: 保底机制确保系统始终可用
4. **易于维护**: 集中管理所有格式提示模板
5. **可扩展性**: 新增游戏时只需添加相应的 `format_prompt`
6. **群星特殊优势**: 基于官方Wiki的准确规则，大幅降低本地化错误率
7. **Victoria 3特殊优势**: 基于官方Wiki的复杂语法规则，特别是数据函数、作用域和概念的处理
8. **HOI4特殊优势**: 基于官方Wiki的军事策略游戏语法规则，特别是格式化变量、国家旗帜和本地化格式化器的处理

## 注意事项

1. 所有 `format_prompt` 都必须包含以下占位符：
   - `{chunk_size}`: 批次大小
   - `{punctuation_prompt}`: 标点符号转换提示
   - `{numbered_list}`: 编号列表

2. 新增游戏时，建议参考现有模板的结构
3. 保持与现有 `prompt_template` 和 `single_prompt_template` 的一致性
4. **群星特殊要求**: 严格遵循官方Wiki的语法规则，特别是作用域命令、转义序列和修饰符的处理
5. **Victoria 3特殊要求**: 严格遵循官方Wiki的复杂语法规则，特别是数据函数、作用域、概念和格式化命令的处理
6. **HOI4特殊要求**: 严格遵循官方Wiki的语法规则，特别是格式化变量、国家旗帜、本地化格式化器和转义序列的处理

## 测试验证

已通过测试脚本验证：
- 所有5个游戏的 `format_prompt` 都能正确格式化
- 保底选项能正常工作
- 所有占位符都能正确替换
- **群星format_prompt**: 包含所有关键规则，格式化成功，长度2068字符
- **Victoria 3 format_prompt**: 包含所有关键规则，格式化成功，长度2798字符
- **HOI4 format_prompt**: 包含所有关键规则，格式化成功，长度2708字符

## 更新历史

### 2025-10-06 - 最新更新
- 基于 `scripts/config.py` 中的 `GAME_PROFILES`，详细说明了 Victoria 3, Stellaris, Europa Universalis IV, Hearts of Iron IV, Crusader Kings III 等游戏的 `format_prompt` 规则。
- 强调了 `FALLBACK_FORMAT_PROMPT` 的保底机制。
- 明确了 API Handler 如何智能选择 `format_prompt`。
- 增加了 `punctuation_prompt` 占位符的说明。

