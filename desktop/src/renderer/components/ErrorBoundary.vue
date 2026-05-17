<script setup lang="ts">
import { ref, onErrorCaptured } from 'vue'
import { useToast } from '@/composables/useToast'
import { AlertTriangle, RotateCcw } from 'lucide-vue-next'

const toast = useToast()
const hasError = ref(false)
const errorMessage = ref('')

onErrorCaptured((err) => {
  hasError.value = true
  errorMessage.value = err instanceof Error ? err.message : String(err)
  toast.error(`组件异常: ${errorMessage.value}`)
  // 阻止错误继续向上冒泡
  return false
})

function retry() {
  hasError.value = false
  errorMessage.value = ''
}
</script>

<template>
  <div v-if="hasError" class="flex flex-col items-center justify-center min-h-[200px] gap-4 p-8">
    <div class="w-14 h-14 rounded-2xl bg-red-500/10 flex items-center justify-center">
      <AlertTriangle :size="28" class="text-red-400" />
    </div>
    <div class="text-center space-y-1">
      <p class="text-sm font-semibold text-[var(--color-text-primary)]">页面出了点问题</p>
      <p class="text-xs text-[var(--color-text-secondary)] max-w-xs">{{ errorMessage }}</p>
    </div>
    <button
      @click="retry"
      class="flex items-center gap-2 px-4 py-2 rounded-xl bg-[var(--color-primary)]/10 text-[var(--color-primary)] text-sm font-medium hover:bg-[var(--color-primary)]/20 transition-colors"
    >
      <RotateCcw :size="14" />
      重试
    </button>
  </div>
  <slot v-else />
</template>
