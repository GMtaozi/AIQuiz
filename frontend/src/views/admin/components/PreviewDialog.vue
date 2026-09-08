<template>
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
</template>

<script setup>
import {
  previewDialogVisible,
  previewPaperData,
  getSubjectName,
  getQuestionTypeName,
  getCorrectAnswerLabels,
  exportWord,
  exportPdf
} from '@/composables/usePaperManagement'
</script>

<style scoped>
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
