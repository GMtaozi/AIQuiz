<template>
  <div class="auto-paper-view">
    <el-card>
      <template #header>
        <div class="card-header">
          <h3>智能组卷</h3>
          <div class="header-actions">
            <el-button @click="saveDraft" :disabled="currentStep < 4">
              <Icon icon="mdi:content-save" />
              保存草稿
            </el-button>
            <el-button @click="saveAsTemplate" :disabled="!paperForm.subjectId">
              <Icon icon="mdi:star" />
              保存为模板
            </el-button>
            <el-button type="primary" @click="publishPaper" :disabled="currentStep < 4">
              <Icon icon="mdi:send" />
              直接发布
            </el-button>
          </div>
        </div>
      </template>

      <!-- 步骤条 -->
      <div class="steps-container">
        <el-steps :active="currentStep" finish-status="success" align-center>
          <el-step title="选择模板" icon="mdi:file-document-outline" />
          <el-step title="基本信息" icon="mdi:pencil" />
          <el-step title="知识点配置" icon="mdi:treasure-chest" />
          <el-step title="试卷大纲" icon="mdi:menu" />
          <el-step title="AI分配题目" icon="mdi:auto-fix" />
          <el-step title="调整预览" icon="mdi:eye" />
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
                <Icon :icon="template.icon" :size="32" />
              </div>
              <div class="template-info">
                <h5>{{ template.name }}</h5>
                <p>{{ template.description }}</p>
                <div class="template-meta">
                  <span><Icon icon="mdi:help-circle" /> {{ template.questionCount }}题</span>
                  <span><Icon icon="mdi:timer" /> {{ template.duration }}分钟</span>
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

      <!-- Step 4: 试卷大纲 -->
      <div v-show="currentStep === 3" class="step-content">
        <div class="outline-section">
          <h4>AI 试卷大纲</h4>
          <p class="outline-desc">
            基于已选知识点和题型配置，自动生成章节级出题计划。您可以在此基础上调整，确认后进入 AI 出题。
          </p>

          <div v-if="outlineLoading" class="outline-loading">
            <Icon icon="mdi:loading" spin />
            <span>AI 正在生成大纲...</span>
          </div>

          <template v-else>
            <el-alert v-if="outlineMessage" :title="outlineMessage" type="info" :closable="false" style="margin-bottom: 16px;" />

            <el-table :data="outlineSections" stripe style="width: 100%" max-height="400">
              <el-table-column type="index" label="#" width="60" />
              <el-table-column prop="section_name" label="章节/题型" min-width="180" />
              <el-table-column prop="question_type" label="题型" width="120">
                <template #default="{ row }">
                  <el-tag size="small">{{ getTypeName(row.question_type) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="count" label="题数" width="100" />
              <el-table-column prop="score" label="分值" width="100" />
              <el-table-column label="关联知识点" min-width="200">
                <template #default="{ row }">
                  <el-tag
                    v-for="kpId in row.knowledge_point_ids"
                    :key="kpId"
                    size="small"
                    style="margin-right: 4px;"
                  >
                    {{ getKnowledgePointName(kpId) }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>

            <div class="outline-actions">
              <el-button @click="regenerateOutline" :loading="outlineLoading">
                <Icon icon="mdi:refresh" />
                重新生成
              </el-button>
            </div>
          </template>
        </div>

        <div class="step-actions">
          <el-button @click="prevStep">上一步</el-button>
          <el-button type="primary" @click="confirmOutline" :disabled="!outlineSections.length">
            确认大纲，继续
          </el-button>
        </div>
      </div>

      <!-- Step 5: AI分配题目 -->
      <div v-show="currentStep === 4" class="step-content">
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
                <Icon icon="mdi:auto-fix" />
                智能调整难度分布
              </el-button>
            </div>
            <div class="summary-item" v-else>
              <el-tooltip content="不选择知识点时，题目难度为默认值，无需调整分布">
                <el-button type="warning" size="small" disabled>
                  <Icon icon="mdi:auto-fix" />
                  智能调整难度分布
                </el-button>
              </el-tooltip>
            </div>
          </div>

          <div class="ai-generate-action">
            <el-button type="primary" size="large" @click="generateQuestions" :loading="generating">
              <Icon v-if="!generating" icon="mdi:auto-fix" />
              {{ generating ? 'AI正在分配题目...' : 'AI智能分配题目' }}
            </el-button>
            <el-button size="large" @click="generateABPapers" :loading="generating">
              <Icon icon="mdi:file-document-multiple" />
              生成 A/B 卷
            </el-button>
          </div>
        </div>

        <div class="step-actions">
          <el-button @click="prevStep">上一步</el-button>
        </div>
      </div>

      <!-- Step 5: 调整预览 -->
      <div v-show="currentStep === 5" class="step-content">
        <div class="preview-section">
          <div class="preview-header">
            <h4>试卷预览</h4>
            <div class="preview-actions" v-if="generatedQuestions.length > 0">
              <el-button @click="reorderQuestions">
                <Icon icon="mdi:swap-vertical" />
                调整顺序
              </el-button>
              <el-button @click="exportWord">
                <Icon icon="mdi:download" />
                导出Word
              </el-button>
              <el-button @click="exportPdf">
                <Icon icon="mdi:download" />
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
                  <Icon icon="mdi:drag-vertical" class="drag-handle" />
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
                    <Icon icon="mdi:refresh" />
                    替换
                  </el-button>
                  <el-button link size="small" @click="removeQuestion(index)">
                    <Icon icon="mdi:delete" />
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
import { useAutoPaper } from '@/composables/useAutoPaper'
import Icon from '@/components/common/Icon.vue'

const {
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
  saveDraft,
  publishPaper,
  exportWord,
  exportPdf,
  replaceQuestion,
  // Outline
  outlineSections,
  outlineLoading,
  outlineMessage,
  generateOutline,
  regenerateOutline,
  confirmOutline,
  getKnowledgePointName,
  // Helpers
  getTypeName,
  getDifficultyLevel,
  getDifficultyNameByLevel,
  getDifficultyType,
  handleDragStart,
  handleDrop,
  reorderQuestions,
  // Templates
  templates,
  templatesLoading,
  loadTemplates,
  saveAsTemplate,
  DEFAULT_TEMPLATES
} = useAutoPaper()

// Initialize
onMounted(async () => {
  await loadExamCategories()
  await loadTemplates()
})
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
  /* 评估 P2-14：原紫色渐变违反 DESIGN.md，改为规范主色浅底 */
  background: #E8F3FF;
  border-radius: 8px;
  margin-bottom: 20px;
  color: #0D47A1;
}

.weight-summary span {
  font-size: 15px;
  font-weight: 500;
}

.weight-summary .el-button {
  background: #165DFF;
  border: 1px solid #165DFF;
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
