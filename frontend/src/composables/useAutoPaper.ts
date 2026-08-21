import { ref, reactive, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { systemAPI, knowledgeAPI, paperAPI } from '@/api'

// ============ Types ============
export interface KnowledgePoint {
  id: number
  name: string
  weight: number
  _descendantCount?: number
  questionCount?: number
  children?: KnowledgePoint[]
  node_type?: string
  parent_id?: number
  label?: string
}

export interface QuestionTypeConfig {
  type: string
  typeName: string
  count: number
  score: number
  easyRatio: number
  mediumRatio: number
  hardRatio: number
}

export interface PaperForm {
  title: string
  categoryId: number | null
  subjectId: number | null
  duration: number
  totalScore: number
  passScore: number
  showAnswer: boolean
}

export interface GeneratedQuestion {
  id: number
  examPaperQuestionId: number
  type: string
  typeName: string
  difficulty: string
  difficultyName: string
  content: string
  options: string[]
  answer: string
  score: number
  knowledgePoint: string
  selected?: boolean
}

export interface Template {
  id: number
  name: string
  description: string
  icon: string
  questionCount: number
  duration: number
  config?: any
}

// ============ Template Definitions ============
export const DEFAULT_TEMPLATES: Template[] = [
  {
    id: 2,
    name: '模拟测试卷',
    description: '根据教学大纲生成的模拟题目',
    icon: 'Collection',
    questionCount: 40,
    duration: 90
  },
  {
    id: 3,
    name: '专项练习卷',
    description: '针对特定知识点的强化练习',
    icon: 'QuestionFilled',
    questionCount: 30,
    duration: 60
  }
]

// ============ State ==========
export const currentStep = ref(0)
export const generating = ref(false)
export const generationProgress = ref(0)
export const generationStatus = ref('')
export const useCustomMode = ref(false)
export const selectedTemplate = ref<Template | null>(null)
export const knowledgeTreeRef = ref<any>(null)
export const dragIndex = ref(-1)
export const currentPaperId = ref<number | null>(null)
export const templates = ref<Template[]>(DEFAULT_TEMPLATES)
export const templatesLoading = ref(false)
export const previewVisible = ref(false)
export const previewData = ref<any>(null)

// ============ Computed ============
export const showKnowledgeTree = computed(() => {
  if (useCustomMode.value) return true
  if (selectedTemplate.value?.id === 3) return true
  return false
})

// ============ Paper Form ============
export const paperForm = reactive<PaperForm>({
  title: '',
  categoryId: null,
  subjectId: null,
  duration: 120,
  totalScore: 100,
  passScore: 60,
  showAnswer: false
})

// ============ Knowledge Tree ============
export const knowledgeTree = ref<any[]>([])
export const selectedKnowledgePoints = ref<KnowledgePoint[]>([])
export const skipKnowledgePoints = ref(false)
export const chartColors = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399', '#c71585']

// ============ Question Type Config ============
export const questionTypeConfig = reactive<QuestionTypeConfig[]>([
  { type: 'single_choice', typeName: '单选题', count: 20, score: 2, easyRatio: 40, mediumRatio: 40, hardRatio: 20 },
  { type: 'multiple_choice', typeName: '多选题', count: 10, score: 4, easyRatio: 30, mediumRatio: 40, hardRatio: 30 },
  { type: 'true_false', typeName: '判断题', count: 10, score: 2, easyRatio: 50, mediumRatio: 30, hardRatio: 20 },
  { type: 'essay', typeName: '简答题', count: 5, score: 8, easyRatio: 20, mediumRatio: 50, hardRatio: 30 }
])

// ============ Generated Questions ============
export const generatedQuestions = ref<GeneratedQuestion[]>([])

// ============ Computed Values ============
export const totalWeight = computed(() => {
  return selectedKnowledgePoints.value.reduce((sum, kp) => sum + kp.weight, 0)
})

export const totalQuestionCount = computed(() => {
  return questionTypeConfig.reduce((sum, t) => sum + t.count, 0)
})

export const totalConfiguredScore = computed(() => {
  return questionTypeConfig.reduce((sum, t) => sum + t.count * t.score, 0)
})

// ============ Exam Categories & Types ============
export const examCategories = ref<any[]>([])
export const examTypes = ref<any[]>([])

export const loadExamCategories = async () => {
  try {
    const res = await systemAPI.getExamCategories()
    examCategories.value = res.data.items || []
  } catch (error) {
    console.error('加载考试种类失败:', error)
  }
}

export const handleCategoryChange = async (categoryId: number) => {
  paperForm.subjectId = null
  examTypes.value = []
  selectedKnowledgePoints.value = []
  knowledgeTree.value = []

  if (!categoryId) return

  try {
    const res = await systemAPI.getExamTypes({ category_id: categoryId })
    examTypes.value = res.data.items || []
  } catch (error) {
    console.error('加载考试科目失败:', error)
  }
}

export const handleSubjectChange = async (subjectId: number) => {
  selectedKnowledgePoints.value = []
  knowledgeTree.value = []

  if (!subjectId) return

  try {
    const res = await knowledgeAPI.getHierarchyTrees({ exam_type_id: subjectId })
    knowledgeTree.value = res.data.trees || []
    console.log('加载的知识点树:', knowledgeTree.value)

    // 如果选择了模拟测试卷模板，加载完知识点后自动选择所有知识点
    if (selectedTemplate.value?.id === 2) {
      await selectAllKnowledgePoints()
    }
  } catch (error) {
    console.error('加载知识点失败:', error)
  }
}

// ============ Knowledge Point Selection ============
// 统计节点的子节点数量（递归）
const countDescendants = (node: any): number => {
  if (!node.children || node.children.length === 0) return 1
  let count = 1
  for (const child of node.children) {
    count += countDescendants(child)
  }
  return count
}

// 根据子节点数量和题目数量计算智能权重
// 公式：权重 = (子节点数量占比) × (1 - 题目数量占比 × 0.3)
const calculateIntelligentWeight = (
  kpList: any[],
  totalDescendants: number,
  totalQuestions: number,
  countsData: any
) => {
  if (kpList.length === 0) return

  // 计算各维度占比
  const weights = kpList.map((kp) => {
    const descendantRatio = totalDescendants > 0 ? kp._descendantCount / totalDescendants : 0
    const questionInfo = countsData[kp.id] || { question_count: 0 }
    const questionCount = questionInfo.question_count || 0
    const questionRatio = totalQuestions > 0 ? questionCount / totalQuestions : 0

    // 综合权重：子节点占比 × (1 - 题目占比 × 0.3)
    // 题目多的降权(最多降30%)，题目少的保持较高权重
    const adjustedRatio = descendantRatio * (1 - questionRatio * 0.3)

    return {
      id: kp.id,
      weight: adjustedRatio,
      questionCount,
      descendantCount: kp._descendantCount
    }
  })

  // 归一化，确保总和为100
  const totalWeight = weights.reduce((sum, w) => sum + w.weight, 0)

  weights.forEach((w, index) => {
    const normalizedWeight = totalWeight > 0 ? Math.round((w.weight / totalWeight) * 100) : Math.floor(100 / kpList.length)
    kpList[index].weight = normalizedWeight
  })

  // 确保总和为100，调整最大值
  const currentTotal = kpList.reduce((sum, kp) => sum + kp.weight, 0)
  if (currentTotal !== 100 && kpList.length > 0) {
    const diff = 100 - currentTotal
    // 找到最大权重的知识点进行补偿
    let maxIndex = 0
    let maxWeight = kpList[0].weight
    kpList.forEach((kp, index) => {
      if (kp.weight > maxWeight) {
        maxWeight = kp.weight
        maxIndex = index
      }
    })
    kpList[maxIndex].weight += diff
  }

  console.log('智能权重计算结果:', kpList.map((kp) => ({
    id: kp.id,
    label: kp.label,
    weight: kp.weight,
    descendantCount: kp._descendantCount,
    questionCount: kp._questionCount
  })))
}

// 自动选择所有知识点（用于模拟测试卷）- 只选择挂在exam_type下的第一层知识点
export const selectAllKnowledgePoints = async () => {
  if (!knowledgeTree.value || knowledgeTree.value.length === 0) return

  // 找到 exam_type 节点，取其直接子节点（挂在exam_type下的第一层知识点）
  let examTypeNode: any = null
  for (const cat of knowledgeTree.value) {
    if (cat.children) {
      for (const child of cat.children) {
        if (child.node_type === 'exam_type') {
          examTypeNode = child
          break
        }
      }
    }
    if (examTypeNode) break
  }

  if (!examTypeNode || !examTypeNode.children) return

  // 只取 exam_type 的直接子节点（第一层知识点）
  const firstLevelKps = examTypeNode.children.filter(
    (node: any) => node.node_type !== 'category' && node.node_type !== 'exam_type'
  )

  // 构建知识点列表，同时统计子节点数量
  const kpList = firstLevelKps.map((kp: any) => {
    const descendantCount = countDescendants(kp)
    return {
      id: kp.id,
      label: kp.name,
      weight: 0,
      _descendantCount: descendantCount
    }
  })

  // 获取各知识点的题目数量
  try {
    const kpIds = kpList.map((kp: any) => kp.id)
    const res = await knowledgeAPI.getQuestionCounts(kpIds)
    const countsData = res.data || {}

    // 计算总子节点数和总题目数
    const totalDescendants = kpList.reduce((sum: number, kp: any) => sum + kp._descendantCount, 0)
    const totalQuestions = Object.values(countsData).reduce((sum: number, info: any) => sum + (info.question_count || 0), 0)

    // 计算智能权重
    calculateIntelligentWeight(kpList, totalDescendants, totalQuestions, countsData)
  } catch (error) {
    console.error('获取知识点题目数量失败，使用平均权重:', error)
    // 失败时使用平均权重
    const baseWeight = Math.floor(100 / kpList.length)
    const remainder = 100 - baseWeight * kpList.length
    kpList.forEach((kp: any, index: number) => {
      kp.weight = baseWeight + (index < remainder ? 1 : 0)
    })
  }

  selectedKnowledgePoints.value = kpList

  // 同时设置树的勾选状态
  const allKeys = kpList.map((kp: any) => kp.id)
  knowledgeTreeRef.value?.setCheckedKeys(allKeys)
}

export const handleKnowledgeChange = () => {
  // 只获取完全选中的节点键，避免半选父节点被包含
  const checkedKeys = knowledgeTreeRef.value?.getCheckedKeys() || []

  if (checkedKeys.length === 0) {
    selectedKnowledgePoints.value = []
    return
  }

  // 构建所有节点的映射
  const allNodesMap = new Map<number, any>()

  // 递归收集所有节点
  const collectNodes = (nodes: any[]) => {
    for (const node of nodes) {
      allNodesMap.set(node.id, node)
      if (node.children && node.children.length > 0) {
        collectNodes(node.children)
      }
    }
  }
  collectNodes(knowledgeTree.value)

  // 使用完全选中的键获取节点
  const checkedNodes = checkedKeys.map((key: any) => allNodesMap.get(key)).filter(Boolean)

  // 找出每个选中节点对应的顶级父节点（挂在exam_type下的第一层知识点）
  const rootKnowledgePoints = new Map<number, { id: number; label: string; weight: number }>()

  for (const node of checkedNodes) {
    // 找出这个节点的最顶层父节点（挂在exam_type下的第一层知识点）
    let currentNode: any = node

    // 向上追溯直到找到挂在exam_type下的第一层知识点
    while (currentNode) {
      const parentNode = currentNode.parent_id ? allNodesMap.get(currentNode.parent_id) : null

      if (!parentNode) {
        break
      }

      // 如果父节点是exam_type，当前节点就是挂在exam_type下的第一层知识点
      if (parentNode.node_type === 'exam_type') {
        break
      }

      // 如果父节点是category，继续向上找
      if (parentNode.node_type === 'category') {
        currentNode = parentNode
        continue
      }

      currentNode = parentNode
    }

    // 如果找到的节点不是category也不是exam_type，就是我们要找的顶级知识点
    if (currentNode && currentNode.node_type !== 'category' && currentNode.node_type !== 'exam_type') {
      if (!rootKnowledgePoints.has(currentNode.id)) {
        rootKnowledgePoints.set(currentNode.id, {
          id: currentNode.id,
          label: currentNode.name,
          weight: 0
        })
      }
    }
  }

  // 转换为数组并计算权重
  const rootNodes = Array.from(rootKnowledgePoints.values())
  const count = rootNodes.length

  if (count > 0) {
    const baseWeight = Math.floor(100 / count)
    const remainder = 100 - baseWeight * count

    rootNodes.forEach((kp, index) => {
      kp.weight = baseWeight + (index < remainder ? 1 : 0)
    })
  }

  selectedKnowledgePoints.value = rootNodes as unknown as KnowledgePoint[]
}

export const autoBalanceWeight = () => {
  const count = selectedKnowledgePoints.value.length
  if (count === 0) return

  const baseWeight = Math.floor(100 / count)
  const remainder = 100 - baseWeight * count

  selectedKnowledgePoints.value.forEach((kp, index) => {
    kp.weight = baseWeight + (index < remainder ? 1 : 0)
  })
}

// ============ Template Selection ============
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

// ============ Navigation ============
export const nextStep = async () => {
  if (currentStep.value < 5) {
    // 如果从知识点配置进入大纲步骤，自动生成大纲
    if (currentStep.value === 2 && paperForm.subjectId) {
      try {
        await generateOutline()
      } catch (e) {
        console.error('自动生成大纲失败:', e)
      }
    }
    currentStep.value++
  }
}

export const prevStep = () => {
  if (currentStep.value > 0) {
    currentStep.value--
  }
}

// ============ Skip Knowledge ============
export const handleSkipKnowledgeChange = (checked: boolean) => {
  if (checked) {
    // 清空知识点选择
    selectedKnowledgePoints.value = []
    knowledgeTreeRef.value?.setCheckedKeys([])
  }
}

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

// ============ AI 试卷大纲 ============
export const outlineSections = ref<any[]>([])
export const outlineLoading = ref(false)
export const outlineMessage = ref('')

export const getKnowledgePointName = (kpId: number) => {
  const allNodes: any[] = []
  const collect = (nodes: any[]) => {
    for (const node of nodes) {
      allNodes.push(node)
      if (node.children) collect(node.children)
    }
  }
  collect(knowledgeTree.value)
  const node = allNodes.find(n => n.id === kpId)
  return node?.name || `知识点${kpId}`
}

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

// ============ Helper Functions ============
// 将后端难度值(1-5)转换为前端难度等级
export const getDifficultyLevel = (difficulty: number) => {
  if (difficulty <= 2) return 'easy'
  if (difficulty === 3) return 'medium'
  return 'hard'
}

// 获取题型名称
export const getTypeName = (type: string) => {
  const map: Record<string, string> = {
    'single_choice': '单选题',
    'multiple_choice': '多选题',
    'true_false': '判断题',
    'essay': '简答题'
  }
  return map[type] || type
}

export const getDifficultyNameByLevel = (difficulty: string) => {
  const map: Record<string, string> = { easy: '简单', medium: '中等', hard: '困难' }
  return map[difficulty] || difficulty
}

export const getDifficultyType = (difficulty: string) => {
  const map: Record<string, string> = { easy: 'success', medium: 'warning', hard: 'danger' }
  return map[difficulty] || 'info'
}

// ============ Drag & Drop ============
export const handleDragStart = (index: number) => {
  dragIndex.value = index
}

export const handleDrop = (targetIndex: number) => {
  if (dragIndex.value === -1 || dragIndex.value === targetIndex) return

  const questions = [...generatedQuestions.value]
  const [removed] = questions.splice(dragIndex.value, 1)
  questions.splice(targetIndex, 0, removed)
  generatedQuestions.value = questions
  dragIndex.value = -1

  ElMessage.success('题目顺序已调整')
}

export const reorderQuestions = () => {
  ElMessage.info('拖拽题目左侧手柄可调整顺序')
}

// ============ 权重/数量/分数回调与删题（评估 P0-3 补全） ============
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

export const removeQuestion = (index: number) => {
  if (index < 0 || index >= generatedQuestions.value.length) return
  generatedQuestions.value.splice(index, 1)
  ElMessage.success('题目已移除')
}

// ============ Composable ============
export function useAutoPaper() {
  // 评估 P2-13：模块级 watch 永不销毁（组件卸载后仍存活且可能触发无效请求），
  // 移入工厂内注册，随调用组件卸载自动清理。
  watch(() => paperForm.subjectId, (newVal) => {
    if (newVal) {
      handleSubjectChange(newVal)
    }
  })

  return {
    // State
    currentStep,
    generating,
    useCustomMode,
    selectedTemplate,
    knowledgeTreeRef,
    dragIndex,
    currentPaperId,
    // Computed
    showKnowledgeTree,
    // Form
    paperForm,
    // Knowledge tree
    knowledgeTree,
    selectedKnowledgePoints,
    skipKnowledgePoints,
    chartColors,
    // Question type config
    questionTypeConfig,
    // Generated questions
    generatedQuestions,
    // Computed values
    totalWeight,
    totalQuestionCount,
    totalConfiguredScore,
    // Exam data
    examCategories,
    examTypes,
    // Actions
    loadExamCategories,
    handleCategoryChange,
    handleSubjectChange,
    selectAllKnowledgePoints,
    handleKnowledgeChange,
    autoBalanceWeight,
    selectTemplate,
    handleCustomModeChange,
    nextStep,
    prevStep,
    handleSkipKnowledgeChange,
    autoAdjustDifficulty,
    generateQuestions,
    generateABPapers,
    // Helpers
    getTypeName,
    getDifficultyLevel,
    getDifficultyNameByLevel,
    getDifficultyType,
    handleDragStart,
    handleDrop,
    reorderQuestions,
    replaceQuestion,
    // Outline 与试卷操作（评估 P0-3：此前缺失导致 AutoPaperView 解构出 undefined）
    outlineSections,
    outlineLoading,
    outlineMessage,
    generateOutline,
    regenerateOutline,
    confirmOutline,
    getKnowledgePointName,
    saveDraft,
    publishPaper,
    exportWord,
    exportPdf,
    // 权重/数量/分数回调与删题（评估 P0-3 补全实现）
    handleWeightChange,
    calculateTotalQuestions,
    calculateTotalScore,
    removeQuestion,
    // Templates
    templates,
    templatesLoading,
    loadTemplates,
    saveAsTemplate,
    DEFAULT_TEMPLATES
  }
}
