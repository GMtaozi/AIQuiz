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
  background: var(--surface-secondary);
}

.topbar {
  background: var(--surface-primary);
  border-bottom: 1px solid var(--border-default);
  position: sticky;
  top: 0;
  z-index: 10;
}

.topbar-inner {
  max-width: 1080px;
  margin: 0 auto;
  padding: 0 var(--space-6);
  height: 56px;
  display: flex;
  align-items: center;
  gap: var(--space-8);
}

.brand {
  display: flex;
  align-items: center;
  gap: var(--space-3);

  .logo {
    font-size: var(--font-size-lg);
    font-weight: 600;
    color: var(--color-primary);
  }

  .divider {
    width: 1px;
    height: 16px;
    background: var(--border-default);
  }

  .subtitle {
    font-size: var(--font-size-sm);
    color: var(--text-regular);
  }
}

.nav {
  display: flex;
  gap: var(--space-2);
  flex: 1;

  .nav-item {
    padding: var(--space-1) var(--space-4);
    border-radius: var(--radius-md);
    font-size: var(--font-size-base);
    color: var(--text-regular);
    text-decoration: none;
    transition: all var(--transition-fast);

    &:hover {
      background: var(--surface-tertiary);
      color: var(--color-primary);
    }

    &.active {
      background: rgba(var(--color-primary-rgb), 0.1);
      color: var(--color-primary);
      font-weight: 500;
    }
  }
}

.user-area {
  display: flex;
  align-items: center;
  gap: var(--space-2);

  .username {
    font-size: var(--font-size-base);
    color: var(--text-primary);
  }
}

.content {
  max-width: 1080px;
  margin: 0 auto;
  padding: var(--space-6);
}
</style>
