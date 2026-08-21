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
        <el-button type="warning" @click="showSimilarityCheck">查重</el-button>
      </div>
    </div>

    <!-- 题目列表表格 -->
    <div class="table-container">
      <el-empty v-if="!loading && questionList.length === 0" description="暂无题目数据" :image-size="80" />
      <el-table
        v-else
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
            <span v-html="renderMarkdown(option.option_content)"></span>
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

    <!-- 相似度检测弹窗 -->
    <el-dialog
      v-model="similarityDialogVisible"
      title="题目相似度检测"
      width="1000px"
      :close-on-click-modal="false"
    >
      <div v-if="similarityData">
        <div class="similarity-summary">
          <span>检测范围：{{ getFilterSummary() }}</span>
          <span>发现相似对：<strong :style="{color: similarityData.similar_pairs_count > 0 ? '#f56c6c' : '#67c23a'}">{{ similarityData.similar_pairs_count }}</strong> 对</span>
        </div>

        <el-alert v-if="similarityData.message" type="info" :closable="false" style="margin-bottom: 16px;">
          {{ similarityData.message }}
        </el-alert>

        <el-table v-if="similarityData.similar_pairs.length > 0" :data="similarityData.similar_pairs" stripe style="width: 100%">
          <el-table-column label="相似度" width="120">
            <template #default="{ row }">
              <el-tag :type="getSimilarityType(row.similarity_score)" size="large">
                {{ Math.round(row.similarity_score * 100) }}%
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="相似等级" width="120">
            <template #default="{ row }">
              <el-tag :type="getSimilarityType(row.similarity_score)" size="small">
                {{ getSimilarityLevel(row.similarity_score) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="question_type" label="题型" width="120">
            <template #default="{ row }">
              {{ getTypeName(row.question_type) }}
            </template>
          </el-table-column>
          <el-table-column label="题目A" min-width="250" show-overflow-tooltip>
            <template #default="{ row }">
              <div class="similarity-content">
                <span class="similarity-id">#{{ row.question_a_id }}</span>
                <span>{{ row.question_a_content }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="题目B" min-width="250" show-overflow-tooltip>
            <template #default="{ row }">
              <div class="similarity-content">
                <span class="similarity-id">#{{ row.question_b_id }}</span>
                <span>{{ row.question_b_content }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="similarity_reason" label="相似原因" min-width="180" show-overflow-tooltip />
        </el-table>

        <el-empty v-else description="未发现相似题目" :image-size="80" />
      </div>
      <div v-else class="similarity-empty">
        <p>点击下方按钮开始检测题库中的相似题目</p>
        <div class="similarity-config">
          <span>相似度阈值：</span>
          <el-slider v-model="similarityThreshold" :min="0" :max="1" :step="0.1" style="width: 300px;" />
          <span>{{ Math.round(similarityThreshold * 100) }}%</span>
        </div>
      </div>
      <template #footer>
        <el-button @click="similarityDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="runSimilarityCheck" :loading="similarityLoading">
          {{ similarityData ? '重新检测' : '开始检测' }}
        </el-button>
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
import { useQuestionBank } from '@/composables/useQuestionBank'

// 获取筛选条件摘要
const getFilterSummary = () => {
  const parts = []
  if (filterForm.examTypeId) {
    const subject = examTypeOptions.value.find(et => et.id === filterForm.examTypeId)
    if (subject) parts.push(subject.name)
  }
  if (filterForm.questionType) {
    const typeMap = { single: '单选题', multiple: '多选题', judge: '判断题', short_answer: '简答题' }
    parts.push(typeMap[filterForm.questionType] || filterForm.questionType)
  }
  if (filterForm.difficulty) {
    const diffMap = { easy: '简单', medium: '中等', hard: '困难' }
    parts.push(diffMap[filterForm.difficulty] || filterForm.difficulty)
  }
  return parts.length > 0 ? parts.join(' / ') : '全部题目'
}

const {
  // State
  loading,
  searchKeyword,
  questionList,
  selectedQuestions,
  categoryOptions,
  examTypeOptions,
  loadingCategories,
  loadingExamTypes,
  questionDialogVisible,
  previewDialogVisible,
  importDialogVisible,
  exportDialogVisible,
  isEdit,
  submitLoading,
  currentQuestion,
  importTab,
  importFormat,
  importText,
  importing,
  importProgress,
  importedCount,
  totalCount,
  importResult,
  uploadRef,
  selectedFile,
  importCategoryId,
  importSubjectId,
  previewResult,
  // Forms
  exportForm,
  pagination,
  filterForm,
  questionForm,
  formRules,
  // Computed
  importProgressStatus,
  filteredExamTypeOptions,
  // Actions
  handleCategoryChange,
  fetchCategories,
  fetchExamTypes,
  fetchQuestionList,
  handleSearch,
  handleSizeChange,
  handlePageChange,
  handleSelectionChange,
  handleStatusChange,
  handleBatchCommand,
  handleBatchDelete,
  handleBatchStatusChange,
  openQuestionDialog,
  editQuestion,
  resetQuestionForm,
  submitQuestionForm,
  deleteQuestion,
  showImportDialog,
  handlePreview,
  resetPreview,
  handleFileChange,
  downloadTemplate,
  startImport,
  showExportDialog,
  startExport,
  // Helpers
  getTypeName,
  getDifficultyType,
  getDifficultyName,
  getStatusName,
  getStatusTagType,
  getExamTypeName,
  getCategoryName,
  formatDate,
  renderMarkdown,
  isCorrectAnswer,
  formatAnswer,
  // 相似度检测
  similarityDialogVisible,
  similarityLoading,
  similarityData,
  similarityThreshold,
  showSimilarityCheck,
  runSimilarityCheck,
  getSimilarityType,
  getSimilarityLevel
} = useQuestionBank()

// Initialize
onMounted(() => {
  fetchCategories()
  fetchExamTypes()
  fetchQuestionList()
})
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
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
}

.right-operations {
  display: flex;
  gap: 12px;
}

.search-input {
  width: 200px;
}

.filter-select {
  width: 150px;
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

.similarity-summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 6px;
  margin-bottom: 16px;
  font-size: 14px;
  color: #606266;
}

.similarity-summary span:last-child {
  font-weight: 600;
}

.similarity-empty {
  text-align: center;
  padding: 40px 20px;
  color: #909399;
}

.similarity-config {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-top: 24px;
  font-size: 14px;
  color: #606266;
}

.similarity-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.similarity-id {
  font-size: 12px;
  color: #909399;
}
</style>
