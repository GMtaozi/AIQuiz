## Why

题库管理批量导入功能存在两个问题：

1. **文件格式校验过严**：后端 `_detect_file_format` 函数对上传的 Excel/Word 文件进行严格的内容校验（表头必须包含特定关键字、Word 必须包含特定标记），导致很多格式正确但表头名称略有不同的文件无法导入。

2. **上传文件失败**：由于格式校验过于严格，用户上传符合格式要求的文件时仍然会因为内容不符合预期而被拒绝，导致导入失败。

移除不必要的格式校验可以提高批量导入功能的实用性，让用户能够导入更多格式变体的文件。

## What Changes

- **移除后端文件内容校验**：删除 `_validate_excel_content` 和 `_validate_word_content` 函数，不再对 Excel 表头和 Word 内容进行严格校验
- **保留文件类型检测**：保留基于魔数的文件类型检测（区分 Excel 和 Word），确保文件解析到正确的解析器
- **前端保持不变**：文件选择器的 `accept` 属性保持现状，继续限制只能选择 `.xlsx`, `.xls`, `.docx` 文件

## Capabilities

### Modified Capabilities
- `question-bank-import`: 修改题库批量导入的校验逻辑，移除严格的内容格式校验，只保留文件类型检测

## Impact

- **后端**：`backend/app/routers/questions.py` 中的 `_validate_excel_content` 和 `_validate_word_content` 函数将不再被调用
- **用户体验**：批量导入功能将更宽容，不再因为表头名称差异或缺少特定标记而拒绝文件
