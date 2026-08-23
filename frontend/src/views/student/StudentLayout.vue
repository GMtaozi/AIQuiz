<template>
  <div class="student-layout">
    <header class="topbar">
      <div class="topbar-inner">
        <div class="brand">
          <span class="logo">智题 AIQuiz</span>
          <span class="divider"></span>
          <span class="subtitle">学生端</span>
        </div>
        <nav class="nav">
          <router-link to="/student/exams" class="nav-item" active-class="active">考试中心</router-link>
          <router-link to="/student/scores" class="nav-item" active-class="active">我的成绩</router-link>
        </nav>
        <div class="user-area">
          <span class="username">{{ authStore.user?.username }}</span>
          <el-button text size="small" @click="handleLogout">退出</el-button>
        </div>
      </div>
    </header>
    <main class="content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const router = useRouter()

const handleLogout = async () => {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped lang="scss">
.student-layout {
  min-height: 100vh;
  background: #F5F7FA;
}

.topbar {
  background: #FFFFFF;
  border-bottom: 1px solid #E5E6EB;
  position: sticky;
  top: 0;
  z-index: 10;
}

.topbar-inner {
  max-width: 1080px;
  margin: 0 auto;
  padding: 0 24px;
  height: 56px;
  display: flex;
  align-items: center;
  gap: 32px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;

  .logo {
    font-size: 17px;
    font-weight: 600;
    color: #165DFF;
  }

  .divider {
    width: 1px;
    height: 16px;
    background: #E5E6EB;
  }

  .subtitle {
    font-size: 13px;
    color: #4E5969;
  }
}

.nav {
  display: flex;
  gap: 8px;
  flex: 1;

  .nav-item {
    padding: 6px 16px;
    border-radius: 6px;
    font-size: 14px;
    color: #4E5969;
    text-decoration: none;
    transition: all 0.2s;

    &:hover {
      background: #F2F3F5;
      color: #165DFF;
    }

    &.active {
      background: #E8F3FF;
      color: #165DFF;
      font-weight: 500;
    }
  }
}

.user-area {
  display: flex;
  align-items: center;
  gap: 8px;

  .username {
    font-size: 14px;
    color: #1D2129;
  }
}

.content {
  max-width: 1080px;
  margin: 0 auto;
  padding: 24px;
}
</style>
