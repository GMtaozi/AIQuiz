<template>
  <div class="question-bank-view">
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

        <el-select v-model="filterForm.examTypeId" placeholder="考试科目" clearable class="filter-select" :loading="loadingExamTypes" :disabled="!filterForm.categoryId">
          <el-option
            v-for="item in filteredExamTypeOptions"
            :key="item.id"
            :label="item.name"
            :value="item.id"
          />
        </el-select>

        <el-select v-model="filterForm.questionType" placeholder="题型" clearable class="filter-select">
          <el-option label="单选题" value="single" />
          <el-option label="多选题" value="multiple" />
          <el-option label="判断题" value="judge" />
          <el-option label="简答题" value="short_answer" />
        </el-select>

        <el-select v-model="filterForm.difficulty" placeholder="难度" clearable class="filter-select">
          <el-option label="简单" value="easy" />
          <el-option label="中等" value="medium" />
          <el-option label="困难" value="hard" />
        </el-select>

        <el-select v-model="filterForm.status" placeholder="状态" clearable class="filter-select">
          <el-option label="启用" :value="1" />
          <el-option label="待启用" :value="2" />
          <el-option label="禁用" :value="0" />
        </el-select>

        <el-input
          v-model="searchKeyword"
          placeholder="搜索题目..."
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
        <el-button type="primary" @click="openQuestionDialog">新建题目</el-button>

        <el-dropdown @command="handleBatchCommand" trigger="click">
          <el-button>
            批量操作 <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="import">批量导入</el-dropdown-item>
              <el-dropdown-item command="export">批量导出</el-dropdown-item>
              <el-dropdown-item command="delete">批量删除</el-dropdown-item>
              <el-dropdown-item command="status">批量修改状态</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <!-- 题目列表表格 -->
    <div class="table-container">
      <el-table
        ref="tableRef"
        :data="questionList"
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
        <el-table-column prop="content" label="题目内容" min-width="300">
          <template #default="{ row }">
            <div class="question-content" v-html="renderMarkdown(row.content)"></div>
          </template>
        </el-table-column>
        <el-table-column label="考试科目" width="120">
          <template #default="{ row }">
            {{ getExamTypeName(row.subject_id) || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="题型" width="100">
          <template #default="{ row }">
            {{ getTypeName(row.question_type) }}
          </template>
        </el-table-column>
        <el-table-column label="难度" width="100">
          <template #default="{ row }">
            <el-tag :type="getDifficultyType(row.difficulty)" size="small" class="difficulty-tag">
              {{ getDifficultyName(row.difficulty) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createTime" label="创建时间" width="120">
          <template #default="{ row }">
            {{ formatDate(row.createTime) }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status)" size="small">
              {{ getStatusName(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <div class="operation-buttons">
              <el-button link size="small" @click="previewQuestion(row)">预览</el-button>
              <el-button link size="small" @click="editQuestion(row)">编辑</el-button>
              <el-button link size="small" class="delete-btn" @click="deleteQuestion(row.id)">删除</el-button>
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

    <!-- 新建/编辑题目弹窗 -->
    <el-dialog
      v-model="questionDialogVisible"
      :title="isEdit ? '编辑题目' : '新建题目'"
      width="680px"
      :close-on-click-modal="false"
    >
      <el-form :model="questionForm" :rules="formRules" ref="questionFormRef" label-width="80px">
        <div class="form-section">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="题型" prop="type">
                <el-select v-model="questionForm.type" placeholder="请选择" style="width: 100%">
                  <el-option label="单选题" value="single" />
                  <el-option label="多选题" value="multiple" />
                  <el-option label="判断题" value="judge" />
                  <el-option label="简答题" value="short_answer" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="难度" prop="difficulty">
                <el-select v-model="questionForm.difficulty" placeholder="请选择" style="width: 100%">
                  <el-option label="简单" value="easy" />
                  <el-option label="中等" value="medium" />
                  <el-option label="困难" value="hard" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <div class="form-section">
          <el-form-item label="题目内容" prop="content">
            <el-input
              v-model="questionForm.content"
              type="textarea"
              :rows="3"
              placeholder="请输入题目内容，支持Markdown格式"
            />
          </el-form-item>
        </div>

        <!-- 选项配置（单选/多选） -->
        <div class="form-section" v-if="questionForm.type === 'single' || questionForm.type === 'multiple'">
          <el-form-item label="选项列表">
            <div class="options-list">
              <div v-for="(option, index) in questionForm.options" :key="index" class="option-item">
                <el-radio
                  v-if="questionForm.type === 'single'"
                  v-model="questionForm.correctAnswer"
                  :label="index"
                  class="option-radio"
                >
                  {{ String.fromCharCode(65 + index) }}.
                </el-radio>
                <el-checkbox
                  v-else
                  v-model="questionForm.correctAnswer"
                  :label="index"
                  class="option-checkbox"
                >
                  {{ String.fromCharCode(65 + index) }}.
                </el-checkbox>
                <el-input v-model="option.content" placeholder="请输入选项内容" class="option-input" />
                <el-button
                  v-if="questionForm.options.length > 2"
                  type="danger"
                  link
                  @click="removeOption(index)"
                >
                  删除
                </el-button>
              </div>
              <el-button type="primary" link @click="addOption" v-if="questionForm.options.length < 6">
                + 添加选项
              </el-button>
            </div>
          </el-form-item>
        </div>

        <!-- 判断题正确答案 -->
        <div class="form-section" v-if="questionForm.type === 'judge'">
          <el-form-item label="正确答案" prop="correctAnswer">
            <el-radio-group v-model="questionForm.judgeAnswer">
              <el-radio :value="true">正确</el-radio>
              <el-radio :value="false">错误</el-radio>
            </el-radio-group>
          </el-form-item>
        </div>

        <!-- 简答题 -->
        <div class="form-section" v-if="questionForm.type === 'short_answer'">
          <el-form-item label="参考答案" prop="correctAnswer">
            <el-input
              v-model="questionForm.correctAnswer"
              type="textarea"
              :rows="3"
              placeholder="请输入参考答案"
            />
          </el-form-item>
        </div>

        <div class="form-section">
          <el-form-item label="解析">
            <el-input
              v-model="questionForm.explanation"
              type="textarea"
              :rows="2"
              placeholder="请输入题目解析"
            />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="questionDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitQuestionForm" :loading="submitLoading">确定</el-button>
      </template>
    </el-dialog>

    <!-- 题目预览弹窗 -->
    <el-dialog v-model="previewDialogVisible" title="题目预览" width="600px">
      <div class="question-preview" v-if="currentQuestion">
        <div class="preview-header">
          <el-tag>{{ getTypeName(currentQuestion.question_type) }}</el-tag>
          <el-tag :type="getDifficultyType(currentQuestion.difficulty)">
            {{ getDifficultyName(currentQuestion.difficulty) }}
          </el-tag>
        </div>
        <div class="preview-content" v-html="renderMarkdown(currentQuestion.content)"></div>
        <div class="preview-options" v-if="currentQuestion.options">
          <div
            v-for="(option, index) in currentQuestion.options"
            :key="index"
            class="preview-option"
            :class="{ correct: isCorrectAnswer(index) }"
          >
            <span class="option-label">{{ String.fromCharCode(65 + index) }}.</span>
            <span v-html="option.option_content"></span>
          </div>
        </div>
        <div class="preview-answer">
          <strong>正确答案：</strong>
          <span v-if="currentQuestion.question_type === 'true_false'">
            {{ currentQuestion.answer === 'true' ? '正确' : '错误' }}
          </span>
          <span v-else-if="currentQuestion.question_type === 'essay' || currentQuestion.question_type === 'short_answer'">
            {{ currentQuestion.answer }}
          </span>
          <span v-else>
            {{ formatAnswer(currentQuestion.answer) }}
          </span>
        </div>
        <div class="preview-explanation" v-if="currentQuestion.explanation">
          <strong>解析：</strong>
          <span v-html="renderMarkdown(currentQuestion.explanation)"></span>
        </div>
      </div>
      <template #footer>
        <el-button @click="previewDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 批量导入弹窗 -->
    <el-dialog v-model="importDialogVisible" title="批量导入题目" width="700px">
      <div class="import-target-settings">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="考试种类" required>
              <el-select v-model="importCategoryId" placeholder="请选择考试种类" clearable style="width: 100%">
                <el-option
                  v-for="cat in categoryOptions"
                  :key="cat.id"
                  :label="cat.name"
                  :value="cat.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="考试科目" required>
              <el-select v-model="importSubjectId" placeholder="请选择考试科目" clearable style="width: 100%">
                <el-option
                  v-for="subj in filteredExamTypeOptions"
                  :key="subj.id"
                  :label="subj.name"
                  :value="subj.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
      </div>
      <el-tabs v-model="importTab">
        <el-tab-pane label="上传文件" name="excel">
          <div class="import-upload">
            <el-upload
              ref="uploadRef"
              drag
              :limit="1"
              accept=".xlsx,.xls,.docx"
              :auto-upload="false"
              :on-change="handleFileChange"
              :disabled="!!previewResult"
            >
              <el-icon class="el-icon--upload"><upload-filled /></el-icon>
              <div class="el-upload__text">将文件拖到此处，或<em>点击上传</em></div>
              <template #tip>
                <div class="el-upload__tip">支持 Excel (.xlsx/.xls) 和 Word (.docx) 文件</div>
              </template>
            </el-upload>
            <el-button type="primary" @click="downloadTemplate" class="template-btn">下载导入模板</el-button>
          </div>

          <!-- 预览结果 -->
          <div class="preview-result" v-if="previewResult && !importResult">
            <el-alert type="success" :closable="false">
              <template #title>
                系统已识别文档内容，共发现 <strong>{{ previewResult.total }}</strong> 道题目：
              </template>
            </el-alert>
            <div class="preview-stats">
              <el-row :gutter="8" style="margin-top: 16px;">
                <el-col :span="4">
                  <el-statistic title="单选题" :value="previewResult.single_choice" />
                </el-col>
                <el-col :span="4">
                  <el-statistic title="多选题" :value="previewResult.multiple_choice" />
                </el-col>
                <el-col :span="4">
                  <el-statistic title="判断题" :value="previewResult.true_false" />
                </el-col>
                <el-col :span="4">
                  <el-statistic title="简答题" :value="previewResult.essay" />
                </el-col>
                <el-col :span="4">
                  <el-statistic title="文件内重复" :value="previewResult.internal_duplicate_count">
                    <template #suffix>
                      <span v-if="previewResult.internal_duplicate_count > 0" style="color: #E6A23C; font-size: 14px;">(将去重)</span>
                    </template>
                  </el-statistic>
                </el-col>
                <el-col :span="4">
                  <el-statistic title="库内重复" :value="previewResult.duplicate_count">
                    <template #suffix>
                      <span v-if="previewResult.duplicate_count > 0" style="color: #E6A23C; font-size: 14px;">(已存在)</span>
                    </template>
                  </el-statistic>
                </el-col>
              </el-row>
              <el-row :gutter="8" style="margin-top: 12px;">
                <el-col :span="24">
                  <el-alert type="success" :closable="false">
                    实际可导入 <strong>{{ previewResult.unique_count }}</strong> 道题目
                  </el-alert>
                </el-col>
              </el-row>
            </div>
            <el-alert
              type="warning"
              :closable="false"
              style="margin-top: 16px;"
            >
              导入后所有题目状态为"待审核"，需要审核后才能使用。
            </el-alert>
          </div>
        </el-tab-pane>
        <el-tab-pane label="粘贴文本" name="text" disabled>
          <div class="import-text">
            <el-input
              v-model="importText"
              type="textarea"
              :rows="10"
              placeholder="请粘贴题目文本，格式要求：&#10;题目内容|题型|难度|正确答案|选项A|选项B|选项C|选项D&#10;每行一个题目"
            />
            <div class="text-format-tip">
              <el-alert type="info" :closable="false">
                格式说明：题目内容|题型(单选/多选/判断/简答)|难度(简单/中等/困难)|正确答案|选项内容（简答和判断题不需要选项）
              </el-alert>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>

      <!-- 导入进度 -->
      <div class="import-progress" v-if="importing">
        <el-progress :percentage="importProgress" :status="importProgressStatus" />
        <div class="progress-text">正在导入... {{ importedCount }} / {{ totalCount }}</div>
      </div>

      <!-- 导入结果 -->
      <div class="import-result" v-if="importResult">
        <el-statistic title="导入成功" :value="importResult.success" />
        <el-statistic title="导入失败" :value="importResult.failed" />
        <el-statistic title="重复题目" :value="importResult.duplicate" />
      </div>

      <template #footer>
        <div v-if="previewResult && !importResult">
          <el-button @click="resetPreview">重新选择</el-button>
          <el-button type="primary" @click="startImport" :loading="importing">确认导入</el-button>
        </div>
        <div v-else>
          <el-button @click="importDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handlePreview" :disabled="!selectedFile">预览</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 导出设置弹窗 -->
    <el-dialog v-model="exportDialogVisible" title="导出题目" width="500px">
      <el-form :model="exportForm" label-width="100px">
        <el-form-item label="导出格式">
          <el-radio-group v-model="exportForm.format">
            <el-radio value="excel">Excel</el-radio>
            <el-radio value="word">Word</el-radio>
            <el-radio value="pdf">PDF</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="导出范围">
          <el-radio-group v-model="exportForm.scope">
            <el-radio value="selected">选中题目 ({{ selectedQuestions.length }}道)</el-radio>
            <el-radio value="filtered">筛选结果 ({{ pagination.total }}道)</el-radio>
            <el-radio value="all">全部题目 ({{ pagination.total }}道)</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="自定义字段">
          <el-checkbox-group v-model="exportForm.fields">
            <el-checkbox value="id">题目ID</el-checkbox>
            <el-checkbox value="content">题目内容</el-checkbox>
            <el-checkbox value="type">题型</el-checkbox>
            <el-checkbox value="difficulty">难度</el-checkbox>
            <el-checkbox value="knowledge">知识点</el-checkbox>
            <el-checkbox value="answer">正确答案</el-checkbox>
            <el-checkbox value="explanation">解析</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="exportDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="startExport">导出</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Search, ArrowDown, CircleCheck, Select, Finished, Edit,
  UploadFilled
} from '@element-plus/icons-vue'
import { adminAPI, systemAPI, questionBankAPI } from '@/api'

// 状态
const loading = ref(false)
const searchKeyword = ref('')
const questionList = ref([])
const selectedQuestions = ref([])

// 考试种类和科目
const categoryOptions = ref([])
const examTypeOptions = ref([])
const loadingCategories = ref(false)
const loadingExamTypes = ref(false)

// 弹窗状态
const questionDialogVisible = ref(false)
const previewDialogVisible = ref(false)
const importDialogVisible = ref(false)
const exportDialogVisible = ref(false)
const isEdit = ref(false)
const submitLoading = ref(false)
const currentQuestion = ref(null)

// 导入相关
const importTab = ref('excel')
const importFormat = ref('excel')
const importText = ref('')
const importing = ref(false)
const importProgress = ref(0)
const importedCount = ref(0)
const totalCount = ref(0)
const importResult = ref(null)
const uploadRef = ref(null)
const selectedFile = ref(null)
const importCategoryId = ref(null)
const importSubjectId = ref(null)
const previewResult = ref(null)

// 导出相关
const exportForm = reactive({
  format: 'excel',
  scope: 'filtered',
  fields: ['content', 'type', 'difficulty', 'answer']
})

// 分页
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

// 筛选表单
const filterForm = reactive({
  categoryId: null,
  examTypeId: null,
  questionType: '',
  difficulty: '',
  status: null
})

// 题目表单
const questionForm = reactive({
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
const formRules = {
  type: [{ required: true, message: '请选择题型', trigger: 'change' }],
  difficulty: [{ required: true, message: '请选择难度', trigger: 'change' }],
  content: [{ required: true, message: '请输入题目内容', trigger: 'blur' }]
}

// 计算属性
const importProgressStatus = computed(() => {
  if (importProgress.value === 100) return 'success'
  return undefined
})

const filteredExamTypeOptions = computed(() => {
  if (!filterForm.categoryId) return examTypeOptions.value
  return examTypeOptions.value.filter(et => et.category_id === filterForm.categoryId)
})

// 考试种类变化时清空考试科目
const handleCategoryChange = () => {
  filterForm.examTypeId = null
}

// 生命周期
onMounted(() => {
  fetchCategories()
  fetchExamTypes()
  fetchQuestionList()
})

// 获取考试种类
const fetchCategories = async () => {
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
const fetchExamTypes = async () => {
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
const fetchQuestionList = async () => {
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
      question_type: filterForm.questionType ? (typeMap[filterForm.questionType] || filterForm.questionType) : undefined,
      difficulty: filterForm.difficulty ? (difficultyMap[filterForm.difficulty] || parseInt(filterForm.difficulty)) : undefined,
      category_id: filterForm.categoryId || undefined,
      subject_id: filterForm.examTypeId || undefined,
      status: filterForm.status !== null ? filterForm.status : undefined
    }
    const response = await adminAPI.getQuestions(params)
    let list = response.data.items.map(item => ({
      ...item,
      createTime: item.created_at || item.createTime,
      status: item.status ?? 1,
      knowledgePoints: item.knowledgePoints || [],
      meta: item.meta || {}
    }))
    // 排序：启用(1) > 待启用(2) > 禁用(0)
    list.sort((a, b) => {
      const order = { 1: 0, 2: 1, 0: 2 }
      return (order[a.status] ?? 3) - (order[b.status] ?? 3)
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
const handleSearch = () => {
  pagination.page = 1
  fetchQuestionList()
}

// 分页
const handleSizeChange = (val) => {
  pagination.pageSize = val
  fetchQuestionList()
}

const handlePageChange = (val) => {
  pagination.page = val
  fetchQuestionList()
}

// 选择变化
const handleSelectionChange = (selection) => {
  selectedQuestions.value = selection
}

// 状态切换
const handleStatusChange = async (row) => {
  try {
    await adminAPI.updateQuestionStatus(row.id, { status: row.status })
    ElMessage.success('状态更新成功')
  } catch (error) {
    ElMessage.error('状态更新失败')
    row.status = row.status === 1 ? 0 : 1
  }
}

// 批量操作
const handleBatchCommand = (command) => {
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
const handleBatchDelete = () => {
  ElMessageBox.confirm(`确定要删除选中的 ${selectedQuestions.value.length} 道题目吗？删除后可在状态筛选中恢复。`, '提示', {
    type: 'warning'
  }).then(async () => {
    try {
      // 批量删除实际上是软删除：直接设置状态为禁用
      for (const question of selectedQuestions.value) {
        await adminAPI.updateQuestion(question.id, { status: 0 })
      }
      ElMessage.success('删除成功（已禁用）')
      fetchQuestionList()
    } catch (error) {
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

// 批量修改状态：启用(1)→待启用(2)，待启用(2)→启用(1)，禁用(0)不可操作
const handleBatchStatusChange = () => {
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
      for (const question of selectedQuestions.value) {
        if (question.status === 1 && newStatus === 2) {
          await adminAPI.updateQuestion(question.id, { status: 2 })
        } else if (question.status === 2 && newStatus === 1) {
          await adminAPI.updateQuestion(question.id, { status: 1 })
        }
      }
      ElMessage.success(newStatus === 2 ? '已设为待启用' : '已恢复为启用')
      fetchQuestionList()
    } catch (error) {
      ElMessage.error('状态更新失败')
    }
  }).catch(() => {})
}

// 新建/编辑题目
const openQuestionDialog = () => {
  isEdit.value = false
  resetQuestionForm()
  questionDialogVisible.value = true
}

const editQuestion = (row) => {
  isEdit.value = true
  // 转换题型: single_choice -> single, multiple_choice -> multiple, true_false -> judge, essay -> short_answer
  const typeMap = { 'single_choice': 'single', 'multiple_choice': 'multiple', 'true_false': 'judge', 'essay': 'short_answer' }
  // 转换难度: 1-2 -> easy, 3 -> medium, 4-5 -> hard
  const difficultyMap = { 1: 'easy', 2: 'easy', 3: 'medium', 4: 'hard', 5: 'hard' }

  Object.assign(questionForm, {
    id: row.id,
    type: typeMap[row.question_type] || row.question_type,
    difficulty: difficultyMap[row.difficulty] || row.difficulty,
    score: row.score,
    content: row.content,
    options: (row.options || []).map(opt => ({
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
const resetQuestionForm = () => {
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
const submitQuestionForm = async () => {
  try {
    submitLoading.value = true
    const data = { ...questionForm }

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
const deleteQuestion = (id) => {
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
const previewQuestion = (row) => {
  currentQuestion.value = row
  previewDialogVisible.value = true
}

// 选项操作
const addOption = () => {
  if (questionForm.options.length < 6) {
    questionForm.options.push({ content: '' })
  }
}

const removeOption = (index) => {
  questionForm.options.splice(index, 1)
  if (questionForm.correctAnswer >= index) {
    questionForm.correctAnswer = Math.max(0, questionForm.correctAnswer - 1)
  }
}

// 导入相关
const showImportDialog = () => {
  importDialogVisible.value = true
  importResult.value = null
  previewResult.value = null
  importProgress.value = 0
  importedCount.value = 0
}

// 预览导入
const handlePreview = async () => {
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
  } catch (err) {
    console.error('预览失败:', err)
    ElMessage.error(err.response?.data?.detail || '预览失败')
    previewResult.value = null
  }
}

// 重新预览
const resetPreview = () => {
  previewResult.value = null
  selectedFile.value = null
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
}

const handleFileChange = (file) => {
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

const downloadTemplate = () => {
  ElMessage.success('正在下载导入模板')
}

const startImport = async () => {
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
  } catch (err) {
    console.error('导入失败:', err)
    ElMessage.error(err.response?.data?.detail || '导入失败')
    importing.value = false
  }
}

// 导出相关
const showExportDialog = () => {
  exportDialogVisible.value = true
}

const startExport = async () => {
  try {
    // 构建查询参数
    const params = {
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
        params.question_type = typeMap[filterForm.questionType] || filterForm.questionType
      }
      if (filterForm.difficulty !== null && filterForm.difficulty !== undefined) {
        const diffMap = { 'easy': 2, 'medium': 3, 'hard': 5 }
        params.difficulty = diffMap[filterForm.difficulty]
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
const getTypeName = (type) => {
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
  return map[type] || type
}

const getDifficultyType = (difficulty) => {
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
  return map[difficulty] || 'info'
}

const getDifficultyName = (difficulty) => {
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
  return map[difficulty] || difficulty
}

const getStatusName = (status) => {
  const map = { 0: '禁用', 1: '启用', 2: '待启用' }
  return map[status] ?? '启用'
}

const getStatusTagType = (status) => {
  const map = { 0: 'danger', 1: 'success', 2: 'warning' }
  return map[status] ?? 'info'
}

const getExamTypeName = (subjectId) => {
  if (!subjectId) return ''
  const id = Number(subjectId)
  // questions.subject_id 对应 subjects.id，也对应 exam_types.subject_id
  const subject = examTypeOptions.value.find(et => Number(et.subject_id) === id)
  return subject ? subject.name : ''
}

const getCategoryName = (categoryId) => {
  if (!categoryId) return ''
  const id = Number(categoryId)
  const category = categoryOptions.value.find(c => Number(c.id) === id)
  return category ? category.name : ''
}

const formatDate = (date) => {
  if (!date) return '-'
  const d = new Date(date)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const renderMarkdown = (content) => {
  if (!content) return ''
  return content
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
}

const isCorrectAnswer = (index) => {
  if (!currentQuestion.value) return false
  // 将 index (0,1,2,3) 转换为字母 (A,B,C,D)
  const correctLetter = String.fromCharCode(65 + index)
  const answer = currentQuestion.value.answer
  if (Array.isArray(answer)) {
    return answer.includes(correctLetter)
  }
  return answer === correctLetter
}

const formatAnswer = (answer) => {
  if (Array.isArray(answer)) {
    return answer.join(', ')
  }
  // answer 已经是字母字符串如 'A' 或 'A,B'
  return answer || '-'
}
</script>

<style scoped>
.question-bank-view {
  padding: 20px;
  background-color: #f5f5f5;
  min-height: calc(100vh - 60px);
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

.question-content {
  max-height: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.type-icon {
  font-size: 18px;
  color: #409eff;
}

.difficulty-tag {
  border-radius: 12px;
}

.knowledge-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.knowledge-tag {
  border-radius: 12px;
  background-color: #ecf5ff;
  color: #409eff;
  border: none;
}

.more-tag {
  border-radius: 12px;
  background-color: #f4f4f5;
  color: #909399;
  border: none;
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

/* 表单样式 */
.form-section {
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #ebeef5;
}

.form-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
}

.options-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.option-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.option-radio,
.option-checkbox {
  width: 50px;
}

.option-input {
  flex: 1;
}

/* 预览样式 */
.preview-header {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 16px;
}

.preview-score {
  margin-left: auto;
  color: #909399;
}

.preview-content {
  font-size: 16px;
  line-height: 1.8;
  margin-bottom: 20px;
}

.preview-options {
  margin-bottom: 20px;
}

.preview-option {
  padding: 8px 12px;
  border-radius: 4px;
  margin-bottom: 8px;
  background-color: #f5f7fa;
}

.preview-option.correct {
  background-color: #f0f9ff;
  border: 1px solid #409eff;
}

.option-label {
  font-weight: bold;
  margin-right: 8px;
}

.preview-answer,
.preview-explanation {
  padding: 12px;
  background-color: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 12px;
  line-height: 1.6;
}

/* 导入样式 */
.import-upload {
  text-align: center;
}

.template-btn {
  margin-top: 16px;
}

.import-progress {
  margin-top: 20px;
}

.progress-text {
  text-align: center;
  margin-top: 8px;
  color: #909399;
}

.import-result {
  display: flex;
  justify-content: space-around;
  margin-top: 20px;
  padding: 20px;
  background-color: #f5f7fa;
  border-radius: 8px;
}

.text-format-tip {
  margin-top: 16px;
}
</style>
