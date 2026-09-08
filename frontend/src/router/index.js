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
    // 学生区：不依赖菜单权限（后端按考生名单归属校验）
    path: '/student',
    component: () => import('@/views/student/StudentLayout.vue'),
    meta: { requiresAuth: true, studentArea: true },
    children: [
      {
        path: '',
        redirect: '/student/exams'
      },
      {
        path: 'exams',
        name: 'StudentExams',
        component: () => import('@/views/student/StudentExamListView.vue'),
        meta: { title: '考试中心' }
      },
      {
        path: 'exams/:id',
        name: 'StudentExamTaking',
        component: () => import('@/views/student/StudentExamTakingView.vue'),
        meta: { title: '在线作答' }
      },
      {
        path: 'scores',
        name: 'StudentScores',
        component: () => import('@/views/student/StudentScoresView.vue'),
        meta: { title: '我的成绩' }
      }
    ]
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
        meta: { title: '控制台', icon: 'Odometer', permission: null }
      },
      {
        path: 'ai-question',
        name: 'AIQuestion',
        component: () => import('@/views/admin/AIQuestionView.vue'),
        meta: { title: 'AI出题', icon: 'MagicStick', permission: 'ai-question' }
      },
      {
        path: 'audit',
        name: 'Audit',
        component: () => import('@/views/admin/AuditView.vue'),
        meta: { title: '试题审核', icon: 'CircleCheck', permission: 'audit' }
      },
      {
        path: 'auto-paper',
        name: 'AutoPaper',
        component: () => import('@/views/admin/AutoPaperView.vue'),
        meta: { title: '智能组卷', icon: 'DocumentCopy', permission: 'auto-paper' }
      },
      {
        path: 'question-bank',
        name: 'QuestionBank',
        component: () => import('@/views/admin/QuestionBankView.vue'),
        meta: { title: '题库管理', icon: 'Collection', permission: 'question-bank' }
      },
      {
        path: 'paper-management',
        name: 'PaperManagement',
        component: () => import('@/views/admin/PaperManagementView.vue'),
        meta: { title: '试卷管理', icon: 'Document', permission: 'paper-management' }
      },
      {
        path: 'template-market',
        name: 'TemplateMarket',
        component: () => import('@/views/admin/TemplateMarketView.vue'),
        meta: { title: '模板市场', icon: 'Goods', permission: 'template-market' }
      },
      {
        path: 'knowledge',
        name: 'Knowledge',
        component: () => import('@/views/admin/KnowledgeView.vue'),
        meta: { title: '知识点管理', icon: 'Connection', permission: 'knowledge' }
      },
      {
        path: 'knowledge-bases',
        name: 'KnowledgeBases',
        component: () => import('@/views/admin/KnowledgeBaseView.vue'),
        meta: { title: '知识库管理', icon: 'FolderOpened', permission: 'knowledge-bases' }
      },
      {
        path: 'knowledge/batch',
        name: 'BatchKnowledge',
        component: () => import('@/views/admin/BatchKnowledgeView.vue'),
        meta: { title: '批量导入', icon: 'Upload', permission: 'knowledge' }
      },
      {
        path: 'user-permission',
        name: 'UserPermission',
        component: () => import('@/views/admin/UserPermissionView.vue'),
        meta: { title: '用户权限', icon: 'Key', permission: 'user-permission' }
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/admin/SystemSettingsView.vue'),
        meta: { title: '系统设置', icon: 'Setting', permission: 'settings' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  // 路由切换时滚动到顶部
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) {
      return savedPosition
    }
    return { top: 0, behavior: 'smooth' }
  }
})

// 路由守卫
router.beforeEach((to, from, next) => {
  // 设置页面标题
  if (to.meta.title) {
    document.title = `${to.meta.title} - 智题 AIQuiz`
  }

  const authStore = useAuthStore()

  // 登录/注册页直接放行
  if (to.path === '/login' || to.path === '/register') {
    next()
    return
  }

  if (to.meta.requiresAuth) {
    if (!authStore.isLoggedIn) {
      next({ name: 'Login' })
      return
    }

    // 学生区跳过菜单权限校验（role=3 默认无管理端权限；
    // 考试可见性由后端按考生名单/时间窗校验）
    if (to.meta.studentArea) {
      next()
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

    // 评估 P0-7 修复：逐路由校验所需菜单权限（此前只判断"有无任何权限"，
    // 导致仅拥有 audit 权限的用户可 URL 直达 /settings、/user-permission 等）
    if (to.meta.permission && !authStore.hasPermission(to.meta.permission)) {
      next({ name: 'NoPermission' })
      return
    }
  }

  next()
})

export default router
