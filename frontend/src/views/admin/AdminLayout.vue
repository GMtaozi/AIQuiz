<template>
  <div class="admin-layout">
    <!-- 跳过链接（可访问性） -->
    <a href="#main-content" class="skip-link">跳转到主要内容</a>
    <!-- 权限不足提示 -->
    <el-dialog
      v-model="showPermissionDialog"
      title="权限提示"
      width="400px"
      :close-on-click-modal="false"
      show-close
    >
      <div style="text-align: center; padding: 20px 0;">
        <Icon icon="mdi:alert-circle" :size="48" color="#E6A23C" />
        <p style="margin-top: 16px; font-size: 15px; color: #303133;">
          您的账号尚未分配完整权限
        </p>
        <p style="margin-top: 8px; font-size: 13px; color: #909399;">
          请联系系统管理员分配相应菜单权限
        </p>
      </div>
      <template #footer>
        <el-button type="primary" @click="showPermissionDialog = false">我知道了</el-button>
      </template>
    </el-dialog>

    <!-- 侧边栏 -->
    <aside class="sidebar" :class="{ 'is-collapse': isCollapse, 'is-open': sidebarOpen }">
      <div class="sidebar-header">
        <div class="logo">
          <div class="logo-icon">
            <Icon icon="mdi:school" :size="28" />
          </div>
          <transition name="fade">
            <div v-if="!isCollapse" class="logo-text">
              <span class="logo-title">智题</span>
              <span class="logo-subtitle">AIQuiz</span>
            </div>
          </transition>
        </div>
      </div>

      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapse"
        :collapse-transition="false"
        router
        class="sidebar-menu"
        background-color="transparent"
        text-color="#a8b1c2"
        active-text-color="#165DFF"
      >
        <el-menu-item index="/dashboard">
          <Icon icon="mdi:gauge" />
          <template #title>控制台</template>
        </el-menu-item>
        <el-menu-item v-if="hasPermission('ai-question')" index="/ai-question">
          <Icon icon="mdi:auto-fix" />
          <template #title>AI出题</template>
        </el-menu-item>
        <el-menu-item v-if="hasPermission('audit')" index="/audit">
          <Icon icon="mdi:check-circle" />
          <template #title>试题审核</template>
        </el-menu-item>
        <el-menu-item v-if="hasPermission('auto-paper')" index="/auto-paper">
          <Icon icon="mdi:file-document-multiple" />
          <template #title>智能组卷</template>
        </el-menu-item>
        <el-menu-item v-if="hasPermission('question-bank')" index="/question-bank">
          <Icon icon="mdi:treasure-chest" />
          <template #title>题库管理</template>
        </el-menu-item>
        <el-menu-item v-if="hasPermission('paper-management')" index="/paper-management">
          <span class="menu-icon-wrapper">
            <ExamPaperIcon :size="20" />
          </span>
          <template #title>试卷管理</template>
        </el-menu-item>
        <el-menu-item v-if="hasPermission('template-market')" index="/template-market">
          <Icon icon="mdi:package-variant-closed" />
          <template #title>模板市场</template>
        </el-menu-item>
        <el-menu-item v-if="hasPermission('knowledge')" index="/knowledge">
          <Icon icon="mdi:vector-link" />
          <template #title>知识点管理</template>
        </el-menu-item>
        <el-menu-item v-if="hasPermission('knowledge-bases')" index="/knowledge-bases">
          <Icon icon="mdi:folder-open" />
          <template #title>知识库管理</template>
        </el-menu-item>
        <el-menu-item v-if="hasPermission('user-permission')" index="/user-permission">
          <Icon icon="mdi:key" />
          <template #title>用户权限</template>
        </el-menu-item>
        <el-menu-item v-if="hasPermission('settings')" index="/settings">
          <Icon icon="mdi:cog" />
          <template #title>系统设置</template>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-footer">
        <div class="collapse-btn" @click="toggleCollapse">
          <Icon :icon="isCollapse ? 'mdi:arrow-right' : 'mdi:arrow-left'" />
        </div>
      </div>
    </aside>

    <!-- 主内容区 -->
    <div class="main-wrapper">
      <!-- 顶部导航 -->
      <header class="header" role="banner">
        <div class="header-left">
          <!-- 移动端：侧边栏切换按钮 -->
          <button class="sidebar-toggle" aria-label="切换侧边栏" @click="sidebarOpen = !sidebarOpen">
            <Icon icon="mdi:menu" :size="20" />
          </button>
          <el-breadcrumb separator="/" aria-label="面包屑导航">
            <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="currentRoute">{{ currentRoute }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <div class="header-right">
          <!-- 搜索 -->
          <div class="header-search" role="search">
            <el-input
              v-model="searchQuery"
              placeholder="搜索题目、试卷..."
              clearable
              class="search-input"
              aria-label="搜索题目和试卷"
            >
              <template #prefix><Icon icon="mdi:magnify" /></template>
            </el-input>
          </div>

          <!-- 深色模式 -->
          <el-tooltip :content="isDark ? '浅色模式' : '深色模式'" placement="bottom">
            <button class="header-icon-btn" @click="toggleTheme" :aria-label="isDark ? '切换到浅色模式' : '切换到深色模式'">
              <Icon :icon="isDark ? 'mdi:weather-sunny' : 'mdi:weather-night'" :size="20" />
            </button>
          </el-tooltip>

          <!-- 消息通知 -->
          <el-popover placement="bottom-end" :width="320" trigger="click">
            <template #reference>
              <button class="header-icon-btn" aria-label="通知中心" :aria-badge="notificationStats.unread">
                <el-badge :value="notificationStats.unread" :max="99" class="badge" v-if="notificationStats.unread > 0">
                  <Icon icon="mdi:bell" :size="20" />
                </el-badge>
                <Icon v-else icon="mdi:bell" :size="20" />
              </button>
            </template>
            <div class="notification-panel">
              <div class="notification-header">
                <span class="notification-title">通知中心</span>
                <el-button type="primary" link size="small" @click="handleMarkAllRead">全部已读</el-button>
              </div>
              <div class="notification-list" v-if="notificationList.length > 0">
                <div
                  v-for="item in notificationList"
                  :key="item.id"
                  class="notification-item"
                  :class="{ unread: !item.is_read }"
                  @click="handleNotificationClick(item)"
                >
                  <div class="notification-icon" :class="item.type">
                    <Icon :icon="item.type === 'success' ? 'mdi:check-circle' : item.type === 'warning' ? 'mdi:clock' : 'mdi:information'" />
                  </div>
                  <div class="notification-content">
                    <div class="notification-text">{{ item.title }}</div>
                    <div class="notification-time">{{ formatTime(item.created_at) }}</div>
                  </div>
                  <el-button
                    type="danger"
                    link
                    size="small"
                    class="notification-delete-btn"
                    @click.stop="handleDeleteNotification(item)"
                    title="删除"
                  >
                    <Icon icon="mdi:close" />
                  </el-button>
                </div>
              </div>
              <el-empty v-else description="暂无通知" :image-size="60" />
              <div v-if="notificationStats.total > 10" class="notification-footer">
                <el-button type="primary" link size="small">
                  查看全部 {{ notificationStats.total }} 条通知
                </el-button>
              </div>
            </div>
          </el-popover>

          <!-- 用户信息 -->
          <el-dropdown trigger="click" @command="handleUserCommand">
            <button class="user-info" aria-haspopup="menu" :aria-label="`用户菜单：${authStore.user?.username || '管理员'}`">
              <el-avatar :size="36" :icon="UserFilled" class="user-avatar" aria-hidden="true" />
              <div class="user-detail">
                <span class="user-name">{{ authStore.user?.username || '管理员' }}</span>
                <span class="user-role">{{ getRoleName(authStore.user?.role) }}</span>
              </div>
              <Icon icon="mdi:chevron-down" class="user-arrow" aria-hidden="true" />
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">
                  <Icon icon="mdi:account" />个人中心
                </el-dropdown-item>
                <el-dropdown-item v-if="hasPermission('settings')" command="settings">
                  <Icon icon="mdi:cog" />账号设置
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <Icon icon="mdi:logout" />退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <!-- 页面内容 -->
      <main id="main-content" class="main-content" role="main">
        <router-view v-slot="{ Component }">
          <transition name="page-slide" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>

      <!-- 版权信息 -->
      <footer class="footer" role="contentinfo">
        <p>智题 AIQuiz © 2024-2026 技术支持</p>
      </footer>
    </div>

    <!-- 侧边栏遮罩（移动端） -->
    <div class="sidebar-overlay" :class="{ 'active': sidebarOpen }" @click="sidebarOpen = false" aria-hidden="true"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { ElMessageBox, ElMessage } from 'element-plus'
import ExamPaperIcon from '@/components/icons/ExamPaperIcon.vue'
import Icon from '@/components/common/Icon.vue'
import { notificationAPI } from '@/api'
import { UserFilled } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const themeStore = useThemeStore()

const isCollapse = ref(false)
const sidebarOpen = ref(false)
const searchQuery = ref('')
const notificationList = ref([])
const notificationStats = ref({ unread: 0, pending_audit: 0, ai_tasks_completed: 0, ai_tasks_failed: 0 })
const showPermissionDialog = ref(false)

// 通知轮询定时器（30秒刷新一次）
let notificationPollingTimer: ReturnType<typeof setInterval> | null = null
const NOTIFICATION_POLLING_INTERVAL = 30000 // 30秒

const isDark = computed(() => themeStore.isDark)
const activeMenu = computed(() => route.path)

const currentRoute = computed(() => {
  const routeMap = {
    '/dashboard': '控制台',
    '/ai-question': 'AI出题',
    '/audit': '试题审核',
    '/auto-paper': '智能组卷',
    '/question-bank': '题库管理',
    '/paper-management': '试卷管理',
    '/template-market': '模板市场',
    '/knowledge': '知识点管理',
    '/knowledge/batch': '批量导入',
    '/knowledge-bases': '知识库管理',
    '/user-permission': '用户权限',
    '/settings': '系统设置'
  }
  return routeMap[route.path]
})

// 权限判断统一委托给 authStore.hasPermission（评估 P0-7 修复）：
// - 含管理员（role=1）全权限豁免
// - 含角色默认权限回退
// 此前本地实现既无管理员豁免、也无默认回退，导致管理员菜单只剩"控制台"、
// 且与页面内 authStore.hasPermission 结果不一致。
const hasPermission = (feature) => authStore.hasPermission(feature)

const getRoleName = (role) => {
  const names = { 1: '管理员', 2: '教师', 3: '学生' }
  return names[role] || '未知'
}

const toggleCollapse = () => {
  isCollapse.value = !isCollapse.value
}

const toggleTheme = () => {
  themeStore.toggleTheme()
}

const handleUserCommand = (command) => {
  if (command === 'logout') {
    ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      type: 'warning'
    }).then(() => {
      authStore.logout()
      router.push('/login')
      ElMessage.success('已安全退出')
    }).catch(() => {})
  } else if (command === 'profile') {
    ElMessage.info('个人中心功能开发中')
  } else if (command === 'settings') {
    router.push('/settings')
  }
}

// 加载通知数据
const loadNotifications = async () => {
  try {
    const [statsRes, listRes] = await Promise.all([
      notificationAPI.getStats(),
      notificationAPI.getList({ page: 1, page_size: 10 })
    ])
    notificationStats.value = statsRes.data
    notificationList.value = listRes.data
  } catch (error) {
    console.error('加载通知失败:', error)
  }
}

// 标记全部已读
const handleMarkAllRead = async () => {
  try {
    await notificationAPI.markAllAsRead()
    notificationStats.value.unread = 0
    notificationList.value.forEach(item => item.is_read = true)
    ElMessage.success('已全部标记为已读')
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

// 点击单条通知
const handleNotificationClick = (item) => {
  if (!item.is_read) {
    notificationAPI.markAsRead(item.id)
    item.is_read = true
    notificationStats.value.unread--
  }
  if (item.link) {
    router.push(item.link)
  }
}

// 删除单条通知
const handleDeleteNotification = async (item) => {
  try {
    await notificationAPI.delete(item.id)
    notificationList.value = notificationList.value.filter(n => n.id !== item.id)
    notificationStats.value.total--
    if (!item.is_read) {
      notificationStats.value.unread--
    }
    ElMessage.success('已删除通知')
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

// 启动通知轮询
const startNotificationPolling = () => {
  if (notificationPollingTimer) return
  notificationPollingTimer = setInterval(() => {
    loadNotifications()
  }, NOTIFICATION_POLLING_INTERVAL)
}

// 停止通知轮询
const stopNotificationPolling = () => {
  if (notificationPollingTimer) {
    clearInterval(notificationPollingTimer)
    notificationPollingTimer = null
  }
}

onMounted(() => {
  loadNotifications()
  startNotificationPolling()
  // 检查是否需要显示权限提示
  if (authStore.user?.needsAdminApproval) {
    showPermissionDialog.value = true
  }
  // 检查用户是否有任何菜单权限，无权限则跳转到无权限页面
  const permissions = authStore.user?.menu_permissions
  const hasNoPermissions = !permissions
    || permissions === null
    || (typeof permissions === 'object' && Object.keys(permissions).length === 0)
    || (Array.isArray(permissions) && permissions.length === 0)
  if (hasNoPermissions && route.path !== '/no-permission') {
    router.push('/no-permission')
  }
})

onUnmounted(() => {
  stopNotificationPolling()
})

// 格式化时间
const formatTime = (timeStr) => {
  if (!timeStr) return ''
  const now = new Date()
  const time = new Date(timeStr)
  const diff = Math.floor((now - time) / 1000)
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`
  if (diff < 604800) return `${Math.floor(diff / 86400)}天前`
  return time.toLocaleDateString()
}
</script>

<style lang="scss" scoped>
.admin-layout {
  display: flex;
  min-height: 100vh;
  background: var(--surface-secondary);
  transition: background var(--transition-normal);
}

// 侧边栏
.sidebar {
  width: var(--sidebar-width);
  background: linear-gradient(180deg, #0a1628 0%, #0d1f3c 40%, #0f2847 70%, #0a1628 100%);
  display: flex;
  flex-direction: column;
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  z-index: 100;
  transition: width var(--transition-normal), transform var(--transition-normal);
  box-shadow: 2px 0 12px rgba(0, 0, 0, 0.15);

  // 移动端：默认隐藏
  @media (max-width: 767px) {
    transform: translateX(-100%);

    &.is-open {
      transform: translateX(0);
    }
  }

  &.is-collapse {
    width: var(--sidebar-collapsed-width);

    .logo-text {
      display: none;
    }
  }
}

.sidebar-header {
  height: var(--header-height);
  display: flex;
  align-items: center;
  padding: 0 var(--space-5);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.logo {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.logo-icon {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, var(--color-primary) 0%, #4080FF 100%);
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(22, 93, 255, 0.4);
}

.logo-text {
  display: flex;
  flex-direction: column;
}

.logo-title {
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: white;
  line-height: 1.2;
}

.logo-subtitle {
  font-size: var(--font-size-xs);
  color: rgba(255, 255, 255, 0.6);
  line-height: 1.2;
}

.sidebar-menu {
  flex: 1;
  border-right: none !important;
  padding: var(--space-2) 0;

  :deep(.el-menu-item) {
    height: 50px;
    line-height: 50px;
    margin: 4px 8px;
    border-radius: var(--radius-lg);

    &:hover {
      background: rgba(255, 255, 255, 0.08) !important;
    }

    &.is-active {
      background: linear-gradient(90deg, rgba(22, 93, 255, 0.2) 0%, rgba(22, 93, 255, 0.1) 100%) !important;
      color: #fff !important;
      font-weight: 500;

      &::before {
        content: '';
        position: absolute;
        left: 0;
        top: 50%;
        transform: translateY(-50%);
        width: 3px;
        height: 24px;
        background: linear-gradient(180deg, var(--color-primary) 0%, var(--color-primary-hover) 100%);
        border-radius: 0 3px 3px 0;
        box-shadow: 0 0 8px rgba(22, 93, 255, 0.5);
      }
    }
  }

  :deep(.el-icon) {
    margin-right: var(--space-3);
  }

  :deep(.menu-icon-wrapper) {
    margin-right: var(--space-3);
    display: inline-flex;
    align-items: center;
  }
}

.sidebar-footer {
  padding: var(--space-4);
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.collapse-btn {
  width: 100%;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(255, 255, 255, 0.6);
  cursor: pointer;
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
  border: 1px solid rgba(255, 255, 255, 0.1);

  &:hover {
    background: rgba(255, 255, 255, 0.08);
    color: white;
    border-color: rgba(255, 255, 255, 0.2);
  }
}

// 主内容区
.main-wrapper {
  flex: 1;
  margin-left: var(--sidebar-width);
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  transition: margin-left var(--transition-normal);

  .sidebar.is-collapse + & {
    margin-left: var(--sidebar-collapsed-width);
  }
}

.header {
  height: var(--header-height);
  background: var(--surface-primary);
  border-bottom: 1px solid var(--border-default);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-6);
  position: sticky;
  top: 0;
  z-index: 50;
  box-shadow: var(--shadow-sm);
  transition: background var(--transition-normal), border-color var(--transition-normal);

  // 移动端：减小内边距
  @media (max-width: 767px) {
    padding: 0 var(--space-3);
  }
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.sidebar-toggle {
  display: none;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-lg);
  border: none;
  background: transparent;
  cursor: pointer;
  color: var(--text-regular);
  transition: all var(--transition-fast);

  &:hover {
    background: var(--surface-tertiary);
    color: var(--color-primary);
  }

  @media (max-width: 767px) {
    display: flex;
  }
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--space-5);

  // 移动端：减小间距，隐藏搜索
  @media (max-width: 767px) {
    gap: var(--space-2);
  }
}

.header-search {
  // 移动端：隐藏搜索框
  @media (max-width: 767px) {
    display: none;
  }

  :deep(.search-input) {
    width: 240px;

    .el-input__wrapper {
      border-radius: var(--radius-full);
      background: var(--surface-secondary);
      box-shadow: none;
      border: 1px solid transparent;
      transition: all var(--transition-fast);

      &:hover, &:focus-within {
        border-color: var(--color-primary);
        background: var(--surface-primary);
      }
    }
  }
}

.header-icon-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-lg);
  cursor: pointer;
  color: var(--text-regular);
  transition: all var(--transition-fast);

  &:hover {
    background: var(--surface-secondary);
    color: var(--color-primary);
  }
}

.badge {
  :deep(.el-badge__content) {
    background: var(--color-danger);
  }
}

.notification-panel {
  margin: -12px;
}

.notification-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3) var(--space-5);
  border-bottom: 1px solid var(--border-default);
}

.notification-title {
  font-weight: 600;
  color: var(--text-primary);
}

.notification-list {
  max-height: 300px;
  overflow-y: auto;
}

.notification-item {
  display: flex;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-5);
  cursor: pointer;
  transition: background var(--transition-fast);

  &:hover {
    background: var(--surface-secondary);
  }

  &.unread {
    background: rgba(var(--color-primary-rgb), 0.05);
  }
}

.notification-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  &.success {
    background: rgba(103, 194, 58, 0.1);
    color: var(--color-success);
  }

  &.warning {
    background: rgba(230, 162, 60, 0.1);
    color: var(--color-warning);
  }

  &.info {
    background: rgba(var(--color-primary-rgb), 0.1);
    color: var(--color-primary);
  }
}

.notification-content {
  flex: 1;
}

.notification-text {
  font-size: var(--font-size-sm);
  color: var(--text-primary);
  line-height: 1.4;
}

.notification-time {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  margin-top: 4px;
}

.notification-delete-btn {
  opacity: 0;
  transition: opacity var(--transition-fast);
  flex-shrink: 0;

  .notification-item:hover & {
    opacity: 1;
  }
}

.notification-footer {
  text-align: center;
  padding: var(--space-2);
  border-top: 1px solid var(--border-default);
}

.user-info {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: background var(--transition-fast);

  &:hover {
    background: var(--surface-secondary);
  }
}

.user-avatar {
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-hover) 100%);
}

.user-detail {
  display: flex;
  flex-direction: column;

  // 移动端：隐藏用户名/角色
  @media (max-width: 767px) {
    display: none;
  }
}

.user-name {
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--text-primary);
  line-height: 1.2;
}

.user-role {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  line-height: 1.2;
}

.user-arrow {
  color: var(--text-secondary);
  margin-left: var(--space-1);
}

// 主内容
.main-content {
  flex: 1;
  padding: var(--space-6);
  background: var(--surface-secondary);
  transition: background var(--transition-normal);

  // 移动端：减小内边距
  @media (max-width: 767px) {
    padding: var(--space-3);
  }
}

// 页脚
.footer {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-top: 1px solid var(--border-default);
  background: var(--surface-primary);
  transition: background var(--transition-normal), border-color var(--transition-normal);

  p {
    font-size: var(--font-size-sm);
    color: var(--text-secondary);
    margin: 0;
  }
}

// 页面过渡
.page-slide-enter-active {
  animation: slideIn 0.3s ease forwards;
}

.page-slide-leave-active {
  animation: slideOut 0.2s ease forwards;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes slideOut {
  from {
    opacity: 1;
    transform: translateY(0);
  }
  to {
    opacity: 0;
    transform: translateY(-12px);
  }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
