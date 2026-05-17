<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Gift, LogIn, MessageSquare, Radio, RefreshCw, ShieldCheck, Users } from 'lucide-vue-next'
import StatusBadge from '@/components/StatusBadge.vue'
import { useApi } from '@/composables/useApi'
import { useAppStore } from '@/stores/useAppStore'
import { useToast } from '@/composables/useToast'

type Slot = {
  slot: number
  has_cookie: boolean
  is_valid: boolean
  name?: string
  mid?: string | number
  avatar?: string
  live_entry?: { room_id: string; expires_at: string; name: string }
}

type LogItem = { time: string; level: 'info' | 'success' | 'error' | 'warn'; msg: string }

const api = useApi()
const app = useAppStore()
const toast = useToast()

const roomId = ref(app.room_id || '')
const durationMinutes = ref(16)
const customDanmaku = ref('')
const loading = ref(false)
const slots = ref<Slot[]>([])
const logs = ref<LogItem[]>([])
const modalSlot = ref<Slot | null>(null)
const audienceCookie = ref('')
const qrInfo = ref<{ qr_key: string; qr_url: string; expires_in: number } | null>(null)
const qrMessage = ref('')
let pollTimer: ReturnType<typeof setInterval> | null = null
let statusTimer: ReturnType<typeof setInterval> | null = null

const validCount = computed(() => slots.value.filter((slot) => slot.is_valid).length)

const levelClass: Record<string, string> = {
  info: 'text-[var(--color-text-secondary)]',
  success: 'text-[var(--color-success)]',
  error: 'text-[var(--color-error)]',
  warn: 'text-[var(--color-warning)]',
}

function stopQrPolling() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = null
}

async function loadStatus() {
  const data = await api.get('/api/daily/status')
  if (!data) return
  slots.value = data.slots || []
  logs.value = data.logs || []
}

async function openQr(slot: Slot) {
  modalSlot.value = slot
  audienceCookie.value = ''
  qrInfo.value = null
  qrMessage.value = '正在生成二维码...'
  stopQrPolling()
  const data = await api.post(`/api/daily/audience/qrcode?slot=${slot.slot}`)
  if (!data?.success) {
    qrMessage.value = data?.error || '二维码生成失败'
    return
  }
  qrInfo.value = data
  qrMessage.value = '请使用哔哩哔哩 APP 扫码'
  pollTimer = setInterval(async () => {
    if (!qrInfo.value?.qr_key) return
    const status = await api.get(`/api/daily/audience/qrcode/status?qr_key=${encodeURIComponent(qrInfo.value.qr_key)}`)
    if (!status) return
    qrMessage.value = status.message || qrMessage.value
    if (status.status === 'success') {
      toast.success(`观众 ${slot.slot + 1} 身份已保存`)
      closeModal()
      await loadStatus()
    }
    if (['expired', 'failed', 'error'].includes(status.status)) stopQrPolling()
  }, 1600)
}

function closeModal() {
  modalSlot.value = null
  qrInfo.value = null
  audienceCookie.value = ''
  stopQrPolling()
}

async function saveManualCookie() {
  if (!modalSlot.value || !audienceCookie.value.trim()) {
    toast.warning('请粘贴观众 Cookie')
    return
  }
  const data = await api.post('/api/daily/audience/cookie', { slot: modalSlot.value.slot, cookies: audienceCookie.value.trim() })
  if (data?.success) {
    toast.success('观众身份已保存')
    closeModal()
    await loadStatus()
  }
}

async function runSlot(slot: Slot, path: string, okText: string) {
  if (!roomId.value) {
    toast.warning('请填写直播间房间号')
    return
  }
  loading.value = true
  try {
    const data = await api.post(path, {
      slot: slot.slot,
      room_id: roomId.value,
      msg: customDanmaku.value,
      duration_minutes: durationMinutes.value,
    })
    if (data?.success) toast.success(okText)
    else toast.warning(data?.payload?.message || data?.payload?.msg || '接口返回失败')
    await loadStatus()
  } finally {
    loading.value = false
  }
}

async function runAll(path: string, okText: string) {
  for (const slot of slots.value.filter((item) => item.is_valid)) {
    await runSlot(slot, path, `观众 ${slot.slot + 1} ${okText}`)
  }
}

function remaining(entry?: Slot['live_entry']) {
  if (!entry?.expires_at) return ''
  const ms = new Date(entry.expires_at).getTime() - Date.now()
  if (ms <= 0) return '已到期'
  const minutes = Math.floor(ms / 60000)
  const seconds = Math.floor((ms % 60000) / 1000)
  return `${minutes}分${String(seconds).padStart(2, '0')}秒`
}

onMounted(() => {
  loadStatus()
  statusTimer = setInterval(loadStatus, 5000)
})

onUnmounted(() => {
  stopQrPolling()
  if (statusTimer) clearInterval(statusTimer)
})
</script>

<template>
  <div class="p-6 space-y-6 main-bg min-h-full">
    <div class="flex items-center justify-between">
      <div>
        <div class="h-1 w-12 bg-gradient-to-r from-[var(--color-primary)] to-[var(--color-primary-hover)] rounded-full mb-3" />
        <h1 class="text-2xl font-bold text-[var(--color-text-primary)]">每日任务系统</h1>
        <p class="text-sm text-[var(--color-text-secondary)] mt-0.5">观众扫码身份 · 进房 · 发弹幕 · 赠送礼物</p>
      </div>
      <StatusBadge :status="loading ? 'running' : 'idle'" :pulse="loading">
        {{ loading ? '执行中' : `${validCount}/4 可用` }}
      </StatusBadge>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-4 gap-4">
      <div class="glass-card p-5 lg:col-span-1 space-y-4">
        <div class="flex items-center gap-2 text-sm font-semibold text-[var(--color-text-primary)]">
          <Radio :size="16" class="text-[var(--color-primary)]" /> 任务参数
        </div>
        <div>
          <label class="text-[11px] text-[var(--color-text-disabled)] mb-1.5 block">直播间房间号</label>
          <input v-model="roomId" type="text" class="input-field w-full text-sm" placeholder="登录后自动填充，也可手动输入" />
        </div>
        <div>
          <label class="text-[11px] text-[var(--color-text-disabled)] mb-1.5 block">进房保持时间（分钟）</label>
          <input v-model.number="durationMinutes" type="number" min="1" max="360" class="input-field w-full text-sm" />
        </div>
        <div>
          <label class="text-[11px] text-[var(--color-text-disabled)] mb-1.5 block">弹幕内容</label>
          <input v-model="customDanmaku" type="text" class="input-field w-full text-sm" placeholder="留空使用随机弹幕" />
        </div>
        <div class="grid grid-cols-1 gap-2 pt-2">
          <button class="btn-primary flex items-center justify-center gap-2" :disabled="loading || validCount === 0" @click="runAll('/api/daily/audience/enter', '已进入直播间')">
            <LogIn :size="14" /> 全部进房
          </button>
          <button class="btn-ghost flex items-center justify-center gap-2" :disabled="loading || validCount === 0" @click="runAll('/api/daily/audience/danmaku', '弹幕已发送')">
            <MessageSquare :size="14" /> 全部弹幕
          </button>
          <button class="btn-ghost flex items-center justify-center gap-2" :disabled="loading || validCount === 0" @click="runAll('/api/daily/audience/gift', '礼物已发送')">
            <Gift :size="14" /> 全部送礼
          </button>
        </div>
      </div>

      <div class="lg:col-span-3 grid grid-cols-1 md:grid-cols-2 gap-4">
        <div v-for="slot in slots" :key="slot.slot" class="glass-card p-5">
          <div class="flex items-start justify-between gap-3">
            <div class="flex items-center gap-3 min-w-0">
              <img v-if="slot.avatar" :src="slot.avatar" class="w-11 h-11 rounded-full object-cover ring-2 ring-white/10" alt="avatar" />
              <div v-else class="w-11 h-11 rounded-full bg-[var(--color-bg-base)] flex items-center justify-center">
                <Users :size="18" class="text-[var(--color-text-secondary)]" />
              </div>
              <div class="min-w-0">
                <div class="text-sm font-semibold text-[var(--color-text-primary)] truncate">观众 {{ slot.slot + 1 }} · {{ slot.name || '未绑定' }}</div>
                <div class="text-[11px] text-[var(--color-text-disabled)] truncate">{{ slot.mid ? `UID ${slot.mid}` : '扫码后自动保存 Cookie' }}</div>
              </div>
            </div>
            <StatusBadge :status="slot.is_valid ? 'success' : slot.has_cookie ? 'warning' : 'idle'">
              {{ slot.is_valid ? '有效' : slot.has_cookie ? '需验证' : '未配置' }}
            </StatusBadge>
          </div>

          <div v-if="slot.live_entry" class="mt-4 rounded-lg border border-white/5 bg-[var(--color-bg-base)] p-3 text-xs text-[var(--color-text-secondary)]">
            <div>直播间 {{ slot.live_entry.room_id }}</div>
            <div class="mt-1 text-[var(--color-primary)]">进房倒计时 {{ remaining(slot.live_entry) }}</div>
          </div>

          <div class="mt-4 grid grid-cols-2 gap-2">
            <button class="btn-primary flex items-center justify-center gap-1.5" @click="openQr(slot)">
              <ShieldCheck :size="14" /> 扫码
            </button>
            <button class="btn-ghost flex items-center justify-center gap-1.5" :disabled="loading" @click="runSlot(slot, '/api/daily/audience/validate', '身份有效')">
              <RefreshCw :size="14" /> 验证
            </button>
            <button class="btn-ghost flex items-center justify-center gap-1.5" :disabled="loading || !slot.is_valid" @click="runSlot(slot, '/api/daily/audience/enter', '已进入直播间')">
              <LogIn :size="14" /> 进房
            </button>
            <button class="btn-ghost flex items-center justify-center gap-1.5" :disabled="loading || !slot.is_valid" @click="runSlot(slot, '/api/daily/audience/danmaku', '弹幕已发送')">
              <MessageSquare :size="14" /> 弹幕
            </button>
            <button class="btn-ghost col-span-2 flex items-center justify-center gap-1.5" :disabled="loading || !slot.is_valid" @click="runSlot(slot, '/api/daily/audience/gift', '礼物已发送')">
              <Gift :size="14" /> 赠送牛蛙
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="glass-card p-5">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-sm font-semibold text-[var(--color-text-primary)]">执行日志</h2>
        <button class="btn-ghost flex items-center gap-1.5 text-sm" @click="loadStatus">
          <RefreshCw :size="14" /> 刷新
        </button>
      </div>
      <div class="space-y-2 max-h-80 overflow-y-auto">
        <div v-for="(log, index) in logs.slice().reverse()" :key="`${log.time}-${index}`" class="grid grid-cols-[72px_80px_1fr] gap-3 rounded-lg bg-[var(--color-bg-base)]/80 px-3 py-2 text-xs">
          <span class="font-mono text-[var(--color-text-disabled)]">{{ log.time }}</span>
          <span :class="['font-medium', levelClass[log.level]]">{{ log.level }}</span>
          <span class="text-[var(--color-text-secondary)] break-words">{{ log.msg }}</span>
        </div>
        <div v-if="logs.length === 0" class="text-sm text-[var(--color-text-disabled)] text-center py-8">暂无日志</div>
      </div>
    </div>

    <div v-if="modalSlot" class="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
      <div class="glass-card w-full max-w-xl p-6 space-y-5">
        <div class="flex items-center justify-between">
          <div>
            <h3 class="text-lg font-semibold text-[var(--color-text-primary)]">观众 {{ modalSlot.slot + 1 }} 扫码登录</h3>
            <p class="text-xs text-[var(--color-text-secondary)] mt-1">{{ qrMessage }}</p>
          </div>
          <button class="btn-ghost" @click="closeModal">关闭</button>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-[220px_1fr] gap-5">
          <div class="rounded-xl bg-white p-4 aspect-square flex items-center justify-center">
            <img v-if="qrInfo?.qr_url" :src="qrInfo.qr_url" class="w-full h-full object-contain" alt="观众登录二维码" />
            <span v-else class="text-sm text-gray-500">生成中...</span>
          </div>
          <div class="space-y-3">
            <div class="text-xs text-[var(--color-text-secondary)] leading-6">
              扫码成功后会自动写入 <span class="font-mono">cookies/bili_cookies_sub{{ modalSlot.slot }}</span>。
              如果网络环境导致回写失败，也可以在这里粘贴 Cookie 手动保存。
            </div>
            <textarea v-model="audienceCookie" class="input-field w-full h-32 text-xs font-mono" placeholder="SESSDATA=...; bili_jct=...; DedeUserID=..." />
            <button class="btn-primary w-full" @click="saveManualCookie">保存手动 Cookie</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
