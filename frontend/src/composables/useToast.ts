import { h, render } from 'vue'
import BaseToast from '@/components/common/BaseToast.vue'

interface ToastOptions {
  message: string
  type?: 'success' | 'warning' | 'error' | 'info'
  duration?: number
}

interface ToastItem {
  id: number
  message: string
  type: 'success' | 'warning' | 'error' | 'info'
  duration: number
}

// ============================================================
// 全局单例：Toast 管理器
// - 单一容器，避免重复创建/销毁导致的内存泄漏
// - 队列管理，支持多条 Toast 同时显示（最多 5 条）
// - 自动清理，组件卸载时安全回收
// ============================================================

let container: HTMLElement | null = null
let toastIdCounter = 0
const activeToasts = new Map<number, { vnode: any; el: HTMLElement }>()
const MAX_VISIBLE = 5

/**
 * 获取或创建全局 Toast 容器
 */
function getContainer(): HTMLElement {
  if (!container) {
    container = document.createElement('div')
    container.id = 'toast-container'
    container.style.cssText = [
      'position: fixed',
      'top: 20px',
      'left: 50%',
      'transform: translateX(-50%)',
      'z-index: 9999',
      'display: flex',
      'flex-direction: column',
      'gap: 8px',
      'pointer-events: none'
    ].join(';')
    document.body.appendChild(container)
  }
  return container
}

/**
 * 移除单条 Toast
 */
function removeToast(id: number): void {
  const item = activeToasts.get(id)
  if (!item) return

  // 触发关闭动画
  const el = item.el
  el.style.transition = 'all 0.3s ease'
  el.style.opacity = '0'
  el.style.transform = 'translateX(-50%) translateY(-20px)'

  setTimeout(() => {
    if (el.parentNode) {
      el.parentNode.removeChild(el)
    }
    activeToasts.delete(id)

    // 如果所有 Toast 都关闭了，清理容器
    if (activeToasts.size === 0 && container) {
      if (container.parentNode) {
        container.parentNode.removeChild(container)
      }
      container = null
    }
  }, 300)
}

/**
 * 显示一条 Toast
 */
function showToast(options: ToastOptions): void {
  const { message, type = 'info', duration = 3000 } = options
  const id = ++toastIdCounter

  const containerEl = getContainer()

  // 创建独立的 DOM 元素（每条 Toast 独立定位）
  const el = document.createElement('div')
  el.style.cssText = 'pointer-events: auto;'

  // 如果超过最大可见数，移除最早的一条
  if (activeToasts.size >= MAX_VISIBLE) {
    const firstId = activeToasts.keys().next().value as number
    if (firstId !== undefined) {
      removeToast(firstId)
    }
  }

  // 创建 Vue 组件
  const vnode = h(BaseToast, {
    message,
    type,
    duration,
    visible: true,
    onClose: () => removeToast(id)
  })

  render(vnode, el)
  containerEl.appendChild(el)
  activeToasts.set(id, { vnode, el })

  // 自动关闭
  if (duration > 0) {
    setTimeout(() => {
      removeToast(id)
    }, duration)
  }
}

/**
 * 清空所有 Toast
 */
function clearAll(): void {
  activeToasts.forEach((_, id) => removeToast(id))
}

/**
 * 程序化调用入口
 */
export function useToast() {
  return {
    showToast,
    success: (message: string, duration?: number) => showToast({ message, type: 'success', duration }),
    warning: (message: string, duration?: number) => showToast({ message, type: 'warning', duration }),
    error: (message: string, duration?: number) => showToast({ message, type: 'error', duration }),
    info: (message: string, duration?: number) => showToast({ message, type: 'info', duration }),
    clearAll
  }
}

// 导出单例管理器（供高级场景使用）
export const toastManager = {
  showToast,
  clearAll,
  get activeCount() {
    return activeToasts.size
  }
}
