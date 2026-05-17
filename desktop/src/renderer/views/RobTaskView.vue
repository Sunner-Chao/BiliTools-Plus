<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useAppStore } from '@/stores/useAppStore'
import { useTaskStore } from '@/stores/useTaskStore'
import StatusBadge from '@/components/StatusBadge.vue'
import { Crosshair, Clock, Play, Pause, Zap, AlertCircle, CheckSquare, Square, Timer, RefreshCw, ChevronDown, ChevronUp } from 'lucide-vue-next'
import { useApi } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'

const app = useAppStore()
const taskStore = useTaskStore()
const api = useApi()
const toast = useToast()

// ── Activity countdown ──
const countdownTarget = ref<string>('')
const countdownActive = ref(false)
let timerInterval: ReturnType<typeof setInterval> | null = null
let statusInterval: ReturnType<typeof setInterval> | null = null

const countdownDisplay = ref({ days: 0, hours: 0, minutes: 0, seconds: 0 })

const updateCountdown = () => {
  if (!countdownActive.value || !countdownTarget.value) {
    countdownDisplay.value = { days: 0, hours: 0, minutes: 0, seconds: 0 }
    return
  }
  const now = Date.now()
  const target = new Date(countdownTarget.value).getTime()
  const diff = Math.max(0, target - now)
  countdownDisplay.value = {
    days: Math.floor(diff / 86400000),
    hours: Math.floor((diff % 86400000) / 3600000),
    minutes: Math.floor((diff % 3600000) / 60000),
    seconds: Math.floor((diff % 60000) / 1000),
  }
  if (diff === 0) {
    countdownActive.value = false
    toast.warning('抢购时间已到！')
  }
}

const startCountdown = () => {
  if (!countdownTarget.value) { toast.warning('请先设置抢购时间'); return }
  countdownActive.value = true
  // Auto-fill robPeriod with countdown target
  robPeriod.value = countdownTarget.value.replace('T', ' ').replace(/Z$|[+-]\d{2}:\d{2}$/, '')
  toast.success('倒计时已启动')
}

const setQuickTime = (offsetMs: number) => {
  countdownTarget.value = new Date(Date.now() + offsetMs).toISOString().slice(0, 19)
  countdownActive.value = true
  toast.success(`已设置 ${offsetMs < 60000 ? offsetMs / 1000 + '秒' : offsetMs / 60000 + '分钟'} 后开始`)
}

// ── Task config ──
const isRunning = ref(false)
const robPeriod = ref('')
const robHoldtime = ref(30)
const robInterval = ref(0.3)
const robMode = ref('auto')
const activeTaskId = ref('')
const overview = ref<any>({})
const overviewLoading = ref(false)
const sourceUrl = ref('https://www.bilibili.com/blackboard/era/n2drQa9NUK5Xruku.html?spm_id_from=333.337.0.0')
const refreshConfigLoading = ref(false)

// ── Snipe engine tasks ──
const snipeTasks = ref<any[]>([])

// Per-item execution status (mapped from snipe engine results)
const itemResults = ref<Record<string, { status: string; message: string; cdkey?: string }>>({})

const stats = computed(() => {
  const tasks = snipeTasks.value
  const results = Object.values(itemResults.value)
  return {
    total: taskStore.tasks.length,
    success: results.filter(r => r.status === 'success').length,
    fail: results.filter(r => r.status === 'failed').length,
    pending: taskStore.tasks.length - results.length,
    running: tasks.filter(t => t.status === 'running').length,
  }
})

const loadTasks = async () => {
  const res = await api.get<any>(`/api/tasks?game=${app.currentGame}`)
  const payload = res || {}
  if (payload) {
    taskStore.setTasks(payload.tasks || [])
  }
}

const loadOverview = async () => {
  overviewLoading.value = true
  try {
    const params = new URLSearchParams({ game: app.currentGame, source_url: sourceUrl.value })
    const res = await api.get<any>(`/api/tasks/overview?${params.toString()}`)
    overview.value = res || {}
    // Auto-fill countdown from activity end_time
    if (overview.value?.activity?.end_time) {
      countdownTarget.value = overview.value.activity.end_time.slice(0, 19)
      countdownActive.value = true
    }
  } catch { /* ignore */ }
  overviewLoading.value = false
}

const refreshConfigFromUrl = async () => {
  if (!sourceUrl.value.trim()) {
    toast.warning('请先填写活动网页 URL')
    return
  }
  refreshConfigLoading.value = true
  try {
    const res = await api.post<any>('/api/tasks/refresh', {
      game: app.currentGame,
      url: sourceUrl.value.trim(),
    })
    if (res?.success) {
      toast.success(`已从网页抓取 ${res.task_count ?? 0} 个资源任务`)
      await loadTasks()
      await loadOverview()
      taskStore.clearSelection()
    } else {
      toast.error(res?.error || res?.msg || '网页抓取失败')
    }
  } finally {
    refreshConfigLoading.value = false
  }
}

const formatSeconds = (seconds: number) => {
  const value = Math.max(0, Math.floor(seconds || 0))
  const h = String(Math.floor(value / 3600)).padStart(2, '0')
  const m = String(Math.floor((value % 3600) / 60)).padStart(2, '0')
  const s = String(value % 60).padStart(2, '0')
  return `${h}:${m}:${s}`
}

const startRob = async () => {
  const selected = [...taskStore.selectedTaskIds]
  if (selected.length === 0) {
    toast.warning('请先选择至少一个资源道具')
    return
  }
  // Clear previous results
  itemResults.value = {}
  logs.value = []

  const res = await api.post<any>('/api/tasks/execute', {
    game: app.currentGame,
    tasks: selected,
    period: robInterval.value,
    holdtime: robHoldtime.value,
    target_time: robPeriod.value ? new Date(robPeriod.value).toISOString() : '',
    cookies: app.cookies,
  })
  if (res?.task_id) {
    activeTaskId.value = res.task_id
    isRunning.value = true
    appendLog('info', `抢码任务已提交: ${res.task_id}`)
    if (res.item_count) appendLog('info', `共 ${res.item_count} 个资源道具待抢兑`)
    if (robPeriod.value) {
      const targetTime = new Date(robPeriod.value)
      const now = new Date()
      const diff = Math.max(0, Math.floor((targetTime.getTime() - now.getTime()) / 1000))
      if (diff > 0) {
        appendLog('info', `距抢购时间还有 ${formatSeconds(diff)}`)
      }
    }
  } else if (res?.msg) {
    toast.error(res.msg)
  }
}

const stopRob = async () => {
  if (activeTaskId.value) {
    await api.post(`/api/tasks/${activeTaskId.value}/cancel`)
  }
  isRunning.value = false
  activeTaskId.value = ''
  toast.warning('抢码任务已停止')
}

// ── Logs ──
const logs = ref<Array<{ time: string; level: 'info'|'success'|'error'|'warn'; msg: string }>>([])
const appendLog = (level: typeof logs.value[0]['level'], msg: string) => {
  const now = new Date()
  const time = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`
  logs.value.unshift({ time, level, msg })
  if (logs.value.length > 200) logs.value.pop()
}

// ── Task status panel collapse ──
const showTaskPanel = ref(true)

// ── Poll snipe engine status ──
const pollTaskStatus = async () => {
  try {
    const res = await api.get<any>('/api/tasks/status')
    const payload = res || {}
    const tasks = payload.tasks || []
    snipeTasks.value = tasks

    // Find active task and update logs
    const current = tasks.find((t: any) => t.id === activeTaskId.value)
    if (current) {
      isRunning.value = current.status === 'running' || current.status === 'waiting'

      // Map results back to individual items
      if (current.results?.length) {
        for (const r of current.results) {
          const key = r.task_id || r.name
          if (key) {
            itemResults.value[key] = {
              status: r.status,
              message: r.message || '',
              cdkey: r.cdkey || '',
            }
          }
        }
      }

      if (current.logs?.length) {
        const newLogs = current.logs.map((log: any) => ({
          time: log.time,
          level: log.level === 'warning' ? 'warn' : log.level,
          msg: log.msg,
        }))
        // Only update if there are new logs
        if (newLogs.length !== logs.value.length || (newLogs[0]?.msg !== logs.value[0]?.msg)) {
          logs.value = newLogs
        }
      }
      // Auto-update running state
      if (current.status === 'success' || current.status === 'failed' || current.status === 'cancelled') {
        isRunning.value = false
        const successCount = current.results?.filter((r: any) => r.status === 'success').length || 0
        const totalCount = current.results?.length || 0
        if (current.status === 'success') {
          appendLog('success', `任务完成！${successCount}/${totalCount} 个资源抢兑成功`)
        } else if (current.status === 'failed') {
          appendLog('error', `任务结束: ${successCount}/${totalCount} 成功`)
        }
      }
    }
  } catch { /* ignore polling errors */ }
}

onMounted(() => {
  loadTasks()
  loadOverview()
  timerInterval = setInterval(updateCountdown, 1000)
  statusInterval = setInterval(pollTaskStatus, 2000)
})

onUnmounted(() => {
  if (timerInterval) clearInterval(timerInterval)
  if (statusInterval) clearInterval(statusInterval)
})

const logColorMap: Record<string, string> = {
  info: 'text-[var(--color-text-secondary)]',
  success: 'text-[var(--color-success)]',
  error: 'text-[var(--color-error)]',
  warn: 'text-[var(--color-warning)]',
}

const taskStatusMap: Record<string, string> = {
  pending: 'idle', waiting: 'idle', success: 'success', failed: 'error', fail: 'error', running: 'running', cancelled: 'idle',
}

const taskStatusColor: Record<string, string> = {
  pending: 'text-[var(--color-text-disabled)]',
  waiting: 'text-[var(--color-warning)]',
  running: 'text-[var(--color-primary)]',
  success: 'text-[var(--color-success)]',
  failed: 'text-[var(--color-error)]',
  cancelled: 'text-[var(--color-text-disabled)]',
}

const taskStatusLabel: Record<string, string> = {
  pending: '待执行',
  waiting: '等待中',
  running: '执行中',
  success: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

const refreshAll = () => {
  loadTasks()
  loadOverview()
  pollTaskStatus()
  toast.info('数据已刷新')
}
</script>

<template>
  <div class="p-6 space-y-6 main-bg min-h-full">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <div class="h-1 w-12 bg-gradient-to-r from-[var(--color-primary)] to-[var(--color-primary-hover)] rounded-full mb-3" />
        <h1 class="text-2xl font-bold text-[var(--color-text-primary)]">抢码任务</h1>
        <p class="text-sm text-[var(--color-text-secondary)] mt-0.5">精准定时 · 多线程并发 · 自动重试</p>
      </div>
      <div class="flex items-center gap-3">
        <StatusBadge :status="isRunning ? 'running' : 'idle'" :pulse="isRunning">
          {{ isRunning ? '运行中' : '空闲' }}
        </StatusBadge>
        <button @click="refreshAll" class="btn-ghost p-2" title="刷新全部数据">
          <RefreshCw :size="14" class="text-[var(--color-text-secondary)]" />
        </button>
      </div>
    </div>

    <!-- Countdown Timer Card -->
    <div class="glass-card p-6">
      <div class="flex items-center gap-2 mb-5">
        <Timer :size="16" class="text-[var(--color-primary)]" />
        <span class="text-sm font-medium text-[var(--color-text-secondary)]">抢购倒计时</span>
        <span v-if="countdownActive" class="text-[10px] px-2 py-0.5 rounded-full bg-[var(--color-primary)]/10 text-[var(--color-primary)]">运行中</span>
      </div>

      <div class="flex flex-col lg:flex-row items-center gap-6">
        <!-- Countdown Display -->
        <div class="flex-1 w-full">
          <div v-if="countdownActive" class="grid grid-cols-4 gap-3">
            <div v-for="(val, label) in { 天: countdownDisplay.days, 时: countdownDisplay.hours, 分: countdownDisplay.minutes, 秒: countdownDisplay.seconds }" :key="label"
              class="bg-[var(--color-bg-base)] rounded-2xl p-4 text-center border border-white/5">
              <div class="text-3xl font-bold text-[var(--color-text-primary)] tabular-nums">
                {{ String(val).padStart(2, '0') }}
              </div>
              <div class="text-[10px] text-[var(--color-text-disabled)] mt-1 uppercase tracking-wider">{{ label }}</div>
            </div>
          </div>
          <div v-else class="text-center py-8">
            <div class="text-4xl font-bold text-[var(--color-text-disabled)] tabular-nums">--:--:--</div>
            <p class="text-sm text-[var(--color-text-disabled)] mt-2">设置倒计时时间或等待活动信息自动加载</p>
          </div>
        </div>

        <!-- Controls -->
        <div class="flex flex-col gap-3 w-full lg:w-auto">
          <input v-model="countdownTarget" type="datetime-local" class="input-field w-full lg:w-64 text-xs" />
          <div class="flex gap-2 flex-wrap">
            <button @click="startCountdown" class="btn-primary flex items-center gap-1.5 text-sm">
              <Play :size="14" /> 启动
            </button>
            <button @click="countdownActive = false" class="btn-ghost flex items-center gap-1.5 text-sm">
              <Pause :size="14" /> 暂停
            </button>
            <button @click="setQuickTime(30000)" class="btn-ghost text-xs px-3 py-2">30秒</button>
            <button @click="setQuickTime(60000)" class="btn-ghost text-xs px-3 py-2">1分钟</button>
            <button @click="setQuickTime(300000)" class="btn-ghost text-xs px-3 py-2">5分钟</button>
            <button @click="setQuickTime(600000)" class="btn-ghost text-xs px-3 py-2">10分钟</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Stats Row -->
    <div class="grid grid-cols-2 lg:grid-cols-5 gap-4">
      <div class="stat-card p-4">
        <div class="flex items-center justify-between mb-3">
          <span class="text-[10px] text-[var(--color-text-disabled)] uppercase tracking-wider">任务总数</span>
          <div class="w-7 h-7 rounded-lg bg-[var(--color-primary)]/10 flex items-center justify-center">
            <Crosshair :size="14" class="text-[var(--color-primary)]" />
          </div>
        </div>
        <div class="text-2xl font-bold text-[var(--color-text-primary)]">{{ stats.total }}</div>
      </div>
      <div class="stat-card p-4">
        <div class="flex items-center justify-between mb-3">
          <span class="text-[10px] text-[var(--color-text-disabled)] uppercase tracking-wider">成功</span>
          <div class="w-7 h-7 rounded-lg bg-[var(--color-success)]/10 flex items-center justify-center">
            <Zap :size="14" class="text-[var(--color-success)]" />
          </div>
        </div>
        <div class="text-2xl font-bold text-[var(--color-success)]">{{ stats.success }}</div>
      </div>
      <div class="stat-card p-4">
        <div class="flex items-center justify-between mb-3">
          <span class="text-[10px] text-[var(--color-text-disabled)] uppercase tracking-wider">执行中</span>
          <div class="w-7 h-7 rounded-lg bg-[var(--color-primary)]/10 flex items-center justify-center">
            <Play :size="14" class="text-[var(--color-primary)]" />
          </div>
        </div>
        <div class="text-2xl font-bold text-[var(--color-primary)]">{{ stats.running }}</div>
      </div>
      <div class="stat-card p-4">
        <div class="flex items-center justify-between mb-3">
          <span class="text-[10px] text-[var(--color-text-disabled)] uppercase tracking-wider">失败</span>
          <div class="w-7 h-7 rounded-lg bg-[var(--color-error)]/10 flex items-center justify-center">
            <AlertCircle :size="14" class="text-[var(--color-error)]" />
          </div>
        </div>
        <div class="text-2xl font-bold text-[var(--color-error)]">{{ stats.fail }}</div>
      </div>
      <div class="stat-card p-4">
        <div class="flex items-center justify-between mb-3">
          <span class="text-[10px] text-[var(--color-text-disabled)] uppercase tracking-wider">待执行</span>
          <div class="w-7 h-7 rounded-lg bg-[var(--color-warning)]/10 flex items-center justify-center">
            <Clock :size="14" class="text-[var(--color-warning)]" />
          </div>
        </div>
        <div class="text-2xl font-bold text-[var(--color-warning)]">{{ stats.pending }}</div>
      </div>
    </div>

    <!-- Activity Overview -->
    <div class="glass-card p-5">
      <div class="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        <div class="flex-1">
          <div class="flex items-center gap-2 mb-1">
            <h3 class="text-sm font-semibold text-[var(--color-text-primary)]">本期活动</h3>
            <button @click="loadOverview" :disabled="overviewLoading" class="p-1 rounded hover:bg-white/5">
              <RefreshCw :size="12" :class="['text-[var(--color-text-disabled)]', overviewLoading && 'animate-spin']" />
            </button>
          </div>
          <p class="text-xs text-[var(--color-text-secondary)] mt-1">{{ overview.activity?.title || '加载中...' }}</p>
          <div class="flex flex-wrap gap-3 mt-2 text-[11px] text-[var(--color-text-disabled)]">
            <span v-if="overview.area_name">分区: {{ overview.area_name }}</span>
            <span v-if="overview.live_days != null">直播天数: {{ overview.live_days }}</span>
            <span v-if="overview.submit_count != null">投稿数: {{ overview.submit_count }}</span>
            <span v-if="overview.activity?.start_time">开始: {{ overview.activity.start_time }}</span>
            <span v-if="overview.activity?.end_time">结束: {{ overview.activity.end_time }}</span>
          </div>
        </div>
        <div class="flex items-center gap-3 text-xs">
          <div class="px-3 py-2 rounded-lg bg-[var(--color-bg-base)] border border-white/5">
            <span class="text-[var(--color-text-disabled)]">活动结束倒计时</span>
            <span class="ml-2 font-mono font-bold text-[var(--color-warning)]">{{ formatSeconds(overview.activity?.countdown_seconds || 0) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Config + Task Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Config Panel -->
      <div class="glass-card p-5">
        <h3 class="text-sm font-semibold text-[var(--color-text-primary)] mb-4">任务配置</h3>
        <div class="space-y-4">
          <div>
            <label class="text-[11px] text-[var(--color-text-disabled)] mb-1.5 block">活动网页 URL</label>
            <div class="flex gap-2">
              <input v-model="sourceUrl" type="url" class="input-field flex-1 min-w-0 text-xs" placeholder="https://www.bilibili.com/blackboard/era/..." />
              <button @click="refreshConfigFromUrl" :disabled="refreshConfigLoading" class="btn-ghost px-3 flex items-center justify-center" title="从网页抓取资源配置">
                <RefreshCw :size="14" :class="refreshConfigLoading && 'animate-spin'" />
              </button>
            </div>
          </div>
          <div>
            <label class="text-[11px] text-[var(--color-text-disabled)] mb-1.5 block">游戏配置</label>
            <select v-model="app.currentGame" @change="() => { loadTasks(); loadOverview() }" class="input-field w-full text-sm">
              <option v-for="game in app.games" :key="game.key" :value="game.key">{{ game.label }}</option>
            </select>
          </div>
          <div>
            <label class="text-[11px] text-[var(--color-text-disabled)] mb-1.5 block">抢购时间</label>
            <input v-model="robPeriod" type="datetime-local" class="input-field w-full text-xs" />
          </div>
          <div>
            <label class="text-[11px] text-[var(--color-text-disabled)] mb-1.5 block">抢兑间隔（秒）</label>
            <input v-model.number="robInterval" type="number" min="0.05" step="0.05" class="input-field w-full" />
          </div>
          <div>
            <label class="text-[11px] text-[var(--color-text-disabled)] mb-1.5 block">持续时间（秒）</label>
            <input v-model.number="robHoldtime" type="number" min="1" max="300" class="input-field w-full" />
          </div>
          <div>
            <label class="text-[11px] text-[var(--color-text-disabled)] mb-1.5 block">运行模式</label>
            <select v-model="robMode" class="input-field w-full text-sm">
              <option value="auto">自动模式</option>
              <option value="manual">手动模式</option>
              <option value="scheduled">定时模式</option>
            </select>
          </div>
          <div class="flex gap-2 pt-2">
            <button @click="startRob" :disabled="isRunning" class="btn-primary flex-1 flex items-center justify-center gap-1.5">
              <Play :size="14" /> 启动
            </button>
            <button @click="stopRob" :disabled="!isRunning" class="btn-ghost flex-1 flex items-center justify-center gap-1.5">
              <Pause :size="14" /> 停止
            </button>
          </div>
        </div>
      </div>

      <!-- Resource Task List -->
      <div class="lg:col-span-2 glass-card p-5">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-sm font-semibold text-[var(--color-text-primary)]">资源道具列表</h3>
          <div class="flex items-center gap-2">
            <button @click="taskStore.selectAll()" class="btn-ghost text-[10px] px-3 py-1">全选</button>
            <button @click="taskStore.clearSelection()" class="btn-ghost text-[10px] px-3 py-1">清空</button>
            <span class="text-[10px] text-[var(--color-text-disabled)]">{{ taskStore.selectedTaskIds.size }}/{{ taskStore.tasks.length }}</span>
          </div>
        </div>
        <div class="space-y-2 max-h-60 overflow-y-auto">
          <div v-if="taskStore.tasks.length === 0" class="text-center py-12 text-[var(--color-text-disabled)] text-sm">
            暂无任务，请先登录或刷新配置
          </div>
          <div v-for="task in taskStore.tasks" :key="task.id"
            @click="!isRunning && taskStore.toggleTask(task.id)"
            :class="[
              'flex items-center justify-between px-4 py-3 rounded-xl border transition-all',
              itemResults[task.id]?.status === 'success'
                ? 'border-[var(--color-success)]/30 bg-[var(--color-success)]/5'
                : itemResults[task.id]?.status === 'failed'
                ? 'border-[var(--color-error)]/20 bg-[var(--color-error)]/5'
                : taskStore.selectedTaskIds.has(task.id)
                ? 'border-[var(--color-primary)]/30 bg-[var(--color-primary)]/5 cursor-pointer'
                : 'border-white/5 bg-[var(--color-bg-overlay)] hover:border-white/10 cursor-pointer'
            ]">
            <div class="flex items-center gap-3 flex-1 min-w-0">
              <!-- Checkbox / Status icon -->
              <template v-if="itemResults[task.id]?.status === 'success'">
                <CheckSquare :size="14" class="text-[var(--color-success)] shrink-0" />
              </template>
              <template v-else-if="itemResults[task.id]?.status === 'failed'">
                <AlertCircle :size="14" class="text-[var(--color-error)] shrink-0" />
              </template>
              <template v-else>
                <CheckSquare v-if="taskStore.selectedTaskIds.has(task.id)" :size="14" class="text-[var(--color-primary)] shrink-0" />
                <Square v-else :size="14" class="text-[var(--color-text-disabled)] shrink-0" />
              </template>
              <div class="flex-1 min-w-0">
                <div class="text-xs font-medium text-[var(--color-text-primary)] truncate">{{ task.name }}</div>
                <div class="text-[10px] text-[var(--color-text-disabled)] mt-0.5 truncate">{{ task.description || task.id }}</div>
                <!-- Execution result message -->
                <div v-if="itemResults[task.id]" class="mt-1">
                  <span :class="[
                    'text-[10px] font-medium',
                    itemResults[task.id].status === 'success' ? 'text-[var(--color-success)]' : 'text-[var(--color-error)]'
                  ]">
                    {{ itemResults[task.id].message }}
                  </span>
                  <span v-if="itemResults[task.id].cdkey" class="ml-2 text-[10px] font-mono px-1.5 py-0.5 rounded bg-[var(--color-warning)]/10 text-[var(--color-warning)]">
                    {{ itemResults[task.id].cdkey }}
                  </span>
                </div>
              </div>
            </div>
            <div class="shrink-0 ml-2">
              <StatusBadge v-if="itemResults[task.id]" :status="itemResults[task.id].status === 'success' ? 'success' : 'error'" />
              <StatusBadge v-else :status="taskStatusMap[task.status ?? 'idle'] ?? 'idle'" />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Snipe Engine Task History -->
    <div v-if="snipeTasks.length > 0" class="glass-card p-5">
      <div class="flex items-center justify-between mb-4 cursor-pointer" @click="showTaskPanel = !showTaskPanel">
        <div class="flex items-center gap-2">
          <h3 class="text-sm font-semibold text-[var(--color-text-primary)]">抢兑任务记录</h3>
          <span class="text-[10px] px-2 py-0.5 rounded-full bg-[var(--color-bg-base)] text-[var(--color-text-disabled)]">{{ snipeTasks.length }}</span>
        </div>
        <ChevronUp v-if="showTaskPanel" :size="14" class="text-[var(--color-text-disabled)]" />
        <ChevronDown v-else :size="14" class="text-[var(--color-text-disabled)]" />
      </div>
      <div v-show="showTaskPanel" class="space-y-2">
        <div v-for="task in snipeTasks" :key="task.id"
          class="bg-[var(--color-bg-base)] rounded-xl p-4 border border-white/5">
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center gap-2">
              <span :class="['text-xs font-semibold', taskStatusColor[task.status]]">{{ taskStatusLabel[task.status] || task.status }}</span>
              <span class="text-[10px] text-[var(--color-text-disabled)] font-mono">{{ task.id }}</span>
            </div>
            <div class="flex items-center gap-2 text-[10px] text-[var(--color-text-disabled)]">
              <span v-if="task.progress">{{ task.progress }}%</span>
              <span v-if="task.status === 'waiting' && task.countdown_seconds" class="text-[var(--color-warning)] font-mono">
                等待 {{ formatSeconds(task.countdown_seconds) }}
              </span>
              <span v-if="task.results?.length">
                {{ task.results.filter((r: any) => r.status === 'success').length }}/{{ task.results.length }} 成功
              </span>
            </div>
          </div>
          <!-- Progress bar -->
          <div v-if="task.status === 'running'" class="h-1 rounded-full bg-white/5 mb-2 overflow-hidden">
            <div class="h-full bg-gradient-to-r from-[var(--color-primary)] to-[var(--color-primary-hover)] rounded-full transition-all"
              :style="{ width: `${task.progress || 0}%` }" />
          </div>
          <!-- Results -->
          <div v-if="task.results?.length" class="space-y-1 mt-2">
            <div v-for="(r, ri) in task.results" :key="ri"
              :class="['flex items-center gap-2 text-[11px] px-2 py-1 rounded', r.status === 'success' ? 'bg-[var(--color-success)]/5 text-[var(--color-success)]' : 'bg-[var(--color-error)]/5 text-[var(--color-error)]']">
              <span class="font-medium">{{ r.name || r.task_id }}</span>
              <span class="flex-1">{{ r.message }}</span>
              <span v-if="r.cdkey" class="font-mono text-[var(--color-warning)] bg-[var(--color-warning)]/10 px-1 rounded">{{ r.cdkey }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Live Log -->
    <div class="glass-card p-5">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-sm font-semibold text-[var(--color-text-primary)]">执行日志</h3>
        <div class="flex items-center gap-2">
          <span class="text-[10px] text-[var(--color-text-disabled)]">{{ logs.length }} 条</span>
          <button @click="logs = []" class="btn-ghost text-[10px] px-3 py-1">清空</button>
        </div>
      </div>
      <div class="bg-[var(--color-bg-base)] rounded-xl p-4 h-52 overflow-y-auto font-mono text-xs space-y-1">
        <div v-if="logs.length === 0" class="text-center py-8 text-[var(--color-text-disabled)]">
          暂无日志，启动抢码任务后将在此显示执行过程
        </div>
        <div v-for="(log, i) in logs" :key="i" :class="['flex gap-3', logColorMap[log.level]]">
          <span class="text-[var(--color-text-disabled)] shrink-0">{{ log.time }}</span>
          <span>[{{ log.level.toUpperCase() }}]</span>
          <span class="text-[var(--color-text-primary)]">{{ log.msg }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
