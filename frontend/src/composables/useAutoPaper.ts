// ============
// useAutoPaper - Main Composable (Orchestrator)
// ============
// This file orchestrates all sub-modules and exports the useAutoPaper() composable.
// All shared reactive state is in useAutoPaperCore.ts.
// Business logic is split into:
//   - useAutoPaperTypes.ts      : interfaces, constants, pure helpers
//   - useAutoPaperCore.ts       : shared reactive state
//   - useTemplateManager.ts     : template loading/selection
//   - useKnowledgeSelector.ts   : knowledge point selection
//   - useQuestionConfig.ts      : question type config & difficulty
//   - usePaperGeneration.ts     : paper generation & A/B papers
//   - usePaperOperations.ts     : CRUD: save/publish/export/replace
//   - usePaperOutline.ts        : AI outline generation

import { watch } from 'vue'
import { systemAPI, knowledgeAPI } from '@/api'
import {
  DEFAULT_TEMPLATES,
  getTypeName,
  getDifficultyLevel,
  getDifficultyNameByLevel,
  getDifficultyType,
  type KnowledgePoint,
  type QuestionTypeConfig,
  type PaperForm,
  type GeneratedQuestion,
  type Template
} from './useAutoPaperTypes'

// ============ Core State (re-exported for consumers) ============
import {
  currentStep,
  generating,
  generationProgress,
  generationStatus,
  useCustomMode,
  selectedTemplate,
  knowledgeTreeRef,
  dragIndex,
  currentPaperId,
  templates,
  templatesLoading,
  previewVisible,
  previewData,
  paperForm,
  knowledgeTree,
  selectedKnowledgePoints,
  skipKnowledgePoints,
  chartColors,
  questionTypeConfig,
  generatedQuestions,
  totalWeight,
  totalQuestionCount,
  totalConfiguredScore,
  examCategories,
  examTypes,
  showKnowledgeTree,
  outlineSections,
  outlineLoading,
  outlineMessage
} from './useAutoPaperCore'

// ============ Sub-module Functions ============
import {
  loadTemplates,
  saveAsTemplate,
  selectTemplate,
  handleCustomModeChange
} from './useTemplateManager'

import {
  selectAllKnowledgePoints,
  handleKnowledgeChange,
  autoBalanceWeight,
  handleSkipKnowledgeChange,
  getKnowledgePointName
} from './useKnowledgeSelector'

import {
  autoAdjustDifficulty,
  handleWeightChange,
  calculateTotalQuestions,
  calculateTotalScore
} from './useQuestionConfig'

import {
  previewGeneration,
  generateQuestions,
  generateABPapers
} from './usePaperGeneration'

import {
  saveDraft,
  publishPaper,
  exportWord,
  exportPdf,
  replaceQuestion,
  removeQuestion
} from './usePaperOperations'

import {
  generateOutline,
  regenerateOutline,
  confirmOutline
} from './usePaperOutline'

// ============ Exam Categories & Types ============

export const loadExamCategories = async () => {
  try {
    const res = await systemAPI.getExamCategories()
    examCategories.value = res.data.items || []
  } catch (error) {
    console.error('加载考试种类失败:', error)
  }
}

export const handleCategoryChange = async (categoryId: number) => {
  paperForm.subjectId = null
  examTypes.value = []
  selectedKnowledgePoints.value = []
  knowledgeTree.value = []

  if (!categoryId) return

  try {
    const res = await systemAPI.getExamTypes({ category_id: categoryId })
    examTypes.value = res.data.items || []
  } catch (error) {
    console.error('加载考试科目失败:', error)
  }
}

export const handleSubjectChange = async (subjectId: number) => {
  selectedKnowledgePoints.value = []
  knowledgeTree.value = []

  if (!subjectId) return

  try {
    const res = await knowledgeAPI.getHierarchyTrees({ exam_type_id: subjectId })
    knowledgeTree.value = res.data.trees || []
    console.log('加载的知识点树:', knowledgeTree.value)

    // 如果选择了模拟测试卷模板，加载完知识点后自动选择所有知识点
    if (selectedTemplate.value?.id === 2) {
      await selectAllKnowledgePoints()
    }
  } catch (error) {
    console.error('加载知识点失败:', error)
  }
}

// ============ Navigation ============

export const nextStep = async () => {
  if (currentStep.value < 5) {
    // 如果从知识点配置进入大纲步骤，自动生成大纲
    if (currentStep.value === 2 && paperForm.subjectId) {
      try {
        await generateOutline()
      } catch (e) {
        console.error('自动生成大纲失败:', e)
      }
    }
    currentStep.value++
  }
}

export const prevStep = () => {
  if (currentStep.value > 0) {
    currentStep.value--
  }
}

// ============ Drag & Drop ============

export const handleDragStart = (index: number) => {
  dragIndex.value = index
}

export const handleDrop = (targetIndex: number) => {
  if (dragIndex.value === -1 || dragIndex.value === targetIndex) return

  const questions = [...generatedQuestions.value]
  const [removed] = questions.splice(dragIndex.value, 1)
  questions.splice(targetIndex, 0, removed)
  generatedQuestions.value = questions
  dragIndex.value = -1
}

export const reorderQuestions = () => {
  console.info('拖拽题目左侧手柄可调整顺序')
}

// ============ Composable ============

export function useAutoPaper() {
  // Watch for subject change to auto-load knowledge tree
  watch(() => paperForm.subjectId, (newVal) => {
    if (newVal) {
      handleSubjectChange(newVal)
    }
  })

  return {
    // State
    currentStep,
    generating,
    useCustomMode,
    selectedTemplate,
    knowledgeTreeRef,
    dragIndex,
    currentPaperId,
    // Computed
    showKnowledgeTree,
    // Form
    paperForm,
    // Knowledge tree
    knowledgeTree,
    selectedKnowledgePoints,
    skipKnowledgePoints,
    chartColors,
    // Question type config
    questionTypeConfig,
    // Generated questions
    generatedQuestions,
    // Computed values
    totalWeight,
    totalQuestionCount,
    totalConfiguredScore,
    // Exam data
    examCategories,
    examTypes,
    // Actions
    loadExamCategories,
    handleCategoryChange,
    handleSubjectChange,
    selectAllKnowledgePoints,
    handleKnowledgeChange,
    autoBalanceWeight,
    selectTemplate,
    handleCustomModeChange,
    nextStep,
    prevStep,
    handleSkipKnowledgeChange,
    autoAdjustDifficulty,
    generateQuestions,
    generateABPapers,
    // Helpers
    getTypeName,
    getDifficultyLevel,
    getDifficultyNameByLevel,
    getDifficultyType,
    handleDragStart,
    handleDrop,
    reorderQuestions,
    replaceQuestion,
    // Outline 与试卷操作
    outlineSections,
    outlineLoading,
    outlineMessage,
    generateOutline,
    regenerateOutline,
    confirmOutline,
    getKnowledgePointName,
    saveDraft,
    publishPaper,
    exportWord,
    exportPdf,
    // 权重/数量/分数回调与删题
    handleWeightChange,
    calculateTotalQuestions,
    calculateTotalScore,
    removeQuestion,
    // Templates
    templates,
    templatesLoading,
    loadTemplates,
    saveAsTemplate,
    DEFAULT_TEMPLATES
  }
}
