// ============
// Paper Operations Module for useAutoPaper
// ============
// Handles paper CRUD operations: save draft, publish, export, replace question.

import { ElMessage, ElMessageBox } from 'element-plus'
import { paperAPI } from '@/api'
import {
  paperForm,
  questionTypeConfig,
  selectedKnowledgePoints,
  skipKnowledgePoints,
  generatedQuestions,
  currentPaperId
} from './useAutoPaperCore'

// ============ Paper CRUD Operations ============

export const saveDraft = async () => {
  if (!paperForm.title) {
    ElMessage.warning('请先填写试卷名称')
    return
  }

  try {
    const paperData = {
      title: paperForm.title,
      subject_id: paperForm.subjectId,
      total_time: paperForm.duration,
      passing_score: paperForm.passScore,
      description: paperForm.showAnswer ? '显示答案' : '',
      config: {
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
      },
      status: 0,  // draft
      paper_type: 2,  // random
      questions: generatedQuestions.value.map((q, index) => ({
        question_id: q.id,
        order: index,
        score: q.score
      }))
    }

    let res
    if (currentPaperId.value) {
      res = await paperAPI.updatePaper(currentPaperId.value, paperData)
      ElMessage.success('草稿更新成功')
    } else {
      res = await paperAPI.createPaper(paperData)
      currentPaperId.value = res.data.id
      ElMessage.success('草稿保存成功')
    }
  } catch (error) {
    console.error('保存草稿失败:', error)
    ElMessage.error('保存草稿失败，请重试')
  }
}

export const publishPaper = async () => {
  if (!currentPaperId.value) {
    ElMessage.warning('请先生成试卷')
    return
  }

  try {
    await ElMessageBox.confirm('确认发布此试卷？发布后将无法修改。', '确认发布', {
      type: 'warning'
    })

    const res = await paperAPI.publishPaper(currentPaperId.value)
    ElMessage.success('试卷发布成功')
    currentPaperId.value = res.data.id
  } catch (error) {
    if (error !== 'cancel') {
      console.error('发布试卷失败:', error)
      ElMessage.error('发布试卷失败，请重试')
    }
  }
}

export const exportWord = async () => {
  if (!currentPaperId.value) {
    ElMessage.warning('请先生成试卷')
    return
  }

  try {
    const res = await paperAPI.exportPaper(currentPaperId.value, 'word')
    const blob = new Blob([res.data], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${paperForm.title || '试卷'}.docx`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (error) {
    console.error('导出Word失败:', error)
    ElMessage.error('导出失败，请重试')
  }
}

export const exportPdf = async () => {
  if (!currentPaperId.value) {
    ElMessage.warning('请先生成试卷')
    return
  }

  try {
    const res = await paperAPI.exportPaper(currentPaperId.value, 'pdf')
    const blob = new Blob([res.data], { type: 'application/pdf' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${paperForm.title || '试卷'}.pdf`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (error) {
    console.error('导出PDF失败:', error)
    ElMessage.error('导出失败，请重试')
  }
}

export const replaceQuestion = async (index: number) => {
  const currentQuestion = generatedQuestions.value[index]
  if (!currentQuestion) return

  try {
    // 查找同知识点、同题型、同难度的题目
    const kpIds = skipKnowledgePoints.value ? [] : selectedKnowledgePoints.value.map(kp => kp.id)
    const res = await paperAPI.getAutoGeneratePreview({
      subject_id: paperForm.subjectId,
      knowledge_point_ids: kpIds,
      question_type_config: {
        [currentQuestion.type]: { count: 1 }
      },
      difficulty_config: {
        [currentQuestion.difficulty]: 1
      },
      total_score: paperForm.totalScore
    })

    const availableQuestions = res.data?.questions || []
    // 过滤掉已使用的题目
    const usedIds = new Set(generatedQuestions.value.map(q => q.id))
    const candidateQuestions = availableQuestions.filter((q: any) => !usedIds.has(q.id))

    if (candidateQuestions.length === 0) {
      ElMessage.warning('没有可替换的题目')
      return
    }

    // 随机选择一个
    const randomIndex = Math.floor(Math.random() * candidateQuestions.length)
    const newQuestion = candidateQuestions[randomIndex]

    generatedQuestions.value[index] = {
      ...newQuestion,
      examPaperQuestionId: currentQuestion.examPaperQuestionId
    }

    ElMessage.success('题目已替换')
  } catch (error) {
    console.error('替换题目失败:', error)
    ElMessage.error('替换题目失败，请重试')
  }
}

export const removeQuestion = (index: number) => {
  if (index < 0 || index >= generatedQuestions.value.length) return
  generatedQuestions.value.splice(index, 1)
  ElMessage.success('题目已移除')
}
