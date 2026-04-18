<template>
  <div class="permission-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h2 class="page-title">
          <el-icon class="title-icon"><Key /></el-icon>
          用户权限管理
        </h2>
        <p class="page-desc">为用户分配菜单访问权限，支持批量操作与个性化配置</p>
      </div>
      <div class="header-actions">
        <el-button @click="handleBatchSet">
          <el-icon><Setting /></el-icon>
          批量设置
        </el-button>
        <el-button type="primary" @click="loadUsers" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 主内容区：左右分栏 -->
    <div class="main-container">
      <!-- 左侧：用户列表 -->
      <div class="user-list-panel">
        <!-- 搜索和筛选 -->
        <div class="list-toolbar">
          <el-input
            v-model="searchQuery"
            placeholder="搜索用户名、邮箱..."
            prefix-icon="Search"
            clearable
            class="search-input"
          />
          <el-select v-model="filterRole" placeholder="筛选角色" clearable class="role-filter">
            <el-option label="全部角色" :value="null" />
            <el-option label="管理员" :value="1" />
            <el-option label="题库编辑" :value="2" />
            <el-option label="审核员" :value="3" />
          </el-select>
        </div>

        <!-- 用户统计 -->
        <div class="user-stats">
          <div class="stat-item">
            <span class="stat-value">{{ allUsers.length }}</span>
            <span class="stat-label">全部用户</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">{{ userCountByRole(1) }}</span>
            <span class="stat-label">管理员</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">{{ userCountByRole(2) }}</span>
            <span class="stat-label">题库编辑</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">{{ userCountByRole(3) }}</span>
            <span class="stat-label">审核员</span>
          </div>
        </div>

        <!-- 用户列表 -->
        <div class="user-list" v-loading="loading">
          <div
            v-for="user in filteredUsers"
            :key="user.id"
            class="user-item"
            :class="{
              active: selectedUser?.id === user.id,
              disabled: user.status !== 1,
              'has-custom': hasCustomPermissions(user)
            }"
            @click="selectUser(user)"
          >
            <div class="user-avatar">
              <el-avatar :size="40" :style="{ background: getAvatarBg(user.role) }">
                {{ user.username?.charAt(0)?.toUpperCase() || 'U' }}
              </el-avatar>
              <span class="status-dot" :class="user.status === 1 ? 'online' : 'offline'"></span>
            </div>
            <div class="user-info">
              <span class="user-name">{{ user.username }}</span>
              <span class="user-role">{{ getRoleName(user.role) }}</span>
            </div>
            <div class="user-badges">
              <el-tag v-if="hasCustomPermissions(user)" size="small" type="warning" class="custom-tag">
                <el-icon><Edit /></el-icon>
                自定义
              </el-tag>
              <el-tag size="small" :type="user.status === 1 ? 'success' : 'info'">
                {{ user.status === 1 ? '正常' : '禁用' }}
              </el-tag>
            </div>
          </div>
          <el-empty v-if="filteredUsers.length === 0 && !loading" description="暂无用户" />
        </div>
      </div>

      <!-- 右侧：权限配置面板 -->
      <div class="permission-panel" v-if="selectedUser">
        <!-- 用户信息头部 -->
        <div class="panel-header">
          <div class="user-header-info">
            <div class="avatar-wrapper">
              <el-avatar :size="64" :style="{ background: getAvatarBg(selectedUser.role), fontSize: '28px' }">
                {{ selectedUser.username?.charAt(0)?.toUpperCase() || 'U' }}
              </el-avatar>
              <span class="status-indicator" :class="selectedUser.status === 1 ? 'active' : 'inactive'"></span>
            </div>
            <div class="user-details">
              <h3 class="selected-user-name">{{ selectedUser.username }}</h3>
              <div class="user-meta-row">
                <span class="meta-tag">
                  <el-icon><Message /></el-icon>
                  {{ selectedUser.email }}
                </span>
                <span class="meta-tag">
                  <el-icon><Clock /></el-icon>
                  {{ formatDate(selectedUser.created_at) }}
                </span>
                <span class="meta-tag" v-if="selectedUser.last_login">
                  <el-icon><Timer /></el-icon>
                  {{ formatTimeAgo(selectedUser.last_login) }}
                </span>
              </div>
            </div>
          </div>
          <div class="user-controls">
            <div class="control-item">
              <span class="control-label">账号状态</span>
              <el-switch
                v-model="selectedUser.status"
                :active-value="1"
                :inactive-value="0"
                @change="handleStatusChange"
              />
            </div>
            <el-button type="danger" plain @click="handleDeleteUser" :loading="deleteLoading">
              <el-icon><Delete /></el-icon>
              删除用户
            </el-button>
          </div>
        </div>

        <!-- 角色信息 -->
        <div class="role-section">
          <div class="section-header">
            <span class="section-title">角色分配</span>
            <span class="section-hint">修改角色将重置为该角色的默认权限</span>
          </div>
          <div class="role-cards">
            <div
              v-for="role in roleOptions"
              :key="role.value"
              class="role-card"
              :class="{ active: selectedUser.role === role.value }"
              @click="handleRoleChange(role.value)"
            >
              <div class="role-icon" :style="{ background: role.bg }">
                <el-icon><component :is="role.icon" /></el-icon>
              </div>
              <div class="role-info">
                <span class="role-name">{{ role.label }}</span>
                <span class="role-count">{{ userCountByRole(role.value) }} 人</span>
              </div>
              <div class="role-check" v-if="selectedUser.role === role.value">
                <el-icon><Check /></el-icon>
              </div>
            </div>
          </div>
        </div>

        <!-- 个性化权限开关 -->
        <div class="custom-permission-section">
          <div class="section-header">
            <span class="section-title">个性化权限配置</span>
            <div class="custom-toggle">
              <span class="toggle-label">启用个性化权限</span>
              <el-switch v-model="customEnabled" @change="handleCustomToggle" />
            </div>
          </div>
          <div class="custom-hint" v-if="!customEnabled">
            <el-icon><InfoFilled /></el-icon>
            <span>关闭后将使用角色默认权限，当前配置将暂存但不会生效</span>
          </div>
          <div class="custom-hint success" v-else>
            <el-icon><CircleCheckFilled /></el-icon>
            <span>已启用个性化权限，用户将忽略角色默认权限配置</span>
          </div>
        </div>

        <!-- 菜单权限配置 -->
        <div class="permission-config" :class="{ locked: !customEnabled }">
          <div class="config-header">
            <span class="config-title">
              菜单权限
              <el-tag v-if="customEnabled" size="small" type="warning" class="mode-tag">自定义模式</el-tag>
              <el-tag v-else size="small" type="info" class="mode-tag">角色继承</el-tag>
            </span>
            <el-checkbox
              v-model="selectAll"
              @change="handleSelectAll"
              :disabled="!customEnabled"
              :indeterminate="isIndeterminate"
            >
              全选
            </el-checkbox>
          </div>

          <!-- 权限统计 -->
          <div class="perm-stats">
            <span class="perm-stat">
              <el-icon><Check /></el-icon>
              {{ effectivePermissions.length || 0 }} 已授权
            </span>
            <span class="perm-stat inactive">
              <el-icon><Close /></el-icon>
              {{ permissionModules.length - (effectivePermissions.length || 0) }} 未授权
            </span>
          </div>

          <div class="permission-grid">
            <div
              v-for="perm in permissionModules"
              :key="perm.key"
              class="permission-card"
              :class="{
                granted: isGranted(perm.key),
                inherited: isInherited(perm.key),
                custom: isCustom(perm.key),
                disabled: !customEnabled
              }"
              @click="togglePermission(perm.key)"
            >
              <div class="perm-indicator"></div>
              <div class="perm-icon" :style="{ background: getPermBg(perm.key) }">
                <el-icon :size="22"><component :is="perm.icon" /></el-icon>
              </div>
              <div class="perm-content">
                <span class="perm-name">{{ perm.name }}</span>
                <span class="perm-desc">{{ perm.description }}</span>
              </div>
              <div class="perm-status">
                <el-tag v-if="isInherited(perm.key) && !isCustom(perm.key)" size="small" type="info" class="inherit-tag">
                  继承
                </el-tag>
                <el-tag v-else-if="isCustom(perm.key)" size="small" type="warning" class="custom-tag">
                  自定义
                </el-tag>
              </div>
              <div class="perm-check" v-if="isGranted(perm.key)">
                <el-icon><Check /></el-icon>
              </div>
            </div>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="panel-footer">
          <el-button @click="resetToRoleDefault" :disabled="!customEnabled">
            <el-icon><RefreshLeft /></el-icon>
            重置为角色默认
          </el-button>
          <div class="footer-right">
            <el-button @click="selectUser(selectedUser)">取消</el-button>
            <el-button type="primary" @click="savePermissions" :loading="saving">
              <el-icon><Check /></el-icon>
              保存配置
            </el-button>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div class="permission-panel empty" v-else>
        <div class="empty-illustration">
          <div class="empty-icon">
            <el-icon :size="64"><User /></el-icon>
          </div>
          <h3 class="empty-title">选择一位用户</h3>
          <p class="empty-desc">从左侧用户列表中选择一位用户<br/>进行权限配置</p>
        </div>
      </div>
    </div>

    <!-- 批量设置弹窗 -->
    <el-dialog v-model="batchDialogVisible" title="批量设置权限" width="560px" class="batch-dialog">
      <el-form :model="batchForm" label-width="90px">
        <el-form-item label="目标角色">
          <el-select v-model="batchForm.role" placeholder="请选择角色" style="width: 100%">
            <el-option label="管理员" :value="1" />
            <el-option label="题库编辑" :value="2" />
            <el-option label="审核员" :value="3" />
          </el-select>
        </el-form-item>
        <el-form-item label="权限模板">
          <el-radio-group v-model="batchForm.template" class="template-group">
            <el-radio :value="1">
              <span class="template-option">
                <span class="template-name">完全权限</span>
                <span class="template-desc">管理员默认</span>
              </span>
            </el-radio>
            <el-radio :value="2">
              <span class="template-option">
                <span class="template-name">题库编辑</span>
                <span class="template-desc">题库编辑默认</span>
              </span>
            </el-radio>
            <el-radio :value="3">
              <span class="template-option">
                <span class="template-name">审核员</span>
                <span class="template-desc">审核员默认</span>
              </span>
            </el-radio>
            <el-radio :value="0">
              <span class="template-option">
                <span class="template-name">自定义</span>
                <span class="template-desc">手动选择</span>
              </span>
            </el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="权限配置" v-if="batchForm.template === 0" class="custom-perms">
          <el-checkbox-group v-model="batchForm.permissions">
            <el-checkbox value="dashboard">控制台</el-checkbox>
            <el-checkbox value="ai-question">AI出题</el-checkbox>
            <el-checkbox value="audit">试题审核</el-checkbox>
            <el-checkbox value="auto-paper">智能组卷</el-checkbox>
            <el-checkbox value="question-bank">题库管理</el-checkbox>
            <el-checkbox value="paper-management">试卷管理</el-checkbox>
            <el-checkbox value="knowledge">知识点管理</el-checkbox>
            <el-checkbox value="settings">系统设置</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-alert type="warning" :closable="false" class="batch-warning">
          <template #title>
            <span>批量设置将影响该角色下的所有用户</span>
          </template>
        </el-alert>
      </el-form>
      <template #footer>
        <el-button @click="batchDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmBatchSet">确认批量设置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { systemAPI } from '@/api'
import {
  Search, Setting, Message, Clock, Timer, Check, Close,
  Key, Refresh, Edit, InfoFilled, CircleCheckFilled, RefreshLeft,
  Odometer, MagicStick, CircleCheck, DocumentCopy,
  Collection, Connection, Document, User, UserFilled, School, Delete
} from '@element-plus/icons-vue'

const loading = ref(false)
const saving = ref(false)
const deleteLoading = ref(false)
const allUsers = ref([])
const searchQuery = ref('')
const filterRole = ref(null)
const selectedUser = ref(null)
const customEnabled = ref(false)
const selectAll = ref(false)

// 角色选项
const roleOptions = [
  { value: 1, label: '管理员', icon: 'UserFilled', bg: 'linear-gradient(135deg, #165DFF 0%, #3B82F6 100%)' },
  { value: 2, label: '题库编辑', icon: 'School', bg: 'linear-gradient(135deg, #10B981 0%, #34D399 100%)' },
  { value: 3, label: '审核员', icon: 'User', bg: 'linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%)' }
]

// 权限模块配置
const permissionModules = [
  { key: 'dashboard', name: '控制台', description: '系统仪表盘和数据概览', icon: 'Odometer' },
  { key: 'ai-question', name: 'AI出题', description: '使用AI生成试题', icon: 'MagicStick' },
  { key: 'audit', name: '试题审核', description: '审核和管理试题', icon: 'CircleCheck' },
  { key: 'auto-paper', name: '智能组卷', description: '自动生成试卷', icon: 'DocumentCopy' },
  { key: 'question-bank', name: '题库管理', description: '管理题库资源', icon: 'Collection' },
  { key: 'paper-management', name: '试卷管理', description: '管理试卷文件', icon: 'Document' },
  { key: 'knowledge', name: '知识点管理', description: '管理知识点结构', icon: 'Connection' },
  { key: 'settings', name: '系统设置', description: '系统配置和管理', icon: 'Setting' }
]

// 角色默认权限
const roleDefaultPermissions = {
  1: ['ai-question', 'audit', 'auto-paper', 'question-bank', 'paper-management', 'knowledge', 'settings', 'user-permission'],
  2: ['ai-question', 'audit', 'auto-paper', 'question-bank', 'paper-management', 'knowledge'],
  3: ['audit', 'question-bank']
}

// 批量设置弹窗
const batchDialogVisible = ref(false)
const batchForm = reactive({
  role: null,
  template: 1,
  permissions: []
})

// 计算属性
const filteredUsers = computed(() => {
  return allUsers.value.filter(user => {
    const matchSearch = !searchQuery.value ||
      user.username.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      user.email.toLowerCase().includes(searchQuery.value.toLowerCase())
    const matchRole = !filterRole.value || user.role === filterRole.value
    return matchSearch && matchRole
  })
})

// 有效权限（根据是否启用自定义权限计算）
const effectivePermissions = computed(() => {
  if (!selectedUser.value) return []
  const role = selectedUser.value.role
  // 如果启用了自定义权限或有个性化权限设置，使用自定义权限
  if (customEnabled.value && selectedUser.value.custom_permissions) {
    return selectedUser.value.custom_permissions
  }
  // 否则使用角色默认权限
  return roleDefaultPermissions[role] || []
})

const isIndeterminate = computed(() => {
  if (!selectedUser.value?.custom_permissions) return false
  const permCount = selectedUser.value.custom_permissions.length
  return permCount > 0 && permCount < permissionModules.length
})

// 用户统计
const userCountByRole = (role) => {
  return allUsers.value.filter(u => u.role === role).length
}

// 权限判断
const hasCustomPermissions = (user) => {
  return user.custom_permissions && user.custom_permissions.length > 0
}

const isGranted = (key) => {
  if (!selectedUser.value) return false
  // 如果启用了个性化权限，使用自定义权限
  if (customEnabled.value) {
    return selectedUser.value.custom_permissions?.includes(key) || false
  }
  // 否则使用角色默认权限
  return roleDefaultPermissions[selectedUser.value.role]?.includes(key) || false
}

const isInherited = (key) => {
  return roleDefaultPermissions[selectedUser.value?.role]?.includes(key) || false
}

const isCustom = (key) => {
  return selectedUser.value?.custom_permissions?.includes(key) || false
}

// 方法
const getRoleName = (role) => {
  const names = { 1: '管理员', 2: '题库编辑', 3: '审核员' }
  return names[role] || '未知'
}

const getAvatarBg = (role) => {
  const bgs = {
    1: 'linear-gradient(135deg, #165DFF 0%, #3B82F6 100%)',
    2: 'linear-gradient(135deg, #10B981 0%, #34D399 100%)',
    3: 'linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%)'
  }
  return bgs[role] || bgs[3]
}

const getPermBg = (key) => {
  const colors = {
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

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN')
}

const formatTimeAgo = (dateStr) => {
  if (!dateStr) return '从未登录'
  const now = new Date()
  const date = new Date(dateStr)
  const diff = Math.floor((now - date) / 1000)
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`
  if (diff < 604800) return `${Math.floor(diff / 86400)}天前`
  return formatDate(dateStr)
}

// 加载用户数据
const loadUsers = async () => {
  loading.value = true
  try {
    const res = await systemAPI.getUsers()
    // axios response: res.data contains the actual response body
    allUsers.value = res.data?.items || res.data || []
  } catch (err) {
    console.error('加载用户失败:', err)
    ElMessage.error('加载用户列表失败')
  } finally {
    loading.value = false
  }
}

// 选择用户
const selectUser = (user) => {
  selectedUser.value = { ...user }
  customEnabled.value = hasCustomPermissions(user)
  updateSelectAll()
}

// 切换个性化权限
const handleCustomToggle = (enabled) => {
  if (enabled) {
    // 启用时，初始化自定义权限为当前生效的权限
    if (!selectedUser.value.custom_permissions || selectedUser.value.custom_permissions.length === 0) {
      // 使用角色默认权限初始化
      selectedUser.value.custom_permissions = [...(roleDefaultPermissions[selectedUser.value.role] || [])]
    }
  }
  updateSelectAll()
}

// 切换权限
const togglePermission = (key) => {
  if (!customEnabled.value) return
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

// 全选
const handleSelectAll = (checked) => {
  if (!selectedUser.value) return
  selectedUser.value.custom_permissions = checked
    ? permissionModules.map(p => p.key)
    : []
}

const updateSelectAll = () => {
  if (!selectedUser.value?.custom_permissions) {
    selectAll.value = false
    return
  }
  selectAll.value = selectedUser.value.custom_permissions.length === permissionModules.length
}

// 重置为角色默认
const resetToRoleDefault = () => {
  selectedUser.value.custom_permissions = [...(roleDefaultPermissions[selectedUser.value.role] || [])]
  ElMessage.success('已重置为角色默认权限')
  updateSelectAll()
}

// 保存权限
const savePermissions = async () => {
  if (!selectedUser.value) return
  saving.value = true
  try {
    // 调用后端API保存用户权限
    await systemAPI.updateUserPermissions(selectedUser.value.id, {
      custom_permissions: customEnabled.value ? selectedUser.value.custom_permissions : null,
      role: selectedUser.value.role,
      status: selectedUser.value.status
    })

    // 更新本地数据
    const idx = allUsers.value.findIndex(u => u.id === selectedUser.value.id)
    if (idx !== -1) {
      allUsers.value[idx] = {
        ...allUsers.value[idx],
        role: selectedUser.value.role,
        status: selectedUser.value.status,
        custom_permissions: customEnabled.value ? selectedUser.value.custom_permissions : null
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

// 状态变更
const handleStatusChange = () => {
  ElMessage.success(`账号已${selectedUser.value.status === 1 ? '启用' : '禁用'}`)
}

// 删除用户
const handleDeleteUser = async () => {
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

    // 更新本地状态
    const user = allUsers.value.find(u => u.id === selectedUser.value.id)
    if (user) {
      user.status = 0 // 禁用
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

// 角色变更
const handleRoleChange = async (newRole) => {
  if (selectedUser.value.role === newRole) return
  try {
    // 调用API更新用户角色
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

// 批量设置
const handleBatchSet = () => {
  batchForm.role = null
  batchForm.template = 1
  batchForm.permissions = []
  batchDialogVisible.value = true
}

const confirmBatchSet = async () => {
  if (!batchForm.role) {
    ElMessage.warning('请选择目标角色')
    return
  }

  const perms = batchForm.template === 0
    ? batchForm.permissions
    : roleDefaultPermissions[batchForm.template]

  try {
    // 调用后端批量更新API
    await systemAPI.batchUpdateRolePermissions(batchForm.role, perms)

    // 更新本地数据
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

// 初始化
onMounted(() => {
  loadUsers()
})
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Noto+Sans+SC:wght@400;500;600&display=swap');

.permission-page {
  padding: 24px;
  min-height: calc(100vh - 120px);
  background: linear-gradient(180deg, #F8FAFC 0%, #F1F5F9 100%);
  font-family: 'Geist', 'Noto Sans SC', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* 页面标题 */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
  padding: 24px 28px;
  background: white;
  border-radius: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 4px 12px rgba(22, 93, 255, 0.03);
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.title-icon {
  color: #165DFF;
  margin-right: 8px;
}

.page-title {
  font-size: 22px;
  font-weight: 700;
  color: #0F172A;
  margin: 0;
  display: flex;
  align-items: center;
  letter-spacing: -0.3px;
}

.page-desc {
  font-size: 14px;
  color: #64748B;
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 12px;
}

/* 主容器 */
.main-container {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 24px;
  min-height: calc(100vh - 220px);
}

/* 用户列表面板 */
.user-list-panel {
  background: white;
  border-radius: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 4px 12px rgba(22, 93, 255, 0.03);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.list-toolbar {
  padding: 16px;
  border-bottom: 1px solid #F1F5F9;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.search-input {
  width: 100%;
}

.role-filter {
  width: 100%;
}

/* 用户统计 */
.user-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  padding: 12px 16px;
  background: #F8FAFC;
  border-bottom: 1px solid #F1F5F9;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.stat-value {
  font-size: 18px;
  font-weight: 700;
  color: #0F172A;
}

.stat-label {
  font-size: 11px;
  color: #64748B;
}

/* 用户列表 */
.user-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.user-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
  border: 2px solid transparent;
}

.user-item:hover {
  background: #F8FAFC;
}

.user-item.active {
  background: rgba(22, 93, 255, 0.06);
  border-color: #165DFF;
}

.user-item.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.user-item.has-custom::after {
  content: '';
  position: absolute;
  top: 8px;
  right: 8px;
  width: 6px;
  height: 6px;
  background: #F59E0B;
  border-radius: 50%;
}

.user-avatar {
  position: relative;
  flex-shrink: 0;
}

.status-dot {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 2px solid white;
}

.status-dot.online {
  background: #10B981;
}

.status-dot.offline {
  background: #94A3B8;
}

.user-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.user-name {
  font-size: 14px;
  font-weight: 600;
  color: #0F172A;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-role {
  font-size: 12px;
  color: #64748B;
}

.user-badges {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: flex-end;
}

.custom-tag {
  display: flex;
  align-items: center;
  gap: 2px;
}

/* 权限配置面板 */
.permission-panel {
  background: white;
  border-radius: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 4px 12px rgba(22, 93, 255, 0.03);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.permission-panel.empty {
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-illustration {
  text-align: center;
  padding: 48px;
}

.empty-icon {
  width: 120px;
  height: 120px;
  margin: 0 auto 24px;
  background: linear-gradient(135deg, #F1F5F9 0%, #E2E8F0 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94A3B8;
}

.empty-title {
  font-size: 18px;
  font-weight: 600;
  color: #0F172A;
  margin: 0 0 8px;
}

.empty-desc {
  font-size: 14px;
  color: #64748B;
  margin: 0;
  line-height: 1.6;
}

/* 面板头部 */
.panel-header {
  padding: 24px;
  border-bottom: 1px solid #F1F5F9;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.user-header-info {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.avatar-wrapper {
  position: relative;
}

.status-indicator {
  position: absolute;
  bottom: 2px;
  right: 2px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 3px solid white;
}

.status-indicator.active {
  background: #10B981;
}

.status-indicator.inactive {
  background: #94A3B8;
}

.user-details {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.selected-user-name {
  font-size: 20px;
  font-weight: 700;
  color: #0F172A;
  margin: 0;
}

.user-meta-row {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.meta-tag {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #64748B;
}

.user-controls {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.control-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.control-label {
  font-size: 13px;
  color: #64748B;
}

/* 角色区域 */
.role-section {
  padding: 20px 24px;
  border-bottom: 1px solid #F1F5F9;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #0F172A;
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-hint {
  font-size: 12px;
  color: #94A3B8;
}

.role-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.role-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  background: #F8FAFC;
  border: 2px solid transparent;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
}

.role-card:hover {
  background: #F1F5F9;
}

.role-card.active {
  background: rgba(22, 93, 255, 0.06);
  border-color: #165DFF;
}

.role-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 18px;
}

.role-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.role-name {
  font-size: 14px;
  font-weight: 600;
  color: #0F172A;
}

.role-count {
  font-size: 12px;
  color: #64748B;
}

.role-check {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 20px;
  height: 20px;
  background: #165DFF;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 12px;
}

/* 个性化权限区域 */
.custom-permission-section {
  padding: 20px 24px;
  border-bottom: 1px solid #F1F5F9;
}

.custom-toggle {
  display: flex;
  align-items: center;
  gap: 12px;
}

.toggle-label {
  font-size: 13px;
  color: #64748B;
}

.custom-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding: 10px 14px;
  background: #FEF3C7;
  border-radius: 8px;
  font-size: 13px;
  color: #92400E;
}

.custom-hint.success {
  background: #D1FAE5;
  color: #065F46;
}

/* 权限配置区域 */
.permission-config {
  padding: 20px 24px;
  flex: 1;
  overflow-y: auto;
}

.permission-config.locked {
  opacity: 0.6;
  pointer-events: none;
}

.config-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.config-title {
  font-size: 14px;
  font-weight: 600;
  color: #0F172A;
  display: flex;
  align-items: center;
  gap: 8px;
}

.mode-tag {
  font-size: 11px;
}

/* 权限统计 */
.perm-stats {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}

.perm-stat {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #10B981;
}

.perm-stat.inactive {
  color: #94A3B8;
}

/* 权限网格 */
.permission-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.permission-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  background: #F8FAFC;
  border: 2px solid transparent;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
}

.permission-card:hover:not(.disabled) {
  background: #F1F5F9;
  transform: translateY(-1px);
}

.permission-card.granted {
  background: rgba(16, 185, 129, 0.06);
  border-color: #10B981;
}

.permission-card.disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.perm-indicator {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  border-radius: 12px 0 0 12px;
  background: transparent;
  transition: all 0.2s ease;
}

.permission-card.granted .perm-indicator {
  background: #10B981;
}

.permission-card.custom .perm-indicator {
  background: #F59E0B;
}

.perm-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #165DFF;
  flex-shrink: 0;
}

.perm-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.perm-name {
  font-size: 14px;
  font-weight: 600;
  color: #0F172A;
}

.perm-desc {
  font-size: 12px;
  color: #64748B;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.perm-status {
  flex-shrink: 0;
}

.inherit-tag {
  font-size: 10px;
}

.perm-check {
  width: 24px;
  height: 24px;
  background: #10B981;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
}

/* 面板底部 */
.panel-footer {
  padding: 20px 24px;
  border-top: 1px solid #F1F5F9;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.footer-right {
  display: flex;
  gap: 12px;
}

/* 批量设置弹窗 */
.batch-dialog :deep(.el-dialog__header) {
  padding: 20px 24px;
  border-bottom: 1px solid #F1F5F9;
}

.batch-dialog :deep(.el-dialog__title) {
  font-size: 16px;
  font-weight: 600;
  color: #0F172A;
}

.template-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.template-group :deep(.el-radio) {
  margin-right: 0;
  padding: 10px 14px;
  background: #F8FAFC;
  border-radius: 8px;
  border: 1px solid #E2E8F0;
}

.template-group :deep(.el-radio:hover) {
  background: #F1F5F9;
}

.template-group :deep(.el-radio.is-checked) {
  background: rgba(22, 93, 255, 0.06);
  border-color: #165DFF;
}

.template-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.template-name {
  font-size: 14px;
  font-weight: 500;
  color: #0F172A;
}

.template-desc {
  font-size: 12px;
  color: #64748B;
}

.custom-perms :deep(.el-checkbox-group) {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.batch-warning {
  margin-top: 16px;
}
</style>
