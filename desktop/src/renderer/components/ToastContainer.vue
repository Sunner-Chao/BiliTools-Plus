<script setup lang="ts">
import { useToast } from '@/composables/useToast'
import { CheckCircle2, XCircle, AlertTriangle, Info } from 'lucide-vue-next'
const { toasts, remove } = useToast()
const config: Record<string, { icon: any; bg: string; border: string }> = {
  success: { icon: CheckCircle2, bg: 'from-green-500/90 to-emerald-600/80', border: 'border-green-400/50' },
  error:   { icon: XCircle,        bg: 'from-red-500/90 to-rose-600/80',   border: 'border-red-400/50' },
  warning: { icon: AlertTriangle, bg: 'from-yellow-500/90 to-amber-600/80', border: 'border-yellow-400/50' },
  info:    { icon: Info,          bg: 'from-blue-500/90 to-indigo-600/80',   border: 'border-blue-400/50' },
}
</script>
<template>
  <Teleport to="body">
    <div class="fixed top-5 right-5 z-[9999] flex flex-col gap-3 pointer-events-none">
      <TransitionGroup name="toast">
        <div v-for="t in toasts" :key="t.id"
          :class="['pointer-events-auto relative flex items-center gap-3 pl-4 pr-3 py-3 rounded-xl shadow-2xl backdrop-blur-md border text-sm max-w-xs bg-gradient-to-r ' + config[t.type]?.bg, config[t.type]?.border]"
          style="box-shadow: 0 8px 32px rgba(0,0,0,0.4)">
          <component :is="config[t.type]?.icon" :size="16" class="shrink-0 text-white/90" />
          <span class="flex-1 text-white/90 font-medium">{{ t.message }}</span>
          <button @click="remove(t.id)" class="shrink-0 w-5 h-5 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center transition-colors">
            <span class="text-white/70 text-xs leading-none">×</span>
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>
<style scoped>
.toast-enter-active { transition: all 0.35s cubic-bezier(0.34, 1.56, 0.64, 1); }
.toast-leave-active { transition: all 0.25s ease-in; }
.toast-enter-from { opacity: 0; transform: translateX(80px) scale(0.8); }
.toast-leave-to   { opacity: 0; transform: translateX(80px) scale(0.8); }
</style>
