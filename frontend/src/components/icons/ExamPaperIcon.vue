<template>
  <svg
    class="exam-paper-icon"
    :width="size"
    :height="size"
    viewBox="0 0 48 48"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    :style="{ color: color }"
  >
    <!-- Paper background with slight rotation for dynamic feel -->
    <g transform="rotate(-3 24 24)">
      <!-- Main paper -->
      <rect
        x="8"
        y="6"
        width="32"
        height="36"
        rx="2"
        fill="currentColor"
        fill-opacity="0.1"
        stroke="currentColor"
        stroke-width="2"
      />

      <!-- Folded corner -->
      <path
        d="M32 6 L40 6 L40 14"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        fill="none"
      />
      <path
        d="M32 6 L32 14 L40 14"
        fill="currentColor"
        fill-opacity="0.15"
      />

      <!-- Question lines (representing text/questions) -->
      <line x1="14" y1="18" x2="26" y2="18" stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity="0.6" />
      <line x1="14" y1="24" x2="22" y2="24" stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity="0.4" />

      <!-- Multiple choice options -->
      <circle cx="14" cy="30" r="2" fill="currentColor" opacity="0.7" />
      <line x1="18" y1="30" x2="28" y2="30" stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity="0.5" />

      <circle cx="14" cy="36" r="2" fill="currentColor" opacity="0.7" />
      <line x1="18" y1="36" x2="24" y2="36" stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity="0.5" />

      <!-- Checkmark badge (indicating verified/published) -->
      <circle cx="38" cy="38" r="8" fill="#67C23A" />
      <path
        d="M34 38 L37 41 L43 35"
        stroke="white"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        fill="none"
      />
    </g>
  </svg>
</template>

<script setup>
defineProps({
  size: {
    type: [Number, String],
    default: 20
  },
  color: {
    type: String,
    default: 'currentColor'
  }
})
</script>

<style scoped>
.exam-paper-icon {
  display: inline-block;
  vertical-align: middle;
  transition: transform 0.2s ease;
}

.exam-paper-icon:hover {
  transform: scale(1.1) rotate(3deg);
}
</style>
