import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'

const routes = [
  {
    path: '/',
    redirect: '/login'
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/admin/LoginView.vue'),
    meta: { title: '登录' }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/admin/RegisterView.vue'),
    meta: { title: '注册' }
  },
  {
    path: '/no-permission',
    name: 'NoPermission',
    component: () => import('@/views/admin/NoPermissionView.vue'),
    meta: { title: '无权限' }
  },
  {
    path: '/',
    component: () => import('@/views/admin/AdminLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/dashboard'
      },
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/admin/DashboardView.vue'),
        meta: { title: '控制台', icon: 'Odometer' }
      },
      {
        path: 'ai-question',
        name: 'AIQuestion',
        component: () => import('@/views/admin/AIQuestionView.vue'),
        meta: { title: 'AI出题', icon: 'MagicStick' }
      },
      {
        path: 'audit',
        name: 'Audit',
        component: () => import('@/views/admin/AuditView.vue'),
        meta: { title: '试题审核', icon: 'CircleCheck' }
      },
      {
        path: 'auto-paper',
        name: 'AutoPaper',
        component: () => import('@/views/admin/AutoPaperView.vue'),
        meta: { title: '智能组卷', icon: 'DocumentCopy' }
      },
      {
        path: 'question-bank',
        name: 'QuestionBank',
        component: () => import('@/views/admin/QuestionBankView.vue'),
        meta: { title: '题库管理', icon: 'Collection' }
      },
      {
        path: 'paper-management',
        name: 'PaperManagement',
        component: () => import('@/views/admin/PaperManagementView.vue'),
        meta: { title: '试卷管理', icon: 'Document' }
      },
      {
        path: 'knowledge',
        name: 'Knowledge',
        component: () => import('@/views/admin/KnowledgeView.vue'),
        meta: { title: '知识点管理', icon: 'Connection' }
      },
      {
        path: 'knowledge/batch',
        name: 'BatchKnowledge',
        component: () => import('@/views/admin/BatchKnowledgeView.vue'),
        meta: { title: '批量导入', icon: 'Upload' }
      },
      {
        path: 'user-permission',
        name: 'UserPermission',
        component: () => import('@/views/admin/UserPermissionView.vue'),
        meta: { title: '用户权限', icon: 'Key' }
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/admin/SystemSettingsView.vue'),
        meta: { title: '系统设置', icon: 'Setting' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  // 设置页面标题
  if (to.meta.title) {
    document.title = `${to.meta.title} - 智题 AIQuiz`
  }

  const authStore = useAuthStore()

  // 登录页直接放行
  if (to.path === '/login') {
    next()
    return
  }

  if (to.meta.requiresAuth) {
    if (!authStore.token) {
      next({ name: 'Login' })
      return
    }

    // 用户已登录但无菜单权限 → 跳转无权限提示页
    const permissions = authStore.user?.menu_permissions
    const isNoPermissions = !permissions
      || permissions === null
      || permissions === undefined
      || (Array.isArray(permissions) && permissions.length === 0)
      || (typeof permissions === 'object' && Object.keys(permissions).length === 0)
    if (to.path !== '/no-permission' && isNoPermissions) {
      next({ name: 'NoPermission' })
      return
    }
  }

  next()
})

export default router
