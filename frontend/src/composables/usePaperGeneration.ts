// ============
// Paper Generation Module for useAutoPaper
// ============
// Handles paper generation, preview, and A/B paper generation.

import { ElMessage, ElMessageBox } from 'element-plus'
import { paperAPI } from '@/api'
import { getTypeName, getDifficultyLevel, getDifficultyNameByLevel } from './useAutoPaperTypes'
import {
  paperForm,
  questionTypeConfig,
  selectedKnowledgePoints,
  skipKnowledgePoints,
  generatedQuestions,
  currentPaperId,
  currentStep,
  generating,
  generationProgress,
  generationStatus,
  previewVisible,
  previewData
} from './useAutoPaperCore'

// ============ Paper Generation ============

export const previewGeneration = async () => {
  if (!paperForm.subjectId) {
    ElMessage.warning('请先选择考试科目')
    return
  }

  try {
    generationProgress.value = 10
    generationStatus.value = '正在分析题库...'

    const kpIds = skipKnowledgePoints.value ? [] : selectedKnowledgePoints.value.map((kp) => kp.id)
    const questionTypes = questionTypeConfig.map((t) => t.type).filter((t: any) => t.count > 0)

    const res = await paperAPI.getAutoGeneratePreview({
      subject_id: paperForm.subjectId,
      knowledge_point_ids: kpIds,
      question_type_config: questionTypeConfig.reduce((acc, t) => {
        if (t.count > 0) acc[t.type] = { count: t.count }
        return acc
      }, {} as Record<string, any>),
      difficulty_config: {
        easy: questionTypeConfig.reduce((sum, t) => sum + t.easyRatio * t.count, 0),
        medium: questionTypeConfig.reduce((sum, t) => sum + t.mediumRatio * t.count, 0),
        hard: questionTypeConfig.reduce((sum, t) => sum + t.hardRatio * t.count, 0)
      },
      total_score: paperForm.totalScore
    })

    generationProgress.value = 100
    generationStatus.value = '预览完成'

    previewData.value = res.data
    previewVisible.value = true

    // 显示可用题目统计
    const totalAvailable = res.data?.total_available || 0
    const byType = res.data?.by_type || {}
    const typeStats = Object.entries(byType)
      .map(([type, info]: [string, any]) => `${getTypeName(type)}: ${info.count || 0}题`)
      .join('，')

    if (totalAvailable === 0) {
      ElMessage.warning('题库中没有符合条件的题目，请调整配置')
    } else {
      ElMessage.success(`题库预览：共${totalAvailable}题可用（${typeStats}）`)
    }
  } catch (error) {
    console.error('预览失败:', error)
    ElMessage.error('预览失败，请重试')
    generationProgress.value = 0
    generationStatus.value = ''
  }
}

export const generateQuestions = async () => {
  generating.value = true
  generationProgress.value = 0
  generationStatus.value = '正在初始化...'

  try {
    // 先进行预览
    await previewGeneration()
    if (!previewData.value) return

    await ElMessageBox.confirm(
      `题库中共有 ${previewData.value.total_available || 0} 题符合条件，是否开始组卷？`,
      '确认组卷',
      { type: 'info' }
    )

    // 构建题型配置（包含数量和每题分值）
    const questionTypeConfigBuild: Record<string, { count: number; score: number }> = {}
    questionTypeConfig.forEach((t) => {
      if (t.count > 0) {
        questionTypeConfigBuild[t.type] = {
          count: t.count,
          score: t.score
        }
      }
    })

    // 构建难度配置 - 根据各题型的难度比例计算
    const difficultyConfig = {
      easy: 0,
      medium: 0,
      hard: 0
    }
    let totalRatio = 0
    questionTypeConfig.forEach((t) => {
      const typeTotal = t.easyRatio + t.mediumRatio + t.hardRatio
      if (typeTotal > 0) {
        difficultyConfig.easy += t.count * t.easyRatio / 100
        difficultyConfig.medium += t.count * t.mediumRatio / 100
        difficultyConfig.hard += t.count * t.hardRatio / 100
        totalRatio += typeTotal
      }
    })
    // 归一化
    if (totalRatio > 0) {
      difficultyConfig.easy = difficultyConfig.easy / (totalRatio / 100)
      difficultyConfig.medium = difficultyConfig.medium / (totalRatio / 100)
      difficultyConfig.hard = difficultyConfig.hard / (totalRatio / 100)
    }

    // 构建请求数据
    // exam_types.id 直接对应后端的 subject_id
    const requestData = {
      title: paperForm.title,
      subject_id: paperForm.subjectId,
      total_time: paperForm.duration,
      passing_score: paperForm.passScore,
      description: paperForm.showAnswer ? '显示答案' : '',
      knowledge_point_ids: skipKnowledgePoints.value ? [] : selectedKnowledgePoints.value.map((kp) => kp.id),
      question_type_config: questionTypeConfigBuild,
      difficulty_config: difficultyConfig
    }

    console.log('发送智能组卷请求:', requestData)

    // 开始生成 - 模拟进度（后端同步处理，前端模拟进度）
    generationProgress.value = 20
    generationStatus.value = '正在分配题目...'

    // 调用后端API
    const res = await paperAPI.autoGenerate(requestData)
    console.log('智能组卷响应:', res.data)

    generationProgress.value = 80
    generationStatus.value = '正在生成试卷...'

    // 检查是否有题型短缺通知
    if (res.data?.shortage_notice) {
      ElMessage.warning(res.data.shortage_notice)
    }

    // 处理返回数据 - PaperDetailResponse 格式
    if (res.data && res.data.questions && res.data.questions.length > 0) {
      currentPaperId.value = res.data.id

      generatedQuestions.value = res.data.questions.map((epq: any, index: number) => {
        const q = epq.question
        return {
          id: q.id || index + 1,
          examPaperQuestionId: epq.id,
          type: q.question_type,
          typeName: getTypeName(q.question_type),
          difficulty: getDifficultyLevel(q.difficulty),
          difficultyName: getDifficultyNameByLevel(getDifficultyLevel(q.difficulty)),
          content: q.content,
          options: q.options || [],
          answer: q.answer,
          score: epq.score,
          knowledgePoint: selectedKnowledgePoints.value.find((kp) => kp.id === q.chapter_id)?.label || ''
        }
      })

      console.log('生成的题目:', generatedQuestions.value)

      if (res.data.shortage_notice) {
        ElMessage.warning('题目分配完成，但部分题型数量不足！')
      } else {
        ElMessage.success('题目分配完成！')
      }
      currentStep.value = 4
    } else {
      ElMessage.warning('未找到符合条件的题目，请调整配置')
      generationProgress.value = 0
      generationStatus.value = ''
      return
    }
  } catch {
    // 用户取消
  } finally {
    generating.value = false
    generationProgress.value = 100
    generationStatus.value = '完成'
    setTimeout(() => {
      generationProgress.value = 0
      generationStatus.value = ''
    }, 2000)
  }
}

// ============ A/B 卷生成 ============

export const generateABPapers = async () => {
  if (!paperForm.subjectId) {
    ElMessage.warning('请先选择考试科目')
    return
  }

  try {
    await ElMessageBox.confirm(
      '将生成 A/B 两套平行卷，题目不重复，难度分布一致。是否继续？',
      '生成 A/B 卷',
      { type: 'info' }
    )

    generating.value = true
    generationProgress.value = 10
    generationStatus.value = '正在生成 A 卷...'

    // 构建请求数据
    const questionTypeConfigBuild: Record<string, { count: number; score: number }> = {}
    questionTypeConfig.forEach((t) => {
      if (t.count > 0) {
        questionTypeConfigBuild[t.type] = {
          count: t.count,
          score: t.score
        }
      }
    })

    const difficultyConfig = {
      easy: 0,
      medium: 0,
      hard: 0
    }
    let totalRatio = 0
    questionTypeConfig.forEach((t) => {
      const typeTotal = t.easyRatio + t.mediumRatio + t.hardRatio
      if (typeTotal > 0) {
        difficultyConfig.easy += t.count * t.easyRatio / 100
        difficultyConfig.medium += t.count * t.mediumRatio / 100
        difficultyConfig.hard += t.count * t.hardRatio / 100
        totalRatio += typeTotal
      }
    })
    if (totalRatio > 0) {
      difficultyConfig.easy = difficultyConfig.easy / (totalRatio / 100)
      difficultyConfig.medium = difficultyConfig.medium / (totalRatio / 100)
      difficultyConfig.hard = difficultyConfig.hard / (totalRatio / 100)
    }

    const requestData = {
      title: paperForm.title,
      subject_id: paperForm.subjectId,
      total_time: paperForm.duration,
      passing_score: paperForm.passScore,
      description: paperForm.showAnswer ? '显示答案' : '',
      knowledge_point_ids: skipKnowledgePoints.value ? [] : selectedKnowledgePoints.value.map((kp) => kp.id),
      question_type_config: questionTypeConfigBuild,
      difficulty_config: difficultyConfig
    }

    // 调用A/B卷生成接口
    const res = await paperAPI.autoGenerateAB(requestData)
    generationProgress.value = 100
    generationStatus.value = 'A/B 卷生成完成'

    if (res.data && res.data.paper_a && res.data.paper_b) {
      // 显示A/B卷选择对话框
      showABPaperSelection(res.data)
    } else {
      ElMessage.warning('生成A/B卷失败，请重试')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('生成A/B卷失败:', error)
      ElMessage.error('生成A/B卷失败，请重试')
    }
  } finally {
    generating.value = false
    generationProgress.value = 0
    generationStatus.value = ''
  }
}

// 显示A/B卷选择对话框
const showABPaperSelection = (abData: any) => {
  const paperA = abData.paper_a
  const paperB = abData.paper_b

  ElMessageBox.confirm(
    `A/B 两卷已生成成功！\n\nA卷：${paperA.title}（${paperA.questions?.length || 0}题）\nB卷：${paperB.title}（${paperB.questions?.length || 0}题）\n\n请选择要使用的试卷：`,
    'A/B 卷生成成功',
    {
      dangerouslyUseHTMLString: true,
      confirmButtonText: '使用 A 卷',
      cancelButtonText: '使用 B 卷',
      showCancelButton: true,
      showClose: false,
      closeOnClickModal: false,
      closeOnPressEscape: false,
    }
  ).then(() => {
    // 用户选择A卷
    loadPaperIntoPreview(paperA)
    ElMessage.success('已加载 A 卷')
  }).catch(() => {
    // 用户选择B卷
    loadPaperIntoPreview(paperB)
    ElMessage.success('已加载 B 卷')
  })
}

// 将试卷加载到预览中
const loadPaperIntoPreview = (paper: any) => {
  currentPaperId.value = paper.id
  generatedQuestions.value = paper.questions.map((epq: any, index: number) => {
    const q = epq.question
    return {
      id: q.id || index + 1,
      examPaperQuestionId: epq.id,
      type: q.question_type,
      typeName: getTypeName(q.question_type),
      difficulty: getDifficultyLevel(q.difficulty),
      difficultyName: getDifficultyNameByLevel(getDifficultyLevel(q.difficulty)),
      content: q.content,
      options: q.options || [],
      answer: q.answer,
      score: epq.score,
      knowledgePoint: selectedKnowledgePoints.value.find((kp) => kp.id === q.chapter_id)?.label || ''
    }
  })
  currentStep.value = 4
}
