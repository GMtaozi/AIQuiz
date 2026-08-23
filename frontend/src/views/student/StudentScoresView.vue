<template>
  <div v-loading="loading">
    <h2 class="page-title">我的成绩</h2>
    <el-empty v-if="!loading && records.length === 0" description="暂无考试记录" />

    <el-table v-else :data="records" stripe>
      <el-table-column label="考试" min-width="220">
        <template #default="{ row }">{{ examTitleOf(row) }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="110">
        <template #default="{ row }">
          <el-tag size="small" :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="score" label="得分" width="100">
        <template #default="{ row }">{{ row.score ?? '—' }}</template>
      </el-table-column>
      <el-table-column label="开始时间" width="180">
        <template #default="{ row }">{{ fmt(row.started_at) }}</template>
      </el-table-column>
      <el-table-column label="提交时间" width="180">
        <template #default="{ row }">{{ fmt(row.submitted_at) }}</template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'

const loading = ref(false)
const records = ref([])
const titles = ref({})

const statusMap = {
  in_progress: { text: '进行中', type: 'primary' },
  submitted: { text: '已提交待判分', type: 'warning' },
  graded: { text: '已出分', type: 'success' }
}
const statusText = (s) => statusMap[s]?.text ?? s
const statusType = (s) => statusMap[s]?.type ?? 'info'

const fmt = (iso) => (iso ? new Date(iso).toLocaleString('zh-CN', { hour12: false }) : '—')
const examTitleOf = (row) => titles.value[row.exam_paper_id] ?? `考试 #${row.exam_paper_id}`

onMounted(async () => {
  loading.value = true
  try {
    const [recRes, examRes] = await Promise.all([api.get('/exam-records'), api.get('/exams')])
    records.value = Array.isArray(recRes.data) ? recRes.data : []
    // 一次拉考试列表建标题映射（避免逐条详情 N+1）
    const map = {}
    for (const e of Array.isArray(examRes.data) ? examRes.data : []) {
      map[e.exam_paper_id ?? e.id] = e.title
    }
    titles.value = map
  } catch (e) {
    ElMessage.error(e.message || '加载成绩失败')
  } finally {
    loading.value = false
  }
})
</script>

<style scoped lang="scss">
.page-title {
  font-size: 20px;
  font-weight: 600;
  color: #1D2129;
  margin: 0 0 20px;
}
</style>
