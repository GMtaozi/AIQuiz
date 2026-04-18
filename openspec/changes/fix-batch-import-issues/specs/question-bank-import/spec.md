## ADDED Requirements

### Requirement: File Type Detection via Magic Number

The system SHALL detect whether an uploaded file is Excel or Word format based on file magic numbers, not file extension.

#### Scenario: Upload valid Excel .xlsx file
- **WHEN** user uploads a file with Excel content (ZIP-based with xl/ directory)
- **THEN** system SHALL detect the file as "excel" format

#### Scenario: Upload valid Word .docx file
- **WHEN** user uploads a file with Word content (ZIP-based with word/ directory)
- **THEN** system SHALL detect the file as "word" format

#### Scenario: Upload legacy .xls file
- **WHEN** user uploads a file with OLE2 format (starts with \xD0\xCF\x11\xE0) and Excel markers
- **THEN** system SHALL detect the file as "excel" format

#### Scenario: Upload legacy .doc file
- **WHEN** user uploads a file with OLE2 format and Word markers
- **THEN** system SHALL detect the file as "word" format

#### Scenario: Upload unsupported file format
- **WHEN** user uploads a file with unsupported magic numbers
- **THEN** system SHALL return error "文件格式不受支持（需要 Excel 或 Word 格式）"

### Requirement: Relaxed Excel Content Validation

The system SHALL NOT enforce strict header keyword requirements on uploaded Excel files. Any valid Excel file with parseable content SHALL be accepted.

#### Scenario: Upload Excel with custom header names
- **WHEN** user uploads an Excel file with headers that do not match expected keywords
- **THEN** system SHALL attempt to parse the file without returning header validation errors

#### Scenario: Upload Excel missing expected headers
- **WHEN** user uploads an Excel file that lacks typical headers like "题型" or "答案"
- **THEN** system SHALL attempt to parse the file (parsing may fail at row level with appropriate error)

### Requirement: Relaxed Word Content Validation

The system SHALL NOT enforce strict content format markers on uploaded Word files. Any valid Word file SHALL be accepted for parsing.

#### Scenario: Upload Word without type markers
- **WHEN** user uploads a Word file that lacks 【题型】 markers
- **THEN** system SHALL attempt to parse the file without returning content format errors

#### Scenario: Upload Word without answer markers
- **WHEN** user uploads a Word file that lacks "答案：" markers
- **THEN** system SHALL attempt to parse the file without returning content format errors

### Requirement: File Content Length Validation

The system SHALL verify that uploaded files contain sufficient content before attempting parsing.

#### Scenario: Upload empty or too-small file
- **WHEN** user uploads a file with less than 4 bytes of content
- **THEN** system SHALL return error "文件内容为空或过小"
