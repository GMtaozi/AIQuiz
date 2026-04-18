"""Application Constants - Magic numbers replaced with named constants"""

# User Roles
class UserRole:
    ADMIN = 1           # 管理员
    TEACHER = 2         # 题库编辑 (原教师)
    STUDENT = 3         # 审核员 (原学生)

    @classmethod
    def is_valid(cls, role: int) -> bool:
        return role in (cls.ADMIN, cls.TEACHER, cls.STUDENT)

    @classmethod
    def is_editor_or_admin(cls, role: int) -> bool:
        """题库编辑或管理员"""
        return role in (cls.ADMIN, cls.TEACHER)

    @classmethod
    def is_auditor_or_admin(cls, role: int) -> bool:
        """审核员或管理员"""
        return role in (cls.ADMIN, cls.STUDENT)


# Status Constants
class Status:
    INACTIVE = 0
    ACTIVE = 1


# Paper Status
class PaperStatus:
    DRAFT = 0
    PUBLISHED = 1
    ARCHIVED = 2


# Exam Status
class ExamStatus:
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    GRADED = "graded"


# Question Types
class QuestionType:
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    ESSAY = "essay"

    ALL = (SINGLE_CHOICE, MULTIPLE_CHOICE, TRUE_FALSE, ESSAY)

    @classmethod
    def is_valid(cls, question_type: str) -> bool:
        return question_type in cls.ALL


# AI Template Types
class AiTemplateType:
    QUESTION_GENERATION = "question_generation"
    GRADING = "grading"
    EXPLANATION = "explanation"


# Pagination defaults
class Pagination:
    DEFAULT_PAGE = 1
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
