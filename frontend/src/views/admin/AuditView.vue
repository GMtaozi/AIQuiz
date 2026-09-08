<template>
  <div class="audit-view">
    <el-card>
      <template #header>
        <div class="card-header">
          <h3>试题审核</h3>
          <div class="header-actions">
            <el-button
              :type="reviewMode ? 'success' : 'default'"
              @click="toggleReviewMode"
            >
              <Icon icon="mdi:pencil" />
              {{ reviewMode ? '列表模式' : '逐题审核模式' }}
            </el-button>
            <el-button type="primary" @click="fetchQuestions">
              <Icon icon="mdi:refresh" />
              刷新
            </el-button>
          </div>
        </div>
      </template>

      <!-- 筛选工具栏 -->
      <div class="filter-toolbar">
        <div class="filter-row">
          <el-select v-model="filterForm.categoryId" placeholder="考试种类" clearable style="width: 150px" @change="handleCategoryChange">
            <el-option
              v-for="cat in categories"
              :key="cat.id"
              :label="cat.name"
              :value="cat.id"
            />
          </el-select>
          <el-select v-model="filterForm.examTypeId" placeholder="考试科目" clearable style="width: 160px" :disabled="!filterForm.categoryId">
            <el-option
              v-for="et in examTypes"
              :key="et.id"
              :label="et.name"
              :value="et.id"
            />
          </el-select>
          <el-select v-model="filterForm.questionType" placeholder="题型" clearable style="width: 130px">
            <el-option label="单选题" value="choice" />
            <el-option label="多选题" value="multiple" />
            <el-option label="简答题" value="short_answer" />
            <el-option label="判断题" value="true_false" />
          </el-select>
          <el-select v-model="filterForm.difficulty" placeholder="难度" clearable style="width: 110px">
            <el-option label="简单" value="easy" />
            <el-option label="中等" value="medium" />
            <el-option label="困难" value="hard" />
          </el-select>
          <el-select v-model="filterForm.status" placeholder="状态" clearable style="width: 120px">
            <el-option label="待审核" value="pending" />
            <el-option label="已通过" value="approved" />
            <el-option label="已驳回" value="rejected" />
          </el-select>
          <el-date-picker
            v-model="filterForm.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 260px"
            @change="handleDateRangeChange"
          />
          <el-input
            v-model="filterForm.keyword"
            placeholder="搜索题目内容"
            style="width: 220px"
            clearable
            @keyup.enter="handleSearch"
          >
            <template #prefix>
              <Icon icon="mdi:magnify" />
            </template>
          </el-input>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
          <el-button @click="resetFilter">重置</el-button>
        </div>
        <div class="filter-summary" v-if="pagination.total > 0">
          共找到 <span class="highlight">{{ pagination.total }}</span> 道题目
        </div>
      </div>

      <!-- 逐题审核模式 -->
      <div v-if="reviewMode && currentReviewQuestion" class="review-mode">
        <div class="review-card">
          <div class="review-header">
            <div class="review-info">
              <el-tag size="small" :type="getDifficultyType(currentReviewQuestion.difficulty)">
                {{ getDifficultyName(currentReviewQuestion.difficulty) }}
              </el-tag>
              <el-tag size="small" type="info">{{ getTypeName(currentReviewQuestion.type) }}</el-tag>
            </div>
            <div class="review-progress">
              {{ currentReviewIndex + 1 }} / {{ questions.length }}
            </div>
          </div>

          <div class="review-content">
            <div class="question-content">
              <h4>题目内容</h4>
              <p>{{ currentReviewQuestion.content }}</p>
            </div>

            <div class="question-options" v-if="currentReviewQuestion.optionA || currentReviewQuestion.optionB">
              <h4>选项</h4>
              <div v-if="currentReviewQuestion.optionA" class="option-item" :class="{ 'is-answer': currentReviewQuestion.answer && currentReviewQuestion.answer.includes('A') }">
                <span class="option-label">A.</span>
                <span>{{ currentReviewQuestion.optionA }}</span>
              </div>
              <div v-if="currentReviewQuestion.optionB" class="option-item" :class="{ 'is-answer': currentReviewQuestion.answer && currentReviewQuestion.answer.includes('B') }">
                <span class="option-label">B.</span>
                <span>{{ currentReviewQuestion.optionB }}</span>
              </div>
              <div v-if="currentReviewQuestion.optionC" class="option-item" :class="{ 'is-answer': currentReviewQuestion.answer && currentReviewQuestion.answer.includes('C') }">
                <span class="option-label">C.</span>
                <span>{{ currentReviewQuestion.optionC }}</span>
              </div>
              <div v-if="currentReviewQuestion.optionD" class="option-item" :class="{ 'is-answer': currentReviewQuestion.answer && currentReviewQuestion.answer.includes('D') }">
                <span class="option-label">D.</span>
                <span>{{ currentReviewQuestion.optionD }}</span>
              </div>
            </div>

            <div class="question-answer" v-if="currentReviewQuestion.answer">
              <h4>正确答案</h4>
              <p class="answer-text">{{ currentReviewQuestion.answer }}</p>
            </div>

            <div class="question-analysis" v-if="currentReviewQuestion.analysis">
              <h4>题目解析</h4>
              <p>{{ currentReviewQuestion.analysis }}</p>
            </div>
          </div>

          <div class="review-actions">
            <el-button type="success" size="large" @click="approveCurrentQuestion">
              <Icon icon="mdi:check" />
              通过
            </el-button>
            <el-button type="danger" size="large" @click="openRejectForCurrent">
              <Icon icon="mdi:close" />
              驳回
            </el-button>
            <el-button size="large" @click="skipToNext" :disabled="currentReviewIndex >= questions.length - 1">
              跳过
              <Icon icon="mdi:arrow-right" />
            </el-button>
          </div>

          <div class="review-nav">
            <el-button @click="previousQuestion" :disabled="currentReviewIndex === 0">
              <Icon icon="mdi:arrow-left" />
              上一题
            </el-button>
            <el-button @click="nextQuestion" :disabled="currentReviewIndex >= questions.length - 1">
              下一题
              <Icon icon="mdi:arrow-right" />
            </el-button>
          </div>
        </div>
      </div>

      <!-- 批量操作栏 -->
      <div class="batch-actions" v-if="!reviewMode && selectedQuestions.length > 0">
        <div class="selected-info">
          <Icon icon="mdi:check" />
          已选中 <span class="count">{{ selectedQuestions.length }}</span> 项
        </div>
        <div class="action-buttons">
          <el-button type="success" @click="batchApprove">
            <Icon icon="mdi:check" />
            批量通过
          </el-button>
          <el-button type="danger" @click="batchReject">
            <Icon icon="mdi:close" />
            批量驳回
          </el-button>
          <el-button @click="clearSelection">清空选择</el-button>
        </div>
      </div>

      <!-- 题目列表表格 (非逐题模式) -->
      <el-empty v-if="!reviewMode && !loading && questions.length === 0" description="暂无待审核题目" :image-size="80" />
      <el-table
        v-if="!reviewMode"
        ref="tableRef"
        :data="questions"
        stripe
        style="width: 100%; margin-top: 16px"
        v-loading="loading"
        @selection-change="handleSelectionChange"
        :row-class-name="tableRowClassName"
        @row-click="handleRowClick"
      >
        <el-table-column type="selection" width="50" />
        <el-table-column type="index" label="ID" width="70" :index="(index) => index + 1 + (pagination.page - 1) * pagination.pageSize" />
        <el-table-column prop="content" label="题目内容" min-width="280">
          <template #default="{ row }">
            <div class="content-preview" :title="row.content">
              {{ row.content.length > 80 ? row.content.substring(0, 80) + '...' : row.content }}
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="type" label="题型" width="90">
          <template #default="{ row }">
            <el-tag size="small">{{ getTypeName(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="difficulty" label="难度" width="80">
          <template #default="{ row }">
            <el-tag size="small" :type="getDifficultyType(row.difficulty)">
              {{ getDifficultyName(row.difficulty) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="getStatusType(row.status)">
              {{ getStatusName(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button type="primary" link size="small" @click.stop="viewDetail(row)">查看</el-button>
              <template v-if="row.status === 'pending'">
                <el-button type="success" link size="small" @click.stop="approveQuestion(row)">通过</el-button>
                <el-button type="danger" link size="small" @click.stop="openRejectDialog(row)">驳回</el-button>
              </template>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-if="!reviewMode"
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @size-change="handleSizeChange"
        @current-change="handlePageChange"
        style="margin-top: 20px; text-align: right"
      />
    </el-card>

    <!-- 题目详情抽屉 -->
    <el-drawer
      v-model="detailDrawerVisible"
      title="题目详情"
      size="500px"
      direction="rtl"
    >
      <div v-if="currentQuestion" class="question-detail">
        <div class="detail-header">
          <el-tag size="small" type="info">{{ getTypeName(currentQuestion.type) }}</el-tag>
          <el-tag size="small" :type="getDifficultyType(currentQuestion.difficulty)">
            {{ getDifficultyName(currentQuestion.difficulty) }}
          </el-tag>
        </div>

        <div class="detail-section">
          <h4>题目内容</h4>
          <p>{{ currentQuestion.content }}</p>
        </div>

        <div class="detail-section" v-if="currentQuestion.optionA">
          <h4>选项</h4>
          <div class="option-item">A. {{ currentQuestion.optionA }}</div>
          <div class="option-item">B. {{ currentQuestion.optionB }}</div>
          <div class="option-item" v-if="currentQuestion.optionC">C. {{ currentQuestion.optionC }}</div>
          <div class="option-item" v-if="currentQuestion.optionD">D. {{ currentQuestion.optionD }}</div>
        </div>

        <div class="detail-section">
          <h4>正确答案</h4>
          <p class="answer-text">{{ currentQuestion.answer }}</p>
        </div>

        <div class="detail-section" v-if="currentQuestion.analysis">
          <h4>解析</h4>
          <p>{{ currentQuestion.analysis }}</p>
        </div>

        <div class="detail-section" v-if="currentQuestion.status !== 'pending'">
          <h4>审核信息</h4>
          <p>状态：<el-tag size="small" :type="getStatusType(currentQuestion.status)">{{ getStatusName(currentQuestion.status) }}</el-tag></p>
          <p v-if="currentQuestion.rejectReason">驳回原因：{{ currentQuestion.rejectReason }}</p>
          <p v-if="currentQuestion.auditTime">审核时间：{{ currentQuestion.auditTime }}</p>
        </div>
      </div>
      <template #footer>
        <div v-if="currentQuestion && currentQuestion.status === 'pending'" class="detail-actions">
          <el-button type="success" @click="approveQuestion(currentQuestion)">通过</el-button>
          <el-button type="danger" @click="openRejectDialog(currentQuestion)">驳回</el-button>
        </div>
      </template>
    </el-drawer>

    <!-- 驳回对话框 -->
    <el-dialog v-model="rejectDialogVisible" title="驳回题目" width="400px">
      <div class="reject-form">
        <p>请选择或输入驳回原因：</p>
        <div class="preset-reasons">
          <el-tag
            v-for="reason in presetReasons"
            :key="reason"
            class="reason-tag"
            :class="{ 'is-selected': rejectForm.reason === reason }"
            @click="selectPresetReason(reason)"
          >
            {{ reason }}
          </el-tag>
        </div>
        <el-input
          v-model="rejectForm.reason"
          type="textarea"
          :rows="2"
          placeholder="或输入自定义原因..."
          style="margin-top: 12px"
        />
      </div>
      <template #footer>
        <el-button @click="rejectDialogVisible = false">取消</el-button>
        <el-button type="danger" @click="confirmReject">确认驳回</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { auditAPI, systemAPI } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, MagicStick } from '@element-plus/icons-vue'
import Icon from '@/components/common/Icon.vue'

const tableRef = ref(null)
const questions = ref([])
const selectedQuestions = ref([])
const loading = ref(false)
const detailDrawerVisible = ref(false)
const rejectDialogVisible = ref(false)
const currentQuestion = ref(null)
const currentRejectQuestion = ref(null)
const reviewMode = ref(false)
const currentReviewIndex = ref(0)

// 考试种类和科目
const categories = ref([])
const examTypes = ref([])

const filterForm = reactive({
  categoryId: '',
  examTypeId: '',
  questionType: '',
  difficulty: '',
  status: 'pending',
  dateRange: null,
  keyword: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const rejectForm = reactive({
  reason: ''
})

const presetReasons = [
  '题目内容存在错误',
  '答案不正确',
  '知识点标注有误',
  '题目难度与标注不符',
  '题目重复',
  '格式不规范',
  '涉及敏感内容'
];

// 题型映射：前端 -> 后端
const typeMapBackend = {
  choice: 'single_choice',
  multiple: 'multiple_choice',
  true_false: 'true_false',
  short_answer: 'essay'
}

// 难度映射：前端字符串 -> 后端数字
// 注意：AI生成题目时 difficulty=2 表示简单，difficulty=3 表示中等，difficulty=4/5 表示困难
const difficultyMapBackend = {
  easy: 2,
  medium: 3,
  hard: 4
}

const currentReviewQuestion = computed(() => {
  return questions.value[currentReviewIndex.value] || null
})

onMounted(async () => {
  await fetchCategories()
  fetchQuestions()
})

// 获取考试种类
const fetchCategories = async () => {
  try {
    const response = await systemAPI.getExamCategories()
    categories.value = response.data.items || []
  } catch (error) {
    console.error('获取考试种类失败:', error)
  }
}

// 考试种类变化时，获取对应的考试科目
const handleCategoryChange = async (categoryId) => {
  filterForm.examTypeId = '' // 重置科目选择
  examTypes.value = []
  if (categoryId) {
    try {
      const response = await systemAPI.getExamTypes({ category_id: categoryId })
      examTypes.value = response.data.items || []
    } catch (error) {
      console.error('获取考试科目失败:', error)
    }
  }
}

const handleDateRangeChange = (val) => {
  if (val && val.length === 2) {
    filterForm.startDate = val[0]
    filterForm.endDate = val[1]
  } else {
    filterForm.startDate = null
    filterForm.endDate = null
  }
}

const handleSearch = () => {
  pagination.page = 1
  currentReviewIndex.value = 0
  fetchQuestions()
}

const handleSizeChange = () => {
  pagination.page = 1
  fetchQuestions()
}

const handlePageChange = () => {
  currentReviewIndex.value = 0
  fetchQuestions()
}

const toggleReviewMode = () => {
  reviewMode.value = !reviewMode.value
  if (reviewMode.value) {
    currentReviewIndex.value = 0
  }
}

const fetchQuestions = async () => {
  loading.value = true
  try {
    // 过滤掉 undefined 和空字符串的参数
    const buildParams = () => {
      const p = {}
      p.page = pagination.page
      p.page_size = pagination.pageSize
      if (filterForm.examTypeId) p.exam_type_id = filterForm.examTypeId
      if (filterForm.questionType) p.question_type = typeMapBackend[filterForm.questionType] || filterForm.questionType
      if (filterForm.difficulty) p.difficulty = difficultyMapBackend[filterForm.difficulty]
      if (filterForm.status) p.status = filterForm.status
      if (filterForm.keyword) p.keyword = filterForm.keyword
      if (filterForm.startDate) p.start_date = filterForm.startDate
      if (filterForm.endDate) p.end_date = filterForm.endDate
      return p
    }
    const params = buildParams()
    const response = await auditAPI.getPendingQuestions(params)
    const data = response.data

    // 映射后端数据到前端格式
    questions.value = data.items.map(q => {
      // 将选项数组转换为 optionA, optionB, optionC, optionD
      const options = {}
      const optionLabels = ['A', 'B', 'C', 'D']
      if (q.options && q.options.length > 0) {
        q.options.forEach((opt, idx) => {
          options[`option${optionLabels[idx]}`] = opt.option_content || ''
        })
      }

      return {
        id: q.id,
        content: q.content,
        type: q.question_type === 'single_choice' ? 'choice' :
              q.question_type === 'multiple_choice' ? 'multiple' :
              q.question_type === 'true_false' ? 'true_false' :
              q.question_type === 'essay' ? 'short_answer' : 'choice',
        difficulty: q.difficulty === 1 || q.difficulty === 2 ? 'easy' :
                   q.difficulty === 3 ? 'medium' :
                   q.difficulty === 4 || q.difficulty === 5 ? 'hard' : 'medium',
        status: q.audit_status,
        answer: q.answer || '',
        analysis: q.explanation || '',
        optionA: options.optionA || '',
        optionB: options.optionB || '',
        optionC: options.optionC || '',
        optionD: options.optionD || '',
        createTime: q.created_at ? new Date(q.created_at).toLocaleString() : '',
        auditTime: q.audited_at ? new Date(q.audited_at).toLocaleString() : '',
        rejectReason: q.audit_reason || '',
        _raw: q
      }
    })
    pagination.total = data.total

    // 重置逐题审核的索引
    if (currentReviewIndex.value >= questions.value.length) {
      currentReviewIndex.value = 0
    }
  } catch (error) {
    console.error('获取题目列表失败:', error)
    ElMessage.error('获取题目列表失败')
  } finally {
    loading.value = false
  }
}

const getTypeName = (type) => {
  const map = { choice: '单选题', multiple: '多选题', short_answer: '简答题', true_false: '判断题' }
  return map[type] || type
}

const getDifficultyName = (difficulty) => {
  const map = { easy: '简单', medium: '中等', hard: '困难' }
  return map[difficulty] || difficulty
}

const getDifficultyType = (difficulty) => {
  const map = { easy: 'success', medium: 'warning', hard: 'danger' }
  return map[difficulty] || 'info'
}

const getStatusName = (status) => {
  const map = { pending: '待审核', approved: '已通过', rejected: '已驳回' }
  return map[status] || status
}

const getStatusType = (status) => {
  const map = { pending: 'warning', approved: 'success', rejected: 'danger' }
  return map[status] || 'info'
}

const handleSelectionChange = (selection) => {
  selectedQuestions.value = selection
}

const handleRowClick = (row) => {
  // 点击行打开详情
}

const tableRowClassName = ({ rowIndex }) => {
  return rowIndex % 2 === 0 ? 'even-row' : 'odd-row'
}

const resetFilter = () => {
  filterForm.categoryId = ''
  filterForm.examTypeId = ''
  examTypes.value = []
  filterForm.questionType = ''
  filterForm.difficulty = ''
  filterForm.status = 'pending'
  filterForm.dateRange = null
  filterForm.startDate = null
  filterForm.endDate = null
  filterForm.keyword = ''
  pagination.page = 1
  currentReviewIndex.value = 0
  fetchQuestions()
}

const viewDetail = (row) => {
  currentQuestion.value = { ...row }
  detailDrawerVisible.value = true
}

const closeDetailDrawer = () => {
  detailDrawerVisible.value = false
  currentQuestion.value = null
}

const approveQuestion = async (row) => {
  try {
    await ElMessageBox.confirm('确定要通过这道题目吗？', '确认', { type: 'info' })
    await auditAPI.approveQuestion(row.id)
    ElMessage.success('题目已通过')
    await fetchQuestions() // 刷新列表
  } catch (error) {
    if (error !== 'cancel') {
      console.error('审核操作失败:', error)
      ElMessage.error('操作失败')
    }
  }
}

const openRejectDialog = (row) => {
  currentRejectQuestion.value = row
  rejectForm.reason = ''
  rejectDialogVisible.value = true
}

const openRejectForCurrent = () => {
  if (currentReviewQuestion.value) {
    openRejectDialog(currentReviewQuestion.value)
  }
}

const selectPresetReason = (reason) => {
  rejectForm.reason = reason
}

const confirmReject = async () => {
  if (!rejectForm.reason) {
    ElMessage.warning('请填写驳回原因')
    return
  }
  try {
    if (currentRejectQuestion.value.id === 'batch') {
      const ids = selectedQuestions.value.map(q => q.id)
      await auditAPI.batchReject({ ids, reason: rejectForm.reason })
      ElMessage.success(`成功驳回 ${ids.length} 道题目`)
      clearSelection()
    } else {
      await auditAPI.rejectQuestion(currentRejectQuestion.value.id, { reason: rejectForm.reason })
      ElMessage.success('题目已驳回')
    }
    rejectDialogVisible.value = false
    await fetchQuestions() // 刷新列表
  } catch (error) {
    console.error('驳回操作失败:', error)
    ElMessage.error('操作失败')
  }
}

const batchApprove = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要通过选中的 ${selectedQuestions.value.length} 道题目吗？`,
      '确认',
      { type: 'info' }
    )
    const ids = selectedQuestions.value.map(q => Number(q.id))
    await auditAPI.batchApprove(ids)
    ElMessage.success(`成功通过 ${selectedQuestions.value.length} 道题目`)
    clearSelection()
    await fetchQuestions() // 刷新列表
  } catch (error) {
    if (error !== 'cancel') {
      console.error('批量通过失败:', error)
      ElMessage.error('操作失败')
    }
  }
}

const batchReject = async () => {
  if (selectedQuestions.value.length === 0) {
    ElMessage.warning('请先选择题目')
    return
  }
  openRejectDialog({ id: 'batch' })
}

const clearSelection = () => {
  tableRef.value?.clearSelection()
  selectedQuestions.value = []
}

// 逐题审核相关方法
const approveCurrentQuestion = async () => {
  if (!currentReviewQuestion.value) return
  await approveQuestion(currentReviewQuestion.value)
  await skipToNext()
}

const skipToNext = async () => {
  if (currentReviewIndex.value < questions.value.length - 1) {
    currentReviewIndex.value++
  } else if (pagination.page * pagination.pageSize < pagination.total) {
    // 还有更多数据，加载下一页
    pagination.page++
    await fetchQuestions()
    currentReviewIndex.value = 0
  } else {
    ElMessage.info('已经是最后一题了')
  }
}

const previousQuestion = () => {
  if (currentReviewIndex.value > 0) {
    currentReviewIndex.value--
  }
}

const nextQuestion = async () => {
  if (currentReviewIndex.value < questions.value.length - 1) {
    currentReviewIndex.value++
  } else {
    // 加载更多
    if (pagination.page * pagination.pageSize < pagination.total) {
      pagination.page++
      await fetchQuestions()
      currentReviewIndex.value = 0
    } else {
      ElMessage.info('已经没有更多题目了')
    }
  }
}
</script>

<style scoped>
.audit-view {
  width: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.filter-toolbar {
  margin-bottom: 16px;
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  align-items: center;
}

.filter-summary {
  margin-top: 12px;
  color: #666;
  font-size: 14px;
}

.filter-summary .highlight {
  color: #409eff;
  font-weight: bold;
}

.batch-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 16px;
}

.selected-info {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #409eff;
}

.selected-info .count {
  font-weight: bold;
  font-size: 16px;
}

.action-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: nowrap;
}

.action-buttons .el-button {
  padding: 8px 16px;
  font-size: 13px;
}

.content-preview {
  cursor: pointer;
}

.manual-tag {
  color: #909399;
  font-size: 12px;
}

.detail-header {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
}

.detail-section {
  margin-bottom: 20px;
}

.detail-section h4 {
  color: #666;
  font-size: 14px;
  margin-bottom: 8px;
}

.detail-section p {
  line-height: 1.8;
}

.option-item {
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 6px;
}

.reject-form p {
  margin-bottom: 12px;
  color: #666;
}

.preset-reasons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.reason-tag {
  cursor: pointer;
  transition: all 0.3s;
}

.reason-tag.is-selected {
  background: #f56c6c;
  color: #fff;
  border-color: #f56c6c;
}

.detail-actions {
  margin-top: 30px;
  display: flex;
  gap: 12px;
}

/* 逐题审核模式样式 */
.review-mode {
  padding: 20px 0;
}

.review-card {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.review-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid #ebeef5;
}

.review-info {
  display: flex;
  gap: 8px;
  align-items: center;
}

.review-progress {
  color: #909399;
  font-size: 14px;
}

.review-content {
  margin-bottom: 24px;
}

.review-content h4 {
  color: #303133;
  font-size: 16px;
  margin-bottom: 12px;
  font-weight: 600;
}

.review-content p {
  color: #606266;
  line-height: 1.8;
  font-size: 15px;
}

.question-content {
  margin-bottom: 24px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
}

.question-content p {
  font-size: 16px !important;
  color: #303133 !important;
}

.question-options {
  margin-bottom: 24px;
}

.question-options .option-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px 16px;
  background: #fff;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  margin-bottom: 8px;
}

.question-options .option-item.is-answer {
  background: #f0f9eb;
  border-color: #67c23a;
}

.option-label {
  font-weight: bold;
  color: #409eff;
  min-width: 20px;
}

.question-answer {
  margin-bottom: 24px;
  padding: 16px;
  background: #fff;
  border: 2px solid #67c23a;
  border-radius: 8px;
}

.answer-text {
  color: #67c23a !important;
  font-weight: bold;
  font-size: 16px !important;
}

.question-analysis {
  padding: 16px;
  background: #ecf5ff;
  border-radius: 8px;
}

.review-actions {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin-bottom: 20px;
}

.review-nav {
  display: flex;
  justify-content: center;
  gap: 24px;
}
</style>
