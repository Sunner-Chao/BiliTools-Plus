<script setup lang="ts">
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { useAppStore } from '@/stores/useAppStore'
import { useTaskStore } from '@/stores/useTaskStore'
import { useWebSocket } from '@/composables/useWebSocket'
import { useNtpSync } from '@/composables/useNtpSync'
import { useApi } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import LogPanel from '@/components/LogPanel.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import StockMonitorCard from '@/components/StockMonitorCard.vue'
import type { StockState } from '@/components/StockMonitorCard.vue'
import { Gamepad2, Radio, FileText, Clock, ScanEye } from 'lucide-vue-next'
import type { LogMessage, StockChangeEvent } from '@/composables/useWebSocket'

const app = useAppStore()
const taskStore = useTaskStore()
const { request } = useApi()
const toast = useToast()
const { offset: ntpOffset, start: startNtpSync } = useNtpSync()

const globalLogs = ref<LogMessage[]>([])
const isRunning = ref(false)

// ── P6: 商品库存监控状态 ──────────────────────────────
const stockStates = reactive<Map<string, StockState>>(new Map())
const autoTriggerMap = reactive<Map<string, boolean>>(new Map())

function handleStockChange(evt: StockChangeEvent) {
  const existing = stockStates.get(evt.product_id)
  stockStates.set(evt.product_id, {
    productId: evt.product_id,
    productName: evt.product_name,
    price: evt.price,
    newStock: evt.new_stock,
    lastUpdate: evt.timestamp * 1000,
    pollingInterval: existing?.pollingInterval ?? 30,
    secondsUntilSale: existing?.secondsUntilSale ?? 0,
  })

  // 自动抢码：库存 > 0 且用户已开启自动触发
  if (evt.new_stock > 0 && autoTriggerMap.get(evt.product_id)) {
    sendRequestSnipe(evt.product_id)
    toast.info(`[自动抢码] ${evt.product_name} 库存 ${evt.new_stock}，已发送抢购请求`)
  }
}

function handleToggleAutoTrigger(productId: string, enabled: boolean) {
  autoTriggerMap.set(productId, enabled)
  if (enabled) {
    toast.success(`已开启自动抢码：${stockStates.get(productId)?.productName ?? productId}`)
  }
}

function handleManualSnipe(productId: string) {
  sendRequestSnipe(productId)
  toast.info('抢购请求已发送')
}

// ── WebSocket 连接 ───────────────────────────────────
const wsUrl = computed(() => {
  const base = app.server.url.replace(/^https?:\/\//, '')
  return app.accessToken
    ? `ws://${base}/ws/progress?token=${encodeURIComponent(app.accessToken)}`
    : `ws://${base}/ws/progress`
})
const { status, send } = useWebSocket(
  wsUrl,
  {
  onLog: (msg) => {
    globalLogs.value.push(msg)
    if (msg.task_id) taskStore.appendLog(msg.task_id, msg)
  },
  onTaskProgress: (e) => {
    if (e.status === 'running') isRunning.value = true
  },
  onTaskComplete: () => {
    isRunning.value = false
  },
  onErrorAlert: (e) => {
    console.warn('[WS] error_alert:', e.msg)
  },
  onStockChange: handleStockChange,
  onStatusChange: (s) => { app.globalWsStatus = s as any },
})

/** 通过 WebSocket 发送抢购请求（绕过 HTTP 1 RTT） */
function sendRequestSnipe(productId: string) {
  send({ event: 'request_snipe', product_id: productId })
}

const daySummary = ref({ liveDays: 0, submitCount: 0 })

async function refreshDashboardSummary() {
  const res = await request<{ tasks: any[]; live_task_days: number; submit_task_count: number }>('/api/tasks?game=' + app.currentGame)
  if (res?.data) {
    taskStore.setTasks(res.data.tasks ?? [])
    daySummary.value = {
      liveDays: res.data.live_task_days ?? daySummary.value.liveDays,
      submitCount: res.data.submit_task_count ?? daySummary.value.submitCount,
    }
  }
  const overview = await request<{ live_days?: number; liveDays?: number; submit_count?: number; submitCount?: number }>(
    `/api/tasks/overview?game=${encodeURIComponent(app.currentGame)}`,
  )
  if (overview) {
    daySummary.value = {
      liveDays: overview.live_days ?? overview.liveDays ?? daySummary.value.liveDays,
      submitCount: overview.submit_count ?? overview.submitCount ?? daySummary.value.submitCount,
    }
  }
}

onMounted(async () => {
  startNtpSync()
  await refreshDashboardSummary()
})

watch(() => app.currentGame, () => {
  refreshDashboardSummary()
})
</script>

<template>
  <div class="main-bg min-h-full p-6 space-y-6">
    <!-- Premium page header -->
    <div class="flex items-center justify-between animate-fade-in">
      <div>
        <div class="flex items-center gap-3 mb-1">
          <div class="w-1 h-6 rounded-full bg-gradient-to-b from-[var(--color-primary)] to-transparent"></div>
          <h2 class="text-2xl font-bold text-[var(--color-text-primary)] tracking-tight">仪表盘</h2>
        </div>
        <p class="text-sm text-[var(--color-text-secondary)] ml-4">
          当前分区：<span class="text-[var(--color-primary)] font-semibold">{{ app.games.find(g => g.key === app.currentGame)?.label }}</span>
        </p>
      </div>
      <StatusBadge :status="status" :pulse="status === 'connecting'" />
    </div>

    <!-- Stats row -->
    <div class="grid grid-cols-4 gap-4">
      <div class="stat-card p-5 group overflow-hidden relative">
        <div class="absolute inset-0 bg-gradient-to-br from-[var(--color-primary)]/5 to-transparent" />
        <div class="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[var(--color-primary)]/40 to-transparent" />
        <div class="flex items-center justify-between mb-3 relative">
          <span class="text-xs text-[var(--color-text-secondary)] font-medium uppercase tracking-wider">游戏分区</span>
          <span class="w-9 h-9 rounded-xl bg-[var(--color-primary)]/10 flex items-center justify-center ring-1 ring-[var(--color-primary)]/15 group-hover:bg-[var(--color-primary)]/20 transition-colors">
            <Gamepad2 :size="16" class="text-[var(--color-primary)]" />
          </span>
        </div>
        <p class="text-xl font-bold text-[var(--color-text-primary)] relative">{{ app.games.find(g => g.key === app.currentGame)?.label }}</p>
      </div>
      <div class="stat-card p-5 group overflow-hidden relative">
        <div class="absolute inset-0 bg-gradient-to-br from-[var(--color-success)]/5 to-transparent" />
        <div class="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[var(--color-success)]/40 to-transparent" />
        <div class="flex items-center justify-between mb-3 relative">
          <span class="text-xs text-[var(--color-text-secondary)] font-medium uppercase tracking-wider">直播天数</span>
          <span class="w-9 h-9 rounded-xl bg-[var(--color-success)]/10 flex items-center justify-center ring-1 ring-[var(--color-success)]/15 group-hover:bg-[var(--color-success)]/20 transition-colors">
            <Radio :size="16" class="text-[var(--color-success)]" />
          </span>
        </div>
        <p class="text-xl font-bold text-[var(--color-success)] relative">{{ daySummary.liveDays }}</p>
      </div>
      <div class="stat-card p-5 group overflow-hidden relative">
        <div class="absolute inset-0 bg-gradient-to-br from-[var(--color-info)]/5 to-transparent" />
        <div class="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[var(--color-info)]/40 to-transparent" />
        <div class="flex items-center justify-between mb-3 relative">
          <span class="text-xs text-[var(--color-text-secondary)] font-medium uppercase tracking-wider">稿件总数</span>
          <span class="w-9 h-9 rounded-xl bg-[var(--color-info)]/10 flex items-center justify-center ring-1 ring-[var(--color-info)]/15 group-hover:bg-[var(--color-info)]/20 transition-colors">
            <FileText :size="16" class="text-[var(--color-info)]" />
          </span>
        </div>
        <p class="text-xl font-bold text-[var(--color-info)] relative">{{ daySummary.submitCount }}</p>
      </div>
      <div class="stat-card p-5 group overflow-hidden relative" :class="Math.abs(ntpOffset) >= 100 && '!border-[var(--color-warning)]/30'">
        <div class="absolute inset-0 bg-gradient-to-br from-[var(--color-accent)]/5 to-transparent" />
        <div class="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[var(--color-warning)]/40 to-transparent" />
        <div class="flex items-center justify-between mb-3 relative">
          <span class="text-xs text-[var(--color-text-secondary)] font-medium uppercase tracking-wider">NTP偏移</span>
          <span class="w-9 h-9 rounded-xl bg-[var(--color-accent)]/10 flex items-center justify-center ring-1 ring-[var(--color-accent)]/15 group-hover:bg-[var(--color-accent)]/20 transition-colors">
            <Clock :size="16" class="text-[var(--color-accent)]" />
          </span>
        </div>
        <p class="text-xl font-bold relative" :class="Math.abs(ntpOffset) < 100 ? 'text-[var(--color-success)]' : 'text-[var(--color-warning)]'">
          {{ ntpOffset ? `${ntpOffset > 0 ? '+' : ''}${ntpOffset}ms` : '--' }}
          <span v-if="Math.abs(ntpOffset) >= 100" class="text-xs font-normal ml-2 animate-pulse">⚠ 时钟偏移过大</span>
        </p>
      </div>
    </div>

    <!-- P6: 商品库存监控 -->
    <section v-if="stockStates.size > 0">
      <div class="flex items-center gap-2 mb-3">
        <ScanEye :size="16" class="text-[var(--color-primary)]" />
        <h3 class="text-sm font-semibold text-[var(--color-text-secondary)]">商品库存监控</h3>
        <span class="text-xs text-[var(--color-text-secondary)]/60 font-mono ml-auto">{{ stockStates.size }} 个商品</span>
      </div>
      <div class="grid gap-4" :class="stockStates.size > 1 ? 'grid-cols-2' : 'grid-cols-1'">
        <StockMonitorCard
          v-for="[id, state] in stockStates"
          :key="id"
          :state="state"
          :auto-trigger-enabled="autoTriggerMap.get(id) ?? false"
          @toggle-auto-trigger="(enabled: boolean) => handleToggleAutoTrigger(id, enabled)"
          @request-snipe="handleManualSnipe"
        />
      </div>
    </section>

    <!-- Global log -->
    <section>
      <h3 class="text-sm font-semibold mb-3 text-[var(--color-text-secondary)]">全局日志</h3>
      <LogPanel :logs="globalLogs" :max-items="200" class="h-64" />
    </section>
  </div>
</template>
