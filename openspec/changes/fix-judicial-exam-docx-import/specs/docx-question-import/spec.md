## ADDED Requirements

### Requirement: Word document question parsing
The system SHALL support parsing questions from Word (.docx) files in multiple format variations commonly used in Chinese exam files.

#### Scenario: Parse questions with type markers
- **WHEN** a Word document contains questions prefixed with type markers like 【单选题】, 【多选题】, 【判断题】, or 【简答题】
- **THEN** the system SHALL correctly identify the question type and extract the question content

#### Scenario: Parse questions with numbered format
- **WHEN** a Word document contains questions prefixed with numeric or Chinese numeric indexes (e.g., "1. ", "2. ", "一、", "二、", "【1】", "【2】")
- **THEN** the system SHALL extract each numbered question as a separate question

#### Scenario: Parse questions from tables
- **WHEN** a Word document contains questions organized in tables with columns for question type, content, options, and answer
- **THEN** the system SHALL extract questions from such tables

#### Scenario: Parse inline options
- **WHEN** question options appear on the same line as the question content (e.g., "题目内容 A. 选项1 B. 选项2 C. 选项3 D. 选项4")
- **THEN** the system SHALL correctly separate the question content from its options

#### Scenario: Parse answer keys
- **WHEN** questions are followed by lines containing "答案：" or "答案:" markers
- **THEN** the system SHALL associate the correct answer with the preceding question

### Requirement: Question option parsing
The system SHALL correctly parse and structure question options for choice questions.

#### Scenario: Parse multi-letter options
- **WHEN** options are formatted as "A. 选项内容", "B. 选项内容", etc. on separate lines or the same line
- **THEN** the system SHALL create option records with correct labels (A, B, C, D) and content

#### Scenario: Identify correct answers
- **WHEN** a correct answer is specified (e.g., "答案：A" or "答案：AB")
- **THEN** the system SHALL mark the corresponding options as is_correct=True

### Requirement: Error handling and logging
The system SHALL provide helpful error messages and logging for debugging parse failures.

#### Scenario: Log unparseable lines
- **WHEN** certain lines in the document cannot be matched to any known question format
- **THEN** the system SHALL log these lines for debugging purposes without failing the entire import

#### Scenario: Validate extracted questions
- **WHEN** questions are extracted from a document
- **THEN** the system SHALL validate that each question has required fields (question_type, content)
