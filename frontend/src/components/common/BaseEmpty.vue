<template>
  <div class="base-empty" :class="`base-empty--${size}`">
    <div class="base-empty__icon">
      <slot name="icon">
        <svg :width="iconSize" :height="iconSize" viewBox="0 0 80 80" fill="none">
          <rect x="10" y="15" width="60" height="50" rx="4" fill="var(--surface-tertiary)" stroke="var(--border-default)" stroke-width="2"/>
          <rect x="20" y="28" width="40" height="4" rx="1" fill="var(--border-strong)" opacity="0.5"/>
          <rect x="20" y="38" width="30" height="4" rx="1" fill="var(--border-strong)" opacity="0.3"/>
          <rect x="20" y="48" width="35" height="4" rx="1" fill="var(--border-strong)" opacity="0.3"/>
          <circle cx="60" cy="20" r="8" fill="var(--color-success)" opacity="0.2"/>
          <text x="60" y="24" text-anchor="middle" fill="var(--color-success)" font-size="12">?</text>
        </svg>
      </slot>
    </div>
    <p v-if="description" class="base-empty__description">{{ description }}</p>
    <div v-if="$slots.action" class="base-empty__action">
      <slot name="action" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

/**
 * 空状态组件
 *
 * @description 用于显示无数据、无结果等空状态场景。
 * 支持自定义图标、描述文本和操作按钮区域。
 *
 * @example
 * ```vue
 * <!-- 基础用法 -->
 * <BaseEmpty description="暂无数据" />
 *
 * <!-- 自定义图标 -->
 * <BaseEmpty description="没有找到结果">
 *   <template #icon>
 *     <Icon icon="mdi:magnify" size="lg" />
 *   </template>
 * </BaseEmpty>
 *
 * <!-- 带操作按钮 -->
 * <BaseEmpty description="还没有创建任何试卷">
 *   <template #action>
 *     <BaseButton type="primary" @click="createPaper">立即创建</BaseButton>
 *   </template>
 * </BaseEmpty>
 *
 * <!-- 不同尺寸 -->
 * <BaseEmpty size="sm" description="小尺寸空状态" />
 * <BaseEmpty size="md" description="中尺寸空状态" />
 * <BaseEmpty size="lg" description="大尺寸空状态" />
 * ```
 */
interface Props {
  /** 空状态描述文本 */
  description?: string
  /** 空状态尺寸（影响内边距和图标大小） */
  size?: 'sm' | 'md' | 'lg'
}

const props = withDefaults(defineProps<Props>(), {
  description: '暂无数据',
  size: 'md'
})

const iconSize = computed(() => {
  const sizes = { sm: 60, md: 80, lg: 120 }
  return sizes[props.size]
})
</script>

<style scoped>
.base-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-10) var(--space-5);
}

.base-empty--sm {
  padding: var(--space-6) var(--space-3);
}

.base-empty--lg {
  padding: var(--space-16) var(--space-8);
}

.base-empty__icon {
  margin-bottom: var(--space-4);
  opacity: 0.6;
}

.base-empty__description {
  font-size: var(--font-size-base);
  color: var(--text-secondary);
  margin: 0;
  text-align: center;
}

.base-empty__action {
  margin-top: var(--space-4);
}
</style>
