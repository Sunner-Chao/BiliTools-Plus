<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">监控面板</h1>
      <div class="flex items-center gap-3">
        <span v-if="summary?.updated_at" class="text-xs text-gray-400 dark:text-gray-500">
          更新于 {{ updatedAt }}
        </span>
        <button
          @click="refresh"
          :disabled="loading"
          class="px-3 py-1.5 text-sm rounded-lg bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-50 transition-colors"
          aria-label="刷新数据"
        >
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>
    </div>

    <div v-if="error" class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3 text-sm text-red-600 dark:text-red-400" role="alert">
      {{ error }}
    </div>

    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      <MetricsGauge
        title="请求数/分"
        :value="summary?.requests_per_min ?? 0"
        unit="req/min"
        :max="100"
        :thresholds="{ warn: 60, danger: 80 }"
      />
      <MetricsGauge
        title="平均延迟"
        :value="summary?.avg_latency_ms ?? 0"
        unit="ms"
        :max="500"
        :thresholds="{ warn: 200, danger: 400 }"
      />
      <MetricsGauge
        title="B站限流"
        :value="summary?.bili_429_count ?? 0"
        unit="次"
        :max="50"
        :thresholds="{ warn: 10, danger: 30 }"
      />
      <MetricsGauge
        title="WS 连接"
        :value="summary?.ws_connections ?? 0"
        unit="个"
        :max="50"
        :thresholds="{ warn: 30, danger: 45 }"
      />
      <MetricsGauge
        title="可用 Token"
        :value="summary?.available_tokens ?? 0"
        unit="个"
        :max="10"
        :thresholds="{ warn: 3, danger: 1 }"
      />
      <MetricsGauge
        title="队列积压"
        :value="summary?.queue_size ?? 0"
        unit="个"
        :max="100"
        :thresholds="{ warn: 50, danger: 80 }"
      />
    </div>

    <MetricsChart
      title="请求量 & 延迟趋势"
      :data="history"
      :series="requestSeries"
    />

    <MetricsChart
      title="B站限流趋势"
      :data="history"
      :series="errorSeries"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useMetrics } from '@/composables/useMetrics'
import MetricsChart from '@/components/MetricsChart.vue'
import MetricsGauge from '@/components/MetricsGauge.vue'

const { summary, history, loading, error, refresh } = useMetrics('5m', 30000)

const updatedAt = computed(() => {
  if (!summary.value?.updated_at) return ''
  try {
    return new Date(summary.value.updated_at).toLocaleTimeString()
  } catch {
    return summary.value.updated_at
  }
})

const requestSeries = [
  { name: '请求数/分', key: 'rpm' as const, color: '#3b82f6' },
  { name: '延迟(ms)', key: 'latency' as const, color: '#10b981' },
]

const errorSeries = [
  { name: '429次数', key: 'errors_429' as const, color: '#f59e0b' },
]
</script>
