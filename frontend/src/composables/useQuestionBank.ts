import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminAPI, systemAPI, questionBankAPI } from '@/api'

// ============ Types ============
export interface Question {
  id: number
  question_type: string
  difficulty: number
  score: number
  content: string
  options: Array<{ option_content: string }>
  answer: string | string[]
  knowledge_point_ids?: number[]
  explanation?: string
  status: number
  created_at?: string
  meta?: Record<string, any>
}

export interface QuestionForm {
  id: number | null
  type: string
  difficulty: string
  score: number
  content: string
  options: Array<{ content: string }>
  correctAnswer: number
  judgeAnswer: boolean
  knowledgePointIds: number[]
  explanation: string
}

export interface ExportForm {
  format: string
  scope: string
  fields: string[]
}

export interface Pagination {
  page: number
  pageSize: number
  total: number
}

export interface FilterForm {
  categoryId: number | null
  examTypeId: number | null
  questionType: string
  difficulty: string
  status: number | null
}

export interface ImportResult {
  success: number
  failed: number
  errors?: string[]
}

export interface PreviewResult {
  questions: any[]
  errors?: string[]
}


// 状态
export const loading = ref(false)
export const searchKeyword = ref('')
export const questionList = ref<any[]>([])
export const selectedQuestions = ref<any[]>([])
// 考试种类和科目
export const categoryOptions = ref<any[]>([])
export const examTypeOptions = ref<any[]>([])
export const loadingCategories = ref(false)
export const loadingExamTypes = ref(false)
// 弹窗状态
export const questionDialogVisible = ref(false)
export const previewDialogVisible = ref(false)
export const importDialogVisible = ref(false)
export const exportDialogVisible = ref(false)
export const isEdit = ref(false)
export const submitLoading = ref(false)
export const currentQuestion = ref<any>(null)
// 导入相关
export const importTab = ref('excel')
export const importFormat = ref('excel')
export const importText = ref('')
export const importing = ref(false)
export const importProgress = ref(0)
export const importedCount = ref(0)
export const totalCount = ref(0)
export const importResult = ref<any>(null)
export const uploadRef = ref<any>(null)
export const selectedFile = ref<any>(null)
export const importCategoryId = ref(null)
export const importSubjectId = ref(null)
export const previewResult = ref(null)
// 导出相关
export const exportForm = reactive({
  format: 'excel',
  scope: 'filtered',
  fields: ['content', 'type', 'difficulty', 'answer']
})
// 分页
export const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})
// 筛选表单
export const filterForm = reactive({
  categoryId: null,
  examTypeId: null,
  questionType: '',
  difficulty: '',
  status: null
})
// 题目表单
export const questionForm = reactive({
  id: null,
  type: 'single',
  difficulty: 'medium',
  score: 5,
  content: '',
  options: [
    { content: '' },
    { content: '' },
    { content: '' },
    { content: '' }
  ],
  correctAnswer: 0,
  judgeAnswer: true,
  knowledgePointIds: [],
  explanation: ''
})
// 表单校验规则
export const formRules = {
  type: [{ required: true, message: '请选择题型', trigger: 'change' }],
  difficulty: [{ required: true, message: '请选择难度', trigger: 'change' }],
  content: [{ required: true, message: '请输入题目内容', trigger: 'blur' }]
}
// 计算属性
export const importProgressStatus = computed(() => {
  if (importProgress.value === 100) return 'success'
  return undefined
})
export const filteredExamTypeOptions = computed(() => {
  if (!filterForm.categoryId) return examTypeOptions.value
  return examTypeOptions.value.filter(et => et.category_id === filterForm.categoryId)
})
// 考试种类变化时清空考试科目
export const handleCategoryChange = () => {
  filterForm.examTypeId = null
}
// 注意：原模块顶层 onMounted 已移除（评估 P0-6）——模块顶层生命周期钩子不会注册到任何组件；
// 初始化由 QuestionBankView.vue 自身的 onMounted 负责（fetchCategories/fetchExamTypes/fetchQuestionList）。
// 获取考试种类
export const fetchCategories = async () => {
  loadingCategories.value = true
  try {
    const res = await systemAPI.getExamCategories()
    categoryOptions.value = res.data?.items || res.data || []
    console.log('考试种类数据:', JSON.stringify(categoryOptions.value, null, 2))
  } catch (e) {
    console.error('获取考试种类失败:', e)
  } finally {
    loadingCategories.value = false
  }
}
// 获取考试科目
export const fetchExamTypes = async () => {
  loadingExamTypes.value = true
  try {
    const res = await systemAPI.getExamTypes()
    // 支持多种返回结构
    examTypeOptions.value = res.data?.items || res.data || []
    console.log('考试科目数据:', JSON.stringify(examTypeOptions.value, null, 2))
  } catch (e) {
    console.error('获取考试科目失败:', e)
  } finally {
    loadingExamTypes.value = false
  }
}
// 获取题目列表
export const fetchQuestionList = async () => {
  loading.value = true
  try {
    // 转换题型: single -> single_choice, multiple -> multiple_choice, judge -> true_false, short_answer -> essay
    const typeMap = { single: 'single_choice', multiple: 'multiple_choice', judge: 'true_false', short_answer: 'essay' }
    // 转换难度: easy -> 2, medium -> 3, hard -> 4
    const difficultyMap = { easy: 2, medium: 3, hard: 4 }
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      keyword: searchKeyword.value || undefined,
      question_type: filterForm.questionType ? (typeMap[filterForm.questionType as keyof typeof typeMap] || filterForm.questionType) : undefined,
      difficulty: filterForm.difficulty ? (difficultyMap[filterForm.difficulty as keyof typeof difficultyMap] || parseInt(filterForm.difficulty)) : undefined,
      category_id: filterForm.categoryId || undefined,
      subject_id: filterForm.examTypeId || undefined,
      status: filterForm.status !== null ? filterForm.status : undefined
    }
    const response = await adminAPI.getQuestions(params)
    let list = response.data.items.map((item: any) => ({
      ...item,
      createTime: item.created_at || item.createTime,
      status: item.status ?? 1,
      knowledgePoints: item.knowledgePoints || [],
      meta: item.meta || {}
    }))
    // 排序：启用(1) > 待启用(2) > 禁用(0)
    list.sort((a: any, b: any) => {
    const order = { 1: 0, 2: 1, 0: 2 }
      return (order[a.status as keyof typeof order] ?? 3) - (order[b.status as keyof typeof order] ?? 3)
    })
    questionList.value = list
    pagination.total = response.data.total
  } catch (error) {
    ElMessage.error('获取题目列表失败')
  } finally {
    loading.value = false
  }
}
// 搜索
export const handleSearch = () => {
  pagination.page = 1
  fetchQuestionList()
}
// 分页
export const handleSizeChange = (val: any) => {
  pagination.pageSize = val
  fetchQuestionList()
}
export const handlePageChange = (val: any) => {
  pagination.page = val
  fetchQuestionList()
}
// 选择变化
export const handleSelectionChange = (selection: any) => {
  selectedQuestions.value = selection
}
// 状态切换
export const handleStatusChange = async (row: any) => {
  try {
    await adminAPI.updateQuestion(row.id, { status: row.status })
    ElMessage.success('状态更新成功')
  } catch (error) {
    ElMessage.error('状态更新失败')
    row.status = row.status === 1 ? 0 : 1
  }
}
// 批量操作
export const handleBatchCommand = (command: any) => {
  switch (command) {
    case 'import':
      showImportDialog()
      break
    case 'delete':
      if (selectedQuestions.value.length === 0) {
        ElMessage.warning('请先选择题目')
        return
      }
      handleBatchDelete()
      break
    case 'export':
      if (selectedQuestions.value.length === 0) {
        ElMessage.warning('请先选择题目')
        return
      }
      exportDialogVisible.value = true
      break
    case 'status':
      if (selectedQuestions.value.length === 0) {
        ElMessage.warning('请先选择题目')
        return
      }
      handleBatchStatusChange()
      break
  }
}
// 批量删除（软删除：直接禁用）
export const handleBatchDelete = () => {
  ElMessageBox.confirm(`确定要删除选中的 ${selectedQuestions.value.length} 道题目吗？删除后可在状态筛选中恢复。`, '提示', {
    type: 'warning'
  }).then(async () => {
    try {
      // 评估 P2-15：批量删除改用后端 batch 接口（一次请求 + 事务原子性 + 逐条权限校验），
      // 替代原先逐条 updateQuestion 的 N+1 请求。语义一致：软删除（status=0 禁用）。
      const ids = selectedQuestions.value.map(q => q.id)
      await adminAPI.batchDeleteQuestions(ids)
      ElMessage.success('删除成功（已禁用）')
      fetchQuestionList()
    } catch (error) {
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}
// 批量修改状态：启用(1)→待启用(2)，待启用(2)→启用(1)，禁用(0)不可操作
export const handleBatchStatusChange = () => {
  // 检查是否有禁用的题目
  const disabledQuestions = selectedQuestions.value.filter(q => q.status === 0)
  if (disabledQuestions.length > 0) {
    ElMessage.warning('选中的题目中包含禁用状态，无法修改')
    return
  }
  // 统计启用和待启用的数量
  const enabledCount = selectedQuestions.value.filter(q => q.status === 1).length
  const pendingCount = selectedQuestions.value.filter(q => q.status === 2).length
  if (pendingCount > 0 && enabledCount > 0) {
    ElMessage.warning('不能同时选中"待启用"和"启用"状态的题目')
    return
  }
  let confirmMsg = ''
  let newStatus = 2
  if (enabledCount > 0) {
    // 启用 → 待启用
    confirmMsg = `确定要将选中的 ${enabledCount} 道题目从"启用"设为"待启用"吗？待启用的题目可以通过再次修改状态恢复为"启用"。`
    newStatus = 2
  } else if (pendingCount > 0) {
    // 待启用 → 启用
    confirmMsg = `确定要将选中的 ${pendingCount} 道题目从"待启用"恢复为"启用"吗？`
    newStatus = 1
  }
  ElMessageBox.confirm(confirmMsg, '提示', {
    type: 'warning'
  }).then(async () => {
    try {
      // 评估 P2-15：改用后端 batch 接口（一次请求），替代逐条 updateQuestion 的 N+1 请求
      const ids = selectedQuestions.value
        .filter(q => (q.status === 1 && newStatus === 2) || (q.status === 2 && newStatus === 1))
        .map(q => q.id)
      if (ids.length === 0) return
      await adminAPI.batchUpdateQuestionStatus(ids, { status: newStatus })
      ElMessage.success(newStatus === 2 ? '已设为待启用' : '已恢复为启用')
      fetchQuestionList()
    } catch (error) {
      ElMessage.error('状态更新失败')
    }
  }).catch(() => {})
}
// 新建/编辑题目
export const openQuestionDialog = () => {
  isEdit.value = false
  resetQuestionForm()
  questionDialogVisible.value = true
}
export const editQuestion = (row: any) => {
  isEdit.value = true
  // 转换题型: single_choice -> single, multiple_choice -> multiple, true_false -> judge, essay -> short_answer
  const typeMap = { 'single_choice': 'single', 'multiple_choice': 'multiple', 'true_false': 'judge', 'essay': 'short_answer' }
  // 转换难度: 1-2 -> easy, 3 -> medium, 4-5 -> hard
  const difficultyMap = { 1: 'easy', 2: 'easy', 3: 'medium', 4: 'hard', 5: 'hard' }
  Object.assign(questionForm, {
    id: row.id,
    type: typeMap[row.question_type as keyof typeof typeMap] || row.question_type,
    difficulty: difficultyMap[row.difficulty as keyof typeof difficultyMap] || row.difficulty,
    score: row.score,
    content: row.content,
    options: (row.options || []).map((opt: any) => ({
      content: opt.option_content || ''
    })),
    correctAnswer: row.answer || 0,
    judgeAnswer: row.answer === 'true',
    // 从 meta.knowledge_point_ids 获取知识点ID列表
    knowledgePointIds: row.meta?.knowledge_point_ids || [],
    explanation: row.explanation || ''
  })
  questionDialogVisible.value = true
}
// 重置表单
export const resetQuestionForm = () => {
  questionForm.id = null
  questionForm.type = 'single'
  questionForm.difficulty = 'medium'
  questionForm.score = 5
  questionForm.content = ''
  questionForm.options = [
    { content: '' },
    { content: '' },
    { content: '' },
    { content: '' }
  ]
  questionForm.correctAnswer = 0
  questionForm.judgeAnswer = true
  questionForm.knowledgePointIds = []
  questionForm.explanation = ''
}
// 提交表单
export const submitQuestionForm = async () => {
  try {
    submitLoading.value = true
    const data: any = { ...questionForm }
    if (data.type === 'judge') {
      data.correctAnswer = data.judgeAnswer ? 'true' : 'false'
    }
    if (isEdit.value) {
      await adminAPI.updateQuestion(data.id, data)
      ElMessage.success('更新成功')
    } else {
      await adminAPI.createQuestion(data)
      ElMessage.success('创建成功')
    }
    questionDialogVisible.value = false
    fetchQuestionList()
  } catch (error) {
    ElMessage.error('操作失败')
  } finally {
    submitLoading.value = false
  }
}
// 删除题目
export const deleteQuestion = (id: any) => {
  ElMessageBox.confirm('确定要删除这道题目吗？', '提示', {
    type: 'warning'
  }).then(async () => {
    try {
      await adminAPI.deleteQuestion(id)
      ElMessage.success('删除成功')
      fetchQuestionList()
    } catch (error) {
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}
// 预览题目
export const previewQuestion = (row: any) => {
  currentQuestion.value = row
  previewDialogVisible.value = true
}
// 选项操作
export const addOption = () => {
  if (questionForm.options.length < 6) {
    questionForm.options.push({ content: '' })
  }
}
export const removeOption = (index: any) => {
  questionForm.options.splice(index, 1)
  if (questionForm.correctAnswer >= index) {
    questionForm.correctAnswer = Math.max(0, questionForm.correctAnswer - 1)
  }
}
// 导入相关
export const showImportDialog = () => {
  importDialogVisible.value = true
  importResult.value = null
  previewResult.value = null
  importProgress.value = 0
  importedCount.value = 0
}
// 预览导入
export const handlePreview = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }
  try {
    const formData = new FormData()
    // 使用原始文件确保稳定性
    formData.append('file', selectedFile.value)
    formData.append('format', importFormat.value)
    const res = await questionBankAPI.previewImport(formData)
    previewResult.value = res.data
    if (res.data?.errors?.length > 0) {
      ElMessage.warning(`预览发现问题：${res.data.errors.join('; ')}`)
    } else {
      ElMessage.success('预览完成，请确认导入内容')
    }
  } catch (err: any) {
    console.error('预览失败:', err)
    ElMessage.error(err.response?.data?.detail || '预览失败')
    previewResult.value = null
  }
}
// 重新预览
export const resetPreview = () => {
  previewResult.value = null
  selectedFile.value = null
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
}
export const handleFileChange = (file: any) => {
  // 创建新的文件引用，避免浏览器缓存导致的上传问题
    const newFile = new File([file.raw], file.name, { type: file.raw.type })
  selectedFile.value = newFile
  // 根据文件扩展名自动判断格式
    const ext = file.name.split('.').pop().toLowerCase()
  if (ext === 'docx') {
    importFormat.value = 'word'
  } else {
    importFormat.value = 'excel'
  }
}
export const downloadTemplate = () => {
  ElMessage.success('正在下载导入模板')
}
export const startImport = async () => {
  importing.value = true
  importProgress.value = 0
  importedCount.value = 0
  try {
    // 文件上传导入（Excel 或 Word）
    if (selectedFile.value) {
      console.log('准备上传文件:', selectedFile.value, '格式:', importFormat.value)
    const res = await questionBankAPI.importQuestions(
        selectedFile.value,
        importFormat.value,
        importSubjectId.value
      )
      importing.value = false
      importProgress.value = 100
      importedCount.value = res.data?.success_count || 0
      importResult.value = {
        success: res.data?.success_count || 0,
        failed: res.data?.fail_count || 0
      }
      if (res.data?.success_count > 0) {
        ElMessage.success(`导入成功：${res.data.success_count} 题`)
        importDialogVisible.value = false
        previewResult.value = null
        fetchQuestionList()
      }
      if (res.data?.errors?.length > 0) {
        ElMessage.warning(`部分导入失败：${res.data.errors.slice(0, 3).join('; ')}`)
      }
    } else {
      // 文本导入暂不支持
      ElMessage.info('文本导入功能开发中')
      importing.value = false
    }
  } catch (err: any) {
    console.error('导入失败:', err)
    ElMessage.error(err.response?.data?.detail || '导入失败')
    importing.value = false
  }
}
// 导出相关
export const showExportDialog = () => {
  exportDialogVisible.value = true
}
export const startExport = async () => {
  try {
    // 构建查询参数
    const params: Record<string, any> = {
      format: exportForm.format,
    }
    // 根据导出范围处理
    if (exportForm.scope === 'selected') {
      // 只导出选中的题目
      if (selectedQuestions.value.length === 0) {
        ElMessage.warning('请先选择要导出的题目')
        return
      }
      params.question_ids = selectedQuestions.value.map(q => q.id).join(',')
    } else if (exportForm.scope === 'filtered') {
      // 导出筛选结果
      if (filterForm.examTypeId) {
        params.subject_id = filterForm.examTypeId
      }
      if (filterForm.questionType) {
        const typeMap = { 'single': 'single_choice', 'multiple': 'multiple_choice', 'judge': 'true_false', 'short_answer': 'essay' }
        params.question_type = typeMap[filterForm.questionType as keyof typeof typeMap] || filterForm.questionType
      }
      if (filterForm.difficulty !== null && filterForm.difficulty !== undefined) {
        const diffMap = { 'easy': 2, 'medium': 3, 'hard': 5 }
        params.difficulty = diffMap[filterForm.difficulty as keyof typeof diffMap]
      }
    }
    // 'all' scope 导出所有题目，不添加额外参数
    ElMessage.info('正在导出题目，请稍候...')
    exportDialogVisible.value = false
    // 调用导出接口
    const response = await adminAPI.exportQuestions(params)
    // 创建下载链接
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    // 根据格式设置文件名
    const ext = exportForm.format === 'excel' ? 'xlsx' : exportForm.format
    const filename = `题目导出_${new Date().toISOString().slice(0, 10)}.${ext}`
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (error) {
    console.error('导出失败:', error)
    ElMessage.error('导出失败，请稍后重试')
  }
}
// 工具函数
export const getTypeName = (type: any) => {
  const map = {
    single: '单选题',
    single_choice: '单选题',
    multiple: '多选题',
    multiple_choice: '多选题',
    judge: '判断题',
    true_false: '判断题',
    short_answer: '简答题',
    essay: '简答题'
  }
  return map[type as keyof typeof map] || type
}
export const getDifficultyType = (difficulty: any) => {
  // 支持数字和字符串
  const map = {
    1: 'success',
    2: 'success',
    3: 'warning',
    4: 'danger',
    5: 'danger',
    easy: 'success',
    medium: 'warning',
    hard: 'danger'
  }
  return map[difficulty as keyof typeof map] || 'info'
}
export const getDifficultyName = (difficulty: any) => {
  // 支持数字和字符串
  const map = {
    1: '简单',
    2: '简单',
    3: '中等',
    4: '困难',
    5: '困难',
    easy: '简单',
    medium: '中等',
    hard: '困难'
  }
  return map[difficulty as keyof typeof map] || difficulty
}
export const getStatusName = (status: any) => {
  const map = { 0: '禁用', 1: '启用', 2: '待启用' }
  return map[status as keyof typeof map] ?? '启用'
}
export const getStatusTagType = (status: any) => {
  const map = { 0: 'danger', 1: 'success', 2: 'warning' }
  return map[status as keyof typeof map] ?? 'info'
}
export const getExamTypeName = (subjectId: any) => {
  if (!subjectId) return ''
  const id = Number(subjectId)
  // questions.subject_id 对应 subjects.id，也对应 exam_types.subject_id
  const subject = examTypeOptions.value.find(et => Number(et.subject_id) === id)
  return subject ? subject.name : ''
}
export const getCategoryName = (categoryId: any) => {
  if (!categoryId) return ''
  const id = Number(categoryId)
  const category = categoryOptions.value.find(c => Number(c.id) === id)
  return category ? category.name : ''
}
export const formatDate = (date: any) => {
  if (!date) return '-'
    const d = new Date(date)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
export const escapeHtml = (str: string | null | undefined): string => {
  if (str === null || str === undefined) return ''
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}
// 安全修复（评估 P0-4）：先转义 HTML 再应用轻量 markdown 转换，
// 防止题目内容/选项中注入 <img onerror> 等存储型 XSS。
export const renderMarkdown = (content: any) => {
  if (!content) return ''
  const escaped = escapeHtml(content)
  return escaped
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
}
export const isCorrectAnswer = (index: any) => {
  if (!currentQuestion.value) return false
  // 将 index (0,1,2,3) 转换为字母 (A,B,C,D)
  const correctLetter = String.fromCharCode(65 + index)
  const answer = currentQuestion.value.answer
  if (Array.isArray(answer)) {
    return answer.includes(correctLetter)
  }
  return answer === correctLetter
}
export const formatAnswer = (answer: any) => {
  if (Array.isArray(answer)) {
    return answer.join(', ')
  }
  // answer 已经是字母字符串如 'A' 或 'A,B'
  return answer || '-'
}

// ============ Composable ============
export function useQuestionBank() {
  // 相似度检测状态
  const similarityDialogVisible = ref(false)
  const similarityLoading = ref(false)
  const similarityData = ref<any>(null)
  const similarityThreshold = ref(0.7)

  // 显示相似度检测弹窗
  const showSimilarityCheck = () => {
    similarityData.value = null
    similarityThreshold.value = 0.7
    similarityDialogVisible.value = true
  }

  // 执行相似度检测
  const runSimilarityCheck = async () => {
    similarityLoading.value = true
    try {
      const params = {
        subject_id: filterForm.examTypeId || undefined,
        question_type: filterForm.questionType || undefined,
        threshold: similarityThreshold.value
      }
      const res = await questionBankAPI.checkSimilarity(params)
      similarityData.value = res.data
      if (similarityData.value.similar_pairs_count === 0) {
        ElMessage.success('未发现相似题目')
      } else {
        ElMessage.warning(`发现 ${similarityData.value.similar_pairs_count} 对相似题目`)
      }
    } catch (e) {
      console.error('相似度检测失败:', e)
      ElMessage.error('相似度检测失败')
    } finally {
      similarityLoading.value = false
    }
  }

  const getSimilarityType = (score: any) => {
    if (score >= 0.9) return 'danger'
    if (score >= 0.8) return 'warning'
    return 'info'
  }

  const getSimilarityLevel = (score: any) => {
    if (score >= 0.9) return '高度相似'
    if (score >= 0.8) return '中度相似'
    return '轻度相似'
  }

  return {
    // State
    loading,
    searchKeyword,
    questionList,
    selectedQuestions,
    categoryOptions,
    examTypeOptions,
    loadingCategories,
    loadingExamTypes,
    questionDialogVisible,
    previewDialogVisible,
    importDialogVisible,
    exportDialogVisible,
    isEdit,
    submitLoading,
    currentQuestion,
    importTab,
    importFormat,
    importText,
    importing,
    importProgress,
    importedCount,
    totalCount,
    importResult,
    uploadRef,
    selectedFile,
    importCategoryId,
    importSubjectId,
    previewResult,
    // Forms
    exportForm,
    pagination,
    filterForm,
    questionForm,
    formRules,
    // Computed
    importProgressStatus,
    filteredExamTypeOptions,
    // Actions
    handleCategoryChange,
    fetchCategories,
    fetchExamTypes,
    fetchQuestionList,
    handleSearch,
    handleSizeChange,
    handlePageChange,
    handleSelectionChange,
    handleStatusChange,
    handleBatchCommand,
    handleBatchDelete,
    handleBatchStatusChange,
    openQuestionDialog,
    editQuestion,
    resetQuestionForm,
    submitQuestionForm,
    deleteQuestion,
    showImportDialog,
    handlePreview,
    resetPreview,
    handleFileChange,
    downloadTemplate,
    startImport,
    showExportDialog,
    startExport,
    // Helpers
    getTypeName,
    getDifficultyType,
    getDifficultyName,
    getStatusName,
    getStatusTagType,
    getExamTypeName,
    getCategoryName,
    formatDate,
    renderMarkdown,
    isCorrectAnswer,
    formatAnswer,
    // 相似度检测
    similarityDialogVisible,
    similarityLoading,
    similarityData,
    similarityThreshold,
    showSimilarityCheck,
    runSimilarityCheck,
    getSimilarityType,
    getSimilarityLevel
  }
}
