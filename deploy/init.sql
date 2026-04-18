-- AI Automatic Question Generation System - Database Init Script
-- Version: 1.0.0

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role SMALLINT DEFAULT 1,
    status SMALLINT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Subject table
CREATE TABLE IF NOT EXISTS subjects (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    status SMALLINT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_subjects_code ON subjects(code);
CREATE INDEX IF NOT EXISTS idx_subjects_status ON subjects(status);

-- Chapter table
CREATE TABLE IF NOT EXISTS chapters (
    id BIGSERIAL PRIMARY KEY,
    subject_id BIGINT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    parent_id BIGINT REFERENCES chapters(id) ON DELETE SET NULL,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_chapters_subject ON chapters(subject_id);
CREATE INDEX IF NOT EXISTS idx_chapters_parent ON chapters(parent_id);

-- Question table
CREATE TABLE IF NOT EXISTS questions (
    id BIGSERIAL PRIMARY KEY,
    subject_id BIGINT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    chapter_id BIGINT REFERENCES chapters(id) ON DELETE SET NULL,
    type SMALLINT NOT NULL CHECK (type BETWEEN 1 AND 5),
    difficulty SMALLINT NOT NULL CHECK (difficulty BETWEEN 1 AND 3),
    content TEXT NOT NULL,
    answer TEXT,
    analysis TEXT,
    tags VARCHAR(500),
    source VARCHAR(100),
    ai_generated BOOLEAN DEFAULT FALSE,
    ai_prompt_id BIGINT,
    status SMALLINT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_questions_subject ON questions(subject_id);
CREATE INDEX IF NOT EXISTS idx_questions_chapter ON questions(chapter_id);
CREATE INDEX IF NOT EXISTS idx_questions_type ON questions(type);
CREATE INDEX IF NOT EXISTS idx_questions_difficulty ON questions(difficulty);
CREATE INDEX IF NOT EXISTS idx_questions_status ON questions(status);

-- Question Options table
CREATE TABLE IF NOT EXISTS question_options (
    id BIGSERIAL PRIMARY KEY,
    question_id BIGINT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    option_label VARCHAR(10) NOT NULL,
    option_content TEXT NOT NULL,
    is_correct BOOLEAN DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_question_options_question ON question_options(question_id);

-- Exam Paper table
CREATE TABLE IF NOT EXISTS exam_papers (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    subject_id BIGINT NOT NULL REFERENCES subjects(id),
    type SMALLINT NOT NULL CHECK (type BETWEEN 1 AND 2),
    total_score DECIMAL(5,2) DEFAULT 100,
    total_questions INTEGER DEFAULT 0,
    duration INTEGER NOT NULL DEFAULT 120,
    pass_score DECIMAL(5,2) DEFAULT 60,
    rule_config JSONB,
    status SMALLINT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_exam_papers_subject ON exam_papers(subject_id);
CREATE INDEX IF NOT EXISTS idx_exam_papers_type ON exam_papers(type);
CREATE INDEX IF NOT EXISTS idx_exam_papers_status ON exam_papers(status);

-- Exam Paper Questions table
CREATE TABLE IF NOT EXISTS exam_paper_questions (
    id BIGSERIAL PRIMARY KEY,
    exam_paper_id BIGINT NOT NULL REFERENCES exam_papers(id) ON DELETE CASCADE,
    question_id BIGINT NOT NULL REFERENCES questions(id),
    sort_order INTEGER NOT NULL,
    score DECIMAL(5,2) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_epq_exam_paper ON exam_paper_questions(exam_paper_id);
CREATE INDEX IF NOT EXISTS idx_epq_question ON exam_paper_questions(question_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_epq_unique ON exam_paper_questions(exam_paper_id, sort_order);

-- Exam Records table
CREATE TABLE IF NOT EXISTS exam_records (
    id BIGSERIAL PRIMARY KEY,
    exam_paper_id BIGINT NOT NULL REFERENCES exam_papers(id),
    user_id BIGINT NOT NULL,
    start_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    submit_time TIMESTAMP,
    score DECIMAL(5,2),
    status SMALLINT DEFAULT 1 CHECK (status BETWEEN 1 AND 3),
    ip_address VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_exam_records_paper ON exam_records(exam_paper_id);
CREATE INDEX IF NOT EXISTS idx_exam_records_user ON exam_records(user_id);
CREATE INDEX IF NOT EXISTS idx_exam_records_status ON exam_records(status);

-- User Answers table
CREATE TABLE IF NOT EXISTS user_answers (
    id BIGSERIAL PRIMARY KEY,
    exam_record_id BIGINT NOT NULL REFERENCES exam_records(id) ON DELETE CASCADE,
    question_id BIGINT NOT NULL REFERENCES questions(id),
    answer_content TEXT,
    is_correct BOOLEAN,
    score DECIMAL(5,2),
    answer_time INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_user_answers_record ON user_answers(exam_record_id);
CREATE INDEX IF NOT EXISTS idx_user_answers_question ON user_answers(question_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_answers_unique ON user_answers(exam_record_id, question_id);

-- AI Prompt Template table
CREATE TABLE IF NOT EXISTS ai_prompt_templates (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    type SMALLINT NOT NULL CHECK (type BETWEEN 1 AND 2),
    content TEXT NOT NULL,
    variables JSONB,
    version VARCHAR(20) NOT NULL DEFAULT '1.0',
    max_tokens INTEGER DEFAULT 2048,
    status SMALLINT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ai_prompt_type ON ai_prompt_templates(type);
CREATE INDEX IF NOT EXISTS idx_ai_prompt_status ON ai_prompt_templates(status);

-- AI Call Logs table
CREATE TABLE IF NOT EXISTS ai_call_logs (
    id BIGSERIAL PRIMARY KEY,
    prompt_template_id BIGINT REFERENCES ai_prompt_templates(id),
    request_params JSONB,
    request_content TEXT,
    response_content TEXT,
    status SMALLINT DEFAULT 1 CHECK (status BETWEEN 1 AND 3),
    error_message TEXT,
    duration INTEGER,
    tokens_used INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ai_call_logs_template ON ai_call_logs(prompt_template_id);
CREATE INDEX IF NOT EXISTS idx_ai_call_logs_status ON ai_call_logs(status);
CREATE INDEX IF NOT EXISTS idx_ai_call_logs_created ON ai_call_logs(created_at);

-- Knowledge Points table
CREATE TABLE IF NOT EXISTS knowledge_points (
    id BIGSERIAL PRIMARY KEY,
    subject_id BIGINT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    chapter_id BIGINT REFERENCES chapters(id) ON DELETE SET NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    parent_id BIGINT REFERENCES knowledge_points(id) ON DELETE SET NULL,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_knowledge_points_subject ON knowledge_points(subject_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_points_chapter ON knowledge_points(chapter_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_points_parent ON knowledge_points(parent_id);

SELECT 'Database initialization completed successfully!' as status;