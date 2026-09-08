<template>
  <el-dialog
    v-model="analysisDialogVisible"
    title="试卷分析报告"
    width="900px"
    :close-on-click-modal="false"
  >
    <div v-if="analysisData" class="analysis-container">
      <!-- 基本信息 -->
      <div class="analysis-section">
        <h4>基本信息</h4>
        <div class="info-cards">
          <el-card class="info-card">
            <div class="info-value">{{ analysisData.total_questions }}</div>
            <div class="info-label">题目数量</div>
          </el-card>
          <el-card class="info-card">
            <div class="info-value">{{ analysisData.total_score }}</div>
            <div class="info-label">总分</div>
          </el-card>
          <el-card class="info-card">
            <div class="info-value">{{ analysisData.estimated_time }}分钟</div>
            <div class="info-label">预估完成时间</div>
          </el-card>
          <el-card class="info-card">
            <div class="info-value" :class="getCoverageClass(analysisData.coverage_rate)">
              {{ analysisData.coverage_rate }}%
            </div>
            <div class="info-label">知识点覆盖率</div>
          </el-card>
        </div>
      </div>

      <!-- 题型统计 -->
      <div class="analysis-section">
        <h4>题型统计</h4>
        <el-table :data="getTypeStatsTable(analysisData.type_stats)" stripe style="width: 100%">
          <el-table-column prop="type" label="题型" width="120">
            <template #default="{ row }">{{ row.type }}</template>
          </el-table-column>
          <el-table-column prop="count" label="题数" width="80" />
          <el-table-column prop="score" label="分值" width="80" />
          <el-table-column label="占比">
            <template #default="{ row }">
              <el-progress
                :percentage="row.percentage"
                :stroke-width="12"
                :color="getTypeColor(row.type)"
              />
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 难度分布 -->
      <div class="analysis-section">
        <h4>难度分布</h4>
        <div class="difficulty-bars">
          <div class="difficulty-item">
            <span class="difficulty-label">简单</span>
            <div class="difficulty-bar-wrapper">
              <el-progress
                :percentage="analysisData.difficulty_distribution.easy"
                :stroke-width="16"
                color="#67c23a"
                :show-text="true"
              />
            </div>
            <span class="difficulty-count">{{ analysisData.difficulty_stats.easy }}题</span>
          </div>
          <div class="difficulty-item">
            <span class="difficulty-label">中等</span>
            <div class="difficulty-bar-wrapper">
              <el-progress
                :percentage="analysisData.difficulty_distribution.medium"
                :stroke-width="16"
                color="#e6a23c"
                :show-text="true"
              />
            </div>
            <span class="difficulty-count">{{ analysisData.difficulty_stats.medium }}题</span>
          </div>
          <div class="difficulty-item">
            <span class="difficulty-label">困难</span>
            <div class="difficulty-bar-wrapper">
              <el-progress
                :percentage="analysisData.difficulty_distribution.hard"
                :stroke-width="16"
                color="#f56c6c"
                :show-text="true"
              />
            </div>
            <span class="difficulty-count">{{ analysisData.difficulty_stats.hard }}题</span>
          </div>
        </div>
      </div>

      <!-- 知识点覆盖 -->
      <div class="analysis-section">
        <h4>知识点覆盖情况</h4>
        <div class="knowledge-coverage">
          <div class="coverage-summary">
            <span>已配置知识点：{{ analysisData.selected_knowledge_points?.length || 0 }}个</span>
            <span>实际覆盖：{{ analysisData.covered_knowledge_points?.length || 0 }}个</span>
            <span>覆盖率：{{ analysisData.coverage_rate }}%</span>
          </div>
          <div v-if="analysisData.knowledge_point_stats && Object.keys(analysisData.knowledge_point_stats).length > 0" class="knowledge-table">
            <el-table :data="getKnowledgePointStatsTable(analysisData.knowledge_point_stats)" stripe style="width: 100%">
              <el-table-column prop="kp_id" label="知识点ID" width="100" />
              <el-table-column prop="count" label="题目数" width="100" />
              <el-table-column prop="score" label="总分" width="100" />
              <el-table-column label="覆盖状态" width="120">
                <template #default="{ row }">
                  <el-tag :type="row.covered ? 'success' : 'danger'" size="small">
                    {{ row.covered ? '已覆盖' : '未覆盖' }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
          </div>
          <el-alert v-else type="info" :closable="false" style="margin-top: 12px;">
            该试卷未配置知识点覆盖范围，或题目未关联知识点
          </el-alert>
        </div>
      </div>

      <!-- 高级分析指标 -->
      <div class="analysis-section">
        <h4>高级分析</h4>
        <div class="advanced-metrics">
          <div class="metric-card">
            <div class="metric-label">区分度</div>
            <div class="metric-value">
              <el-tag :type="getDiscriminationType(analysisData.discrimination_index)" size="large">
                {{ analysisData.discrimination_index ?? '-' }}
              </el-tag>
            </div>
            <div class="metric-desc">越高越能区分学生水平</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">预估通过率</div>
            <div class="metric-value">
              <el-progress
                :percentage="analysisData.predicted_pass_rate || 0"
                :stroke-width="18"
                :color="getPassRateColor(analysisData.predicted_pass_rate)"
              />
            </div>
            <div class="metric-desc">基于难度分布估算</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">综合质量分</div>
            <div class="metric-value">
              <el-progress
                :percentage="analysisData.quality_score || 0"
                :stroke-width="18"
                :color="getQualityScoreColor(analysisData.quality_score)"
              />
            </div>
            <div class="metric-desc">覆盖率、难度、区分度综合评估</div>
          </div>
        </div>

        <!-- 知识点掌握度 -->
        <div v-if="analysisData.knowledge_mastery && analysisData.knowledge_mastery.length > 0" class="knowledge-mastery">
          <h5 style="margin-top: 16px;">知识点掌握度</h5>
          <el-table :data="analysisData.knowledge_mastery" stripe style="width: 100%">
            <el-table-column prop="knowledge_point_id" label="知识点ID" width="120" />
            <el-table-column prop="count" label="题目数" width="100" />
            <el-table-column prop="score" label="总分" width="100" />
            <el-table-column prop="avg_difficulty" label="平均难度" width="120">
              <template #default="{ row }">
                <el-rate
                  :model-value="row.avg_difficulty"
                  disabled
                  :max="5"
                  :colors="['#67c23a', '#e6a23c', '#f56c6c']"
                />
              </template>
            </el-table-column>
            <el-table-column prop="mastery_level" label="掌握度" width="120">
              <template #default="{ row }">
                <el-tag :type="getMasteryType(row.mastery_level)" size="small">
                  {{ getMasteryLabel(row.mastery_level) }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <!-- 分析建议 -->
      <div class="analysis-section" v-if="analysisSuggestions.length > 0">
        <h4>优化建议</h4>
        <div class="suggestions">
          <div v-for="(suggestion, index) in analysisSuggestions" :key="index" class="suggestion-item">
            <el-icon class="suggestion-icon"><Warning /></el-icon>
            <span>{{ suggestion }}</span>
          </div>
        </div>
      </div>
    </div>
    <template #footer>
      <el-button @click="analysisDialogVisible = false">关闭</el-button>
      <el-button type="primary" @click="exportWord">导出Word</el-button>
      <el-button type="primary" @click="exportPdf">导出PDF</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { Warning } from '@element-plus/icons-vue'
import {
  analysisDialogVisible,
  analysisData,
  analysisSuggestions,
  getTypeStatsTable,
  getTypeColor,
  getCoverageClass,
  getKnowledgePointStatsTable,
  getDiscriminationType,
  getPassRateColor,
  getQualityScoreColor,
  getMasteryType,
  getMasteryLabel,
  exportWord,
  exportPdf
} from '@/composables/usePaperManagement'
</script>

<style scoped>
.analysis-container {
  max-height: 65vh;
  overflow-y: auto;
}

.analysis-section {
  margin-bottom: 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid #ebeef5;
}

.analysis-section:last-child {
  border-bottom: none;
}

.analysis-section h4 {
  margin: 0 0 16px 0;
  font-size: 16px;
  color: #303133;
  font-weight: 600;
}

.info-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.info-card {
  text-align: center;
  padding: 16px;
}

.info-value {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 6px;
}

.info-label {
  font-size: 13px;
  color: #909399;
}

.coverage-good {
  color: #67c23a;
}

.coverage-medium {
  color: #e6a23c;
}

.coverage-poor {
  color: #f56c6c;
}

.difficulty-bars {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.difficulty-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.difficulty-label {
  width: 60px;
  font-size: 14px;
  color: #606266;
}

.difficulty-bar-wrapper {
  flex: 1;
}

.difficulty-count {
  width: 80px;
  text-align: right;
  font-size: 14px;
  color: #606266;
}

.coverage-summary {
  display: flex;
  gap: 24px;
  margin-bottom: 12px;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 6px;
  font-size: 14px;
  color: #606266;
}

.knowledge-table {
  margin-top: 12px;
}

.suggestions {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.suggestion-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px;
  background: #fdf6ec;
  border-left: 4px solid #e6a23c;
  border-radius: 4px;
  font-size: 14px;
  color: #606266;
  line-height: 1.6;
}

.suggestion-icon {
  color: #e6a23c;
  margin-top: 2px;
}

.advanced-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

.metric-card {
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
  text-align: center;
}

.metric-label {
  font-size: 14px;
  color: #606266;
  margin-bottom: 12px;
}

.metric-value {
  margin-bottom: 8px;
}

.metric-desc {
  font-size: 12px;
  color: #909399;
}

.knowledge-mastery {
  margin-top: 16px;
}
</style>
