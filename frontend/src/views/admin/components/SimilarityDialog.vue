<template>
  <el-dialog
    v-model="similarityDialogVisible"
    title="题目相似度检测"
    width="1000px"
    :close-on-click-modal="false"
  >
    <div v-if="similarityData">
      <div class="similarity-summary">
        <span>检测试卷：{{ previewPaperData?.title }}</span>
        <span>检测题目数：{{ similarityData.total_checked }} 题</span>
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
            {{ getQuestionTypeName(row.question_type) }}
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
      <p>点击下方按钮开始检测试卷中的相似题目</p>
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
</template>

<script setup>
import {
  similarityDialogVisible,
  similarityLoading,
  similarityData,
  similarityThreshold,
  previewPaperData,
  getQuestionTypeName,
  getSimilarityType,
  getSimilarityLevel,
  runSimilarityCheck
} from '@/composables/usePaperManagement'
</script>

<style scoped>
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
