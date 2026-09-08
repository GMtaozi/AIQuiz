<template>
  <div class="base-skeleton" :class="`base-skeleton--${variant}`">
    <div v-for="i in rows" :key="i" class="base-skeleton__row" :style="{ '--delay': `${i * 100}ms` }">
      <div v-if="avatar" class="base-skeleton__avatar" />
      <div class="base-skeleton__content">
        <div class="base-skeleton__line base-skeleton__line--title" />
        <div class="base-skeleton__line" />
        <div v-if="variant === 'card'" class="base-skeleton__line base-skeleton__line--short" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 骨架屏组件
 *
 * @description 用于在内容加载时显示占位骨架，提升用户体验。
 * 支持列表、卡片、表格三种变体，可配置行数和头像占位。
 *
 * @example
 * ```vue
 * <!-- 基础列表骨架 -->
 * <BaseSkeleton :rows="3" />
 *
 * <!-- 带头像的列表骨架 -->
 * <BaseSkeleton :rows="4" avatar />
 *
 * <!-- 卡片骨架 -->
 * <BaseSkeleton variant="card" :rows="2" />
 *
 * <!-- 表格骨架 -->
 * <BaseSkeleton variant="table" :rows="5" />
 *
 * <!-- 条件显示 -->
 * <BaseSkeleton v-if="loading" :rows="3" />
 * <div v-else>实际内容</div>
 * ```
 */
interface Props {
  /** 骨架行数 */
  rows?: number
  /** 是否显示头像占位 */
  avatar?: boolean
  /** 骨架屏变体类型 */
  variant?: 'list' | 'card' | 'table'
}

withDefaults(defineProps<Props>(), {
  rows: 3,
  avatar: false,
  variant: 'list'
})
</script>

<style scoped>
.base-skeleton {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.base-skeleton__row {
  display: flex;
  gap: var(--space-3);
  align-items: flex-start;
  animation: shimmer 1.5s infinite var(--delay, 0ms);
}

.base-skeleton__avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(90deg, var(--surface-tertiary) 25%, var(--border-light) 50%, var(--surface-tertiary) 75%);
  background-size: 200% 100%;
  flex-shrink: 0;
}

.base-skeleton__content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.base-skeleton__line {
  height: 12px;
  border-radius: var(--radius-sm);
  background: linear-gradient(90deg, var(--surface-tertiary) 25%, var(--border-light) 50%, var(--surface-tertiary) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}

.base-skeleton__line--title {
  width: 40%;
  height: 16px;
}

.base-skeleton__line--short {
  width: 60%;
}

@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}
</style>
