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
              <el-checkbox-group v-model="configForm.questionTypes">
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
                <link x="160" y="46" link-anchor="middle" fill="#00B42A" font-size="20">?</link>
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
          <el-input v-model="editingQuestion.content" type="linkarea" :rows="3" />
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
          <el-input v-model="editingQuestion.answer" type="linkarea" :rows="2" />
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

// 状态
const currentStep = ref(0)
const configPanelVisible = ref(true)
const generating = ref(false)
const generationStatus = ref('')
const currentTaskId = ref('')
const startTime = ref('')
const remainingTime = ref('')
const progressPercentage = ref(0)
const progressStatus = ref('')
const logs = ref([])
const logContainerRef = ref(null)
const knowledgeTreeRef = ref(null)
const selectAll = ref(false)
const editDialogVisible = ref(false)
const editingQuestionIndex = ref(-1)
const historyFilter = ref('')

// 生成任务控制
let progressInterval = null
let pollTimer = null
const isGeneratingCancelled = ref(false)
const timerHandles = { progressInterval: null, pollTimer: null }

// 配置表单
const configForm = reactive({
  categoryId: null,
  examTypeId: null,
  questionTypes: ['choice', 'multiple'],
  generationMode: 'hybrid',  // hybrid / rule_only
  quantity: 20,
  difficulty: 'mixed',
  difficultyRate: 50
})

// 题型映射：前端标签 → 后端枚举
const typeMap = {
  choice: 'single_choice',
  multiple: 'multiple_choice',
  judge: 'true_false',
  short_answer: 'essay'
}

// 考试种类选项
const categoryOptions = ref([])
const loadingCategories = ref(false)

// 考试科目选项
const examTypeOptions = ref([])
const loadingExamTypes = ref(false)

// 计算属性：按考试种类筛选考试科目
const filteredExamTypeOptions = computed(() => {
  if (!configForm.categoryId) return examTypeOptions.value
  return examTypeOptions.value.filter(et => et.category_id === configForm.categoryId)
})

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

const handleCategoryChange = () => {
  configForm.examTypeId = null
  fetchExamTypes()  // 加载考试科目列表
  fetchKnowledgeTree()  // 加载知识点树（显示科目列表）
}

// 知识点树数据
const knowledgeTreeData = ref([])
const loadingKnowledge = ref(false)

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

    // 如果选择了考试科目，直接显示该科目下的知识点
    if (configForm.examTypeId) {
      for (const cat of trees) {
        const et = (cat.children || []).find(e => e.exam_type_id === configForm.examTypeId)
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

    // 没有选择考试科目时，只显示考试科目列表（不显示知识点）
    knowledgeTreeData.value = []
    for (const cat of trees) {
      for (const et of (cat.children || [])) {
        knowledgeTreeData.value.push({
          id: et.id,
          label: et.name,
          node_type: et.node_type,
          exam_type_id: et.exam_type_id,
          children: null  // 不加载知识点，等待用户选择科目
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

// 将知识点 API 数据转为 el-tree 格式
const convertKpTree = (nodes) => {
  if (!nodes) return []
  return nodes.map(n => ({
    id: n.id,
    label: n.name,
    children: convertKpTree(n.children || [])
  }))
}

// 监听科目变化，刷新知识点
watch(() => configForm.examTypeId, () => {
  fetchKnowledgeTree()
})

// 生成的题目
const generatedQuestions = ref([])

// 提交失败的题目（暂存）
const failedQuestions = ref([])

// 编辑中的题目
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

// 历史任务
const historyTasks = ref([])

// 计算属性
const filteredHistoryTasks = computed(() => {
  if (!historyFilter.value) return historyTasks.value
  return historyTasks.value.filter(task => task.status === historyFilter.value)
})

const statusText = computed(() => {
  const map = { pending: '等待中', running: '生成中', completed: '已完成', failed: '已失败' }
  return map[generationStatus.value] || '等待中'
})

const statusTagType = computed(() => {
  const map = { pending: 'info', running: 'warning', completed: 'success', failed: 'danger' }
  return map[generationStatus.value] || 'info'
})

// 方法
const getTypeName = (type) => {
  const map = { choice: '单选', multiple: '多选', judge: '判断', short_answer: '简答' }
  return map[type] || type
}

const getTypeTagType = (type) => {
  const map = { choice: '', multiple: 'success', judge: 'info', short_answer: 'warning' }
  return map[type] || 'info'
}

const getDifficultyName = (difficulty) => {
  const map = { easy: '简单', medium: '中等', hard: '困难' }
  return map[difficulty] || difficulty
}

const getDifficultyTagType = (difficulty) => {
  const map = { easy: 'success', medium: 'warning', hard: 'danger' }
  return map[difficulty] || 'info'
}

const getStatusText = (status) => {
  const map = { pending: '等待', running: '进行中', completed: '完成', failed: '失败' }
  return map[status] || status
}

const getStatusTagType = (status) => {
  const map = { pending: 'info', running: 'warning', completed: 'success', failed: 'danger' }
  return map[status] || 'info'
}

const getProgressStatus = (status) => {
  if (status === 'failed') return 'exception'
  if (status === 'completed') return 'success'
  return ''
}

const updateSelectedCount = () => {
  const selected = generatedQuestions.value.filter(q => q.selected).length
  selectAll.value = selected === generatedQuestions.value.length
}

const addLog = (message, type = 'info') => {
  const now = new Date()
  const time = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`
  logs.value.push({ time, message, type })

  nextTick(() => {
    if (logContainerRef.value) {
      logContainerRef.value.scrollTop = logContainerRef.value.scrollHeight
    }
  })
}

const clearLogs = () => {
  logs.value = []
}

const resetConfig = () => {
  configForm.categoryId = categoryOptions.value.length > 0 ? categoryOptions.value[0].id : null
  configForm.examTypeId = null
  configForm.questionTypes = ['choice', 'multiple']
  configForm.quantity = 20
  configForm.difficulty = 'mixed'
  configForm.difficultyRate = 50
  ElMessage.success('配置已重置')
}

const startGeneration = async () => {
  if (!configForm.categoryId) {
    ElMessage.warning('请选择考试种类')
    return
  }
  if (!configForm.examTypeId) {
    ElMessage.warning('请选择考试科目')
    return
  }
  if (configForm.questionTypes.length === 0) {
    ElMessage.warning('请至少选择一种题型')
    return
  }

  // 获取选中的知识点
  const selectedKpNodes = knowledgeTreeRef.value?.getCheckedNodes() || []
  if (selectedKpNodes.length === 0) {
    ElMessage.warning('请至少选择一个知识点')
    return
  }

  generating.value = true
  generationStatus.value = 'running'
  currentStep.value = 1
  progressPercentage.value = 0
  progressStatus.value = ''
  generatedQuestions.value = []
  clearLogs()
  // 重置取消状态
  isGeneratingCancelled.value = false
  // 清理可能存在的旧定时器
  if (timerHandles.progressInterval) {
    clearInterval(timerHandles.progressInterval)
    timerHandles.progressInterval = null
  }
  if (timerHandles.pollTimer) {
    clearInterval(timerHandles.pollTimer)
    timerHandles.pollTimer = null
  }

  const now = new Date()
  currentTaskId.value = `TASK-${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}-${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}`
  startTime.value = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`
  remainingTime.value = '计算中...'

  addLog('任务已创建，正在准备知识点内容...', 'info')

  // 收集选中的知识点ID（包含半选的父节点 + 全选的所有节点）
  // getCheckedNodes(false, false) 返回所有勾选节点（含非叶子）
  // 注意：category/exam_type 节点的 id 是字符串（如 "cat_SIFAJIANDU"），需要过滤掉
  const selectedKpIds = selectedKpNodes.map(n => n.id).filter(id => typeof id === 'number')

  // 如果没有数字ID，尝试从半选节点获取子节点ID
  if (selectedKpIds.length === 0) {
    const halfCheckedNodes = knowledgeTreeRef.value?.getHalfCheckedNodes() || []
    // 从半选的父节点中收集子节点ID
    const collectChildIds = (nodes) => {
      for (const n of nodes) {
        if (typeof n.id === 'number') selectedKpIds.push(n.id)
        if (n.children) collectChildIds(n.children)
      }
    }
    collectChildIds(halfCheckedNodes)
  }

  if (selectedKpIds.length === 0) {
    generating.value = false
    generationStatus.value = ''
    ElMessage.error('未找到有效的知识点ID，请确保知识点数据已正确加载')
    addLog('错误：选中的节点中没有有效的数字ID，请检查知识点树数据', 'error')
    return
  }

  // 不再前端拼接 knowledge_content，由后端根据 knowledge_point_ids 从数据库查询完整描述
  // 这样能获取到知识点的 description 等详细信息，AI 出题质量更高
  const knowledgeContent = ''

  addLog(`已选择 ${selectedKpIds.length} 个知识点，后端将查询知识点详情用于出题...`, 'info')

  // 获取当前科目和种类名称
  const currentCategory = categoryOptions.value.find(c => c.id === configForm.categoryId)
  const currentExamType = examTypeOptions.value.find(e => e.id === configForm.examTypeId)
  const subjectName = currentExamType?.name || currentCategory?.name || '通用'

  // 难度映射: easy=2, medium=3, hard=4, mixed=3 (后按比例分配)
  const difficultyMap = { easy: 2, medium: 3, hard: 4, mixed: 3 }
  const baseDifficulty = difficultyMap[configForm.difficulty] || 3

  try {
    // 进度模拟（在等待响应期间）
    // rule_only 模式秒级返回，不需要慢速模拟
    const isRuleOnly = configForm.generationMode === 'rule_only'
    let progress = isRuleOnly ? 60 : 0
    let elapsedSeconds = 0
    let progressUpdated = false  // 标记是否已收到后端进度
    timerHandles.progressInterval = setInterval(() => {
      // 检查是否已取消
      if (isGeneratingCancelled.value) {
        clearInterval(timerHandles.progressInterval)
        return
      }
      // 一旦收到后端进度，就不再使用前端模拟进度
      if (!progressUpdated) {
        if (isRuleOnly) {
          // 规则出题快速进度
          progress = Math.min(progress + 10, 95)
        } else {
          progress += Math.random() * 3
          if (progress > 95) progress = 95
        }
        progressPercentage.value = Math.round(progress)
      }
      elapsedSeconds++
      // 显示已运行时间
      remainingTime.value = `已运行 ${elapsedSeconds} 秒`
      // 超时提示
      if (!isRuleOnly) {
        if (elapsedSeconds === 30) {
          addLog('AI正在思考中，请耐心等待...', 'info')
        } else if (elapsedSeconds === 60) {
          addLog('AI响应较慢，可能因为知识点较多，继续等待...', 'warning')
        } else if (elapsedSeconds === 120) {
          addLog('等待时间较长，AI可能遇到网络问题，建议稍后重试', 'warning')
        } else if (elapsedSeconds > 180 && elapsedSeconds % 60 === 0) {
          addLog(`已等待 ${Math.floor(elapsedSeconds / 60)} 分钟，仍未收到响应`, 'warning')
        }
      }
    }, isRuleOnly ? 200 : 1000)

    const allQuestions = []
    const mode = configForm.generationMode

    // ── 混合出题模式：异步调用 + 轮询进度 ──
    if (mode === 'hybrid' || mode === 'rule_only') {
      const modeNames = { hybrid: '智能混合', rule_only: '规则出题' }
      addLog(`使用${modeNames[mode]}模式生成题目...`, 'info')

      // 混合出题支持多题型，前端勾选的题型转换为后端格式
      const questionTypeList = configForm.questionTypes.map(t => typeMap[t] || 'single_choice')

      // 从选中的知识点节点中获取 exam_type_id，优先使用它
      // 注意：examTypeId 是考试科目ID，对应的 subject_id 才是题库系统使用的科目ID
      const currentExamType = examTypeOptions.value.find(e => e.id === configForm.examTypeId)
      let effectiveSubjectId = currentExamType?.subject_id || 1
      const firstNodeWithExamType = selectedKpNodes.find(n => n.exam_type_id)
      if (firstNodeWithExamType && firstNodeWithExamType.exam_type_id) {
        // 知识点可能关联了不同的考试科目，需要获取对应的 subject_id
        const kpExamType = examTypeOptions.value.find(e => e.id === firstNodeWithExamType.exam_type_id)
        if (kpExamType?.subject_id) {
          effectiveSubjectId = kpExamType.subject_id
        }
      }

      const reqBody = {
        subject_id: effectiveSubjectId,
        subject_name: subjectName || '通用',
        chapter_ids: [],
        chapter_names: [],
        question_types: questionTypeList,
        difficulty: Number(baseDifficulty),
        count: Math.max(1, Number(configForm.quantity)),
        knowledge_point_ids: selectedKpIds.map(id => Number(id)).filter(id => !isNaN(id)),
        mode: mode,
      }

      addLog(`请求参数：${questionTypeList.join('/')} × ${configForm.quantity}题，知识点ID ${reqBody.knowledge_point_ids.length} 个`, 'info')
      console.log('[AI出题] 请求体:', JSON.stringify(reqBody, null, 2))

      if (reqBody.knowledge_point_ids.length === 0) {
        addLog('错误：知识点ID列表为空，请重新选择知识点', 'error')
        clearInterval(timerHandles.progressInterval)
        generating.value = false
        generationStatus.value = 'failed'
        progressPercentage.value = 0
        progressStatus.value = 'exception'
        remainingTime.value = '失败'
        ElMessage.error('知识点ID为空，请确保知识点树数据正确加载后重试')
        return
      }

      if (mode === 'hybrid') {
        addLog('规则引擎正在分析知识点类型并制定出题策略...', 'info')
      } else if (mode === 'rule_only') {
        addLog('规则引擎正在快速生成题目...', 'info')
      }

      try {
        // 1. 创建异步任务
        const asyncRes = await adminAPI.hybridGenerateAsync(reqBody)
        const taskId = asyncRes.data?.task_id
        if (!taskId) {
          throw new Error('创建出题任务失败：未返回任务ID')
        }
        addLog(`出题任务已创建 (ID: ${taskId})，正在后台执行...`, 'info')
        currentTaskId.value = `TASK-${taskId}`

        // 2. 轮询任务进度
        // rule_only 模式轮询间隔更短（预期秒级完成）
        const pollInterval = isRuleOnly ? 500 : 2000
        let pollCount = 0
        const maxPolls = 180 // 最多轮询180次（rule_only: 90秒, AI: 360秒）

        const pollTask = async () => {
          return new Promise((resolve, reject) => {
            timerHandles.pollTimer = setInterval(async () => {
              // 检查是否已取消
              if (isGeneratingCancelled.value) {
                clearInterval(timerHandles.pollTimer)
                clearInterval(timerHandles.progressInterval)
                reject(new Error('用户取消'))
                return
              }
              pollCount++
              try {
                const progressRes = await adminAPI.getTaskProgress(taskId)
                const taskData = progressRes.data

                // 更新进度条（使用后端真实进度）
                progressUpdated = true  // 标记已收到后端进度，不再使用模拟值
                progressPercentage.value = taskData.progress
                // 继续显示已运行时间，不受后端进度波动影响

                if (taskData.status === 'completed') {
                  clearInterval(timerHandles.pollTimer)
                  clearInterval(timerHandles.progressInterval)
                  progressPercentage.value = 100  // 确保进度到100%
                  try {
                    const questions = taskData.questions || []
                    addLog(`出题完成：规则 ${taskData.rule_questions} 题 + AI ${taskData.ai_questions} 题 = ${questions.length} 题`,
                           questions.length < configForm.quantity ? 'warning' : 'success')

                    // 转换题目格式
                    for (let idx = 0; idx < questions.length; idx++) {
                      const q = questions[idx]
                      try {
                        const frontType = Object.keys(typeMap).find(k => typeMap[k] === q.question_type) || 'choice'
                        allQuestions.push({
                          id: `Q-${Date.now()}-${idx}`,
                          type: frontType,
                          difficulty: mapDifficultyNum(q.difficulty),
                          content: q.content || '',
                          selected: false,
                          options: q.options ? q.options.map(o => (typeof o === 'string' ? o : (o.option_content || o.option_label || ''))) : null,
                          answer: q.answer || '',
                          explanation: q.explanation || '',
                          knowledgePoints: selectedKpNodes.map(n => n.label),
                          _raw: q,
                          _questionType: q.question_type || typeMap[frontType],
                          _difficultyNum: q.difficulty || baseDifficulty,
                          _knowledgePointIds: selectedKpIds,
                        })
                      } catch (convertErr) {
                        console.error(`题目 ${idx + 1} 格式转换失败:`, convertErr, q)
                        addLog(`题目 ${idx + 1} 格式转换失败，已跳过`, 'warning')
                      }
                    }
                  } catch (processErr) {
                    console.error('[AI出题] 处理完成结果失败:', processErr)
                  }
                  // 无论处理是否出错，都 resolve 让流程继续
                  resolve()
                } else if (taskData.status === 'failed') {
                  clearInterval(timerHandles.pollTimer)
                  clearInterval(timerHandles.progressInterval)
                  addLog(`出题失败: ${taskData.error_message || '未知错误'}`, 'error')
                  reject(new Error(taskData.error_message || '出题失败'))
                } else if (pollCount >= maxPolls) {
                  clearInterval(timerHandles.pollTimer)
                  clearInterval(timerHandles.progressInterval)
                  addLog('轮询超时，任务可能仍在后台执行', 'warning')
                  reject(new Error('轮询超时'))
                }
                // running/pending: 继续轮询
              } catch (pollErr) {
                console.error('[AI出题] 轮询失败:', pollErr)
                // 轮询失败不立即放弃，继续尝试
                if (pollCount >= maxPolls) {
                  clearInterval(timerHandles.pollTimer)
                  clearInterval(timerHandles.progressInterval)
                  reject(pollErr)
                }
              }
            }, pollInterval)
          })
        }

        await pollTask()
      } catch (apiErr) {
        console.error('[AI出题] API调用失败:', apiErr)
        clearInterval(timerHandles.progressInterval)
        const errMsg = apiErr.message || '未知错误'
        addLog(`出题失败: ${errMsg}`, 'error')
      }
    }

    clearInterval(timerHandles.progressInterval)

    if (allQuestions.length > 0) {
      progressPercentage.value = 100
      progressStatus.value = 'success'
      generationStatus.value = 'completed'
      currentStep.value = 2
      remainingTime.value = '已完成'
      generatedQuestions.value = allQuestions
      const actualCount = allQuestions.length
      const targetCount = configForm.quantity
      if (actualCount < targetCount) {
        addLog(`题目生成完成！共 ${actualCount} 题（目标 ${targetCount} 题，缺少 ${targetCount - actualCount} 题）`, 'warning')
      } else {
        addLog(`所有题目生成完成！共 ${actualCount} 题`, 'success')
      }

      // 加入历史记录
      historyTasks.value.unshift({
        id: currentTaskId.value,
        createdAt: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`,
        config: { subject: subjectName, quantity: allQuestions.length },
        status: 'completed',
        progress: 100,
        resultCount: allQuestions.length
      })
    } else {
      progressPercentage.value = 0
      progressStatus.value = 'exception'
      generationStatus.value = 'failed'
      addLog('AI生成失败，请检查网络或配置后重试', 'error')
    }
  } catch (e) {
    progressPercentage.value = 0
    progressStatus.value = 'exception'
    generationStatus.value = 'failed'
    const errMsg = e.response?.data?.detail
      ? (Array.isArray(e.response.data.detail)
          ? e.response.data.detail.map(d => `${d.loc?.join('.')}: ${d.msg}`).join('; ')
          : String(e.response.data.detail))
      : e.message || '未知错误'
    addLog(`生成出错: ${errMsg}`, 'error')
    console.error('AI出题失败:', e)
  } finally {
    generating.value = false
  }
}

// 取消生成
const cancelGeneration = () => {
  isGeneratingCancelled.value = true
  if (timerHandles.progressInterval) {
    clearInterval(timerHandles.progressInterval)
    timerHandles.progressInterval = null
  }
  if (timerHandles.pollTimer) {
    clearInterval(timerHandles.pollTimer)
    timerHandles.pollTimer = null
  }
  // 直接关闭进度区
  generating.value = false
  generationStatus.value = ''
  progressPercentage.value = 0
  progressStatus.value = ''
  remainingTime.value = ''
  addLog('已取消生成', 'warning')
}

// 难度数字→前端标签映射
const mapDifficultyNum = (num) => {
  const map = { 1: 'easy', 2: 'easy', 3: 'medium', 4: 'hard', 5: 'hard' }
  return map[num] || 'medium'
}

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
      // 构建选项数据
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

      const payload = {
        chapter_id: 1,  // 默认章节，AI生成题目无固定章节
        subject_id: q._raw?.subject_id || 1,
        question_type: q._questionType || typeMap[q.type] || 'single_choice',
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
        options: options,
      }

      await adminAPI.createQuestion(payload)
      successCount++
    } catch (e) {
      console.error('提交题目失败:', e)
      // 保存失败的题目，带上错误信息
      failedQuestions.value.push({
        ...q,
        _error: e.message || '提交失败',
        _failedAt: new Date().toLocaleString()
      })
      failCount++
    }
  }

  loading.close()

  if (successCount > 0) {
    ElMessage.success(`已提交 ${successCount} 道题目到审核队列${failCount > 0 ? `，${failCount} 道提交失败（已暂存）` : ''}`)
    // 从列表中移除已提交的题目
    generatedQuestions.value = generatedQuestions.value.filter(q => !q.selected)
  } else {
    ElMessage.error('提交失败，请修复问题后重试暂存的题目')
  }
}

// 重试提交失败的题目
const retryFailedQuestions = async () => {
  if (failedQuestions.value.length === 0) {
    ElMessage.warning('没有待重试的题目')
    return
  }

  const loading = ElMessage({ message: '正在重试提交...', type: 'info', duration: 0 })
  let successCount = 0
  const stillFailed = []

  for (const q of failedQuestions.value) {
    try {
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

      const payload = {
        chapter_id: 1,
        subject_id: q._raw?.subject_id || 1,
        question_type: q._questionType || typeMap[q.type] || 'single_choice',
        content: q.content,
        answer: q.answer,
        explanation: q.explanation,
        difficulty: q._difficultyNum || 3,
        score: q.type === 'short_answer' ? 10 : 5,
        is_public: false,
        tags: { knowledge_points: q.knowledgePoints || [], source: 'ai_generated' },
        meta: { knowledge_point_ids: q._knowledgePointIds || [] },
        status: 1,
        options: options,
      }

      await adminAPI.createQuestion(payload)
      successCount++
    } catch (e) {
      console.error('重试提交题目失败:', e)
      stillFailed.push({
        ...q,
        _error: e.message || '提交失败',
        _failedAt: new Date().toLocaleString()
      })
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

// 移除失败的题目
const removeFailedQuestion = (index) => {
  failedQuestions.value.splice(index, 1)
}

// 清空所有失败题目
const clearFailedQuestions = () => {
  failedQuestions.value = []
}

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
  editQuestion(index)
}

const editQuestion = (index) => {
  const question = generatedQuestions.value[index]
  editingQuestionIndex.value = index
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

const deleteQuestion = (index) => {
  ElMessageBox.confirm('确定要删除这道题目吗？', '提示', { type: 'warning' })
    .then(() => {
      generatedQuestions.value.splice(index, 1)
      ElMessage.success('题目已删除')
    })
    .catch(() => {})
}

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

const viewTaskResult = (task) => {
  ElMessage.info(`查看任务 ${task.id} 的结果`)
}

const regenerateTask = (task) => {
  ElMessageBox.confirm(`确定要重新生成任务 ${task.id} 吗？`, '提示', { type: 'info' })
    .then(() => {
      task.status = 'running'
      task.progress = 0
      generationStatus.value = 'running'
      generating.value = true
      currentStep.value = 1
      addLog(`重新生成任务 ${task.id}...`, 'info')

      setTimeout(() => {
        task.status = 'completed'
        task.progress = 100
        generationStatus.value = 'completed'
        generating.value = false
        currentStep.value = 2
        addLog('重新生成完成！', 'success')
      }, 3000)
    })
    .catch(() => {})
}

watch(selectAll, (val) => {
  generatedQuestions.value.forEach(q => q.selected = val)
})

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

.steps-indicator :deep(.el-step__title) {
  font-size: 14px;
}

.steps-indicator :deep(.el-step__description) {
  font-size: 12px;
}

/* 主内容区 */
.main-content {
  min-height: calc(100vh - 200px);
}

/* 配置卡片 */
.config-card {
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  position: sticky;
  top: 20px;
}

.config-col {
  transition: all 0.3s ease;
}

.expand-btn {
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  padding: 40px 20px;
  link-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
  margin-bottom: 16px;
}

.expand-btn:hover {
  background: #f9fafb;
}

.expand-btn span {
  display: block;
  margin-top: 8px;
  font-size: 14px;
  color: #6b7280;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.progress-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.title {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

/* 配置表单 */
.config-form {
  padding: 0 4px;
}

.config-form :deep(.el-form-item__label) {
  font-weight: 500;
  color: #374151;
}

.required-mark {
  color: #F53F3F;
  margin-right: 2px;
}

.knowledge-hint {
  color: #F53F3F;
  font-size: 13px;
  link-align: center;
  padding: 8px;
  border: 1px dashed #f56c6c;
  border-radius: 4px;
  background: #fff1f0;
}

/* 出题模式 */
.mode-radio-wrapper {
  width: 100%;
}

.mode-radio-group {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  gap: 8px;
}

.mode-radio-group :deep(.el-radio) {
  display: flex;
  align-items: center;
  height: auto;
  padding: 8px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  transition: all 0.2s;
  margin-right: 0;
}

.mode-radio-group :deep(.el-radio.is-checked) {
  border-color: #165DFF;
  background: #f0f5ff;
}

.mode-desc {
  font-size: 11px;
  color: #9ca3af;
  margin-left: 4px;
}

/* 难度等级 */
.difficulty-form-item {
  position: relative;
}

.difficulty-layout {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  flex-wrap: wrap;
}

.difficulty-radio-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.difficulty-radio-group :deep(.el-radio) {
  margin-right: 0;
  padding: 6px 12px;
}

.mixed-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
}

.mixed-radio {
  margin-right: 0;
}

.difficulty-rate {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: #6b7280;
  padding: 6px 12px;
  background: #f9fafb;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}

.difficulty-rate :deep(.el-slider) {
  flex: 1;
  min-width: 120px;
  max-width: 160px;
}

/* 过渡动画 */
.slider-fade-enter-active,
.slider-fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.slider-fade-enter-from,
.slider-fade-leave-to {
  opacity: 0;
  transform: translateX(-10px);
}

.form-actions {
  display: flex;
  gap: 10px;
  margin-top: 20px;
}

.form-actions :deep(.el-button) {
  flex: 1;
}

/* 进度区 */
.progress-section {
  margin-bottom: 20px;
}

.progress-card {
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.progress-content {
  padding: 0 4px;
}

.progress-info {
  display: flex;
  gap: 24px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.progress-item {
  display: flex;
  gap: 8px;
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

/* 日志容器 */
.log-container {
  margin-top: 20px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
  font-size: 13px;
  font-weight: 500;
  color: #374151;
}

.log-content {
  height: 160px;
  overflow-y: auto;
  padding: 12px;
  background: #fefefe;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 12px;
}

.log-item {
  display: flex;
  gap: 10px;
  padding: 4px 0;
  color: #374151;
}

.log-item.success {
  color: #00B42A;
}

.log-item.warning {
  color: #FF7D00;
}

.log-item.error {
  color: #F53F3F;
}

.log-time {
  color: #9ca3af;
  flex-shrink: 0;
}

.log-message {
  flex: 1;
}

.log-empty {
  link-align: center;
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
  link-align: center;
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

/* 历史记录卡片 */
.history-card {
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

/* 响应式 */
@media (max-width: 768px) {
  .steps-indicator {
    padding: 16px;
  }

  .steps-indicator :deep(.el-step__title) {
    font-size: 12px;
  }

  .steps-indicator :deep(.el-step__description) {
    display: none;
  }

  .config-card {
    position: static;
  }

  .progress-info {
    flex-direction: column;
    gap: 10px;
  }

  .question-options {
    grid-template-columns: 1fr;
  }

  .header-actions {
    flex-wrap: wrap;
  }
}
</style>
