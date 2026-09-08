<template>
  <div class="admin-layout" :class="{ 'dark-mode': isDark }">
    <!-- 权限不足提示 -->
    <el-dialog
      v-model="showPermissionDialog"
      title="权限提示"
      width="400px"
      :close-on-click-modal="false"
      show-close
    >
      <div style="text-align: center; padding: 20px 0;">
        <el-icon size="48" color="#E6A23C"><WarningFilled /></el-icon>
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
    <aside class="sidebar" :class="{ 'is-collapse': isCollapse }">
      <div class="sidebar-header">
        <div class="logo">
          <div class="logo-icon">
            <el-icon :size="28"><School /></el-icon>
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
          <el-icon><Odometer /></el-icon>
          <template #title>控制台</template>
        </el-menu-item>
        <el-menu-item v-if="hasPermission('ai-question')" index="/ai-question">
          <el-icon><MagicStick /></el-icon>
          <template #title>AI出题</template>
        </el-menu-item>
        <el-menu-item v-if="hasPermission('audit')" index="/audit">
          <el-icon><CircleCheck /></el-icon>
          <template #title>试题审核</template>
        </el-menu-item>
        <el-menu-item v-if="hasPermission('auto-paper')" index="/auto-paper">
          <el-icon><DocumentCopy /></el-icon>
          <template #title>智能组卷</template>
        </el-menu-item>
        <el-menu-item v-if="hasPermission('question-bank')" index="/question-bank">
          <el-icon><Collection /></el-icon>
          <template #title>题库管理</template>
        </el-menu-item>
        <el-menu-item v-if="hasPermission('paper-management')" index="/paper-management">
          <span class="menu-icon-wrapper">
            <ExamPaperIcon :size="20" />
          </span>
          <template #title>试卷管理</template>
        </el-menu-item>
        <el-menu-item v-if="hasPermission('template-market')" index="/template-market">
          <el-icon><Goods /></el-icon>
          <template #title>模板市场</template>
        </el-menu-item>
        <el-menu-item v-if="hasPermission('knowledge')" index="/knowledge">
          <el-icon><Connection /></el-icon>
          <template #title>知识点管理</template>
        </el-menu-item>
        <el-menu-item v-if="hasPermission('knowledge-bases')" index="/knowledge-bases">
          <el-icon><FolderOpened /></el-icon>
          <template #title>知识库管理</template>
        </el-menu-item>
        <el-menu-item v-if="hasPermission('user-permission')" index="/user-permission">
          <el-icon><Key /></el-icon>
          <template #title>用户权限</template>
        </el-menu-item>
        <el-menu-item v-if="hasPermission('settings')" index="/settings">
          <el-icon><Setting /></el-icon>
          <template #title>系统设置</template>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-footer">
        <div class="collapse-btn" @click="toggleCollapse">
          <el-icon v-if="isCollapse"><DArrowRight /></el-icon>
          <el-icon v-else><DArrowLeft /></el-icon>
        </div>
      </div>
    </aside>

    <!-- 主内容区 -->
    <div class="main-wrapper">
      <!-- 顶部导航 -->
      <header class="header">
        <div class="header-left">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="currentRoute">{{ currentRoute }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <div class="header-right">
          <!-- 搜索 -->
          <div class="header-search">
            <el-input
              v-model="searchQuery"
              placeholder="搜索题目、试卷..."
              clearable
              class="search-input"
            >
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>

          <!-- 深色模式 -->
          <el-tooltip :content="isDark ? '浅色模式' : '深色模式'" placement="bottom">
            <div class="header-icon-btn" @click="toggleTheme">
              <el-icon v-if="isDark" :size="20"><Sunny /></el-icon>
              <el-icon v-else :size="20"><Moon /></el-icon>
            </div>
          </el-tooltip>

          <!-- 消息通知 -->
          <el-popover placement="bottom-end" :width="320" trigger="click">
            <template #reference>
              <div class="header-icon-btn">
                <el-badge :value="notificationStats.unread" :max="99" class="badge" v-if="notificationStats.unread > 0">
                  <el-icon :size="20"><Bell /></el-icon>
                </el-badge>
                <el-icon v-else :size="20"><Bell /></el-icon>
              </div>
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
                    <el-icon><CircleCheck v-if="item.type === 'success'" /><Clock v-else-if="item.type === 'warning'" /><InfoFilled v-else /></el-icon>
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
                    <el-icon><Close /></el-icon>
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
            <div class="user-info">
              <el-avatar :size="36" :icon="UserFilled" class="user-avatar" />
              <div class="user-detail">
                <span class="user-name">{{ authStore.user?.username || '管理员' }}</span>
                <span class="user-role">{{ getRoleName(authStore.user?.role) }}</span>
              </div>
              <el-icon class="user-arrow"><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">
                  <el-icon><User /></el-icon>个人中心
                </el-dropdown-item>
                <el-dropdown-item v-if="hasPermission('settings')" command="settings">
                  <el-icon><Setting /></el-icon>账号设置
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <el-icon><SwitchButton /></el-icon>退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <!-- 页面内容 -->
      <main class="main-content">
        <router-view v-slot="{ Component }">
          <transition name="page-fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>

      <!-- 版权信息 -->
      <footer class="footer">
        <p>智题 AIQuiz © 2024-2026 技术支持</p>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { ElMessageBox, ElMessage } from 'element-plus'
import ExamPaperIcon from '@/components/icons/ExamPaperIcon.vue'
import { notificationAPI } from '@/api'
import {
  Odometer, MagicStick, CircleCheck, DocumentCopy,
  Collection, Connection, Setting, Bell, Moon, Sunny,
  UserFilled, ArrowDown, Search, DArrowLeft, DArrowRight,
  User, SwitchButton, School, Clock, InfoFilled, WarningFilled,
  Key, FolderOpened, Goods, Close
} from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const themeStore = useThemeStore()

const isCollapse = ref(false)
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
@import '@/assets/styles/variables.scss';

.admin-layout {
  display: flex;
  min-height: 100vh;
  background: $bg-page;
  transition: background $transition-base;

  &.dark-mode {
    --sidebar-bg: #{$dark-bg};
    --header-bg: #{$dark-bg-secondary};
    --content-bg: #{$dark-bg};
  }
}

// 侧边栏
.sidebar {
  width: $sidebar-width;
  background: linear-gradient(180deg, #001529 0%, #000c17 100%);
  display: flex;
  flex-direction: column;
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  z-index: 100;
  transition: width $transition-base;

  &.is-collapse {
    width: $sidebar-collapsed-width;

    .logo-text {
      display: none;
    }
  }
}

.sidebar-header {
  height: $header-height;
  display: flex;
  align-items: center;
  padding: 0 $spacing-lg;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.logo {
  display: flex;
  align-items: center;
  gap: $spacing-md;
}

.logo-icon {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, $primary-color 0%, #4080FF 100%);
  border-radius: $radius-lg;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
}

.logo-text {
  display: flex;
  flex-direction: column;
}

.logo-title {
  font-size: $font-size-lg;
  font-weight: 600;
  color: white;
  line-height: 1.2;
}

.logo-subtitle {
  font-size: $font-size-xs;
  color: rgba(255, 255, 255, 0.6);
  line-height: 1.2;
}

.sidebar-menu {
  flex: 1;
  border-right: none !important;
  padding: $spacing-sm 0;

  :deep(.el-menu-item) {
    height: 50px;
    line-height: 50px;
    margin: 4px 8px;
    border-radius: $radius-lg;

    &:hover {
      background: rgba(255, 255, 255, 0.08) !important;
    }

    &.is-active {
      background: rgba(22, 93, 255, 0.15) !important;
      color: $primary-color !important;

      &::before {
        content: '';
        position: absolute;
        left: 0;
        top: 50%;
        transform: translateY(-50%);
        width: 3px;
        height: 20px;
        background: $primary-color;
        border-radius: 0 2px 2px 0;
      }
    }
  }

  :deep(.el-icon) {
    margin-right: $spacing-md;
  }

  :deep(.menu-icon-wrapper) {
    margin-right: $spacing-md;
    display: inline-flex;
    align-items: center;
  }
}

.sidebar-footer {
  padding: $spacing-base;
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
  border-radius: $radius-md;
  transition: all $transition-fast;

  &:hover {
    background: rgba(255, 255, 255, 0.08);
    color: white;
  }
}

// 主内容区
.main-wrapper {
  flex: 1;
  margin-left: $sidebar-width;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  transition: margin-left $transition-base;

  .sidebar.is-collapse + & {
    margin-left: $sidebar-collapsed-width;
  }
}

.header {
  height: $header-height;
  background: white;
  border-bottom: 1px solid $border-light;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 $spacing-xl;
  position: sticky;
  top: 0;
  z-index: 50;
  box-shadow: $shadow-sm;
}

.header-left {
  display: flex;
  align-items: center;
}

.header-right {
  display: flex;
  align-items: center;
  gap: $spacing-lg;
}

.header-search {
  :deep(.search-input) {
    width: 240px;

    .el-input__wrapper {
      border-radius: $radius-full;
      background: $bg-page;
      box-shadow: none;
      border: 1px solid transparent;
      transition: all $transition-fast;

      &:hover, &:focus-within {
        border-color: $primary-color;
        background: white;
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
  border-radius: $radius-lg;
  cursor: pointer;
  color: $text-regular;
  transition: all $transition-fast;

  &:hover {
    background: $bg-page;
    color: $primary-color;
  }
}

.badge {
  :deep(.el-badge__content) {
    background: $danger-color;
  }
}

.notification-panel {
  margin: -12px;
}

.notification-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: $spacing-md $spacing-lg;
  border-bottom: 1px solid $border-light;
}

.notification-title {
  font-weight: 600;
  color: $text-primary;
}

.notification-list {
  max-height: 300px;
  overflow-y: auto;
}

.notification-item {
  display: flex;
  gap: $spacing-md;
  padding: $spacing-md $spacing-lg;
  cursor: pointer;
  transition: background $transition-fast;

  &:hover {
    background: $bg-page;
  }

  &.unread {
    background: rgba($primary-color, 0.05);
  }
}

.notification-icon {
  width: 32px;
  height: 32px;
  border-radius: $radius-full;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  &.success {
    background: rgba($success-color, 0.1);
    color: $success-color;
  }

  &.warning {
    background: rgba($warning-color, 0.1);
    color: $warning-color;
  }

  &.info {
    background: rgba($primary-color, 0.1);
    color: $primary-color;
  }
}

.notification-content {
  flex: 1;
}

.notification-text {
  font-size: $font-size-sm;
  color: $text-primary;
  line-height: 1.4;
}

.notification-time {
  font-size: $font-size-xs;
  color: $text-secondary;
  margin-top: 4px;
}

.notification-delete-btn {
  opacity: 0;
  transition: opacity $transition-fast;
  flex-shrink: 0;

  .notification-item:hover & {
    opacity: 1;
  }
}

.notification-footer {
  text-align: center;
  padding: $spacing-sm;
  border-top: 1px solid $border-light;
}

.user-info {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  padding: $spacing-xs $spacing-sm;
  border-radius: $radius-lg;
  cursor: pointer;
  transition: background $transition-fast;

  &:hover {
    background: $bg-page;
  }
}

.user-avatar {
  background: linear-gradient(135deg, $primary-color 0%, #4080FF 100%);
}

.user-detail {
  display: flex;
  flex-direction: column;
}

.user-name {
  font-size: $font-size-sm;
  font-weight: 500;
  color: $text-primary;
  line-height: 1.2;
}

.user-role {
  font-size: $font-size-xs;
  color: $text-secondary;
  line-height: 1.2;
}

.user-arrow {
  color: $text-secondary;
  margin-left: $spacing-xs;
}

// 主内容
.main-content {
  flex: 1;
  padding: $spacing-xl;
  background: $bg-page;
}

// 页脚
.footer {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-top: 1px solid $border-light;
  background: white;

  p {
    font-size: $font-size-sm;
    color: $text-secondary;
    margin: 0;
  }
}

// 页面过渡
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.page-fade-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.page-fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

// 深色模式适配
.dark-mode {
  .header {
    background: $dark-bg-secondary;
    border-color: $dark-border;
  }

  .header-search {
    :deep(.search-input .el-input__wrapper) {
      background: $dark-bg-tertiary;
      color: $dark-text-primary;
    }
  }

  .header-icon-btn:hover {
    background: $dark-bg-tertiary;
  }

  .user-info:hover {
    background: $dark-bg-tertiary;
  }

  .user-detail {
    .user-name {
      color: $dark-text-primary;
    }
    .user-role {
      color: $dark-text-secondary;
    }
  }

  .main-content {
    background: $dark-bg;
  }

  .footer {
    background: $dark-bg-secondary;
    border-color: $dark-border;

    p {
      color: $dark-text-secondary;
    }
  }

  .notification-header {
    border-color: $dark-border;
  }

  .notification-item:hover {
    background: $dark-bg-tertiary;
  }

  .notification-footer {
    border-color: $dark-border;
  }
}
</style>
