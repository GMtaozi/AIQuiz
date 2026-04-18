<template>
  <div class="redirect-page">
    <div class="redirect-content">
      <div class="spinner"></div>
      <p>正在跳转到登录页面...</p>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

onMounted(() => {
  router.replace('/login')
})
</script>

<style scoped>
.redirect-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #F8FAFC;
}

.redirect-content {
  text-align: center;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #E2E8F0;
  border-top-color: #165DFF;
  border-radius: 50%;
  margin: 0 auto 16px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

p {
  font-family: 'DM Sans', sans-serif;
  font-size: 14px;
  color: #64748B;
  margin: 0;
}
</style>
