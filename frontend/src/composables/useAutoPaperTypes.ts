// ============
// Types & Constants & Pure Helpers for useAutoPaper
// ============
// This file contains: interfaces, DEFAULT_TEMPLATES constant, and pure helper functions.
// No Vue reactivity imports needed here.

// ============ Interfaces ============

export interface KnowledgePoint {
  id: number
  name: string
  weight: number
  _descendantCount?: number
  questionCount?: number
  children?: KnowledgePoint[]
  node_type?: string
  parent_id?: number
  label?: string
}

export interface QuestionTypeConfig {
  type: string
  typeName: string
  count: number
  score: number
  easyRatio: number
  mediumRatio: number
  hardRatio: number
}

export interface PaperForm {
  title: string
  categoryId: number | null
  subjectId: number | null
  duration: number
  totalScore: number
  passScore: number
  showAnswer: boolean
}

export interface GeneratedQuestion {
  id: number
  examPaperQuestionId: number
  type: string
  typeName: string
  difficulty: string
  difficultyName: string
  content: string
  options: string[]
  answer: string
  score: number
  knowledgePoint: string
  selected?: boolean
}

export interface Template {
  id: number
  name: string
  description: string
  icon: string
  questionCount: number
  duration: number
  config?: any
}

// ============ Template Definitions ============

export const DEFAULT_TEMPLATES: Template[] = [
  {
    id: 2,
    name: '模拟测试卷',
    description: '根据教学大纲生成的模拟题目',
    icon: 'Collection',
    questionCount: 40,
    duration: 90
  },
  {
    id: 3,
    name: '专项练习卷',
    description: '针对特定知识点的强化练习',
    icon: 'QuestionFilled',
    questionCount: 30,
    duration: 60
  }
]

// ============ Pure Helper Functions ============

// 将后端难度值(1-5)转换为前端难度等级
export const getDifficultyLevel = (difficulty: number) => {
  if (difficulty <= 2) return 'easy'
  if (difficulty === 3) return 'medium'
  return 'hard'
}

// 获取题型名称
export const getTypeName = (type: string) => {
  const map: Record<string, string> = {
    'single_choice': '单选题',
    'multiple_choice': '多选题',
    'true_false': '判断题',
    'essay': '简答题'
  }
  return map[type] || type
}

export const getDifficultyNameByLevel = (difficulty: string) => {
  const map: Record<string, string> = { easy: '简单', medium: '中等', hard: '困难' }
  return map[difficulty] || difficulty
}

export const getDifficultyType = (difficulty: string) => {
  const map: Record<string, string> = { easy: 'success', medium: 'warning', hard: 'danger' }
  return map[difficulty] || 'info'
}
