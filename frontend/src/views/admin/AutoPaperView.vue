<template>
  <div class="auto-paper-view">
    <el-card>
      <template #header>
        <div class="card-header">
          <h3>智能组卷</h3>
          <div class="header-actions">
            <el-button @click="saveDraft" :disabled="currentStep < 4">
              <el-icon><Document /></el-icon>
              保存草稿
            </el-button>
            <el-button type="primary" @click="publishPaper" :disabled="currentStep < 4">
              <el-icon><Promotion /></el-icon>
              直接发布
            </el-button>
          </div>
        </div>
      </template>

      <!-- 步骤条 -->
      <div class="steps-container">
        <el-steps :active="currentStep" finish-status="success" align-center>
          <el-step title="选择模板" :icon="Document" />
          <el-step title="基本信息" :icon="Edit" />
          <el-step title="知识点配置" :icon="Collection" />
          <el-step title="AI分配题目" :icon="MagicStick" />
          <el-step title="调整预览" :icon="View" />
        </el-steps>
      </div>

      <!-- Step 1: 选择模板 -->
      <div v-show="currentStep === 0" class="step-content">
        <div class="template-section">
          <h4>选择组卷模板</h4>
          <div class="template-grid">
            <div
              v-for="template in templates"
              :key="template.id"
              class="template-card"
              :class="{ active: selectedTemplate?.id === template.id }"
              @click="selectTemplate(template)"
            >
              <div class="template-icon">
                <el-icon :size="32"><component :is="template.icon" /></el-icon>
              </div>
              <div class="template-info">
                <h5>{{ template.name }}</h5>
                <p>{{ template.description }}</p>
                <div class="template-meta">
                  <span><el-icon><QuestionFilled /></el-icon> {{ template.questionCount }}题</span>
                  <span><el-icon><Timer /></el-icon> {{ template.duration }}分钟</span>
                </div>
              </div>
              <div v-if="selectedTemplate?.id === template.id" class="template-check">
                <el-icon><Check /></el-icon>
              </div>
            </div>
          </div>
        </div>

        <div class="custom-option">
          <el-checkbox v-model="useCustomMode" @change="handleCustomModeChange">
            自定义配置（不使用模板）
          </el-checkbox>
        </div>

        <div class="step-actions">
          <el-button type="primary" @click="nextStep" :disabled="!selectedTemplate && !useCustomMode">
            下一步
          </el-button>
        </div>
      </div>

      <!-- Step 2: 基本信息 -->
      <div v-show="currentStep === 1" class="step-content">
        <div class="form-section">
          <h4>试卷基本信息</h4>
          <el-form :model="paperForm" label-width="120px" class="paper-form">
            <el-form-item label="试卷名称" required>
              <el-input v-model="paperForm.title" placeholder="请输入试卷名称" style="width: 400px" />
            </el-form-item>
            <el-form-item label="考试种类" required>
              <el-select v-model="paperForm.categoryId" placeholder="请选择考试种类" style="width: 300px" @change="handleCategoryChange">
                <el-option v-for="cat in examCategories" :key="cat.id" :label="cat.name" :value="cat.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="考试科目" required>
              <el-select v-model="paperForm.subjectId" placeholder="请先选择考试种类" style="width: 300px" :disabled="!paperForm.categoryId">
                <el-option v-for="type in examTypes" :key="type.id" :label="type.name" :value="type.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="时长（分钟）">
              <el-input-number v-model="paperForm.duration" :min="30" :max="300" />
            </el-form-item>
            <el-form-item label="总分">
              <el-input-number v-model="paperForm.totalScore" :min="100" :max="500" :step="10" />
            </el-form-item>
            <el-form-item label="及格线">
              <el-input-number v-model="paperForm.passScore" :min="0" :max="paperForm.totalScore" />
            </el-form-item>
            <el-form-item label="显示答案">
              <el-switch v-model="paperForm.showAnswer" />
            </el-form-item>
          </el-form>
        </div>

        <div class="step-actions">
          <el-button @click="prevStep">上一步</el-button>
          <el-button type="primary" @click="nextStep" :disabled="!paperForm.title || !paperForm.subjectId">
            下一步
          </el-button>
        </div>
      </div>

      <!-- Step 3: 知识点配置 -->
      <div v-show="currentStep === 2" class="step-content">
        <!-- 不选择知识点复选框 - 所有模板都显示 -->
        <div style="margin-bottom: 20px;">
          <el-checkbox
            v-model="skipKnowledgePoints"
            @change="handleSkipKnowledgeChange"
          >
            不选择知识点，使用该科目下所有题目
          </el-checkbox>
        </div>
        <div :class="showKnowledgeTree ? 'knowledge-config' : 'knowledge-config-full'">
          <!-- 模拟测试卷不显示知识点树，只显示权重配置 -->
          <div v-if="showKnowledgeTree" class="config-left">
            <h4>选择知识点</h4>
            <div class="tree-scroll-wrapper" :class="{ 'is-disabled': skipKnowledgePoints }">
              <el-tree
                ref="knowledgeTreeRef"
                :data="knowledgeTree"
                :props="{ children: 'children', label: 'name' }"
                node-key="id"
                show-checkbox
                default-expand-all
                :disabled="skipKnowledgePoints"
                @check="handleKnowledgeChange"
              />
            </div>
          </div>

          <!-- 右侧：知识点权重配置 -->
          <div :class="showKnowledgeTree ? 'config-right' : 'config-full'">
            <h4>
              {{ skipKnowledgePoints ? '使用所有题目' : (showKnowledgeTree ? '知识点权重配置' : '权重配置（已自动选择全部知识点）') }}
            </h4>
            <div v-if="skipKnowledgePoints" class="weight-message">
              <el-alert type="info" :closable="false">
                将使用该科目下所有已审核通过的题目进行组卷，不限制知识点。
              </el-alert>
            </div>
            <div v-else class="weight-sliders">
              <div
                v-for="kp in selectedKnowledgePoints"
                :key="kp.id"
                class="weight-item"
              >
                <div class="weight-header">
                  <span class="kp-name">{{ kp.label }}</span>
                  <span class="kp-weight">{{ kp.weight }}%</span>
                </div>
                <el-slider
                  v-model="kp.weight"
                  :min="0"
                  :max="100"
                  :step="5"
                  @change="handleWeightChange"
                />
              </div>
            </div>

            <div v-if="!skipKnowledgePoints" class="weight-summary">
              <span>总权重：{{ totalWeight }}%</span>
              <el-button
                v-if="totalWeight !== 100"
                type="warning"
                size="small"
                @click="autoBalanceWeight"
              >
                自动平衡
              </el-button>
            </div>

            <div v-if="!skipKnowledgePoints" class="weight-chart">
              <h5>权重分布</h5>
              <div class="chart-container">
                <div
                  v-for="(kp, index) in selectedKnowledgePoints"
                  :key="kp.id"
                  class="chart-segment"
                  :style="{
                    width: kp.weight + '%',
                    backgroundColor: chartColors[index % chartColors.length]
                  }"
                >
                  <span v-if="kp.weight > 10">{{ kp.weight }}%</span>
                </div>
              </div>
              <div class="chart-legend">
                <div
                  v-for="(kp, index) in selectedKnowledgePoints"
                  :key="kp.id"
                  class="legend-item"
                >
                  <span
                    class="legend-color"
                    :style="{ backgroundColor: chartColors[index % chartColors.length] }"
                  ></span>
                  <span class="legend-label">{{ kp.label }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="step-actions">
          <el-button @click="prevStep">上一步</el-button>
          <el-button
            type="primary"
            @click="nextStep"
            :disabled="!skipKnowledgePoints && selectedKnowledgePoints.length === 0"
          >
            下一步
          </el-button>
        </div>
      </div>

      <!-- Step 4: AI分配题目 -->
      <div v-show="currentStep === 3" class="step-content">
        <div class="type-config">
          <h4>题型配比配置</h4>
          <div class="type-table">
            <el-table :data="questionTypeConfig" stripe style="width: 100%">
              <el-table-column prop="typeName" label="题型" width="120" />
              <el-table-column label="题目数量" width="180">
                <template #default="{ row }">
                  <el-input-number
                    v-model="row.count"
                    :min="0"
                    :max="50"
                    size="small"
                    @change="calculateTotalQuestions"
                  />
                </template>
              </el-table-column>
              <el-table-column label="每题分值" width="180">
                <template #default="{ row }">
                  <el-input-number
                    v-model="row.score"
                    :min="1"
                    :max="20"
                    size="small"
                    @change="calculateTotalScore"
                  />
                </template>
              </el-table-column>
              <el-table-column label="小计">
                <template #default="{ row }">
                  <span class="subtotal">{{ row.count * row.score }} 分</span>
                </template>
              </el-table-column>
              <el-table-column prop="difficulty" label="难度分布" min-width="320">
                <template #default="{ row }">
                  <div class="difficulty-dist">
                    <span class="dist-label">易</span>
                    <el-input-number
                      v-model="row.easyRatio"
                      :min="0"
                      :max="100"
                      size="small"
                      controls-position="right"
                      :step="10"
                    />
                    <span class="dist-label">中</span>
                    <el-input-number
                      v-model="row.mediumRatio"
                      :min="0"
                      :max="100"
                      size="small"
                      controls-position="right"
                      :step="10"
                    />
                    <span class="dist-label">难</span>
                    <el-input-number
                      v-model="row.hardRatio"
                      :min="0"
                      :max="100"
                      size="small"
                      controls-position="right"
                      :step="10"
                    />
                  </div>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <div class="total-summary">
            <div class="summary-item">
              <span class="label">总题数：</span>
              <span class="value">{{ totalQuestionCount }} 题</span>
            </div>
            <div class="summary-item">
              <span class="label">总分：</span>
              <span class="value">{{ totalConfiguredScore }} 分</span>
            </div>
            <div class="summary-item" v-if="!skipKnowledgePoints">
              <el-button type="warning" size="small" @click="autoAdjustDifficulty">
                <el-icon><MagicStick /></el-icon>
                智能调整难度分布
              </el-button>
            </div>
            <div class="summary-item" v-else>
              <el-tooltip content="不选择知识点时，题目难度为默认值，无需调整分布">
                <el-button type="warning" size="small" disabled>
                  <el-icon><MagicStick /></el-icon>
                  智能调整难度分布
                </el-button>
              </el-tooltip>
            </div>
          </div>

          <div class="ai-generate-action">
            <el-button type="primary" size="large" @click="generateQuestions" :loading="generating">
              <el-icon v-if="!generating"><MagicStick /></el-icon>
              {{ generating ? 'AI正在分配题目...' : 'AI智能分配题目' }}
            </el-button>
          </div>
        </div>

        <div class="step-actions">
          <el-button @click="prevStep">上一步</el-button>
        </div>
      </div>

      <!-- Step 5: 调整预览 -->
      <div v-show="currentStep === 4" class="step-content">
        <div class="preview-section">
          <div class="preview-header">
            <h4>试卷预览</h4>
            <div class="preview-actions" v-if="generatedQuestions.length === 0">
              <el-button @click="reorderQuestions">
                <el-icon><Rank /></el-icon>
                调整顺序
              </el-button>
              <el-button @click="exportWord">
                <el-icon><Download /></el-icon>
                导出Word
              </el-button>
              <el-button @click="exportPdf">
                <el-icon><Download /></el-icon>
                导出PDF
              </el-button>
            </div>
          </div>

          <div class="paper-preview">
            <div class="paper-header-info">
              <h2>{{ paperForm.title || '未命名试卷' }}</h2>
              <div class="paper-meta">
                <span>科目：{{ examTypes.find(t => t.id === paperForm.subjectId)?.name || '未知' }}</span>
                <span>时长：{{ paperForm.duration }}分钟</span>
                <span>总分：{{ paperForm.totalScore }}分</span>
                <span>及格：{{ paperForm.passScore }}分</span>
              </div>
            </div>

            <div class="question-list">
              <div
                v-for="(q, index) in generatedQuestions"
                :key="q.id"
                class="question-item"
                draggable="true"
                @dragstart="handleDragStart(index)"
                @dragover.prevent
                @drop="handleDrop(index)"
              >
                <div class="question-number">
                  <el-icon class="drag-handle"><Rank /></el-icon>
                  <span>{{ index + 1 }}</span>
                </div>
                <div class="question-content">
                  <div class="question-text">
                    <el-tag size="small" class="type-tag">{{ q.typeName }}</el-tag>
                    <el-tag
                      size="small"
                      :type="getDifficultyType(q.difficulty)"
                      class="difficulty-tag"
                    >
                      {{ q.difficultyName }}
                    </el-tag>
                    <span class="question-desc">{{ q.content }}</span>
                  </div>
                  <div v-if="q.type === 'single_choice' || q.type === 'multiple_choice'" class="question-options">
                    <div v-for="opt in (q.options || [])" :key="opt.id || opt.option_label" class="option-line">
                      <span class="opt-label">{{ opt.option_label }}.</span>
                      <span>{{ opt.option_content }}</span>
                    </div>
                  </div>
                  <div class="question-score">（{{ q.score }}分）</div>
                </div>
                <div class="question-actions">
                  <el-button link size="small" @click="replaceQuestion(index)">
                    <el-icon><RefreshRight /></el-icon>
                    替换
                  </el-button>
                  <el-button link size="small" @click="removeQuestion(index)">
                    <el-icon><Delete /></el-icon>
                  </el-button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="step-actions">
          <el-button @click="prevStep">上一步</el-button>
          <el-button type="success" @click="publishPaper">
            <el-icon><Promotion /></el-icon>
            发布试卷
          </el-button>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Document, Edit, Collection, MagicStick, View,
  Check, QuestionFilled, Timer, Promotion, Rank,
  Download, RefreshRight, Delete
} from '@element-plus/icons-vue'
import { systemAPI, knowledgeAPI, paperAPI, api } from '@/api'

const currentStep = ref(0)
const generating = ref(false)
const useCustomMode = ref(false)
const selectedTemplate = ref(null)
const knowledgeTreeRef = ref(null)
const dragIndex = ref(-1)
const currentPaperId = ref(null)  // 当前生成的试卷ID

// 是否显示知识点树（模拟测试卷不需要显示，直接显示权重配置）
const showKnowledgeTree = computed(() => {
  // 如果使用自定义模式，显示知识点树
  if (useCustomMode.value) return true
  // 如果选择了专项练习卷，显示知识点树
  if (selectedTemplate.value?.id === 3) return true
  // 否则（模拟测试卷）不显示知识点树
  return false
})

// 考试种类和科目数据
const examCategories = ref([])
const examTypes = ref([])

const templates = [
  // {
  //   id: 1,
  //   name: '历年真题卷',
  //   description: '基于近5年真实考试题目，难度适中',
  //   icon: 'Document',
  //   questionCount: 50,
  //   duration: 120
  // },
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
  },
  // {
  //   id: 4,
  //   name: '考前冲刺卷',
  //   description: '高难度考前模拟，检验学习成果',
  //   icon: 'MagicStick',
  //   questionCount: 35,
  //   duration: 90
  // }
]

const paperForm = reactive({
  title: '',
  categoryId: null,     // 考试种类ID
  subjectId: null,       // 科目ID (exam_type_id)
  duration: 120,
  totalScore: 100,
  passScore: 60,
  showAnswer: false
})

// 知识点树数据
const knowledgeTree = ref([])

const selectedKnowledgePoints = ref([])
const skipKnowledgePoints = ref(false)  // 是否跳过知识点选择，使用所有题目
const chartColors = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399', '#c71585']

// 题型配置 - 使用后端期望的题型值
const questionTypeConfig = reactive([
  { type: 'single_choice', typeName: '单选题', count: 20, score: 2, easyRatio: 40, mediumRatio: 40, hardRatio: 20 },
  { type: 'multiple_choice', typeName: '多选题', count: 10, score: 4, easyRatio: 30, mediumRatio: 40, hardRatio: 30 },
  { type: 'true_false', typeName: '判断题', count: 10, score: 2, easyRatio: 50, mediumRatio: 30, hardRatio: 20 },
  { type: 'essay', typeName: '简答题', count: 5, score: 8, easyRatio: 20, mediumRatio: 50, hardRatio: 30 }
])

const generatedQuestions = ref([])

const totalWeight = computed(() => {
  return selectedKnowledgePoints.value.reduce((sum, kp) => sum + kp.weight, 0)
})

const totalQuestionCount = computed(() => {
  return questionTypeConfig.reduce((sum, t) => sum + t.count, 0)
})

const totalConfiguredScore = computed(() => {
  return questionTypeConfig.reduce((sum, t) => sum + t.count * t.score, 0)
})

// 加载考试种类数据
const loadExamCategories = async () => {
  try {
    const res = await systemAPI.getExamCategories()
    examCategories.value = res.data.items || []
  } catch (error) {
    console.error('加载考试种类失败:', error)
  }
}

// 当选择考试种类变化时，加载对应科目
const handleCategoryChange = async (categoryId) => {
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

// 当选择科目变化时，加载对应知识点
const handleSubjectChange = async (subjectId) => {
  selectedKnowledgePoints.value = []
  knowledgeTree.value = []

  if (!subjectId) return

  try {
    const res = await knowledgeAPI.getHierarchyTrees({ exam_type_id: subjectId })
    knowledgeTree.value = res.data.trees || []
    console.log('加载的知识点树:', knowledgeTree.value)

    // 如果选择了模拟测试卷模板，加载完知识点后自动选择所有知识点
    if (selectedTemplate.value?.id === 2) {
      selectAllKnowledgePoints()
    }
  } catch (error) {
    console.error('加载知识点失败:', error)
  }
}

// 自动选择所有知识点（用于模拟测试卷）- 只选择挂在exam_type下的第一层知识点
const selectAllKnowledgePoints = async () => {
  if (!knowledgeTree.value || knowledgeTree.value.length === 0) return

  // 找到 exam_type 节点，取其直接子节点（挂在exam_type下的第一层知识点）
  let examTypeNode = null
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
    node => node.node_type !== 'category' && node.node_type !== 'exam_type'
  )

  // 构建知识点列表，同时统计子节点数量
  const kpList = firstLevelKps.map(kp => {
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
    const kpIds = kpList.map(kp => kp.id)
    const res = await knowledgeAPI.getQuestionCounts(kpIds)
    const countsData = res.data || {}

    // 计算总子节点数和总题目数
    const totalDescendants = kpList.reduce((sum, kp) => sum + kp._descendantCount, 0)
    const totalQuestions = Object.values(countsData).reduce((sum, info) => sum + (info.question_count || 0), 0)

    // 计算智能权重
    calculateIntelligentWeight(kpList, totalDescendants, totalQuestions, countsData)
  } catch (error) {
    console.error('获取知识点题目数量失败，使用平均权重:', error)
    // 失败时使用平均权重
    const baseWeight = Math.floor(100 / kpList.length)
    const remainder = 100 - baseWeight * kpList.length
    kpList.forEach((kp, index) => {
      kp.weight = baseWeight + (index < remainder ? 1 : 0)
    })
  }

  selectedKnowledgePoints.value = kpList

  // 同时设置树的勾选状态
  const allKeys = kpList.map(kp => kp.id)
  knowledgeTreeRef.value?.setCheckedKeys(allKeys)
}

// 统计节点的子节点数量（递归）
const countDescendants = (node) => {
  if (!node.children || node.children.length === 0) return 1
  let count = 1
  for (const child of node.children) {
    count += countDescendants(child)
  }
  return count
}

// 根据子节点数量和题目数量计算智能权重
// 公式：权重 = (子节点数量占比) × (1 - 题目数量占比 × 0.3)
const calculateIntelligentWeight = (kpList, totalDescendants, totalQuestions, countsData) => {
  if (kpList.length === 0) return

  // 计算各维度占比
  const weights = kpList.map(kp => {
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
      questionCount: questionCount,
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

  console.log('智能权重计算结果:', kpList.map(kp => ({
    id: kp.id,
    label: kp.label,
    weight: kp.weight,
    descendantCount: kp._descendantCount,
    questionCount: kp._questionCount
  })))
}

// 监听科目变化
watch(() => paperForm.subjectId, (newVal) => {
  if (newVal) {
    handleSubjectChange(newVal)
  }
})

onMounted(async () => {
  await loadExamCategories()
})

const selectTemplate = async (template) => {
  selectedTemplate.value = template
  useCustomMode.value = false
  paperForm.title = template.name
  paperForm.duration = template.duration

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

const handleCustomModeChange = (checked) => {
  if (checked) {
    selectedTemplate.value = null
    // 自定义模式：清空知识点选择，让用户手动选择
    knowledgeTreeRef.value?.setCheckedKeys([])
    selectedKnowledgePoints.value = []
  }
}

const nextStep = () => {
  if (currentStep.value < 4) {
    currentStep.value++
  }
}

const prevStep = () => {
  if (currentStep.value > 0) {
    currentStep.value--
  }
}

const handleSkipKnowledgeChange = (checked) => {
  if (checked) {
    // 清空知识点选择
    selectedKnowledgePoints.value = []
    knowledgeTreeRef.value?.setCheckedKeys([])
  }
}

const handleKnowledgeChange = () => {
  // 只获取完全选中的节点键，避免半选父节点被包含
  const checkedKeys = knowledgeTreeRef.value?.getCheckedKeys() || []

  if (checkedKeys.length === 0) {
    selectedKnowledgePoints.value = []
    return
  }

  // 构建所有节点的映射
  const allNodesMap = new Map()

  // 递归收集所有节点
  const collectNodes = (nodes) => {
    for (const node of nodes) {
      allNodesMap.set(node.id, node)
      if (node.children && node.children.length > 0) {
        collectNodes(node.children)
      }
    }
  }
  collectNodes(knowledgeTree.value)

  // 使用完全选中的键获取节点
  const checkedNodes = checkedKeys.map(key => allNodesMap.get(key)).filter(Boolean)

  // 找出每个选中节点对应的顶级父节点（挂在exam_type下的第一层知识点）
  const rootKnowledgePoints = new Map()

  for (const node of checkedNodes) {
    // 找出这个节点的最顶层父节点（挂在exam_type下的第一层知识点）
    let currentNode = node

    // 向上追溯直到找到挂在exam_type下的第一层知识点
    // 即 node_type 不是 'category' 也不是 'exam_type'，且 parent_id 为 null 或父节点是 exam_type
    while (currentNode) {
      const parentNode = currentNode.parent_id ? allNodesMap.get(currentNode.parent_id) : null

      // 如果当前节点挂在exam_type下（父节点是exam_type或者父节点是category而再上一层是exam_type）
      // 找到挂在exam_type下的直接子节点，即node_type不是category也不是exam_type的节点
      if (!parentNode) {
        // 没有父节点，说明是顶级节点
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

      // 否则继续向上找
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

  selectedKnowledgePoints.value = rootNodes
}

const handleWeightChange = () => {
  // 权重变化后的处理
}

const autoBalanceWeight = () => {
  const count = selectedKnowledgePoints.value.length
  if (count === 0) return

  const baseWeight = Math.floor(100 / count)
  const remainder = 100 - baseWeight * count

  selectedKnowledgePoints.value.forEach((kp, index) => {
    kp.weight = baseWeight + (index < remainder ? 1 : 0)
  })
}

// 智能调整难度分布 - 根据题库中实际可用的题目难度自动设置
const autoAdjustDifficulty = async () => {
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
    const kpIds = skipKnowledgePoints.value ? [] : selectedKnowledgePoints.value.map(kp => kp.id)
    const questionTypes = questionTypeConfig.map(t => t.type).filter(t => t)  // 获取配置的题型

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
    questionTypeConfig.forEach(t => {
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
      .map(([type, d]) => `${getTypeName(type)}易${d.easy_ratio}%/中${d.medium_ratio}%/难${d.hard_ratio}%`)
      .join('；')

    ElMessage.success(`已根据题库自动调整各题型难度分布（${distInfo}），题库共有${data.total}题`)
  } catch (error) {
    console.error('获取难度分布失败:', error)
    ElMessage.error('获取题库难度分布失败，请手动设置')
  }
}

const calculateTotalQuestions = () => {
  // 重新计算总分
  calculateTotalScore()
}

const calculateTotalScore = () => {
  // 分数计算
}

const generateQuestions = async () => {
  generating.value = true

  try {
    await ElMessageBox.confirm('AI将根据您的配置自动分配题目，是否继续？', '确认', {
      type: 'info'
    })

    // 构建题型配置（包含数量和每题分值）
    const questionTypeConfigBuild = {}
    questionTypeConfig.forEach(t => {
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
    questionTypeConfig.forEach(t => {
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
      knowledge_point_ids: skipKnowledgePoints.value ? [] : selectedKnowledgePoints.value.map(kp => kp.id),
      question_type_config: questionTypeConfigBuild,
      difficulty_config: difficultyConfig
    }

    console.log('发送智能组卷请求:', requestData)

    // 调用后端API
    const res = await paperAPI.autoGenerate(requestData)
    console.log('智能组卷响应:', res.data)

    // 检查是否有题型短缺通知
    if (res.data?.shortage_notice) {
      ElMessage.warning(res.data.shortage_notice)
    }

    // 处理返回数据 - PaperDetailResponse 格式
    if (res.data && res.data.questions && res.data.questions.length > 0) {
      currentPaperId.value = res.data.id

      generatedQuestions.value = res.data.questions.map((epq, index) => {
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
          knowledgePoint: selectedKnowledgePoints.value.find(kp => kp.id === q.chapter_id)?.label || ''
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
      return
    }
  } catch {
    // 用户取消
  } finally {
    generating.value = false
  }
}

// 将后端难度值(1-5)转换为前端难度等级
const getDifficultyLevel = (difficulty) => {
  if (difficulty <= 2) return 'easy'
  if (difficulty === 3) return 'medium'
  return 'hard'
}

// 获取题型名称
const getTypeName = (type) => {
  const map = {
    'single_choice': '单选题',
    'multiple_choice': '多选题',
    'true_false': '判断题',
    'essay': '简答题'
  }
  return map[type] || type
}

const getDifficultyNameByLevel = (difficulty) => {
  const map = { easy: '简单', medium: '中等', hard: '困难' }
  return map[difficulty] || difficulty
}

const getDifficultyType = (difficulty) => {
  const map = { easy: 'success', medium: 'warning', hard: 'danger' }
  return map[difficulty] || 'info'
}

const handleDragStart = (index) => {
  dragIndex.value = index
}

const handleDrop = (targetIndex) => {
  if (dragIndex.value === -1 || dragIndex.value === targetIndex) return

  const questions = [...generatedQuestions.value]
  const [removed] = questions.splice(dragIndex.value, 1)
  questions.splice(targetIndex, 0, removed)
  generatedQuestions.value = questions
  dragIndex.value = -1

  ElMessage.success('题目顺序已调整')
}

const reorderQuestions = () => {
  ElMessage.info('拖拽题目左侧手柄可调整顺序')
}

const replaceQuestion = (index) => {
  ElMessage.info('替换题目功能开发中')
}

const removeQuestion = (index) => {
  ElMessageBox.confirm('确定要移除这道题目吗？', '提示', {
    type: 'warning'
  }).then(() => {
    generatedQuestions.value.splice(index, 1)
    ElMessage.success('题目已移除')
  }).catch(() => {})
}

// 导出试卷
const exportPaper = async (format) => {
  if (!currentPaperId.value) {
    ElMessage.warning('请先生成试卷后再导出')
    return
  }

  try {
    ElMessage.info(`正在导出${format === 'word' ? 'Word' : 'PDF'}文档...`)

    const response = await api.post(`/papers/export`, {
      paper_id: currentPaperId.value,
      format: format
    }, {
      responseType: 'blob'
    })

    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.download = `${paperForm.title || '试卷'}.${format === 'word' ? 'docx' : 'pdf'}`
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

const exportWord = () => exportPaper('word')
const exportPdf = () => exportPaper('pdf')

const saveDraft = () => {
  if (!currentPaperId.value) {
    ElMessage.warning('请先生成试卷后再保存')
    return
  }
  ElMessage.success('试卷已保存为草稿')
}

const publishPaper = async () => {
  if (!currentPaperId.value) {
    ElMessage.warning('请先生成试卷后再发布')
    return
  }

  try {
    await ElMessageBox.confirm('确定要发布这份试卷吗？发布后将无法修改。', '确认发布', {
      type: 'info'
    })

    await api.post(`/papers/${currentPaperId.value}/publish`)
    ElMessage.success('试卷发布成功！')
  } catch (error) {
    console.error('发布失败:', error)
    ElMessage.error('发布失败，请稍后重试')
  }
}
</script>

<style scoped>
.auto-paper-view {
  width: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.steps-container {
  padding: 30px 50px;
  background: #f5f7fa;
  border-radius: 8px;
  margin-bottom: 24px;
}

.step-content {
  min-height: 500px;
  padding: 20px 0;
}

/* Step 1: 模板选择 */
.template-section h4,
.form-section h4,
.knowledge-config h4,
.type-config h4,
.preview-section h4 {
  margin: 0 0 20px 0;
  padding-bottom: 10px;
  border-bottom: 1px solid #eee;
  color: #303133;
}

.template-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.template-card {
  display: flex;
  align-items: center;
  padding: 20px;
  background: #fff;
  border: 2px solid #e4e7ed;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s;
  position: relative;
}

.template-card:hover {
  border-color: #409eff;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.2);
}

.template-card.active {
  border-color: #409eff;
  background: #ecf5ff;
}

.template-icon {
  width: 60px;
  height: 60px;
  background: #f5f7fa;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 16px;
  color: #409eff;
}

.template-card.active .template-icon {
  background: #409eff;
  color: #fff;
}

.template-info h5 {
  margin: 0 0 6px 0;
  font-size: 16px;
  color: #303133;
}

.template-info p {
  margin: 0 0 8px 0;
  font-size: 13px;
  color: #909399;
}

.template-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #606266;
}

.template-meta span {
  display: flex;
  align-items: center;
  gap: 4px;
}

.template-check {
  position: absolute;
  top: 10px;
  right: 10px;
  width: 24px;
  height: 24px;
  background: #409eff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}

.custom-option {
  padding: 16px;
  background: #fdf6ec;
  border-radius: 8px;
  margin-bottom: 20px;
}

/* Step 2: 基本信息 */
.paper-form {
  max-width: 600px;
}

/* Step 3: 知识点配置 */
.knowledge-config {
  display: grid;
  grid-template-columns: 1fr 1.2fr;
  gap: 30px;
}

.knowledge-config-full {
  display: block;
}

.config-left {
  background: #f5f7fa;
  padding: 20px;
  border-radius: 12px;
  overflow: auto;
  max-height: 500px;
}

.tree-scroll-wrapper {
  overflow-x: auto;
}

.tree-scroll-wrapper.is-disabled {
  opacity: 0.5;
  pointer-events: none;
}

::deep(.tree-scroll-wrapper .el-tree) {
  min-width: 100%;
}

.config-right {
  background: #fff;
  padding: 24px;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  max-height: 500px;
  overflow-y: auto;
}

.config-full {
  background: #fff;
  padding: 24px;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  width: 100%;
  max-height: 500px;
  overflow-y: auto;
}

.weight-sliders {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.weight-item {
  background: linear-gradient(135deg, #f8f9fb 0%, #f0f2f7 100%);
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 12px 14px;
  transition: all 0.3s;
}

.weight-item:hover {
  background: linear-gradient(135deg, #f0f2f7 0%, #e8ebf2 100%);
  border-color: #409eff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.15);
  transform: translateY(-1px);
}

.weight-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.kp-name {
  font-weight: 600;
  color: #303133;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.kp-name::before {
  content: '';
  display: inline-block;
  width: 3px;
  height: 10px;
  background: linear-gradient(180deg, #409eff, #67c23a);
  border-radius: 2px;
}

.kp-weight {
  color: #409eff;
  font-weight: bold;
  font-size: 13px;
  background: linear-gradient(135deg, #ecf5ff 0%, #d9edff 100%);
  padding: 2px 8px;
  border-radius: 4px;
}

.weight-summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 8px;
  margin-bottom: 20px;
  color: #fff;
}

.weight-summary span {
  font-size: 15px;
  font-weight: 500;
}

.weight-summary .el-button {
  background: rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: #fff;
}

.weight-summary .el-button:hover {
  background: rgba(255, 255, 255, 0.3);
}

.weight-chart {
  background: #fafbfc;
  border-radius: 8px;
  padding: 14px;
  border: 1px dashed #dcdfe6;
}

.weight-chart h5 {
  margin: 0 0 10px 0;
  color: #606266;
  font-size: 13px;
}

.chart-container {
  display: flex;
  height: 20px;
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 12px;
  box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.1);
}

.chart-segment {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 10px;
  font-weight: 600;
  min-width: 24px;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

.chart-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
}

.legend-color {
  width: 8px;
  height: 8px;
  border-radius: 2px;
}

.legend-label {
  font-size: 11px;
  color: #606266;
}

.weight-message {
  margin: 20px 0;
}

/* Step 4: 题型配置 */
.type-table {
  margin-bottom: 20px;
}

.subtotal {
  font-weight: 500;
  color: #409eff;
}

.difficulty-dist {
  display: flex;
  align-items: center;
  gap: 4px;
}

.difficulty-dist .el-input-number {
  width: 70px;
}

.dist-label {
  font-size: 12px;
  color: #909399;
}

.total-summary {
  display: flex;
  gap: 40px;
  padding: 16px 20px;
  background: #f5f7fa;
  border-radius: 8px;
  margin-bottom: 24px;
}

.summary-item .label {
  color: #909399;
  margin-right: 8px;
}

.summary-item .value {
  font-size: 18px;
  font-weight: bold;
  color: #409eff;
}

.ai-generate-action {
  text-align: center;
  padding: 30px 0;
}

/* Step 5: 预览 */
.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.preview-header h4 {
  margin: 0;
  padding: 0;
  border: none;
}

.preview-actions {
  display: flex;
  gap: 10px;
}

.paper-preview {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  padding: 30px;
}

.paper-header-info {
  text-align: center;
  margin-bottom: 30px;
  padding-bottom: 20px;
  border-bottom: 2px solid #409eff;
}

.paper-header-info h2 {
  margin: 0 0 16px 0;
  color: #303133;
}

.paper-meta {
  display: flex;
  justify-content: center;
  gap: 30px;
  color: #606266;
  font-size: 14px;
}

.question-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.question-item {
  display: flex;
  align-items: flex-start;
  padding: 16px;
  background: #fafafa;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  transition: all 0.3s;
}

.question-item:hover {
  background: #f5f7fa;
  border-color: #c0c4cc;
}

.question-number {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 60px;
  color: #409eff;
  font-weight: bold;
}

.drag-handle {
  cursor: grab;
  color: #909399;
}

.drag-handle:active {
  cursor: grabbing;
}

.question-content {
  flex: 1;
}

.question-text {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.type-tag {
  flex-shrink: 0;
}

.difficulty-tag {
  flex-shrink: 0;
}

.question-desc {
  color: #303133;
  line-height: 1.6;
}

.question-options {
  padding-left: 10px;
  margin-bottom: 8px;
}

.option-line {
  display: flex;
  line-height: 1.8;
}

.opt-label {
  min-width: 24px;
  font-weight: 500;
  color: #606266;
}

.question-score {
  color: #909399;
  font-size: 13px;
}

.question-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  opacity: 0;
  transition: opacity 0.3s;
}

.question-item:hover .question-actions {
  opacity: 1;
}

/* 步骤操作按钮 */
.step-actions {
  display: flex;
  justify-content: center;
  gap: 16px;
  padding: 30px 0;
  border-top: 1px solid #eee;
  margin-top: 30px;
}
</style>
