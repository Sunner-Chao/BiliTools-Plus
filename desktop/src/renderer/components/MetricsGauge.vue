<template>
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
    <h3 class="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">{{ title }}</h3>
    <div class="flex items-baseline gap-2">
      <span class="text-3xl font-bold" :class="valueColor">{{ displayValue }}</span>
      <span v-if="unit" class="text-sm text-gray-500 dark:text-gray-400">{{ unit }}</span>
    </div>
    <div v-if="subtitle" class="text-xs text-gray-400 dark:text-gray-500 mt-1">{{ subtitle }}</div>
    <div class="mt-3 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
      <div
        class="h-full rounded-full transition-all duration-500"
        :class="barColor"
        :style="{ width: `${Math.min(100, percentage)}%` }"
        role="progressbar"
        :aria-valuenow="value"
        :aria-valuemin="min"
        :aria-valuemax="max"
      ></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  title: string
  value: number
  unit?: string
  subtitle?: string
  min?: number
  max?: number
  thresholds?: { warn: number; danger: number }
}>(), {
  min: 0,
  max: 100,
  thresholds: () => ({ warn: 70, danger: 90 }),
})

const displayValue = computed(() => {
  if (props.value >= 1000) return `${(props.value / 1000).toFixed(1)}k`
  return props.value.toString()
})

const percentage = computed(() => {
  if (props.max === 0) return 0
  return (props.value / props.max) * 100
})

const valueColor = computed(() => {
  if (props.value >= props.thresholds.danger) return 'text-red-500'
  if (props.value >= props.thresholds.warn) return 'text-yellow-500'
  return 'text-green-500'
})

const barColor = computed(() => {
  if (props.value >= props.thresholds.danger) return 'bg-red-500'
  if (props.value >= props.thresholds.warn) return 'bg-yellow-500'
  return 'bg-green-500'
})
</script>
