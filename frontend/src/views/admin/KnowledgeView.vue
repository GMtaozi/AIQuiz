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
            @input="handleTreeSearch"
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
    <el-dialog v-model="importDialogVisible" title="导入知识点" width="600px" :close-on-click-modal="false">
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
import { knowledgeAPI, systemAPI } from '@/api'

const router = useRouter()

// 树形结构数据
const treeRef = ref(null)
const knowledgeTreeData = ref([])
const filteredTreeData = ref([])
const treeSearchKeyword = ref('')
const selectedKnowledge = ref(null)
const relatedQuestions = ref([])

// 弹窗状态
const dialogVisible = ref(false)
const importDialogVisible = ref(false)
const isEdit = ref(false)
const submitLoading = ref(false)

// 右键菜单
const contextMenuVisible = ref(false)
const contextMenuX = ref(0)
const contextMenuY = ref(0)
const contextMenuNode = ref(null)

// 导入相关
const importMode = ref('file')
const uploadRef = ref(null)
const aiUploadRef = ref(null)
const selectedFile = ref(null)
const aiSelectedFile = ref(null)
const aiAnalyzing = ref(false)
const aiResult = ref(null)
const aiImportForm = reactive({
  parentId: null,
  categoryId: null,
  examTypeId: null
})

// 树形配置
const treeProps = {
  label: 'name',
  children: 'children',
  value: 'id'
}

// 知识点表单
const knowledgeForm = reactive({
  id: null,
  name: '',
  parentId: null,
  categoryId: null,
  examTypeId: null,
  sortOrder: 0,
  description: ''
})

// 表单校验
const formRules = {
  name: [{ required: true, message: '请输入知识点名称', trigger: 'blur' }]
}

// 考试类型选项
const examTypeOptions = ref([])
const examCategoryOptions = ref([])

// 统计
const totalKnowledgeCount = ref(0)
const categoryCount = ref(0)
const examTypeCount = ref(0)

// 计算属性 - 仅知识点的树（用于弹窗选择父节点）
const knowledgeOnlyTreeData = computed(() => {
  return extractKnowledgeNodes(knowledgeTreeData.value)
})

const filteredFormExamTypeOptions = computed(() => {
  if (!knowledgeForm.categoryId) return examTypeOptions.value
  return examTypeOptions.value.filter(et => et.category_id === knowledgeForm.categoryId)
})

const filteredAIExamTypeOptions = computed(() => {
  if (!aiImportForm.categoryId) return examTypeOptions.value
  return examTypeOptions.value.filter(et => et.category_id === aiImportForm.categoryId)
})

// 从层级树中提取纯知识点节点（去掉 category/exam_type 虚拟节点）
const extractKnowledgeNodes = (nodes) => {
  const result = []
  for (const node of nodes) {
    if (node.node_type === 'category' || node.node_type === 'exam_type') {
      // 递归到子节点
      if (node.children) {
        result.push(...extractKnowledgeNodes(node.children))
      }
    } else {
      // 知识点节点，保留并递归子知识点
      const cloned = { ...node }
      if (cloned.children) {
        cloned.children = extractKnowledgeNodes(cloned.children)
      }
      result.push(cloned)
    }
  }
  return result
}

// 默认展开的节点 key
const defaultExpandedKeys = computed(() => {
  const keys = []
  const collectKeys = (nodes) => {
    for (const node of nodes) {
      if (node.node_type === 'category' || node.node_type === 'exam_type') {
        keys.push(node.id)
      }
      if (node.children) collectKeys(node.children)
    }
  }
  collectKeys(knowledgeTreeData.value)
  return keys
})

const handleFormCategoryChange = () => {
  knowledgeForm.examTypeId = null
}

const fetchExamTypesAndCourses = async () => {
  try {
    const categoryRes = await systemAPI.getExamCategories()
    examCategoryOptions.value = categoryRes.data?.items || []
    const examRes = await systemAPI.getExamTypes()
    examTypeOptions.value = examRes.data?.items || []
  } catch (e) {
    console.error('获取考试种类/考试类型失败:', e)
  }
}

// 拖拽控制
const allowDrop = (draggingNode, dropNode, type) => {
  // 只允许知识点节点拖拽，不允许拖到 category/exam_type 内部
  if (draggingNode.data.node_type) return false
  if (dropNode.data.node_type === 'category') return false
  return type !== 'inner'
}

const allowDrag = (draggingNode) => {
  // category 和 exam_type 节点不可拖拽
  return !draggingNode.data.node_type
}

// 生命周期
onMounted(() => {
  fetchKnowledgeTree()
  fetchExamTypesAndCourses()
  document.addEventListener('click', hideContextMenu)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', hideContextMenu)
})

// 获取层级知识树
const fetchKnowledgeTree = async () => {
  try {
    const response = await knowledgeAPI.getHierarchyTrees()
    knowledgeTreeData.value = response.data?.trees || response.data || []
    filteredTreeData.value = knowledgeTreeData.value
    calculateStats()
  } catch (error) {
    console.error('获取知识树失败:', error)
    knowledgeTreeData.value = []
    filteredTreeData.value = []
    calculateStats()
  }
}

// 统计知识节点后代中的知识点数量
const countDescendantKnowledge = (node) => {
  if (!node) return 0
  if (!node.node_type) return 1
  let count = 0
  if (node.children) {
    for (const child of node.children) {
      count += countDescendantKnowledge(child)
    }
  }
  return count
}

// 计算统计数据
const calculateStats = () => {
  // 递归统计
  let kpCount = 0
  let catCount = 0
  let etCount = 0
  const collectStats = (nodes) => {
    for (const node of nodes) {
      if (node.node_type === 'category') {
        catCount++
      } else if (node.node_type === 'exam_type') {
        etCount++
      } else {
        kpCount++
      }
      if (node.children) collectStats(node.children)
    }
  }
  collectStats(knowledgeTreeData.value)
  totalKnowledgeCount.value = kpCount
  categoryCount.value = catCount
  examTypeCount.value = etCount
}

// 树搜索 - 只匹配知识点节点
const handleTreeSearch = () => {
  if (!treeSearchKeyword.value) {
    filteredTreeData.value = knowledgeTreeData.value
    return
  }
  const keyword = treeSearchKeyword.value.toLowerCase()
  const filterTree = (nodes) => {
    const result = []
    for (const node of nodes) {
      if (node.node_type === 'category' || node.node_type === 'exam_type') {
        // 虚拟节点保留，但过滤子节点
        const filteredChildren = filterTree(node.children || [])
        if (filteredChildren.length > 0) {
          result.push({ ...node, children: filteredChildren })
        }
      } else {
        // 知识点节点，按名称匹配
        if (node.name.toLowerCase().includes(keyword)) {
          result.push(node)
        } else if (node.children) {
          const filteredChildren = filterTree(node.children)
          if (filteredChildren.length > 0) {
            result.push({ ...node, children: filteredChildren })
          }
        }
      }
    }
    return result
  }
  filteredTreeData.value = filterTree(knowledgeTreeData.value)
}

// 节点点击
const handleNodeClick = async (data) => {
  selectedKnowledge.value = { ...data }
  // 如果是知识点节点，查找额外信息
  if (!data.node_type) {
    const findParentName = (nodes, targetId, parentName = null) => {
      for (const node of nodes) {
        if (node.id === targetId && !node.node_type) {
          return parentName
        }
        if (node.children) {
          const found = findParentName(node.children, targetId, node.node_type ? null : node.name)
          if (found !== undefined) return found
        }
      }
      return undefined
    }
    selectedKnowledge.value.parentName = findParentName(knowledgeTreeData.value, data.id)

    // 查找所属种类和科目名称
    const findCategoryExamType = (nodes, targetId, catName = '', etName = '') => {
      for (const node of nodes) {
        if (node.node_type === 'category') {
          if (node.children) {
            const found = findCategoryExamType(node.children, targetId, node.name, etName)
            if (found) return found
          }
        } else if (node.node_type === 'exam_type') {
          if (node.children) {
            const found = findCategoryExamType(node.children, targetId, catName, node.name)
            if (found) return found
          }
        } else if (node.id === targetId) {
          return { categoryName: catName, examTypeName: etName }
        }
      }
      return null
    }
    const info = findCategoryExamType(knowledgeTreeData.value, data.id)
    if (info) {
      selectedKnowledge.value.categoryName = info.categoryName
      selectedKnowledge.value.examTypeName = info.examTypeName
    }

    // 获取相关题目
    try {
      const response = await knowledgeAPI.getNodesByCategory(data.id)
      relatedQuestions.value = response.data || []
    } catch (error) {
      relatedQuestions.value = []
    }
  }
}

// 右键菜单
const handleNodeContextMenu = (event, data) => {
  event.preventDefault()
  contextMenuNode.value = data
  contextMenuX.value = event.clientX
  contextMenuY.value = event.clientY
  contextMenuVisible.value = true
}

const hideContextMenu = () => {
  contextMenuVisible.value = false
}

// 拖拽
const handleDragStart = (node) => {
  console.log('Drag started:', node.data.name)
}

const handleDragEnd = async (node, dropNode, type) => {
  if (type === 'before' || type === 'after') {
    ElMessage.success('节点顺序已更新')
  }
}

// 新建知识点
const openCreateDialog = () => {
  isEdit.value = false
  resetForm()
  dialogVisible.value = true
}

// 在考试科目下新增知识点
const handleAddKnowledgeUnderExamType = () => {
  hideContextMenu()
  if (contextMenuNode.value) {
    isEdit.value = false
    resetForm()
    // 根据选中的 exam_type 节点自动设置种类和科目
    const etNode = contextMenuNode.value
    if (etNode.exam_type_id) {
      knowledgeForm.examTypeId = etNode.exam_type_id
      // 查找对应的 categoryId
      const etObj = examTypeOptions.value.find(e => e.id === etNode.exam_type_id)
      if (etObj?.category_id) {
        knowledgeForm.categoryId = etObj.category_id
      }
    }
    dialogVisible.value = true
  }
}

// 编辑知识点
const openEditDialog = () => {
  if (!selectedKnowledge.value) return
  isEdit.value = true
  Object.assign(knowledgeForm, {
    id: selectedKnowledge.value.id,
    name: selectedKnowledge.value.name,
    parentId: selectedKnowledge.value.parent_id || selectedKnowledge.value.parentId || null,
    categoryId: selectedKnowledge.value.categoryId || null,
    examTypeId: selectedKnowledge.value.examTypeId || null,
    sortOrder: selectedKnowledge.value.sortOrder || selectedKnowledge.value.order || 0,
    description: selectedKnowledge.value.description || ''
  })
  dialogVisible.value = true
}

// 重置表单
const resetForm = () => {
  knowledgeForm.id = null
  knowledgeForm.name = ''
  knowledgeForm.parentId = null
  knowledgeForm.categoryId = null
  knowledgeForm.examTypeId = null
  knowledgeForm.sortOrder = 0
  knowledgeForm.description = ''
}

// 提交表单
const submitForm = async () => {
  try {
    submitLoading.value = true
    if (isEdit.value) {
      await knowledgeAPI.updateNode(knowledgeForm.id, knowledgeForm)
      ElMessage.success('更新成功')
    } else {
      await knowledgeAPI.createNode(knowledgeForm)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchKnowledgeTree()
  } catch (error) {
    ElMessage.error('操作失败')
  } finally {
    submitLoading.value = false
  }
}

// 删除知识点
const deleteKnowledge = () => {
  if (!selectedKnowledge.value) return
  ElMessageBox.confirm(
    `确定要删除知识点"${selectedKnowledge.value.name}"吗？${
      selectedKnowledge.value.children?.length
        ? '（该知识点下有子节点，将一并删除）'
        : ''
    }`,
    '提示',
    { type: 'warning' }
  ).then(async () => {
    try {
      await knowledgeAPI.deleteNode(selectedKnowledge.value.id)
      ElMessage.success('删除成功')
      selectedKnowledge.value = null
      fetchKnowledgeTree()
    } catch (error) {
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

// 右键菜单操作
const handleAddChild = () => {
  hideContextMenu()
  if (contextMenuNode.value) {
    knowledgeForm.parentId = contextMenuNode.value.id
    isEdit.value = false
    resetForm()
    knowledgeForm.parentId = contextMenuNode.value.id
    dialogVisible.value = true
  }
}

const handleRename = () => {
  hideContextMenu()
  if (contextMenuNode.value) {
    selectedKnowledge.value = contextMenuNode.value
    openEditDialog()
  }
}

const handleDelete = () => {
  hideContextMenu()
  if (contextMenuNode.value) {
    selectedKnowledge.value = contextMenuNode.value
    deleteKnowledge()
  }
}

// 导入
const handleImport = () => {
  importMode.value = 'file'
  importDialogVisible.value = true
  resetImportState()
}

const resetImportState = () => {
  selectedFile.value = null
  aiSelectedFile.value = null
  aiResult.value = null
  aiAnalyzing.value = false
  if (uploadRef.value) uploadRef.value.clearFiles()
  if (aiUploadRef.value) aiUploadRef.value.clearFiles()
}

const closeImportDialog = () => {
  importDialogVisible.value = false
  resetImportState()
}

const handleFileChange = (file) => {
  selectedFile.value = file.raw
}

const handleAIFileChange = (file) => {
  aiSelectedFile.value = file.raw
  // 上传文件后自动触发规则解析（毫秒级，无需用户额外操作）
  autoRuleAnalyze()
}

const autoRuleAnalyze = async () => {
  if (!aiSelectedFile.value) return

  aiAnalyzing.value = false
  aiResult.value = null

  const formData = new FormData()
  formData.append('file', aiSelectedFile.value)
  formData.append('parent_id', aiImportForm.parentId || '')
  formData.append('category', typeof aiImportForm.categoryId === 'string' ? aiImportForm.categoryId : 'default')
  formData.append('category_id', aiImportForm.categoryId || '')

  try {
    // 第一步：规则解析（毫秒级，先展示结果让用户看到）
    const response = await knowledgeAPI.ruleAnalyze(formData)
    aiResult.value = response.data

    if (response.data.success) {
      ElMessage.success(`结构解析完成，提取 ${response.data.total_points} 个知识点，正在AI深度归纳...`)
      // 第二步：自动触发AI深度归纳（后台进行，完成后自动替换结果）
      startAIAnalysis()
    } else {
      ElMessage.error(response.data.error || '解析失败')
    }
  } catch (error) {
    console.error('规则解析失败:', error)
    ElMessage.error('文档解析失败，请重试')
  }
}

const startAIAnalysis = async () => {
  if (!aiSelectedFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }

  aiAnalyzing.value = true
  // 保留规则解析结果作为参考，不清空（AI分析失败时可回退）

  const formData = new FormData()
  formData.append('file', aiSelectedFile.value)
  formData.append('parent_id', aiImportForm.parentId || '')
  formData.append('category', typeof aiImportForm.categoryId === 'string' ? aiImportForm.categoryId : 'default')
  formData.append('category_id', aiImportForm.categoryId || '')

  console.log('开始AI深度分析 - parentId:', aiImportForm.parentId, 'categoryId:', aiImportForm.categoryId)

  try {
    const response = await knowledgeAPI.aiAnalyze(formData)
    aiResult.value = response.data
    console.log('AI分析完成 - parent_id in result:', response.data.parent_id)

    if (response.data.success) {
      ElMessage.success(response.data.message || 'AI 深度分析完成')
    } else {
      ElMessage.error(response.data.error || 'AI 分析失败')
    }
  } catch (error) {
    console.error('AI 分析失败:', error)
    ElMessage.error(error.message || 'AI 分析失败，请重试')
  } finally {
    aiAnalyzing.value = false
  }
}

const confirmAIImport = async () => {
  if (!aiResult.value || !aiResult.value.knowledge_points) {
    ElMessage.warning('没有可导入的知识点')
    return
  }

  console.log('确认导入 - knowledge_points count:', aiResult.value.knowledge_points.length, 'parent_id:', aiResult.value.parent_id, 'aiImportForm.parentId:', aiImportForm.parentId, 'document_name:', aiResult.value.document_name)

  try {
    const response = await knowledgeAPI.aiImport(
      aiResult.value.knowledge_points,
      aiImportForm.categoryId,
      aiImportForm.examTypeId,
      aiResult.value.parent_id || aiImportForm.parentId,
      aiResult.value.document_name  // 传递文档名，用于创建文档节点
    )

    if (response.data.success) {
      ElMessage.success(response.data.message || `成功导入 ${response.data.created_count} 个知识点`)
      closeImportDialog()
      fetchKnowledgeTree()
    } else {
      ElMessage.error(response.data.detail || '导入失败')
    }
  } catch (error) {
    console.error('导入失败:', error)
    ElMessage.error(error.message || '导入失败，请重试')
  }
}

const confirmImport = () => {
  ElMessage.success('导入成功')
  importDialogVisible.value = false
  fetchKnowledgeTree()
}

// 导出
const handleExport = () => {
  ElMessage.success('正在导出知识点，请稍候...')
}

// 批量文档导入 - 跳转到专用页面
const handleBatchImport = () => {
  router.push({ name: 'BatchKnowledge' })
}

// 查看题目
const viewQuestion = (question) => {
  ElMessage.info(`查看题目 ${question.id}`)
}

const viewAllQuestions = () => {
  ElMessage.info('跳转到题目列表')
}

// 工具函数
const formatDate = (date) => {
  if (!date) return '-'
  const d = new Date(date)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const truncateContent = (content) => {
  if (!content) return ''
  return content.length > 20 ? content.substring(0, 20) + '...' : content
}
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
