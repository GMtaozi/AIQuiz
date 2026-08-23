import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/api'

export const useAuthStore = defineStore('auth', () => {
  // 认证令牌由后端 httpOnly cookie 承载（JS 不可读，防 XSS 窃取），
  // 前端仅缓存非敏感的用户信息用于渲染与权限判断。
  // 评估修复：localStorage 数据损坏时 JSON.parse 抛异常会导致整页白屏，加 try/catch 兜底
  let cachedUser = null
  try {
    cachedUser = JSON.parse(localStorage.getItem('user') || 'null')
  } catch {
    cachedUser = null
  }
  const user = ref(cachedUser)

  const isLoggedIn = computed(() => !!user.value)
  const isAdmin = computed(() => user.value?.role === 1)

  async function login(username, password) {
    try {
      const response = await api.post('/auth/login/json', { username, password })

      // 登录成功后 cookie 已由后端 Set-Cookie 种下，这里获取完整用户信息
      const userResponse = await api.get('/auth/me')
      user.value = {
        id: userResponse.data.id,
        username: userResponse.data.username,
        email: userResponse.data.email,
        role: userResponse.data.role,
        menu_permissions: response.data.menu_permissions || {},
        needsAdminApproval: response.data.needs_admin_approval || false
      }
      localStorage.setItem('user', JSON.stringify(user.value))
      localStorage.removeItem('token') // 清理历史版本遗留的 localStorage token
      return { success: true }
    } catch (error) {
      return { success: false, message: error.response?.data?.message || error.response?.data?.detail || '登录失败' }
    }
  }

  function logout() {
    user.value = null
    localStorage.removeItem('user')
    localStorage.removeItem('token')
    // 尽力通知后端清除 httpOnly cookie（失败不影响本地登出）
    api.post('/auth/logout').catch(() => {})
  }

  function hasPermission(permission) {
    if (!user.value) return false
    // 管理员拥有所有权限
    if (user.value.role === 1) return true
    // 权限单一来源：后端登录时下发有效权限（扁平数组），前端不再维护角色默认表
    const userPerms = user.value.menu_permissions
    if (Array.isArray(userPerms)) {
      return userPerms.includes(permission)
    }
    if (typeof userPerms === 'object' && userPerms !== null) {
      const roleKey = String(user.value.role)
      const perms = userPerms[roleKey] || userPerms[user.value.role] || []
      return Array.isArray(perms) ? perms.includes(permission) : false
    }
    return false
  }

  return {
    user,
    isLoggedIn,
    isAdmin,
    login,
    logout,
    hasPermission
  }
})
