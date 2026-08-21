import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/api'

// Simple XOR encryption for localStorage token (not as secure as proper encryption,
// but better than plain text. In production, use httpOnly cookies instead.)
const ENCRYPTION_KEY = '__secure_storage_key__'

function xorEncrypt(text, key) {
  if (!text) return ''
  let result = ''
  for (let i = 0; i < text.length; i++) {
    result += String.fromCharCode(text.charCodeAt(i) ^ key.charCodeAt(i % key.length))
  }
  return btoa(result)
}

function xorDecrypt(encoded, key) {
  if (!encoded) return ''
  try {
    const text = atob(encoded)
    let result = ''
    for (let i = 0; i < text.length; i++) {
      result += String.fromCharCode(text.charCodeAt(i) ^ key.charCodeAt(i % key.length))
    }
    return result
  } catch {
    return ''
  }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(xorDecrypt(localStorage.getItem('token') || '', ENCRYPTION_KEY))
  // 评估修复：localStorage 数据损坏时 JSON.parse 抛异常会导致整页白屏，加 try/catch 兜底
  let cachedUser = null
  try {
    cachedUser = JSON.parse(localStorage.getItem('user') || 'null')
  } catch {
    cachedUser = null
  }
  const user = ref(cachedUser)

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 1)

  async function login(username, password) {
    try {
      const response = await api.post('/auth/login/json', { username, password })
      token.value = response.data.access_token

      // 获取完整用户信息
      try {
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
      } catch {
        // 如果获取用户信息失败，至少使用JWT中的信息
        const payload = response.data.access_token.split('.')[1]
        const decoded = JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')))
        user.value = {
          id: decoded.sub,
          role: decoded.role || 3,
          menu_permissions: response.data.menu_permissions || {},
          needsAdminApproval: response.data.needs_admin_approval || false
        }
        localStorage.setItem('user', JSON.stringify(user.value))
      }
      // Store encrypted token
      localStorage.setItem('token', xorEncrypt(token.value, ENCRYPTION_KEY))
      return { success: true }
    } catch (error) {
      return { success: false, message: error.response?.data?.message || error.response?.data?.detail || '登录失败' }
    }
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  function getDefaultPermissions(role) {
    // 评估 P0-7：单一默认权限来源（与菜单/路由 meta.permission 对齐）
    const defaults = {
      1: ['ai-question', 'audit', 'auto-paper', 'question-bank', 'paper-management', 'template-market', 'knowledge', 'knowledge-bases', 'settings', 'user-permission'],
      2: ['ai-question', 'audit', 'auto-paper', 'question-bank', 'paper-management', 'template-market', 'knowledge', 'knowledge-bases'],
      3: ['audit', 'question-bank']
    }
    return defaults[role] || defaults[3]
  }

  function hasPermission(permission) {
    if (!user.value) return false
    // 管理员拥有所有权限
    if (user.value.role === 1) return true
    // 获取用户实际权限
    const userPerms = user.value.menu_permissions
    if (Array.isArray(userPerms)) {
      return userPerms.includes(permission)
    }
    if (typeof userPerms === 'object' && userPerms !== null) {
      const roleKey = String(user.value.role)
      const perms = userPerms[roleKey] || userPerms[user.value.role] || []
      return Array.isArray(perms) ? perms.includes(permission) : false
    }
    // 如果没有个性化权限，使用默认权限
    const defaultPerms = getDefaultPermissions(user.value.role)
    return defaultPerms.includes(permission)
  }

  return {
    token,
    user,
    isLoggedIn,
    isAdmin,
    login,
    logout,
    getDefaultPermissions,
    hasPermission
  }
})
