<template>
  <!-- 版本历史弹窗 -->
  <el-dialog
    v-model="versionDialogVisible"
    title="版本历史"
    width="800px"
    :close-on-click-modal="false"
  >
    <div v-if="currentVersionPaperId">
      <el-table :data="versionList" stripe style="width: 100%">
        <el-table-column prop="version_number" label="版本号" width="100" />
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="change_log" label="变更说明" min-width="200" show-overflow-tooltip />
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link size="small" @click="showVersionDetail(row)">详情</el-button>
            <el-button link size="small" type="warning" @click="restoreVersion(row)">回滚</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination-container" style="margin-top: 16px; justify-content: flex-end;">
        <el-pagination
          v-model:current-page="versionPagination.page"
          v-model:page-size="versionPagination.pageSize"
          :total="versionPagination.total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @size-change="handleVersionPageChange"
          @current-change="handleVersionPageChange"
        />
      </div>
    </div>
    <template #footer>
      <el-button @click="versionDialogVisible = false">关闭</el-button>
    </template>
  </el-dialog>

  <!-- 版本详情弹窗 -->
  <el-dialog
    v-model="versionDetailDialogVisible"
    :title="`版本 ${versionDetail?.version_number || ''} 详情`"
    width="800px"
    :close-on-click-modal="false"
  >
    <div v-if="versionDetail" class="version-detail">
      <div class="version-info">
        <p><strong>标题：</strong>{{ versionDetail.title }}</p>
        <p v-if="versionDetail.description"><strong>描述：</strong>{{ versionDetail.description }}</p>
        <p><strong>变更日志：</strong>{{ versionDetail.change_log || '无' }}</p>
        <p><strong>创建时间：</strong>{{ formatDate(versionDetail.created_at) }}</p>
      </div>

      <div class="version-questions" v-if="versionDetail.questions_snapshot && versionDetail.questions_snapshot.length > 0">
        <h4>题目列表（{{ versionDetail.questions_snapshot.length }}题）</h4>
        <el-table :data="versionDetail.questions_snapshot" stripe style="width: 100%">
          <el-table-column prop="order" label="序号" width="80" />
          <el-table-column prop="question_id" label="题目ID" width="120" />
          <el-table-column prop="score" label="分值" width="100" />
        </el-table>
      </div>
      <el-alert v-else type="info" :closable="false">该版本无题目数据</el-alert>
    </div>
    <template #footer>
      <el-button @click="versionDetailDialogVisible = false">关闭</el-button>
      <el-button type="warning" @click="handleRestoreFromDetail">回滚到此版本</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import {
  versionDialogVisible,
  versionDetailDialogVisible,
  versionList,
  versionDetail,
  currentVersionPaperId,
  versionPagination,
  formatDate,
  showVersionDetail,
  restoreVersion,
  handleVersionPageChange
} from '@/composables/usePaperManagement'

const handleRestoreFromDetail = async () => {
  if (versionDetail.value) {
    await restoreVersion(versionDetail.value)
  }
}
</script>

<style scoped>
.version-detail {
  padding: 0;
}

.version-info {
  margin-bottom: 20px;
}

.version-info p {
  margin: 8px 0;
  color: #606266;
  line-height: 1.6;
}

.version-questions h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: #303133;
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
}
</style>
