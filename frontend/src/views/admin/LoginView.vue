<template>
  <div class="login-page" :class="{ 'dark-mode': isDark }">
    <!-- 左侧品牌区 2/3 -->
    <div class="brand-panel">
      <!-- 科技感背景 -->
      <div class="tech-canvas">
        <!-- 动态网格 -->
        <div class="grid-overlay"></div>

        <!-- 渐变光层 -->
        <div class="gradient-layers">
          <div class="glow-panel gp-1"></div>
          <div class="glow-panel gp-2"></div>
          <div class="glow-panel gp-3"></div>
        </div>

        <!-- 装饰线条 -->
        <svg class="tech-lines" viewBox="0 0 800 600" preserveAspectRatio="xMidYMid slice">
          <defs>
            <linearGradient id="lineGrad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stop-color="#165DFF" stop-opacity="0"/>
              <stop offset="50%" stop-color="#165DFF" stop-opacity="0.6"/>
              <stop offset="100%" stop-color="#165DFF" stop-opacity="0"/>
            </linearGradient>
            <linearGradient id="lineGradV" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stop-color="#60A5FA" stop-opacity="0"/>
              <stop offset="50%" stop-color="#60A5FA" stop-opacity="0.4"/>
              <stop offset="100%" stop-color="#60A5FA" stop-opacity="0"/>
            </linearGradient>
          </defs>
          <!-- 水平线 -->
          <line x1="0" y1="100" x2="800" y2="100" stroke="url(#lineGrad)" stroke-width="1"/>
          <line x1="0" y1="200" x2="800" y2="200" stroke="url(#lineGrad)" stroke-width="1"/>
          <line x1="0" y1="300" x2="800" y2="300" stroke="url(#lineGrad)" stroke-width="1"/>
          <line x1="0" y1="400" x2="800" y2="400" stroke="url(#lineGrad)" stroke-width="1"/>
          <line x1="0" y1="500" x2="800" y2="500" stroke="url(#lineGrad)" stroke-width="1"/>
          <!-- 垂直线 -->
          <line x1="100" y1="0" x2="100" y2="600" stroke="url(#lineGradV)" stroke-width="1"/>
          <line x1="200" y1="0" x2="200" y2="600" stroke="url(#lineGradV)" stroke-width="1"/>
          <line x1="300" y1="0" x2="300" y2="600" stroke="url(#lineGradV)" stroke-width="1"/>
          <line x1="400" y1="0" x2="400" y2="600" stroke="url(#lineGradV)" stroke-width="1"/>
          <line x1="500" y1="0" x2="500" y2="600" stroke="url(#lineGradV)" stroke-width="1"/>
          <line x1="600" y1="0" x2="600" y2="600" stroke="url(#lineGradV)" stroke-width="1"/>
          <line x1="700" y1="0" x2="700" y2="600" stroke="url(#lineGradV)" stroke-width="1"/>
          <!-- 连接点 -->
          <circle cx="300" cy="200" r="4" fill="#165DFF" class="node n1"/>
          <circle cx="500" cy="200" r="4" fill="#165DFF" class="node n2"/>
          <circle cx="400" cy="300" r="6" fill="#165DFF" class="node n3 pulse"/>
          <circle cx="200" cy="400" r="4" fill="#60A5FA" class="node n4"/>
          <circle cx="600" cy="400" r="4" fill="#60A5FA" class="node n5"/>
          <!-- 数据流动线 -->
          <path d="M300 200 L400 300 L500 200" stroke="#165DFF" stroke-width="2" fill="none" class="flow-line"/>
          <path d="M200 400 L400 300 L600 400" stroke="#60A5FA" stroke-width="2" fill="none" class="flow-line fl-2"/>
        </svg>
      </div>

      <!-- 品牌内容 -->
      <div class="brand-content">
        <div class="brand-header">
          <div class="brand-logo">
            <svg viewBox="0 0 48 48" width="56" height="56" fill="none">
              <rect x="4" y="8" width="40" height="32" rx="4" stroke="currentColor" stroke-width="2.5"/>
              <path d="M4 16h40" stroke="currentColor" stroke-width="2.5"/>
              <circle cx="14" cy="12" r="2" fill="currentColor"/>
              <circle cx="22" cy="12" r="2" fill="currentColor"/>
              <path d="M12 24l4 4 8-8" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M28 26h8M28 32h5" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
            </svg>
          </div>
          <div class="brand-text">
            <h1 class="brand-title">智题 AIQuiz</h1>
            <p class="brand-subtitle">AI 驱动智能题库建设</p>
          </div>
        </div>

        <div class="brand-features">
          <div class="feature-block">
            <div class="feature-icon-wrap">
              <el-icon :size="24"><MagicStick /></el-icon>
            </div>
            <div class="feature-info">
              <h3>智能出题</h3>
              <p>AI大模型驱动，高质量题目生成</p>
            </div>
          </div>
          <div class="feature-block">
            <div class="feature-icon-wrap">
              <el-icon :size="24"><CopyDocument /></el-icon>
            </div>
            <div class="feature-info">
              <h3>灵活组卷</h3>
              <p>多维度配置，快速生成考试试卷</p>
            </div>
          </div>
          <div class="feature-block">
            <div class="feature-icon-wrap">
              <el-icon :size="24"><Box /></el-icon>
            </div>
            <div class="feature-info">
              <h3>题库管理</h3>
              <p>标准化管理，高效维护题目资源</p>
            </div>
          </div>
        </div>

        <!-- 法律声明 -->
        <div class="legal-statement">
          <p class="disclaimer">本系统试题均为AI原创模拟题，非真实考试真题</p>
          <div class="legal-links">
            <a href="#" @click.prevent="showLegalDialog('agreement')">用户协议</a>
            <span class="divider">|</span>
            <a href="#" @click.prevent="showLegalDialog('privacy')">隐私政策</a>
          </div>
        </div>
      </div>
    </div>

    <!-- 右侧表单区 1/3 -->
    <div class="form-panel">
      <div class="form-container" :class="{ 'animate-in': mounted }">
        <!-- 主题切换 -->
        <button class="theme-toggle" @click="toggleTheme" :title="isDark ? '浅色模式' : '深色模式'">
          <el-icon :size="18">
            <Sunny v-if="isDark" />
            <Moon v-else />
          </el-icon>
        </button>

        <div class="form-header">
          <h2 class="form-title">用户登录</h2>
          <p class="form-desc">欢迎回来，请输入账号信息</p>
        </div>

        <el-form
          ref="formRef"
          :model="loginForm"
          :rules="rules"
          label-position="top"
          class="login-form"
          @submit.prevent="handleLogin"
        >
          <el-form-item prop="username" label="用户名">
            <el-input
              v-model="loginForm.username"
              placeholder="请输入用户名"
              size="large"
              clearable
              autocomplete="username"
              class="custom-input"
            >
              <template #prefix>
                <el-icon class="input-icon"><User /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item prop="password" label="密码">
            <el-input
              v-model="loginForm.password"
              type="password"
              placeholder="请输入密码"
              size="large"
              show-password
              autocomplete="current-password"
              class="custom-input"
            >
              <template #prefix>
                <el-icon class="input-icon"><Lock /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <div class="form-options">
            <el-checkbox v-model="rememberMe">记住我</el-checkbox>
            <a href="#" class="forgot-link" @click.prevent="showForgotDialog">忘记密码？</a>
          </div>

          <el-form-item class="submit-item">
            <el-button
              type="primary"
              size="large"
              :loading="loading"
              class="login-btn"
              native-type="submit"
            >
              {{ loading ? '登录中...' : '登 录' }}
            </el-button>
          </el-form-item>
        </el-form>

        <div class="register-section">
          <span class="register-text">还没有账号？</span>
          <router-link to="/register" class="register-link">立即注册</router-link>
        </div>
      </div>
    </div>

    <!-- 忘记密码弹窗 -->
    <el-dialog
      v-model="forgotDialogVisible"
      title="忘记密码"
      width="400px"
      class="forgot-dialog"
    >
      <el-form :model="forgotForm" label-position="top" class="forgot-form">
        <el-alert type="info" :closable="false" show-icon style="margin-bottom: 16px;">
          请联系系统管理员重置密码
        </el-alert>
        <el-form-item label="用户名">
          <el-input v-model="forgotForm.username" placeholder="请输入用户名" size="large" clearable>
            <template #prefix><el-icon><User /></el-icon></template>
          </el-input>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="forgotDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleResetPassword" :loading="resetLoading">提交申请</el-button>
      </template>
    </el-dialog>

    <!-- 法律文本弹窗 -->
    <el-dialog
      v-model="legalDialogVisible"
      :title="legalDialogTitle"
      width="600px"
      class="legal-dialog"
    >
      <div class="legal-content" v-html="legalDialogContent"></div>
      <template #footer>
        <el-button type="primary" @click="legalDialogVisible = false">我已阅读</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { ElMessage } from 'element-plus'
import { User, Lock, Moon, Sunny, MagicStick, CopyDocument, Message } from '@element-plus/icons-vue'
import { authAPI } from '@/api'

const router = useRouter()
const authStore = useAuthStore()
const themeStore = useThemeStore()

const formRef = ref(null)
const loading = ref(false)
const mounted = ref(false)
const rememberMe = ref(false)
const forgotDialogVisible = ref(false)
const resetLoading = ref(false)
const legalDialogVisible = ref(false)
const legalDialogTitle = ref('')
const legalDialogContent = ref('')

const loginForm = reactive({
  username: '',
  password: ''
})

const forgotForm = reactive({
  username: ''
})

const isDark = computed(() => themeStore.isDark)

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const forgotRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入新密码', trigger: 'blur' }, { min: 6, message: '密码至少6位', trigger: 'blur' }],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== forgotForm.password) {
          callback(new Error('两次输入密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

const showForgotDialog = () => {
  forgotDialogVisible.value = true
}

const handleResetPassword = async () => {
  if (!forgotForm.username) {
    ElMessage.warning('请输入用户名')
    return
  }
  resetLoading.value = true
  try {
    // 调用忘记密码API，显示管理员联系信息
    const result = await authAPI.forgotPassword(forgotForm.username)
    ElMessage.info(result.data?.message || '请联系系统管理员重置密码')
    forgotDialogVisible.value = false
    forgotForm.username = ''
  } catch (error) {
    ElMessage.error(error.message || '请求失败')
  } finally {
    resetLoading.value = false
  }
}

const showLegalDialog = (type) => {
  if (type === 'agreement') {
    legalDialogTitle.value = '用户协议'
    legalDialogContent.value = `
      <h3>智题 AIQuiz 用户协议</h3>
      <p>欢迎您使用智题 AIQuiz 系统。</p>
      <h4>一、服务说明</h4>
      <p>智题 AIQuiz 是一款基于人工智能技术的智能题库管理系统，提供AI出题、智能组卷、试题审核等功能。</p>
      <h4>二、使用规范</h4>
      <p>用户在使用本系统时，应遵守中华人民共和国相关法律法规，不得利用本系统从事违法违规活动。</p>
      <h4>三、知识产权</h4>
      <p>本系统生成的试题均为AI原创模拟题，不涉及真实考试真题。用户不得将系统生成的试题用于商业用途或进行二次传播。</p>
      <h4>四、免责声明</h4>
      <p>本系统仅作为辅助教学工具，生成的模拟题仅供参考学习使用。对于因使用本系统而产生的任何直接或间接损失，我方不承担任何责任。</p>
    `
  } else if (type === 'privacy') {
    legalDialogTitle.value = '隐私政策'
    legalDialogContent.value = `
      <h3>智题 AIQuiz 隐私政策</h3>
      <p>我们承诺保护您的个人隐私。</p>
      <h4>一、信息收集</h4>
      <p>我们收集您注册时提供的用户名、邮箱等信息，以及您在使用系统过程中产生的操作日志。</p>
      <h4>二、信息使用</h4>
      <p>您的信息仅用于系统运行和用户身份验证，不会提供给任何第三方。</p>
      <h4>三、信息保护</h4>
      <p>我们采用行业标准的安全措施保护您的个人信息，防止信息泄露、丢失或被篡改。</p>
      <h4>四、联系我们</h4>
      <p>如您对隐私政策有任何疑问，请联系系统管理员。</p>
    `
  }
  legalDialogVisible.value = true
}

const handleLogin = async () => {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const result = await authStore.login(loginForm.username, loginForm.password)
    if (result.success) {
      ElMessage.success('登录成功')
      router.push('/dashboard')
    } else {
      ElMessage.error(result.message || '登录失败')
    }
  } catch (error) {
    ElMessage.error(error.message || '登录失败')
  } finally {
    loading.value = false
  }
}

const toggleTheme = () => themeStore.toggleTheme()

onMounted(() => { mounted.value = true })
</script>

<style scoped>
/* 评估 P2-14：移除 Google Fonts 引入（国内不可达 + 规范使用系统字体栈） */
* { box-sizing: border-box; }

.login-page {
  display: flex;
  min-height: 100vh;
  font-family: 'Geist', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ========== 左侧品牌区 2/3 ========== */
.brand-panel {
  width: 66.67%;
  background: linear-gradient(135deg, #030712 0%, #0F172A 30%, #1E3A5F 70%, #0F172A 100%);
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

@media (max-width: 992px) { .brand-panel { display: none; } }

/* 科技画布 */
.tech-canvas {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.grid-overlay {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(22, 93, 255, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(22, 93, 255, 0.05) 1px, transparent 1px);
  background-size: 40px 40px;
}

.gradient-layers { position: absolute; inset: 0; }

.glow-panel {
  position: absolute;
  border-radius: 50%;
  filter: blur(100px);
}

.gp-1 {
  width: 600px; height: 600px;
  top: -200px; right: -100px;
  background: radial-gradient(circle, rgba(22, 93, 255, 0.5) 0%, transparent 70%);
  animation: pulse-glow 8s ease-in-out infinite;
}

.gp-2 {
  width: 400px; height: 400px;
  bottom: -100px; left: -100px;
  background: radial-gradient(circle, rgba(96, 165, 250, 0.4) 0%, transparent 70%);
  animation: pulse-glow 6s ease-in-out infinite 2s;
}

.gp-3 {
  width: 300px; height: 300px;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  background: radial-gradient(circle, rgba(22, 93, 255, 0.2) 0%, transparent 70%);
  animation: pulse-glow 4s ease-in-out infinite 1s;
}

@keyframes pulse-glow {
  0%, 100% { opacity: 0.6; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.05); }
}

.tech-lines {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.node {
  fill: #165DFF;
  opacity: 0.8;
}

.node.pulse {
  animation: node-pulse 2s ease-in-out infinite;
}

@keyframes node-pulse {
  0%, 100% { r: 6; opacity: 0.8; }
  50% { r: 8; opacity: 1; filter: drop-shadow(0 0 8px #165DFF); }
}

.flow-line {
  stroke-dasharray: 1000;
  stroke-dashoffset: 1000;
  animation: draw-line 3s ease forwards;
}

.fl-2 {
  stroke-dashoffset: 800;
  animation-delay: 0.5s;
}

@keyframes draw-line {
  to { stroke-dashoffset: 0; }
}

/* 品牌内容 */
.brand-content {
  position: relative;
  z-index: 10;
  padding: 60px;
  max-width: 640px;
}

.brand-header {
  display: flex;
  align-items: center;
  gap: 24px;
  margin-bottom: 56px;
}

.brand-logo {
  width: 72px; height: 72px;
  background: linear-gradient(135deg, #165DFF 0%, #3B82F6 100%);
  border-radius: 18px;
  display: flex; align-items: center; justify-content: center;
  color: white;
  box-shadow: 0 12px 40px rgba(22, 93, 255, 0.5);
  flex-shrink: 0;
}

.brand-title {
  font-size: 36px; font-weight: 700;
  color: white; margin: 0 0 8px;
  letter-spacing: -1px; line-height: 1.2;
}

.brand-subtitle {
  font-size: 16px; color: rgba(255,255,255,0.6); margin: 0;
}

.brand-features {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.feature-block {
  display: flex;
  align-items: flex-start;
  gap: 20px;
  padding: 20px 24px;
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(22, 93, 255, 0.2);
  border-radius: 14px;
  transition: all 0.3s ease;
}

.feature-block:hover {
  background: rgba(22, 93, 255, 0.1);
  border-color: rgba(22, 93, 255, 0.4);
  transform: translateX(8px);
}

.feature-icon-wrap {
  width: 48px; height: 48px;
  background: linear-gradient(135deg, #165DFF 0%, #3B82F6 100%);
  border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  color: white; flex-shrink: 0;
}

.feature-info h3 {
  font-size: 17px; font-weight: 600;
  color: white; margin: 0 0 6px;
}

.feature-info p {
  font-size: 14px; color: rgba(255,255,255,0.5); margin: 0;
}

/* 法律声明 */
.legal-statement {
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid rgba(22, 93, 255, 0.2);
  text-align: center;
}

.disclaimer {
  font-size: 12px;
  color: rgba(255,255,255,0.5);
  margin: 0 0 12px;
}

.legal-links {
  display: flex;
  justify-content: center;
  gap: 8px;
  font-size: 12px;
}

.legal-links a {
  color: rgba(22, 93, 255, 0.8);
  text-decoration: none;
  transition: color 0.2s;
}

.legal-links a:hover {
  color: #165DFF;
}

.legal-links .divider {
  color: rgba(255,255,255,0.3);
}

/* 法律弹窗内容 */
.legal-content {
  font-size: 14px;
  line-height: 1.8;
  color: #333;
}

.legal-content h3 {
  font-size: 18px;
  margin-bottom: 16px;
  color: #1a1a1a;
}

.legal-content h4 {
  font-size: 15px;
  margin-top: 20px;
  margin-bottom: 8px;
  color: #333;
}

.legal-content p {
  margin-bottom: 12px;
}

/* ========== 右侧表单区 1/3 ========== */
.form-panel {
  width: 33.33%;
  background: #F8FAFC;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.dark-mode .form-panel { background: #0F172A; }

.form-container {
  width: 100%;
  max-width: 320px;
  position: relative;
  opacity: 0;
  transform: translateY(16px);
}

.form-container.animate-in { animation: slideUp 0.4s ease forwards; }

@keyframes slideUp { to { opacity: 1; transform: translateY(0); } }

.theme-toggle {
  position: absolute;
  top: -52px; right: 0;
  width: 38px; height: 38px;
  border-radius: 9px;
  background: white;
  border: 1px solid #E2E8F0;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; color: #64748B;
  transition: all 0.2s ease;
}

.theme-toggle:hover { background: #F1F5F9; border-color: #CBD5E1; }

.dark-mode .theme-toggle { background: #1E293B; border-color: #334155; color: #94A3B8; }
.dark-mode .theme-toggle:hover { background: #334155; }

.form-header { margin-bottom: 24px; }

.form-title {
  font-size: 22px; font-weight: 700;
  color: #0F172A; margin: 0 0 6px;
  letter-spacing: -0.3px;
}

.dark-mode .form-title { color: #F1F5F9; }

.form-desc {
  font-size: 13px; color: #64748B; margin: 0;
}

.dark-mode .form-desc { color: #94A3B8; }

.login-form { margin-bottom: 16px; }

.login-form :deep(.el-form-item) { margin-bottom: 14px; }

.login-form :deep(.el-form-item__label) {
  font-size: 13px; font-weight: 500;
  color: #374151; padding: 0 0 6px; height: auto;
}

.dark-mode .login-form :deep(.el-form-item__label) { color: #E2E8F0; }

.custom-input :deep(.el-input__wrapper) {
  padding: 10px 14px; border-radius: 8px;
  border: 1.5px solid #E2E8F0;
  background: white; box-shadow: none;
  transition: all 0.2s ease;
}

.custom-input :deep(.el-input__wrapper:hover) { border-color: #CBD5E1; }

.custom-input :deep(.el-input__wrapper.is-focus) {
  border-color: #165DFF;
  box-shadow: 0 0 0 3px rgba(22,93,255,0.1);
}

.dark-mode .custom-input :deep(.el-input__wrapper) { background: #1E293B; border-color: #334155; }
.dark-mode .custom-input :deep(.el-input__wrapper:hover) { border-color: #475569; }
.dark-mode .custom-input :deep(.el-input__wrapper.is-focus) { border-color: #3B82F6; box-shadow: 0 0 0 3px rgba(59,130,246,0.15); }

.custom-input :deep(.el-input__inner) { font-size: 14px; color: #0F172A; }
.dark-mode .custom-input :deep(.el-input__inner) { color: #F1F5F9; }
.custom-input :deep(.el-input__inner::placeholder) { color: #94A3B8; }
.dark-mode .custom-input :deep(.el-input__inner::placeholder) { color: #6B7280; }

.input-icon { color: #94A3B8; font-size: 15px; }
.dark-mode .input-icon { color: #6B7280; }

.form-options {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 16px;
}

.form-options :deep(.el-checkbox__label) { font-size: 13px; color: #64748B; }
.dark-mode .form-options :deep(.el-checkbox__label) { color: #94A3B8; }

.forgot-link {
  font-size: 13px; color: #165DFF; text-decoration: none;
  transition: color 0.2s ease;
}

.forgot-link:hover { color: #3B82F6; text-decoration: underline; }
.dark-mode .forgot-link { color: #60A5FA; }
.dark-mode .forgot-link:hover { color: #93C5FD; }

.submit-item :deep(.el-form-item__content) { margin-left: 0 !important; }

.login-btn {
  width: 100%; height: 44px;
  border-radius: 8px; font-size: 14px; font-weight: 600;
  background: linear-gradient(135deg, #165DFF 0%, #3B82F6 100%);
  border: none; box-shadow: 0 4px 12px rgba(22,93,255,0.35);
  transition: all 0.2s ease;
}

.login-btn:hover {
  background: linear-gradient(135deg, #1455E0 0%, #2563EB 100%);
  box-shadow: 0 6px 18px rgba(22,93,255,0.45);
  transform: translateY(-1px);
}

.dark-mode .login-btn { background: linear-gradient(135deg, #3B82F6 0%, #60A5FA 100%); }
.dark-mode .login-btn:hover { background: linear-gradient(135deg, #2563EB 0%, #3B82F6 100%); }

.register-section {
  text-align: center;
  padding-top: 16px;
  border-top: 1px solid #E2E8F0;
}

.dark-mode .register-section { border-top-color: #334155; }

.register-text { font-size: 13px; color: #64748B; }
.register-link { font-size: 13px; font-weight: 500; color: #165DFF; text-decoration: none; margin-left: 4px; }
.register-link:hover { color: #3B82F6; text-decoration: underline; }
.dark-mode .register-text { color: #94A3B8; }
.dark-mode .register-link { color: #60A5FA; }
.dark-mode .register-link:hover { color: #93C5FD; }

/* 忘记密码弹窗 */
.forgot-dialog :deep(.el-dialog) { border-radius: 16px; }
.forgot-dialog :deep(.el-dialog__header) { padding: 20px 24px 16px; }
.forgot-dialog :deep(.el-dialog__title) { font-size: 17px; font-weight: 600; color: #0F172A; }
.forgot-dialog :deep(.el-dialog__body) { padding: 8px 24px 16px; }
.forgot-dialog :deep(.el-dialog__footer) { padding: 12px 24px 20px; }

.forgot-form :deep(.el-form-item) { margin-bottom: 14px; }
.forgot-form :deep(.el-form-item__label) { font-size: 13px; font-weight: 500; color: #374151; padding: 0 0 6px; }

@media (max-width: 768px) {
  .form-panel { width: 100%; padding: 32px 24px; }
  .form-container { max-width: 100%; }
  .theme-toggle { top: -48px; }
}
</style>
