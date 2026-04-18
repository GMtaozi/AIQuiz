## Why

用户反馈司法鉴定考试题库 Word 文件（`电子数据鉴定项目司法鉴定执业专业能力测试题.docx`）导入时无法解析出题目。现有的 `_parse_word_questions` 函数无法处理该文件的格式，导致预览和导入均失败。

## What Changes

- 改进 Word 题目解析器，支持更多题目格式变体
- 支持以表格形式组织的题目（常见于正式考试文件）
- 支持常见题目编号格式（中文数字、阿拉伯数字混合）
- 增强错误处理和调试信息，方便后续问题排查

## Capabilities

### New Capabilities
- `docx-question-import`: 支持更多 Word 文档题目格式的解析能力，包括表格格式、多种编号格式、选项与题目混排等复杂排版方式

### Modified Capabilities
- （无）

## Impact

- **代码文件**: `backend/app/routers/questions.py` 中的 `_parse_word_questions` 函数
- **受影响功能**: 题目导入预览（`/api/questions/preview`）和批量导入（`/api/questions/import`）
- **依赖**: `python-docx` 库（已安装）
