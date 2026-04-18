<template>
  <div class="paper-management-view">
    <!-- 顶部操作栏 -->
    <div class="operation-bar">
      <div class="left-operations">
        <el-select v-model="filterForm.categoryId" placeholder="考试种类" clearable class="filter-select" :loading="loadingCategories" @change="handleCategoryChange">
          <el-option
            v-for="item in categoryOptions"
            :key="item.id"
            :label="item.name"
            :value="item.id"
          />
        </el-select>

        <el-select v-model="filterForm.subjectId" placeholder="考试科目" clearable class="filter-select" :loading="loadingSubjects" :disabled="!filterForm.categoryId">
          <el-option
            v-for="item in filteredSubjectOptions"
            :key="item.id"
            :label="item.name"
            :value="item.id"
          />
        </el-select>

        <el-select v-model="filterForm.status" placeholder="状态" clearable class="filter-select">
          <el-option label="草稿" :value="0" />
          <el-option label="已发布" :value="1" />
          <el-option label="已归档" :value="2" />
        </el-select>

        <el-input
          v-model="searchKeyword"
          placeholder="搜索试卷..."
          class="search-input"
          clearable
          @clear="handleSearch"
          @keyup.enter="handleSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>

        <el-button type="primary" @click="handleSearch">查询</el-button>
      </div>

      <div class="right-operations">
        <el-dropdown @command="handleBatchCommand" trigger="click">
          <el-button>
            批量操作 <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="publish">批量发布</el-dropdown-item>
              <el-dropdown-item command="archive">批量归档</el-dropdown-item>
              <el-dropdown-item command="delete">批量删除</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <!-- 试卷列表表格 -->
    <div class="table-container">
      <el-table
        ref="tableRef"
        :data="paperList"
        stripe
        style="width: 100%"
        v-loading="loading"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="50" />
        <el-table-column label="序号" width="80">
          <template #default="{ $index }">
            {{ $index + 1 }}
          </template>
        </el-table-column>
        <el-table-column prop="title" label="试卷标题" min-width="200" show-overflow-tooltip />
        <el-table-column label="考试科目" width="120">
          <template #default="{ row }">
            {{ getSubjectName(row.subject_id) || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="total_time" label="时长(分钟)" width="100" />
        <el-table-column prop="total_score" label="总分" width="80" />
        <el-table-column prop="passing_score" label="及格分" width="80" />
        <el-table-column label="题目数" width="80">
          <template #default="{ row }">
            {{ row.config?.actual_question_count || 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status)" size="small">
              {{ getStatusName(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <div class="operation-buttons">
              <el-button link size="small" @click="previewPaper(row)">预览</el-button>
              <el-button link size="small" @click="editPaper(row)">编辑</el-button>
              <el-button link size="small" v-if="row.status === 0" @click="publishPaper(row)">发布</el-button>
              <el-button link size="small" v-if="row.status === 1" @click="archivePaper(row)">归档</el-button>
              <el-button link size="small" class="delete-btn" @click="deletePaper(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </div>

    <!-- 新建/编辑试卷弹窗 -->
    <el-dialog
      v-model="paperDialogVisible"
      :title="isEdit ? '编辑试卷' : '新建试卷'"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form :model="paperForm" :rules="formRules" ref="paperFormRef" label-width="100px">
        <el-form-item label="试卷标题" prop="title">
          <el-input v-model="paperForm.title" placeholder="请输入试卷标题" />
        </el-form-item>

        <el-form-item label="考试种类" prop="categoryId">
          <el-select v-model="paperForm.categoryId" placeholder="请选择考试种类" style="width: 100%" @change="handleDialogCategoryChange">
            <el-option
              v-for="item in categoryOptions"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="考试科目" prop="subjectId">
          <el-select v-model="paperForm.subjectId" placeholder="请选择考试科目" style="width: 100%" :disabled="!paperForm.categoryId">
            <el-option
              v-for="item in dialogFilteredSubjects"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="时长(分钟)" prop="totalTime">
              <el-input-number v-model="paperForm.totalTime" :min="1" :max="300" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="总分" prop="totalScore">
              <el-input-number v-model="paperForm.totalScore" :min="1" :max="500" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="及格分" prop="passingScore">
              <el-input-number v-model="paperForm.passingScore" :min="0" :max="paperForm.totalScore" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="描述">
          <el-input v-model="paperForm.description" type="textarea" :rows="3" placeholder="请输入试卷描述" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="paperDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="savePaper" :loading="saveLoading">保存</el-button>
      </template>
    </el-dialog>

    <!-- 试卷预览弹窗 -->
    <el-dialog
      v-model="previewDialogVisible"
      title="试卷预览"
      width="800px"
    >
      <div class="paper-preview" v-if="previewPaperData">
        <div class="preview-header">
          <h2>{{ previewPaperData.title }}</h2>
          <div class="preview-info">
            <span>科目：{{ getSubjectName(previewPaperData.subject_id) }}</span>
            <span>时长：{{ previewPaperData.total_time }}分钟</span>
            <span>总分：{{ previewPaperData.total_score }}</span>
            <span>及格：{{ previewPaperData.passing_score }}</span>
          </div>
        </div>
        <div class="preview-questions">
          <div v-for="(item, index) in previewPaperData.questions" :key="item.id" class="preview-question-item">
            <div class="question-header">
              <span class="question-index">{{ index + 1 }}.</span>
              <span class="question-type">[{{ getQuestionTypeName(item.question.question_type) }}]</span>
              <span class="question-score">({{ item.score }}分)</span>
            </div>
            <div class="question-content">{{ item.question.content }}</div>
            <!-- 选择题选项显示（单选题、多选题） -->
            <div v-if="item.question.options && item.question.options.length > 0" class="question-options">
              <div v-for="(opt, optIdx) in item.question.options" :key="opt.id" class="option-item">
                <span class="option-label">{{ opt.option_label }}.</span>
                <span>{{ opt.option_content }}</span>
                <span v-if="opt.is_correct" class="correct-badge">✓</span>
              </div>
            </div>
            <!-- 判断题答案 -->
            <div v-if="item.question.question_type === 'true_false'" class="true-false-answer">
              <span class="answer-label">答案：</span>
              <span>{{ item.question.answer === 'true' || item.question.answer === 'T' ? '正确' : '错误' }}</span>
            </div>
            <!-- 简答题答案 -->
            <div v-if="item.question.question_type === 'essay'" class="essay-answer">
              <span class="answer-label">参考答案：</span>
              <span>{{ item.question.answer }}</span>
            </div>
            <!-- 答案显示（选择题单独显示答案标签） -->
            <div v-if="item.question.options && item.question.options.length > 0" class="choice-answer">
              <span class="answer-label">正确答案：</span>
              <span>{{ getCorrectAnswerLabels(item.question.options) }}</span>
            </div>
            <!-- 解析 -->
            <div v-if="item.question.explanation" class="question-explanation">
              <span class="explanation-label">解析：</span>
              <span>{{ item.question.explanation }}</span>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="previewDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="exportWord">导出Word</el-button>
        <el-button type="primary" @click="exportPdf">导出PDF</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, ArrowDown } from '@element-plus/icons-vue'
import { adminAPI, systemAPI, paperAPI, api } from '@/api'

// 工具函数
const formatDate = (date) => {
  if (!date) return '-'
  const d = new Date(date)
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

// 状态
const loading = ref(false)
const loadingCategories = ref(false)
const loadingSubjects = ref(false)
const paperList = ref([])
const selectedRows = ref([])
const searchKeyword = ref('')
const paperDialogVisible = ref(false)
const previewDialogVisible = ref(false)
const isEdit = ref(false)
const saveLoading = ref(false)
const currentEditId = ref(null)
const previewPaperData = ref(null)
const tableRef = ref(null)
const paperFormRef = ref(null)

// 分页
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

// 筛选表单
const filterForm = reactive({
  categoryId: null,
  subjectId: null,
  status: null
})

// 考试种类选项
const categoryOptions = ref([])

// 考试科目选项
const subjectOptions = ref([])

// 计算属性：按考试种类筛选考试科目
const filteredSubjectOptions = computed(() => {
  if (!filterForm.categoryId) return subjectOptions.value
  return subjectOptions.value.filter(s => s.category_id === filterForm.categoryId)
})

// 弹窗内的考试科目（过滤用）
const dialogFilteredSubjects = computed(() => {
  if (!paperForm.categoryId) return subjectOptions.value
  return subjectOptions.value.filter(s => s.category_id === paperForm.categoryId)
})

// 试卷表单
const paperForm = reactive({
  title: '',
  categoryId: null,
  subjectId: null,
  totalTime: 120,
  totalScore: 100,
  passingScore: 60,
  description: ''
})

// 表单验证规则
const formRules = {
  title: [{ required: true, message: '请输入试卷标题', trigger: 'blur' }],
  categoryId: [{ required: true, message: '请选择考试种类', trigger: 'change' }],
  subjectId: [{ required: true, message: '请选择考试科目', trigger: 'change' }],
  totalTime: [{ required: true, message: '请输入时长', trigger: 'blur' }],
  totalScore: [{ required: true, message: '请输入总分', trigger: 'blur' }],
  passingScore: [{ required: true, message: '请输入及格分', trigger: 'blur' }]
}

// 挂载时获取数据
onMounted(() => {
  fetchCategories()
  fetchSubjects()
  fetchPaperList()
})

// 获取考试种类
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

// 获取考试科目
const fetchSubjects = async () => {
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

// 获取试卷列表
const fetchPaperList = async () => {
  loading.value = true
  try {
    const params = {
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

// 搜索
const handleSearch = () => {
  pagination.page = 1
  fetchPaperList()
}

// 分页变化
const handleSizeChange = () => {
  pagination.page = 1
  fetchPaperList()
}

const handlePageChange = () => {
  fetchPaperList()
}

// 考试种类变化
const handleCategoryChange = () => {
  filterForm.subjectId = null
  fetchPaperList()
}

// 弹窗内考试种类变化
const handleDialogCategoryChange = () => {
  paperForm.subjectId = null
}

// 获取科目名称
const getSubjectName = (subjectId) => {
  // exam_types.subject_id 对应 subjects.id
  const subject = subjectOptions.value.find(s => s.subject_id === subjectId)
  return subject?.name || ''
}

// 状态名称
const getStatusName = (status) => {
  const map = { 0: '草稿', 1: '已发布', 2: '已归档' }
  return map[status] ?? '草稿'
}

// 状态标签类型
const getStatusTagType = (status) => {
  const map = { 0: 'info', 1: 'success', 2: 'warning' }
  return map[status] ?? 'info'
}

// 题型名称
const getQuestionTypeName = (type) => {
  const map = {
    'single_choice': '单选题',
    'multiple_choice': '多选题',
    'true_false': '判断题',
    'essay': '简答题'
  }
  return map[type] || type
}

// 获取选择题正确答案标签
const getCorrectAnswerLabels = (options) => {
  if (!options || options.length === 0) return ''
  const correctLabels = options.filter(opt => opt.is_correct).map(opt => opt.option_label)
  return correctLabels.join(', ')
}

// 表格选择变化
const handleSelectionChange = (rows) => {
  selectedRows.value = rows
}

// 打开新建弹窗
const openPaperDialog = () => {
  isEdit.value = false
  currentEditId.value = null
  resetPaperForm()
  paperDialogVisible.value = true
}

// 编辑试卷
const editPaper = (row) => {
  isEdit.value = true
  currentEditId.value = row.id
  paperForm.title = row.title
  // 根据subject_id反推category_id（需要遍历）
  const subject = subjectOptions.value.find(s => s.id === row.subject_id)
  paperForm.categoryId = subject?.category_id || null
  paperForm.subjectId = row.subject_id
  paperForm.totalTime = row.total_time
  paperForm.totalScore = row.total_score
  paperForm.passingScore = row.passing_score
  paperForm.description = row.description || ''
  paperDialogVisible.value = true
}

// 重置表单
const resetPaperForm = () => {
  paperForm.title = ''
  paperForm.categoryId = null
  paperForm.subjectId = null
  paperForm.totalTime = 120
  paperForm.totalScore = 100
  paperForm.passingScore = 60
  paperForm.description = ''
}

// 保存试卷
const savePaper = async () => {
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

// 预览试卷
const previewPaper = async (row) => {
  try {
    const res = await adminAPI.getPaperById(row.id)
    previewPaperData.value = res.data
    previewDialogVisible.value = true
  } catch (e) {
    console.error('获取试卷详情失败:', e)
    ElMessage.error('获取试卷详情失败')
  }
}

// 发布试卷
const publishPaper = (row) => {
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

// 归档试卷
const archivePaper = (row) => {
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

// 删除试卷
const deletePaper = (row) => {
  ElMessageBox.confirm(`确定要删除试卷"${row.title}"吗？此操作不可恢复。`, '确认删除', { type: 'warning' })
    .then(async () => {
      try {
        await adminAPI.deletePaper(Number(row.id))
        ElMessage.success('删除成功')
        fetchPaperList()
      } catch (e) {
        console.error('删除失败:', e)
        ElMessage.error('删除失败')
      }
    })
    .catch(() => {})
}

// 批量操作
const handleBatchCommand = (command) => {
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
    ElMessageBox.confirm(`确定要删除选中的 ${ids.length} 份试卷吗？此操作不可恢复。`, '批量删除', { type: 'warning' })
      .then(async () => {
        try {
          for (const id of ids) {
            await adminAPI.deletePaper(Number(id))
          }
          ElMessage.success('批量删除成功')
          fetchPaperList()
        } catch (e) {
          ElMessage.error('批量删除失败')
        }
      })
      .catch(() => {})
  }
}

// 导出Word
const exportWord = async () => {
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

// 导出PDF
const exportPdf = async () => {
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
</script>

<style scoped>
.paper-management-view {
  padding: 0;
}

.operation-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 16px 20px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.left-operations {
  display: flex;
  gap: 12px;
  align-items: center;
}

.search-input {
  width: 160px;
}

.filter-select {
  width: 140px;
}

.right-operations {
  display: flex;
  gap: 12px;
}

.table-container {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.operation-buttons {
  display: flex;
  gap: 8px;
}

.delete-btn {
  color: #f56c6c;
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.paper-preview {
  max-height: 60vh;
  overflow-y: auto;
}

.preview-header {
  text-align: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 2px solid #e4e7ed;
}

.preview-header h2 {
  margin: 0 0 12px 0;
  color: #303133;
}

.preview-info {
  display: flex;
  justify-content: center;
  gap: 24px;
  color: #606266;
  font-size: 14px;
}

.preview-questions {
  padding: 0 8px;
}

.preview-question-item {
  margin-bottom: 20px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
}

.question-header {
  margin-bottom: 8px;
  font-size: 14px;
  color: #409eff;
}

.question-index {
  font-weight: 600;
  margin-right: 4px;
}

.question-type {
  margin-right: 8px;
}

.question-score {
  color: #67c23a;
}

.question-content {
  color: #303133;
  line-height: 1.6;
  margin-bottom: 12px;
}

.question-options {
  margin-top: 12px;
  padding-left: 20px;
}

.option-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 8px;
  line-height: 1.6;
}

.option-label {
  font-weight: 500;
  color: #409eff;
}

.correct-badge {
  color: #67c23a;
  font-size: 12px;
  margin-left: 8px;
}

.true-false-answer,
.essay-answer,
.choice-answer,
.question-explanation {
  margin-top: 12px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
  color: #606266;
}

.choice-answer {
  background: #f0f9ff;
  border: 1px solid #409eff;
  color: #303133;
}

.question-explanation {
  background: #f5f7fa;
  color: #606266;
  line-height: 1.6;
}

.answer-label {
  color: #67c23a;
  font-weight: 500;
}

.explanation-label {
  color: #909eff;
  font-weight: 500;
}
</style>
