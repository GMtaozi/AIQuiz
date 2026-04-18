## ADDED Requirements

### Requirement: Login page shall display legal disclaimer
The system SHALL display a disclaimer notice on the login page stating that all questions are AI-generated simulations and not real exam questions.

#### Scenario: User views login page
- **WHEN** user navigates to the login page
- **THEN** a disclaimer notice shall be visible in Chinese: "本系统试题均为AI原创模拟题，非真实考试真题"

### Requirement: Registration page shall display user agreement link
The system SHALL display a user agreement link on the registration page.

#### Scenario: User views registration page
- **WHEN** user navigates to the registration page
- **THEN** a link to the user agreement shall be displayed below the registration form

### Requirement: User can view privacy policy
The system SHALL provide a way for users to view the privacy policy.

#### Scenario: User clicks privacy policy link
- **WHEN** user clicks the privacy policy link
- **THEN** a dialog displaying the privacy policy content shall appear

### Requirement: User can view user agreement
The system SHALL provide a way for users to view the full user agreement.

#### Scenario: User clicks user agreement link
- **WHEN** user clicks the user agreement link
- **THEN** a dialog displaying the user agreement content shall appear

### Requirement: Exported papers shall contain copyright notice
The system SHALL add a copyright notice to all exported Word and PDF documents.

#### Scenario: User exports a paper
- **WHEN** user exports a paper to Word or PDF format
- **THEN** the document footer shall contain: "智题 AIQuiz © 2024-2026 | 本试卷题目为AI原创模拟题"
