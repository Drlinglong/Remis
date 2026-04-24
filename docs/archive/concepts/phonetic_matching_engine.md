# 拼音/语音匹配引擎 (Phonetic Matching Engine)

## 1. 概述 (Overview)

拼音匹配引擎 (`PhoneticsEngine`) 是 Remis 术语系统 "Tiered Defense Strategy" 的第一层防御机制。旨在解决传统编辑距离 (Levenshtein Distance) 无法有效识别 CJK (中日韩) 语言同音异形词 (Homophones) 的问题。

### 核心目标
- **中文**: 识别拼音相同但汉字不同的词 (如 "格黑娜" vs "格黑那")。
- **日文**: 通过罗马字 (Romaji) 转换识别读音相似的词 (如 "科学" vs "化学")。
- **韩文**: 通过 Jamo 分解识别字形/读音相似的词。

## 2. 架构设计 (Architecture)

### 2.1 核心类: `PhoneticsEngine`
位于 `scripts/utils/phonetics_engine.py`。

#### 主要方法
- **`generate_fingerprint(text: str, lang: str) -> str`**
    - 根据语言生成“语音指纹”。
    - **zh (中文)**: 使用 `pypinyin` 转换为无声调拼音 (如 `geheina`)。
    - **ja (日文)**: 使用 `pykakasi` 转换为罗马字 (如 `kagaku`)。
    - **ko (韩文)**: 使用 `jamo` 分解为字母序列。
    - **其他**: 返回小写原字符串。

- **`calculate_phonetic_distance(term_a: str, term_b: str, lang: str) -> float`**
    - 计算两个词语音指纹的归一化 Levenshtein 相似度 (0.0 - 1.0)。
    - 1.0 表示语音完全匹配 (同音词)。

### 2.2 集成: `GlossaryManager`
位于 `scripts/core/glossary_manager.py`。

在 `_smart_term_matching` 流程中增加了 **Phonetic Match** 阶段：
1. **Exact Match**: 精确匹配 (最高优先级)。
2. **Phonetic Match**: 语音匹配 (Tier 1)。
    - 如果源文本中检测到术语的语音指纹 (Fingerprint Substring Match)。
    - 标记为 `[PHONETIC]` 类型，置信度 0.85。
    - 提示 Prompt 中会警告可能存在同音错别字。
3. **Variant/Abbreviation/Partial**: 其他模糊匹配。

## 3. 依赖库 (Dependencies)

需要在 `requirements.txt` 中添加：
- `pypinyin`: 用于中文拼音转换。
- `pykakasi`: 用于日文罗马字转换。
- `jamo`: 用于韩文 Jamo 分解。

## 4. 未来扩展 (Future Roadmap)

- **Tier 2 (Heavyweight)**: 预留了 `AdvancedCorrector` 接口，未来可接入 `pycorrector` 或 LLM 进行更精准的上下文纠错。
