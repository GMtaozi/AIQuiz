<template>
  <div class="kb-view">
    <!-- ===== 列表模式 ===== -->
    <template v-if="!currentKb">
      <div class="operation-bar">
        <div class="left">
          <el-input
            v-model="kbFilters.keyword"
            placeholder="搜索知识库名称..."
            clearable
            style="width: 240px"
            @keyup.enter="fetchKnowledgeBases"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-select v-model="kbFilters.category" placeholder="分类" clearable style="width: 140px" @change="fetchKnowledgeBases">
            <el-option v-for="c in categoryOptions" :key="c.value" :label="c.label" :value="c.value" />
          </el-select>
          <el-select v-model="kbFilters.visibility" placeholder="可见性" clearable style="width: 120px" @change="fetchKnowledgeBases">
            <el-option label="私有" value="private" />
            <el-option label="共享" value="shared" />
            <el-option label="公开" value="public" />
          </el-select>
        </div>
        <div class="right">
          <el-button type="primary" @click="openCreateDialog">
            <el-icon><Plus /></el-icon> 新建知识库
          </el-button>
          <el-button circle @click="fetchKnowledgeBases"><el-icon><Refresh /></el-icon></el-button>
        </div>
      </div>

      <el-card shadow="never" class="table-card">
        <el-table
          :data="knowledgeBases"
          :loading="kbLoading"
          style="width: 100%"
          @row-click="viewKbDetail"
          :row-style="{ cursor: 'pointer' }"
        >
          <el-table-column prop="name" label="名称" min-width="200" show-overflow-tooltip />
          <el-table-column prop="description" label="描述" min-width="220" show-overflow-tooltip />
          <el-table-column prop="category" label="分类" width="120" align="center" />
          <el-table-column prop="exam_type" label="考试类型" width="140" align="center" show-overflow-tooltip />
          <el-table-column prop="subject_name" label="所属科目" width="140" align="center" show-overflow-tooltip />
          <el-table-column label="条目数" width="100" align="center">
            <template #default="{ row }">{{ row.entries_count ?? '-' }}</template>
          </el-table-column>
          <el-table-column label="知识点" width="100" align="center">
            <template #default="{ row }">{{ row.points_count ?? '-' }}</template>
          </el-table-column>
          <el-table-column prop="visibility" label="可见性" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="visibilityTagType(row.visibility)" size="small">
                {{ visibilityLabel(row.visibility) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="180" align="center" />
          <el-table-column label="操作" width="220" align="center" fixed="right">
            <template #default="{ row }">
              <el-button type="primary" link size="small" @click.stop="viewKbDetail(row)">查看</el-button>
              <el-button type="primary" link size="small" @click.stop="openEditDialog(row)">编辑</el-button>
              <el-popconfirm title="确定删除？将级联删除所有条目和知识点" @confirm="deleteKb(row)">
                <template #reference>
                  <el-button type="danger" link size="small" @click.stop>删除</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-wrap">
          <el-pagination
            v-model:current-page="kbCurrentPage"
            v-model:page-size="kbPageSize"
            :total="totalKb"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next"
            @size-change="fetchKnowledgeBases"
            @current-change="fetchKnowledgeBases"
          />
        </div>
      </el-card>
    </template>

    <!-- ===== 详情模式 ===== -->
    <template v-else>
      <div class="detail-view">
        <div class="detail-header">
          <div class="header-left">
            <el-button @click="backToList"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
            <div class="kb-info">
              <h2>{{ currentKb.name }}</h2>
              <div class="kb-meta">
                <el-tag :type="visibilityTagType(currentKb.visibility)" size="small">
                  {{ visibilityLabel(currentKb.visibility) }}
                </el-tag>
                <span v-if="currentKb.category" class="meta-item">{{ currentKb.category }}</span>
                <span v-if="currentKb.exam_type" class="meta-item">{{ currentKb.exam_type }}</span>
                <span v-if="currentKb.entries_count !== undefined" class="meta-item">
                  条目 {{ currentKb.entries_count }}
                </span>
                <span v-if="currentKb.points_count !== undefined" class="meta-item">
                  知识点 {{ currentKb.points_count }}
                </span>
              </div>
              <p v-if="currentKb.description" class="kb-desc">{{ currentKb.description }}</p>
            </div>
          </div>
          <div class="header-right">
            <el-button @click="openEditDialog(currentKb)"><el-icon><Edit /></el-icon> 编辑</el-button>
            <el-button type="danger" @click="deleteKb(currentKb)"><el-icon><Delete /></el-icon> 删除</el-button>
          </div>
        </div>

        <el-tabs v-model="activeTab" class="detail-tabs">
          <!-- 知识条目 -->
          <el-tab-pane label="文档条目" name="entries">
            <div class="operation-bar">
              <div class="left">
                <el-button type="primary" @click="uploadDialogVisible = true">
                  <el-icon><Upload /></el-icon> 上传文档
                </el-button>
              </div>
            </div>

            <el-card shadow="never" class="table-card">
              <el-table :data="entries" :loading="entriesLoading" style="width: 100%">
                <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
                <el-table-column prop="source_location" label="位置" width="150" align="center" show-overflow-tooltip />
                <el-table-column label="内容长度" width="110" align="center">
                  <template #default="{ row }">{{ contentLengthLabel(row.content) }}</template>
                </el-table-column>
                <el-table-column prop="order" label="排序" width="80" align="center" />
                <el-table-column prop="created_at" label="创建时间" width="170" align="center" />
                <el-table-column label="操作" width="260" align="center" fixed="right">
                  <template #default="{ row }">
                    <el-button link size="small" @click="viewEntryDetail(row)">查看</el-button>
                    <el-button type="primary" link size="small" @click="analyzeSingleEntry(currentKb!.id, row.id, extractMode)">提取</el-button>
                    <el-button type="success" link size="small" @click="handleImportFromEntry(row)">导入</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-card>
          </el-tab-pane>

          <!-- 知识点 -->
          <el-tab-pane label="知识点" name="points">
            <div class="operation-bar">
              <div class="left">
                <el-select v-model="extractMode" placeholder="提取模式" style="width: 140px">
                  <el-option label="规则提取" value="rule" />
                  <el-option label="AI提取" value="ai" />
                  <el-option label="自动" value="auto" />
                </el-select>
                <el-button type="primary" :loading="analyzing" @click="handleAnalyzeAll">
                  <el-icon><MagicStick /></el-icon> 批量提取所有条目
                </el-button>
              </div>
            </div>
            <el-card shadow="never" class="table-card">
              <div v-if="pointsTree.length === 0 && !pointsLoading" class="empty-tip">
                <el-empty description="暂无知识点，请先上传文档并提取" />
              </div>
              <el-tree
                v-else
                :data="pointsTree"
                :props="treeProps"
                default-expand-all
                :load="loadTreeNode"
                lazy
                node-key="id"
                :loading="pointsLoading"
                class="points-tree"
              >
                <template #default="{ node, data }">
                  <div class="point-node">
                    <span class="point-name">{{ node.label }}</span>
                    <el-tag v-if="data.content_excerpt" type="info" size="small" effect="plain">有原文</el-tag>
                  </div>
                </template>
              </el-tree>
            </el-card>
          </el-tab-pane>
        </el-tabs>
      </div>
    </template>

    <!-- ===== 创建/编辑对话框 ===== -->
    <el-dialog
      v-model="kbDialogVisible"
      :title="kbDialogMode === 'create' ? '新建知识库' : '编辑知识库'"
      width="520px"
      :close-on-click-modal="false"
      @close="resetKbForm"
    >
      <el-form :model="kbForm" :rules="kbFormRules" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="kbForm.name" placeholder="请输入知识库名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="kbForm.description" type="textarea" :rows="3" placeholder="可选描述" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="kbForm.category" placeholder="请选择分类" style="width: 100%">
            <el-option v-for="c in categoryOptions" :key="c.value" :label="c.label" :value="c.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="考试类型">
          <el-select v-model="kbForm.exam_type" placeholder="请选择（可选）" clearable style="width: 100%">
            <el-option v-for="t in examTypeOptions" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="可见性">
          <el-radio-group v-model="kbForm.visibility">
            <el-radio value="private">私有</el-radio>
            <el-radio value="shared">共享</el-radio>
            <el-radio value="public">公开</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="kbDialogVisible = false; resetKbForm()">取消</el-button>
        <el-button type="primary" :loading="kbSubmitting" @click="submitKbForm">确定</el-button>
      </template>
    </el-dialog>

    <!-- ===== 上传文档对话框 ===== -->
    <el-dialog
      v-model="uploadDialogVisible"
      title="上传文档"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-upload
        ref="uploadRef"
        v-model:file-list="uploadFileList"
        drag
        accept=".pdf,.txt,.md,.docx,.doc"
        :auto-upload="false"
        :limit="5"
        :on-change="handleUploadFileChange"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">拖拽文件到此处，或<em>点击上传</em></div>
        <template #tip>
          <div class="el-upload__tip">支持 PDF、TXT、Markdown、Word，单文件不超过 50MB</div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="uploadDialogVisible = false; uploadFileList = []">取消</el-button>
        <el-button type="primary" :loading="uploadProcessing" @click="handleUploadConfirm">
          上传并解析
        </el-button>
      </template>
    </el-dialog>

    <!-- ===== 条目详情抽屉 ===== -->
    <el-drawer v-model="entryDrawerVisible" title="条目详情" direction="rtl" size="50%">
      <div v-if="currentEntry" class="entry-detail">
        <h3>{{ currentEntry.title }}</h3>
        <div class="entry-meta">
          <span v-if="currentEntry.source_location">位置：{{ currentEntry.source_location }}</span>
          <span>内容长度：{{ currentEntry.content.length }} 字</span>
        </div>
        <el-divider />
        <pre class="entry-content">{{ currentEntry.content }}</pre>
      </div>
    </el-drawer>

    <!-- ===== 提取预览对话框 ===== -->
    <el-dialog
      v-model="extractPreviewVisible"
      title="提取预览"
      width="700px"
      :close-on-click-modal="false"
    >
      <div v-if="extractPreview.length === 0" class="empty-tip">
        <el-empty description="提取结果为空" />
      </div>
      <el-scrollbar v-else max-height="450px">
        <div v-for="(kp, idx) in extractPreview" :key="idx" class="preview-kp">
          <div class="preview-kp-name">{{ kp.name || kp.title || `知识点 ${idx + 1}` }}</div>
          <div v-if="kp.description" class="preview-kp-desc">{{ kp.description }}</div>
          <div v-if="kp.content_excerpt || kp.excerpt || kp.原文" class="preview-kp-excerpt">
            {{ kp.content_excerpt || kp.excerpt || kp.原文 }}
          </div>
        </div>
      </el-scrollbar>
      <template #footer>
        <el-button @click="extractPreviewVisible = false">取消</el-button>
        <el-button type="primary" @click="handleConfirmImport">确认导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  knowledgeBaseAPI,
  knowledgeAPI,
} from '@/api'
import { useKnowledgeBase } from '@/composables/useKnowledgeBase'
import type { KnowledgeBase } from '@/composables/useKnowledgeBase'
import type { UploadFile } from 'element-plus'

const {
  // State
  knowledgeBases,
  totalKb,
  kbLoading,
  kbCurrentPage,
  kbPageSize,
  kbFilters,
  currentKb,
  currentEntry,
  entries,
  entriesLoading,
  pointsTree,
  pointsLoading,
  analyzing,
  extractMode,
  extractPreview,
  extractPreviewVisible,
  uploadDialogVisible,
  uploadFileList,
  uploadProcessing,
  kbDialogVisible,
  kbDialogMode,
  kbSubmitting,
  kbForm,
  kbFormRules,
  subjectOptions,
  categoryOptions,
  examTypeOptions,
  // Actions
  fetchKnowledgeBases,
  fetchOptions,
  openCreateDialog,
  openEditDialog,
  resetKbForm,
  submitKbForm,
  deleteKb,
  viewKbDetail,
  fetchEntries,
  fetchPoints,
  analyzeSingleEntry,
  importAnalyzedEntry,
  analyzeAllEntries,
  uploadDocument,
} = useKnowledgeBase()

// Local state
const activeTab = ref('entries')
const entryDrawerVisible = ref(false)
const uploadRef = ref<any>(null)
const treeProps = {
  label: 'name',
  children: 'children',
  isLeaf: (data: any) => !data.children || data.children.length === 0,
}

// ============ Lifecycle ============
onMounted(() => {
  fetchOptions()
  fetchKnowledgeBases()
})

// ============ Helpers ============
function visibilityLabel(v: string): string {
  const map: Record<string, string> = { private: '私有', shared: '共享', public: '公开' }
  return map[v] || v
}

function visibilityTagType(v: string): string {
  const map: Record<string, string> = { private: 'info', shared: 'warning', public: 'success' }
  return map[v] || 'info'
}

function contentLengthLabel(content: string): string {
  const len = content.length
  if (len >= 10000) return `${(len / 10000).toFixed(1)}万字`
  if (len >= 1000) return `${(len / 1000).toFixed(1)}千字`
  return `${len}字`
}

function backToList() {
  currentKb.value = null
  entries.value = []
  pointsTree.value = []
  fetchKnowledgeBases()
}

// ============ Entry Actions ============
function viewEntryDetail(row: any) {
  // Fetch full entry content if needed
  if (row.content && row.content.length > 500) {
    currentEntry.value = row
    entryDrawerVisible.value = true
  } else {
    ElMessage.info('条目内容较短，已在列表中展示')
  }
}

async function handleAnalyzeAll() {
  if (!currentKb.value) return
  try {
    await analyzeAllEntries(currentKb.value.id, extractMode.value)
    await fetchPoints(currentKb.value.id)
  } catch (e) {
    // error handled in composable
  }
}

async function handleImportFromEntry(row: any) {
  if (!currentKb.value) return
  try {
    const preview = await analyzeSingleEntry(currentKb.value.id, row.id, extractMode.value)
    // Preview is already set by analyzeSingleEntry
  } catch (e) {
    // error handled
  }
}

async function handleConfirmImport() {
  if (!currentKb.value || extractPreview.value.length === 0) return
  try {
    await importAnalyzedEntry(currentKb.value.id, 0, extractPreview.value)
    await fetchPoints(currentKb.value.id)
  } catch (e) {
    // error handled
  }
}

function handleUploadFileChange(file: UploadFile, fileList: UploadFile[]) {
  uploadFileList.value = fileList.map(f => f.raw || f).filter(Boolean) as File[]
}

async function handleUploadConfirm() {
  if (!currentKb.value || uploadFileList.value.length === 0) {
    ElMessage.warning('请选择要上传的文件')
    return
  }
  const file = uploadFileList.value[0]
  try {
    await uploadDocument(currentKb.value.id, file)
  } catch (e) {
    // error handled
  }
}

function loadTreeNode(node: any, resolve: (data: any[]) => void) {
  if (node.level === 0) {
    resolve(pointsTree.value)
    return
  }
  if (node.data.children && node.data.children.length > 0) {
    resolve(node.data.children)
  } else {
    resolve([])
  }
}
</script>

<style scoped>
.kb-view {
  padding: 20px;
  background-color: #f5f5f5;
  height: calc(100vh - 60px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ===== Operation bar ===== */
.operation-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  gap: 12px;
}
.operation-bar .left {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.operation-bar .right {
  display: flex;
  gap: 10px;
  align-items: center;
}

/* ===== Table card ===== */
.table-card {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.table-card .el-table {
  flex: 1;
}

/* ===== Pagination ===== */
.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  padding: 12px 0 0;
}

/* ===== Detail view ===== */
.detail-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
  gap: 16px;
}
.header-left {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  flex: 1;
}
.kb-info h2 {
  margin: 0 0 6px;
  font-size: 18px;
  font-weight: 600;
}
.kb-meta {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.meta-item {
  font-size: 13px;
  color: #606266;
}
.kb-desc {
  margin: 8px 0 0;
  font-size: 13px;
  color: #909399;
  max-width: 600px;
}
.header-right {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

/* ===== Tabs ===== */
.detail-tabs {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.detail-tabs :deep(.el-tabs__content) {
  flex: 1;
  overflow: auto;
}

/* ===== Points tree ===== */
.points-tree {
  padding: 8px 0;
}
.point-node {
  display: flex;
  align-items: center;
  gap: 8px;
}
.point-name {
  font-size: 14px;
}

/* ===== Preview ===== */
.preview-kp {
  padding: 12px;
  margin-bottom: 8px;
  background: #fafafa;
  border-radius: 4px;
  border-left: 3px solid #165DFF;
}
.preview-kp-name {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 4px;
}
.preview-kp-desc {
  font-size: 13px;
  color: #555;
  margin-bottom: 4px;
}
.preview-kp-excerpt {
  font-size: 12px;
  color: #888;
  background: #f0f0f0;
  padding: 6px 10px;
  border-radius: 3px;
  max-height: 120px;
  overflow: hidden;
}

/* ===== Entry detail ===== */
.entry-detail h3 {
  margin: 0 0 12px;
}
.entry-meta {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: #909399;
}
.entry-content {
  font-size: 14px;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 60vh;
  overflow-y: auto;
}

/* ===== Empty tip ===== */
.empty-tip {
  padding: 40px;
  text-align: center;
}
</style>
