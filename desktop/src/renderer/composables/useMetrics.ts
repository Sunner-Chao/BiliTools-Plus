import { ref, onMounted, onUnmounted } from 'vue'
import { useApi } from '@/composables/useApi'

export interface MetricsSummary {
  requests_per_min: number
  avg_latency_ms: number
  bili_429_count: number
  ws_connections: number
  available_tokens: number
  queue_size: number
  updated_at: string
}

export interface MetricsHistory {
  timeline: string[]
  rpm: number[]
  latency: number[]
  errors_429: number[]
}

export type Granularity = '1m' | '5m' | '15m'

export function useMetrics(granularity: Granularity = '5m', pollInterval = 30000) {
  const { get } = useApi()

  const summary = ref<MetricsSummary | null>(null)
  const history = ref<MetricsHistory | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  let pollTimer: ReturnType<typeof setInterval> | null = null

  async function fetchSummary() {
    const resp = await get<MetricsSummary>('/api/v1/metrics/summary')
    if (resp && resp.data) {
      summary.value = resp.data
    }
  }

  async function fetchHistory() {
    const resp = await get<MetricsHistory>(`/api/v1/metrics/history?granularity=${granularity}`)
    if (resp && resp.data) {
      history.value = resp.data
    }
  }

  async function refresh() {
    loading.value = true
    error.value = null
    try {
      await Promise.all([fetchSummary(), fetchHistory()])
    } catch (e) {
      error.value = e instanceof Error ? e.message : '数据加载失败'
    } finally {
      loading.value = false
    }
  }

  function startPolling() {
    stopPolling()
    refresh()
    pollTimer = setInterval(refresh, pollInterval)
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  onMounted(() => {
    startPolling()
  })

  onUnmounted(() => {
    stopPolling()
  })

  return {
    summary,
    history,
    loading,
    error,
    refresh,
    startPolling,
    stopPolling,
  }
}
