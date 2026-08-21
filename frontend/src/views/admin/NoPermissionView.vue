<template>
  <div class="no-permission-page">
    <div class="no-permission-card">
      <div class="icon-wrapper">
        <el-icon :size="64" color="#909399"><Lock /></el-icon>
      </div>
      <h1 class="title">暂无访问权限</h1>
      <p class="message">请联系管理员分配权限后再试</p>
      <el-button type="primary" @click="handleLogout">退出登录</el-button>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const router = useRouter()
const authStore = useAuthStore()

const handleLogout = () => {
  authStore.logout()
  router.push({ name: 'Login' })
}
</script>

<style scoped>
.no-permission-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  /* 评估 P2-14：原紫色渐变违反 DESIGN.md「Don't use purple gradient」，改为规范浅灰底 */
  background: #F5F7FA;
}

.no-permission-card {
  background: white;
  border-radius: 16px;
  padding: 48px 40px;
  text-align: center;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
  max-width: 400px;
  width: 90%;
}

.icon-wrapper {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  background: #f5f5f5;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 24px;
}

.title {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 12px;
}

.message {
  font-size: 16px;
  color: #909399;
  margin: 0 0 32px;
  line-height: 1.6;
}

.el-button {
  width: 160px;
  height: 40px;
  font-size: 16px;
}
</style>
