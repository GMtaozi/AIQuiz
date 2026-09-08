// ============
// Core State Module for useAutoPaper
// ============
// All shared reactive state is defined here.
// Sub-modules import from this file to access shared state.
// This avoids circular dependency issues since sub-modules only
// import from this file (never the other way around at init time).

import { ref, reactive, computed } from 'vue'
import {
  DEFAULT_TEMPLATES,
  type KnowledgePoint,
  type QuestionTypeConfig,
  type PaperForm,
  type GeneratedQuestion,
  type Template
} from './useAutoPaperTypes'

// ============ Core Navigation State ============

export const currentStep = ref(0)
export const generating = ref(false)
export const generationProgress = ref(0)
export const generationStatus = ref('')

// ============ Template State ============

export const useCustomMode = ref(false)
export const selectedTemplate = ref<Template | null>(null)
export const templates = ref<Template[]>(DEFAULT_TEMPLATES)
export const templatesLoading = ref(false)

// ============ Knowledge Tree State ============

export const knowledgeTreeRef = ref<any>(null)
export const knowledgeTree = ref<any[]>([])
export const selectedKnowledgePoints = ref<KnowledgePoint[]>([])
export const skipKnowledgePoints = ref(false)
export const chartColors = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399', '#c71585']

// ============ Paper Form ============

export const paperForm = reactive<PaperForm>({
  title: '',
  categoryId: null,
  subjectId: null,
  duration: 120,
  totalScore: 100,
  passScore: 60,
  showAnswer: false
})

// ============ Question Type Config ============

export const questionTypeConfig = reactive<QuestionTypeConfig[]>([
  { type: 'single_choice', typeName: '单选题', count: 20, score: 2, easyRatio: 40, mediumRatio: 40, hardRatio: 20 },
  { type: 'multiple_choice', typeName: '多选题', count: 10, score: 4, easyRatio: 30, mediumRatio: 40, hardRatio: 30 },
  { type: 'true_false', typeName: '判断题', count: 10, score: 2, easyRatio: 50, mediumRatio: 30, hardRatio: 20 },
  { type: 'essay', typeName: '简答题', count: 5, score: 8, easyRatio: 20, mediumRatio: 50, hardRatio: 30 }
])

// ============ Generated Questions ============

export const generatedQuestions = ref<GeneratedQuestion[]>([])
export const currentPaperId = ref<number | null>(null)
export const dragIndex = ref(-1)

// ============ Preview State ============

export const previewVisible = ref(false)
export const previewData = ref<any>(null)

// ============ Exam Categories & Types ============

export const examCategories = ref<any[]>([])
export const examTypes = ref<any[]>([])

// ============ Outline State ============

export const outlineSections = ref<any[]>([])
export const outlineLoading = ref(false)
export const outlineMessage = ref('')

// ============ Computed Values ============

export const showKnowledgeTree = computed(() => {
  if (useCustomMode.value) return true
  if (selectedTemplate.value?.id === 3) return true
  return false
})

export const totalWeight = computed(() => {
  return selectedKnowledgePoints.value.reduce((sum, kp) => sum + kp.weight, 0)
})

export const totalQuestionCount = computed(() => {
  return questionTypeConfig.reduce((sum, t) => sum + t.count, 0)
})

export const totalConfiguredScore = computed(() => {
  return questionTypeConfig.reduce((sum, t) => sum + t.count * t.score, 0)
})
