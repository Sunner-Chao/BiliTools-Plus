<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useSoundNotification } from '@/composables/useSoundNotification'
import { useToast } from '@/composables/useToast'
import { Eye, EyeOff, Zap, Clock, PackageCheck, PackageX, AlertTriangle } from 'lucide-vue-next'

export interface StockState {
  productId: string
  productName: string
  price: number
  newStock: number
  lastUpdate: number
  pollingInterval: number       // 当前轮询间隔（秒）
  secondsUntilSale: number      // 距开售秒数
}

const props = defineProps<{
  state: StockState
  autoTriggerEnabled?: boolean
}>()

const emit = defineEmits<{
  toggleAutoTrigger: [enabled: boolean]
  requestSnipe: [productId: string]
}>()

const toast = useToast()
const { unlocked, unlock, playStockAlert } = useSoundNotification()
const showConfirmDialog = ref(false)
const autoTrigger = ref(props.autoTriggerEnabled ?? false)

/** 四态状态机 */
const monitorState = computed(() => {
  const s = props.state
  if (s.newStock > 0 && s.secondsUntilSale <= 0) return 'in_stock'
  if (s.newStock === 0 && s.secondsUntilSale <= 0) return 'out_of_stock'
  if (s.secondsUntilSale > 0 && s.secondsUntilSale <= 300) return 'approaching'
  return 'waiting'
})

const stateConfig = computed(() => {
  switch (monitorState.value) {
    case 'waiting':
      return { label: '等待开售', color: 'text-[var(--color-text-secondary)]', bg: 'bg-gray-500/10', icon: Clock, ringColor: 'ring-gray-500/20' }
    case 'approaching':
      return { label: '即将开售', color: 'text-[var(--color-warning)]', bg: 'bg-[var(--color-warning)]/10', icon: AlertTriangle, ringColor: 'ring-[var(--color-warning)]/20' }
    case 'in_stock':
      return { label: '可购买', color: 'text-[var(--color-success)]', bg: 'bg-[var(--color-success)]/10', icon: PackageCheck, ringColor: 'ring-[var(--color-success)]/30' }
    case 'out_of_stock':
      return { label: '已售罄', color: 'text-[var(--color-error)]', bg: 'bg-[var(--color-error)]/10', icon: PackageX, ringColor: 'ring-[var(--color-error)]/20' }
    default:
      return { label: '未知', color: 'text-[var(--color-text-secondary)]', bg: 'bg-gray-500/10', icon: Clock, ringColor: 'ring-gray-500/20' }
  }
})

const intervalLabel = computed(() => {
  const sec = props.state.pollingInterval
  if (sec <= 2) return '每 2s 检查'
  if (sec <= 10) return '每 10s 检查'
  return '每 30s 检查'
})

const countdownText = computed(() => {
  const sec = props.state.secondsUntilSale
  if (sec <= 0) return '已开售'
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}分${s.toString().padStart(2, '0')}秒`
})

function handleToggleAutoTrigger() {
  if (!unlocked.value) unlock()
  if (!autoTrigger.value) {
    showConfirmDialog.value = true
  } else {
    autoTrigger.value = false
    emit('toggleAutoTrigger', false)
  }
}

function confirmAutoTrigger() {
  autoTrigger.value = true
  showConfirmDialog.value = false
  emit('toggleAutoTrigger', true)
  toast.success('自动抢码已开启')
}

function cancelAutoTrigger() {
  showConfirmDialog.value = false
}

function handleManualSnipe() {
  emit('requestSnipe', props.state.productId)
}

onMounted(() => {
  document.addEventListener('click', unlock, { once: true })
})

// 监听库存突变播放提示音
import { watch } from 'vue'
watch(() => props.state.newStock, (newVal, oldVal) => {
  if (newVal > 0 && (oldVal === 0 || oldVal === undefined)) {
    playStockAlert()
  }
})
</script>

<template>
  <div class="stat-card p-5 group overflow-hidden relative" role="region" aria-label="商品监控">
    <!-- 顶部状态条 -->
    <div class="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-current to-transparent" :class="stateConfig.color" />

    <div class="flex items-center justify-between mb-4">
      <div class="flex items-center gap-2">
        <span class="w-8 h-8 rounded-lg flex items-center justify-center ring-1" :class="[stateConfig.bg, stateConfig.ringColor]">
          <component :is="stateConfig.icon" :size="16" :class="stateConfig.color" />
        </span>
        <span class="text-sm font-semibold" :class="stateConfig.color">{{ stateConfig.label }}</span>
        <span v-if="monitorState === 'approaching'" class="w-2 h-2 rounded-full bg-[var(--color-warning)] animate-pulse" />
      </div>
      <span class="text-xs text-[var(--color-text-secondary)] font-mono">{{ intervalLabel }}</span>
    </div>

    <!-- 商品信息 -->
    <div class="mb-4">
      <h4 class="text-base font-bold text-[var(--color-text-primary)] truncate">{{ state.productName || '未指定商品' }}</h4>
      <p class="text-sm text-[var(--color-text-secondary)] mt-1">
        <span v-if="state.price > 0">¥{{ state.price }}</span>
        <span v-if="state.price > 0 && state.secondsUntilSale > 0" class="mx-2">·</span>
        <span v-if="state.secondsUntilSale > 0" class="font-mono" :class="monitorState === 'approaching' ? 'text-[var(--color-warning)]' : ''">
          {{ countdownText }}
        </span>
      </p>
    </div>

    <!-- 库存状态 -->
    <div class="flex items-center gap-3 mb-4 p-3 rounded-lg" :class="stateConfig.bg">
      <div class="flex-1">
        <span class="text-xs text-[var(--color-text-secondary)] block">当前库存</span>
        <span class="text-lg font-bold" :class="stateConfig.color">
          {{ state.newStock > 0 ? state.newStock : (state.secondsUntilSale > 0 ? '—' : '0') }}
        </span>
      </div>
      <button
        v-if="monitorState === 'in_stock'"
        @click="handleManualSnipe"
        class="px-4 py-2 rounded-lg text-sm font-semibold bg-[var(--color-success)] text-white hover:brightness-110 transition-all active:scale-95"
        aria-label="立即抢购"
      >
        <Zap :size="14" class="inline mr-1" />立即抢购
      </button>
    </div>

    <!-- 自动触发开关 -->
    <div class="flex items-center justify-between p-3 rounded-lg bg-[var(--color-bg-secondary)]/50">
      <div class="flex items-center gap-2">
        <component :is="autoTrigger ? Eye : EyeOff" :size="14" class="text-[var(--color-text-secondary)]" />
        <span class="text-sm text-[var(--color-text-secondary)]">自动抢码</span>
      </div>
      <button
        @click="handleToggleAutoTrigger"
        :class="['relative w-11 h-6 rounded-full transition-colors', autoTrigger ? 'bg-[var(--color-success)]' : 'bg-[var(--color-text-secondary)]/30']"
        :aria-pressed="autoTrigger"
        aria-label="切换自动抢码"
        role="switch"
      >
        <span :class="['absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform', autoTrigger ? 'translate-x-5' : '']" />
      </button>
    </div>

    <!-- 确认弹窗 -->
    <Teleport to="body">
      <div v-if="showConfirmDialog" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" @click.self="cancelAutoTrigger" role="dialog" aria-label="确认开启自动抢码" aria-modal="true">
        <div class="glass-card p-6 max-w-sm w-full mx-4 rounded-2xl">
          <h3 class="text-lg font-bold text-[var(--color-text-primary)] mb-2">确认开启自动抢码？</h3>
          <p class="text-sm text-[var(--color-text-secondary)] mb-6">库存出现时将立即执行抢购，请确认商品信息无误。</p>
          <div class="flex gap-3 justify-end">
            <button @click="cancelAutoTrigger" class="px-4 py-2 rounded-lg text-sm text-[var(--color-text-secondary)] hover:bg-white/5 transition-colors">取消</button>
            <button @click="confirmAutoTrigger" class="px-4 py-2 rounded-lg text-sm font-semibold bg-[var(--color-primary)] text-white hover:brightness-110 transition-all">确认开启</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
