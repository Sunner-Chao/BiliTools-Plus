<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <div class="logo-icon">B</div>
        <h1>BiliTools-Plus</h1>
        <p class="subtitle">B站游戏资源抢购工具</p>
      </div>

      <div class="login-tabs" v-if="!isLogin">
        <button :class="{ active: activeMode === 'qr' }" @click="switchMode('qr')">扫码登录</button>
        <button :class="{ active: activeMode === 'cookie' }" @click="switchMode('cookie')">Cookie登录</button>
      </div>

      <div class="qr-section" v-if="!isLogin && activeMode === 'qr'">
        <h2>扫码登录</h2>

        <div class="qr-box" :class="{ scanning: qrStatus === 'pending' }">
          <img v-if="qrImage" :src="qrImage" alt="扫码登录" class="qr-image" />
          <div v-else class="qr-placeholder">
            <div class="spinner"></div>
            <span>生成二维码中...</span>
          </div>

          <div v-if="['scanned', 'confirmed', 'expired', 'failed'].includes(qrStatus)" class="qr-overlay">
            <div v-if="qrStatus === 'scanned'" class="status-msg scanned">
              <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20 6L9 17l-5-5"/>
              </svg>
              <span>已扫码，请在手机确认</span>
            </div>
            <div v-else-if="qrStatus === 'confirmed'" class="status-msg confirmed">
              <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20 6L9 17l-5-5"/>
              </svg>
              <span>登录成功！正在跳转...</span>
            </div>
            <div v-else-if="qrStatus === 'expired'" class="status-msg expired">
              <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 6L6 18M6 6l12 12"/>
              </svg>
              <span>二维码已过期</span>
              <button class="refresh-btn" @click="refreshQR">重新获取</button>
            </div>
            <div v-else-if="qrStatus === 'failed'" class="status-msg failed">
              <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 6L6 18M6 6l12 12"/>
              </svg>
              <span>扫码失败，请重试</span>
              <button class="refresh-btn" @click="refreshQR">重新获取</button>
            </div>
          </div>
        </div>

        <div class="hint">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/><path d="M12 16v-4m0-4h.01"/>
          </svg>
          <span>请使用B站手机客户端扫码登录</span>
        </div>
      </div>

      <div class="cookie-section" v-if="!isLogin && activeMode === 'cookie'">
        <h2>Cookie登录</h2>
        <textarea
          v-model="cookieInput"
          class="cookie-input"
          placeholder="SESSDATA=...; bili_jct=...; DedeUserID=..."
          spellcheck="false"
        />
        <button class="cookie-submit" :disabled="cookieLoading" @click="handleCookieLogin">
          {{ cookieLoading ? '验证中...' : '登录' }}
        </button>
        <div class="hint">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/><path d="M12 16v-4m0-4h.01"/>
          </svg>
          <span>从浏览器复制 B 站 Cookie 后粘贴到这里</span>
        </div>
      </div>

      <div v-else class="user-section">
        <div class="user-avatar">
          <img v-if="userInfo.avatar" :src="userInfo.avatar" alt="avatar" referrerpolicy="no-referrer" />
          <div v-else class="avatar-placeholder">{{ (userInfo.username || 'U')[0] }}</div>
        </div>
        <div class="user-info">
          <h3>{{ userInfo.username }}</h3>
          <p>UID: {{ userInfo.uid }}</p>
          <p v-if="userInfo.room_id">直播: {{ userInfo.room_id }}</p>
        </div>
        <button class="logout-btn" @click="handleLogout">退出登录</button>
      </div>

      <div v-if="error" class="error-msg">{{ error }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/stores/useAppStore'
import { useApi } from '@/composables/useApi'

const router = useRouter()
const store = useAppStore()
const api = useApi()

const qrImage = ref('')
const qrStatus = ref<'idle' | 'pending' | 'scanned' | 'confirmed' | 'expired' | 'failed'>('idle')
const error = ref('')
const pollTimer = ref<ReturnType<typeof setTimeout> | null>(null)
const currentQRKey = ref('')
const activeMode = ref<'qr' | 'cookie'>('qr')
const cookieInput = ref('')
const cookieLoading = ref(false)

const isLogin = computed(() => store.isLoggedIn)
const userInfo = computed(() => ({
  username: store.username || '',
  uid: store.uid || '',
  avatar: store.avatar || '',
  room_id: store.room_id || '',
}))

async function fetchQR() {
  error.value = ''
  qrStatus.value = 'idle'
  qrImage.value = ''
  try {
    const data = await api.post('/api/auth/qrcode/generate')
    if (data && data.code === 0) {
      qrImage.value = data.data.image
      currentQRKey.value = data.data.qrcode_key
      qrStatus.value = 'pending'
      startPolling(data.data.qrcode_key)
    } else {
      error.value = data.msg || '生成二维码失败'
    }
  } catch (e: any) {
    error.value = '网络错误: ' + (e.message || String(e))
  }
}

function startPolling(qrcode_key: string) {
  stopPolling()
  function poll() {
    pollTimer.value = setTimeout(async () => {
      try {
        const data = await api.get(`/api/auth/qrcode/poll?qrcode_key=${qrcode_key}`)
        if (!data) { qrStatus.value = 'failed'; error.value = '轮询失败'; return }
        const status = data.data?.status ?? data?.status

        if (status === 'pending') {
          qrStatus.value = 'pending'
          poll()
        } else if (status === 'scanned') {
          qrStatus.value = 'scanned'
          poll()
        } else if (status === 'confirmed') {
          qrStatus.value = 'confirmed'
          await confirmLogin(qrcode_key)
        } else if (status === 'expired') {
          qrStatus.value = 'expired'
          error.value = '二维码已过期'
        } else {
          qrStatus.value = 'failed'
          error.value = data.msg || '扫码失败'
        }
      } catch {
        qrStatus.value = 'failed'
        error.value = '轮询失败'
      }
    }, 1500)
  }
  poll()
}

function stopPolling() {
  if (pollTimer.value) {
    clearTimeout(pollTimer.value)
    pollTimer.value = null
  }
}

async function confirmLogin(qrcode_key: string) {
  try {
    const data = await api.post(`/api/auth/qrcode/confirm?qrcode_key=${qrcode_key}`)
    if (data && data.code === 0) {
      applyLoginPayload(data.data)
      stopPolling()
      setTimeout(() => router.push('/'), 800)
    } else {
      error.value = data.msg || '确认登录失败'
      qrStatus.value = 'failed'
    }
  } catch (e: any) {
    error.value = '确认登录失败: ' + (e.message || String(e))
    qrStatus.value = 'failed'
  }
}

function applyLoginPayload(d: any) {
  store.login({
    username: d.username,
    token: d.access_token,
    uid: d.uid,
    avatar: d.avatar,
    room_id: d.room_id,
    cookies: d.cookies,
    bili_jct: d.bili_jct || '',
    level: d.level || 0,
  })
}

function switchMode(mode: 'qr' | 'cookie') {
  activeMode.value = mode
  error.value = ''
  if (mode === 'cookie') {
    stopPolling()
    return
  }
  if (!qrImage.value && !store.isLoggedIn) {
    fetchQR()
  }
}

async function handleCookieLogin() {
  const cookie = cookieInput.value.trim()
  if (!cookie) {
    error.value = '请粘贴 B 站 Cookie'
    return
  }

  cookieLoading.value = true
  error.value = ''
  stopPolling()
  try {
    const data = await api.post('/api/auth/cookie', { cookie })
    if (data && data.code === 0) {
      applyLoginPayload(data.data)
      cookieInput.value = ''
      setTimeout(() => router.push('/'), 300)
    } else {
      error.value = data.msg || 'Cookie 登录失败'
    }
  } catch (e: any) {
    error.value = 'Cookie 登录失败: ' + (e.message || String(e))
  } finally {
    cookieLoading.value = false
  }
}

function refreshQR() {
  stopPolling()
  fetchQR()
}

async function handleLogout() {
  store.logout()
  router.push('/login')
  fetchQR()
}

onMounted(() => {
  if (!store.isLoggedIn) {
    fetchQR()
  }
})

onUnmounted(() => stopPolling())
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(ellipse 80% 60% at 50% 0%, rgba(129,140,248,0.15) 0%, transparent 50%),
    radial-gradient(ellipse 60% 40% at 80% 80%, rgba(99,102,241,0.08) 0%, transparent 50%),
    var(--color-bg-base);
  padding: 1rem;
}

.login-card {
  background: var(--glass-bg);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--glass-border);
  border-radius: 20px;
  padding: 2.5rem;
  width: 100%;
  max-width: 440px;
  box-shadow: var(--shadow-card), 0 0 60px rgba(129,140,248,0.06);
}

.login-header {
  text-align: center;
  margin-bottom: 2rem;
}

.logo-icon {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  background: linear-gradient(135deg, var(--color-primary-active), var(--color-primary), var(--color-primary-hover));
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 800;
  font-size: 22px;
  box-shadow: 0 4px 16px rgba(99,102,241,0.3);
  margin-bottom: 16px;
}

.login-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-text-primary);
  margin: 0 0 0.25rem;
}

.subtitle {
  color: var(--color-text-secondary);
  font-size: 0.875rem;
  margin: 0;
}

.login-tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
  padding: 0.25rem;
  background: var(--color-bg-base);
  border: 1px solid var(--color-border);
  border-radius: 12px;
}

.login-tabs button {
  border: none;
  border-radius: 9px;
  padding: 0.65rem 0.75rem;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.login-tabs button.active {
  background: var(--color-primary);
  color: white;
  box-shadow: 0 4px 14px rgba(99,102,241,0.22);
}

.qr-section h2 {
  text-align: center;
  font-size: 1rem;
  color: var(--color-text-secondary);
  margin: 0 0 1.5rem;
  font-weight: 400;
}

.qr-box {
  position: relative;
  width: 200px;
  height: 200px;
  margin: 0 auto 1rem;
  border: 2px solid var(--color-border);
  border-radius: 14px;
  overflow: hidden;
  background: white;
  transition: border-color 300ms;
}

.qr-box.scanning {
  border-color: var(--color-primary);
  animation: border-pulse 2s ease-in-out infinite;
}

@keyframes border-pulse {
  0%, 100% { border-color: var(--color-primary); }
  50% { border-color: transparent; }
}

.qr-image {
  width: 100%;
  height: 100%;
  display: block;
}

.qr-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  color: var(--color-text-secondary);
  font-size: 0.875rem;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--color-border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.qr-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(4px);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  color: white;
  font-size: 0.8rem;
  text-align: center;
  padding: 1rem;
  border-radius: 12px;
}

.status-msg {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}

.status-msg.scanned { color: var(--color-primary); }

.status-msg.confirmed { color: var(--color-success); }

.status-msg.expired, .status-msg.failed { color: var(--color-error); }

.refresh-btn {
  background: rgba(255, 255, 255, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: white;
  padding: 0.35rem 0.75rem;
  border-radius: 8px;
  font-size: 0.75rem;
  cursor: pointer;
  margin-top: 0.25rem;
  transition: background 200ms;
}

.refresh-btn:hover { background: rgba(255, 255, 255, 0.25); }

.hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  color: var(--color-text-secondary);
  font-size: 0.8rem;
  text-align: center;
}

.cookie-section h2 {
  text-align: center;
  font-size: 1rem;
  color: var(--color-text-secondary);
  margin: 0 0 1rem;
  font-weight: 400;
}

.cookie-input {
  width: 100%;
  min-height: 128px;
  resize: vertical;
  padding: 0.8rem;
  border-radius: 12px;
  border: 1px solid var(--color-border);
  background: var(--color-bg-base);
  color: var(--color-text-primary);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.78rem;
  line-height: 1.5;
  outline: none;
  transition: all 0.2s;
}

.cookie-input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 4px rgba(129,140,248,0.12);
}

.cookie-input::placeholder {
  color: var(--color-text-disabled);
}

.cookie-submit {
  width: 100%;
  margin: 0.9rem 0 0.8rem;
  padding: 0.75rem;
  border: none;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--color-primary-active), var(--color-primary));
  color: white;
  font-size: 0.92rem;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 6px 18px rgba(99,102,241,0.25);
}

.cookie-submit:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 10px 26px rgba(99,102,241,0.32);
}

.cookie-submit:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.user-section {
  text-align: center;
}

.user-avatar {
  width: 72px;
  height: 72px;
  margin: 0 auto 1rem;
  border-radius: 50%;
  overflow: hidden;
  border: 3px solid var(--color-primary);
  box-shadow: 0 0 20px rgba(129,140,248,0.2);
}

.user-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-active));
  color: white;
  font-size: 1.5rem;
  font-weight: 700;
}

.user-info h3 {
  margin: 0 0 0.5rem;
  color: var(--color-text-primary);
}

.user-info p {
  margin: 0.2rem 0;
  color: var(--color-text-secondary);
  font-size: 0.85rem;
}

.logout-btn {
  margin-top: 1.5rem;
  width: 100%;
  padding: 0.6rem;
  background: transparent;
  border: 1px solid var(--color-error);
  color: var(--color-error);
  border-radius: 10px;
  cursor: pointer;
  font-size: 0.875rem;
  transition: all 0.2s;
}

.logout-btn:hover {
  background: rgba(248, 113, 113, 0.1);
}

.error-msg {
  margin-top: 1rem;
  padding: 0.5rem 0.75rem;
  background: rgba(248, 113, 113, 0.1);
  border: 1px solid rgba(248, 113, 113, 0.3);
  border-radius: 10px;
  color: var(--color-error);
  font-size: 0.8rem;
  text-align: center;
}
</style>
