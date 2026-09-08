// ============
// Paper Outline Module for useAutoPaper
// ============
// Handles AI paper outline generation and management.

import { ElMessage } from 'element-plus'
import { paperAPI } from '@/api'
import {
  paperForm,
  selectedKnowledgePoints,
  skipKnowledgePoints,
  outlineSections,
  outlineLoading,
  outlineMessage,
  currentStep
} from './useAutoPaperCore'

// ============ AI 试卷大纲 ============

export const generateOutline = async () => {
  if (!paperForm.subjectId) {
    ElMessage.warning('请先选择考试科目')
    return
  }

  outlineLoading.value = true
  outlineMessage.value = ''

  try {
    const kpIds = skipKnowledgePoints.value ? [] : selectedKnowledgePoints.value.map(kp => kp.id)
    const res = await paperAPI.generatePaperOutline({
      subject_id: paperForm.subjectId,
      knowledge_point_ids: kpIds,
      total_score: paperForm.totalScore,
      total_time: paperForm.duration
    })

    const data = res.data || {}
    outlineSections.value = data.sections || []
    outlineMessage.value = data.message || ''

    if (data.suggestions && data.suggestions.length > 0) {
      outlineMessage.value = data.suggestions.join('；')
    }

    if (!outlineSections.value.length) {
      ElMessage.warning('未生成任何大纲章节，请调整知识点或题型配置')
    } else {
      ElMessage.success(`已生成 ${outlineSections.value.length} 个大纲章节`)
    }
  } catch (error) {
    console.error('生成大纲失败:', error)
    ElMessage.error('生成大纲失败，请重试')
    outlineSections.value = []
  } finally {
    outlineLoading.value = false
  }
}

export const regenerateOutline = async () => {
  await generateOutline()
}

export const confirmOutline = () => {
  if (!outlineSections.value.length) {
    ElMessage.warning('请先生成大纲')
    return
  }
  currentStep.value = 4
}
