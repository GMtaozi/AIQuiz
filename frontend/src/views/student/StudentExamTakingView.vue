<template>
  <div v-loading="loading" class="taking">
    <template v-if="!loading && questions.length > 0">
      <div class="header-card">
        <h2 class="exam-title">{{ examTitle }}</h2>
        <p class="meta">
          共 {{ questions.length }} 题 · 总分 {{ totalScore }} 分
          <span v-if="deadline" class="countdown" :class="{ danger: remainSeconds <= 300 }">
            剩余 {{ formatCountdown(remainSeconds) }}
          </span>
        </p>
      </div>

      <div class="body-grid">
        <div class="question-panel">
          <div class="question-card">
            <p class="q-label">第 {{ currentIndex + 1 }} / {{ questions.length }} 题 · {{ typeName(current.type) }}（{{ current.score }} 分）</p>
            <p class="q-content">{{ current.content }}</p>

            <el-radio-group v-if="isChoice(current)" v-model="answers[current.question_id]">
              <el-radio
                v-for="opt in current.options"
                :key="opt.option_label"
                :value="opt.option_label"
                class="option-row"
              >
                <b>{{ opt.option_label }}.</b> {{ opt.option_content }}
              </el-radio>
            </el-radio-group>
            <el-input
              v-else
              v-model="answers[current.question_id]"
              type="textarea"
              :rows="4"
              placeholder="请输入答案"
            />
          </div>

          <div class="nav-bar">
            <el-button :disabled="currentIndex === 0" @click="currentIndex--">上一题</el-button>
            <el-button :disabled="currentIndex >= questions.length - 1" @click="currentIndex++">下一题</el-button>
            <el-button type="primary" class="submit-btn" :loading="submitting" @click="handleSubmit">
              交卷
            </el-button>
          </div>
        </div>

        <aside class="answer-sheet">
          <p class="sheet-title">答题卡</p>
          <div class="sheet-grid">
            <button
              v-for="(q, i) in questions"
              :key="q.question_id"
              class="sheet-cell"
              :class="{ done: isAnswered(q), current: i === currentIndex }"
              @click="currentIndex = i"
            >
              {{ i + 1 }}
            </button>
          </div>
          <p class="sheet-summary">已答 {{ answeredCount }} / {{ questions.length }}</p>
        </aside>
      </div>
    </template>

    <el-empty v-else-if="!loading" description="无法加载试卷或试卷为空" />
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'

const route = useRoute()
const router = useRouter()
const examId = Number(route.params.id)

const loading = ref(true)
const submitting = ref(false)
const examTitle = ref('')
const recordId = ref(null)
const deadline = ref(null)
const remainSeconds = ref(0)
const questions = ref([])
const answers = ref({})
const currentIndex = ref(0)

let timer = null

const TYPE_NAMES = {
  single_choice: '单选题',
  multiple_choice: '多选题',
  true_false: '判断题',
  fill_blank: '填空题',
  essay: '简答题'
}
const typeName = (t) => TYPE_NAMES[t] ?? t

// 后端单选以选项标签作答；非选择题为文本作答
const isChoice = (q) => q.question_type === 'single_choice' || q.question_type === 'true_false'

const totalScore = computed(() => questions.value.reduce((s, q) => s + (q.score || 0), 0))
const answeredCount = computed(() => questions.value.filter(isAnswered).length)

function isAnswered(q) {
  const a = answers.value[q.question_id]
  return a !== undefined && a !== null && String(a).trim() !== ''
}

function formatCountdown(sec) {
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

async function init() {
  loading.value = true
  try {
    // 1. 开始/恢复考试记录（后端幂等：已有进行中的记录直接返回）
    const startRes = await api.post(`/exams/${examId}/start`)
    const records = Array.isArray(startRes.data) ? startRes.data : []
    if (records.length === 0) {
      ElMessage.error('未能创建考试记录')
      return
    }
    recordId.value = records[0].id

    if (records[0].status !== 'in_progress') {
      ElMessage.warning('本场考试已提交')
      router.replace('/student/scores')
      return
    }

    // 2. 拉取题目（服务端裁剪答案）
    const qRes = await api.get(`/exams/${examId}/questions`)
    questions.value = Array.isArray(qRes.data) ? qRes.data : []

    // 3. 考试详情 → 截止时间倒计时
    const examRes = await api.get(`/exams/${examId}`)
    examTitle.value = examRes.data?.title || `考试 #${examId}`
    if (examRes.data?.end_time) {
      deadline.value = new Date(examRes.data.end_time).getTime()
      tick()
      timer = setInterval(tick, 1000)
    }
  } catch (e) {
    ElMessage.error(e.message || '进入考试失败')
    router.replace('/student/exams')
  } finally {
    loading.value = false
  }
}

function tick() {
  if (!deadline.value) return
  remainSeconds.value = Math.max(0, Math.floor((deadline.value - Date.now()) / 1000))
  if (remainSeconds.value === 0) {
    clearInterval(timer)
    ElMessage.warning('考试时间已到，自动交卷')
    doSubmit()
  }
}

async function doSubmit() {
  if (submitting.value) return
  clearInterval(timer)
  submitting.value = true
  try {
    const payload = questions.value.map((q) => ({
      question_id: q.question_id,
      answer_content: String(answers.value[q.question_id] ?? '')
    }))
    await api.post(
      `/exams/${examId}/submit?exam_record_id=${recordId.value}`,
      payload
    )
    await ElMessageBox.alert('答卷已提交，客观题成绩将由系统判定。', '提交成功', { confirmButtonText: '查看成绩' })
    router.replace('/student/scores')
  } catch (e) {
    ElMessage.error(e.message || '提交失败')
    submitting.value = false
    timer = setInterval(tick, 1000)
  }
}

function handleSubmit() {
  if (answeredCount.value < questions.value.length) {
    ElMessageBox.confirm(`还有 ${questions.value.length - answeredCount.value} 题未作答，确认交卷？`, '提示')
      .then(() => doSubmit())
      .catch(() => {})
    return
  }
  ElMessageBox.confirm('确认交卷？交卷后不可修改。', '提示')
    .then(() => doSubmit())
    .catch(() => {})
}

onMounted(init)
onUnmounted(() => clearInterval(timer))
</script>

<style scoped lang="scss">
.taking { max-width: 960px; margin: 0 auto; }

.header-card {
  background: #FFFFFF;
  border: 1px solid #E5E6EB;
  border-radius: 8px;
  padding: 16px 20px;
  margin-bottom: 16px;

  .exam-title { margin: 0 0 6px; font-size: 18px; font-weight: 600; color: #1D2129; }
  .meta { margin: 0; font-size: 13px; color: #86909C; display: flex; gap: 16px; align-items: center; }
  .countdown {
    font-weight: 600;
    color: #165DFF;
    &.danger { color: #F53F3F; }
  }
}

.body-grid {
  display: grid;
  grid-template-columns: 1fr 200px;
  gap: 16px;
  align-items: start;
}

.question-card {
  background: #FFFFFF;
  border: 1px solid #E5E6EB;
  border-radius: 8px;
  padding: 20px;

  .q-label { font-size: 13px; color: #86909C; margin: 0 0 10px; }
  .q-content { font-size: 15px; color: #1D2129; line-height: 1.7; white-space: pre-wrap; margin: 0 0 16px; }

  .option-row {
    display: flex;
    padding: 8px 12px;
    border: 1px solid #F2F3F5;
    border-radius: 6px;
    margin-bottom: 8px;

    &:hover { border-color: #165DFF; }
  }
}

.nav-bar {
  display: flex;
  gap: 8px;
  margin-top: 16px;

  .submit-btn { margin-left: auto; }
}

.answer-sheet {
  background: #FFFFFF;
  border: 1px solid #E5E6EB;
  border-radius: 8px;
  padding: 16px;

  .sheet-title { font-size: 14px; font-weight: 600; color: #1D2129; margin: 0 0 12px; }

  .sheet-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; }

  .sheet-cell {
    height: 32px;
    border: 1px solid #E5E6EB;
    border-radius: 4px;
    background: #FFFFFF;
    cursor: pointer;
    font-size: 13px;
    color: #4E5969;

    &.done { background: #E8F3FF; border-color: #165DFF; color: #165DFF; }
    &.current { outline: 2px solid #165DFF; outline-offset: -1px; }
  }

  .sheet-summary { font-size: 12px; color: #86909C; margin: 12px 0 0; }
}

@media (max-width: 720px) {
  .body-grid { grid-template-columns: 1fr; }
}
</style>
