## Context

题库管理批量导入功能允许用户通过上传 Excel 或 Word 文件批量导入题目。后端 `import_questions` API 使用 `_detect_file_format` 函数检测文件格式，并在检测通过后调用 `_validate_excel_content` 和 `_validate_word_content` 对文件内容进行严格校验。

当前问题：
- `_validate_excel_content` 要求 Excel 表头必须包含"题型"、"题目"、"内容"等特定关键字
- `_validate_word_content` 要求 Word 文件必须包含【题型】标记和"答案："等关键字
- 这些校验过于严格，导致格式正确但表头名称略有不同的文件无法导入

## Goals / Non-Goals

**Goals:**
- 移除对 Excel 文件表头的严格关键字校验
- 移除对 Word 文件内容格式的严格标记校验
- 保留基于魔数的文件类型检测（区分 Excel 和 Word）
- 修复批量导入上传文件失败的问题

**Non-Goals:**
- 不修改文件解析逻辑（`_parse_excel_questions` 和 `_parse_word_questions` 保持不变）
- 不修改前端文件选择器的 `accept` 属性
- 不添加新的文件格式支持（如 PDF、TXT 等）

## Decisions

### 1. 移除内容校验函数调用

**决定**：在 `_detect_file_format` 函数中移除对 `_validate_excel_content` 和 `_validate_word_content` 的调用。

**原因**：
- 这些校验函数过于严格，与实际解析器的容错能力不匹配
- `_parse_excel_questions` 和 `_parse_word_questions` 本身对格式更宽容
- 移除校验代码量最小，风险最低

**替代方案考虑**：
- 修改校验函数使其更宽容 → 校验逻辑复杂，且难以覆盖所有边界情况
- 完全重写检测逻辑 → 工作量大，收益不明显

### 2. 保留魔数检测

**决定**：保留基于文件魔数（PK、\xD0\xCF\x11\xE0）的文件类型检测。

**原因**：
- 确保文件能被正确路由到对应的解析器（Excel vs Word）
- 检测逻辑简单可靠，不依赖文件扩展名
- 避免安全风险（如伪造文件扩展名）

## Risks / Trade-offs

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 用户上传错误格式文件 | 解析失败，返回通用错误 | 保留基础的魔数检测，确保文件类型基本正确 |
| 解析器遇到畸形文件崩溃 | 500 错误 | 解析器应有异常处理，捕获并返回有意义的错误 |

## Open Questions

- 是否需要添加更多文件格式（如 .xls 传统 Excel 格式）的测试？
- 移除校验后，用户体验是否有其他需要改进的地方？
