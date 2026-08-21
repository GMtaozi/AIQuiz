/**
 * Composable for AI question generation logic
 *
 * Encapsulates the hybrid/rule-only generation workflow:
 * 1. Create async generation task
 * 2. Poll for progress
 * 3. Process completed questions
 * 4. Submit to question bank
 */
import { ref, reactive, computed, nextTick, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminAPI } from '@/api'
import type { QuestionNode } from '@/types/knowledge'

// Type map: frontend label → backend enum
const TYPE_MAP = {
  choice: 'single_choice',
  multiple: 'multiple_choice',
  judge: 'true_false',
  short_answer: 'essay',
}

// Difficulty map: frontend label → backend number
const DIFFICULTY_MAP = { easy: 2, medium: 3, hard: 4, mixed: 3 }
const DIFFICULTY_NUM_MAP = { 1: 'easy', 2: 'easy', 3: 'medium', 4: 'hard', 5: 'hard' }

// Status text/tag maps
const STATUS_TEXT_MAP = { pending: '等待中', running: '生成中', completed: '已完成', failed: '已失败' }
const STATUS_TAG_MAP = { pending: 'info', running: 'warning', completed: 'success', failed: 'danger' }
const TASK_STATUS_TEXT_MAP = { pending: '等待', running: '进行中', completed: '完成', failed: '失败' }
const TASK_STATUS_TAG_MAP = { pending: 'info', running: 'warning', completed: 'success', failed: 'danger' }

export interface GeneratedQuestion {
  id: string
  type: string
  difficulty: string
  content: string
  selected: boolean
  options: string[] | null
  answer: string
  explanation: string
  knowledgePoints: string[]
  _raw: Record<string, any>
  _questionType: string
  _difficultyNum: number
  _knowledgePointIds: number[]
}

export interface GenerationTask {
  id: string
  createdAt: string
  config: { subject: string; quantity: number }
  status: string
  progress: number
  resultCount: number
}

export interface UseGenerationOptions {
  /** Callback when questions are generated and ready */
  onQuestionsGenerated?: (questions: GeneratedQuestion[]) => void
  /** Callback when generation fails */
  onGenerationFailed?: (error: Error) => void
  /** Callback for log messages */
  onLog?: (message: string, type?: string) => void
}

export function useGeneration(options: UseGenerationOptions = {}) {
  // Generation state
  const generating = ref(false)
  const generationStatus = ref('')
  const currentTaskId = ref('')
  const progressPercentage = ref(0)
  const progressStatus = ref('')
  const remainingTime = ref('')
  const startTime = ref('')
  const generatedQuestions = ref<GeneratedQuestion[]>([])
  const failedQuestions = ref<GeneratedQuestion[]>([])
  const historyTasks = ref<GenerationTask[]>([])
  const historyFilter = ref('')

  // Timer handles
  const timerHandles = reactive({ progressInterval: null as number | null, pollTimer: null as number | null })
  const isGeneratingCancelled = ref(false)

  // Logs
  const logs = ref<{ time: string; message: string; type: string }[]>([])
  const logContainerRef = ref<HTMLElement | null>(null)

  // Computed
  const statusText = computed(() => STATUS_TEXT_MAP[generationStatus.value as keyof typeof STATUS_TEXT_MAP] || '等待中')
  const statusTagType = computed(() => STATUS_TAG_MAP[generationStatus.value as keyof typeof STATUS_TAG_MAP] || 'info')
  const filteredHistoryTasks = computed(() => {
    if (!historyFilter.value) return historyTasks.value
    return historyTasks.value.filter(task => task.status === historyFilter.value)
  })

  const addLog = (message: string, type = 'info') => {
    const now = new Date()
    const time = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`
    logs.value.push({ time, message, type })
    options.onLog?.(message, type)

    nextTick(() => {
      if (logContainerRef.value) {
        logContainerRef.value.scrollTop = logContainerRef.value.scrollHeight
      }
    })
  }

  const clearLogs = () => {
    logs.value = []
  }

  // Collect selected knowledge point IDs from tree
  const collectSelectedKpIds = (knowledgeTreeRef: any, selectedKpNodes: any[]): number[] => {
    const selectedKpIds = selectedKpNodes.map(n => n.id).filter(id => typeof id === 'number')

    if (selectedKpIds.length === 0) {
      const halfCheckedNodes = knowledgeTreeRef?.getHalfCheckedNodes() || []
      const collectChildIds = (nodes: any[]) => {
        for (const n of nodes) {
          if (typeof n.id === 'number') selectedKpIds.push(n.id)
          if (n.children) collectChildIds(n.children)
        }
      }
      collectChildIds(halfCheckedNodes)
    }

    return selectedKpIds
  }

  // Convert backend question to frontend format
  const convertQuestion = (q: any, idx: number, selectedKpNodes: any[], selectedKpIds: number[], baseDifficulty: number): GeneratedQuestion => {
    const frontType = Object.keys(TYPE_MAP).find(k => TYPE_MAP[k as keyof typeof TYPE_MAP] === q.question_type) || 'choice'
    return {
      id: `Q-${Date.now()}-${idx}`,
      type: frontType,
      difficulty: DIFFICULTY_NUM_MAP[q.difficulty as keyof typeof DIFFICULTY_NUM_MAP] || 'medium',
      content: q.content || '',
      selected: false,
      options: q.options ? q.options.map((o: any) => (typeof o === 'string' ? o : (o.option_content || o.option_label || ''))) : null,
      answer: q.answer || '',
      explanation: q.explanation || '',
      knowledgePoints: selectedKpNodes.map(n => n.label),
      _raw: q,
      _questionType: q.question_type || TYPE_MAP[frontType as keyof typeof TYPE_MAP],
      _difficultyNum: q.difficulty || baseDifficulty,
      _knowledgePointIds: selectedKpIds,
    }
  }

  // Build API request body
  const buildRequestBody = (
    configForm: Record<string, any>,
    selectedKpIds: number[],
    examTypeOptions: any[],
    selectedKpNodes: any[],
    subjectName: string,
    baseDifficulty: number
  ): Record<string, any> => {
    const questionTypeList = (configForm.questionTypes || []).map((t: string) => TYPE_MAP[t as keyof typeof TYPE_MAP] || 'single_choice')

    const currentExamType = examTypeOptions.find((e: any) => e.id === configForm.examTypeId)
    let effectiveSubjectId = currentExamType?.subject_id || 1
    const firstNodeWithExamType = selectedKpNodes.find((n: any) => n.exam_type_id)
    if (firstNodeWithExamType?.exam_type_id) {
      const kpExamType = examTypeOptions.find((e: any) => e.id === firstNodeWithExamType.exam_type_id)
      if (kpExamType?.subject_id) {
        effectiveSubjectId = kpExamType.subject_id
      }
    }

    return {
      subject_id: effectiveSubjectId,
      subject_name: subjectName || '通用',
      chapter_ids: [],
      chapter_names: [],
      question_types: questionTypeList,
      difficulty: Number(baseDifficulty),
      count: Math.max(1, Number(configForm.quantity)),
      knowledge_point_ids: selectedKpIds.map(id => Number(id)).filter(id => !isNaN(id)),
      mode: configForm.generationMode,
    }
  }

  // Poll task progress
  const pollTaskProgress = async (
    taskId: number,
    configForm: Record<string, any>,
    selectedKpNodes: any[],
    selectedKpIds: number[],
    baseDifficulty: number,
  ): Promise<GeneratedQuestion[]> => {
    const allQuestions: GeneratedQuestion[] = []
    const isRuleOnly = configForm.generationMode === 'rule_only'
    const pollInterval = isRuleOnly ? 500 : 2000
    const maxPolls = 180
    let pollCount = 0
    let progressUpdated = false

    return new Promise((resolve, reject) => {
      timerHandles.pollTimer = setInterval(async () => {
        if (isGeneratingCancelled.value) {
          clearInterval(timerHandles.pollTimer as any)
          clearInterval(timerHandles.progressInterval as any)
          reject(new Error('用户取消'))
          return
        }

        pollCount++
        try {
          const progressRes = await adminAPI.getTaskProgress(taskId)
          const taskData = progressRes.data

          // Stop local simulation and use backend progress
          if (!(timerHandles.progressInterval as any)?._backendProgressReceived) {
            (timerHandles.progressInterval as any)._backendProgressReceived = true
          }
          progressUpdated = true
          progressPercentage.value = taskData.progress

          if (taskData.status === 'completed') {
            clearInterval(timerHandles.pollTimer as any)
            clearInterval(timerHandles.progressInterval as any)
            progressPercentage.value = 100

            try {
              const questions = taskData.questions || []
              addLog(
                `出题完成：规则 ${taskData.rule_questions} 题 + AI ${taskData.ai_questions} 题 = ${questions.length} 题`,
                questions.length < configForm.quantity ? 'warning' : 'success'
              )

              for (let idx = 0; idx < questions.length; idx++) {
                allQuestions.push(convertQuestion(questions[idx], idx, selectedKpNodes, selectedKpIds, baseDifficulty))
              }
            } catch (processErr) {
              console.error('[AI出题] 处理完成结果失败:', processErr)
            }

            resolve(allQuestions)
          } else if (taskData.status === 'failed') {
            clearInterval(timerHandles.pollTimer as any)
            clearInterval(timerHandles.progressInterval as any)
            addLog(`出题失败: ${taskData.error_message || '未知错误'}`, 'error')
            reject(new Error(taskData.error_message || '出题失败'))
          } else if (pollCount >= maxPolls) {
            clearInterval(timerHandles.pollTimer as any)
            clearInterval(timerHandles.progressInterval as any)
            addLog('轮询超时，任务可能仍在后台执行', 'warning')
            reject(new Error('轮询超时'))
          }
        } catch (pollErr) {
          console.error('[AI出题] 轮询失败:', pollErr)
          if (pollCount >= maxPolls) {
            clearInterval(timerHandles.pollTimer as any)
            clearInterval(timerHandles.progressInterval as any)
            reject(pollErr)
          }
        }
      }, pollInterval)
    })
  }

  // Start generation
  const startGeneration = async (
    configForm: Record<string, any>,
    knowledgeTreeRef: any,
    selectedKpNodes: any[],
    examTypeOptions: any[],
    categoryOptions: any[],
  ) => {
    if (!configForm.categoryId) {
      ElMessage.warning('请选择考试种类')
      return
    }
    if (!configForm.examTypeId) {
      ElMessage.warning('请选择考试科目')
      return
    }
    if ((configForm.questionTypes || []).length === 0) {
      ElMessage.warning('请至少选择一种题型')
      return
    }

    const selectedKpIds = collectSelectedKpIds(knowledgeTreeRef, selectedKpNodes)
    if (selectedKpIds.length === 0) {
      ElMessage.warning('请至少选择一个知识点')
      return
    }

    generating.value = true
    generationStatus.value = 'running'
    progressPercentage.value = 0
    progressStatus.value = ''
    generatedQuestions.value = []
    clearLogs()
    isGeneratingCancelled.value = false

    // Cleanup old timers
    if (timerHandles.progressInterval) { clearInterval(timerHandles.progressInterval); timerHandles.progressInterval = null }
    if (timerHandles.pollTimer) { clearInterval(timerHandles.pollTimer); timerHandles.pollTimer = null }

    const now = new Date()
    currentTaskId.value = `TASK-${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}-${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}`
    startTime.value = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`
    remainingTime.value = '计算中...'

    addLog('任务已创建，正在准备知识点内容...', 'info')

    const currentCategory = categoryOptions.find(c => c.id === configForm.categoryId)
    const currentExamType = examTypeOptions.find(e => e.id === configForm.examTypeId)
    const subjectName = currentExamType?.name || currentCategory?.name || '通用'
    const baseDifficulty = DIFFICULTY_MAP[configForm.difficulty as keyof typeof DIFFICULTY_MAP] || 3

    try {
      const isRuleOnly = configForm.generationMode === 'rule_only'
      let progress = isRuleOnly ? 60 : 0
      let elapsedSeconds = 0

      timerHandles.progressInterval = setInterval(() => {
        if (isGeneratingCancelled.value) { clearInterval(timerHandles.progressInterval as any); return }
        if (!(timerHandles.progressInterval as any)?._backendProgressReceived) {
          if (isRuleOnly) {
            progress = Math.min(progress + 10, 95)
          } else {
            progress += Math.random() * 3
            if (progress > 95) progress = 95
          }
          progressPercentage.value = Math.round(progress)
        }
        elapsedSeconds++
        remainingTime.value = `已运行 ${elapsedSeconds} 秒`
        if (!isRuleOnly) {
          if (elapsedSeconds === 30) addLog('AI正在思考中，请耐心等待...', 'info')
          else if (elapsedSeconds === 60) addLog('AI响应较慢，继续等待...', 'warning')
          else if (elapsedSeconds === 120) addLog('等待时间较长，建议稍后重试', 'warning')
          else if (elapsedSeconds > 180 && elapsedSeconds % 60 === 0) addLog(`已等待 ${Math.floor(elapsedSeconds / 60)} 分钟`, 'warning')
        }
      }, isRuleOnly ? 200 : 1000)

      const modeNames = { hybrid: '智能混合', rule_only: '规则出题' }
      addLog(`使用${modeNames[configForm.generationMode as keyof typeof modeNames]}模式生成题目...`, 'info')

      const reqBody = buildRequestBody(configForm, selectedKpIds, examTypeOptions, selectedKpNodes, subjectName, baseDifficulty)

      if (reqBody.knowledge_point_ids.length === 0) {
        throw new Error('知识点ID为空，请确保知识点树数据正确加载后重试')
      }

      addLog(`请求参数：${reqBody.question_types.join('/')} × ${configForm.quantity}题，知识点ID ${reqBody.knowledge_point_ids.length} 个`, 'info')

      // Create async task
      const asyncRes = await adminAPI.hybridGenerateAsync(reqBody)
      const taskId = asyncRes.data?.task_id
      if (!taskId) throw new Error('创建出题任务失败：未返回任务ID')

      addLog(`出题任务已创建 (ID: ${taskId})，正在后台执行...`, 'info')
      currentTaskId.value = `TASK-${taskId}`

      // Poll for progress
      const questions = await pollTaskProgress(taskId, configForm, selectedKpNodes, selectedKpIds, baseDifficulty)

      clearInterval(timerHandles.progressInterval as any)
      timerHandles.progressInterval = null

      if (questions.length > 0) {
        progressPercentage.value = 100
        progressStatus.value = 'success'
        generationStatus.value = 'completed'
        remainingTime.value = '已完成'
        generatedQuestions.value = questions
        const actualCount = questions.length
        const targetCount = configForm.quantity
        if (actualCount < targetCount) {
          addLog(`题目生成完成！共 ${actualCount} 题（目标 ${targetCount} 题，缺少 ${targetCount - actualCount} 题）`, 'warning')
        } else {
          addLog(`所有题目生成完成！共 ${actualCount} 题`, 'success')
        }

        historyTasks.value.unshift({
          id: currentTaskId.value,
          createdAt: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`,
          config: { subject: subjectName, quantity: questions.length },
          status: 'completed',
          progress: 100,
          resultCount: questions.length
        })

        options.onQuestionsGenerated?.(questions)
      } else {
        throw new Error('AI生成失败，请检查网络或配置后重试')
      }
    } catch (e: any) {
      clearInterval(timerHandles.progressInterval as any)
      timerHandles.progressInterval = null
      progressPercentage.value = 0
      progressStatus.value = 'exception'
      generationStatus.value = 'failed'
      remainingTime.value = '失败'

      const errData = e.response?.data || {}
      const errMsg = errData.message || errData.detail
        ? (Array.isArray(errData.detail)
          ? errData.detail.map((d: any) => `${d.loc?.join('.')}: ${d.msg}`).join('; ')
          : String(errData.message || errData.detail))
        : e.message || '未知错误'
      addLog(`生成出错: ${errMsg}`, 'error')
      console.error('AI出题失败:', e)
      options.onGenerationFailed?.(e)
    } finally {
      generating.value = false
    }
  }

  // Cancel generation
  const cancelGeneration = async () => {
    isGeneratingCancelled.value = true
    if (timerHandles.progressInterval) { clearInterval(timerHandles.progressInterval); timerHandles.progressInterval = null }
    if (timerHandles.pollTimer) { clearInterval(timerHandles.pollTimer); timerHandles.pollTimer = null }
    generating.value = false
    generationStatus.value = ''
    progressPercentage.value = 0
    progressStatus.value = ''
    remainingTime.value = ''

    // 调用后端取消接口
    const taskIdStr = currentTaskId.value || ''
    const match = taskIdStr.match(/TASK-(\d+)/)
    if (match) {
      const taskId = Number(match[1])
      try {
        await adminAPI.cancelTask(taskId)
        addLog('已向后台发送取消请求', 'warning')
      } catch (e: any) {
        const errMsg = e?.response?.data?.message || e?.message || '取消请求失败'
        addLog(`取消请求失败: ${errMsg}`, 'error')
      }
    } else {
      addLog('已取消生成（本地）', 'warning')
    }
  }

  // Build question payload for API submission
  const buildQuestionPayload = (q: GeneratedQuestion): Record<string, any> => {
    let options = null
    if (q.options && (q.type === 'choice' || q.type === 'multiple')) {
      const labels = ['A', 'B', 'C', 'D']
      const correctAnswer = q.answer || ''
      options = q.options.map((optContent, idx) => ({
        option_label: labels[idx] || String(idx + 1),
        option_content: optContent,
        is_correct: correctAnswer.includes(labels[idx]),
        order: idx
      }))
    }

    return {
      chapter_id: null,
      subject_id: q._raw?.subject_id || 1,
      question_type: q._questionType || TYPE_MAP[q.type as keyof typeof TYPE_MAP] || 'single_choice',
      content: q.content,
      answer: q.answer,
      explanation: q.explanation,
      difficulty: q._difficultyNum || 3,
      score: q.type === 'short_answer' ? 10 : 5,
      is_public: false,
      tags: { knowledge_points: q.knowledgePoints || [], source: 'ai_generated' },
      meta: { knowledge_point_ids: q._knowledgePointIds || [] },
      status: 1,
      source: 'ai',
      is_ai_generated: true,
      options,
    }
  }

  // Submit selected questions
  const submitSelected = async () => {
    const selected = generatedQuestions.value.filter(q => q.selected)
    if (selected.length === 0) {
      ElMessage.warning('请先选择要提交的题目')
      return
    }

    const loading = ElMessage({ message: '正在提交题目到审核队列...', type: 'info', duration: 0 })
    let successCount = 0
    let failCount = 0

    for (const q of selected) {
      try {
        const payload = buildQuestionPayload(q)
        await adminAPI.createQuestion(payload)
        successCount++
      } catch (e: any) {
        console.error('提交题目失败:', e)
        failedQuestions.value.push({
          ...q,
          _error: e.message || '提交失败',
          _failedAt: new Date().toLocaleString()
        } as GeneratedQuestion & { _error?: string; _failedAt?: string })
        failCount++
      }
    }

    loading.close()

    if (successCount > 0) {
      ElMessage.success(`已提交 ${successCount} 道题目到审核队列${failCount > 0 ? `，${failCount} 道提交失败（已暂存）` : ''}`)
      generatedQuestions.value = generatedQuestions.value.filter(q => !q.selected)
    } else {
      ElMessage.error('提交失败，请修复问题后重试暂存的题目')
    }
  }

  // Retry failed questions
  const retryFailedQuestions = async () => {
    if (failedQuestions.value.length === 0) {
      ElMessage.warning('没有待重试的题目')
      return
    }

    const loading = ElMessage({ message: '正在重试提交...', type: 'info', duration: 0 })
    let successCount = 0
    const stillFailed: GeneratedQuestion[] = []

    for (const q of failedQuestions.value) {
      try {
        const payload = buildQuestionPayload(q)
        await adminAPI.createQuestion(payload)
        successCount++
      } catch (e: any) {
        console.error('重试提交题目失败:', e)
        stillFailed.push({
          ...q,
          _error: e.message || '提交失败',
          _failedAt: new Date().toLocaleString()
        } as GeneratedQuestion & { _error?: string; _failedAt?: string })
      }
    }

    failedQuestions.value = stillFailed
    loading.close()

    if (successCount > 0) {
      ElMessage.success(`重试成功 ${successCount} 道题目${stillFailed.length > 0 ? `，${stillFailed.length} 道仍失败` : ''}`)
    } else {
      ElMessage.error('重试全部失败，请检查问题')
    }
  }

  // Edit a single question
  const editQuestion = (index: number, generatedQuestionsRef: any, editingQuestion: any, editDialogVisible: any) => {
    const question = generatedQuestionsRef.value[index]
    const editingIndex = index
    Object.assign(editingQuestion, {
      content: question.content,
      type: question.type,
      difficulty: question.difficulty,
      optionA: question.options?.[0] || '',
      optionB: question.options?.[1] || '',
      optionC: question.options?.[2] || '',
      optionD: question.options?.[3] || '',
      answer: question.answer
    })
    editDialogVisible.value = true
    return editingIndex
  }

  // Save edited question
  const saveEditedQuestion = (index: number, editingQuestion: any, generatedQuestionsRef: any, editDialogVisible: any) => {
    const question = generatedQuestionsRef.value[index]
    question.content = editingQuestion.content
    question.type = editingQuestion.type
    question.difficulty = editingQuestion.difficulty
    question.answer = editingQuestion.answer

    if (editingQuestion.type === 'choice' || editingQuestion.type === 'multiple') {
      question.options = [editingQuestion.optionA, editingQuestion.optionB, editingQuestion.optionC, editingQuestion.optionD]
    }

    editDialogVisible.value = false
    ElMessage.success('题目已保存')
  }

  const deleteQuestion = (index: number, generatedQuestionsRef: any) => {
    ElMessageBox.confirm('确定要删除这道题目吗？', '提示', { type: 'warning' })
      .then(() => {
        generatedQuestionsRef.value.splice(index, 1)
        ElMessage.success('题目已删除')
      })
      .catch(() => {})
  }

  const deleteSelected = (generatedQuestionsRef: any) => {
    const selected = generatedQuestionsRef.value.filter((q: any) => q.selected)
    if (selected.length === 0) {
      ElMessage.warning('请先选择要删除的题目')
      return
    }

    ElMessageBox.confirm(`确定要删除选中的${selected.length}道题目吗？`, '提示', { type: 'warning' })
      .then(() => {
        generatedQuestionsRef.value = generatedQuestionsRef.value.filter((q: any) => !q.selected)
        ElMessage.success('题目已删除')
      })
      .catch(() => {})
  }

  const viewTaskResult = (task: GenerationTask) => {
    ElMessage.info(`查看任务 ${task.id} 的结果`)
  }

  const regenerateTask = async (task: GenerationTask) => {
    ElMessageBox.confirm(`确定要重新生成任务 ${task.id} 吗？`, '提示', { type: 'info' })
      .then(async () => {
        // 提取 task.id 中的数字任务ID
        const match = task.id.match(/(\d+)/)
        if (!match) {
          ElMessage.error('无效的任务ID格式')
          return
        }
        const originalTaskId = Number(match[1])
        task.status = 'running'
        task.progress = 0
        generationStatus.value = 'running'
        generating.value = true
        progressPercentage.value = 0
        addLog(`正在重新生成任务 ${task.id}...`, 'info')

        try {
          const res = await adminAPI.regenerateTask(originalTaskId)
          const newTaskId = res.data?.task_id
          if (!newTaskId) throw new Error('未返回新任务ID')
          currentTaskId.value = `TASK-${newTaskId}`
          addLog(`重新生成任务已创建 (新ID: ${newTaskId})，正在后台执行...`, 'success')

          // 轮询新任务进度
          const questions = await pollTaskProgress(newTaskId, { generationMode: 'hybrid', quantity: 10 }, [], [], 3)
          if (questions.length > 0) {
            addLog(`重新生成完成！共 ${questions.length} 题`, 'success')
            generatedQuestions.value = questions
            options.onQuestionsGenerated?.(questions)
          }
        } catch (e: any) {
          const errMsg = e?.response?.data?.message || e?.message || '重新生成失败'
          addLog(`重新生成失败: ${errMsg}`, 'error')
          task.status = 'failed'
          task.progress = 0
          generationStatus.value = 'failed'
          generating.value = false
          progressPercentage.value = 0
        }
      })
      .catch(() => {})
  }

  // Cleanup on unmount
  onUnmounted(() => {
    if (timerHandles.progressInterval) clearInterval(timerHandles.progressInterval)
    if (timerHandles.pollTimer) clearInterval(timerHandles.pollTimer)
  })

  return {
    // State
    generating,
    generationStatus,
    currentTaskId,
    progressPercentage,
    progressStatus,
    remainingTime,
    startTime,
    generatedQuestions,
    failedQuestions,
    historyTasks,
    historyFilter,
    logs,
    logContainerRef,
    isGeneratingCancelled,
    // Computed
    statusText,
    statusTagType,
    filteredHistoryTasks,
    // Actions
    addLog,
    clearLogs,
    startGeneration,
    cancelGeneration,
    submitSelected,
    retryFailedQuestions,
    editQuestion,
    saveEditedQuestion,
    deleteQuestion,
    deleteSelected,
    viewTaskResult,
    regenerateTask,
    // Helpers
    collectSelectedKpIds,
    convertQuestion,
    buildRequestBody,
    buildQuestionPayload,
    pollTaskProgress,
  }
}
