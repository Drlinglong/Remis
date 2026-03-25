# 增量更新固定化冒烟用例

本文档用于固定当前已跑通的增量更新 MVP 冒烟路径，作为后续版本的最低回归基线。

---

## 一、 用例目标

验证以下闭环在真实项目上持续可用：

- 归档上传
- 存档检测
- Dry-run 预扫描
- 正式执行增量翻译
- 输出重建
- 归档回写

---

## 二、 固定项目

- 项目名称：`商船`
- 项目 ID：`315f6f1f-6fff-4e68-a45f-5e348881ba18`
- 基线源码目录：`J:\V3_Mod_Localization_Factory\source_mod\提供更多商船`
- 测试源码目录：`J:\V3_Mod_Localization_Factory\source_mod\提供更多商船 2026Mar26更新`
- 源语言：`en`
- 目标语言：`zh-CN`

---

## 三、 固定变更

测试文件：

- `J:\V3_Mod_Localization_Factory\source_mod\提供更多商船 2026Mar26更新\localization\english\OCC_l_english.yml`

当前固定场景：

- 总条目数：`8`
- 变更条目数：`1`
- 未变化条目数：`7`
- 新增条目数：`0`

---

## 四、 执行步骤

### Step 1：上传翻译建立基线

入口：

- 项目管理页 -> “上传翻译”

期望结果：

- 成功提示，无 500
- 历史记录新增“存档更新”
- `check-archive` 能返回有效存档点

---

### Step 2：检查存档点

入口：

- 增量更新页 -> 选择项目

期望结果：

- 能检测到存档点
- 默认目标语言为 `zh-CN`
- 不出现整套假本地化语言列表

---

### Step 3：运行 Dry-run 预扫描

输入：

- 自定义源码路径：`J:\V3_Mod_Localization_Factory\source_mod\提供更多商船 2026Mar26更新`
- 目标语言：`zh-CN`
- `dry_run = true`

期望摘要：

```text
total = 8
new = 0
changed = 1
unchanged = 7
```

期望行为：

- 预扫描能结束，不无限转圈
- 执行日志可滚动
- 页面能进入“预扫描摘要”

---

### Step 4：运行正式增量更新

输入：

- 与 Dry-run 相同
- `dry_run = false`

期望行为：

- 只处理变更条目
- 页面显示“增量翻译完成”
- 输出目录生成成功

---

### Step 5：验证输出

输出目录：

- `J:\V3_Mod_Localization_Factory\source_mod\Remis_Incremental_Update`

期望结果：

- 输出文件结构与新版模板一致
- 7 条未变化文本继承旧译文
- 1 条变化文本使用新译文

---

### Step 6：验证归档回写

期望结果：

- 执行完成后生成新的归档版本
- 下一次 `check-archive` 能继续工作
- 之后再次 Dry-run 时，应基于最新归档继续比较

---

## 五、 后端日志关键锚点

Dry-run 成功时，后端日志应至少出现：

```text
Snapshot build completed for 商船: 1 source files detected.
Pre-fetched 8 archive entries for 商船.
Built history index for 商船 (zh-CN): 8 indexed entries.
Prepared language update for 商船 (zh-CN): summary={'total': 8, 'new': 0, 'changed': 1, 'unchanged': 7}
Dry-run completed for 商船: overall_summary={'total': 8, 'new': 0, 'changed': 1, 'unchanged': 7}
```

---

## 六、 判定标准

只要满足以下全部条件，即视为本冒烟用例通过：

- [ ] 上传翻译成功
- [ ] 存档点可检测
- [ ] 目标语言列表正确
- [ ] Dry-run 摘要为 `8 / 0 / 1 / 7`
- [ ] 正式增量更新完成
- [ ] 输出目录生成正确
- [ ] 新归档版本可被下次增量更新继续使用

---

## 七、 使用规则

建议在以下时机跑这条冒烟用例：

- 归档相关 schema / CRUD 调整后
- 增量更新 workflow/service 重构后
- 前端增量更新页面改动后
- 发布前

如果这条固定用例失败，优先视为主链回归，而不是边角问题。
