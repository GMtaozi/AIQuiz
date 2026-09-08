<template>
  <IconifyIcon
    :icon="icon"
    :class="['base-icon', sizeClass, { 'base-icon--spin': spin }]"
    :style="styleObject"
    :aria-label="ariaLabel"
    :role="ariaLabel ? 'img' : 'presentation'"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Icon as IconifyIcon } from '@iconify/vue'

/**
 * 统一图标组件
 *
 * @description 基于 Iconify 的轻量级图标组件，支持 100000+ 图标。
 * 通过图标字符串名称引用图标，支持尺寸、颜色、旋转动画。
 *
 * @example
 * ```vue
 * <!-- 基础用法 -->
 * <Icon icon="mdi:search" />
 *
 * <!-- 不同尺寸 -->
 * <Icon icon="mdi:delete" size="xs" />
 * <Icon icon="mdi:edit" size="sm" />
 * <Icon icon="mdi:plus" size="md" />
 * <Icon icon="mdi:refresh" size="lg" />
 * <Icon icon="mdi:settings" size="xl" />
 *
 * <!-- 自定义颜色 -->
 * <Icon icon="mdi:heart" color="red" />
 * <Icon icon="mdi:check" color="var(--color-success)" />
 *
 * <!-- 旋转动画（加载状态） -->
 * <Icon icon="mdi:loading" spin />
 *
 * <!-- 无障碍标签 -->
 * <Icon icon="mdi:close" aria-label="关闭" />
 * ```
 *
 * @example
 * ```vue
 * <!-- 替代 Element Plus 图标 -->
 * <!-- 之前 -->
 * <el-icon><Search /></el-icon>
 * <!-- 之后 -->
 * <Icon icon="mdi:search" />
 * ```
 */
interface Props {
  /** 图标名称，格式为 "集合:图标名"，如 "mdi:search"、"mdi:delete" */
  icon: string
  /** 图标尺寸预设（xs/sm/md/lg/xl）或具体像素数值 */
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | number
  /** 图标颜色，支持 CSS 颜色值 */
  color?: string
  /** 是否启用旋转动画（常用于加载状态） */
  spin?: boolean
  /** 无障碍标签，设置后图标具有 img 角色 */
  ariaLabel?: string
}

const props = withDefaults(defineProps<Props>(), {
  size: 'md',
  color: undefined,
  spin: false,
  ariaLabel: undefined
})

const sizeMap: Record<string, string> = {
  xs: '12px',
  sm: '14px',
  md: '16px',
  lg: '20px',
  xl: '24px'
}

const sizeClass = computed(() => {
  if (typeof props.size === 'number') return ''
  return `base-icon--${props.size}`
})

const styleObject = computed(() => {
  const fontSize = typeof props.size === 'number' 
    ? `${props.size}px` 
    : sizeMap[props.size as string]
  return {
    fontSize,
    color: props.color,
    animation: props.spin ? 'base-icon-spin 1s linear infinite' : undefined
  }
})
</script>

<style scoped>
.base-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  vertical-align: middle;
}

.base-icon--spin {
  animation: base-icon-spin 1s linear infinite;
}

@keyframes base-icon-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
