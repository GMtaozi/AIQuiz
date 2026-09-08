<template>
  <div class="base-card" :class="[shadowClass, hoverClass, sizeClass]">
    <div v-if="$slots.header || title" class="base-card__header">
      <slot name="header">
        <span class="base-card__title">{{ title }}</span>
        <span v-if="subtitle" class="base-card__subtitle">{{ subtitle }}</span>
      </slot>
    </div>
    <div class="base-card__body">
      <slot />
    </div>
    <div v-if="$slots.footer" class="base-card__footer">
      <slot name="footer" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

/**
 * 基础卡片容器组件
 *
 * @description 通用的卡片容器，支持标题、副标题、阴影、悬浮效果和尺寸调整。
 * 提供 header、default、footer 三个插槽，可灵活组合内容。
 *
 * @example
 * ```vue
 * <!-- 基础用法 -->
 * <BaseCard title="卡片标题">
 *   <p>卡片内容</p>
 * </BaseCard>
 *
 * <!-- 带副标题 -->
 * <BaseCard title="主标题" subtitle="副标题信息">
 *   <p>卡片内容</p>
 * </BaseCard>
 *
 * <!-- 带阴影和悬浮效果 -->
 * <BaseCard shadow="md" hover>
 *   <p>鼠标悬浮时有阴影和位移效果</p>
 * </BaseCard>
 *
 * <!-- 自定义头部插槽 -->
 * <BaseCard>
 *   <template #header>
 *     <div class="custom-header">
 *       <h3>自定义头部</h3>
 *     </div>
 *   </template>
 *   <p>卡片内容</p>
 *   <template #footer>
 *     <div class="custom-footer">
 *       <button>操作按钮</button>
 *     </div>
 *   </template>
 * </BaseCard>
 *
 * <!-- 不同尺寸 -->
 * <BaseCard size="sm">小卡片</BaseCard>
 * <BaseCard size="md">中卡片</BaseCard>
 * <BaseCard size="lg">大卡片</BaseCard>
 * ```
 */
interface Props {
  /** 卡片标题，显示在 header 区域 */
  title?: string
  /** 卡片副标题，显示在标题下方 */
  subtitle?: string
  /** 阴影大小 */
  shadow?: 'none' | 'sm' | 'md' | 'lg'
  /** 是否启用悬浮效果（悬浮时有阴影和位移） */
  hover?: boolean
  /** 卡片尺寸（影响 body 区域内边距） */
  size?: 'sm' | 'md' | 'lg'
}

const props = withDefaults(defineProps<Props>(), {
  shadow: 'sm',
  hover: false,
  size: 'md'
})

const shadowClass = computed(() => `base-card--shadow-${props.shadow}`)
const hoverClass = computed(() => props.hover ? 'base-card--hover' : '')
const sizeClass = computed(() => `base-card--size-${props.size}`)
</script>

<style scoped>
.base-card {
  background-color: var(--surface-primary);
  border-radius: var(--radius-xl);
  border: 1px solid var(--border-default);
  overflow: hidden;
  transition: box-shadow var(--transition-normal), transform var(--transition-normal);
}

.base-card--shadow-none {
  box-shadow: none;
}

.base-card--shadow-sm {
  box-shadow: var(--shadow-sm);
}

.base-card--shadow-md {
  box-shadow: var(--shadow-md);
}

.base-card--shadow-lg {
  box-shadow: var(--shadow-lg);
}

.base-card--hover:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
}

.base-card__header {
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-light);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.base-card__title {
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--text-primary);
}

.base-card__subtitle {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}

.base-card__body {
  padding: var(--space-5);
}

.base-card--size-sm .base-card__body {
  padding: var(--space-3);
}

.base-card--size-lg .base-card__body {
  padding: var(--space-6);
}

.base-card__footer {
  padding: var(--space-3) var(--space-5);
  border-top: 1px solid var(--border-light);
  background-color: var(--surface-tertiary);
}
</style>
