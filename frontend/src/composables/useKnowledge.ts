import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { knowledgeAPI, systemAPI } from '@/api'
import { useRouter } from 'vue-router'

// ============ Types ============
export interface KnowledgeNode {
  id: number
  name: string
  parent_id?: number
  categoryId?: number
  examTypeId?: number
  sortOrder?: number
  description?: string
  node_type?: string
  children?: KnowledgeNode[]
  chapter_id?: number
  // 展示/辅助字段（类型声明仅为通过类型检查，不影响运行时）
  parentName?: string | null
  categoryName?: string
  examTypeName?: string
  exam_type_id?: number | null
  parentId?: number
  order?: number
}

export interface RelatedQuestion {
  id: number
  content: string
  question_type: string
  difficulty: number
}

export interface KnowledgeForm {
  id: number | null
  name: string
  parentId: number | null
  categoryId: number | null
  examTypeId: number | null
  sortOrder: number
  description: string
}

export interface AIImportForm {
  parentId: number | null
  categoryId: number | null
  examTypeId: number | null
}

export interface AIAnalysisResult {
  success: boolean
  knowledge_points: any[]
  parent_id?: number
  document_name?: string
  total_points?: number
  message?: string
  error?: string
}

// ============ Router ============
// 安全修复（评估 P0-6）：useRouter() 必须在组件 setup 内调用，
// 模块顶层调用会返回 undefined（inject 失败）。
// 改为在 useKnowledge() 工厂内（组件 setup 中）获取并保存到模块级引用。
let routerRef: ReturnType<typeof useRouter> | null = null

// ============ Tree State ============
export const treeRef = ref<any>(null)
export const knowledgeTreeData = ref<KnowledgeNode[]>([])
export const filteredTreeData = ref<KnowledgeNode[]>([])
export const treeSearchKeyword = ref('')
export const selectedKnowledge = ref<KnowledgeNode | null>(null)
export const relatedQuestions = ref<RelatedQuestion[]>([])

// ============ Dialog State ============
export const dialogVisible = ref(false)
export const importDialogVisible = ref(false)
export const isEdit = ref(false)
export const submitLoading = ref(false)

// ============ Context Menu State ============
export const contextMenuVisible = ref(false)
export const contextMenuX = ref(0)
export const contextMenuY = ref(0)
export const contextMenuNode = ref<KnowledgeNode | null>(null)

// ============ Import State ============
export const importMode = ref('file')
export const uploadRef = ref<any>(null)
export const aiUploadRef = ref<any>(null)
export const selectedFile = ref<File | null>(null)
export const aiSelectedFile = ref<File | null>(null)
export const aiAnalyzing = ref(false)
export const aiResult = ref<AIAnalysisResult | null>(null)
export const aiImportForm = reactive<AIImportForm>({
  parentId: null,
  categoryId: null,
  examTypeId: null
})

// ============ Tree Config ============
export const treeProps = {
  label: 'name',
  children: 'children',
  value: 'id'
}

// ============ Knowledge Form ============
export const knowledgeForm = reactive<KnowledgeForm>({
  id: null,
  name: '',
  parentId: null,
  categoryId: null,
  examTypeId: null,
  sortOrder: 0,
  description: ''
})

export const formRules = {
  name: [{ required: true, message: '请输入知识点名称', trigger: 'blur' }]
}

// ============ Options ============
export const examTypeOptions = ref<any[]>([])
export const examCategoryOptions = ref<any[]>([])

// ============ Stats ============
export const totalKnowledgeCount = ref(0)
export const categoryCount = ref(0)
export const examTypeCount = ref(0)

// ============ Computed ============
// 从层级树中提取纯知识点节点（去掉 category/exam_type 虚拟节点）
const extractKnowledgeNodes = (nodes: KnowledgeNode[]): KnowledgeNode[] => {
  const result: KnowledgeNode[] = []
  for (const node of nodes) {
    if (node.node_type === 'category' || node.node_type === 'exam_type') {
      // 递归到子节点
      if (node.children) {
        result.push(...extractKnowledgeNodes(node.children))
      }
    } else {
      // 知识点节点，保留并递归子知识点
      const cloned = { ...node }
      if (cloned.children) {
        cloned.children = extractKnowledgeNodes(cloned.children)
      }
      result.push(cloned)
    }
  }
  return result
}

export const knowledgeOnlyTreeData = computed(() => {
  return extractKnowledgeNodes(knowledgeTreeData.value)
})

export const filteredFormExamTypeOptions = computed(() => {
  if (!knowledgeForm.categoryId) return examTypeOptions.value
  return examTypeOptions.value.filter(et => et.category_id === knowledgeForm.categoryId)
})

export const filteredAIExamTypeOptions = computed(() => {
  if (!aiImportForm.categoryId) return examTypeOptions.value
  return examTypeOptions.value.filter(et => et.category_id === aiImportForm.categoryId)
})

export const defaultExpandedKeys = computed(() => {
  const keys: number[] = []
  const collectKeys = (nodes: KnowledgeNode[]) => {
    for (const node of nodes) {
      if (node.node_type === 'category' || node.node_type === 'exam_type') {
        keys.push(node.id)
      }
      if (node.children) collectKeys(node.children)
    }
  }
  collectKeys(knowledgeTreeData.value)
  return keys
})

// ============ Form Handling ============
export const handleFormCategoryChange = () => {
  knowledgeForm.examTypeId = null
}

export const fetchExamTypesAndCourses = async () => {
  try {
    const categoryRes = await systemAPI.getExamCategories()
    examCategoryOptions.value = categoryRes.data?.items || []
    const examRes = await systemAPI.getExamTypes()
    examTypeOptions.value = examRes.data?.items || []
  } catch (e) {
    console.error('获取考试种类/考试类型失败:', e)
  }
}

// ============ Drag & Drop ============
export const allowDrop = (draggingNode: any, dropNode: any, type: string) => {
  // 只允许知识点节点拖拽，不允许拖到 category/exam_type 内部或上方
  if (draggingNode.data.node_type) return false
  if (dropNode.data.node_type === 'category') return false
  if (dropNode.data.node_type === 'exam_type') return false
  return type !== 'inner'
}

export const allowDrag = (draggingNode: any) => {
  // category 和 exam_type 节点不可拖拽
  return !draggingNode.data.node_type
}

// ============ Tree Fetching ============
export const fetchKnowledgeTree = async () => {
  try {
    const response = await knowledgeAPI.getHierarchyTrees()
    knowledgeTreeData.value = response.data?.trees || response.data || []
    filteredTreeData.value = knowledgeTreeData.value
    calculateStats()
  } catch (error) {
    console.error('获取知识树失败:', error)
    knowledgeTreeData.value = []
    filteredTreeData.value = []
    calculateStats()
  }
}

// ============ Stats Calculation ============
const countDescendantKnowledge = (node: KnowledgeNode): number => {
  if (!node) return 0
  if (!node.node_type) return 1
  let count = 0
  if (node.children) {
    for (const child of node.children) {
      count += countDescendantKnowledge(child)
    }
  }
  return count
}

export const calculateStats = () => {
  // 递归统计
  let kpCount = 0
  let catCount = 0
  let etCount = 0
  const collectStats = (nodes: KnowledgeNode[]) => {
    for (const node of nodes) {
      if (node.node_type === 'category') {
        catCount++
      } else if (node.node_type === 'exam_type') {
        etCount++
      } else {
        kpCount++
      }
      if (node.children) collectStats(node.children)
    }
  }
  collectStats(knowledgeTreeData.value)
  totalKnowledgeCount.value = kpCount
  categoryCount.value = catCount
  examTypeCount.value = etCount
}

// ============ Search ============
export const handleTreeSearch = () => {
  if (!treeSearchKeyword.value) {
    filteredTreeData.value = knowledgeTreeData.value
    return
  }
  const keyword = treeSearchKeyword.value.toLowerCase()
  const filterTree = (nodes: KnowledgeNode[]): KnowledgeNode[] => {
    const result: KnowledgeNode[] = []
    for (const node of nodes) {
      if (node.node_type === 'category' || node.node_type === 'exam_type') {
        // 虚拟节点保留，但过滤子节点
        const filteredChildren = filterTree(node.children || [])
        if (filteredChildren.length > 0) {
          result.push({ ...node, children: filteredChildren } as KnowledgeNode)
        }
      } else {
        // 知识点节点，按名称匹配
        if (node.name.toLowerCase().includes(keyword)) {
          result.push(node)
        } else if (node.children) {
          const filteredChildren = filterTree(node.children)
          if (filteredChildren.length > 0) {
            result.push({ ...node, children: filteredChildren } as KnowledgeNode)
          }
        }
      }
    }
    return result
  }
  filteredTreeData.value = filterTree(knowledgeTreeData.value)
}

// ============ Node Click ============
export const handleNodeClick = async (data: KnowledgeNode) => {
  selectedKnowledge.value = { ...data }
  // 如果是知识点节点，查找额外信息
  if (!data.node_type) {
    const findParentName = (nodes: KnowledgeNode[], targetId: number, parentName: string | null = null): string | null | undefined => {
      for (const node of nodes) {
        if (node.id === targetId && !node.node_type) {
          return parentName
        }
        if (node.children) {
          const found = findParentName(node.children, targetId, node.node_type ? null : node.name)
          if (found !== undefined) return found
        }
      }
      return undefined
    }
    selectedKnowledge.value.parentName = findParentName(knowledgeTreeData.value, data.id)

    // 查找所属种类和科目名称
    const findCategoryExamType = (nodes: KnowledgeNode[], targetId: number, catName: string = '', etName: string = ''): { categoryName: string; examTypeName: string } | null => {
      for (const node of nodes) {
        if (node.node_type === 'category') {
          if (node.children) {
            const found = findCategoryExamType(node.children, targetId, node.name, etName)
            if (found) return found
          }
        } else if (node.node_type === 'exam_type') {
          if (node.children) {
            const found = findCategoryExamType(node.children, targetId, catName, node.name)
            if (found) return found
          }
        } else if (node.id === targetId) {
          return { categoryName: catName, examTypeName: etName }
        }
      }
      return null
    }
    const info = findCategoryExamType(knowledgeTreeData.value, data.id)
    if (info) {
      selectedKnowledge.value.categoryName = info.categoryName
      selectedKnowledge.value.examTypeName = info.examTypeName
    }

    // 获取相关题目
    try {
      const response = await knowledgeAPI.getKnowledgePointQuestions(data.id)
      relatedQuestions.value = response.data?.questions || []
    } catch (error) {
      relatedQuestions.value = []
    }
  }
}

// ============ Context Menu ============
export const handleNodeContextMenu = (event: MouseEvent, data: KnowledgeNode) => {
  event.preventDefault()
  contextMenuNode.value = data
  contextMenuX.value = event.clientX
  contextMenuY.value = event.clientY
  contextMenuVisible.value = true
}

export const hideContextMenu = () => {
  contextMenuVisible.value = false
}

// ============ Drag & Drop Handlers ============
export const handleDragStart = (node: any) => {
  console.log('Drag started:', node.data.name)
}

export const handleDragEnd = async (draggingNode: any, dropNode: any, type: string) => {
  if (type !== 'before' && type !== 'after' && type !== 'inner') {
    return
  }

  const draggedId = draggingNode.data.id
  const draggedParentId = draggingNode.data.parent_id || draggingNode.data.parentId || null
  const dropId = dropNode.data.id

  // 计算新的父节点和顺序
  let newParentId: number | null = null
  let newOrder = 0

  if (type === 'inner') {
    // 拖到节点内部：成为子节点
    newParentId = dropId
  } else {
    // 拖到节点之前/之后：保持同级，更新 parent_id
    newParentId = dropNode.data.parent_id || dropNode.data.parentId || null
  }

  try {
    // 计算 order：在同级节点中插入到适当位置
    const siblings = knowledgeTreeData.value.flatMap((cat: any) => {
      if (cat.children) {
        if (newParentId === null) {
          // 顶级节点
          return cat.node_type ? [] : [cat, ...(cat.children || [])]
        }
        if (cat.id === newParentId) {
          return cat.children || []
        }
      }
      return []
    })

    const dropIndex = siblings.findIndex((n: any) => n.id === dropId)
    if (dropIndex >= 0) {
      newOrder = type === 'after' ? dropIndex + 1 : dropIndex
    } else {
      newOrder = siblings.length
    }

    // 调用后端更新
    await knowledgeAPI.updateNode(draggedId, {
      parentId: newParentId,
      sortOrder: newOrder,
    })

    ElMessage.success('节点顺序已更新')
    await fetchKnowledgeTree()
  } catch (error) {
    console.error('更新节点顺序失败:', error)
    ElMessage.error('更新顺序失败，请重试')
    await fetchKnowledgeTree()
  }
}

// ============ CRUD Operations ============
export const openCreateDialog = () => {
  isEdit.value = false
  resetForm()
  dialogVisible.value = true
}

export const handleAddKnowledgeUnderExamType = () => {
  hideContextMenu()
  if (contextMenuNode.value) {
    isEdit.value = false
    resetForm()
    // 根据选中的 exam_type 节点自动设置种类和科目
    const etNode = contextMenuNode.value
    if (etNode.exam_type_id) {
      knowledgeForm.examTypeId = etNode.exam_type_id
      // 查找对应的 categoryId
      const etObj = examTypeOptions.value.find(e => e.id === etNode.exam_type_id)
      if (etObj?.category_id) {
        knowledgeForm.categoryId = etObj.category_id
      }
    }
    dialogVisible.value = true
  }
}

export const openEditDialog = () => {
  if (!selectedKnowledge.value) return
  isEdit.value = true
  Object.assign(knowledgeForm, {
    id: selectedKnowledge.value.id,
    name: selectedKnowledge.value.name,
    parentId: selectedKnowledge.value.parent_id || selectedKnowledge.value.parentId || null,
    categoryId: selectedKnowledge.value.categoryId || null,
    examTypeId: selectedKnowledge.value.examTypeId || null,
    sortOrder: selectedKnowledge.value.sortOrder || selectedKnowledge.value.order || 0,
    description: selectedKnowledge.value.description || ''
  })
  dialogVisible.value = true
}

export const resetForm = () => {
  knowledgeForm.id = null
  knowledgeForm.name = ''
  knowledgeForm.parentId = null
  knowledgeForm.categoryId = null
  knowledgeForm.examTypeId = null
  knowledgeForm.sortOrder = 0
  knowledgeForm.description = ''
}

export const submitForm = async () => {
  try {
    submitLoading.value = true
    if (isEdit.value) {
      await knowledgeAPI.updateNode(knowledgeForm.id, knowledgeForm)
      ElMessage.success('更新成功')
    } else {
      await knowledgeAPI.createNode(knowledgeForm)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchKnowledgeTree()
  } catch (error) {
    ElMessage.error('操作失败')
  } finally {
    submitLoading.value = false
  }
}

export const deleteKnowledge = () => {
  if (!selectedKnowledge.value) return
  ElMessageBox.confirm(
    `确定要删除知识点"${selectedKnowledge.value.name}"吗？${
      selectedKnowledge.value.children?.length
        ? '（该知识点下有子节点，将一并删除）'
        : ''
    }`,
    '提示',
    { type: 'warning' }
  ).then(async () => {
    try {
      await knowledgeAPI.deleteNode(selectedKnowledge.value!.id)
      ElMessage.success('删除成功')
      selectedKnowledge.value = null
      fetchKnowledgeTree()
    } catch (error) {
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

// ============ Context Menu Actions ============
export const handleAddChild = () => {
  hideContextMenu()
  if (contextMenuNode.value) {
    knowledgeForm.parentId = contextMenuNode.value.id
    isEdit.value = false
    resetForm()
    knowledgeForm.parentId = contextMenuNode.value.id
    dialogVisible.value = true
  }
}

export const handleRename = () => {
  hideContextMenu()
  if (contextMenuNode.value) {
    selectedKnowledge.value = contextMenuNode.value
    openEditDialog()
  }
}

export const handleDelete = () => {
  hideContextMenu()
  if (contextMenuNode.value) {
    selectedKnowledge.value = contextMenuNode.value
    deleteKnowledge()
  }
}

// ============ Import Functions ============
export const handleImport = () => {
  importMode.value = 'file'
  importDialogVisible.value = true
  resetImportState()
}

export const resetImportState = () => {
  selectedFile.value = null
  aiSelectedFile.value = null
  aiResult.value = null
  aiAnalyzing.value = false
  if (uploadRef.value) uploadRef.value.clearFiles()
  if (aiUploadRef.value) aiUploadRef.value.clearFiles()
}

export const closeImportDialog = () => {
  importDialogVisible.value = false
  resetImportState()
}

export const handleFileChange = (file: File) => {
  selectedFile.value = file
}

export const handleAIFileChange = (file: File) => {
  aiSelectedFile.value = file
  // 上传文件后自动触发规则解析（毫秒级，无需用户额外操作）
  autoRuleAnalyze()
}

export const autoRuleAnalyze = async () => {
  if (!aiSelectedFile.value) return

  aiAnalyzing.value = false
  aiResult.value = null

  const formData = new FormData()
  formData.append('file', aiSelectedFile.value)
  formData.append('parent_id', String(aiImportForm.parentId || ''))
  formData.append('category', typeof aiImportForm.categoryId === 'string' ? aiImportForm.categoryId : 'default')
  formData.append('category_id', String(aiImportForm.categoryId || ''))

  try {
    // 第一步：规则解析（毫秒级，先展示结果让用户看到）
    const response = await knowledgeAPI.ruleAnalyze(formData)
    aiResult.value = response.data

    if (response.data.success) {
      ElMessage.success(`结构解析完成，提取 ${response.data.total_points} 个知识点，正在AI深度归纳...`)
      // 第二步：自动触发AI深度归纳（后台进行，完成后自动替换结果）
      startAIAnalysis()
    } else {
      ElMessage.error(response.data.error || '解析失败')
    }
  } catch (error) {
    console.error('规则解析失败:', error)
    ElMessage.error('文档解析失败，请重试')
  }
}

export const startAIAnalysis = async () => {
  if (!aiSelectedFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }

  aiAnalyzing.value = true
  // 保留规则解析结果作为参考，不清空（AI分析失败时可回退）

  const formData = new FormData()
  formData.append('file', aiSelectedFile.value)
  formData.append('parent_id', String(aiImportForm.parentId || ''))
  formData.append('category', typeof aiImportForm.categoryId === 'string' ? aiImportForm.categoryId : 'default')
  formData.append('category_id', String(aiImportForm.categoryId || ''))

  console.log('开始AI深度分析 - parentId:', aiImportForm.parentId, 'categoryId:', aiImportForm.categoryId)

  try {
    const response = await knowledgeAPI.aiAnalyze(formData)
    aiResult.value = response.data
    console.log('AI分析完成 - parent_id in result:', response.data.parent_id)

    if (response.data.success) {
      ElMessage.success(response.data.message || 'AI 深度分析完成')
    } else {
      ElMessage.error(response.data.error || 'AI 分析失败')
    }
  } catch (error: any) {
    console.error('AI 分析失败:', error)
    ElMessage.error(error.message || 'AI 分析失败，请重试')
  } finally {
    aiAnalyzing.value = false
  }
}

export const confirmAIImport = async () => {
  if (!aiResult.value || !aiResult.value.knowledge_points) {
    ElMessage.warning('没有可导入的知识点')
    return
  }

  console.log('确认导入 - knowledge_points count:', aiResult.value.knowledge_points.length, 'parent_id:', aiResult.value.parent_id, 'aiImportForm.parentId:', aiImportForm.parentId, 'document_name:', aiResult.value.document_name)

  try {
    const response = await knowledgeAPI.aiImport(
      aiResult.value.knowledge_points,
      aiImportForm.categoryId,
      aiImportForm.examTypeId,
      aiResult.value.parent_id || aiImportForm.parentId,
      aiResult.value.document_name  // 传递文档名，用于创建文档节点
    )

    if (response.data.success) {
      ElMessage.success(response.data.message || `成功导入 ${response.data.created_count} 个知识点`)
      closeImportDialog()
      fetchKnowledgeTree()
    } else {
      ElMessage.error(response.data.detail || '导入失败')
    }
  } catch (error: any) {
    console.error('导入失败:', error)
    ElMessage.error(error.message || '导入失败，请重试')
  }
}

export const confirmImport = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择要导入的文件')
    return
  }

  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    formData.append('parent_id', String(knowledgeForm.parentId || ''))
    formData.append('category_id', String(knowledgeForm.categoryId || ''))
    formData.append('exam_type_id', String(knowledgeForm.examTypeId || ''))

    const response = await knowledgeAPI.importFile(formData)

    if (response.data.success) {
      ElMessage.success(response.data.message || `成功导入 ${response.data.created_count} 个知识点`)
      closeImportDialog()
      fetchKnowledgeTree()
    } else {
      ElMessage.error(response.data.detail || response.data.message || '导入失败')
    }
  } catch (error: any) {
    console.error('导入失败:', error)
    ElMessage.error(error.message || '导入失败，请重试')
  }
}

// ============ Export ============
export const handleExport = () => {
  ElMessage.success('正在导出知识点，请稍候...')
}

// ============ Batch Import ============
export const handleBatchImport = () => {
  if (!routerRef) {
    ElMessage.warning('路由未就绪，请重试')
    return
  }
  routerRef.push({ name: 'BatchKnowledge' })
}

// ============ Question Viewers ============
export const viewQuestion = (question: RelatedQuestion) => {
  ElMessage.info(`查看题目 ${question.id}`)
}

export const viewAllQuestions = () => {
  ElMessage.info('跳转到题目列表')
}

// ============ Utility Functions ============
export const formatDate = (date: string | null | undefined): string => {
  if (!date) return '-'
  const d = new Date(date)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export const truncateContent = (content: string | null | undefined): string => {
  if (!content) return ''
  return content.length > 20 ? content.substring(0, 20) + '...' : content
}

// ============ Composable ============
export function useKnowledge() {
  // 安全修复（评估 P0-6）：生命周期钩子必须在组件 setup 内注册，
  // 模块顶层 onMounted 不会绑定任何组件，导致知识点树首屏为空、右键菜单关闭失效。
  routerRef = useRouter()
  onMounted(() => {
    // Parallelize independent tree/categories/examTypes fetching
    Promise.all([fetchKnowledgeTree(), fetchExamTypesAndCourses()])
    document.addEventListener('click', hideContextMenu)
  })

  onBeforeUnmount(() => {
    document.removeEventListener('click', hideContextMenu)
  })

  return {
    // Router
    router: routerRef,
    // Tree state
    treeRef,
    knowledgeTreeData,
    filteredTreeData,
    treeSearchKeyword,
    selectedKnowledge,
    relatedQuestions,
    // Dialog state
    dialogVisible,
    importDialogVisible,
    isEdit,
    submitLoading,
    // Context menu
    contextMenuVisible,
    contextMenuX,
    contextMenuY,
    contextMenuNode,
    // Import state
    importMode,
    uploadRef,
    aiUploadRef,
    selectedFile,
    aiSelectedFile,
    aiAnalyzing,
    aiResult,
    aiImportForm,
    // Tree config
    treeProps,
    // Form
    knowledgeForm,
    formRules,
    // Options
    examTypeOptions,
    examCategoryOptions,
    // Stats
    totalKnowledgeCount,
    categoryCount,
    examTypeCount,
    // Computed
    knowledgeOnlyTreeData,
    filteredFormExamTypeOptions,
    filteredAIExamTypeOptions,
    defaultExpandedKeys,
    // Actions
    handleFormCategoryChange,
    fetchExamTypesAndCourses,
    allowDrop,
    allowDrag,
    fetchKnowledgeTree,
    calculateStats,
    handleTreeSearch,
    handleNodeClick,
    handleNodeContextMenu,
    hideContextMenu,
    handleDragStart,
    handleDragEnd,
    openCreateDialog,
    handleAddKnowledgeUnderExamType,
    openEditDialog,
    resetForm,
    submitForm,
    deleteKnowledge,
    handleAddChild,
    handleRename,
    handleDelete,
    handleImport,
    resetImportState,
    closeImportDialog,
    handleFileChange,
    handleAIFileChange,
    autoRuleAnalyze,
    startAIAnalysis,
    confirmAIImport,
    confirmImport,
    handleExport,
    handleBatchImport,
    viewQuestion,
    viewAllQuestions,
    // Utilities
    formatDate,
    truncateContent
  }
}
