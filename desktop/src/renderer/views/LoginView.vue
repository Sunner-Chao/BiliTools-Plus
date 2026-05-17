<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <div class="logo">
          <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
            <rect width="48" height="48" rx="12" fill="#FB7299"/>
            <path d="M24 8C15.163 8 8 15.163 8 24s7.163 16 16 16 16-7.163 16-16S32.837 8 24 8zm-4 26.5v-5h8v5h-8zm0-9v-5h8v5h-8z" fill="white"/>
          </svg>
        </div>
        <h1>BiliTools-Plus</h1>
        <p class="subtitle">B站游戏资源抢购工具</p>
      </div>

      <div class="qr-section" v-if="!isLogin">
        <h2>扫码登录</h2>

        <!-- 扫码区域 -->
        <div class="qr-box" :class="{ scanning: qrStatus === 'pending' }">
          <img v-if="qrImage" :src="qrImage" alt="扫码登录" class="qr-image" />
          <div v-else class="qr-placeholder">
            <div class="spinner"></div>
            <span>生成二维码中...</span>
          </div>

          <!-- pending 状态下不显示任何遮罩，保证二维码完整可扫 -->
          <!-- <div v-if="qrStatus === 'pending'" class="scan-hint-overlay">
            <div class="pulse-ring"></div>
            <span>等待扫码...</span>
          </div> -->

          <!-- 状态遮罩 — 仅在需要确认/结果时覆盖 -->
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

      <!-- 登录成功状态 -->
      <div v-else class="user-section">
        <div class="user-avatar">
          <img v-if="userInfo.avatar" :src="userInfo.avatar" alt="avatar" />
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

const router = useRouter()
const store = useAppStore()

const qrImage = ref('')
const qrStatus = ref<'idle' | 'pending' | 'scanned' | 'confirmed' | 'expired' | 'failed'>('idle')
const error = ref('')
const pollTimer = ref<ReturnType<typeof setTimeout> | null>(null)
const currentQRKey = ref('')

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
    const res = await fetch('/api/auth/qrcode/generate', { method: 'POST' })
    const data = await res.json()
    if (data.code === 0) {
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
        const res = await fetch(`/api/auth/qrcode/poll?qrcode_key=${qrcode_key}`)
        const data = await res.json()
        const status = data.data?.status

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
    const res = await fetch(`/api/auth/qrcode/confirm?qrcode_key=${qrcode_key}`, { method: 'POST' })
    const data = await res.json()
    if (data.code === 0) {
      const d = data.data
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
  background: var(--bg-primary);
  padding: 1rem;
}

.login-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  padding: 2.5rem;
  width: 100%;
  max-width: 420px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

.login-header {
  text-align: center;
  margin-bottom: 2rem;
}

.logo {
  display: flex;
  justify-content: center;
  margin-bottom: 1rem;
}

.login-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 0.25rem;
}

.subtitle {
  color: var(--text-secondary);
  font-size: 0.875rem;
  margin: 0;
}

.qr-section h2 {
  text-align: center;
  font-size: 1rem;
  color: var(--text-secondary);
  margin: 0 0 1.5rem;
  font-weight: 400;
}

.qr-box {
  position: relative;
  width: 200px;
  height: 200px;
  margin: 0 auto 1rem;
  border: 2px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;
  background: white;
}

.qr-box.scanning {
  border-color: var(--color-primary);
  animation: border-pulse 2s ease-in-out infinite;
}

.scan-hint-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 0.4rem;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.6));
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  color: white;
  font-size: 0.7rem;
  pointer-events: none;
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
  color: var(--text-secondary);
  font-size: 0.875rem;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border-color);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.qr-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  color: white;
  font-size: 0.8rem;
  text-align: center;
  padding: 1rem;
}

.status-msg {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}

.status-msg.pending span { color: #aaa; }

.status-msg.scanned { color: #fb7299; }

.status-msg.confirmed { color: #4ade80; }

.status-msg.expired, .status-msg.failed { color: #f87171; }

.pulse-ring {
  width: 32px;
  height: 32px;
  border: 3px solid #fb7299;
  border-radius: 50%;
  animation: pulse-ring 1.5s ease-out infinite;
}

@keyframes pulse-ring {
  0% { transform: scale(0.8); opacity: 1; }
  100% { transform: scale(1.5); opacity: 0; }
}

.refresh-btn {
  background: rgba(255, 255, 255, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: white;
  padding: 0.35rem 0.75rem;
  border-radius: 6px;
  font-size: 0.75rem;
  cursor: pointer;
  margin-top: 0.25rem;
}

.refresh-btn:hover { background: rgba(255, 255, 255, 0.25); }

.hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  color: var(--text-secondary);
  font-size: 0.8rem;
}

/* 已登录用户信息 */
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
  background: var(--color-primary);
  color: white;
  font-size: 1.5rem;
  font-weight: 700;
}

.user-info h3 {
  margin: 0 0 0.5rem;
  color: var(--text-primary);
}

.user-info p {
  margin: 0.2rem 0;
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.logout-btn {
  margin-top: 1.5rem;
  width: 100%;
  padding: 0.6rem;
  background: transparent;
  border: 1px solid #f87171;
  color: #f87171;
  border-radius: 8px;
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
  border-radius: 8px;
  color: #f87171;
  font-size: 0.8rem;
  text-align: center;
}
</style>