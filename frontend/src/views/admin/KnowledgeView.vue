<template>
  <div class="knowledge-view">
    <!-- 顶部操作栏 -->
    <div class="operation-bar">
      <div class="left-operations">
        <el-button type="primary" @click="openCreateDialog">新建知识点</el-button>
        <el-button @click="handleImport">导入知识点</el-button>
        <el-button @click="handleBatchImport">批量文档导入</el-button>
        <el-button @click="handleExport">导出知识点</el-button>
      </div>
      <div class="right-operations">
        <el-button circle @click="fetchKnowledgeTree">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>
    </div>

    <!-- 主体内容区 -->
    <div class="content-area">
      <!-- 左侧知识树 -->
      <div class="tree-panel">
        <div class="panel-header">
          <span class="panel-title">知识体系</span>
        </div>
        <div class="tree-search-bar">
          <el-input
            v-model="treeSearchKeyword"
            placeholder="搜索知识点..."
            size="small"
            clearable
            class="tree-search"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>
        <div class="tree-container">
          <div class="tree-scroll">
            <el-tree
              ref="treeRef"
              :data="filteredTreeData"
              :props="treeProps"
              node-key="id"
              :expand-on-click-node="false"
              :default-expanded-keys="defaultExpandedKeys"
              :highlight-current="true"
              @node-click="handleNodeClick"
              @node-contextmenu="handleNodeContextMenu"
              draggable
              :allow-drop="allowDrop"
              :allow-drag="allowDrag"
              @node-drag-start="handleDragStart"
              @node-drag-end="handleDragEnd"
            >
            <template #default="{ node, data }">
              <span class="tree-node" :class="'node-type-' + (data.node_type || 'knowledge')">
                <span class="node-icon">
                  <el-icon v-if="data.node_type === 'category'"><Folder /></el-icon>
                  <el-icon v-else-if="data.node_type === 'exam_type'"><Document /></el-icon>
                  <el-icon v-else-if="data.children?.length"><Folder /></el-icon>
                  <el-icon v-else><Document /></el-icon>
                </span>
                <span class="node-label">{{ data.name }}</span>
                <el-tag
                  v-if="data.node_type === 'category'"
                  size="small"
                  type="warning"
                  class="node-type-tag"
                >种类</el-tag>
                <el-tag
                  v-if="data.node_type === 'exam_type'"
                  size="small"
                  type="success"
                  class="node-type-tag"
                >科目</el-tag>
                <span class="node-count" v-if="data.questionCount">({{ data.questionCount }})</span>
              </span>
            </template>
          </el-tree>
          </div>
        </div>
      </div>

      <!-- 右侧详情面板 -->
      <div class="detail-panel">
        <!-- 空白状态 -->
        <div class="empty-state" v-if="!selectedKnowledge">
          <el-empty description="请从左侧选择一个知识点查看详情">
            <el-button type="primary" @click="openCreateDialog">新建知识点</el-button>
          </el-empty>
        </div>

        <!-- 分类/科目信息 -->
        <div class="detail-content" v-else-if="selectedKnowledge.node_type === 'category'">
          <div class="detail-header">
            <h3 class="detail-title">
              <el-icon><Folder /></el-icon>
              {{ selectedKnowledge.name }}
            </h3>
          </div>
          <div class="detail-body">
            <div class="detail-item">
              <span class="detail-label">类型</span>
              <span class="detail-value"><el-tag type="warning">考试种类</el-tag></span>
            </div>
            <div class="detail-item">
              <span class="detail-label">下属科目</span>
              <span class="detail-value highlight">{{ selectedKnowledge.children?.length || 0 }} 个</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">知识点总数</span>
              <span class="detail-value highlight">{{ countDescendantKnowledge(selectedKnowledge) }}</span>
            </div>
          </div>
        </div>

        <div class="detail-content" v-else-if="selectedKnowledge.node_type === 'exam_type'">
          <div class="detail-header">
            <h3 class="detail-title">
              <el-icon><Document /></el-icon>
              {{ selectedKnowledge.name }}
            </h3>
          </div>
          <div class="detail-body">
            <div class="detail-item">
              <span class="detail-label">类型</span>
              <span class="detail-value"><el-tag type="success">考试科目</el-tag></span>
            </div>
            <div class="detail-item">
              <span class="detail-label">知识点数量</span>
              <span class="detail-value highlight">{{ selectedKnowledge.children?.length || 0 }}</span>
            </div>
          </div>
        </div>

        <!-- 知识点详情 -->
        <div class="detail-content" v-else>
          <div class="detail-header">
            <h3 class="detail-title">{{ selectedKnowledge.name }}</h3>
            <div class="detail-actions">
              <el-button type="primary" @click="openEditDialog">编辑</el-button>
              <el-button type="danger" @click="deleteKnowledge">删除</el-button>
            </div>
          </div>

          <div class="detail-body">
            <div class="detail-item">
              <span class="detail-label">上级知识点</span>
              <span class="detail-value">{{ selectedKnowledge.parentName || '顶级知识点' }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">所属种类</span>
              <span class="detail-value">{{ selectedKnowledge.categoryName || '-' }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">所属科目</span>
              <span class="detail-value">{{ selectedKnowledge.examTypeName || '-' }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">题目数量</span>
              <span class="detail-value highlight">{{ selectedKnowledge.questionCount || 0 }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">创建时间</span>
              <span class="detail-value">{{ formatDate(selectedKnowledge.created_at) }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">更新时间</span>
              <span class="detail-value">{{ formatDate(selectedKnowledge.updated_at) }}</span>
            </div>
            <div class="detail-item" v-if="selectedKnowledge.description">
              <span class="detail-label">知识点描述</span>
              <span class="detail-value description">{{ selectedKnowledge.description }}</span>
            </div>
          </div>

          <!-- 相关题目快捷链接 -->
          <div class="related-questions">
            <div class="section-title">相关题目</div>
            <div class="question-links" v-if="relatedQuestions.length">
              <el-tag
                v-for="q in relatedQuestions.slice(0, 10)"
                :key="q.id"
                class="question-link"
                @click="viewQuestion(q)"
              >
                {{ q.id }} - {{ truncateContent(q.content) }}
              </el-tag>
              <el-button
                v-if="relatedQuestions.length > 10"
                type="primary"
                link
                @click="viewAllQuestions"
              >
                查看全部 {{ relatedQuestions.length }} 道题目
              </el-button>
            </div>
            <div class="no-questions" v-else>
              <el-empty description="暂无相关题目" :image-size="60" />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 统计概览卡片 -->
    <div class="stats-cards">
      <el-card class="stat-card">
        <el-statistic title="总知识点数" :value="totalKnowledgeCount" />
      </el-card>
      <el-card class="stat-card">
        <el-statistic title="考试种类" :value="categoryCount" />
      </el-card>
      <el-card class="stat-card">
        <el-statistic title="考试科目" :value="examTypeCount" />
      </el-card>
    </div>

    <!-- 右键菜单 -->
    <div
      v-show="contextMenuVisible"
      class="context-menu"
      :style="{ left: contextMenuX + 'px', top: contextMenuY + 'px' }"
    >
      <div class="context-menu-item" @click="handleAddChild" v-if="contextMenuNode && !contextMenuNode.node_type">
        <el-icon><Plus /></el-icon>
        <span>新增子节点</span>
      </div>
      <div class="context-menu-item" @click="handleAddKnowledgeUnderExamType" v-if="contextMenuNode && contextMenuNode.node_type === 'exam_type'">
        <el-icon><Plus /></el-icon>
        <span>新增知识点</span>
      </div>
      <div class="context-menu-item" @click="handleRename" v-if="contextMenuNode && !contextMenuNode.node_type">
        <el-icon><Edit /></el-icon>
        <span>重命名</span>
      </div>
      <div class="context-menu-item danger" @click="handleDelete" v-if="contextMenuNode && !contextMenuNode.node_type">
        <el-icon><Delete /></el-icon>
        <span>删除</span>
      </div>
    </div>

    <!-- 新建/编辑知识点弹窗 -->
    <el-dialog
      v-if="dialogVisible"
      v-model="dialogVisible"
      :title="isEdit ? '编辑知识点' : '新建知识点'"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form :model="knowledgeForm" :rules="formRules" ref="knowledgeFormRef" label-width="100px">
        <el-form-item label="知识点名称" prop="name">
          <el-input v-model="knowledgeForm.name" placeholder="请输入知识点名称" />
        </el-form-item>
        <el-form-item label="上级知识点">
          <el-tree-select
            v-model="knowledgeForm.parentId"
            :data="knowledgeOnlyTreeData"
            :props="treeProps"
            placeholder="请选择上级知识点（不选则为顶级）"
            clearable
            check-strictly
            :render-after-expand="false"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="所属种类">
          <el-select v-model="knowledgeForm.categoryId" placeholder="请选择考试种类" clearable style="width: 100%" @change="handleFormCategoryChange">
            <el-option
              v-for="cat in examCategoryOptions"
              :key="cat.id"
              :label="cat.name"
              :value="cat.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="所属科目">
          <el-select v-model="knowledgeForm.examTypeId" placeholder="请选择考试科目" clearable style="width: 100%" :disabled="!knowledgeForm.categoryId">
            <el-option
              v-for="et in filteredFormExamTypeOptions"
              :key="et.id"
              :label="et.name"
              :value="et.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="排序权重">
          <el-input-number v-model="knowledgeForm.sortOrder" :min="0" :max="9999" />
        </el-form-item>
        <el-form-item label="知识点描述">
          <el-input
            v-model="knowledgeForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入知识点描述"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitLoading">确定</el-button>
      </template>
    </el-dialog>

    <!-- 导入知识点弹窗 -->
    <el-dialog v-if="importDialogVisible" v-model="importDialogVisible" title="导入知识点" width="600px" :close-on-click-modal="false">
      <!-- 导入模式选择 -->
      <div class="import-mode-tabs">
        <el-radio-group v-model="importMode">
          <el-radio-button value="file">文件导入</el-radio-button>
          <el-radio-button value="ai">AI 智能分析</el-radio-button>
        </el-radio-group>
      </div>

      <!-- 文件导入模式 -->
      <div v-if="importMode === 'file'" class="import-file-mode">
        <el-upload
          ref="uploadRef"
          drag
          :limit="1"
          accept=".json,.xlsx"
          :auto-upload="false"
          :on-change="handleFileChange"
        >
          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          <div class="el-upload__text">将文件拖到此处，或<em>点击上传</em></div>
          <template #tip>
            <div class="el-upload__tip">支持 JSON 和 Excel 格式</div>
          </template>
        </el-upload>
      </div>

      <!-- AI 智能分析模式 -->
      <div v-if="importMode === 'ai'" class="import-ai-mode">
        <el-alert type="info" :closable="false" class="ai-intro">
          <template #title>
            <div>智能导入功能</div>
          </template>
          <div>上传文档后系统自动解析结构提取知识点（毫秒级），也可使用 AI 深度分析获取更精炼的知识归纳</div>
        </el-alert>

        <el-form :model="aiImportForm" label-width="100px" class="ai-form">
          <el-form-item label="选择文件">
            <el-upload
              ref="aiUploadRef"
              drag
              :limit="1"
              accept=".pdf,.docx,.md,.txt,.markdown"
              :auto-upload="false"
              :on-change="handleAIFileChange"
              :disabled="aiAnalyzing"
            >
              <el-icon class="el-icon--upload"><upload-filled /></el-icon>
              <div class="el-upload__text">点击上传或拖拽文件</div>
              <template #tip>
                <div class="el-upload__tip">支持 PDF、Word(.docx)、Markdown(.md)、TXT 格式</div>
              </template>
            </el-upload>
          </el-form-item>
          <el-form-item label="父级知识点">
            <el-tree-select
              v-model="aiImportForm.parentId"
              :data="knowledgeOnlyTreeData"
              :props="treeProps"
              placeholder="选择父级知识点（不选则为顶级）"
              clearable
              check-strictly
              :render-after-expand="false"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="所属种类">
            <el-select v-model="aiImportForm.categoryId" placeholder="请选择考试种类" clearable style="width: 100%">
              <el-option
                v-for="cat in examCategoryOptions"
                :key="cat.id"
                :label="cat.name"
                :value="cat.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="所属科目">
            <el-select v-model="aiImportForm.examTypeId" placeholder="请选择考试科目" clearable style="width: 100%" :disabled="!aiImportForm.categoryId">
              <el-option
                v-for="et in filteredAIExamTypeOptions"
                :key="et.id"
                :label="et.name"
                :value="et.id"
              />
            </el-select>
          </el-form-item>
        </el-form>

        <!-- 解析状态 -->
        <div v-if="aiAnalyzing" class="ai-analyzing">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>AI 正在深度归纳知识点，请稍候...</span>
        </div>

        <!-- 解析结果预览 -->
        <div v-if="aiResult && !aiAnalyzing" class="ai-result">
          <el-divider>
            <span v-if="aiResult.method === 'rule-based'">规则解析结果</span>
            <span v-else>AI 深度分析结果</span>
          </el-divider>
          <div class="result-info">
            <span>文件名：{{ aiResult.document_name }}</span>
            <span>提取知识点：{{ aiResult.total_points }} 个</span>
            <el-tag v-if="aiResult.method === 'rule-based'" type="info" size="small">规则解析</el-tag>
            <el-tag v-else type="success" size="small">AI分析</el-tag>
          </div>
          <div class="knowledge-tree-preview">
            <el-tree
              :data="aiResult.knowledge_points"
              :props="{ label: 'name', children: 'children' }"
              default-expand-all
            >
              <template #default="{ node, data }">
                <span class="tree-node">
                  <span>{{ node.label }}</span>
                  <span v-if="data.description" class="node-desc">{{ data.description }}</span>
                </span>
              </template>
            </el-tree>
          </div>
        </div>
      </div>

      <template #footer>
        <el-button @click="closeImportDialog">取消</el-button>
        <el-button v-if="importMode === 'file'" type="primary" @click="confirmImport">导入</el-button>
        <!-- AI模式：规则解析后自动触发AI归纳，此处仅保留"重新AI分析"入口 -->
        <el-button
          v-if="importMode === 'ai' && aiResult && !aiAnalyzing"
          :loading="aiAnalyzing"
          @click="startAIAnalysis"
        >
          重新 AI 归纳
        </el-button>
        <!-- AI模式：AI归纳完成后显示确认导入按钮 -->
        <el-button
          v-if="importMode === 'ai' && aiResult && !aiAnalyzing"
          type="success"
          @click="confirmAIImport"
        >
          确认导入 ({{ aiResult.total_points }} 个)
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Search, Refresh, Folder, Document, Plus, Edit, Delete, UploadFilled, Loading
} from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { useKnowledge } from '@/composables/useKnowledge'
import { watch } from 'vue'
import { useDebouncedRef } from '@/utils/debounce'

const router = useRouter()

const {
  // Tree state
  treeRef,
  knowledgeTreeData,
  filteredTreeData,
  treeSearchKeyword,
  selectedKnowledge,
  relatedQuestions,
  // Dialog state
  dialogVisible,
  importDialogVisible,
  isEdit,
  submitLoading,
  // Context menu
  contextMenuVisible,
  contextMenuX,
  contextMenuY,
  contextMenuNode,
  // Import state
  importMode,
  uploadRef,
  aiUploadRef,
  selectedFile,
  aiSelectedFile,
  aiAnalyzing,
  aiResult,
  aiImportForm,
  // Tree config
  treeProps,
  // Form
  knowledgeForm,
  formRules,
  // Options
  examTypeOptions,
  examCategoryOptions,
  // Stats
  totalKnowledgeCount,
  categoryCount,
  examTypeCount,
  // Computed
  knowledgeOnlyTreeData,
  filteredFormExamTypeOptions,
  filteredAIExamTypeOptions,
  defaultExpandedKeys,
  // Actions
  handleFormCategoryChange,
  fetchExamTypesAndCourses,
  allowDrop,
  allowDrag,
  fetchKnowledgeTree,
  calculateStats,
  handleTreeSearch,
  handleNodeClick,
  handleNodeContextMenu,
  hideContextMenu,
  handleDragStart,
  handleDragEnd,
  openCreateDialog,
  handleAddKnowledgeUnderExamType,
  openEditDialog,
  resetForm,
  submitForm,
  deleteKnowledge,
  handleAddChild,
  handleRename,
  handleDelete,
  handleImport,
  resetImportState,
  closeImportDialog,
  handleFileChange,
  handleAIFileChange,
  autoRuleAnalyze,
  startAIAnalysis,
  confirmAIImport,
  confirmImport,
  handleExport,
  handleBatchImport,
  viewQuestion,
  viewAllQuestions,
  // Utilities
  formatDate,
  truncateContent
} = useKnowledge()

// Debounced tree search — avoid filtering on every keystroke
const debouncedTreeSearch = useDebouncedRef(treeSearchKeyword, 300)
watch(debouncedTreeSearch, () => {
  handleTreeSearch()
})
</script>


<style scoped>
.knowledge-view {
  padding: 12px;
  background-color: #f5f5f5;
  height: calc(100vh - 60px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.operation-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  padding: 10px 16px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  flex-shrink: 0;
}

.left-operations {
  display: flex;
  gap: 12px;
}

.content-area {
  display: flex;
  gap: 12px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* 左侧知识树 */
.tree-panel {
  width: 380px;
  flex-shrink: 0;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  padding: 10px 12px;
  border-bottom: 1px solid #ebeef5;
}

.panel-title {
  font-weight: bold;
  font-size: 16px;
  color: #303133;
}

.tree-search-bar {
  padding: 8px 12px;
  border-bottom: 1px solid #ebeef5;
}

.tree-search {
  width: 100%;
}

.tree-container {
  flex: 1;
  padding: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

/* 整体树结构横向+纵向滚动 */
.tree-scroll {
  overflow-x: auto;
  overflow-y: auto;
  flex: 1;
  min-height: 0;
  padding: 8px;
  box-sizing: border-box;
}

/* el-tree 使用 inline-block 使其宽度随内容撑开，触发横向滚动 */
:deep(.el-tree) {
  min-width: 100%;
  display: inline-block !important;
}

/* 节点内容不换行，长名称才会撑宽树 */
:deep(.el-tree-node__content) {
  white-space: nowrap !important;
  transition: opacity 0.3s;
}

:deep(.el-tree__empty-text) {
  width: auto;
}

.tree-node {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}

/* 不同层级节点样式 */
.node-type-category > .node-icon {
  color: #e6a23c;
  font-size: 18px;
}

.node-type-category > .node-label {
  font-weight: 600;
  font-size: 14px;
}

.node-type-exam_type > .node-icon {
  color: #67c23a;
  font-size: 16px;
}

.node-type-exam_type > .node-label {
  font-weight: 500;
  color: #606266;
}

.node-icon {
  color: #409eff;
  font-size: 16px;
}

.node-label {
  flex: 1;
}

.node-type-tag {
  flex-shrink: 0;
  font-size: 10px;
  padding: 0 4px;
  height: 18px;
  line-height: 18px;
}

.node-count {
  color: #909399;
  font-size: 12px;
}


/* 拖拽样式 */

:deep(.el-tree-node.is-dragging .el-tree-node__content) {
  opacity: 0.5;
  background-color: #ecf5ff;
}

:deep(.el-tree-node.is-drop-inner .el-tree-node__content) {
  background-color: #f0f9ff;
  border: 1px dashed #409eff;
}

/* 右侧详情面板 */
.detail-panel {
  flex: 1;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  overflow: auto;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 200px;
}

.detail-content {
  padding: 16px;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid #ebeef5;
}

.detail-title {
  margin: 0;
  font-size: 20px;
  color: #303133;
  display: flex;
  align-items: center;
  gap: 8px;
}

.detail-actions {
  display: flex;
  gap: 8px;
}

.detail-body {
  margin-bottom: 12px;
}

.detail-item {
  display: flex;
  padding: 8px 0;
  border-bottom: 1px solid #f5f5f5;
}

.detail-item:last-child {
  border-bottom: none;
}

.detail-label {
  width: 120px;
  color: #909399;
  flex-shrink: 0;
}

.detail-value {
  flex: 1;
  color: #303133;
}

.detail-value.highlight {
  font-size: 24px;
  font-weight: bold;
  color: #409eff;
}

.detail-value.description {
  line-height: 1.6;
  color: #606266;
}

.exam-type-tag {
  margin-right: 8px;
  border-radius: 12px;
}

/* 相关题目 */
.related-questions {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid #ebeef5;
}

.section-title {
  font-weight: bold;
  font-size: 14px;
  color: #303133;
  margin-bottom: 16px;
}

.question-links {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.question-link {
  cursor: pointer;
  border-radius: 12px;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.question-link:hover {
  opacity: 0.8;
}

.no-questions {
  padding: 20px;
}

/* 统计卡片 */
.stats-cards {
  display: flex;
  gap: 12px;
  margin-top: 10px;
  flex-shrink: 0;
}

.stat-card {
  flex: 1;
}

/* 右键菜单 */
.context-menu {
  position: fixed;
  background: white;
  border-radius: 4px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  padding: 4px 0;
  z-index: 9999;
}

.context-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  cursor: pointer;
  font-size: 14px;
  color: #606266;
  transition: background-color 0.2s;
}

.context-menu-item:hover {
  background-color: #ecf5ff;
}

.context-menu-item.danger {
  color: #f56c6c;
}

.context-menu-item.danger:hover {
  background-color: #fef0f0;
}

/* 导入弹窗 */
.import-mode-tabs {
  margin-bottom: 20px;
  text-align: center;
}

.import-file-mode,
.import-ai-mode {
  min-height: 200px;
}

.ai-intro {
  margin-bottom: 20px;
}

.ai-form {
  margin-top: 20px;
}

.ai-analyzing {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px;
  color: #606266;
}

.ai-analyzing .el-icon {
  font-size: 24px;
  color: #165DFF;
}

.ai-result {
  margin-top: 20px;
  max-height: 400px;
  overflow-y: auto;
}

.result-info {
  display: flex;
  gap: 20px;
  margin-bottom: 16px;
  font-size: 14px;
  color: #606266;
}

.knowledge-tree-preview {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 16px;
  background: #fafafa;
}

.knowledge-tree-preview .tree-node {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.knowledge-tree-preview .node-desc {
  font-size: 12px;
  color: #909399;
}
</style>
