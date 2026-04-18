// 统一的前端难度映射常量

// 后端难度等级：1=简单, 2=较简单, 3=中等, 4=较难, 5=困难

// 前端难度选项 -> 后端数字
export const DIFFICULTY_FRONTEND_TO_BACKEND = {
  easy: 2,
  medium: 3,
  hard: 4,
  mixed: 3
}

// 后端数字 -> 前端难度选项
export const DIFFICULTY_BACKEND_TO_FRONTEND = {
  1: 'easy',
  2: 'easy',
  3: 'medium',
  4: 'hard',
  5: 'hard'
}

// 前端题型选项 -> 后端字符串
export const QUESTION_TYPE_FRONTEND_TO_BACKEND = {
  single: 'single_choice',
  multiple: 'multiple_choice',
  judge: 'true_false',
  short_answer: 'essay'
}

// 后端字符串 -> 前端题型选项
export const QUESTION_TYPE_BACKEND_TO_FRONTEND = {
  'single_choice': 'single',
  'multiple_choice': 'multiple',
  'true_false': 'judge',
  'essay': 'short_answer'
}

// 有效题型列表
export const QUESTION_TYPES = ['single', 'multiple', 'judge', 'short_answer']

// 有效难度选项
export const DIFFICULTY_OPTIONS = ['easy', 'medium', 'hard']
