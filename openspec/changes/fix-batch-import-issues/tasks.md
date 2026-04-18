## 1. Modify Backend File Validation

- [x] 1.1 Remove `_validate_excel_content` function call from `_detect_file_format`
- [x] 1.2 Remove `_validate_word_content` function call from `_detect_file_format`
- [x] 1.3 Keep file type detection via magic numbers (PK, OLE2) intact

## 2. Verify Changes

- [x] 2.1 Verify `_detect_file_format` still correctly detects Excel vs Word files
- [ ] 2.2 Test uploading Excel file with non-standard headers succeeds
- [ ] 2.3 Test uploading Word file without 【题型】 markers succeeds
- [ ] 2.4 Test uploading empty file returns appropriate error
