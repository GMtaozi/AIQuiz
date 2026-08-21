<template>
  <div class="dashboard">
    <!-- 页面标题区 -->
    <div class="page-header" :class="{ 'animate-in': mounted }">
      <h1 class="page-title">数据概览</h1>
      <p class="page-subtitle">实时监控系统运行状态</p>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stat-cards">
      <el-col :xs="24" :sm="12" :lg="6" v-for="(stat, index) in stats" :key="index">
        <el-skeleton :loading="loading" animated>
          <template #default>
            <div
              class="stat-card"
              :class="[`stat-card-${index}`, { 'animate-in': mounted }]"
              :style="{ '--delay': `${index * 100}ms`, '--accent': stat.color }"
            >
              <div class="stat-card-bg"></div>
              <div class="stat-card-content">
                <div class="stat-icon-wrap">
                  <el-icon :size="24" class="stat-icon">
                    <component :is="stat.icon" />
                  </el-icon>
                </div>
                <div class="stat-info">
                  <div class="stat-value">{{ animatedValues[index] }}</div>
                  <div class="stat-label">{{ stat.label }}</div>
                </div>
              </div>
            </div>
          </template>
        </el-skeleton>
      </el-col>
    </el-row>

    <!-- 图表区域 -->
    <el-row :gutter="20" class="chart-section">
      <el-col :xs="24" :lg="16">
        <el-card class="chart-card" :class="{ 'animate-in': mounted }" style="--delay: 400ms">
          <template #header>
            <div class="chart-card-header">
              <div class="chart-title-wrap">
                <span class="chart-title">题目增长趋势</span>
                <span class="chart-subtitle">近{{ trendDays }}天数据统计</span>
              </div>
              <el-radio-group v-model="trendPeriod" size="small">
                <el-radio-button value="week">本周</el-radio-button>
                <el-radio-button value="month">本月</el-radio-button>
                <el-radio-button value="year">本年</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <div ref="trendChartRef" class="chart-container" v-loading="loading" element-loading-text="加载中..."></div>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="8">
        <el-card class="chart-card" :class="{ 'animate-in': mounted }" style="--delay: 500ms">
          <template #header>
            <div class="chart-title-wrap">
              <span class="chart-title">题型分布</span>
              <span class="chart-subtitle">各类题型占比</span>
            </div>
          </template>
          <div ref="pieChartRef" class="chart-container pie-container" v-loading="loading" element-loading-text="加载中..."></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 底部双栏 -->
    <el-row :gutter="20" class="bottom-section">
      <!-- 待审核 -->
      <el-col :xs="24" :lg="12">
        <el-card class="pending-card" :class="{ 'animate-in': mounted }" style="--delay: 600ms">
          <template #header>
            <div class="card-header">
              <span class="chart-title">待审核题目</span>
              <el-badge :value="pendingTasks.length" type="warning">
                <el-button size="small" link @click="$router.push('/question-bank')">查看全部</el-button>
              </el-badge>
            </div>
          </template>
          <div class="pending-list" v-if="pendingTasks.length > 0">
            <div v-for="task in pendingTasks.slice(0, 5)" :key="task.id" class="pending-item">
              <div class="pending-info">
                <el-tag size="small" :type="getTypeTagType(task.type)" class="type-tag">
                  {{ getTypeName(task.type) }}
                </el-tag>
                <span class="pending-content">{{ task.content }}</span>
              </div>
              <div class="pending-actions">
                <el-button type="primary" size="small" link @click="approveTask(task)" class="action-btn approve">
                  <el-icon><Check /></el-icon>
                </el-button>
                <el-button type="danger" size="small" link @click="rejectTask(task)" class="action-btn reject">
                  <el-icon><Close /></el-icon>
                </el-button>
              </div>
            </div>
          </div>
          <el-empty v-else description="暂无待审核题目" :image-size="60" />
        </el-card>
      </el-col>

      <!-- 最近活动 -->
      <el-col :xs="24" :lg="12">
        <el-card class="activity-card" :class="{ 'animate-in': mounted }" style="--delay: 700ms">
          <template #header>
            <div class="card-header">
              <span class="chart-title">最近活动</span>
              <span class="chart-subtitle">系统操作日志</span>
            </div>
          </template>
          <div class="activity-timeline" v-if="recentActivities.length > 0">
            <div v-for="(activity, index) in recentActivities.slice(0, 5)" :key="index" class="timeline-item">
              <div class="timeline-marker" :style="{ '--marker-color': activity.color }"></div>
              <div class="timeline-body">
                <div class="timeline-header">
                  <span class="timeline-title">{{ activity.title }}</span>
                  <span class="timeline-time">{{ activity.time }}</span>
                </div>
                <div class="timeline-desc">{{ activity.desc }}</div>
              </div>
            </div>
          </div>
          <el-empty v-else description="暂无活动记录" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check, Close } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { dashboardAPI, auditAPI } from '@/api'

const router = useRouter()
const mounted = ref(false)
const loading = ref(false)
const dashboardError = ref('')

// 统计数据 - 从API加载
const stats = reactive([
  { label: '总题库量', value: 0, icon: 'Document', color: '#165DFF' },
  { label: '今日新增', value: 0, icon: 'Plus', color: '#67C23A' },
  { label: '总试卷数', value: 0, icon: 'Collection', color: '#E6A23C' },
  { label: '待审核', value: 0, icon: 'Clock', color: '#F56C6C' }
])

const animatedValues = ref([0, 0, 0, 0])
const trendPeriod = ref('week')
const trendDays = computed(() => ({ week: 7, month: 30, year: 365 }[trendPeriod.value]))

// 待办事项 - 从API加载
const pendingTasks = ref([])

// 最近活动时间线 - 从API加载
const recentActivities = ref([])

// 图表数据
const trendData = ref([])
const pieData = ref([])

// 图表实例
let trendChart = null
let pieChart = null
const trendChartRef = ref(null)
const pieChartRef = ref(null)

// 获取仪表盘数据
const fetchDashboardData = async () => {
  loading.value = true
  dashboardError.value = ''
  try {
    const response = await dashboardAPI.getOverview()
    const data = response.data

    // 更新统计数据
    stats[0].value = data.stats.total_questions || 0
    stats[1].value = data.stats.today_questions || 0
    stats[2].value = data.stats.total_papers || 0
    stats[3].value = data.stats.pending_audit || 0

    // 更新动画
    animatedValues.value = stats.map(s => s.value)

    // 更新题型分布饼图
    pieData.value = [
      { value: data.question_type_dist.single_choice || 0, name: '单选题', itemStyle: { color: '#3B82F6' } },
      { value: data.question_type_dist.multiple_choice || 0, name: '多选题', itemStyle: { color: '#909399' } },
      { value: data.question_type_dist.true_false || 0, name: '判断题', itemStyle: { color: '#10B981' } },
      { value: data.question_type_dist.essay || 0, name: '简答题', itemStyle: { color: '#F59E0B' } }
    ]

    // 更新趋势数据
    trendData.value = data.question_trend || []

    // 更新待审核任务
    try {
      const auditResponse = await auditAPI.getPending({ page: 1, page_size: 5 })
      pendingTasks.value = (auditResponse.data.items || []).map(q => ({
        id: q.id,
        type: q.question_type === 'single_choice' ? 'choice' : q.question_type === 'multiple_choice' ? 'multiple' : q.question_type === 'true_false' ? 'judge' : 'short_answer',
        content: q.content?.substring(0, 50) + (q.content?.length > 50 ? '...' : '')
      }))
    } catch {
      pendingTasks.value = []
    }

    // 更新最近活动
    recentActivities.value = (data.recent_activities || []).map((a, i) => ({
      title: getActivityTitle(a.type),
      desc: a.description,
      time: formatTime(a.created_at),
      color: ['#165DFF', '#67C23A', '#E6A23C', '#F56C6C', '#909399'][i % 5]  // 评估 P2-14：规范功能色板
    }))

    // 初始化图表
    setTimeout(() => {
      initTrendChart()
      initPieChart()
    }, 100)

  } catch (error) {
    console.error('获取仪表盘数据失败:', error)
    dashboardError.value = '获取仪表盘数据失败，请刷新重试'
    ElMessage.error(dashboardError.value)
  } finally {
    loading.value = false
  }
}

const getActivityTitle = (type) => {
  const map = {
    'question_created': '新增题目',
    'question_approved': '题目审核通过',
    'question_rejected': '题目审核拒绝',
    'paper_created': '创建试卷',
    'ai_task': 'AI任务',
    'user_login': '用户登录',
    'exam_started': '开始考试',
    'exam_submitted': '提交考试'
  }
  return map[type] || type
}

const formatTime = (time) => {
  if (!time) return ''
  const date = new Date(time)
  const now = new Date()
  const diff = (now - date) / 1000

  if (diff < 60) return '刚刚'
  if (diff < 3600) return Math.floor(diff / 60) + '分钟前'
  if (diff < 86400) return Math.floor(diff / 3600) + '小时前'
  return Math.floor(diff / 86400) + '天前'
}

// 动画计数
const animateCounter = (index, target, duration = 1500) => {
  const start = 0
  const startTime = performance.now()

  const update = (currentTime) => {
    const elapsed = currentTime - startTime
    const progress = Math.min(elapsed / duration, 1)
    const easeOutQuart = 1 - Math.pow(1 - progress, 4)
    animatedValues.value[index] = Math.floor(start + (target - start) * easeOutQuart)

    if (progress < 1) {
      requestAnimationFrame(update)
    }
  }

  requestAnimationFrame(update)
}

// 初始化动画
const initAnimations = () => {
  stats.forEach((stat, index) => {
    setTimeout(() => animateCounter(index, stat.value), 300 + index * 150)
  })
}

// 初始化趋势图
const initTrendChart = () => {
  if (!trendChartRef.value) return

  if (trendChart) trendChart.dispose()
  trendChart = echarts.init(trendChartRef.value)

  const xAxisData = trendData.value.map(d => d.date?.substring(5) || d.date)
  const chartData = trendData.value.map(d => d.count || 0)

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#E5E7EB',
      textStyle: { color: '#374151', fontFamily: 'DM Sans' },
      extraCssText: 'box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1); border-radius: 8px;'
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '12%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: xAxisData,
      axisLine: { lineStyle: { color: '#E5E7EB' } },
      axisLabel: { color: '#6B7280', fontFamily: 'DM Sans' },
      splitLine: { show: false }
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisLabel: { color: '#6B7280', fontFamily: 'DM Sans' },
      splitLine: { lineStyle: { color: '#F3F4F6' } }
    },
    series: [
      {
        name: '题目数量',
        type: 'line',
        smooth: 0.4,
        symbol: 'circle',
        symbolSize: 8,
        lineStyle: {
          color: '#3B82F6',
          width: 3
        },
        itemStyle: {
          color: '#3B82F6',
          borderColor: '#fff',
          borderWidth: 2
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(59, 130, 246, 0.2)' },
            { offset: 1, color: 'rgba(59, 130, 246, 0)' }
          ])
        },
        data: chartData,
        animationDuration: 1500,
        animationEasing: 'cubicOut'
      }
    ]
  }

  trendChart.setOption(option)
}

// 初始化饼图
const initPieChart = () => {
  if (!pieChartRef.value) return

  if (pieChart) pieChart.dispose()
  pieChart = echarts.init(pieChartRef.value)

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#E5E7EB',
      textStyle: { color: '#374151', fontFamily: 'DM Sans' },
      extraCssText: 'box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1); border-radius: 8px;'
    },
    legend: {
      orient: 'vertical',
      right: '5%',
      top: 'center',
      textStyle: { color: '#6B7280', fontFamily: 'DM Sans' },
      itemWidth: 12,
      itemHeight: 12,
      itemGap: 12
    },
    series: [
      {
        name: '题型分布',
        type: 'pie',
        radius: ['45%', '70%'],
        center: ['35%', '50%'],
        avoidLabelOverlap: true,
        itemStyle: {
          borderRadius: 6,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: { show: false },
        emphasis: {
          label: {
            show: true,
            fontSize: 13,
            fontWeight: '600',
            color: '#374151',
            fontFamily: 'DM Sans'
          }
        },
        data: pieData.value.length > 0 ? pieData.value : [
          { value: 0, name: '单选题', itemStyle: { color: '#3B82F6' } },
          { value: 0, name: '多选题', itemStyle: { color: '#909399' } },
          { value: 0, name: '判断题', itemStyle: { color: '#10B981' } },
          { value: 0, name: '简答题', itemStyle: { color: '#F59E0B' } }
        ],
        animationDuration: 1200,
        animationEasing: 'cubicOut'
      }
    ]
  }

  pieChart.setOption(option)
}

// 工具函数
const getTypeName = (type) => {
  const map = { choice: '单选', multiple: '多选', short_answer: '简答', judge: '判断' }
  return map[type] || type
}

const getTypeTagType = (type) => {
  const map = { choice: '', multiple: 'success', short_answer: 'warning', judge: 'info' }
  return map[type] || 'info'
}

// 操作处理
const approveTask = async (task) => {
  try {
    await auditAPI.approve(task.id)
    ElMessage.success('题目已通过')
    pendingTasks.value = pendingTasks.value.filter(t => t.id !== task.id)
  } catch {
    ElMessage.error('操作失败')
  }
}

const rejectTask = async (task) => {
  try {
    await ElMessageBox.confirm('确定要拒绝这道题目吗？', '提示', { type: 'warning' })
    await auditAPI.reject(task.id, { reason: '' })
    ElMessage.success('已拒绝题目')
    pendingTasks.value = pendingTasks.value.filter(t => t.id !== task.id)
  } catch {}
}

// 响应式处理
const handleResize = () => {
  trendChart?.resize()
  pieChart?.resize()
}

watch(trendPeriod, () => {
  fetchDashboardData()
})

onMounted(async () => {
  mounted.value = true
  await fetchDashboardData()
  initAnimations()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  trendChart?.dispose()
  pieChart?.dispose()
})
</script>

<style scoped>
.dashboard {
  padding: 0;
}

/* 页面标题 */
.page-header {
  margin-bottom: 24px;
  opacity: 0;
  transform: translateY(20px);
}

.page-header.animate-in {
  animation: fadeSlideIn 0.6s ease forwards;
}

.page-title {
  font-family: 'Outfit', 'Segoe UI', sans-serif;
  font-size: 26px;
  font-weight: 600;
  color: #1F2937;
  margin: 0 0 4px 0;
}

.page-subtitle {
  font-family: 'DM Sans', sans-serif;
  font-size: 14px;
  color: #9CA3AF;
  margin: 0;
}

/* 入场动画 */
.animate-in {
  opacity: 0;
  transform: translateY(24px);
  animation: fadeSlideIn 0.6s cubic-bezier(0.4, 0, 0.2, 1) forwards;
  animation-delay: var(--delay, 0ms);
}

@keyframes fadeSlideIn {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 统计卡片 */
.stat-cards {
  margin-bottom: 20px;
}

.stat-card {
  border-radius: 16px;
  overflow: hidden;
  margin-bottom: 16px;
  position: relative;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
  cursor: default;
}

.stat-card:hover {
  transform: translateY(-4px);
}

.stat-card-bg {
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, var(--accent) 0%, color-mix(in srgb, var(--accent) 75%, white) 100%);
  opacity: 0.08;
  transition: opacity 0.3s ease;
}

.stat-card:hover .stat-card-bg {
  opacity: 0.12;
}

.stat-card-content {
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  position: relative;
  z-index: 1;
}

.stat-icon-wrap {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  background: linear-gradient(135deg, var(--accent) 0%, color-mix(in srgb, var(--accent) 80%, white) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px color-mix(in srgb, var(--accent) 30%, transparent);
}

.stat-icon {
  color: white;
}

.stat-info {
  flex: 1;
  min-width: 0;
}

.stat-value {
  font-family: 'Outfit', sans-serif;
  font-size: 30px;
  font-weight: 700;
  color: #1F2937;
  line-height: 1.1;
  letter-spacing: -0.5px;
}

.stat-label {
  font-family: 'DM Sans', sans-serif;
  font-size: 13px;
  color: #6B7280;
  margin-top: 4px;
}

/* 图表卡片 */
.chart-section {
  margin-bottom: 20px;
}

.chart-card {
  border-radius: 16px;
  border: 1px solid #F3F4F6;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  transition: box-shadow 0.3s ease, transform 0.3s ease;
}

.chart-card:hover {
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
}

.chart-card :deep(.el-card__header) {
  padding: 16px 20px;
  border-bottom: 1px solid #F3F4F6;
}

.chart-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chart-title-wrap {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.chart-title {
  font-family: 'Outfit', sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: #1F2937;
}

.chart-subtitle {
  font-family: 'DM Sans', sans-serif;
  font-size: 12px;
  color: #9CA3AF;
}

.chart-container {
  height: 280px;
  width: 100%;
}

.pie-container {
  height: 260px;
}

/* 待审核列表 */
.pending-list {
  padding: 8px 0;
  max-height: 320px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: #D1D5DB transparent;
}

.pending-list::-webkit-scrollbar {
  width: 6px;
}

.pending-list::-webkit-scrollbar-track {
  background: transparent;
}

.pending-list::-webkit-scrollbar-thumb {
  background: #D1D5DB;
  border-radius: 3px;
}

.pending-list::-webkit-scrollbar-thumb:hover {
  background: #9CA3AF;
}

.pending-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid #F3F4F6;
  transition: background 0.2s ease;
}

.pending-item:last-child {
  border-bottom: none;
}

.pending-item:hover {
  background: #F9FAFB;
  margin: 0 -20px;
  padding: 12px 20px;
}

.pending-info {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.type-tag {
  flex-shrink: 0;
}

.pending-content {
  font-family: 'DM Sans', sans-serif;
  font-size: 14px;
  color: #374151;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pending-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
  margin-left: 12px;
}

.action-btn {
  width: 28px;
  height: 28px;
  padding: 0;
  border-radius: 6px;
}

.action-btn.approve {
  color: #10B981;
}

.action-btn.approve:hover {
  background: rgba(16, 185, 129, 0.1);
}

.action-btn.reject {
  color: #EF4444;
}

.action-btn.reject:hover {
  background: rgba(239, 68, 68, 0.1);
}

/* 活动时间线 */
.activity-timeline {
  position: relative;
  padding-left: 20px;
  max-height: 320px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: #D1D5DB transparent;
}

.activity-timeline::-webkit-scrollbar {
  width: 6px;
}

.activity-timeline::-webkit-scrollbar-track {
  background: transparent;
}

.activity-timeline::-webkit-scrollbar-thumb {
  background: #D1D5DB;
  border-radius: 3px;
}

.activity-timeline::-webkit-scrollbar-thumb:hover {
  background: #9CA3AF;
}

.activity-timeline::before {
  content: '';
  position: absolute;
  left: 6px;
  top: 8px;
  bottom: 8px;
  width: 2px;
  background: linear-gradient(to bottom, #165DFF 0%, #4080FF 100%);  /* 评估 P2-14：紫色 → 规范主色 */
  border-radius: 1px;
}

.timeline-item {
  display: flex;
  gap: 16px;
  padding-bottom: 16px;
  position: relative;
}

.timeline-item:last-child {
  padding-bottom: 0;
}

.timeline-marker {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  position: relative;
  z-index: 1;
}

.timeline-marker::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: var(--marker-color, #3B82F6);
  border: 3px solid white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.timeline-body {
  flex: 1;
  min-width: 0;
  background: #F9FAFB;
  border-radius: 10px;
  padding: 12px 14px;
  border: 1px solid #F3F4F6;
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.timeline-title {
  font-family: 'Outfit', sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: #1F2937;
}

.timeline-time {
  font-family: 'DM Sans', sans-serif;
  font-size: 12px;
  color: #9CA3AF;
}

.timeline-desc {
  font-family: 'DM Sans', sans-serif;
  font-size: 13px;
  color: #6B7280;
  line-height: 1.4;
}

/* 底部区域 */
.bottom-section {
  margin-bottom: 20px;
}

/* 响应式 */
@media (max-width: 768px) {
  .page-title {
    font-size: 22px;
  }

  .stat-value {
    font-size: 26px;
  }

  .stat-card-content {
    padding: 16px;
  }

  .stat-icon-wrap {
    width: 46px;
    height: 46px;
  }

  .chart-container {
    height: 240px;
  }

  .pending-info {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }

  .pending-actions {
    margin-left: 0;
    margin-top: 8px;
  }

  .timeline-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }
}
</style>
