<template>
  <transition name="toast-fade">
    <div
      v-if="visible"
      class="base-toast"
      :class="`base-toast--${type}`"
      @click="handleClose"
    >
      <span class="base-toast__icon">
        <component :is="iconComponent" />
      </span>
      <span class="base-toast__message">{{ message }}</span>
      <button class="base-toast__close" @click.stop="handleClose">
        <el-icon><Close /></el-icon>
      </button>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { SuccessFilled, WarningFilled, CircleCloseFilled, InfoFilled, Close } from '@element-plus/icons-vue'

/**
 * 消息提示组件
 *
 * @description 顶部居中显示的消息提示，支持成功、警告、错误、信息四种类型。
 * 可自动关闭（通过 duration 配置），也可手动点击关闭。
 *
 * @example
 * ```vue
 * <!-- 基础用法 -->
 * <BaseToast message="操作成功" type="success" />
 *
 * <!-- 不同类型 -->
 * <BaseToast message="成功消息" type="success" />
 * <BaseToast message="警告消息" type="warning" />
 * <BaseToast message="错误消息" type="error" />
 * <BaseToast message="信息消息" type="info" />
 *
 * <!-- 自定义时长（毫秒），0 表示不自动关闭 -->
 * <BaseToast message="永久显示" :duration="0" />
 *
 * <!-- 控制显示 -->
 * <BaseToast v-if="showToast" message="提示消息" @close="showToast = false" />
 * ```
 */
interface Props {
  /** 提示消息文本 */
  message: string
  /** 提示类型 */
  type?: 'success' | 'warning' | 'error' | 'info'
  /** 自动关闭时长（毫秒），0 表示不自动关闭 */
  duration?: number
  /** 是否可见 */
  visible?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  type: 'info',
  duration: 3000,
  visible: true
})

const emit = defineEmits<{
  /** 关闭事件 */
  close: []
}>()

const visible = ref(props.visible)

const iconComponent = computed(() => {
  const icons = {
    success: SuccessFilled,
    warning: WarningFilled,
    error: CircleCloseFilled,
    info: InfoFilled
  }
  return icons[props.type]
})

let timer: ReturnType<typeof setTimeout> | null = null

const startTimer = () => {
  if (props.duration > 0) {
    timer = setTimeout(() => {
      handleClose()
    }, props.duration)
  }
}

const handleClose = () => {
  visible.value = false
  if (timer) {
    clearTimeout(timer)
    timer = null
  }
  emit('close')
}

watch(() => props.visible, (val) => {
  visible.value = val
  if (val) startTimer()
}, { immediate: true })
</script>

<style scoped>
.base-toast {
  position: fixed;
  top: var(--space-6);
  left: 50%;
  transform: translateX(-50%);
  z-index: 9999;
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-5);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  background: var(--surface-primary);
  border: 1px solid var(--border-default);
  min-width: 300px;
  max-width: 500px;
  cursor: pointer;
}

.base-toast--success {
  border-color: var(--color-success);
  background: linear-gradient(135deg, rgba(103, 194, 58, 0.05) 0%, var(--surface-primary) 100%);
}

.base-toast--warning {
  border-color: var(--color-warning);
  background: linear-gradient(135deg, rgba(230, 162, 60, 0.05) 0%, var(--surface-primary) 100%);
}

.base-toast--error {
  border-color: var(--color-danger);
  background: linear-gradient(135deg, rgba(245, 108, 108, 0.05) 0%, var(--surface-primary) 100%);
}

.base-toast--info {
  border-color: var(--color-primary);
  background: linear-gradient(135deg, rgba(var(--color-primary-rgb), 0.05) 0%, var(--surface-primary) 100%);
}

.base-toast__icon {
  display: flex;
  align-items: center;
  font-size: 18px;
}

.base-toast--success .base-toast__icon { color: var(--color-success); }
.base-toast--warning .base-toast__icon { color: var(--color-warning); }
.base-toast--error .base-toast__icon { color: var(--color-danger); }
.base-toast--info .base-toast__icon { color: var(--color-primary); }

.base-toast__message {
  flex: 1;
  font-size: var(--font-size-base);
  color: var(--text-primary);
  line-height: 1.4;
}

.base-toast__close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: none;
  background: transparent;
  cursor: pointer;
  color: var(--text-secondary);
  transition: all var(--transition-fast);
}

.base-toast__close:hover {
  background: var(--surface-tertiary);
  color: var(--text-primary);
}

/* 过渡动画 */
.toast-fade-enter-active {
  animation: toastIn 0.3s ease forwards;
}

.toast-fade-leave-active {
  animation: toastOut 0.3s ease forwards;
}

@keyframes toastIn {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(-20px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}

@keyframes toastOut {
  from {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
  to {
    opacity: 0;
    transform: translateX(-50%) translateY(-20px);
  }
}
</style>
