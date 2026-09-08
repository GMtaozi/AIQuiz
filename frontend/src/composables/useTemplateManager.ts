// ============
// Template Manager Module for useAutoPaper
// ============
// Handles template loading, selection, and custom mode.

import { ElMessage } from 'element-plus'
import { paperAPI } from '@/api'
import { DEFAULT_TEMPLATES, type Template } from './useAutoPaperTypes'
import {
  templates,
  templatesLoading,
  selectedTemplate,
  useCustomMode,
  paperForm,
  questionTypeConfig,
  knowledgeTreeRef,
  selectedKnowledgePoints,
  skipKnowledgePoints
} from './useAutoPaperCore'
import { selectAllKnowledgePoints } from './useKnowledgeSelector'

// ============ Template Functions ============

export const loadTemplates = async () => {
  templatesLoading.value = true
  try {
    const res = await paperAPI.getTemplates()
    const backendTemplates = (res.data?.items || res.data || []).map((t: any) => ({
      id: t.id,
      name: t.name,
      description: t.description || '',
      icon: 'Document',
      questionCount: t.config?.total_questions || t.config?.question_count || 0,
      duration: t.config?.duration || t.duration || 120,
      config: t.config || {}
    }))
    templates.value = [...DEFAULT_TEMPLATES, ...backendTemplates]
  } catch (error) {
    console.error('加载模板失败:', error)
    templates.value = [...DEFAULT_TEMPLATES]
  } finally {
    templatesLoading.value = false
  }
}

export const saveAsTemplate = async () => {
  if (!paperForm.title) {
    ElMessage.warning('请先填写试卷名称')
    return
  }

  try {
    const config = {
      title: paperForm.title,
      duration: paperForm.duration,
      total_score: paperForm.totalScore,
      pass_score: paperForm.passScore,
      question_type_config: questionTypeConfig.map(t => ({
        type: t.type,
        count: t.count,
        score: t.score,
        easy_ratio: t.easyRatio,
        medium_ratio: t.mediumRatio,
        hard_ratio: t.hardRatio
      })),
      knowledge_point_ids: skipKnowledgePoints.value ? [] : selectedKnowledgePoints.value.map(kp => kp.id),
      skip_knowledge_points: skipKnowledgePoints.value
    }

    await paperAPI.saveAsTemplate({
      name: paperForm.title,
      subject_id: paperForm.subjectId,
      description: `自动保存的模板：${paperForm.title}`,
      config
    })
    ElMessage.success('模板保存成功')
    await loadTemplates()
  } catch (error) {
    console.error('保存模板失败:', error)
    ElMessage.error('保存模板失败，请重试')
  }
}

export const selectTemplate = async (template: Template) => {
  selectedTemplate.value = template
  useCustomMode.value = false
  paperForm.title = template.name
  paperForm.duration = template.duration

  // 如果模板有配置，应用配置
  if (template.config) {
    if (template.config.total_score) paperForm.totalScore = template.config.total_score
    if (template.config.pass_score) paperForm.passScore = template.config.pass_score
    if (template.config.question_type_config) {
      template.config.question_type_config.forEach((tc: any) => {
        const typeConfig = questionTypeConfig.find(t => t.type === tc.type)
        if (typeConfig) {
          typeConfig.count = tc.count || 0
          typeConfig.score = tc.score || 0
          typeConfig.easyRatio = tc.easy_ratio ?? 40
          typeConfig.mediumRatio = tc.medium_ratio ?? 40
          typeConfig.hardRatio = tc.hard_ratio ?? 20
        }
      })
    }
    if (template.config.knowledge_point_ids && template.config.knowledge_point_ids.length > 0) {
      skipKnowledgePoints.value = template.config.skip_knowledge_points || false
      if (!skipKnowledgePoints.value) {
        knowledgeTreeRef.value?.setCheckedKeys(template.config.knowledge_point_ids)
      }
    }
  }

  // 如果是专项练习卷，清空知识点选择，让用户手动选择
  if (template.id === 3) {
    knowledgeTreeRef.value?.setCheckedKeys([])
    selectedKnowledgePoints.value = []
    return
  }

  // 如果是模拟测试卷，自动选择所有知识点
  if (template.id === 2) {
    await selectAllKnowledgePoints()
  }
}

export const handleCustomModeChange = (checked: boolean) => {
  if (checked) {
    selectedTemplate.value = null
    // 自定义模式：清空知识点选择，让用户手动选择
    knowledgeTreeRef.value?.setCheckedKeys([])
    selectedKnowledgePoints.value = []
  }
}
