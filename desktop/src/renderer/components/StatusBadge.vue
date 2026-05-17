<script setup lang="ts">
defineProps<{ status: string; pulse?: boolean }>()

const colorMap: Record<string, string> = {
  success: 'var(--color-success)', warning: 'var(--color-warning)', error: 'var(--color-error)',
  info: 'var(--color-info)', idle: 'var(--color-text-disabled)', running: 'var(--color-primary)',
  connected: 'var(--color-success)', disconnected: 'var(--color-text-disabled)', connecting: 'var(--color-warning)',
}
const labelMap: Record<string, string> = {
  success: '成功', warning: '警告', error: '错误', info: '信息',
  idle: '空闲', running: '运行中', connected: '已连接', disconnected: '已断开', connecting: '连接中',
}
</script>
<template>
  <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium select-none backdrop-blur-sm"
    :style="{ backgroundColor: `${colorMap[status] ?? 'var(--color-text-disabled)'}15`, color: colorMap[status] ?? 'var(--color-text-disabled)', border: `1px solid ${colorMap[status] ?? 'var(--color-text-disabled)'}25` }">
    <span :class="['inline-block w-1.5 h-1.5 rounded-full', pulse && 'animate-pulse']"
      :style="{ backgroundColor: colorMap[status] ?? 'var(--color-text-disabled)' }" />
    <slot>{{ labelMap[status] ?? status }}</slot>
  </span>
</template>
