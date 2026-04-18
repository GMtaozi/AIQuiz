import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'

const THEME_KEY = '__app_theme__'

export const useThemeStore = defineStore('theme', () => {
  // 从 localStorage 恢复主题设置
  const savedTheme = localStorage.getItem(THEME_KEY)
  const isDark = ref(savedTheme === 'dark')

  // 实际生效的主题（考虑系统偏好）
  const effectiveTheme = computed(() => {
    if (isDark.value) return 'dark'
    return 'light'
  })

  // 是否启用深色模式
  const isDarkMode = computed(() => effectiveTheme.value === 'dark')

  // 切换主题
  function toggleTheme() {
    isDark.value = !isDark.value
    localStorage.setItem(THEME_KEY, isDark.value ? 'dark' : 'light')
    applyTheme()
  }

  // 设置特定主题
  function setTheme(theme) {
    isDark.value = theme === 'dark'
    localStorage.setItem(THEME_KEY, isDark.value ? 'dark' : 'light')
    applyTheme()
  }

  // 应用主题到 document
  function applyTheme() {
    const html = document.documentElement
    if (isDark.value) {
      html.classList.add('dark-mode')
    } else {
      html.classList.remove('dark-mode')
    }
  }

  // 监听主题变化，自动应用到 document
  watch(isDark, () => {
    applyTheme()
  }, { immediate: true })

  // 初始化时应用主题
  applyTheme()

  return {
    isDark,
    isDarkMode,
    effectiveTheme,
    toggleTheme,
    setTheme,
    applyTheme
  }
})
