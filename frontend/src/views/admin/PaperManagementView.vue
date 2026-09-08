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
              <el-dropdown-item command="delete">批量归档</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <!-- 试卷列表表格 -->
    <div class="table-container">
      <el-empty v-if="!loading && paperList.length === 0" description="暂无试卷数据" :image-size="80" />
      <el-table
        v-else
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
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <div class="operation-buttons">
              <el-button link size="small" @click="previewPaper(row)">预览</el-button>
              <el-button link size="small" @click="editPaper(row)">编辑</el-button>
              <el-button link size="small" v-if="row.status === 0" @click="publishPaper(row)">发布</el-button>
              <el-button link size="small" v-if="row.status === 1" @click="archivePaper(row)">归档</el-button>
              <el-dropdown @command="(cmd) => handleRowCommand(cmd, row)">
                <el-button link size="small">更多<el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="analyze">分析</el-dropdown-item>
                    <el-dropdown-item command="version">版本历史</el-dropdown-item>
                    <el-dropdown-item command="similarity">查重</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
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

    <!-- 子组件 -->
    <PaperDialog v-if="paperDialogVisible" />
    <PreviewDialog v-if="previewDialogVisible" />
    <AnalysisDialog v-if="analysisDialogVisible" />
    <VersionHistory v-if="versionDialogVisible" />
    <SimilarityDialog v-if="similarityDialogVisible" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Search, ArrowDown } from '@element-plus/icons-vue'
import {
  loading,
  loadingCategories,
  loadingSubjects,
  paperList,
  selectedRows,
  searchKeyword,
  pagination,
  filterForm,
  categoryOptions,
  filteredSubjectOptions,
  formatDate,
  getSubjectName,
  getStatusName,
  getStatusTagType,
  fetchCategories,
  fetchSubjects,
  fetchPaperList,
  handleSearch,
  handleSizeChange,
  handlePageChange,
  handleCategoryChange,
  handleSelectionChange,
  openPaperDialog,
  editPaper,
  previewPaper,
  publishPaper,
  archivePaper,
  deletePaper,
  handleRowCommand,
  handleBatchCommand
} from '@/composables/usePaperManagement'
import PaperDialog from './components/PaperDialog.vue'
import PreviewDialog from './components/PreviewDialog.vue'
import AnalysisDialog from './components/AnalysisDialog.vue'
import VersionHistory from './components/VersionHistory.vue'
import SimilarityDialog from './components/SimilarityDialog.vue'

const tableRef = ref(null)

onMounted(() => {
  Promise.all([fetchCategories(), fetchSubjects(), fetchPaperList()])
})
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
</style>
