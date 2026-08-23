<template>
  <div v-loading="loading">
    <h2 class="page-title">考试中心</h2>
    <el-empty v-if="!loading && exams.length === 0" description="暂无可参加的考试" />

    <div class="exam-grid">
      <div v-for="exam in exams" :key="exam.id" class="exam-card">
        <div class="card-body">
          <h3 class="exam-title">{{ exam.title }}</h3>
          <p class="exam-time">
            <span v-if="exam.start_time">{{ formatTime(exam.start_time) }}</span>
            <span v-if="exam.end_time"> ~ {{ formatTime(exam.end_time) }}</span>
            <span v-if="!exam.start_time && !exam.end_time">时间待定</span>
          </p>
        </div>
        <div class="card-footer">
          <el-tag :type="statusTagType(exam.status)" size="small">{{ statusText(exam.status) }}</el-tag>
          <el-button
            type="primary"
            size="small"
            :disabled="exam.status !== 'published'"
            @click="enterExam(exam)"
          >
            {{ exam.status === 'published' ? '进入考试' : '未开放' }}
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '@/api'

const router = useRouter()
const loading = ref(false)
const exams = ref([])

const statusMap = {
  pending: { text: '未开始', type: 'info' },
  published: { text: '进行中', type: 'success' },
  ended: { text: '已结束', type: 'warning' }
}
const statusText = (s) => statusMap[s]?.text ?? s
const statusTagType = (s) => statusMap[s]?.type ?? 'info'

const formatTime = (iso) => (iso ? new Date(iso).toLocaleString('zh-CN', { hour12: false }) : '')

const loadExams = async () => {
  loading.value = true
  try {
    const res = await api.get('/exams')
    exams.value = Array.isArray(res.data) ? res.data : []
  } catch (e) {
    ElMessage.error(e.message || '加载考试列表失败')
  } finally {
    loading.value = false
  }
}

const enterExam = (exam) => {
  router.push(`/student/exams/${exam.exam_paper_id ?? exam.id}`)
}

onMounted(loadExams)
</script>

<style scoped lang="scss">
.page-title {
  font-size: 20px;
  font-weight: 600;
  color: #1D2129;
  margin: 0 0 20px;
}

.exam-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.exam-card {
  background: #FFFFFF;
  border: 1px solid #E5E6EB;
  border-radius: 8px;
  overflow: hidden;
  transition: box-shadow 0.2s;

  &:hover {
    box-shadow: 0 4px 16px rgba(29, 33, 41, 0.08);
  }

  .card-body {
    padding: 16px;

    .exam-title {
      font-size: 15px;
      font-weight: 600;
      color: #1D2129;
      margin: 0 0 8px;
    }

    .exam-time {
      font-size: 13px;
      color: #86909C;
      margin: 0;
      display: flex;
      gap: 4px;
    }
  }

  .card-footer {
    padding: 12px 16px;
    border-top: 1px solid #F2F3F5;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
}
</style>
