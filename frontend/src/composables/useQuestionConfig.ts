// ============
// Question Config Module for useAutoPaper
// ============
// Handles question type configuration, difficulty adjustment, and weight callbacks.

import { ElMessage } from 'element-plus'
import { paperAPI } from '@/api'
import { getTypeName } from './useAutoPaperTypes'
import {
  questionTypeConfig,
  paperForm,
  selectedKnowledgePoints,
  skipKnowledgePoints,
  totalWeight,
  totalQuestionCount,
  totalConfiguredScore
} from './useAutoPaperCore'

// ============ Difficulty ============

export const autoAdjustDifficulty = async () => {
  if (!paperForm.subjectId) {
    ElMessage.warning('请先选择考试科目')
    return
  }

  // 检查是否有选中的知识点（如果不选择知识点则跳过此检查）
  if (!skipKnowledgePoints.value && selectedKnowledgePoints.value.length === 0) {
    ElMessage.warning('请先选择知识点')
    return
  }

  try {
    const kpIds = skipKnowledgePoints.value ? [] : selectedKnowledgePoints.value.map((kp) => kp.id)
    const questionTypes = questionTypeConfig.map((t) => t.type).filter((t) => t)

    const res = await paperAPI.getDifficultyDistribution({
      subject_id: paperForm.subjectId,
      knowledge_point_ids: kpIds,
      question_types: questionTypes
    })

    const data = res.data
    console.log('题库难度分布:', data)

    if (data.total === 0) {
      ElMessage.warning('题库中没有找到符合条件的题目')
      return
    }

    // 应用建议的难度分布到每个题型配置
    // 每种题型使用独立的难度分布
    questionTypeConfig.forEach((t) => {
      if (t.count > 0 && data.suggestions[t.type]) {
        const suggestion = data.suggestions[t.type]
        t.easyRatio = suggestion.easy_ratio
        t.mediumRatio = suggestion.medium_ratio
        t.hardRatio = suggestion.hard_ratio
      }
    })

    // 生成各题型的难度分布提示信息
    const distInfo = Object.entries(data.suggestions)
      .filter(([type]) => data.by_question_type[type]?.total > 0)
      .map(([type, d]: [string, any]) => `${getTypeName(type)}易${d.easy_ratio}%/中${d.medium_ratio}%/难${d.hard_ratio}%`)
      .join('；')

    ElMessage.success(`已根据题库自动调整各题型难度分布（${distInfo}），题库共有${data.total}题`)
  } catch (error) {
    console.error('获取难度分布失败:', error)
    ElMessage.error('获取题库难度分布失败，请手动设置')
  }
}

// ============ Weight/Count/Score Callbacks ============

export const handleWeightChange = () => {
  // el-slider 已通过 v-model 绑定 kp.weight 并限制 0-100；此处仅做总量校验提示
  if (totalWeight.value > 100) {
    ElMessage.warning('知识点总权重超过 100%，请调整或使用自动平衡')
  }
}

export const calculateTotalQuestions = () => {
  // 题目总量由 computed totalQuestionCount 实时计算，回调保留以兼容模板 @change 绑定
  return totalQuestionCount.value
}

export const calculateTotalScore = () => {
  // 配置总分由 computed totalConfiguredScore 实时计算，回调保留以兼容模板 @change 绑定
  return totalConfiguredScore.value
}
