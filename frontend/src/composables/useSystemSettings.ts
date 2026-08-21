import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { systemAPI } from '@/api'

// ============ Types ============
export interface ExamCategory {
  id: number
  name: string
  code: string
  description: string
  status: number
}

export interface ExamType {
  id: number
  category_id: number
  name: string
  code: string
  level: string
  duration: number
  total_score: number
  passing_score: number
  question_types: string[]
  description: string
  status: number
}

export interface User {
  id: number
  username: string
  name: string
  role: string
  phone: string
  email: string
  status: boolean
  lastLogin: string
  avatar: string
  password?: string
}

export interface PasswordResetRequest {
  id: number
  username: string
  requestTime: string
  status: 'pending' | 'approved' | 'rejected'
}

export interface RolePermissionItem {
  role: number
  permissions: string[]
}

export interface AIConfig {
  provider: string
  model: string
  apiKey: string
  apiUrl: string
  timeout: number
}

// ============ Password Reset ============
export const passwordResetRequests = ref<PasswordResetRequest[]>([])
export const resetLoading = ref(false)
export const resetDialogVisible = ref(false)
export const resetForm = reactive({
  requestId: null as number | null,
  username: '',
  newPassword: ''
})

export const loadPasswordResetRequests = async () => {
  resetLoading.value = true
  try {
    const res = await systemAPI.getPasswordResetRequests({ status: undefined })
    passwordResetRequests.value = res.data?.items || []
  } catch (error) {
    console.error('加载密码重置申请失败:', error)
    ElMessage.error('加载失败')
  } finally {
    resetLoading.value = false
  }
}

export const approveReset = async (row: PasswordResetRequest) => {
  // 后端处理接口 POST /password-reset-requests/{id}/process 仅接受 { new_password }，
  // 没有独立的"批准"接口，因此复用"处理申请"弹窗，由管理员填写新密码后提交
  showResetDialog(row)
}

export const rejectReset = async (row: PasswordResetRequest) => {
  // 后端暂无"拒绝"接口（只有 process / delete），明确提示未实现，避免假装成功
  ElMessage.warning('该功能尚未实现：后端暂无拒绝申请接口，可删除该申请记录')
}

// ============ Basic Settings ============
export const basicSettings = reactive({
  systemName: '智题 AIQuiz',
  logoUrl: '',
  announcement: '欢迎使用智题 AIQuiz，祝您工作顺利！',
  loginBgUrl: ''
})

export const handleLogoChange = (file: File) => {
  const url = URL.createObjectURL(file)
  basicSettings.logoUrl = url
}

export const handleBgChange = (file: File) => {
  const url = URL.createObjectURL(file)
  basicSettings.loginBgUrl = url
}

export const saveBasicSettings = async () => {
  try {
    const settingsToUpdate = [
      { key: 'system_name', value: basicSettings.systemName },
      { key: 'system_logo', value: basicSettings.logoUrl },
      { key: 'announcement', value: basicSettings.announcement },
      { key: 'login_bg', value: basicSettings.loginBgUrl }
    ]
    await systemAPI.updateSettings(settingsToUpdate)
    ElMessage.success('基础设置保存成功')
  } catch (error) {
    console.error('保存基础设置失败:', error)
    ElMessage.error('保存失败，请稍后重试')
  }
}

// ============ Exam Categories ============
export const examCategories = ref<ExamCategory[]>([])
export const examCategoryDialogVisible = ref(false)
export const isEditExamCategory = ref(false)
export const loading = ref(false)
export const examCategoryFormRef = ref<any>(null)

export const examCategoryForm = reactive({
  id: null as number | null,
  name: '',
  code: '',
  description: '',
  status: 1 as number
})

export const examCategoryRules = {
  name: [{ required: true, message: '请输入种类名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入种类代码', trigger: 'blur' }]
}

export const fetchExamCategories = async () => {
  try {
    const res = await systemAPI.getExamCategories()
    examCategories.value = res.data?.items || []
  } catch (e) {
    console.error('获取考试种类失败:', e)
  }
}

export const showExamCategoryDialog = (row: ExamCategory | null = null) => {
  if (row) {
    isEditExamCategory.value = true
    Object.assign(examCategoryForm, {
      id: row.id,
      name: row.name,
      code: row.code,
      description: row.description || '',
      status: row.status
    })
  } else {
    isEditExamCategory.value = false
    Object.assign(examCategoryForm, {
      id: null,
      name: '',
      code: '',
      description: '',
      status: 1
    })
  }
  examCategoryDialogVisible.value = true
}

export const submitExamCategory = async () => {
  try {
    await examCategoryFormRef.value.validate()
    const data = {
      name: examCategoryForm.name,
      code: examCategoryForm.code,
      description: examCategoryForm.description,
      status: examCategoryForm.status
    }
    if (isEditExamCategory.value) {
      await systemAPI.updateExamCategory(examCategoryForm.id, data)
      ElMessage.success('考试种类更新成功')
    } else {
      await systemAPI.createExamCategory(data)
      ElMessage.success('考试种类添加成功')
    }
    examCategoryDialogVisible.value = false
    fetchExamCategories()
  } catch (error) {
    console.error('提交失败:', error)
  }
}

export const deleteExamCategory = async (id: number) => {
  try {
    await ElMessageBox.confirm('确定要删除该考试种类吗？', '提示', {
      type: 'warning'
    })
    await systemAPI.deleteExamCategory(id)
    ElMessage.success('删除成功')
    fetchExamCategories()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

export const getCategoryName = (categoryId: number) => {
  const cat = examCategories.value.find(c => c.id === categoryId)
  return cat ? cat.name : '-'
}

// 自动生成代码
export const generateCategoryCode = () => {
  if (!isEditExamCategory.value && examCategoryForm.name) {
    examCategoryForm.code = generateCode(examCategoryForm.name)
  }
}

// 生成代码的辅助函数：将中文/英文名称转换为大写字母数字组合
export const generateCode = (name: string) => {
  if (!name) return ''
  // 移除非字母数字字符
  let code = name.replace(/[^\w\u4e00-\u9fa5]/g, '')
  // 如果是纯中文，转换为拼音首字母
  if (/^[\u4e00-\u9fa5]+$/.test(name)) {
    code = name.split('').map(char => charToPinyin(char)).filter(Boolean).join('')
  } else {
    // 英文混合，只保留字母数字
    code = code.replace(/[^\w]/g, '').toUpperCase()
  }
  return code || name.toUpperCase().replace(/[^\w]/g, '')
}

// 汉字转拼音首字母（扩展映射表）
const charToPinyin = (char: string) => {
  const pinyinMap: Record<string, string> = {
    // 考试种类相关
    '软': 'R', '考': 'K', '司': 'S', '法': 'F', '鉴': 'J', '定': 'D',
    '教': 'J', '育': 'Y',
    // 考试科目相关
    '网': 'W', '络': 'L', '管': 'G', '理': 'L', '员': 'Y', '工': 'G',
    '程': 'C', '师': 'S', '规': 'G', '划': 'H', '设': 'S', '计': 'J',
    '基': 'J', '础': 'C', '专': 'Z', '业': 'Y', '初': 'C', '级': 'J',
    '中': 'Z', '高': 'G', '律': 'L', '则': 'Z',
    '度': 'D', '论': 'L', '实': 'S', '务': 'W',
    '别': 'B', '会': 'H', '审': 'S', '财': 'C',
    '税': 'S', '银': 'Y', '行': 'X', '经': 'J',
    '济': 'J', '贸': 'M', '易': 'Y', '保': 'B', '险': 'X', '金': 'J',
    '融': 'R', '投': 'T', '资': 'Z', '房': 'F', '产': 'C', '筑': 'Z',
    '医': 'Y', '疗': 'L', '卫': 'W', '生': 'S', '文': 'W', '化': 'H',
    '源': 'Y', '人': 'R', '力': 'L',
    '政': 'X', '公': 'G', '共': 'G', '安': 'A', '全': 'Q',
    '质': 'Z', '量': 'L', '检': 'J', '测': 'C', '食': 'S', '品': 'P',
    '环': 'H', '境': 'J', '电': 'D', '子': 'Z', '商': 'S',
    '物': 'W', '流': 'L', '输': 'S', '运': 'Y', '园': 'Y',
    '林': 'L', '农': 'N', '机': 'J', '械': 'X',
    '水': 'S', '利': 'L', '铁': 'T', '路': 'L', '航': 'H',
    '空': 'K', '天': 'T', '信': 'X', '息': 'X', '通': 'T'
  }
  return pinyinMap[char] || ''
}

// ============ Exam Types ============
export const examTypes = ref<ExamType[]>([])
export const examTypeDialogVisible = ref(false)
export const isEditExamType = ref(false)
export const examTypeFormRef = ref<any>(null)

export const examTypeForm = reactive({
  id: null as number | null,
  category_id: null as number | null,
  name: '',
  code: '',
  level: '',
  duration: 120,
  total_score: 100,
  passing_score: 60,
  question_types: [] as string[],
  description: '',
  status: 1 as number
})

export const examTypeRules = {
  category_id: [{ required: true, message: '请选择考试种类', trigger: 'change' }],
  name: [{ required: true, message: '请输入科目名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入科目代码', trigger: 'blur' }]
}

// 按考试种类分组的考试科目
export const groupedExamTypes = computed(() => {
  const groups: Array<{ category: ExamCategory; examTypes: ExamType[] }> = []
  for (const cat of examCategories.value) {
    const examTypesInCat = examTypes.value.filter(et => et.category_id === cat.id)
    groups.push({
      category: cat,
      examTypes: examTypesInCat
    })
  }
  return groups
})

export const fetchExamTypes = async () => {
  try {
    const res = await systemAPI.getExamTypes()
    examTypes.value = res.data?.items || []
  } catch (e) {
    console.error('获取考试科目失败:', e)
  }
}

export const showExamTypeDialog = (row: ExamType | null = null) => {
  if (row) {
    isEditExamType.value = true
    Object.assign(examTypeForm, {
      id: row.id,
      category_id: row.category_id,
      name: row.name,
      code: row.code,
      level: row.level || '',
      duration: row.duration,
      total_score: row.total_score,
      passing_score: row.passing_score,
      question_types: row.question_types || [],
      description: row.description || '',
      status: row.status
    })
  } else {
    isEditExamType.value = false
    Object.assign(examTypeForm, {
      id: null,
      category_id: null,
      name: '',
      code: '',
      level: '',
      duration: 120,
      total_score: 100,
      passing_score: 60,
      question_types: [],
      description: '',
      status: 1
    })
  }
  examTypeDialogVisible.value = true
}

export const submitExamType = async () => {
  try {
    await examTypeFormRef.value.validate()
    const data = {
      category_id: examTypeForm.category_id,
      name: examTypeForm.name,
      code: examTypeForm.code,
      level: examTypeForm.level || null,
      duration: examTypeForm.duration,
      total_score: examTypeForm.total_score,
      passing_score: examTypeForm.passing_score,
      question_types: examTypeForm.question_types,
      description: examTypeForm.description,
      status: examTypeForm.status
    }
    if (isEditExamType.value) {
      await systemAPI.updateExamType(examTypeForm.id, data)
      ElMessage.success('考试科目更新成功')
    } else {
      await systemAPI.createExamType(data)
      ElMessage.success('考试科目添加成功')
    }
    examTypeDialogVisible.value = false
    fetchExamTypes()
  } catch (error) {
    console.error('提交失败:', error)
  }
}

export const deleteExamType = async (id: number) => {
  try {
    await ElMessageBox.confirm('确定要删除该考试科目吗？', '提示', {
      type: 'warning'
    })
    await systemAPI.deleteExamType(id)
    ElMessage.success('删除成功')
    fetchExamTypes()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

export const generateExamTypeCode = () => {
  if (!isEditExamType.value && examTypeForm.name) {
    examTypeForm.code = generateCode(examTypeForm.name)
  }
}

// ============ Subjects (question type names) ============
export const subjects = ref<string[]>([])

export const getQuestionTypeName = (type: string) => {
  const map: Record<string, string> = {
    choice: '单选题',
    multiple: '多选题',
    short_answer: '简答题',
    judge: '判断题',
    fill: '填空题'
  }
  return map[type] || type
}

// ============ Users ============
export const users = ref<User[]>([])
export const userPagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})
export const userDialogVisible = ref(false)
export const roleDialogVisible = ref(false)
export const isEditUser = ref(false)
export const userFormRef = ref<any>(null)
export const currentUser = ref<User | null>(null)
export const newRole = ref('')

export const userForm = reactive({
  id: null as number | null,
  username: '',
  name: '',
  role: 'editor',
  phone: '',
  email: '',
  password: '',
  status: true
})

export const userRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' }
  ]
}

export const fetchUsers = async () => {
  try {
    loading.value = true
    const res = await systemAPI.getUsers()
    users.value = (res.data?.items || res.data || []).map((u: any) => ({
      id: u.id,
      username: u.username,
      name: u.real_name || u.username,
      role: u.role === 1 ? 'admin' : u.role === 2 ? 'editor' : 'reviewer',
      phone: u.phone || '',
      email: u.email,
      status: u.status === 1,
      lastLogin: u.last_login || ''
    }))
  } catch (err) {
    console.error('获取用户列表失败:', err)
    ElMessage.error('获取用户列表失败')
  } finally {
    loading.value = false
  }
}

export const showUserDialog = (row: User | null = null) => {
  if (row) {
    isEditUser.value = true
    Object.assign(userForm, row)
    userForm.password = ''
  } else {
    isEditUser.value = false
    Object.assign(userForm, {
      id: null,
      username: '',
      name: '',
      role: 'editor',
      phone: '',
      email: '',
      password: '',
      status: true
    })
  }
  userDialogVisible.value = true
}

export const submitUser = async () => {
  try {
    await userFormRef.value.validate()
    const roleMap: Record<string, number> = { 'admin': 1, 'editor': 2, 'reviewer': 3 }
    const userData: any = {
      username: userForm.username,
      real_name: userForm.name,
      role: typeof userForm.role === 'string' ? (roleMap[userForm.role] || userForm.role) : userForm.role,
      phone: userForm.phone || null,
      email: userForm.email,
      status: userForm.status ? 1 : 0
    }
    if (isEditUser.value) {
      await systemAPI.updateUser(userForm.id, userData)
      const index = users.value.findIndex(item => item.id === userForm.id)
      if (index !== -1) {
        users.value[index] = { ...users.value[index], ...userForm } as User
      }
      ElMessage.success('用户更新成功')
    } else {
      userData.password = userForm.password
      const res = await systemAPI.createUser(userData)
      users.value.push({ ...userForm, id: res.data.id, lastLogin: '', avatar: '' })
      ElMessage.success('用户创建成功')
    }
    userDialogVisible.value = false
  } catch (error) {
    ElMessage.error(isEditUser.value ? '用户更新失败' : '用户创建失败')
  }
}

export const resetUserPassword = async (row: User) => {
  try {
    const { value: newPassword } = await ElMessageBox.prompt(
      `请输入用户"${row.name}"的新密码（至少8位，需包含大小写字母和数字）`,
      '重置密码',
      {
        inputType: 'password',
        inputValidator: (v: string) => (v && v.length >= 8 ? true : '密码长度至少8位')
      }
    )
    // 后端 POST /users/{id}/reset-password 需要请求体 { new_password }
    await systemAPI.resetPassword(row.id, { new_password: newPassword })
    ElMessage.success('密码已重置')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('重置密码失败')
    }
  }
}

export const changeUserRole = (row: User) => {
  currentUser.value = row
  newRole.value = row.role
  roleDialogVisible.value = true
}

export const submitRoleChange = async () => {
  if (newRole.value) {
    try {
      const roleMap: Record<string, number> = { 'admin': 1, 'editor': 2, 'reviewer': 3 }
      let roleInt: number
      if (typeof newRole.value === 'string') {
        roleInt = roleMap[newRole.value]
        if (roleInt === undefined) {
          roleInt = parseInt(newRole.value, 10)
        }
      } else {
        roleInt = newRole.value
      }
      await systemAPI.changeRole(currentUser.value!.id, roleInt)
      const user = users.value.find(item => item.id === currentUser.value!.id)
      if (user) {
        user.role = newRole.value
      }
      ElMessage.success('角色切换成功')
    } catch (error) {
      ElMessage.error('角色切换失败')
    }
  }
  roleDialogVisible.value = false
}

export const toggleUserStatus = async (row: User) => {
  // el-switch 的 v-model 已同步更新 row.status，这里以更新后的值调用后端
  const newStatus = row.status
  try {
    await systemAPI.updateUser(row.id, { status: newStatus ? 1 : 0 })
    ElMessage.success(`用户"${row.name}"已${newStatus ? '启用' : '禁用'}`)
  } catch (error) {
    row.status = !newStatus // 失败时回滚开关状态
    console.error('更新用户状态失败:', error)
    ElMessage.error(`用户"${row.name}"状态更新失败`)
  }
}

export const getRoleName = (role: string) => {
  const map: Record<string, string> = {
    admin: '管理员',
    editor: '题库编辑',
    reviewer: '审核员'
  }
  return map[role] || role
}

export const getRoleTagType = (role: string) => {
  const map: Record<string, string> = {
    admin: 'warning',
    editor: 'success',
    reviewer: 'info'
  }
  return map[role] || 'info'
}

// ============ Exam Rules ============
export const examRules = reactive({
  randomQuestionOrder: true,
  randomOptionOrder: true,
  allowReviewAnswer: false,
  maxScreenSwitch: 5,
  passScoreRatio: 60,
  scoreDisplay: ['score', 'correctRate']
})

export const saveExamRules = async () => {
  try {
    const settingsToUpdate = [
      { key: 'random_question_order', value: examRules.randomQuestionOrder },
      { key: 'random_option_order', value: examRules.randomOptionOrder },
      { key: 'allow_review_answer', value: examRules.allowReviewAnswer },
      { key: 'screen_switch_limit', value: examRules.maxScreenSwitch },
      // 后端 pass_score_ratio 按小数比例存储（默认 0.6 = 60%），前端为百分比
      { key: 'pass_score_ratio', value: examRules.passScoreRatio / 100 }
    ]
    await systemAPI.updateSettings(settingsToUpdate)
    ElMessage.success('考试规则保存成功')
  } catch (error) {
    console.error('保存考试规则失败:', error)
    ElMessage.error('保存失败，请稍后重试')
  }
}

// ============ Notification Settings ============
export const notificationSettings = reactive({
  email: {
    enabled: true,
    smtpHost: 'smtp.example.com',
    smtpPort: 465,
    fromEmail: 'noreply@example.com',
    password: '',
    useSSL: true
  },
  sms: {
    enabled: false,
    provider: 'aliyun',
    accessKeyId: '',
    accessKeySecret: '',
    signName: ''
  },
  templates: {
    review: {
      title: '审核结果通知',
      content: '尊敬的{username}，您的{type}已通过审核。'
    },
    score: {
      title: '成绩发布通知',
      content: '尊敬的{username}，您的考试成绩已发布，总分{score}分。'
    }
  }
})

// 后端暂无邮件/短信/消息模板配置及发送测试接口，明确提示未实现，避免"假保存"
export const saveEmailSettings = () => {
  ElMessage.warning('该功能尚未实现')
}

export const saveSmsSettings = () => {
  ElMessage.warning('该功能尚未实现')
}

export const saveTemplates = () => {
  ElMessage.warning('该功能尚未实现')
}

export const testEmailNotification = () => {
  ElMessage.warning('该功能尚未实现')
}

export const testSmsNotification = () => {
  ElMessage.warning('该功能尚未实现')
}

// ============ Security Settings ============
export const securitySettings = reactive({
  loginLockEnabled: true,
  maxLoginAttempts: 5,
  lockDuration: 30,
  passwordStrengthEnabled: true,
  passwordRules: ['length', 'number'],
  sessionTimeout: 120,
  ipWhitelist: '',
  operationLogEnabled: true
})

export const saveSecuritySettings = async () => {
  try {
    const settingsToUpdate = [
      { key: 'login_lock_enabled', value: securitySettings.loginLockEnabled },
      { key: 'login_lock_count', value: securitySettings.maxLoginAttempts },
      { key: 'login_lock_duration', value: securitySettings.lockDuration },
      { key: 'password_strength_enabled', value: securitySettings.passwordStrengthEnabled },
      { key: 'password_require_uppercase', value: securitySettings.passwordRules.includes('uppercase') },
      { key: 'password_require_lowercase', value: securitySettings.passwordRules.includes('lowercase') },
      { key: 'password_require_digit', value: securitySettings.passwordRules.includes('number') },
      { key: 'password_require_special', value: securitySettings.passwordRules.includes('special') },
      { key: 'session_timeout', value: securitySettings.sessionTimeout },
      { key: 'operation_log_enabled', value: securitySettings.operationLogEnabled }
    ]

    await systemAPI.updateSettings(settingsToUpdate)
    ElMessage.success('安全设置保存成功')
  } catch (error) {
    console.error('保存安全设置失败:', error)
    ElMessage.error('保存失败，请稍后重试')
  }
}

// ============ AI Settings ============
export interface AIProviderDefault {
  key: string
  name: string
  models: string[]
  default_model: string
  default_api_url: string
  protocol: string
  supports_streaming: boolean
}

// 从后端动态加载的厂商配置（含模型列表、默认API地址、协议类型）
// 以后更新模型只需改后端 AI_PROVIDERS_LIST，前端自动生效
export const aiProviderDefaults = reactive<Record<string, AIProviderDefault>>({})

// 兼容旧代码引用（指向动态数据源）
export const AI_PROVIDER_MODELS: Record<string, string[]> = computed(() => {
  const result: Record<string, string[]> = {}
  Object.values(aiProviderDefaults).forEach(p => {
    result[p.key] = p.models
  })
  return result
}) as any

export const aiSettings = reactive<AIConfig>({
  provider: 'minimax',
  model: 'MiniMax-M2.7',
  apiKey: '',
  apiUrl: '',
  timeout: 120
})

// 是否已配置 API 密钥（用于显示占位符）
export const apiKeyConfigured = ref(false)
// API 密钥输入框是否明文显示
export const apiKeyVisible = ref(false)

export const currentProviderModels = computed(() => {
  const provider = aiProviderDefaults[aiSettings.provider]
  return provider?.models || []
})

export const handleProviderChange = () => {
  const provider = aiProviderDefaults[aiSettings.provider]
  const models = provider?.models || []
  aiSettings.model = models[0] || ''
  // 自动填充默认 API 地址（仅在用户未手动填写时）
  if (!aiSettings.apiUrl && provider?.default_api_url) {
    aiSettings.apiUrl = provider.default_api_url
  }
}

export const saveAiSettings = async () => {
  try {
    const payload: any = {
      provider: aiSettings.provider,
      model: aiSettings.model,
      api_url: aiSettings.apiUrl,
      timeout: aiSettings.timeout
    }
    // 只有用户输入了新密钥时才发送，否则保留后端已有密钥
    if (aiSettings.apiKey) {
      payload.api_key = aiSettings.apiKey
    }
    await systemAPI.updateAiConfig(payload)
    // 保存后重新标记状态
    apiKeyConfigured.value = !!(aiSettings.apiKey || apiKeyConfigured.value)
    ElMessage.success('AI配置保存成功')
  } catch (error) {
    console.error('保存AI配置失败:', error)
    ElMessage.error('保存失败，请稍后重试')
  }
}

export const testAiConnection = async () => {
  try {
    ElMessage.info('正在测试AI连接...')
    const payload: any = {
      provider: aiSettings.provider,
      api_url: aiSettings.apiUrl,
      model: aiSettings.model,
      timeout: aiSettings.timeout
    }
    // 优先使用用户输入的密钥；若未输入但系统已配置，则依赖后端读取保存的密钥
    if (aiSettings.apiKey) {
      payload.api_key = aiSettings.apiKey
    }
    const result = await systemAPI.testAiConnection(payload)
    if (result.data?.success) {
      ElMessage.success('AI连接测试成功！')
    } else {
      ElMessage.error('AI连接测试失败：' + (result.data?.message || '未知错误'))
    }
  } catch (error) {
    console.error('测试AI连接失败:', error)
    ElMessage.error('测试连接失败，请稍后重试')
  }
}

// 清除已配置的 API 密钥
export const clearApiKey = async () => {
  try {
    aiSettings.apiKey = ''
    apiKeyConfigured.value = false
    // 通过发送空字符串来清除后端保存的密钥
    await systemAPI.updateAiConfig({
      provider: aiSettings.provider,
      model: aiSettings.model,
      api_key: '',
      api_url: aiSettings.apiUrl,
      timeout: aiSettings.timeout
    })
    ElMessage.success('API密钥已清除')
  } catch (error) {
    console.error('清除API密钥失败:', error)
    ElMessage.error('清除失败，请稍后重试')
  }
}

export const loadAiProviders = async () => {
  try {
    const res = await systemAPI.getAiProviders()
    if (res.data?.providers) {
      res.data.providers.forEach((p: AIProviderDefault) => {
        aiProviderDefaults[p.key] = p
      })
    }
  } catch (error) {
    console.error('加载AI厂商列表失败:', error)
  }
}

// 厂商下拉列表（从后端动态加载）
export const providerList = computed(() => {
  return Object.values(aiProviderDefaults)
})

// ============ Role Permissions ============
export const rolePermissionsForm = reactive({
  role1: [] as string[],
  role2: [] as string[],
  role3: [] as string[]
})

export const loadRolePermissions = async () => {
  try {
    const res = await systemAPI.getRolePermissions()
    if (res.data && res.data.length) {
      res.data.forEach((item: RolePermissionItem) => {
        if (item.role === 1) rolePermissionsForm.role1 = item.permissions || []
        if (item.role === 2) rolePermissionsForm.role2 = item.permissions || []
        if (item.role === 3) rolePermissionsForm.role3 = item.permissions || []
      })
    }
  } catch (error) {
    console.error('加载角色权限失败:', error)
  }
}

// ============ Password Reset Actions ============
export const showResetDialog = (row: PasswordResetRequest) => {
  resetForm.requestId = row.id
  resetForm.username = row.username
  resetForm.newPassword = ''
  resetDialogVisible.value = true
}

export const submitPasswordReset = async () => {
  if (!resetForm.newPassword || resetForm.newPassword.length < 8) {
    ElMessage.warning('密码长度至少8位')
    return
  }
  try {
    await systemAPI.processPasswordResetRequest(resetForm.requestId, {
      new_password: resetForm.newPassword
    })
    ElMessage.success('密码已重置，请告知用户新密码')
    resetDialogVisible.value = false
    loadPasswordResetRequests()
  } catch (error) {
    console.error('重置密码失败:', error)
    ElMessage.error((error as Error).message || '重置失败')
  }
}

export const deleteResetRequest = async (id: number) => {
  try {
    await systemAPI.deletePasswordResetRequest(id)
    ElMessage.success('申请记录已删除')
    loadPasswordResetRequests()
  } catch (error) {
    console.error('删除申请记录失败:', error)
    ElMessage.error('删除失败')
  }
}

export const formatDateTime = (dateStr: string) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleString('zh-CN')
}

export const saveRolePermissions = async () => {
  try {
    await systemAPI.updateRolePermissions(1, rolePermissionsForm.role1)
    await systemAPI.updateRolePermissions(2, rolePermissionsForm.role2)
    await systemAPI.updateRolePermissions(3, rolePermissionsForm.role3)
    ElMessage.success('角色权限配置已保存')
  } catch (error) {
    console.error('保存角色权限失败:', error)
    ElMessage.error('保存失败，请稍后重试')
  }
}

// ============ Tab State ============
export const activeTab = ref('basic')
export const notificationSubTab = ref('email')

// ============ Initialization ============
export const initializeSystemSettings = async () => {
  // 初始化加载数据
  await fetchUsers()
  await fetchExamCategories()
  await fetchExamTypes()
  // 加载角色权限配置
  await loadRolePermissions()
  // 加载AI厂商默认配置（含默认API地址）
  await loadAiProviders()
  // 加载AI配置
  try {
    const res = await systemAPI.getAiConfig()
    if (res.data) {
      aiSettings.provider = res.data.provider
      aiSettings.model = res.data.model
      aiSettings.apiUrl = res.data.api_url || ''
      aiSettings.timeout = res.data.timeout
      // 标记 API 密钥是否已配置，用于显示占位符
      apiKeyConfigured.value = res.data.api_key_configured || false
      // 不清空 apiKey，让用户能看到占位符；但如果用户之前已经输入了新值，保留输入值
      if (!aiSettings.apiKey) {
        // apiKey 为空时，不显示明文，依赖 placeholder "****"
      }
      // 若API地址为空，自动填充厂商默认地址
      if (!aiSettings.apiUrl && aiSettings.provider) {
        const provider = aiProviderDefaults[aiSettings.provider]
        if (provider?.default_api_url) {
          aiSettings.apiUrl = provider.default_api_url
        }
      }
    }
  } catch (error) {
    console.error('加载AI配置失败:', error)
  }
}

// ============ Composable ============
export function useSystemSettings() {
  // 评估 P2-13：模块级 watch 永不销毁，移入工厂内注册，随组件卸载自动清理。
  watch(activeTab, (newTab) => {
    if (newTab === 'passwordReset' && passwordResetRequests.value.length === 0) {
      loadPasswordResetRequests()
    }
  })

  // All state and functions are already exported as named exports
  // This composable just provides a unified interface
  return {
    // Tab state
    activeTab,
    notificationSubTab,
    // Password reset
    passwordResetRequests,
    resetLoading,
    resetDialogVisible,
    resetForm,
    loadPasswordResetRequests,
    approveReset,
    rejectReset,
    // Basic settings
    basicSettings,
    handleLogoChange,
    handleBgChange,
    saveBasicSettings,
    // Exam categories
    examCategories,
    examCategoryDialogVisible,
    isEditExamCategory,
    loading,
    examCategoryFormRef,
    examCategoryForm,
    examCategoryRules,
    fetchExamCategories,
    showExamCategoryDialog,
    submitExamCategory,
    deleteExamCategory,
    getCategoryName,
    generateCategoryCode,
    generateCode,
    // Exam types
    examTypes,
    examTypeDialogVisible,
    isEditExamType,
    examTypeFormRef,
    examTypeForm,
    examTypeRules,
    groupedExamTypes,
    fetchExamTypes,
    showExamTypeDialog,
    submitExamType,
    deleteExamType,
    generateExamTypeCode,
    // Subjects
    subjects,
    getQuestionTypeName,
    // Users
    users,
    userPagination,
    userDialogVisible,
    roleDialogVisible,
    isEditUser,
    userFormRef,
    currentUser,
    newRole,
    userForm,
    userRules,
    fetchUsers,
    showUserDialog,
    submitUser,
    resetUserPassword,
    changeUserRole,
    submitRoleChange,
    toggleUserStatus,
    getRoleName,
    getRoleTagType,
    // Exam rules
    examRules,
    saveExamRules,
    // Notification settings
    notificationSettings,
    saveEmailSettings,
    saveSmsSettings,
    saveTemplates,
    testEmailNotification,
    testSmsNotification,
    // Security settings
    securitySettings,
    saveSecuritySettings,
    // AI settings
    AI_PROVIDER_MODELS,
    aiProviderDefaults,
    aiSettings,
    currentProviderModels,
    handleProviderChange,
    loadAiProviders,
    providerList,
    saveAiSettings,
    testAiConnection,
    // Role permissions
    rolePermissionsForm,
    loadRolePermissions,
    saveRolePermissions,
    // Initialization
    initializeSystemSettings
  }
}
