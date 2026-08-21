<template>
  <div class="template-market">
    <div class="market-header">
      <h2>模板市场</h2>
      <p class="market-desc">浏览公开模板，一键复用优质试卷配置</p>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-input
        v-model="searchKeyword"
        placeholder="搜索模板名称或描述"
        clearable
        style="width: 260px"
        @input="handleSearch"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>

      <el-select
        v-model="filterSubjectId"
        placeholder="按科目筛选"
        clearable
        style="width: 200px"
        @change="handleSearch"
      >
        <el-option
          v-for="subject in subjectOptions"
          :key="subject.id"
          :label="subject.name"
          :value="subject.id"
        />
      </el-select>

      <el-select
        v-model="sortBy"
        placeholder="排序方式"
        style="width: 160px"
        @change="fetchTemplates"
      >
        <el-option label="使用最多" value="usage" />
        <el-option label="评分最高" value="rating" />
        <el-option label="最新发布" value="newest" />
      </el-select>
    </div>

    <!-- 模板卡片列表 -->
    <div v-loading="loading" class="template-list">
      <el-empty v-if="!loading && templates.length === 0" description="暂无公开模板" />

      <div class="template-cards">
        <el-card
          v-for="template in templates"
          :key="template.id"
          class="template-card"
          shadow="hover"
        >
          <div class="card-header">
            <div class="template-title-row">
              <h3 class="template-name" :title="template.name">{{ template.name }}</h3>
              <el-tag v-if="template.is_public" type="success" size="small">公开</el-tag>
            </div>
            <p class="template-desc" :title="template.description">
              {{ template.description || '暂无描述' }}
            </p>
          </div>

          <div class="card-meta">
            <div class="meta-item">
              <el-icon><Collection /></el-icon>
              <span>{{ getSubjectName(template.subject_id) || '未分类' }}</span>
            </div>
            <div class="meta-item">
              <el-icon><Timer /></el-icon>
              <span>{{ template.duration }}分钟</span>
            </div>
            <div class="meta-item">
              <el-icon><EditPen /></el-icon>
              <span>{{ template.total_score }}分</span>
            </div>
          </div>

          <div class="card-footer">
            <div class="rating-row">
              <el-rate
                v-model="template.rating"
                disabled
                show-score
                text-color="#ff9900"
                score-template="{value} 分"
              />
              <span class="usage-count">
                <el-icon><User /></el-icon>
                {{ template.usage_count }} 次使用
              </span>
            </div>

            <div class="card-actions">
              <el-button type="primary" size="small" @click="handleUseTemplate(template)">
                <el-icon><DocumentCopy /></el-icon>
                使用模板
              </el-button>
              <el-button size="small" @click="handleRate(template)">
                <el-icon><Star /></el-icon>
                评分
              </el-button>
            </div>
          </div>
        </el-card>
      </div>
    </div>

    <!-- 分页 -->
    <div v-if="total > 0" class="pagination-wrapper">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :page-sizes="[12, 24, 48]"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
        @current-change="handlePageChange"
      />
    </div>

    <!-- 评分弹窗 -->
    <el-dialog v-model="rateDialogVisible" title="给模板评分" width="420px">
      <div class="rate-dialog-content">
        <p class="rate-template-name">{{ currentRateTemplate?.name }}</p>
        <el-rate v-model="rateValue" :max="5" show-text />
        <p class="rate-hint">请为这个模板打分（0-5分）</p>
      </div>
      <template #footer>
        <el-button @click="rateDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="rateLoading" @click="submitRate">提交评分</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Collection, Timer, EditPen, User, DocumentCopy, Star } from '@element-plus/icons-vue'
import { paperAPI, systemAPI } from '@/api'

const router = useRouter()

const loading = ref(false)
const templates = ref([])
const subjectOptions = ref([])
const searchKeyword = ref('')
const filterSubjectId = ref(null)
const sortBy = ref('usage')
const total = ref(0)
const pagination = reactive({
  page: 1,
  pageSize: 12
})

// 评分相关
const rateDialogVisible = ref(false)
const rateLoading = ref(false)
const rateValue = ref(5)
const currentRateTemplate = ref(null)

const getSubjectName = (subjectId) => {
  const subject = subjectOptions.value.find(s => s.id === subjectId)
  return subject ? subject.name : ''
}

const fetchSubjects = async () => {
  try {
    const res = await systemAPI.getExamTypes()
    subjectOptions.value = res.data?.items || []
  } catch (e) {
    console.error('获取考试科目失败:', e)
  }
}

const fetchTemplates = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      subject_id: filterSubjectId.value,
      sort_by: sortBy.value
    }
    if (searchKeyword.value) {
      params.keyword = searchKeyword.value
    }

    const res = await paperAPI.getMarketplaceTemplates(params)
    templates.value = res.data?.items || []
    total.value = res.data?.total || 0
  } catch (e) {
    console.error('获取模板市场失败:', e)
    ElMessage.error('获取模板市场失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
  fetchTemplates()
}

const handleSizeChange = () => {
  pagination.page = 1
  fetchTemplates()
}

const handlePageChange = () => {
  fetchTemplates()
}

const handleUseTemplate = async (template) => {
  try {
    await paperAPI.useTemplate(template.id)
    ElMessage.success('模板已加载，请继续配置试卷')

    // 跳转到智能组卷页面，并传递模板ID
    router.push({
      path: '/auto-paper',
      query: { templateId: template.id }
    })
  } catch (e) {
    console.error('使用模板失败:', e)
    ElMessage.error(e.message || '使用模板失败')
  }
}

const handleRate = (template) => {
  currentRateTemplate.value = template
  rateValue.value = template.rating || 5
  rateDialogVisible.value = true
}

const submitRate = async () => {
  if (!currentRateTemplate.value) return

  rateLoading.value = true
  try {
    await paperAPI.rateTemplate(currentRateTemplate.value.id, rateValue.value)
    ElMessage.success('评分成功')
    rateDialogVisible.value = false
    fetchTemplates()
  } catch (e) {
    console.error('评分失败:', e)
    ElMessage.error(e.message || '评分失败')
  } finally {
    rateLoading.value = false
  }
}

onMounted(() => {
  fetchSubjects()
  fetchTemplates()
})
</script>

<style scoped lang="scss">
.template-market {
  padding: 20px;
}

.market-header {
  margin-bottom: 20px;

  h2 {
    margin: 0 0 8px 0;
    font-size: 22px;
    font-weight: 600;
    color: #303133;
  }

  .market-desc {
    margin: 0;
    color: #909399;
    font-size: 14px;
  }
}

.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.template-list {
  min-height: 200px;
}

.template-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.template-card {
  transition: transform 0.2s, box-shadow 0.2s;

  &:hover {
    transform: translateY(-2px);
  }

  :deep(.el-card__body) {
    padding: 16px;
  }
}

.card-header {
  margin-bottom: 12px;

  .template-title-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
    gap: 8px;
  }

  .template-name {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: #303133;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
  }

  .template-desc {
    margin: 0;
    color: #606266;
    font-size: 13px;
    line-height: 1.5;
    overflow: hidden;
    text-overflow: ellipsis;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    min-height: 39px;
  }
}

.card-meta {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
  padding: 10px 0;
  border-top: 1px solid #f0f0f0;
  border-bottom: 1px solid #f0f0f0;

  .meta-item {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 13px;
    color: #606266;

    .el-icon {
      color: #909399;
    }
  }
}

.card-footer {
  .rating-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;

    .usage-count {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 13px;
      color: #606266;
    }
  }

  .card-actions {
    display: flex;
    gap: 8px;

    .el-button {
      flex: 1;
    }
  }
}

.pagination-wrapper {
  margin-top: 24px;
  display: flex;
  justify-content: center;
}

.rate-dialog-content {
  text-align: center;
  padding: 20px 0;

  .rate-template-name {
    margin: 0 0 16px 0;
    font-size: 16px;
    font-weight: 600;
    color: #303133;
  }

  .rate-hint {
    margin: 12px 0 0 0;
    color: #909399;
    font-size: 13px;
  }
}
</style>
