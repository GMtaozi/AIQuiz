import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { knowledgeBaseAPI, knowledgeAPI, systemAPI, subjectAPI } from '@/api'
import { useAuthStore } from '@/stores/auth'

// ============ Types ============
export interface KnowledgeBase {
  id: number
  name: string
  description?: string
  subject_id?: number
  subject_name?: string
  category: string
  exam_type?: string
  visibility: string
  source_file?: string
  entries_count?: number
  points_count?: number
  created_by?: number
  creator_name?: string
  created_at: string
  updated_at: string
}

export interface KnowledgeEntry {
  id: number
  knowledge_base_id: number
  title: string
  content: string
  order: number
  source_location?: string
  created_at: string
}

export interface KnowledgePointSummary {
  id: number
  name: string
  description?: string
  content_excerpt?: string
  parent_id?: number
  knowledge_base_id: number
  entry_id?: number
  children?: KnowledgePointSummary[]
}

export interface KbFormData {
  name: string
  description: string
  subject_id: number | null
  category: string
  exam_type: string
  visibility: string
}

// ============ State ============
const authStore = useAuthStore()

// List
const knowledgeBases = ref<KnowledgeBase[]>([])
const totalKb = ref(0)
const kbLoading = ref(false)
const kbCurrentPage = ref(1)
const kbPageSize = ref(10)
const kbFilters = reactive({
  subject_id: null as number | null,
  category: '',
  exam_type: '',
  visibility: '',
  keyword: '',
})

// Detail
const currentKb = ref<KnowledgeBase | null>(null)

// Entries
const entries = ref<KnowledgeEntry[]>([])
const entriesLoading = ref(false)
const currentEntry = ref<KnowledgeEntry | null>(null)

// Points
const pointsTree = ref<KnowledgePointSummary[]>([])
const pointsLoading = ref(false)

// Extract / Import
const analyzing = ref(false)
const extractMode = ref<'rule' | 'ai' | 'auto'>('auto')
const extractPreview = ref<any[]>([])
const extractPreviewVisible = ref(false)

// Upload
const uploadDialogVisible = ref(false)
const uploadFileList = ref<File[]>([])
const uploadProcessing = ref(false)

// Create/Edit dialog
const kbDialogVisible = ref(false)
const kbDialogMode = ref<'create' | 'edit'>('create')
const kbSubmitting = ref(false)
const kbForm = reactive<KbFormData>({
  name: '',
  description: '',
  subject_id: null,
  category: 'default',
  exam_type: '',
  visibility: 'private',
})

// Options
const subjectOptions = ref<{ id: number; name: string }[]>([])
const categoryOptions = ref<{ value: string; label: string }[]>([])
const examTypeOptions = ref<{ value: string; label: string }[]>([])

// ============ Computed ============
const kbFormRules = computed(() => ({
  name: [{ required: true, message: '请输入知识库名称', trigger: 'blur' }],
  category: [{ required: true, message: '请选择分类', trigger: 'change' }],
}))

// ============ Actions ============

/** Fetch dropdown options */
async function fetchOptions() {
  try {
    const [subjectsRes, examCategoriesRes, examTypesRes] = await Promise.all([
      subjectAPI.getSubjects(),
      systemAPI.getExamCategories(),
      systemAPI.getExamTypes({}),
    ])
    subjectOptions.value = (subjectsRes.data as any)?.data || subjectsRes.data || []
    const cats = (examCategoriesRes.data as any)?.items || (examCategoriesRes.data as any)?.data || []
    categoryOptions.value = cats.map((c: any) => ({ value: c.name || c.key, label: c.name || c.label || c.key }))
    const types = (examTypesRes.data as any)?.items || (examTypesRes.data as any)?.data || []
    examTypeOptions.value = types.map((t: any) => ({ value: t.name || t.key, label: t.name || t.label || t.key }))
  } catch (e) {
    console.error('Failed to fetch options', e)
  }
}

/** Fetch paginated knowledge base list */
async function fetchKnowledgeBases() {
  kbLoading.value = true
  try {
    const params: Record<string, any> = {
      page: kbCurrentPage.value,
      page_size: kbPageSize.value,
    }
    if (kbFilters.subject_id) params.subject_id = kbFilters.subject_id
    if (kbFilters.category) params.category = kbFilters.category
    if (kbFilters.exam_type) params.exam_type = kbFilters.exam_type
    if (kbFilters.visibility) params.visibility = kbFilters.visibility
    if (kbFilters.keyword) params.keyword = kbFilters.keyword

    const res = await knowledgeBaseAPI.list(params)
    const data = (res.data as any)?.data || res.data || {}
    knowledgeBases.value = data.items || data.list || data.results || []
    totalKb.value = data.total || 0
  } catch (e: any) {
    ElMessage.error(e.message || '获取知识库列表失败')
  } finally {
    kbLoading.value = false
  }
}

/** Open create dialog */
function openCreateDialog() {
  kbDialogMode.value = 'create'
  resetKbForm()
  kbDialogVisible.value = true
}

/** Open edit dialog */
function openEditDialog(kb: KnowledgeBase) {
  kbDialogMode.value = 'edit'
  kbForm.name = kb.name
  kbForm.description = kb.description || ''
  kbForm.subject_id = kb.subject_id || null
  kbForm.category = kb.category || 'default'
  kbForm.exam_type = kb.exam_type || ''
  kbForm.visibility = kb.visibility || 'private'
  currentKb.value = kb
  kbDialogVisible.value = true
}

/** Reset form */
function resetKbForm() {
  kbForm.name = ''
  kbForm.description = ''
  kbForm.subject_id = null
  kbForm.category = 'default'
  kbForm.exam_type = ''
  kbForm.visibility = 'private'
  currentKb.value = null
}

/** Submit create/update */
async function submitKbForm() {
  if (!kbForm.name.trim()) {
    ElMessage.warning('请输入知识库名称')
    return
  }
  kbSubmitting.value = true
  try {
    const payload = {
      name: kbForm.name.trim(),
      description: kbForm.description.trim() || undefined,
      subject_id: kbForm.subject_id || undefined,
      category: kbForm.category,
      exam_type: kbForm.exam_type.trim() || undefined,
      visibility: kbForm.visibility,
    }

    if (kbDialogMode.value === 'create') {
      await knowledgeBaseAPI.create(payload)
      ElMessage.success('知识库创建成功')
    } else if (currentKb.value) {
      await knowledgeBaseAPI.update(currentKb.value.id, payload)
      ElMessage.success('知识库更新成功')
    }
    kbDialogVisible.value = false
    resetKbForm()
    await fetchKnowledgeBases()
  } catch (e: any) {
    ElMessage.error(e.message || '操作失败')
  } finally {
    kbSubmitting.value = false
  }
}

/** Delete knowledge base */
async function deleteKb(kb: KnowledgeBase) {
  try {
    await ElMessageBox.confirm(
      `确定删除知识库「${kb.name}」？此操作将级联删除所有条目和知识点，不可恢复。`,
      '确认删除',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    await knowledgeBaseAPI.delete(kb.id)
    ElMessage.success('删除成功')
    await fetchKnowledgeBases()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.message || '删除失败')
    }
  }
}

/** Navigate to detail view */
function viewKbDetail(kb: KnowledgeBase) {
  currentKb.value = kb
  fetchEntries(kb.id)
  fetchPoints(kb.id)
}

// ============ Entry Actions ============

/** Fetch entries for current knowledge base */
async function fetchEntries(kbId: number) {
  entriesLoading.value = true
  try {
    const res = await knowledgeBaseAPI.getEntries(kbId)
    const data = (res.data as any)?.data || res.data || {}
    entries.value = data.items || data.list || data.results || []
  } catch (e: any) {
    ElMessage.error(e.message || '获取条目失败')
  } finally {
    entriesLoading.value = false
  }
}

/** Fetch single entry */
async function fetchEntry(kbId: number, entryId: number) {
  try {
    const res = await knowledgeBaseAPI.getEntry(kbId, entryId)
    currentEntry.value = (res.data as any)?.data || res.data
  } catch (e: any) {
    ElMessage.error(e.message || '获取条目详情失败')
  }
}

/** Upload document to current knowledge base */
async function uploadDocument(kbId: number, file: File) {
  uploadProcessing.value = true
  try {
    const res = await knowledgeBaseAPI.uploadDocument(kbId, file)
    ElMessage.success('文档上传并解析成功')
    uploadFileList.value = []
    uploadDialogVisible.value = false
    await fetchEntries(kbId)
    // Refresh detail stats
    if (currentKb.value && currentKb.value.id === kbId) {
      const detailRes = await knowledgeBaseAPI.get(kbId)
      const detail = (detailRes.data as any)?.data || detailRes.data || {}
      currentKb.value = { ...currentKb.value, ...detail }
    }
    return res
  } catch (e: any) {
    ElMessage.error(e.message || '文档上传失败')
    throw e
  } finally {
    uploadProcessing.value = false
  }
}

// ============ Point Actions ============

/** Fetch points tree for current knowledge base */
async function fetchPoints(kbId: number) {
  pointsLoading.value = true
  try {
    const res = await knowledgeBaseAPI.getPoints(kbId)
    const data = (res.data as any)?.data || res.data || {}
    pointsTree.value = data.items || data.list || data.tree || data.results || []
  } catch (e: any) {
    ElMessage.error(e.message || '获取知识点失败')
  } finally {
    pointsLoading.value = false
  }
}

// ============ Extract / Import Actions ============

/** Analyze single entry (preview) */
async function analyzeSingleEntry(kbId: number, entryId: number, mode: 'rule' | 'ai' | 'auto' = 'auto') {
  analyzing.value = true
  try {
    const res = await knowledgeBaseAPI.analyzeEntry(kbId, entryId, mode)
    const data = (res.data as any)?.data || res.data || {}
    extractPreview.value = data.knowledge_points || data.tree || []
    extractPreviewVisible.value = true
    return data
  } catch (e: any) {
    ElMessage.error(e.message || '分析失败')
    throw e
  } finally {
    analyzing.value = false
  }
}

/** Import analyzed preview into knowledge points */
async function importAnalyzedEntry(kbId: number, entryId: number, previewData: any) {
  try {
    const res = await knowledgeBaseAPI.importEntry(kbId, entryId, {
      knowledge_points: previewData,
    })
    const data = (res.data as any)?.data || res.data || {}
    ElMessage.success(data.message || '导入成功')
    extractPreviewVisible.value = false
    extractPreview.value = []
    await fetchPoints(kbId)
    return data
  } catch (e: any) {
    ElMessage.error(e.message || '导入失败')
    throw e
  }
}

/** Analyze all entries in knowledge base */
async function analyzeAllEntries(kbId: number, mode: 'rule' | 'ai' | 'auto' = 'auto') {
  analyzing.value = true
  try {
    const res = await knowledgeBaseAPI.analyzeAll(kbId)
    const data = (res.data as any)?.data || res.data || {}
    ElMessage.success(data.message || '批量分析完成')
    await fetchEntries(kbId)
    await fetchPoints(kbId)
    return data
  } catch (e: any) {
    ElMessage.error(e.message || '批量分析失败')
    throw e
  } finally {
    analyzing.value = false
  }
}

// ============ Computed Helpers ============
const currentKbId = computed(() => currentKb.value?.id || null)

/** ============ Factory ============ */
export function useKnowledgeBase() {
  // 评估 P2-13：原工厂内 onMounted(fetchOptions) 与视图 onMounted 重复触发
  // 初始化请求（fetchOptions 被调用两次），移除——初始化由视图统一负责。
  return {
    // State
    knowledgeBases,
    totalKb,
    kbLoading,
    kbCurrentPage,
    kbPageSize,
    kbFilters,
    currentKb,
    currentKbId,
    entries,
    entriesLoading,
    currentEntry,
    pointsTree,
    pointsLoading,
    analyzing,
    extractMode,
    extractPreview,
    extractPreviewVisible,
    uploadDialogVisible,
    uploadFileList,
    uploadProcessing,
    kbDialogVisible,
    kbDialogMode,
    kbSubmitting,
    kbForm,
    subjectOptions,
    categoryOptions,
    examTypeOptions,
    kbFormRules,
    // Actions
    fetchKnowledgeBases,
    fetchOptions,
    openCreateDialog,
    openEditDialog,
    resetKbForm,
    submitKbForm,
    deleteKb,
    viewKbDetail,
    fetchEntries,
    fetchEntry,
    uploadDocument,
    fetchPoints,
    analyzeSingleEntry,
    importAnalyzedEntry,
    analyzeAllEntries,
  }
}
