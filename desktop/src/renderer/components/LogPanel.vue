<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import type { LogMessage } from '@/composables/useWebSocket'

const props = defineProps<{ logs: LogMessage[]; maxItems?: number }>()
const searchText = ref('')
const filterLevel = ref('all')
const containerRef = ref<HTMLElement | null>(null)
const autoScroll = ref(true)

const filtered = computed(() => {
  let list = props.logs
  if (filterLevel.value !== 'all') list = list.filter(l => l.level === filterLevel.value)
  if (searchText.value) list = list.filter(l => l.message.toLowerCase().includes(searchText.value.toLowerCase()))
  return list.slice(-(props.maxItems ?? 500))
})

watch(() => props.logs.length, () => {
  if (autoScroll.value) nextTick(() => { if (containerRef.value) containerRef.value.scrollTop = containerRef.value.scrollHeight })
})

const levelColor: Record<string, string> = {
  success: 'var(--color-success)', warning: 'var(--color-warning)', error: 'var(--color-error)', info: 'var(--color-info)',
}
const levelIcon: Record<string, string> = {
  success: '✓', warning: '⚠', error: '✕', info: '●',
}
const levels = ['all', 'info', 'success', 'warning', 'error']

function exportLogs() {
  const text = props.logs.map(l => `[${l.timestamp ?? ''}] [${l.level.toUpperCase()}] ${l.message}`).join('\n')
  const blob = new Blob([text], { type: 'text/plain' })
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob)
  a.download = `bili-logs-${new Date().toISOString().slice(0,10)}.txt`; a.click()
}
</script>

<template>
  <div class="flex flex-col h-full glass-card overflow-hidden">
    <div class="flex items-center gap-3 px-4 py-2.5 border-b border-white/5 bg-white/[0.02]">
      <input v-model="searchText" placeholder="搜索日志..." class="input-field flex-1 !py-1.5 !text-xs" />
      <select v-model="filterLevel" class="input-field !py-1.5 !text-xs !px-2">
        <option v-for="lv in levels" :key="lv" :value="lv">{{ lv === 'all' ? '全部级别' : lv.toUpperCase() }}</option>
      </select>
      <label class="flex items-center gap-1.5 text-xs text-[var(--color-text-secondary)] cursor-pointer select-none">
        <input v-model="autoScroll" type="checkbox" class="accent-[var(--color-primary)] w-3.5 h-3.5" /> 自动滚动
      </label>
      <button @click="exportLogs" class="btn-ghost !text-xs !py-1 !px-2">导出</button>
      <span class="text-[10px] text-[var(--color-text-disabled)] tabular-nums">{{ filtered.length }} 条</span>
    </div>
    <div ref="containerRef" class="flex-1 overflow-auto px-4 py-3 font-mono text-[12.5px] leading-[1.8]">
      <div v-if="filtered.length === 0" class="text-[var(--color-text-disabled)] text-center mt-12 text-sm">
        <p class="text-2xl mb-2">📭</p>暂无日志
      </div>
      <div v-for="(log, idx) in filtered" :key="idx"
        class="flex items-start gap-2 py-0.5 hover:bg-white/[0.02] rounded px-1 -mx-1 transition-colors">
        <span class="text-[var(--color-text-disabled)] shrink-0 tabular-nums">{{ log.timestamp?.slice(11, 19) ?? '--:--:--' }}</span>
        <span class="shrink-0 w-4 text-center" :style="{ color: levelColor[log.level] ?? 'var(--color-text-secondary)' }">{{ levelIcon[log.level] ?? '●' }}</span>
        <span :style="{ color: levelColor[log.level] ?? 'var(--color-text-secondary)' }" class="break-all">{{ log.message }}</span>
      </div>
    </div>
  </div>
</template>
