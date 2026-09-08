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
  background: var(--surface-primary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-xl);
  padding: var(--space-4) var(--space-5);
  margin-bottom: var(--space-4);

  .exam-title { margin: 0 0 var(--space-1); font-size: var(--font-size-xl); font-weight: 600; color: var(--text-primary); }
  .meta { margin: 0; font-size: var(--font-size-sm); color: var(--text-secondary); display: flex; gap: var(--space-4); align-items: center; }
  .countdown {
    font-weight: 600;
    color: var(--color-primary);
    &.danger { 
      color: var(--color-danger); 
      animation: countdownPulse 1s infinite;
    }
  }
}

.body-grid {
  display: grid;
  grid-template-columns: 1fr 200px;
  gap: var(--space-4);
  align-items: start;
}

.question-card {
  background: var(--surface-primary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-xl);
  padding: var(--space-5);

  .q-label { font-size: var(--font-size-sm); color: var(--text-secondary); margin: 0 0 var(--space-2); }
  .q-content { font-size: var(--font-size-base); color: var(--text-primary); line-height: 1.7; white-space: pre-wrap; margin: 0 0 var(--space-4); }

  .option-row {
    display: flex;
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--border-light);
    border-radius: var(--radius-md);
    margin-bottom: var(--space-2);

    &:hover { border-color: var(--color-primary); }
  }
}

.nav-bar {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-4);

  .submit-btn { margin-left: auto; }
}

.answer-sheet {
  background: var(--surface-primary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-xl);
  padding: var(--space-4);

  .sheet-title { font-size: var(--font-size-base); font-weight: 600; color: var(--text-primary); margin: 0 0 var(--space-3); }

  .sheet-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: var(--space-1); }

  .sheet-cell {
    height: 32px;
    border: 1px solid var(--border-default);
    border-radius: var(--radius-sm);
    background: var(--surface-primary);
    cursor: pointer;
    font-size: var(--font-size-sm);
    color: var(--text-regular);

    &.done { background: rgba(var(--color-primary-rgb), 0.1); border-color: var(--color-primary); color: var(--color-primary); }
    &.current { outline: 2px solid var(--color-primary); outline-offset: -1px; }
  }

  .sheet-summary { font-size: var(--font-size-xs); color: var(--text-secondary); margin: var(--space-3) 0 0; }
}

@media (max-width: 720px) {
  .body-grid { grid-template-columns: 1fr; }
}

@keyframes countdownPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
