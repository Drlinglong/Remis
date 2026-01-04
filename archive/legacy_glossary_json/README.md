# Legacy Glossary JSON Files

⚠️ **这些文件已废弃，仅供历史参考。**

## 背景

这些 JSON 格式的词典文件是项目早期使用的数据格式。由于性能原因（几千行 JSON 加载效率低），
项目已迁移至 **SQLite 数据库** 作为唯一的词典数据源。

## 当前架构

- **开发环境**: `AppData/RemisModFactoryDev/remis.sqlite`
- **生产环境**: `AppData/RemisModFactory/remis.sqlite`

词典数据现在存储在 SQLite 的 `glossaries` 和 `entries` 表中。

## 如果需要导入这些旧词典

可以使用 `scripts/developer_tools/import_glossary.py` 工具：

```bash
python -m scripts.developer_tools.import_glossary <game_id> <json_file>
```

## 归档时间

2026-01-04
