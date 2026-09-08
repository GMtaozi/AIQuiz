<template>
  <div class="base-loading" :class="`base-loading--${size}`">
    <div class="base-loading__spinner" />
    <p v-if="text" class="base-loading__text">{{ text }}</p>
  </div>
</template>

<script setup lang="ts">
/**
 * 加载状态组件
 *
 * @description 用于显示页面或区域的加载状态。
 * 提供旋转动画和可选的加载文本提示。
 *
 * @example
 * ```vue
 * <!-- 基础用法 -->
 * <BaseLoading />
 *
 * <!-- 带加载文本 -->
 * <BaseLoading text="正在加载数据..." />
 *
 * <!-- 不同尺寸 -->
 * <BaseLoading size="sm" text="小尺寸加载" />
 * <BaseLoading size="md" text="中尺寸加载" />
 * <BaseLoading size="lg" text="大尺寸加载" />
 *
 * <!-- 条件显示 -->
 * <BaseLoading v-if="isLoading" text="加载中，请稍候..." />
 * <div v-else>数据已加载</div>
 * ```
 */
interface Props {
  /** 加载文本提示 */
  text?: string
  /** 加载尺寸（影响 spinner 大小） */
  size?: 'sm' | 'md' | 'lg'
}

withDefaults(defineProps<Props>(), {
  text: '',
  size: 'md'
})
</script>

<style scoped>
.base-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-10) var(--space-5);
}

.base-loading__spinner {
  border: 3px solid var(--border-light);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.base-loading--sm .base-loading__spinner {
  width: 20px;
  height: 20px;
  border-width: 2px;
}

.base-loading--md .base-loading__spinner {
  width: 32px;
  height: 32px;
}

.base-loading--lg .base-loading__spinner {
  width: 48px;
  height: 48px;
  border-width: 4px;
}

.base-loading__text {
  margin-top: var(--space-3);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
