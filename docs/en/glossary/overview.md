# Glossary System Overview

## 📚 Introduction to the Glossary System

The glossary system is a crucial component for ensuring the consistency and accuracy of game Mod translations. It provides accurate terminology references for AI translation through intelligent term matching, fuzzy matching algorithms, and auxiliary glossary support.

## 🔧 Tools and Scripts

### Core Tools
- **[Glossary Tool Usage Guide](tools-guide.md)** - How to use parser.py and validator.py
- **[System Mechanism Description](system-mechanism.md)** - Core mechanisms and algorithms of the glossary system
- **[Blue Archive Glossary Guide](blue-archive-guide.md)** - Usage guide for specific themed glossaries

### Script Files
- `parser.py` - Generic glossary parser, converts Paratranz exported text to JSON
- `validator.py` - Glossary validator, checks data integrity and consistency
- `input.txt` - Paratranz exported term file template

## 🗂️ Glossary File Structure

### Main Glossary
```
data/glossary/
├── victoria3/
│   └── glossary.json          # Victoria 3 main glossary
├── stellaris/
│   └── glossary.json          # Stellaris main glossary
├── eu4/
│   └── glossary.json          # Europa Universalis IV main glossary
├── hoi4/
│   └── glossary.json          # Hearts of Iron IV main glossary
└── ck3/
    └── glossary.json          # Crusader Kings III main glossary
```

### Bundled game reference glossaries

The desktop installer includes separate Simplified and Traditional Chinese
reference glossaries for Surviving Mars and one multilingual reference glossary
for Probably Stolen. Open Glossary Manager and choose the game's library.
These glossaries are editable and opt-in. Upgrades preserve existing copies
of the same resource, local edits, and project bindings.

### Auxiliary Glossaries
```
data/glossary/
├── stellaris/
│   ├── glossary.json          # Stellaris main glossary
│   └── blue_archive.json      # Blue Archive auxiliary glossary
└── victoria3/
    ├── glossary.json          # Victoria 3 main glossary
    └── custom_theme.json      # Custom theme glossary
```

### Glossary Functionality Overview
The glossary system is one of the core functionalities of the project, capable of:
- **Automatic Term Recognition**: Automatically scans text during translation to identify game-related professional terms.
- **Intelligent Prompt Injection**: Injects relevant terms as high-priority instructions into AI translation requests.
- **Ensuring Consistency**: Guarantees complete consistency of the same term across different files.
- **Supports Bidirectional Translation**: Correctly identifies and applies terms regardless of the source and target languages.

### Glossary File Structure
Glossary files use JSON format, with the following structure:
```json
{
  "metadata": {
    "description": "Victoria 3 Game and Mod Community Localization Glossary",
    "last_updated": "2024-01-01",
    "sources": ["Official Localization", "Community Localization", "Mod Localization"]
  },
  "entries": [
    {
      "id": "victoria3_convoy",
      "translations": {
        "en": "convoy",
        "zh-CN": "船队"
      },
      "metadata": {
        "pos": "noun",
        "remarks": "Produced by ports, maintains the operation of national shipping lanes"
      },
    }
  ]
}
```

## 🚀 Quick Start

### 1. Prepare Terminology File
Export the terminology file from Paratranz.cn project, in the following format:
```
English term name
Part of speech (noun/adjective/verb)
Chinese translation
Remarks (optional)
Variant forms (optional, e.g., Term, Terms)
Modified on 2024/01/01
Comments 0
```

### 2. Generate Glossary
```bash
# Run in data/glossary directory
python parser.py
```

### 3. Validate Glossary Quality
```bash
python validator.py
```

### 4. Deploy Glossary
Place the generated `glossary.json` file in the corresponding game directory.
- **Victoria 3**: `data/glossary/victoria3/glossary.json`
- **Stellaris**: `data/glossary/stellaris/glossary.json`
- **Other Games**: Corresponding game folders can be created under `data/glossary/`

## 🔍 Core Feature Highlights

### Intelligent Term Matching
- **EXACT**: Exact match (confidence: 1.0)
- **VARIANT**: Variant match (confidence: 0.9)
- **ABBREVIATION**: Abbreviation match (confidence: 0.8)
- **PARTIAL**: Partial match (confidence: 0.7)
- **FUZZY**: Fuzzy match (confidence: 0.3-0.6)

### Multi-language Variant Support
Supports multi-language term variants and abbreviations, ensuring cross-language translation consistency.

### Auxiliary Glossary System
Provides additional terminology support for MODs with specific themes, such as Blue Archive, sci-fi themes, etc.

## 📖 Detailed Documentation

- **[Tool Usage Guide](tools-guide.md)** - Detailed tool usage instructions
- **[System Mechanism](system-mechanism.md)** - In-depth technical implementation description
- **[Blue Archive Guide](blue-archive-guide.md)** - Usage of specific glossaries

## 🆘 Common Issues

### Q: How to add a new auxiliary glossary?
A: Refer to the format of `blue_archive.json`, create a new JSON file and place it in the corresponding game directory.

### Q: What if glossary validation fails?
A: Check if the input file format is correct and ensure UTF-8 encoding is used.

### Q: How to update an existing glossary?
A: Rerun parser.py, it will automatically merge new term entries.

## Extension Suggestions

1. **More Game Themes**: Can add auxiliary glossaries for other games.
2. **Glossary Validation**: Add format validation for glossary files.
3. **Online Glossaries**: Support loading glossaries from the network.
4. **Glossary Management**: Provide a management interface for enabling/disabling glossaries.

---

For questions or suggestions, please refer to the project's main documentation or submit an Issue.