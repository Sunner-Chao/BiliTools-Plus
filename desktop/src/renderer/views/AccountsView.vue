<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useApi } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useAppStore } from '@/stores/useAppStore'
import StatusBadge from '@/components/StatusBadge.vue'
import { UserCog, QrCode, Smartphone, CheckCircle2, Clock, XCircle, Plus, Trash2, X, RefreshCw, ShieldCheck, Cookie } from 'lucide-vue-next'

interface Account { id: string; username: string; game: string; status: 'active'|'expired'|'error'; last_used: string; cookie_valid: boolean }
type QrStatus = 'idle'|'generating'|'pending'|'scanned'|'confirmed'|'expired'|'error'

const app = useAppStore()
const { request } = useApi()
const toast = useToast()
const accounts = ref<Account[]>([])
const cookieInput = ref('')
const showCookieDialog = ref(false)
const activeTab = ref<'cookie'|'qr'>('qr')

const qrcodeKey = ref('')
const qrcodeImage = ref('')
const qrStatus = ref<QrStatus>('idle')
const qrMessage = ref('')
const expireCountdown = ref(180)
let pollTimer: ReturnType<typeof setInterval> | null = null
let countdownTimer: ReturnType<typeof setInterval> | null = null

async function loadAccounts() {
  const data = await request<Account[]>('/api/accounts')
  if (data) accounts.value = data
}
async function deleteAccount(id: string) {
  const ok = await request(`/api/accounts/${id}`, { method: 'DELETE' })
  if (ok !== null) { toast.success('账号已删除'); accounts.value = accounts.value.filter(a => a.id !== id) }
}
async function importCookie() {
  if (!cookieInput.value.trim()) { toast.warning('请输入Cookie'); return }
  const ok = await request('/api/accounts/import', { method: 'POST', body: JSON.stringify({ cookie: cookieInput.value, game: app.currentGame }) })
  if (ok !== null) { toast.success('Cookie导入成功'); showCookieDialog.value = false; cookieInput.value = ''; loadAccounts() }
}

async function startQrLogin() {
  stopPolling()
  qrStatus.value = 'generating'; qrMessage.value = '正在生成二维码...'
  try {
    const data = await request<{ qrcode_key: string; image: string; expires_in: number }>('/api/auth/qrcode/generate', { method: 'POST' })
    if (!data) { qrStatus.value = 'error'; qrMessage.value = '生成失败'; return }
    qrcodeKey.value = data.qrcode_key; qrcodeImage.value = data.image; expireCountdown.value = data.expires_in ?? 180
    qrStatus.value = 'pending'; qrMessage.value = '请使用B站手机App扫码'
    startPolling(); startCountdown()
  } catch { qrStatus.value = 'error'; qrMessage.value = '网络错误，请重试' }
}
function startPolling() { pollTimer = setInterval(pollQrStatus, 2000) }
function stopPolling() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } }
function stopCountdown() { if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null } }

async function pollQrStatus() {
  if (!qrcodeKey.value) return
  try {
    const data = await request<{ code: number; status: string; message: string; username?: string; uid?: number }>(`/api/auth/qrcode/poll?qrcode_key=${qrcodeKey.value}`)
    if (!data) return
    qrMessage.value = data.message ?? ''
    if (data.code === 86101) qrStatus.value = 'pending'
    else if (data.code === 86090) { qrStatus.value = 'scanned'; qrMessage.value = '扫码成功，请在手机端确认' }
    else if (data.code === 0) {
      qrStatus.value = 'confirmed'; stopPolling(); stopCountdown()
      const confirmResp = await request<{
        is_login: boolean; username: string; uid: string; cookies: string;
        room_id: string; avatar: string; level: number; bili_jct: string;
        access_token: string; expires_in: number;
      }>(`/api/auth/qrcode/confirm?qrcode_key=${qrcodeKey.value}`, { method: 'POST' })
      if (confirmResp) {
        const d = confirmResp.data ?? confirmResp
        app.login({
          token: d.access_token,
          username: d.username,
          cookies: d.cookies ?? '',
          uid: d.uid ?? '',
          room_id: d.room_id ?? '',
          avatar: d.avatar ?? '',
          level: d.level ?? 0,
          bili_jct: d.bili_jct ?? '',
        })
        toast.success(`登录成功，欢迎 ${d.username}！`)
      }
    } else if (data.code === 86038) { qrStatus.value = 'expired'; qrMessage.value = '二维码已过期，请刷新'; stopPolling(); stopCountdown() }
    else { qrStatus.value = 'error'; qrMessage.value = data.message ?? '未知错误'; stopPolling() }
  } catch { /* ignore */ }
}

function startCountdown() {
  stopCountdown(); expireCountdown.value = 180
  countdownTimer = setInterval(() => {
    expireCountdown.value--
    if (expireCountdown.value <= 0) { qrStatus.value = 'expired'; qrMessage.value = '二维码已过期，请刷新'; stopPolling(); stopCountdown() }
  }, 1000)
}

const qrStatusConfig = computed(() => {
  const map: Record<QrStatus, { color: string; icon: any; label: string }> = {
    idle:       { color: 'var(--color-text-secondary)', icon: QrCode, label: '等待生成' },
    generating: { color: 'var(--color-info)', icon: RefreshCw, label: '生成中...' },
    pending:    { color: 'var(--color-warning)', icon: Smartphone, label: '等待扫码' },
    scanned:    { color: 'var(--color-info)', icon: CheckCircle2, label: '已扫码' },
    confirmed:  { color: 'var(--color-success)', icon: ShieldCheck, label: '登录成功' },
    expired:    { color: 'var(--color-error)', icon: XCircle, label: '已过期' },
    error:      { color: 'var(--color-error)', icon: XCircle, label: '错误' },
  }
  return map[qrStatus.value] ?? map.idle
})

onMounted(loadAccounts)
onUnmounted(() => { stopPolling(); stopCountdown() })
</script>

<template>
  <div class="p-6 space-y-5 main-bg min-h-full">
    <div class="flex items-center justify-between">
      <h2 class="text-xl font-bold flex items-center gap-2">
        <UserCog :size="20" class="text-[var(--color-primary)]" /> 账号管理
      </h2>
      <button @click="showCookieDialog = true" class="px-4 py-2 rounded-lg bg-[var(--color-primary)] text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] transition-all shadow-md shadow-[var(--color-primary)]/20 flex items-center gap-1.5">
        <Plus :size="15" /> 导入Cookie
      </button>
    </div>

    <!-- Tab switcher -->
    <div class="glass-card p-1.5 inline-flex rounded-xl">
      <button v-for="tab in [{ key: 'cookie', label: 'Cookie导入' }, { key: 'qr', label: '扫码登录' }]" :key="tab.key"
        @click="activeTab = tab.key as any; if(tab.key==='qr') startQrLogin()"
        :class="['px-5 py-2 rounded-lg text-sm font-medium transition-all', activeTab === tab.key ? 'bg-[var(--color-primary)] text-white shadow-sm' : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]']">
        {{ tab.label }}
      </button>
    </div>

    <!-- QR Login Panel -->
    <div v-if="activeTab === 'qr'" class="glass-card p-6">
      <div class="flex items-center gap-4">
        <div class="relative w-48 h-48 flex-shrink-0 rounded-2xl bg-white overflow-hidden border border-[var(--color-border)]">
          <div v-if="qrStatus === 'idle'" @click="startQrLogin" class="w-full h-full flex flex-col items-center justify-center cursor-pointer hover:bg-gray-50 transition-colors">
            <QrCode :size="40" class="text-gray-400 mb-2" /> <span class="text-xs text-gray-400">点击生成二维码</span>
          </div>
          <img v-else-if="qrcodeImage" :src="qrcodeImage" alt="登录二维码" class="w-full h-full object-contain p-3" />
          <div v-if="qrStatus !== 'idle' && qrStatus !== 'generating'"
            class="absolute inset-0 flex flex-col items-center justify-center bg-black/60 backdrop-blur-sm">
            <component :is="qrStatusConfig.icon" :size="32" :class="'mb-2 ' + qrStatusConfig.color" />
            <span class="text-xs font-medium" :style="{ color: qrStatusConfig.color }">{{ qrStatusConfig.label }}</span>
          </div>
        </div>
        <div class="flex-1 space-y-4">
          <div class="flex items-center gap-3">
            <component :is="qrStatusConfig.icon" :size="24" :class="qrStatusConfig.color" />
            <div>
              <p class="text-sm font-semibold" :style="{ color: qrStatusConfig.color }">{{ qrStatusConfig.label }}</p>
              <p class="text-xs text-[var(--color-text-secondary)] mt-0.5">{{ qrMessage }}</p>
            </div>
          </div>
          <div v-if="qrStatus === 'pending' || qrStatus === 'scanned'" class="space-y-1.5">
            <div class="flex items-center justify-between text-xs text-[var(--color-text-secondary)]">
              <span>有效期倒计时</span> <span class="font-mono tabular-nums">{{ expireCountdown }}s</span>
            </div>
            <div class="w-full h-1.5 bg-[var(--color-bg-overlay)] rounded-full overflow-hidden">
              <div class="h-full bg-gradient-to-r from-[var(--color-primary)] to-[var(--color-primary-hover)] rounded-full transition-all duration-1000" :style="{ width: `${(expireCountdown / 180) * 100}%` }" />
            </div>
          </div>
          <div class="flex items-center gap-3">
            <button v-if="qrStatus !== 'generating' && qrStatus !== 'idle'" @click="startQrLogin" class="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--color-bg-overlay)] hover:bg-white/5 border border-[var(--color-border)] text-sm text-[var(--color-text-secondary)] transition-all">
              <RefreshCw :size="14" /> 刷新二维码
            </button>
            <button v-if="qrStatus !== 'idle' && qrStatus !== 'generating'" @click="stopPolling(); stopCountdown(); qrcodeKey=''; qrcodeImage=''; qrStatus='idle'" class="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 text-[var(--color-error)] text-sm transition-all">
              <XCircle :size="14" /> 取消
            </button>
          </div>
          <div v-if="qrStatus === 'pending'" class="text-xs text-[var(--color-text-disabled)] space-y-1">
            <p>1. 打开手机B站客户端</p><p>2. 点击首页左上角扫一扫</p><p>3. 扫描左侧二维码</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Account list -->
    <div class="space-y-3">
      <div v-if="accounts.length === 0" class="text-center py-12 text-[var(--color-text-disabled)]">
        <p class="text-4xl mb-3">🔒</p><p>暂无账号，请导入Cookie添加</p>
      </div>
      <div v-for="acc in accounts" :key="acc.id"
        class="group flex items-center gap-4 p-4 rounded-xl glass-card hover:border-[var(--color-primary)]/30 transition-all">
        <div class="w-10 h-10 rounded-full bg-gradient-to-br from-[var(--color-primary)] to-[#0066cc] flex items-center justify-center text-white font-bold text-sm shadow-lg shadow-[var(--color-primary)]/20">
          {{ acc.username?.charAt(0)?.toUpperCase() ?? '?' }}
        </div>
        <div class="flex-1 min-w-0">
          <p class="font-semibold text-sm truncate">{{ acc.username || '未知用户' }}</p>
          <p class="text-xs text-[var(--color-text-secondary)]">{{ acc.game }} · {{ acc.last_used || '未使用' }}</p>
        </div>
        <StatusBadge :status="acc.cookie_valid ? 'success' : 'error'">{{ acc.cookie_valid ? '有效' : '已失效' }}</StatusBadge>
        <button @click="deleteAccount(acc.id)" class="opacity-0 group-hover:opacity-100 px-3 py-1 rounded-md text-xs bg-red-500/15 text-[var(--color-error)] hover:bg-red-500/25 transition-all flex items-center gap-1">
          <Trash2 :size="12" /> 删除
        </button>
      </div>
    </div>

    <!-- Cookie Import Dialog -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="showCookieDialog" class="fixed inset-0 z-[9998] flex items-center justify-center bg-black/50 backdrop-blur-sm" @click.self="showCookieDialog = false">
          <div class="w-full max-w-lg p-6 rounded-2xl glass-card shadow-2xl">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-lg font-bold flex items-center gap-2">
                <Cookie :size="18" class="text-[var(--color-primary)]" /> 导入Cookie
              </h3>
              <button @click="showCookieDialog = false"><X :size="18" class="text-[var(--color-text-secondary)]" /></button>
            </div>
            <p class="text-xs text-[var(--color-text-secondary)] mb-3">请粘贴B站登录Cookie，将绑定到当前选中游戏分区（{{ app.games.find(g => g.key === app.currentGame)?.label }}）</p>
            <textarea v-model="cookieInput" rows="5" placeholder="SESSDATA=xxx; bili_jct=xxx; ..."
              class="w-full bg-[var(--color-bg-base)] text-[var(--color-text-primary)] text-sm px-4 py-3 rounded-lg border border-[var(--color-border)] outline-none focus:border-[var(--color-primary)] font-mono resize-none" />
            <div class="flex justify-end gap-3 mt-4">
              <button @click="showCookieDialog = false" class="px-4 py-2 rounded-lg text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]">取消</button>
              <button @click="importCookie" class="px-5 py-2 rounded-lg bg-[var(--color-primary)] text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] transition-all shadow-md shadow-[var(--color-primary)]/20">确认导入</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>
<style scoped>
.modal-enter-active, .modal-leave-active { transition: all 0.25s ease; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
</style>
