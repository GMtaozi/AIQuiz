<template>
  <button
    class="base-button"
    :class="[
      `base-button--${type}`,
      `base-button--${size}`,
      { 'base-button--disabled': disabled }
    ]"
    :disabled="disabled"
    @click="handleClick"
  >
    <span v-if="loading" class="base-button__loading">
      <span class="base-button__spinner" />
    </span>
    <span class="base-button__content">
      <slot />
    </span>
  </button>
</template>

<script setup lang="ts">
/**
 * 基础按钮组件
 *
 * @description 统一的按钮组件，支持多种类型、尺寸和状态。
 * 提供 primary、secondary、text、danger 四种类型，
 * sm、md、lg 三种尺寸，以及 loading 和 disabled 状态。
 *
 * @example
 * ```vue
 * <!-- 基础用法 -->
 * <BaseButton>点击我</BaseButton>
 *
 * <!-- 不同类型 -->
 * <BaseButton type="primary">主要按钮</BaseButton>
 * <BaseButton type="secondary">次要按钮</BaseButton>
 * <BaseButton type="text">文字按钮</BaseButton>
 * <BaseButton type="danger">危险按钮</BaseButton>
 *
 * <!-- 不同尺寸 -->
 * <BaseButton size="sm">小按钮</BaseButton>
 * <BaseButton size="md">中按钮</BaseButton>
 * <BaseButton size="lg">大按钮</BaseButton>
 *
 * <!-- 加载状态 -->
 * <BaseButton loading>提交中...</BaseButton>
 *
 * <!-- 禁用状态 -->
 * <BaseButton disabled>不可点击</BaseButton>
 *
 * <!-- 事件处理 -->
 * <BaseButton @click="handleClick">点击事件</BaseButton>
 * ```
 */
interface Props {
  /** 按钮类型 */
  type?: 'primary' | 'secondary' | 'text' | 'danger'
  /** 按钮尺寸 */
  size?: 'sm' | 'md' | 'lg'
  /** 是否禁用 */
  disabled?: boolean
  /** 是否显示加载状态 */
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  type: 'primary',
  size: 'md',
  disabled: false,
  loading: false
})

const emit = defineEmits<{
  /** 点击事件，仅在非禁用且非加载状态下触发 */
  click: [event: MouseEvent]
}>()

const handleClick = (event: MouseEvent) => {
  if (!props.disabled && !props.loading) {
    emit('click', event)
  }
}
</script>

<style scoped>
.base-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  border: none;
  cursor: pointer;
  font-family: var(--font-family);
  font-weight: 500;
  transition: all var(--transition-fast);
  user-select: none;
  white-space: nowrap;
}

.base-button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

/* 类型 */
.base-button--primary {
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-hover) 100%);
  color: white;
  box-shadow: 0 2px 8px rgba(var(--color-primary-rgb), 0.25);
}

.base-button--primary:hover:not(:disabled) {
  background: linear-gradient(135deg, var(--color-primary-dark) 0%, var(--color-primary) 100%);
  box-shadow: 0 4px 12px rgba(var(--color-primary-rgb), 0.35);
  transform: translateY(-1px);
}

.base-button--secondary {
  background: var(--surface-primary);
  color: var(--text-primary);
  border: 1px solid var(--border-default);
}

.base-button--secondary:hover:not(:disabled) {
  background: var(--surface-tertiary);
  border-color: var(--border-strong);
}

.base-button--text {
  background: transparent;
  color: var(--color-primary);
}

.base-button--text:hover:not(:disabled) {
  background: rgba(var(--color-primary-rgb), 0.05);
}

.base-button--danger {
  background: linear-gradient(135deg, var(--color-danger) 0%, #e74c3c 100%);
  color: white;
  box-shadow: 0 2px 8px rgba(245, 108, 108, 0.25);
}

.base-button--danger:hover:not(:disabled) {
  box-shadow: 0 4px 12px rgba(245, 108, 108, 0.35);
  transform: translateY(-1px);
}

/* 尺寸 */
.base-button--sm {
  padding: var(--space-1) var(--space-3);
  font-size: var(--font-size-xs);
  border-radius: var(--radius-md);
}

.base-button--md {
  padding: var(--space-2) var(--space-4);
  font-size: var(--font-size-base);
  border-radius: var(--radius-lg);
}

.base-button--lg {
  padding: var(--space-3) var(--space-6);
  font-size: var(--font-size-lg);
  border-radius: var(--radius-lg);
}

/* 加载状态 */
.base-button__loading {
  display: flex;
  align-items: center;
}

.base-button__spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
