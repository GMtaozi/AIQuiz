import { ref, reactive, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminAPI, systemAPI, paperAPI, api } from '@/api'

// ============ Types ============
export interface PaperForm {
  title: string
  categoryId: number | null
  subjectId: number | null
  totalTime: number
  totalScore: number
  passingScore: number
  description: string
}

export interface FilterForm {
  categoryId: number | null
  subjectId: number | null
  status: number | null
}

export interface Pagination {
  page: number
  pageSize: number
  total: number
}

export interface VersionPagination {
  page: number
  pageSize: number
  total: number
}

export interface CategoryOption {
  id: number
  name: string
}

export interface SubjectOption {
  id: number
  name: string
  category_id: number
  subject_id: number
}

export interface PaperRow {
  id: number
  title: string
  subject_id: number
  total_time: number
  total_score: number
  passing_score: number
  status: number
  description?: string
  created_at: string
  config?: {
    actual_question_count?: number
  }
}

export interface PreviewQuestion {
  id: number
  score: number
  question: {
    id: number
    question_type: string
    content: string
    options?: Array<{
      id: number
      option_label: string
      option_content: string
      is_correct: boolean
    }>
    answer: string
    explanation?: string
  }
}

export interface PreviewPaperData {
  id: number
  title: string
  subject_id: number
  total_time: number
  total_score: number
  passing_score: number
  description?: string
  questions: PreviewQuestion[]
}

export interface AnalysisData {
  total_questions: number
  total_score: number
  total_time?: number
  estimated_time: number
  coverage_rate: number
  type_stats: Record<string, { count: number; score: number }>
  difficulty_distribution: { easy: number; medium: number; hard: number }
  difficulty_stats: { easy: number; medium: number; hard: number }
  selected_knowledge_points?: number[]
  covered_knowledge_points?: number[]
  knowledge_point_stats?: Record<string, { count: number; score: number }>
  discrimination_index?: number
  predicted_pass_rate?: number
  quality_score?: number
  knowledge_mastery?: Array<{
    knowledge_point_id: number
    count: number
    score: number
    avg_difficulty: number
    mastery_level: string
  }>
}

export interface VersionItem {
  id: number
  version_number: number
  title: string
  change_log?: string
  created_at: string
}

export interface VersionDetail extends VersionItem {
  description?: string
  questions_snapshot?: Array<{ order: number; question_id: number; score: number }>
}

export interface SimilarityPair {
  similarity_score: number
  question_type: string
  question_a_id: number
  question_a_content: string
  question_b_id: number
  question_b_content: string
  similarity_reason: string
}

export interface SimilarityData {
  total_checked: number
  similar_pairs_count: number
  similar_pairs: SimilarityPair[]
  message?: string
}

// ============ State ============
export const loading = ref(false)
export const loadingCategories = ref(false)
export const loadingSubjects = ref(false)
export const paperList = ref<PaperRow[]>([])
export const selectedRows = ref<PaperRow[]>([])
export const searchKeyword = ref('')
export const paperDialogVisible = ref(false)
export const previewDialogVisible = ref(false)
export const isEdit = ref(false)
export const saveLoading = ref(false)
export const currentEditId = ref<number | null>(null)
export const previewPaperData = ref<PreviewPaperData | null>(null)
export const paperFormRef = ref<any>(null)

// 试卷分析
export const analysisDialogVisible = ref(false)
export const analysisData = ref<AnalysisData | null>(null)
export const analysisSuggestions = ref<string[]>([])

// 版本管理
export const versionDialogVisible = ref(false)
export const versionDetailDialogVisible = ref(false)
export const versionList = ref<VersionItem[]>([])
export const versionDetail = ref<VersionDetail | null>(null)
export const currentVersionPaperId = ref<number | null>(null)
export const versionPagination = reactive<VersionPagination>({ page: 1, pageSize: 20, total: 0 })

// 相似度检测
export const similarityDialogVisible = ref(false)
export const similarityLoading = ref(false)
export const similarityData = ref<SimilarityData | null>(null)
export const similarityThreshold = ref(0.7)

// 分页
export const pagination = reactive<Pagination>({
  page: 1,
  pageSize: 20,
  total: 0
})

// 筛选表单
export const filterForm = reactive<FilterForm>({
  categoryId: null,
  subjectId: null,
  status: null
})

// 考试种类选项
export const categoryOptions = ref<CategoryOption[]>([])

// 考试科目选项
export const subjectOptions = ref<SubjectOption[]>([])

// 计算属性：按考试种类筛选考试科目
export const filteredSubjectOptions = computed(() => {
  if (!filterForm.categoryId) return subjectOptions.value
  return subjectOptions.value.filter(s => s.category_id === filterForm.categoryId)
})

// 弹窗内的考试科目（过滤用）
export const dialogFilteredSubjects = computed(() => {
  if (!paperForm.categoryId) return subjectOptions.value
  return subjectOptions.value.filter(s => s.category_id === paperForm.categoryId)
})

// 试卷表单
export const paperForm = reactive<PaperForm>({
  title: '',
  categoryId: null,
  subjectId: null,
  totalTime: 120,
  totalScore: 100,
  passingScore: 60,
  description: ''
})

// 表单验证规则
export const formRules = {
  title: [{ required: true, message: '请输入试卷标题', trigger: 'blur' }],
  categoryId: [{ required: true, message: '请选择考试种类', trigger: 'change' }],
  subjectId: [{ required: true, message: '请选择考试科目', trigger: 'change' }],
  totalTime: [{ required: true, message: '请输入时长', trigger: 'blur' }],
  totalScore: [{ required: true, message: '请输入总分', trigger: 'blur' }],
  passingScore: [{ required: true, message: '请输入及格分', trigger: 'blur' }]
}

// ============ Utility Functions ============
export const formatDate = (date: any) => {
  if (!date) return '-'
  const d = new Date(date)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

export const getSubjectName = (subjectId: number) => {
  const subject = subjectOptions.value.find(s => s.subject_id === subjectId)
  return subject?.name || ''
}

export const getStatusName = (status: number) => {
  const map: Record<number, string> = { 0: '草稿', 1: '已发布', 2: '已归档' }
  return map[status] ?? '草稿'
}

export const getStatusTagType = (status: number) => {
  const map: Record<number, string> = { 0: 'info', 1: 'success', 2: 'warning' }
  return map[status] ?? 'info'
}

export const getQuestionTypeName = (type: string) => {
  const map: Record<string, string> = {
    'single_choice': '单选题',
    'multiple_choice': '多选题',
    'true_false': '判断题',
    'essay': '简答题'
  }
  return map[type] || type
}

export const getCorrectAnswerLabels = (options: Array<{ is_correct: boolean; option_label: string }>) => {
  if (!options || options.length === 0) return ''
  const correctLabels = options.filter(opt => opt.is_correct).map(opt => opt.option_label)
  return correctLabels.join(', ')
}

// ============ API Functions ============
export const fetchCategories = async () => {
  loadingCategories.value = true
  try {
    const res = await systemAPI.getExamCategories()
    categoryOptions.value = res.data?.items || []
  } catch (e) {
    console.error('获取考试种类失败:', e)
  } finally {
    loadingCategories.value = false
  }
}

export const fetchSubjects = async () => {
  loadingSubjects.value = true
  try {
    const res = await systemAPI.getExamTypes()
    subjectOptions.value = res.data?.items || []
  } catch (e) {
    console.error('获取考试科目失败:', e)
  } finally {
    loadingSubjects.value = false
  }
}

export const fetchPaperList = async () => {
  loading.value = true
  try {
    const params: Record<string, any> = {
      page: pagination.page,
      page_size: pagination.pageSize
    }
    if (filterForm.categoryId) params.category_id = filterForm.categoryId
    if (filterForm.subjectId) params.subject_id = filterForm.subjectId
    if (filterForm.status !== null) params.status = filterForm.status
    if (searchKeyword.value) params.keyword = searchKeyword.value

    const res = await adminAPI.getPapers(params)
    paperList.value = res.data?.items || []
    pagination.total = res.data?.total || 0
  } catch (e) {
    console.error('获取试卷列表失败:', e)
  } finally {
    loading.value = false
  }
}

// ============ Handler Functions ============
export const handleSearch = () => {
  pagination.page = 1
  fetchPaperList()
}

export const handleSizeChange = () => {
  pagination.page = 1
  fetchPaperList()
}

export const handlePageChange = () => {
  fetchPaperList()
}

export const handleCategoryChange = () => {
  filterForm.subjectId = null
  fetchPaperList()
}

export const handleDialogCategoryChange = () => {
  paperForm.subjectId = null
}

export const handleSelectionChange = (rows: PaperRow[]) => {
  selectedRows.value = rows
}

// ============ Dialog Operations ============
export const openPaperDialog = () => {
  isEdit.value = false
  currentEditId.value = null
  resetPaperForm()
  paperDialogVisible.value = true
}

export const editPaper = (row: PaperRow) => {
  isEdit.value = true
  currentEditId.value = row.id
  paperForm.title = row.title
  const subject = subjectOptions.value.find(s => s.id === row.subject_id)
  paperForm.categoryId = subject?.category_id || null
  paperForm.subjectId = row.subject_id
  paperForm.totalTime = row.total_time
  paperForm.totalScore = row.total_score
  paperForm.passingScore = row.passing_score
  paperForm.description = row.description || ''
  paperDialogVisible.value = true
}

export const resetPaperForm = () => {
  paperForm.title = ''
  paperForm.categoryId = null
  paperForm.subjectId = null
  paperForm.totalTime = 120
  paperForm.totalScore = 100
  paperForm.passingScore = 60
  paperForm.description = ''
}

export const savePaper = async () => {
  try {
    await paperFormRef.value.validate()
  } catch {
    return
  }

  saveLoading.value = true
  try {
    const data = {
      title: paperForm.title,
      subject_id: paperForm.subjectId,
      total_time: paperForm.totalTime,
      total_score: paperForm.totalScore,
      passing_score: paperForm.passingScore,
      description: paperForm.description,
      paper_type: 1,
      questions: []
    }

    if (isEdit.value) {
      await adminAPI.updatePaper(currentEditId.value, data)
      ElMessage.success('试卷更新成功')
    } else {
      await adminAPI.createPaper(data)
      ElMessage.success('试卷创建成功')
    }

    paperDialogVisible.value = false
    fetchPaperList()
  } catch (e) {
    console.error('保存试卷失败:', e)
    ElMessage.error('保存失败，请稍后重试')
  } finally {
    saveLoading.value = false
  }
}

// ============ Preview Functions ============
export const previewPaper = async (row: PaperRow) => {
  try {
    const res = await adminAPI.getPaperById(row.id)
    previewPaperData.value = res.data
    previewDialogVisible.value = true
  } catch (e) {
    console.error('获取试卷详情失败:', e)
    ElMessage.error('获取试卷详情失败')
  }
}

// ============ Analysis Functions ============
export const analyzePaper = async (row: PaperRow) => {
  try {
    const res = await paperAPI.getPaperAnalysis(row.id)
    analysisData.value = res.data
    analysisSuggestions.value = generateAnalysisSuggestions(res.data)
    analysisDialogVisible.value = true
  } catch (e) {
    console.error('获取试卷分析失败:', e)
    ElMessage.error('获取试卷分析失败')
  }
}

export const generateAnalysisSuggestions = (data: AnalysisData) => {
  const suggestions: string[] = []

  if (data.coverage_rate < 60) {
    suggestions.push(`知识点覆盖率仅${data.coverage_rate}%，建议补充更多知识点以确保考核全面性`)
  } else if (data.coverage_rate < 80) {
    suggestions.push(`知识点覆盖率为${data.coverage_rate}%，覆盖率良好，可考虑补充部分未覆盖知识点`)
  }

  const easyPercent = data.difficulty_distribution.easy || 0
  const hardPercent = data.difficulty_distribution.hard || 0

  if (easyPercent > 60) {
    suggestions.push('简单题目占比过高，建议增加中等和困难题目以提升试卷区分度')
  } else if (hardPercent > 50) {
    suggestions.push('困难题目占比过高，建议适当增加简单和中等题目，避免试卷过于困难')
  }

  const typeStats = data.type_stats || {}
  const totalQuestions = data.total_questions || 0

  if (totalQuestions > 0) {
    const choiceQuestions = (typeStats.single_choice?.count || 0) + (typeStats.multiple_choice?.count || 0)
    const choicePercent = choiceQuestions / totalQuestions * 100

    if (choicePercent > 80) {
      suggestions.push('客观题（选择题）占比过高，建议增加主观题（如简答题）以考察综合能力')
    }
  }

  if (data.estimated_time > (data.total_time ?? 0)) {
    suggestions.push(`预估完成时间（${data.estimated_time}分钟）超过试卷设定时长（${data.total_time}分钟），建议适当减少题量或增加时长`)
  }

  if (data.discrimination_index != null && data.discrimination_index < 5) {
    suggestions.push(`区分度较低（${data.discrimination_index}/10），建议调整难度分布，增加中高难度题目比例`)
  }

  if (data.predicted_pass_rate != null && data.predicted_pass_rate < 50) {
    suggestions.push(`预估通过率偏低（${data.predicted_pass_rate}%），建议适当降低难度或增加基础题`)
  } else if (data.predicted_pass_rate != null && data.predicted_pass_rate > 90) {
    suggestions.push(`预估通过率偏高（${data.predicted_pass_rate}%），建议适当提升难度以更好区分学生水平`)
  }

  if (data.quality_score != null && data.quality_score < 60) {
    suggestions.push(`试卷综合质量分较低（${data.quality_score}/100），建议优化知识点覆盖、难度分布和题型配比`)
  }

  return suggestions
}

export const getTypeStatsTable = (typeStats: Record<string, { count: number; score: number }>) => {
  if (!typeStats) return []
  const total = Object.values(typeStats).reduce((sum, item) => sum + (item.count || 0), 0)
  return Object.entries(typeStats).map(([type, stats]) => ({
    type: getQuestionTypeName(type),
    count: stats.count || 0,
    score: stats.score || 0,
    percentage: total > 0 ? Math.round((stats.count / total) * 100) : 0
  }))
}

export const getTypeColor = (type: string) => {
  const map: Record<string, string> = {
    '单选题': '#409eff',
    '多选题': '#67c23a',
    '判断题': '#e6a23c',
    '简答题': '#f56c6c'
  }
  return map[type] || '#909399'
}

export const getCoverageClass = (rate: number) => {
  if (rate >= 80) return 'coverage-good'
  if (rate >= 60) return 'coverage-medium'
  return 'coverage-poor'
}

export const getKnowledgePointStatsTable = (kpStats: Record<string, { count: number; score: number }>) => {
  if (!kpStats) return []
  return Object.entries(kpStats).map(([kpId, stats]) => ({
    kp_id: kpId,
    count: stats.count || 0,
    score: stats.score || 0,
    covered: (stats.count || 0) > 0
  }))
}

export const getDiscriminationType = (value: number | null | undefined) => {
  if (value == null) return 'info'
  if (value >= 8) return 'success'
  if (value >= 5) return 'warning'
  return 'danger'
}

export const getPassRateColor = (value: number | null | undefined) => {
  if (value == null) return '#909399'
  if (value >= 75) return '#67c23a'
  if (value >= 50) return '#e6a23c'
  return '#f56c6c'
}

export const getQualityScoreColor = (value: number | null | undefined) => {
  if (value == null) return '#909399'
  if (value >= 80) return '#67c23a'
  if (value >= 60) return '#e6a23c'
  return '#f56c6c'
}

export const getMasteryType = (level: string) => {
  const map: Record<string, string> = { high: 'success', medium: 'warning', low: 'danger' }
  return map[level] || 'info'
}

export const getMasteryLabel = (level: string) => {
  const map: Record<string, string> = { high: '掌握良好', medium: '一般', low: '待加强' }
  return map[level] || level
}

// ============ Version Management ============
export const showVersionHistory = async (row: PaperRow) => {
  currentVersionPaperId.value = row.id
  versionDialogVisible.value = true
  await fetchVersions(row.id)
}

export const fetchVersions = async (paperId: number) => {
  versionList.value = []
  versionPagination.total = 0
  try {
    const res = await paperAPI.getPaperVersions(paperId, { page: versionPagination.page, page_size: versionPagination.pageSize })
    versionList.value = res.data?.items || []
    versionPagination.total = res.data?.total || 0
  } catch (e) {
    console.error('获取版本历史失败:', e)
    ElMessage.error('获取版本历史失败')
  }
}

export const showVersionDetail = async (version: VersionItem) => {
  try {
    const res = await paperAPI.getPaperVersion(currentVersionPaperId.value!, version.id)
    versionDetail.value = res.data
    versionDetailDialogVisible.value = true
  } catch (e) {
    console.error('获取版本详情失败:', e)
    ElMessage.error('获取版本详情失败')
  }
}

export const restoreVersion = async (version: VersionItem | VersionDetail) => {
  try {
    await ElMessageBox.confirm(`确定要回滚到版本 ${version.version_number} 吗？当前版本将被覆盖。`, '确认回滚', { type: 'warning' })
    await paperAPI.restorePaperVersion(currentVersionPaperId.value!, version.id)
    ElMessage.success(`已回滚到版本 ${version.version_number}`)
    versionDetailDialogVisible.value = false
    await fetchVersions(currentVersionPaperId.value!)
  } catch (e: any) {
    if (e !== 'cancel') {
      console.error('回滚失败:', e)
      ElMessage.error('回滚失败')
    }
  }
}

export const handleVersionPageChange = () => {
  if (currentVersionPaperId.value) {
    fetchVersions(currentVersionPaperId.value)
  }
}

// ============ Similarity Check ============
export const showSimilarityCheck = (row: PaperRow) => {
  similarityData.value = null
  similarityThreshold.value = 0.7
  similarityDialogVisible.value = true
}

export const runSimilarityCheck = async () => {
  if (!previewPaperData.value) return
  similarityLoading.value = true
  try {
    const res = await paperAPI.checkSimilarity(previewPaperData.value.id, {
      threshold: similarityThreshold.value
    })
    similarityData.value = res.data
    const count = similarityData.value?.similar_pairs_count ?? 0
    if (count === 0) {
      ElMessage.success('未发现相似题目')
    } else {
      ElMessage.warning(`发现 ${count} 对相似题目`)
    }
  } catch (e) {
    console.error('相似度检测失败:', e)
    ElMessage.error('相似度检测失败')
  } finally {
    similarityLoading.value = false
  }
}

export const getSimilarityType = (score: number) => {
  if (score >= 0.9) return 'danger'
  if (score >= 0.8) return 'warning'
  return 'info'
}

export const getSimilarityLevel = (score: number) => {
  if (score >= 0.9) return '高度相似'
  if (score >= 0.8) return '中度相似'
  return '轻度相似'
}

// ============ Row Operations ============
export const handleRowCommand = (command: string, row: PaperRow) => {
  if (command === 'analyze') {
    analyzePaper(row)
  } else if (command === 'version') {
    showVersionHistory(row)
  } else if (command === 'similarity') {
    showSimilarityCheck(row)
  }
}

// ============ Publish / Archive / Delete ============
export const publishPaper = (row: PaperRow) => {
  ElMessageBox.confirm('确定要发布这份试卷吗？', '确认发布', { type: 'info' })
    .then(async () => {
      try {
        await adminAPI.updatePaper(row.id, { status: 1 })
        ElMessage.success('试卷发布成功')
        fetchPaperList()
      } catch (e) {
        console.error('发布失败:', e)
        ElMessage.error('发布失败')
      }
    })
    .catch(() => {})
}

export const archivePaper = (row: PaperRow) => {
  ElMessageBox.confirm('确定要归档这份试卷吗？', '确认归档', { type: 'info' })
    .then(async () => {
      try {
        await adminAPI.updatePaper(row.id, { status: 2 })
        ElMessage.success('试卷归档成功')
        fetchPaperList()
      } catch (e) {
        console.error('归档失败:', e)
        ElMessage.error('归档失败')
      }
    })
    .catch(() => {})
}

export const deletePaper = (row: PaperRow) => {
  ElMessageBox.confirm(`确定要归档试卷"${row.title}"吗？`, '确认归档', { type: 'warning' })
    .then(async () => {
      try {
        await adminAPI.deletePaper(Number(row.id))
        ElMessage.success('归档成功')
        fetchPaperList()
      } catch (e) {
        console.error('归档失败:', e)
        ElMessage.error('归档失败')
      }
    })
    .catch(() => {})
}

// ============ Batch Operations ============
export const handleBatchCommand = (command: string) => {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请先选择要操作的试卷')
    return
  }

  const ids = selectedRows.value.map(r => r.id)

  if (command === 'publish') {
    ElMessageBox.confirm(`确定要发布选中的 ${ids.length} 份试卷吗？`, '批量发布', { type: 'info' })
      .then(async () => {
        try {
          for (const id of ids) {
            await adminAPI.updatePaper(id, { status: 1 })
          }
          ElMessage.success('批量发布成功')
          fetchPaperList()
        } catch (e) {
          ElMessage.error('批量发布失败')
        }
      })
      .catch(() => {})
  } else if (command === 'archive') {
    ElMessageBox.confirm(`确定要归档选中的 ${ids.length} 份试卷吗？`, '批量归档', { type: 'info' })
      .then(async () => {
        try {
          for (const id of ids) {
            await adminAPI.updatePaper(id, { status: 2 })
          }
          ElMessage.success('批量归档成功')
          fetchPaperList()
        } catch (e) {
          ElMessage.error('批量归档失败')
        }
      })
      .catch(() => {})
  } else if (command === 'delete') {
    ElMessageBox.confirm(`确定要归档选中的 ${ids.length} 份试卷吗？`, '批量归档', { type: 'warning' })
      .then(async () => {
        try {
          for (const id of ids) {
            await adminAPI.deletePaper(Number(id))
          }
          ElMessage.success('批量归档成功')
          fetchPaperList()
        } catch (e) {
          ElMessage.error('批量归档失败')
        }
      })
      .catch(() => {})
  }
}

// ============ Export Functions ============
export const exportWord = async () => {
  if (!previewPaperData.value) return
  try {
    ElMessage.info('正在导出Word文档...')
    const response = await api.post(`/papers/export`, {
      paper_id: previewPaperData.value.id,
      format: 'word'
    }, {
      responseType: 'blob'
    })

    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.download = `${previewPaperData.value.title || '试卷'}.docx`
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

export const exportPdf = async () => {
  if (!previewPaperData.value) return
  try {
    ElMessage.info('正在导出PDF文档...')
    const response = await api.post(`/papers/export`, {
      paper_id: previewPaperData.value.id,
      format: 'pdf'
    }, {
      responseType: 'blob'
    })

    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.download = `${previewPaperData.value.title || '试卷'}.pdf`
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

// ============ Composable ============
export function usePaperManagement() {
  return {
    // State
    loading,
    loadingCategories,
    loadingSubjects,
    paperList,
    selectedRows,
    searchKeyword,
    paperDialogVisible,
    previewDialogVisible,
    isEdit,
    saveLoading,
    currentEditId,
    previewPaperData,
    paperFormRef,
    analysisDialogVisible,
    analysisData,
    analysisSuggestions,
    versionDialogVisible,
    versionDetailDialogVisible,
    versionList,
    versionDetail,
    currentVersionPaperId,
    versionPagination,
    similarityDialogVisible,
    similarityLoading,
    similarityData,
    similarityThreshold,
    pagination,
    filterForm,
    categoryOptions,
    subjectOptions,
    paperForm,
    formRules,
    // Computed
    filteredSubjectOptions,
    dialogFilteredSubjects,
    // Utility
    formatDate,
    getSubjectName,
    getStatusName,
    getStatusTagType,
    getQuestionTypeName,
    getCorrectAnswerLabels,
    // API
    fetchCategories,
    fetchSubjects,
    fetchPaperList,
    // Handlers
    handleSearch,
    handleSizeChange,
    handlePageChange,
    handleCategoryChange,
    handleDialogCategoryChange,
    handleSelectionChange,
    // Dialog
    openPaperDialog,
    editPaper,
    resetPaperForm,
    savePaper,
    // Preview
    previewPaper,
    // Analysis
    analyzePaper,
    generateAnalysisSuggestions,
    getTypeStatsTable,
    getTypeColor,
    getCoverageClass,
    getKnowledgePointStatsTable,
    getDiscriminationType,
    getPassRateColor,
    getQualityScoreColor,
    getMasteryType,
    getMasteryLabel,
    // Version
    showVersionHistory,
    fetchVersions,
    showVersionDetail,
    restoreVersion,
    handleVersionPageChange,
    // Similarity
    showSimilarityCheck,
    runSimilarityCheck,
    getSimilarityType,
    getSimilarityLevel,
    // Row operations
    handleRowCommand,
    // Publish/Archive/Delete
    publishPaper,
    archivePaper,
    deletePaper,
    // Batch
    handleBatchCommand,
    // Export
    exportWord,
    exportPdf
  }
}
