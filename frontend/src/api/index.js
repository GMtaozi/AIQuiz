import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000,  // 5分钟超时，用于AI出题等长时间操作
  headers: {
    'Content-Type': 'application/json'
  }
})

api.interceptors.request.use(
  config => {
    const authStore = useAuthStore()
    if (authStore.token) {
      config.headers.Authorization = `Bearer ${authStore.token}`
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      const authStore = useAuthStore()
      authStore.logout()
      window.location.href = '/login'
    }
    // Don't expose internal error details
    if (error.response?.data?.detail) {
      const detail = error.response.data.detail
      // FastAPI 422 验证错误返回 [{loc, msg, type}, ...] 数组
      if (Array.isArray(detail)) {
        const msgs = detail.map(d => d.msg || JSON.stringify(d)).join('; ')
        return Promise.reject(new Error(msgs))
      }
      return Promise.reject(new Error(String(detail)))
    }
    console.error('API Error:', error.config?.url, error.response?.status, error.response?.data)
    return Promise.reject(error)
  }
)

export { api }

// 认证相关
export const authAPI = {
  login: (data) => api.post('/auth/login/json', data),
  logout: () => api.post('/auth/logout'),
  getUser: () => api.get('/auth/me'),
  register: (data) => api.post('/auth/register', data),
  forgotPassword: (username) => api.post('/auth/forgot-password', { username })
}

// 管理员相关
export const adminAPI = {
  getQuestions: (params) => api.get('/questions/', { params }),
  createQuestion: (data) => api.post('/questions/', data),
  updateQuestion: (id, data) => api.put(`/questions/${id}`, data),
  deleteQuestion: (id) => api.delete(`/questions/${id}`),
  batchDeleteQuestions: (ids) => api.post('/questions/batch-delete', { ids }),
  batchUpdateQuestionStatus: (ids, data) => api.put('/questions/batch-status', { ids, ...data }),
  generateQuestions: (data) => api.post('/ai/generate', data),
  hybridGenerate: (data) => api.post('/ai/hybrid-generate', data),
  hybridGenerateAsync: (data) => api.post('/ai/hybrid-generate-async', data),
  getTaskProgress: (taskId) => api.get(`/ai/task/${taskId}/progress`),
  listTasks: (params) => api.get('/ai/tasks', { params }),
  getPapers: (params) => api.get('/papers/', { params }),
  getPaperById: (id) => api.get(`/papers/${id}`),
  createPaper: (data) => api.post('/papers/', data),
  updatePaper: (id, data) => api.put(`/papers/${id}`, data),
  deletePaper: (id) => api.delete(`/papers/${id}`),
  exportQuestions: (params) => api.get('/questions/export', { params, responseType: 'blob' }),
}

// AI 出题相关
export const aiAPI = {
  generateQuestions: (data) => api.post('/question/generate', data),
  getGenerateStatus: (taskId) => api.get(`/question/generate/${taskId}/status`),
  getGenerateResult: (taskId) => api.get(`/question/generate/${taskId}/result`)
}

// 试题审核相关
export const auditAPI = {
  getPendingQuestions: (params) => api.get('/audit/pending', { params }),
  approveQuestion: (id) => api.post(`/audit/${id}/approve`),
  rejectQuestion: (id, data) => api.post(`/audit/${id}/reject`, data),
  batchApprove: (ids) => api.post('/audit/batch/approve', { ids }),
  batchReject: (data) => api.post('/audit/batch/reject', data),
  getPending: (params) => api.get('/audit/pending', { params }),
  approve: (id) => api.post(`/audit/${id}/approve`),
  reject: (id, reason) => api.post(`/audit/${id}/reject`, { reason }),
  review: (id, action, reason = '') => api.post(`/audit/${id}/review`, { action, reason })
}

// 智能组卷相关
export const paperAPI = {
  autoGenerate: (data) => api.post('/papers/auto-generate', data),
  getAutoGeneratePreview: (data) => api.post('/papers/auto-generate/preview', data),
  getDifficultyDistribution: (data) => api.post('/papers/difficulty-distribution', data),
  saveAsTemplate: (data) => api.post('/papers/templates', data),
  getTemplates: () => api.get('/papers/templates'),
  getGenerateProgress: (taskId) => api.get(`/papers/generate/${taskId}/progress`)
}

// 知识点管理
export const knowledgeAPI = {
  getTrees: () => api.get('/knowledge/trees'),
  getHierarchyTrees: (params) => api.get('/knowledge/hierarchy-trees', { params }),
  getQuestionCounts: (knowledgeIds) => api.post('/knowledge/question-counts', { knowledge_ids: knowledgeIds }),
  createNode: (data) => {
    const payload = {
      name: data.name,
      parent_id: data.parentId || null,
      category_id: data.categoryId || null,
      exam_type_id: data.examTypeId || null,
      description: data.description || null,
      order: data.sortOrder || 0
    }
    return api.post('/knowledge/', payload)
  },
  updateNode: (id, data) => {
    const payload = {
      name: data.name,
      parent_id: data.parentId || null,
      category_id: data.categoryId || null,
      exam_type_id: data.examTypeId || null,
      description: data.description || null,
      order: data.sortOrder || 0
    }
    return api.put(`/knowledge/${id}`, payload)
  },
  deleteNode: (id) => api.delete(`/knowledge/${id}`),
  getNodesByCategory: (category) => api.get(`/knowledge/category/${category}`),
  // AI 智能导入
  aiAnalyze: (formData) => api.post('/knowledge/ai/analyze', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  // 规则解析导入（零AI调用，毫秒级）
  ruleAnalyze: (formData) => api.post('/knowledge/rule/analyze', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  aiImport: (knowledgePoints, category, examType, parentId, documentName) => api.post('/knowledge/ai/import', {
    knowledge_points: knowledgePoints,
    category: typeof category === 'string' ? category : 'default',
    category_id: typeof category === 'number' ? category : null,
    exam_type: typeof examType === 'string' ? examType : null,
    exam_type_id: typeof examType === 'number' ? examType : null,
    parent_id: parentId,
    document_name: documentName || null
  }),
  aiPreview: (formData) => api.post('/knowledge/ai/preview', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  // 批量处理
  batchAnalyze: (formData) => api.post('/knowledge/batch/analyze', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  batchImport: (data) => api.post('/knowledge/batch/import', data)
}

// 题库管理 (扩展现有)
export const questionBankAPI = {
  getQuestions: (params) => api.get('/questions/', { params }),
  createQuestion: (data) => api.post('/questions/', data),
  updateQuestion: (id, data) => api.put(`/questions/${id}`, data),
  deleteQuestion: (id) => api.delete(`/questions/${id}`),
  importQuestions: (file, format = 'excel', subjectId = null, chapterId = null) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('format', format)
    if (subjectId) formData.append('subject_id', subjectId)
    if (chapterId) formData.append('chapter_id', chapterId)
    return api.post('/questions/import', formData, {
      headers: { 'Content-Type': undefined }  // 让 axios 自动处理 multipart
    })
  },
  previewImport: (formData) => {
    return api.post('/questions/preview', formData, {
      headers: { 'Content-Type': undefined }
    })
  },
  exportQuestions: (params) => api.get('/questions/export', { params, responseType: 'blob' }),
  getQuestionDetail: (id) => api.get(`/questions/${id}`),
  getStatistics: () => api.get('/questions/statistics')
}

// 科目管理
export const subjectAPI = {
  getSubjects: () => api.get('/subjects/'),
  createSubject: (data) => api.post('/subjects/', data),
  updateSubject: (id, data) => api.put(`/subjects/${id}`, data),
  deleteSubject: (id) => api.delete(`/subjects/${id}`)
}

// 系统设置
export const systemAPI = {
  getSettings: () => api.get('/system/settings'),
  updateSettings: (data) => api.put('/system/settings', data),
  // AI配置
  getAiConfig: () => api.get('/system/ai-config'),
  updateAiConfig: (data) => api.put('/system/ai-config', data),
  testAiConnection: () => api.post('/system/ai-config/test'),
  // 角色权限配置
  getRolePermissions: () => api.get('/system/role-permissions'),
  updateRolePermissions: (role, permissions) => api.put(`/system/role-permissions/${role}`, { role, permissions }),
  // 考试种类
  getExamCategories: () => api.get('/system/exam-categories'),
  createExamCategory: (data) => api.post('/system/exam-categories', data),
  updateExamCategory: (id, data) => api.put(`/system/exam-categories/${id}`, data),
  deleteExamCategory: (id) => api.delete(`/system/exam-categories/${id}`),
  // 考试科目
  getExamTypes: (params) => api.get('/system/exam-types', { params }),
  createExamType: (data) => api.post('/system/exam-types', data),
  updateExamType: (id, data) => api.put(`/system/exam-types/${id}`, data),
  deleteExamType: (id) => api.delete(`/system/exam-types/${id}`),
  // 用户管理
  getUsers: (params) => api.get('/system/users', { params }),
  createUser: (data) => api.post('/system/users', data),
  updateUser: (id, data) => api.put(`/system/users/${id}`, data),
  deleteUser: (id) => api.delete(`/system/users/${id}`),
  resetPassword: (id, data) => api.post(`/system/users/${id}/reset-password`, data),
  // 密码重置申请管理
  getPasswordResetRequests: (params) => api.get('/system/password-reset-requests', { params }),
  processPasswordResetRequest: (id, data) => api.post(`/system/password-reset-requests/${id}/process`, data),
  deletePasswordResetRequest: (id) => api.delete(`/system/password-reset-requests/${id}`),
  changeRole: (id, role) => api.put(`/system/users/${id}/permissions`, { role }),
  // 用户权限管理
  updateUserPermissions: (id, data) => api.put(`/system/users/${id}/permissions`, data),
  batchUpdateRolePermissions: (role, permissions) => api.put(`/system/users/batch-role-permissions/${role}`, { permissions })
}

// 仪表盘统计
export const dashboardAPI = {
  getOverview: () => api.get('/dashboard/overview'),
  getQuestionTrend: (params) => api.get('/dashboard/question-trend', { params }),
  getExamTrend: (params) => api.get('/dashboard/exam-trend', { params }),
  getRecentActivity: () => api.get('/dashboard/recent-activity')
}

// 通知
export const notificationAPI = {
  getList: (params) => api.get('/notifications', { params }),
  getStats: () => api.get('/notifications/stats'),
  markAsRead: (id) => api.put(`/notifications/${id}/read`),
  markAllAsRead: () => api.put('/notifications/read-all'),
  delete: (id) => api.delete(`/notifications/${id}`)
}
