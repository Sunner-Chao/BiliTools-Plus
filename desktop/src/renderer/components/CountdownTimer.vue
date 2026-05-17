<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
const props = defineProps<{ targetTime: number; ntpOffset?: number }>()
const emit = defineEmits<{ expired: [] }>()
const now = ref(Date.now())
let rafId = 0

const display = computed(() => {
  const adjusted = now.value + (props.ntpOffset ?? 0)
  const diff = Math.max(0, props.targetTime - adjusted)
  if (diff === 0) return { h: '00', m: '00', s: '00', ms: '000', expired: true }
  const h = Math.floor(diff / 3_600_000)
  const m = Math.floor((diff % 3_600_000) / 60_000)
  const s = Math.floor((diff % 60_000) / 1000)
  return { h: String(h).padStart(2,'0'), m: String(m).padStart(2,'0'), s: String(s).padStart(2,'0'), ms: String(diff % 1000).padStart(3,'0'), expired: false }
})

function tick() {
  now.value = Date.now()
  if (display.value.expired) { emit('expired'); return }
  rafId = requestAnimationFrame(tick)
}
onMounted(() => { rafId = requestAnimationFrame(tick) })
onUnmounted(() => cancelAnimationFrame(rafId))
</script>

<template>
  <div class="inline-flex items-baseline gap-1 font-mono tabular-nums select-none">
    <template v-if="display.expired">
      <span class="text-[var(--color-error)] text-lg font-bold">已过期</span>
    </template>
    <template v-else>
      <span class="text-2xl font-bold text-[var(--color-primary)]">{{ display.h }}</span>
      <span class="text-[var(--color-text-secondary)] text-lg">:</span>
      <span class="text-2xl font-bold text-[var(--color-primary)]">{{ display.m }}</span>
      <span class="text-[var(--color-text-secondary)] text-lg">:</span>
      <span class="text-2xl font-bold text-[var(--color-primary)]">{{ display.s }}</span>
      <span class="text-sm text-[var(--color-text-secondary)]">.{{ display.ms }}</span>
    </template>
  </div>
</template>
