<template>
  <div class="batch-knowledge-view">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-title">
        <el-icon class="title-icon"><Upload /></el-icon>
        <span>批量导入知识点</span>
      </div>
      <div class="header-desc">支持批量上传多个文档，自动提取知识点</div>
    </div>

    <!-- 主内容区 -->
    <div class="main-content">
      <!-- 左侧：文件上传 -->
      <div class="upload-section">
        <el-card class="upload-card">
          <template #header>
            <div class="card-header">
              <span>上传文档</span>
              <el-tag size="small" type="info">支持 PDF, DOCX, TXT, Markdown</el-tag>
            </div>
          </template>

          <!-- 拖拽上传区域 -->
          <div
            class="upload-zone"
            :class="{ 'is-dragover': isDragOver }"
            @dragover.prevent="handleDragOver"
            @dragleave="handleDragLeave"
            @drop.prevent="handleDrop"
            @click="triggerFileInput"
          >
            <input
              ref="fileInputRef"
              type="file"
              multiple
              accept=".pdf,.docx,.doc,.txt,.md"
              style="display: none"
              @change="handleFileSelect"
            />
            <div class="upload-content">
              <el-icon class="upload-icon"><UploadFilled /></el-icon>
              <div class="upload-text">将文件拖拽到此处或点击上传</div>
              <div class="upload-hint">单个文件不超过 10MB</div>
            </div>
          </div>

          <!-- 目标设置 -->
          <div class="target-settings">
            <div class="setting-item">
              <label>考试分类 <span class="required">*</span></label>
              <el-select v-model="targetCategoryId" placeholder="请选择考试分类" clearable>
                <el-option
                  v-for="cat in categories"
                  :key="cat.id"
                  :label="cat.name"
                  :value="cat.id"
                />
              </el-select>
            </div>
            <div class="setting-item">
              <label>考试科目 <span class="required">*</span></label>
              <el-select v-model="targetExamTypeId" placeholder="请选择考试科目" clearable :disabled="!targetCategoryId">
                <el-option
                  v-for="et in filteredExamTypes"
                  :key="et.id"
                  :label="et.name"
                  :value="et.id"
                />
              </el-select>
            </div>
            <div class="setting-item">
              <label>挂载到</label>
              <el-tree-select
                v-model="parentKpId"
                :data="knowledgeTreeData"
                placeholder="作为根节点（可选）"
                clearable
                check-strictly
                :render-after-expand="false"
              />
            </div>
          </div>

          <!-- 文件列表 -->
          <div class="file-list" v-if="fileList.length > 0">
            <div class="file-list-header">
              <span>已上传 {{ fileList.length }} 个文件</span>
              <el-button text size="small" @click="clearFileList">清空</el-button>
            </div>
            <div class="file-items">
              <div v-for="(file, idx) in fileList" :key="idx" class="file-item">
                <el-icon class="file-icon"><Document /></el-icon>
                <span class="file-name">{{ file.name }}</span>
                <span class="file-size">{{ formatFileSize(file.size) }}</span>
                <el-icon class="file-remove" @click="removeFile(idx)"><Close /></el-icon>
              </div>
            </div>
          </div>

          <!-- 操作按钮 -->
          <div class="action-buttons">
            <el-button
              type="primary"
              :loading="isProcessing"
              :disabled="fileList.length === 0"
              @click="handleAnalyze"
            >
              {{ isProcessing ? '处理中...' : '开始分析' }}
            </el-button>
          </div>
        </el-card>

        <!-- 处理进度 -->
        <el-card class="progress-card" v-if="isProcessing || analysisResults.length > 0">
          <template #header>
            <span>处理状态</span>
          </template>
          <div class="progress-content">
            <el-progress
              v-if="isProcessing"
              :percentage="processingProgress"
              :status="processingProgress === 100 ? 'success' : undefined"
            />
            <div class="result-summary" v-if="analysisResults.length > 0">
              <el-tag type="success" v-if="successCount > 0">成功 {{ successCount }}</el-tag>
              <el-tag type="danger" v-if="failedCount > 0">失败 {{ failedCount }}</el-tag>
            </div>
          </div>
        </el-card>
      </div>

      <!-- 右侧：知识预览 -->
      <div class="preview-section">
        <el-card class="preview-card">
          <template #header>
            <div class="card-header">
              <span>知识点预览</span>
              <el-button
                text
                size="small"
                :disabled="analysisResults.length === 0"
                @click="clearResults"
              >
                清空预览
              </el-button>
            </div>
          </template>

          <div class="preview-empty" v-if="analysisResults.length === 0">
            <el-empty description="请先上传并分析文档">
              <template #image>
                <el-icon :size="60" class="empty-icon"><DocumentCopy /></el-icon>
              </template>
            </el-empty>
          </div>

          <div class="knowledge-preview" v-else>
            <div
              v-for="(result, idx) in analysisResults"
              :key="idx"
              class="document-preview"
            >
              <div
                class="doc-header"
                :class="{ 'is-failed': result.status === 'failed' }"
              >
                <el-icon class="doc-status-icon">
                  <CircleCheck v-if="result.status === 'completed'" />
                  <CircleClose v-else />
                </el-icon>
                <span class="doc-name">{{ result.filename }}</span>
                <el-tag size="small" type="info" v-if="result.method">
                  {{ result.method === 'rule-based' ? '规则' : 'AI' }}
                </el-tag>
                <span class="doc-count" v-if="result.total_points">
                  {{ result.total_points }} 个知识点
                </span>
              </div>

              <!-- 知识点树 -->
              <div class="kp-tree" v-if="result.knowledge_tree && result.knowledge_tree.length > 0">
                <el-tree
                  :data="result.knowledge_tree"
                  :props="{ label: 'name', children: 'children' }"
                  default-expand-all
                  node-key="id"
                  class="knowledge-tree"
                >
                  <template #default="{ node, data }">
                    <span class="kp-node">
                      <span class="kp-name">{{ data.name }}</span>
                      <span class="kp-actions">
                        <el-button text size="small" @click.stop="editNode(data)">
                          <el-icon><Edit /></el-icon>
                        </el-button>
                        <el-button text size="small" @click.stop="removeNode(result.knowledge_tree, node, data)">
                          <el-icon><Delete /></el-icon>
                        </el-button>
                      </span>
                    </span>
                  </template>
                </el-tree>
              </div>

              <!-- 失败原因 -->
              <div class="error-message" v-if="result.status === 'failed'">
                <el-alert type="error" :closable="false">
                  {{ result.error }}
                </el-alert>
              </div>
            </div>
          </div>
        </el-card>

        <!-- 导入按钮 -->
        <div class="import-actions" v-if="canImport">
          <el-button type="success" size="large" @click="handleImport" :loading="isImporting">
            <el-icon><Download /></el-icon>
            批量导入 {{ totalSelectedPoints }} 个知识点
          </el-button>
        </div>
      </div>
    </div>

    <!-- 编辑对话框 -->
    <el-dialog v-model="editDialogVisible" title="编辑知识点" width="500px">
      <el-form :model="editingNode" label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="editingNode.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editingNode.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmEdit">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { knowledgeAPI, systemAPI } from '@/api'
import {
  Upload, UploadFilled, Document, Close, CircleCheck, CircleClose,
  DocumentCopy, Edit, Delete, Download
} from '@element-plus/icons-vue'

// 状态
const fileInputRef = ref(null)
const isDragOver = ref(false)
const fileList = ref([])
const targetCategoryId = ref(null)
const targetExamTypeId = ref(null)
const parentKpId = ref(null)
const categories = ref([])
const examTypes = ref([])
const knowledgeTreeData = ref([])
const analysisResults = ref([])
const isProcessing = ref(false)
const isImporting = ref(false)
const editDialogVisible = ref(false)
const editingNode = ref({ name: '', description: '' })

// 计算属性
const processingProgress = computed(() => {
  if (analysisResults.value.length === 0) return 0
  const completed = analysisResults.value.filter(r => r.status !== 'pending').length
  return Math.round((completed / analysisResults.value.length) * 100)
})

const successCount = computed(() =>
  analysisResults.value.filter(r => r.status === 'completed').length
)

const failedCount = computed(() =>
  analysisResults.value.filter(r => r.status === 'failed').length
)

const totalSelectedPoints = computed(() => {
  return analysisResults.value.reduce((total, result) => {
    if (result.knowledge_tree) {
      return total + countNodes(result.knowledge_tree)
    }
    return total
  }, 0)
})

const canImport = computed(() =>
  analysisResults.value.some(r => r.status === 'completed' && r.knowledge_tree?.length > 0)
)

const filteredExamTypes = computed(() => {
  if (!targetCategoryId.value) return examTypes.value
  return examTypes.value.filter(et => et.category_id === targetCategoryId.value)
})

// 方法
const countNodes = (nodes) => {
  // 只统计叶子节点（没有 children 或 children 为空的节点）
  let count = 0
  for (const node of nodes) {
    if (!node.children || node.children.length === 0) {
      count += 1
    } else {
      count += countNodes(node.children)
    }
  }
  return count
}

const formatFileSize = (bytes) => {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

const triggerFileInput = () => {
  fileInputRef.value?.click()
}

const handleDragOver = () => {
  isDragOver.value = true
}

const handleDragLeave = () => {
  isDragOver.value = false
}

const handleDrop = (e) => {
  isDragOver.value = false
  const files = Array.from(e.dataTransfer.files)
  addFiles(files)
}

const handleFileSelect = (e) => {
  const files = Array.from(e.target.files)
  addFiles(files)
  e.target.value = '' // 清空以便重复选择
}

const addFiles = (files) => {
  const validExts = ['pdf', 'docx', 'doc', 'txt', 'md']
  for (const file of files) {
    const ext = file.name.split('.').pop().toLowerCase()
    if (validExts.includes(ext)) {
      if (!fileList.value.find(f => f.name === file.name)) {
        fileList.value.push(file)
      }
    } else {
      ElMessage.warning(`不支持的文件格式: ${file.name}`)
    }
  }
}

const removeFile = (idx) => {
  fileList.value.splice(idx, 1)
}

const clearFileList = () => {
  fileList.value = []
  analysisResults.value = []
}

const clearResults = () => {
  analysisResults.value = []
}

const fetchCategories = async () => {
  try {
    const res = await knowledgeAPI.getHierarchyTrees()
    // 从层级树中提取分类
    if (res.data?.trees) {
      categories.value = res.data.trees
        .filter(t => t.node_type === 'category')
        .map(t => ({ id: t.category_id, name: t.name }))
    }
  } catch (e) {
    console.error('获取分类失败', e)
  }
}

const fetchExamTypes = async () => {
  try {
    const res = await systemAPI.getExamTypes()
    examTypes.value = res.data?.items || []
  } catch (e) {
    console.error('获取考试科目失败', e)
  }
}

const fetchKnowledgeTree = async () => {
  try {
    const res = await knowledgeAPI.getTrees()
    if (res.data?.trees) {
      knowledgeTreeData.value = res.data.trees.map(t => ({
        id: t.id,
        label: t.original_name || t.name,
        children: t.children?.map(c => convertNode(c))
      }))
    }
  } catch (e) {
    console.error('获取知识树失败', e)
  }
}

const convertNode = (node) => ({
  id: node.id,
  label: node.original_name || node.name,
  children: node.children?.map(c => convertNode(c))
})

const handleAnalyze = async () => {
  if (fileList.value.length === 0) {
    ElMessage.warning('请先上传文件')
    return
  }

  if (!targetCategoryId.value) {
    ElMessage.warning('请选择考试分类')
    return
  }

  if (!targetExamTypeId.value) {
    ElMessage.warning('请选择考试科目')
    return
  }

  isProcessing.value = true
  analysisResults.value = fileList.value.map(f => ({
    filename: f.name,
    status: 'pending',
    knowledge_tree: null,
    total_points: 0
  }))

  const formData = new FormData()
  fileList.value.forEach(f => formData.append('files', f))
  formData.append('category_id', targetCategoryId.value || '')
  formData.append('exam_type_id', targetExamTypeId.value || '')
  formData.append('extraction_mode', 'rule_then_ai')
  formData.append('parent_kp_id', parentKpId.value || '')

  try {
    const res = await knowledgeAPI.batchAnalyze(formData)

    if (res.data?.results) {
      analysisResults.value = res.data.results.map(r => ({
        filename: r.filename,
        status: r.status,
        method: r.method,
        knowledge_tree: r.knowledge_tree,
        total_points: r.total_points,
        error: r.error
      }))
    }

    ElMessage.success(res.data?.message || '分析完成')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '分析失败')
  } finally {
    isProcessing.value = false
  }
}

const handleImport = async () => {
  if (!canImport.value) return

  if (!targetCategoryId.value) {
    ElMessage.warning('请选择考试分类')
    return
  }

  if (!targetExamTypeId.value) {
    ElMessage.warning('请选择考试科目')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确认批量导入 ${totalSelectedPoints.value} 个知识点吗？`,
      '确认导入',
      { type: 'warning' }
    )
  } catch {
    return
  }

  isImporting.value = true

  const documents = analysisResults.value
    .filter(r => r.status === 'completed' && r.knowledge_tree?.length > 0)
    .map(r => ({
      filename: r.filename,
      knowledge_tree: r.knowledge_tree
    }))

  try {
    const res = await knowledgeAPI.batchImport({
      category_id: targetCategoryId.value,
      exam_type_id: targetExamTypeId.value,
      parent_kp_id: parentKpId.value,
      documents
    })

    ElMessage.success(res.data?.message || '导入成功')
    clearFileList()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '导入失败')
  } finally {
    isImporting.value = false
  }
}

const editNode = (data) => {
  editingNode.value = { ...data }
  editDialogVisible.value = true
}

const confirmEdit = () => {
  editDialogVisible.value = false
  ElMessage.success('修改成功')
}

const removeNode = (tree, node, data) => {
  const parent = node.parent
  const children = parent.data.children || parent.data
  const idx = children.findIndex(c => c.id === data.id)
  if (idx > -1) {
    children.splice(idx, 1)
  }
}

onMounted(() => {
  fetchCategories()
  fetchExamTypes()
  fetchKnowledgeTree()
})

// 切换分类时清空科目选择
watch(() => targetCategoryId.value, () => {
  targetExamTypeId.value = null
})
</script>

<style scoped>
.batch-knowledge-view {
  padding: 24px;
  background: #f5f7fa;
  min-height: 100%;
}

.page-header {
  margin-bottom: 24px;
}

.header-title {
  font-size: 20px;
  font-weight: 600;
  color: #1a1a1a;
  display: flex;
  align-items: center;
  gap: 8px;
}

.title-icon {
  color: #165dff;
}

.header-desc {
  margin-top: 4px;
  font-size: 14px;
  color: #666;
}

.main-content {
  display: grid;
  grid-template-columns: 400px 1fr;
  gap: 24px;
}

.upload-card,
.preview-card {
  border-radius: 8px;
  border: none;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.upload-zone {
  border: 2px dashed #d9d9d9;
  border-radius: 8px;
  padding: 40px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
  background: #fafafa;
}

.upload-zone:hover,
.upload-zone.is-dragover {
  border-color: #165dff;
  background: #f0f5ff;
}

.upload-icon {
  font-size: 48px;
  color: #bfbfbf;
  margin-bottom: 12px;
}

.upload-zone.is-dragover .upload-icon {
  color: #165dff;
}

.upload-text {
  font-size: 14px;
  color: #333;
  margin-bottom: 8px;
}

.upload-hint {
  font-size: 12px;
  color: #999;
}

.target-settings {
  margin-top: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.setting-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.setting-item label {
  font-size: 14px;
  color: #333;
  font-weight: 500;
}

.setting-item label .required {
  color: #ff4d4f;
  margin-left: 2px;
}

.file-list {
  margin-top: 20px;
  border: 1px solid #eee;
  border-radius: 8px;
  overflow: hidden;
}

.file-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #fafafa;
  border-bottom: 1px solid #eee;
  font-size: 14px;
  color: #333;
}

.file-items {
  max-height: 200px;
  overflow-y: auto;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-bottom: 1px solid #f0f0f0;
}

.file-item:last-child {
  border-bottom: none;
}

.file-icon {
  color: #165dff;
}

.file-name {
  flex: 1;
  font-size: 13px;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-size {
  font-size: 12px;
  color: #999;
}

.file-remove {
  color: #999;
  cursor: pointer;
}

.file-remove:hover {
  color: #ff4d4f;
}

.action-buttons {
  margin-top: 20px;
  display: flex;
  gap: 12px;
}

.action-buttons .el-button {
  flex: 1;
}

.progress-card {
  margin-top: 16px;
}

.progress-content {
  padding: 8px 0;
}

.result-summary {
  margin-top: 12px;
  display: flex;
  gap: 8px;
}

.preview-empty {
  padding: 60px 0;
}

.empty-icon {
  color: #d9d9d9;
}

.knowledge-preview {
  max-height: calc(100vh - 300px);
  overflow-y: auto;
}

.document-preview {
  border: 1px solid #eee;
  border-radius: 8px;
  margin-bottom: 16px;
  overflow: hidden;
}

.doc-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #fafafa;
  border-bottom: 1px solid #eee;
}

.doc-header.is-failed {
  background: #fff2f0;
}

.doc-status-icon {
  color: #52c41a;
}

.doc-header.is-failed .doc-status-icon {
  color: #ff4d4f;
}

.doc-name {
  flex: 1;
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.doc-count {
  font-size: 12px;
  color: #666;
}

.kp-tree {
  padding: 12px 16px;
}

.knowledge-tree {
  background: transparent;
}

.kp-node {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding-right: 8px;
}

.kp-name {
  font-size: 13px;
  color: #333;
}

.kp-actions {
  display: none;
  gap: 4px;
}

.kp-node:hover .kp-actions {
  display: flex;
}

.error-message {
  padding: 12px 16px;
}

.import-actions {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}
</style>
