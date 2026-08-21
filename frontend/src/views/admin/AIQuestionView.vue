<template>
  <div class="ai-question-page">
    <!-- 步骤指示器 -->
    <div class="steps-indicator">
      <el-steps :active="currentStep" finish-status="success" align-center>
        <el-step title="配置参数" description="设置出题规则" />
        <el-step title="生成题目" description="AI智能生成" />
        <el-step title="预览提交" description="审核后提交" />
      </el-steps>
    </div>

    <el-row :gutter="24" class="main-content">
      <!-- 左侧配置区 -->
      <el-col :xs="24" :lg="configPanelVisible ? 8 : 0" class="config-col">
        <el-card v-show="configPanelVisible" class="config-card">
          <template #header>
            <div class="card-header">
              <span class="title">出题配置</span>
              <el-button link @click="configPanelVisible = false">
                <el-icon><DArrowRight /></el-icon>
              </el-button>
            </div>
          </template>

          <el-form :model="configForm" label-position="top" class="config-form">
            <!-- 考试种类 -->
            <el-form-item>
              <template #label>
                <span class="required-mark">*</span>考试种类
              </template>
              <el-select v-model="configForm.categoryId" placeholder="请选择考试种类" style="width: 100%" :loading="loadingCategories" @change="handleCategoryChange">
                <el-option
                  v-for="item in categoryOptions"
                  :key="item.id"
                  :label="item.name"
                  :value="item.id"
                />
              </el-select>
            </el-form-item>

            <!-- 考试科目 -->
            <el-form-item>
              <template #label>
                <span class="required-mark">*</span>考试科目
              </template>
              <el-select
                v-model="configForm.examTypeId"
                placeholder="请选择考试科目"
                clearable
                style="width: 100%"
                :loading="loadingExamTypes"
                :disabled="!configForm.categoryId"
              >
                <el-option
                  v-for="item in filteredExamTypeOptions"
                  :key="item.id"
                  :label="item.name"
                  :value="item.id"
                />
              </el-select>
            </el-form-item>

            <!-- 题型选择 -->
            <el-form-item label="题目类型">
              <el-checkbox-group v-model="configForm.questionTypes" class="question-types-group">
                <el-checkbox value="choice">单选题</el-checkbox>
                <el-checkbox value="multiple">多选题</el-checkbox>
                <el-checkbox value="judge">判断题</el-checkbox>
                <el-checkbox value="short_answer">简答题</el-checkbox>
              </el-checkbox-group>
            </el-form-item>

            <!-- 出题模式 -->
            <el-form-item label="出题模式">
              <div class="mode-radio-wrapper">
                <el-radio-group v-model="configForm.generationMode" class="mode-radio-group">
                  <el-radio value="hybrid">
                    <span>智能混合</span>
                    <span class="mode-desc">规则规划 + AI执行</span>
                  </el-radio>
                  <el-radio value="rule_only">
                    <span>规则出题</span>
                    <span class="mode-desc">秒级生成，无需AI</span>
                  </el-radio>
                </el-radio-group>
              </div>
            </el-form-item>

            <!-- 题目数量 -->
            <el-form-item label="题目数量">
              <el-slider v-model="configForm.quantity" :min="1" :max="200" show-input />
            </el-form-item>

            <!-- 难度等级 -->
            <el-form-item label="难度等级" class="difficulty-form-item">
              <div class="difficulty-layout">
                <el-radio-group v-model="configForm.difficulty" class="difficulty-radio-group">
                  <el-radio value="easy">简单</el-radio>
                  <el-radio value="medium">中等</el-radio>
                  <el-radio value="hard">困难</el-radio>
                </el-radio-group>
                <div class="mixed-wrapper">
                  <el-radio value="mixed" v-model="configForm.difficulty" class="mixed-radio">
                    混合
                  </el-radio>
                  <transition name="slider-fade">
                    <div v-if="configForm.difficulty === 'mixed'" class="difficulty-rate">
                      <span>简单</span>
                      <el-slider v-model="configForm.difficultyRate" :step="10" show-stops :max="100" />
                      <span>困难</span>
                    </div>
                  </transition>
                </div>
              </div>
            </el-form-item>

            <!-- 知识点范围 -->
            <el-form-item v-if="configForm.categoryId" label="知识点范围">
              <div v-if="!configForm.examTypeId" class="knowledge-hint">
                请先选择考试科目
              </div>
              <div v-else-if="knowledgeTreeData.length === 0" class="knowledge-hint">
                暂无知识点
              </div>
              <el-tree
                v-else
                ref="knowledgeTreeRef"
                :data="knowledgeTreeData"
                :props="{ label: 'label', children: 'children' }"
                node-key="id"
                show-checkbox
                default-expand-all
                :loading="loadingKnowledge"
              />
            </el-form-item>

            <!-- 操作按钮 -->
            <div class="form-actions">
              <el-button type="primary" :loading="generating" @click="startGeneration" style="width: 100%">
                <el-icon v-if="!generating"><MagicStick /></el-icon>
                {{ generating ? '生成中...' : '开始生成' }}
              </el-button>
              <el-button @click="resetConfig">重置</el-button>
            </div>
          </el-form>
        </el-card>

        <!-- 展开按钮（面板折叠时显示） -->
        <div v-show="!configPanelVisible" class="expand-btn" @click="configPanelVisible = true">
          <el-icon><DArrowLeft /></el-icon>
          <span>展开配置</span>
        </div>
      </el-col>

      <!-- 右侧预览区 -->
      <el-col :xs="24" :lg="configPanelVisible ? 16 : 24" class="preview-col">
        <!-- 生成进度区 -->
        <div v-if="generating || generationStatus" class="progress-section">
          <el-card class="progress-card">
            <template #header>
              <div class="card-header">
                <span class="title">生成进度</span>
                <div class="progress-header-actions">
                  <el-tag :type="statusTagType">{{ statusText }}</el-tag>
                  <el-button v-if="generating" type="danger" size="small" @click="cancelGeneration">取消生成</el-button>
                </div>
              </div>
            </template>

            <div class="progress-content">
              <div class="progress-info">
                <div class="progress-item">
                  <span class="label">任务ID:</span>
                  <span class="value">{{ currentTaskId || '-' }}</span>
                </div>
                <div class="progress-item">
                  <span class="label">开始时间:</span>
                  <span class="value">{{ startTime || '-' }}</span>
                </div>
                <div class="progress-item">
                  <span class="label">预计剩余:</span>
                  <span class="value">{{ remainingTime || '-' }}</span>
                </div>
              </div>

              <el-progress
                :percentage="progressPercentage"
                :status="progressStatus"
                :stroke-width="12"
                striped
                striped-flow
              />

              <!-- 实时日志 -->
              <div class="log-container">
                <div class="log-header">
                  <span>生成日志</span>
                  <el-button size="small" link @click="clearLogs">清空</el-button>
                </div>
                <div class="log-content" ref="logContainerRef">
                  <div v-for="(log, index) in logs" :key="index" class="log-item" :class="log.type">
                    <span class="log-time">{{ log.time }}</span>
                    <span class="log-message">{{ log.message }}</span>
                  </div>
                  <div v-if="logs.length === 0" class="log-empty">等待生成...</div>
                </div>
              </div>
            </div>
          </el-card>
        </div>

        <!-- 生成结果预览 -->
        <el-card class="result-card">
          <template #header>
            <div class="card-header">
              <span class="title">生成结果预览</span>
              <div class="header-actions" v-if="generatedQuestions.length > 0">
                <el-checkbox v-model="selectAll">全选</el-checkbox>
                <el-button type="primary" size="small" @click="submitSelected">提交审核</el-button>
                <el-button size="small" @click="editSelected">编辑</el-button>
                <el-button type="danger" size="small" @click="deleteSelected">删除</el-button>
              </div>
            </div>

            <!-- 提交失败的题目 -->
            <div v-if="failedQuestions.length > 0" class="failed-questions-panel">
              <div class="failed-header">
                <span class="failed-title">
                  <el-icon color="#F53F3F"><WarningFilled /></el-icon>
                  提交失败 ({{ failedQuestions.length }})
                </span>
                <div class="failed-actions">
                  <el-button type="primary" size="small" @click="retryFailedQuestions">重试</el-button>
                  <el-button size="small" @click="clearFailedQuestions">清空</el-button>
                </div>
              </div>
              <div class="failed-list">
                <div v-for="(q, idx) in failedQuestions" :key="'failed-' + idx" class="failed-item">
                  <div class="failed-content">
                    <div class="failed-question">{{ q.content?.substring(0, 60) }}{{ q.content?.length > 60 ? '...' : '' }}</div>
                    <div class="failed-error">
                      <el-tag type="danger" size="small">{{ q._error }}</el-tag>
                      <span class="failed-time">{{ q._failedAt }}</span>
                    </div>
                  </div>
                  <el-button type="danger" size="small" text @click="removeFailedQuestion(idx)">移除</el-button>
                </div>
              </div>
            </div>
          </template>

          <!-- 空状态 -->
          <div v-if="generatedQuestions.length === 0 && !generating" class="empty-state">
            <div class="empty-illustration">
              <svg width="200" height="160" viewBox="0 0 200 160">
                <rect x="40" y="30" width="120" height="100" rx="8" fill="#EEF4FF" stroke="#165DFF" stroke-width="2"/>
                <rect x="55" y="50" width="90" height="8" rx="2" fill="#165DFF" opacity="0.3"/>
                <rect x="55" y="65" width="70" height="8" rx="2" fill="#165DFF" opacity="0.3"/>
                <rect x="55" y="80" width="80" height="8" rx="2" fill="#165DFF" opacity="0.3"/>
                <rect x="55" y="95" width="60" height="8" rx="2" fill="#165DFF" opacity="0.3"/>
                <circle cx="160" cy="40" r="25" fill="#00B42A" opacity="0.2"/>
                <text x="160" y="46" text-anchor="middle" fill="#00B42A" font-size="20">?</text>
              </svg>
            </div>
            <div class="empty-link">配置参数后点击"开始生成"<br/>AI将为您智能生成题目</div>
          </div>

          <!-- 骨架屏加载 -->
          <div v-else-if="generating" class="skeleton-list">
            <el-skeleton :rows="5" animated v-for="i in 4" :key="i" class="skeleton-item" />
          </div>

          <!-- 题目列表 -->
          <div v-else class="question-list">
            <div v-for="(question, index) in generatedQuestions" :key="question.id || index" class="question-item">
              <div class="question-header">
                <el-checkbox v-model="question.selected" @change="updateSelectedCount" />
                <span class="question-index">#{{ index + 1 }}</span>
                <el-tag size="small" :type="getTypeTagType(question.type)">{{ getTypeName(question.type) }}</el-tag>
                <el-tag size="small" :type="getDifficultyTagType(question.difficulty)">
                  {{ getDifficultyName(question.difficulty) }}
                </el-tag>
                <span class="question-actions">
                  <el-button type="primary" size="small" link @click="editQuestion(index)">编辑</el-button>
                  <el-button type="danger" size="small" link @click="deleteQuestion(index)">删除</el-button>
                </span>
              </div>
              <div class="question-content">{{ question.content }}</div>
              <div v-if="question.options" class="question-options">
                <div v-for="(opt, optIndex) in question.options" :key="optIndex" class="option-item">
                  <span class="option-label">{{ String.fromCharCode(65 + optIndex) }}.</span>
                  <span>{{ opt }}</span>
                  <el-icon v-if="question.answer && question.answer.includes(String.fromCharCode(65 + optIndex))" color="#00B42A">
                    <Check />
                  </el-icon>
                </div>
              </div>
              <div v-if="question.answer && question.type === 'short_answer'" class="question-answer">
                <span class="answer-label">参考答案:</span>
                <span>{{ question.answer }}</span>
              </div>
            </div>
          </div>
        </el-card>

        <!-- 历史任务记录 -->
        <el-card class="history-card">
          <template #header>
            <div class="card-header">
              <span class="title">历史任务记录</span>
              <div class="header-actions">
                <el-select v-model="historyFilter" placeholder="状态筛选" clearable style="width: 120px">
                  <el-option label="全部" value="" />
                  <el-option label="进行中" value="running" />
                  <el-option label="已完成" value="completed" />
                  <el-option label="已失败" value="failed" />
                </el-select>
              </div>
            </div>
          </template>

          <el-table :data="filteredHistoryTasks" stripe style="width: 100%">
            <el-table-column prop="id" label="任务ID" width="100" />
            <el-table-column prop="createdAt" label="创建时间" width="160" />
            <el-table-column prop="config" label="配置信息" show-overflow-tooltip>
              <template #default="{ row }">
                <span>{{ row.config.subject }} / {{ row.config.quantity }}题</span>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusTagType(row.status)">{{ getStatusText(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="progress" label="进度" width="120">
              <template #default="{ row }">
                <el-progress :percentage="row.progress" :status="getProgressStatus(row.status)" />
              </template>
            </el-table-column>
            <el-table-column prop="resultCount" label="生成数量" width="100" />
            <el-table-column label="操作" width="180">
              <template #default="{ row }">
                <el-button link size="small" @click="viewTaskResult(row)">查看</el-button>
                <el-button
                  v-if="row.status === 'completed' || row.status === 'failed'"
                  link
                  size="small"
                  @click="regenerateTask(row)"
                >
                  重新生成
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- 编辑对话框 -->
    <el-dialog v-model="editDialogVisible" title="编辑题目" width="700px">
      <el-form :model="editingQuestion" label-position="top">
        <el-form-item label="题目内容">
          <el-input v-model="editingQuestion.content" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="题目类型">
          <el-select v-model="editingQuestion.type" style="width: 100%">
            <el-option label="单选题" value="choice" />
            <el-option label="多选题" value="multiple" />
            <el-option label="判断题" value="judge" />
            <el-option label="简答题" value="short_answer" />
          </el-select>
        </el-form-item>
        <el-form-item label="难度">
          <el-select v-model="editingQuestion.difficulty" style="width: 100%">
            <el-option label="简单" value="easy" />
            <el-option label="中等" value="medium" />
            <el-option label="困难" value="hard" />
          </el-select>
        </el-form-item>
        <template v-if="editingQuestion.type === 'choice' || editingQuestion.type === 'multiple'">
          <el-form-item label="选项A">
            <el-input v-model="editingQuestion.optionA" />
          </el-form-item>
          <el-form-item label="选项B">
            <el-input v-model="editingQuestion.optionB" />
          </el-form-item>
          <el-form-item label="选项C">
            <el-input v-model="editingQuestion.optionC" />
          </el-form-item>
          <el-form-item label="选项D">
            <el-input v-model="editingQuestion.optionD" />
          </el-form-item>
          <el-form-item label="正确答案">
            <el-input v-model="editingQuestion.answer" placeholder="如: A 或 A,B" />
          </el-form-item>
        </template>
        <el-form-item v-else label="正确答案">
          <el-input v-model="editingQuestion.answer" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEditedQuestion">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { systemAPI, knowledgeAPI, adminAPI, aiAPI } from '@/api'
import { DArrowRight, MagicStick, DArrowLeft, Check } from '@element-plus/icons-vue'
import { useGeneration } from '@/composables/useGeneration'

// Local UI state (not part of generation logic)
const currentStep = ref(0)
const configPanelVisible = ref(true)
const knowledgeTreeRef = ref(null)
const editDialogVisible = ref(false)
const editingQuestion = reactive({
  content: '',
  type: 'choice',
  difficulty: 'medium',
  optionA: '',
  optionB: '',
  optionC: '',
  optionD: '',
  answer: ''
})
const editingQuestionIndex = ref(-1)

// Knowledge tree data
const knowledgeTreeData = ref([])
const loadingKnowledge = ref(false)

// Options
const categoryOptions = ref([])
const loadingCategories = ref(false)
const examTypeOptions = ref([])
const loadingExamTypes = ref(false)

const filteredExamTypeOptions = computed(() => {
  if (!configForm.categoryId) return examTypeOptions.value
  return examTypeOptions.value.filter(et => et.category_id === configForm.categoryId)
})

// Config form
const configForm = reactive({
  categoryId: null,
  examTypeId: null,
  questionTypes: ['choice', 'multiple'],
  generationMode: 'hybrid',
  quantity: 20,
  difficulty: 'mixed',
  difficultyRate: 50
})

// Type map: frontend label -> backend enum
const typeMap = {
  choice: 'single_choice',
  multiple: 'multiple_choice',
  judge: 'true_false',
  short_answer: 'essay'
}

// Use generation composable
const {
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
  statusText,
  statusTagType,
  filteredHistoryTasks: filteredTasks,
  addLog,
  clearLogs,
  startGeneration: startGen,
  cancelGeneration,
  submitSelected,
  retryFailedQuestions,
  deleteQuestion: deleteQuestionAction,
  deleteSelected: deleteSelectedAction,
  viewTaskResult,
  regenerateTask,
} = useGeneration({
  onQuestionsGenerated: () => {},
  onGenerationFailed: (error) => {
    console.error('Generation failed:', error)
  },
  onLog: () => {}
})

// Helper functions (used in template)
const mapDifficultyNum = (num) => {
  const map = { 1: 'easy', 2: 'easy', 3: 'medium', 4: 'hard', 5: 'hard' }
  return map[num] || 'medium'
}
const getTypeName = (type) => ({ choice: '单选', multiple: '多选', judge: '判断', short_answer: '简答' }[type] || type)
const getTypeTagType = (type) => ({ choice: '', multiple: 'success', judge: 'info', short_answer: 'warning' }[type] || 'info')
const getDifficultyName = (diff) => ({ easy: '简单', medium: '中等', hard: '困难' }[diff] || diff)
const getDifficultyTagType = (type) => ({ easy: 'success', medium: 'warning', hard: 'danger' }[type] || 'info')
const getStatusText = (status) => ({ pending: '等待', running: '进行中', completed: '完成', failed: '失败' }[status] || status)
const getStatusTagType = (status) => ({ pending: 'info', running: 'warning', completed: 'success', failed: 'danger' }[status] || 'info')
const getProgressStatus = (status) => {
  if (status === 'failed') return 'exception'
  if (status === 'completed') return 'success'
  return ''
}
const updateSelectedCount = () => {
  const selected = generatedQuestions.value.filter((q) => q.selected).length
  selectAll.value = selected === generatedQuestions.value.length
}

const selectAll = ref(false)
watch(selectAll, (val) => {
  generatedQuestions.value.forEach((q) => q.selected = val)
})

// Fetch categories
const fetchCategories = async () => {
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

// Fetch exam types
const fetchExamTypes = async () => {
  loadingExamTypes.value = true
  try {
    const res = await systemAPI.getExamTypes()
    examTypeOptions.value = res.data?.items || []
  } catch (e) {
    console.error('获取考试科目失败:', e)
  } finally {
    loadingExamTypes.value = false
  }
}

// Fetch knowledge tree
const fetchKnowledgeTree = async () => {
  if (!configForm.categoryId) {
    knowledgeTreeData.value = []
    return
  }
  loadingKnowledge.value = true
  try {
    const params = { category_id: configForm.categoryId }
    if (configForm.examTypeId) {
      params.exam_type_id = configForm.examTypeId
    }
    const res = await knowledgeAPI.getHierarchyTrees(params)
    const trees = res.data?.trees || []

    if (configForm.examTypeId) {
      for (const cat of trees) {
        const et = (cat.children || []).find((e) => e.exam_type_id === configForm.examTypeId)
        if (et) {
          knowledgeTreeData.value = [{
            id: et.id,
            label: et.name,
            node_type: et.node_type,
            exam_type_id: et.exam_type_id,
            children: convertKpTree(et.children || [])
          }]
          return
        }
      }
    }

    knowledgeTreeData.value = []
    for (const cat of trees) {
      for (const et of (cat.children || [])) {
        knowledgeTreeData.value.push({
          id: et.id,
          label: et.name,
          node_type: et.node_type,
          exam_type_id: et.exam_type_id,
          children: null
        })
      }
    }
  } catch (e) {
    console.error('加载知识点失败:', e)
    knowledgeTreeData.value = []
  } finally {
    loadingKnowledge.value = false
  }
}

// Convert API tree to el-tree format
const convertKpTree = (nodes) => {
  if (!nodes) return []
  return nodes.map(n => ({
    id: n.id,
    label: n.name,
    children: convertKpTree(n.children || [])
  }))
}

// Handle category change
const handleCategoryChange = () => {
  configForm.examTypeId = null
  fetchExamTypes()
  fetchKnowledgeTree()
}

// Listen for exam type changes
watch(() => configForm.examTypeId, () => {
  fetchKnowledgeTree()
})

// Start generation (wraps composable)
const startGeneration = async () => {
  await startGen(
    configForm,
    knowledgeTreeRef.value,
    knowledgeTreeRef.value?.getCheckedNodes() || [],
    examTypeOptions.value,
    categoryOptions.value,
  )
}

// Reset config
const resetConfig = () => {
  configForm.categoryId = categoryOptions.value.length > 0 ? categoryOptions.value[0].id : null
  configForm.examTypeId = null
  configForm.questionTypes = ['choice', 'multiple']
  configForm.quantity = 20
  configForm.difficulty = 'mixed'
  configForm.difficultyRate = 50
  ElMessage.success('配置已重置')
}

// Clear failed questions
const clearFailedQuestions = () => {
  failedQuestions.value = []
}

// Remove a failed question by index
const removeFailedQuestion = (index) => {
  failedQuestions.value.splice(index, 1)
}

// Edit selected question
const editSelected = () => {
  const selected = generatedQuestions.value.filter(q => q.selected)
  if (selected.length === 0) {
    ElMessage.warning('请先选择要编辑的题目')
    return
  }
  if (selected.length > 1) {
    ElMessage.warning('请只选择一道题目进行编辑')
    return
  }
  const index = generatedQuestions.value.findIndex(q => q.selected)
  editingQuestionIndex.value = index
  const question = generatedQuestions.value[index]
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
}

// Save edited question
const saveEditedQuestion = () => {
  const question = generatedQuestions.value[editingQuestionIndex.value]
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

// Delete a single question
const deleteQuestion = (index) => {
  ElMessageBox.confirm('确定要删除这道题目吗？', '提示', { type: 'warning' })
    .then(() => {
      generatedQuestions.value.splice(index, 1)
      ElMessage.success('题目已删除')
    })
    .catch(() => {})
}

// Delete selected questions
const deleteSelected = () => {
  const selected = generatedQuestions.value.filter(q => q.selected)
  if (selected.length === 0) {
    ElMessage.warning('请先选择要删除的题目')
    return
  }

  ElMessageBox.confirm(`确定要删除选中的${selected.length}道题目吗？`, '提示', { type: 'warning' })
    .then(() => {
      generatedQuestions.value = generatedQuestions.value.filter(q => !q.selected)
      ElMessage.success('题目已删除')
    })
    .catch(() => {})
}

// Initialize
onMounted(() => {
  currentStep.value = 0
  fetchCategories()
  // 考试科目等选择考试种类后再加载
})
</script>

<style scoped>
.ai-question-page {
  padding: 0;
}

/* 步骤指示器 */
.steps-indicator {
  background: #ffffff;
  padding: 20px 24px;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  margin-bottom: 20px;
}

.main-content {
  padding: 0 4px;
}

/* 配置面板 */
.config-col {
  transition: all 0.3s ease;
}

.config-card {
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.config-form {
  padding: 20px 0;
}

:deep(.config-form .el-form-item) {
  margin-bottom: 22px;
}

.question-types-group {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
}

.form-actions {
  display: flex;
  gap: 12px;
  margin-top: 24px;
}

.form-actions .el-button {
  flex: 1;
}

.mode-radio-wrapper {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mode-radio-group {
  display: flex;
  flex-direction: row;
  gap: 16px;
}

.mode-desc {
  display: inline;
  font-size: 12px;
  color: #6b7280;
  margin-left: 6px;
}

.difficulty-form-item {
  :deep(.el-form-item__content) {
    flex-direction: column;
    align-items: stretch;
  }
}

.difficulty-layout {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
}

.difficulty-radio-group {
  display: flex;
  gap: 16px;
}

.mixed-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
}

.mixed-radio {
  margin-right: 8px;
}

.difficulty-rate {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.difficulty-rate .el-slider {
  flex: 1;
}

.knowledge-hint {
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 8px;
  color: #6b7280;
  text-align: center;
  font-size: 14px;
}

.expand-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 12px;
  margin-top: 12px;
  background: #ffffff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  cursor: pointer;
  color: #165DFF;
  font-size: 14px;
  transition: all 0.2s ease;
}

.expand-btn:hover {
  background: #f5f9ff;
}

/* 预览区 */
.preview-col {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 进度区 */
.progress-section {
  animation: fadeIn 0.3s ease;
}

.progress-card {
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.progress-content {
  padding: 8px 0;
}

.progress-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 20px;
}

.progress-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.progress-item .label {
  color: #6b7280;
  font-size: 14px;
}

.progress-item .value {
  color: #1f2937;
  font-size: 14px;
  font-weight: 500;
}

.log-container {
  margin-top: 24px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
  font-size: 14px;
  font-weight: 500;
  color: #374151;
}

.log-content {
  max-height: 200px;
  overflow-y: auto;
  padding: 12px 16px;
  background: #1f2937;
}

.log-item {
  display: flex;
  gap: 8px;
  padding: 4px 0;
  font-size: 13px;
  line-height: 1.5;
}

.log-time {
  color: #6b7280;
  font-family: monospace;
  flex-shrink: 0;
}

.log-message {
  color: #e5e7eb;
}

.log-item.info .log-message {
  color: #e5e7eb;
}

.log-item.warning .log-message {
  color: #fbbf24;
}

.log-item.error .log-message {
  color: #f87171;
}

.log-item.success .log-message {
  color: #34d399;
}

.log-empty {
  text-align: center;
  color: #9ca3af;
  padding: 40px 0;
}

/* 结果卡片 */
.result-card {
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  margin-bottom: 20px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* 提交失败面板 */
.failed-questions-panel {
  background: #FFF7F7;
  border: 1px solid #FFCCC7;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 16px;
}

.failed-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.failed-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
  color: #F53F3F;
}

.failed-actions {
  display: flex;
  gap: 8px;
}

.failed-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 300px;
  overflow-y: auto;
}

.failed-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: white;
  padding: 8px 12px;
  border-radius: 4px;
  border: 1px solid #FFE4E4;
}

.failed-content {
  flex: 1;
  min-width: 0;
}

.failed-question {
  font-size: 13px;
  color: #333;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.failed-error {
  display: flex;
  align-items: center;
  gap: 8px;
}

.failed-time {
  font-size: 12px;
  color: #999;
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 40px 20px;
}

.empty-illustration {
  margin-bottom: 20px;
}

.empty-link {
  font-size: 14px;
  color: #6b7280;
  line-height: 1.6;
}

/* 骨架屏 */
.skeleton-list {
  padding: 0 4px;
}

.skeleton-item {
  margin-bottom: 20px;
}

/* 题目列表 */
.question-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.question-item {
  background: #f9fafb;
  border-radius: 8px;
  padding: 16px;
  border: 1px solid #e5e7eb;
  transition: all 0.2s ease;
}

.question-item:hover {
  border-color: #165DFF;
  box-shadow: 0 2px 8px rgba(22, 93, 255, 0.1);
}

.question-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.question-index {
  font-size: 12px;
  color: #9ca3af;
  font-weight: 500;
}

.question-actions {
  margin-left: auto;
  display: flex;
  gap: 4px;
}

.question-content {
  font-size: 14px;
  color: #1f2937;
  line-height: 1.6;
  margin-bottom: 12px;
}

.question-options {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  margin-bottom: 12px;
}

.option-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #374151;
  padding: 6px 10px;
  background: #ffffff;
  border-radius: 4px;
}

.option-label {
  font-weight: 500;
  color: #6b7280;
}

.question-answer {
  background: #ffffff;
  padding: 10px 12px;
  border-radius: 4px;
  font-size: 13px;
}

.answer-label {
  color: #00B42A;
  font-weight: 500;
  margin-right: 8px;
}

/* 历史任务 */
.history-card {
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header .title {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 响应式 */
@media (max-width: 992px) {
  .question-options {
    grid-template-columns: 1fr;
  }
}
</style>
