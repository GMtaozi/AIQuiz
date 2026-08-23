import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { systemAPI } from '@/api'

// ============ Types ============
export interface User {
  id: number
  username: string
  email: string
  role: number
  status: number
  custom_permissions?: string[]
  last_login?: string
}

export interface RoleOption {
  value: number
  label: string
  icon: string
  bg: string
}

export interface PermissionModule {
  key: string
  name: string
  description: string
  icon: string
}

export interface BatchForm {
  role: number | null
  template: number
  permissions: string[]
}

// ============ Constants ============
export const roleOptions: RoleOption[] = [
  { value: 1, label: '管理员', icon: 'UserFilled', bg: 'linear-gradient(135deg, #165DFF 0%, #3B82F6 100%)' },
  { value: 2, label: '题库编辑', icon: 'School', bg: 'linear-gradient(135deg, #10B981 0%, #34D399 100%)' },
  // 评估 P2-14：原角色3紫色渐变违反 DESIGN.md「Don't use purple gradient」，改为中性灰
  { value: 3, label: '审核员', icon: 'User', bg: 'linear-gradient(135deg, #909399 0%, #A8ABB2 100%)' }
]

export const permissionModules: PermissionModule[] = [
  { key: 'dashboard', name: '控制台', description: '系统仪表盘和数据概览', icon: 'Odometer' },
  { key: 'ai-question', name: 'AI出题', description: '使用AI生成试题', icon: 'MagicStick' },
  { key: 'audit', name: '试题审核', description: '审核和管理试题', icon: 'CircleCheck' },
  { key: 'auto-paper', name: '智能组卷', description: '自动生成试卷', icon: 'DocumentCopy' },
  { key: 'question-bank', name: '题库管理', description: '管理题库资源', icon: 'Collection' },
  { key: 'paper-management', name: '试卷管理', description: '管理试卷文件', icon: 'Document' },
  { key: 'template-market', name: '模板市场', description: '查看与使用试卷模板', icon: 'Goods' },
  { key: 'knowledge', name: '知识点管理', description: '管理知识点结构', icon: 'Connection' },
  { key: 'knowledge-bases', name: '知识库管理', description: '管理文档知识库', icon: 'FolderOpened' },
  { key: 'user-permission', name: '用户权限', description: '分配用户与角色权限', icon: 'Key' },
  { key: 'settings', name: '系统设置', description: '系统配置和管理', icon: 'Setting' }
]

// 角色默认权限模板（UI 展示用）。权威来源是后端 app/models/user.py 的
// ROLE_DEFAULT_PERMISSIONS；商业化决策已定 role=3 为"学生"，管理端菜单一律不放行。
export const roleDefaultPermissions: Record<number, string[]> = {
  1: ['ai-question', 'audit', 'auto-paper', 'question-bank', 'paper-management', 'template-market', 'knowledge', 'knowledge-bases', 'settings', 'user-permission'],
  2: ['ai-question', 'audit', 'auto-paper', 'question-bank', 'paper-management', 'template-market', 'knowledge', 'knowledge-bases'],
  3: []
}

// ============ State ============
export const loading = ref(false)
export const saving = ref(false)
export const deleteLoading = ref(false)
export const allUsers = ref<User[]>([])
export const searchQuery = ref('')
export const filterRole = ref<number | null>(null)
export const selectedUser = ref<User | null>(null)
export const customEnabled = ref(false)
export const selectAll = ref(false)
export const batchDialogVisible = ref(false)
export const batchForm = reactive<BatchForm>({
  role: null,
  template: 1,
  permissions: []
})

// ============ Computed ============
export const filteredUsers = computed(() => {
  return allUsers.value.filter(user => {
    const matchSearch = !searchQuery.value ||
      user.username.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      user.email.toLowerCase().includes(searchQuery.value.toLowerCase())
    const matchRole = !filterRole.value || user.role === filterRole.value
    return matchSearch && matchRole
  })
})

export const effectivePermissions = computed(() => {
  if (!selectedUser.value) return []
  const role = selectedUser.value.role
  if (customEnabled.value && selectedUser.value.custom_permissions) {
    return selectedUser.value.custom_permissions
  }
  return roleDefaultPermissions[role] || []
})

export const isIndeterminate = computed(() => {
  if (!selectedUser.value?.custom_permissions) return false
  const permCount = selectedUser.value.custom_permissions.length
  return permCount > 0 && permCount < permissionModules.length
})

// ============ Helper Functions ============
export const userCountByRole = (role: number) => {
  return allUsers.value.filter(u => u.role === role).length
}

export const hasCustomPermissions = (user: User) => {
  return user.custom_permissions && user.custom_permissions.length > 0
}

export const isGranted = (key: string) => {
  if (!selectedUser.value) return false
  if (customEnabled.value) {
    return selectedUser.value.custom_permissions?.includes(key) || false
  }
  return roleDefaultPermissions[selectedUser.value.role]?.includes(key) || false
}

export const isInherited = (key: string) => {
  return roleDefaultPermissions[selectedUser.value?.role as number]?.includes(key) || false
}

export const isCustom = (key: string) => {
  return selectedUser.value?.custom_permissions?.includes(key) || false
}

export const getRoleName = (role: number) => {
  const names: Record<number, string> = { 1: '管理员', 2: '教师', 3: '学生' }
  return names[role] || '未知'
}

export const getAvatarBg = (role: number) => {
  const bgs: Record<number, string> = {
    1: 'linear-gradient(135deg, #165DFF 0%, #3B82F6 100%)',
    2: 'linear-gradient(135deg, #10B981 0%, #34D399 100%)',
    3: 'linear-gradient(135deg, #909399 0%, #A8ABB2 100%)'  // 评估 P2-14：紫色 → 中性灰
  }
  return bgs[role] || bgs[3]
}

export const getPermBg = (key: string) => {
  const colors: Record<string, string> = {
    'dashboard': 'rgba(22, 93, 255, 0.1)',
    'ai-question': 'rgba(139, 92, 246, 0.1)',
    'audit': 'rgba(16, 185, 129, 0.1)',
    'auto-paper': 'rgba(245, 158, 11, 0.1)',
    'question-bank': 'rgba(6, 182, 212, 0.1)',
    'paper-management': 'rgba(239, 68, 68, 0.1)',
    'knowledge': 'rgba(14, 165, 233, 0.1)',
    'settings': 'rgba(107, 114, 128, 0.1)'
  }
  return colors[key] || 'rgba(107, 114, 128, 0.1)'
}

export const formatDate = (dateStr: string | null | undefined): string => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN')
}

export const formatTimeAgo = (dateStr: string | null | undefined): string => {
  if (!dateStr) return '从未登录'
  const now = new Date()
  const date = new Date(dateStr)
  const diff = Math.floor((now.getTime() - date.getTime()) / 1000)
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`
  if (diff < 604800) return `${Math.floor(diff / 86400)}天前`
  return formatDate(dateStr)
}

// ============ Actions ============
export const loadUsers = async () => {
  loading.value = true
  try {
    const res = await systemAPI.getUsers()
    allUsers.value = res.data?.items || res.data || []
  } catch (err) {
    console.error('加载用户失败:', err)
    ElMessage.error('加载用户列表失败')
  } finally {
    loading.value = false
  }
}

export const selectUser = (user: User) => {
  selectedUser.value = { ...user }
  customEnabled.value = hasCustomPermissions(user) as boolean
  updateSelectAll()
}

export const handleCustomToggle = (enabled: boolean) => {
  if (enabled) {
    if (!selectedUser.value?.custom_permissions || selectedUser.value.custom_permissions.length === 0) {
      selectedUser.value!.custom_permissions = [...(roleDefaultPermissions[selectedUser.value!.role] || [])]
    }
  }
  updateSelectAll()
}

export const togglePermission = (key: string) => {
  if (!customEnabled.value || !selectedUser.value) return
  const perms = selectedUser.value.custom_permissions || []
  const idx = perms.indexOf(key)
  if (idx === -1) {
    perms.push(key)
  } else {
    perms.splice(idx, 1)
  }
  selectedUser.value.custom_permissions = perms
  updateSelectAll()
}

export const handleSelectAll = (checked: boolean) => {
  if (!selectedUser.value) return
  selectedUser.value.custom_permissions = checked
    ? permissionModules.map(p => p.key)
    : []
}

export const updateSelectAll = () => {
  if (!selectedUser.value?.custom_permissions) {
    selectAll.value = false
    return
  }
  selectAll.value = selectedUser.value.custom_permissions.length === permissionModules.length
}

export const resetToRoleDefault = () => {
  if (!selectedUser.value) return
  selectedUser.value.custom_permissions = [...(roleDefaultPermissions[selectedUser.value.role] || [])]
  ElMessage.success('已重置为角色默认权限')
  updateSelectAll()
}

export const savePermissions = async () => {
  if (!selectedUser.value) return
  saving.value = true
  try {
    await systemAPI.updateUserPermissions(selectedUser.value.id, {
      custom_permissions: customEnabled.value ? selectedUser.value.custom_permissions : null,
      role: selectedUser.value.role,
      status: selectedUser.value.status
    })

    const idx = allUsers.value.findIndex(u => u.id === selectedUser.value!.id)
    if (idx !== -1) {
      allUsers.value[idx] = {
        ...allUsers.value[idx],
        role: selectedUser.value.role,
        status: selectedUser.value.status,
        custom_permissions: (customEnabled.value ? selectedUser.value.custom_permissions : null) as string[] | undefined
      }
    }

    ElMessage.success('权限配置已保存')
  } catch (err) {
    console.error('保存失败:', err)
    ElMessage.error('保存权限配置失败')
  } finally {
    saving.value = false
  }
}

export const handleStatusChange = () => {
  if (!selectedUser.value) return
  ElMessage.success(`账号已${selectedUser.value.status === 1 ? '启用' : '禁用'}`)
}

export const handleDeleteUser = async () => {
  if (!selectedUser.value) return

  try {
    await ElMessageBox.confirm(
      `确定要删除用户 "${selectedUser.value.username}" 吗？删除后将禁用该账号。`,
      '删除确认',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger'
      }
    )

    deleteLoading.value = true
    await systemAPI.deleteUser(selectedUser.value.id)

    const user = allUsers.value.find(u => u.id === selectedUser.value!.id)
    if (user) {
      user.status = 0
    }
    selectedUser.value.status = 0

    ElMessage.success('用户已删除')
  } catch (err) {
    if (err !== 'cancel') {
      console.error('删除失败:', err)
      ElMessage.error('删除用户失败')
    }
  } finally {
    deleteLoading.value = false
  }
}

export const handleRoleChange = async (newRole: number) => {
  if (!selectedUser.value || selectedUser.value.role === newRole) return
  try {
    await systemAPI.updateUserPermissions(selectedUser.value.id, {
      role: newRole,
      custom_permissions: customEnabled.value ? selectedUser.value.custom_permissions : null,
      status: selectedUser.value.status
    })
    selectedUser.value.role = newRole
    if (customEnabled.value) {
      selectedUser.value.custom_permissions = [...(roleDefaultPermissions[newRole] || [])]
    }
    ElMessage.success(`已切换为${getRoleName(newRole)}角色`)
  } catch (err) {
    console.error('切换角色失败:', err)
    ElMessage.error('切换角色失败')
  }
}

export const handleBatchSet = () => {
  batchForm.role = null
  batchForm.template = 1
  batchForm.permissions = []
  batchDialogVisible.value = true
}

export const confirmBatchSet = async () => {
  if (!batchForm.role) {
    ElMessage.warning('请选择目标角色')
    return
  }

  const perms = batchForm.template === 0
    ? batchForm.permissions
    : roleDefaultPermissions[batchForm.template]

  try {
    await systemAPI.batchUpdateRolePermissions(batchForm.role, perms)

    allUsers.value.forEach(user => {
      if (user.role === batchForm.role) {
        user.custom_permissions = [...perms]
      }
    })

    batchDialogVisible.value = false
    ElMessage.success(`已为所有${getRoleName(batchForm.role)}用户批量设置权限`)
  } catch (err) {
    console.error('批量设置失败:', err)
    ElMessage.error('批量设置权限失败')
  }
}

// ============ Composable ============
export function useUserPermission() {
  return {
    // State
    loading,
    saving,
    deleteLoading,
    allUsers,
    searchQuery,
    filterRole,
    selectedUser,
    customEnabled,
    selectAll,
    batchDialogVisible,
    batchForm,
    // Constants
    roleOptions,
    permissionModules,
    roleDefaultPermissions,
    // Computed
    filteredUsers,
    effectivePermissions,
    isIndeterminate,
    // Actions
    loadUsers,
    selectUser,
    handleCustomToggle,
    togglePermission,
    handleSelectAll,
    updateSelectAll,
    resetToRoleDefault,
    savePermissions,
    handleStatusChange,
    handleDeleteUser,
    handleRoleChange,
    handleBatchSet,
    confirmBatchSet,
    // Helpers
    userCountByRole,
    hasCustomPermissions,
    isGranted,
    isInherited,
    isCustom,
    getRoleName,
    getAvatarBg,
    getPermBg,
    formatDate,
    formatTimeAgo,
    // Lifecycle
    initialize: onMounted(() => {
      loadUsers()
    })
  }
}
