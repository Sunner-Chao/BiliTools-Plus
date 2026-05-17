<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAppStore } from '@/stores/useAppStore'
import StatusBadge from '@/components/StatusBadge.vue'
import { useApi } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { MessageSquare, Gift, Radio, Users, Play, RefreshCw, Zap, Clock, Heart, Share2, Eye } from 'lucide-vue-next'

const app = useAppStore()
const api = useApi()
const toast = useToast()

// ── State ──
const isRunning = ref(false)
const audienceCount = ref(1)
const repeatCount = ref(1)
const giftName = ref('牛蛙')
const customDanmaku = ref('')

const logs = ref<Array<{ time: string; level: 'info' | 'success' | 'error' | 'warn'; msg: string }>>([])

const appendLog = (level: typeof logs.value[0]['level'], msg: string) => {
  const now = new Date()
  const time = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`
  logs.value.unshift({ time, level, msg })
  if (logs.value.length > 200) logs.value.pop()
}

// ── Danmaku ──
const sendDanmaku = async () => {
  if (!app.room_id) { toast.warning('未获取到房间号，请先登录'); return }
  appendLog('info', `正在发送弹幕到房间 ${app.room_id}...`)
  try {
    const res = await api.post<any>('/api/daily/danmaku', {
      room_id: app.room_id,
      cookies: app.cookies,
      msg: customDanmaku.value || undefined,
    })
    if (res?.success) {
      appendLog('success', '弹幕发送成功')
      toast.success('弹幕发送成功')
    } else {
      const errMsg = res?.payload?.message || res?.payload?.msg || '未知错误'
      appendLog('error', `弹幕发送失败: ${errMsg}`)
      toast.error('弹幕发送失败')
    }
  } catch (e: any) {
    appendLog('error', `弹幕请求异常: ${e.message || e}`)
    toast.error('弹幕发送异常')
  }
}

// ── Gift ──
const sendGift = async () => {
  if (!app.room_id) { toast.warning('未获取到房间号，请先登录'); return }
  appendLog('info', `正在赠送礼物到房间 ${app.room_id}...`)
  try {
    const res = await api.post<any>('/api/daily/gift', {
      room_id: app.room_id,
      cookies: app.cookies,
    })
    if (res?.success) {
      appendLog('success', '赠送礼物成功')
      toast.success('赠送礼物成功')
    } else {
      const errMsg = res?.payload?.message || res?.payload?.msg || '未知错误'
      appendLog('error', `赠送礼物失败: ${errMsg}`)
      toast.error('赠送礼物失败')
    }
  } catch (e: any) {
    appendLog('error', `赠送礼物请求异常: ${e.message || e}`)
    toast.error('赠送礼物异常')
  }
}

// ── Watch heartbeat ──
const sendWatch = async () => {
  if (!app.room_id) { toast.warning('未获取到房间号，请先登录'); return }
  appendLog('info', `正在发送看播心跳到房间 ${app.room_id}...`)
  try {
    const res = await api.post<any>('/api/daily/watch', {
      room_id: app.room_id,
      cookies: app.cookies,
    })
    if (res?.success) {
      appendLog('success', '看播心跳发送成功')
      toast.success('看播签到成功')
    } else {
      const errMsg = res?.payload?.message || res?.payload?.msg || '未知错误'
      appendLog('error', `看播心跳失败: ${errMsg}`)
      toast.error('看播心跳失败')
    }
  } catch (e: any) {
    appendLog('error', `看播请求异常: ${e.message || e}`)
    toast.error('看播请求异常')
  }
}

// ── Like live room ──
const sendLike = async () => {
  if (!app.room_id) { toast.warning('未获取到房间号，请先登录'); return }
  appendLog('info', `正在点赞房间 ${app.room_id}...`)
  try {
    const res = await api.post<any>('/api/daily/like', {
      room_id: app.room_id,
      cookies: app.cookies,
    })
    if (res?.success) {
      appendLog('success', '点赞成功')
      toast.success('直播间点赞成功')
    } else {
      const errMsg = res?.payload?.message || res?.payload?.msg || '未知错误'
      appendLog('error', `点赞失败: ${errMsg}`)
      toast.error('点赞失败')
    }
  } catch (e: any) {
    appendLog('error', `点赞请求异常: ${e.message || e}`)
    toast.error('点赞异常')
  }
}

// ── Share live room ──
const sendShare = async () => {
  if (!app.room_id) { toast.warning('未获取到房间号，请先登录'); return }
  appendLog('info', `正在分享房间 ${app.room_id}...`)
  try {
    const res = await api.post<any>('/api/daily/share', {
      room_id: app.room_id,
      cookies: app.cookies,
    })
    if (res?.success) {
      appendLog('success', '分享成功')
      toast.success('直播间分享成功')
    } else {
      const errMsg = res?.payload?.message || res?.payload?.msg || '未知错误'
      appendLog('error', `分享失败: ${errMsg}`)
      toast.error('分享失败')
    }
  } catch (e: any) {
    appendLog('error', `分享请求异常: ${e.message || e}`)
    toast.error('分享异常')
  }
}

// ── Auto daily task ──
const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

const startAutoDaily = async () => {
  if (!app.room_id) { toast.warning('未获取到房间号，请先登录'); return }
  isRunning.value = true
  appendLog('info', `开始自动每日任务，重复 ${repeatCount.value} 次`)
  for (let round = 1; round <= repeatCount.value; round++) {
    if (!isRunning.value) break
    appendLog('info', `--- 第 ${round}/${repeatCount.value} 轮 ---`)
    // 1. 发弹幕
    await sendDanmaku()
    if (!isRunning.value) break
    await sleep(2000)
    // 2. 看播心跳
    await sendWatch()
    if (!isRunning.value) break
    await sleep(2000)
    // 3. 点赞
    await sendLike()
    if (!isRunning.value) break
    await sleep(1500)
    // 4. 分享
    await sendShare()
    if (!isRunning.value) break
    await sleep(1500)
    // 5. 送礼
    await sendGift()
    if (!isRunning.value) break
    if (round < repeatCount.value) await sleep(3000)
  }
  isRunning.value = false
  appendLog('info', '自动每日任务完成')
  toast.success('每日任务已完成')
}

const stopAutoDaily = () => {
  isRunning.value = false
  appendLog('warn', '手动停止自动任务')
  toast.warning('已停止自动任务')
}

// ── Live room entry ──
const enterLiveRoom = () => {
  if (!app.room_id) { toast.warning('未获取到房间号'); return }
  const url = `https://live.bilibili.com/${app.room_id}`
  window.open(url, '_blank')
  appendLog('info', `已打开直播间: ${url}`)
}

const logColorMap: Record<string, string> = {
  info: 'text-[var(--color-text-secondary)]',
  success: 'text-[var(--color-success)]',
  error: 'text-[var(--color-error)]',
  warn: 'text-[var(--color-warning)]',
}
</script>

<template>
  <div class="p-6 space-y-6 main-bg min-h-full">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <div class="h-1 w-12 bg-gradient-to-r from-[var(--color-primary)] to-[var(--color-primary-hover)] rounded-full mb-3" />
        <h1 class="text-2xl font-bold text-[var(--color-text-primary)]">每日任务</h1>
        <p class="text-sm text-[var(--color-text-secondary)] mt-0.5">弹幕 · 送礼 · 直播间互动</p>
      </div>
      <StatusBadge :status="isRunning ? 'running' : 'idle'" :pulse="isRunning">
        {{ isRunning ? '运行中' : '空闲' }}
      </StatusBadge>
    </div>

    <!-- User Info Card -->
    <div class="glass-card p-5">
      <div class="flex items-center gap-4">
        <img v-if="app.avatar" :src="app.avatar" alt="avatar" class="w-14 h-14 rounded-full ring-2 ring-[var(--color-primary)]/30" />
        <div v-else class="w-14 h-14 rounded-full bg-gradient-to-br from-[var(--color-primary)] to-purple-600 flex items-center justify-center text-white text-xl font-bold">
          {{ app.username?.charAt(0)?.toUpperCase() ?? '?' }}
        </div>
        <div class="flex-1">
          <h3 class="text-base font-semibold text-[var(--color-text-primary)]">{{ app.username || '未登录' }}</h3>
          <div class="flex items-center gap-4 mt-1 text-xs text-[var(--color-text-secondary)]">
            <span v-if="app.uid">UID: {{ app.uid }}</span>
            <span v-if="app.room_id">房间号: {{ app.room_id }}</span>
            <span v-if="app.level">Lv.{{ app.level }}</span>
          </div>
        </div>
        <button @click="enterLiveRoom" class="btn-ghost flex items-center gap-1.5 text-sm">
          <Radio :size="14" /> 进入直播间
        </button>
      </div>
    </div>

    <!-- Task Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Config Panel -->
      <div class="glass-card p-5">
        <h3 class="text-sm font-semibold text-[var(--color-text-primary)] mb-4">任务配置</h3>
        <div class="space-y-4">
          <div>
            <label class="text-[11px] text-[var(--color-text-disabled)] mb-1.5 block">房间号</label>
            <input :value="app.room_id || '未获取'" readonly class="input-field w-full text-sm opacity-70" />
          </div>
          <div>
            <label class="text-[11px] text-[var(--color-text-disabled)] mb-1.5 block">重复次数</label>
            <input v-model.number="repeatCount" type="number" min="1" max="100" class="input-field w-full" />
          </div>
          <div>
            <label class="text-[11px] text-[var(--color-text-disabled)] mb-1.5 block">自定义弹幕（留空随机）</label>
            <input v-model="customDanmaku" type="text" placeholder="留空则发送随机弹幕" class="input-field w-full text-sm" />
          </div>
          <div class="flex gap-2 pt-2">
            <button @click="startAutoDaily" :disabled="isRunning" class="btn-primary flex-1 flex items-center justify-center gap-1.5">
              <Play :size="14" /> 开始任务
            </button>
            <button @click="stopAutoDaily" :disabled="!isRunning" class="btn-ghost flex-1 flex items-center justify-center gap-1.5">
              停止
            </button>
          </div>
        </div>
      </div>

      <!-- Quick Actions -->
      <div class="lg:col-span-2 glass-card p-5">
        <h3 class="text-sm font-semibold text-[var(--color-text-primary)] mb-4">快速操作</h3>
        <div class="grid grid-cols-2 lg:grid-cols-3 gap-4">
          <!-- Danmaku Card -->
          <div class="bg-[var(--color-bg-base)]/50 rounded-xl p-5 border border-white/5 hover:border-[var(--color-primary)]/20 transition-all">
            <div class="flex items-center gap-3 mb-3">
              <div class="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center">
                <MessageSquare :size="18" class="text-blue-400" />
              </div>
              <div>
                <h4 class="text-sm font-medium text-[var(--color-text-primary)]">发送弹幕</h4>
                <p class="text-[10px] text-[var(--color-text-disabled)]">向直播间发送随机/自定义弹幕</p>
              </div>
            </div>
            <button @click="sendDanmaku" class="btn-primary w-full flex items-center justify-center gap-1.5 text-sm">
              <Zap :size="14" /> 发送弹幕
            </button>
          </div>

          <!-- Gift Card -->
          <div class="bg-[var(--color-bg-base)]/50 rounded-xl p-5 border border-white/5 hover:border-[var(--color-primary)]/20 transition-all">
            <div class="flex items-center gap-3 mb-3">
              <div class="w-10 h-10 rounded-xl bg-pink-500/10 flex items-center justify-center">
                <Gift :size="18" class="text-pink-400" />
              </div>
              <div>
                <h4 class="text-sm font-medium text-[var(--color-text-primary)]">赠送礼物</h4>
                <p class="text-[10px] text-[var(--color-text-disabled)]">向主播赠送 {{ giftName }}</p>
              </div>
            </div>
            <button @click="sendGift" class="btn-primary w-full flex items-center justify-center gap-1.5 text-sm">
              <Gift :size="14" /> 赠送{{ giftName }}
            </button>
          </div>

          <!-- Watch Card -->
          <div class="bg-[var(--color-bg-base)]/50 rounded-xl p-5 border border-white/5 hover:border-[var(--color-primary)]/20 transition-all">
            <div class="flex items-center gap-3 mb-3">
              <div class="w-10 h-10 rounded-xl bg-cyan-500/10 flex items-center justify-center">
                <Eye :size="18" class="text-cyan-400" />
              </div>
              <div>
                <h4 class="text-sm font-medium text-[var(--color-text-primary)]">看播签到</h4>
                <p class="text-[10px] text-[var(--color-text-disabled)]">发送看播心跳完成签到</p>
              </div>
            </div>
            <button @click="sendWatch" class="btn-primary w-full flex items-center justify-center gap-1.5 text-sm">
              <Eye :size="14" /> 看播签到
            </button>
          </div>

          <!-- Like Card -->
          <div class="bg-[var(--color-bg-base)]/50 rounded-xl p-5 border border-white/5 hover:border-[var(--color-primary)]/20 transition-all">
            <div class="flex items-center gap-3 mb-3">
              <div class="w-10 h-10 rounded-xl bg-rose-500/10 flex items-center justify-center">
                <Heart :size="18" class="text-rose-400" />
              </div>
              <div>
                <h4 class="text-sm font-medium text-[var(--color-text-primary)]">直播间点赞</h4>
                <p class="text-[10px] text-[var(--color-text-disabled)]">为直播间点赞加人气</p>
              </div>
            </div>
            <button @click="sendLike" class="btn-primary w-full flex items-center justify-center gap-1.5 text-sm">
              <Heart :size="14" /> 点赞
            </button>
          </div>

          <!-- Share Card -->
          <div class="bg-[var(--color-bg-base)]/50 rounded-xl p-5 border border-white/5 hover:border-[var(--color-primary)]/20 transition-all">
            <div class="flex items-center gap-3 mb-3">
              <div class="w-10 h-10 rounded-xl bg-violet-500/10 flex items-center justify-center">
                <Share2 :size="18" class="text-violet-400" />
              </div>
              <div>
                <h4 class="text-sm font-medium text-[var(--color-text-primary)]">分享直播间</h4>
                <p class="text-[10px] text-[var(--color-text-disabled)]">分享直播间完成任务</p>
              </div>
            </div>
            <button @click="sendShare" class="btn-primary w-full flex items-center justify-center gap-1.5 text-sm">
              <Share2 :size="14" /> 分享
            </button>
          </div>

          <!-- Execution Status -->
          <div class="bg-[var(--color-bg-base)]/50 rounded-xl p-5 border border-white/5">
            <div class="flex items-center gap-3 mb-3">
              <div class="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center">
                <Clock :size="18" class="text-amber-400" />
              </div>
              <div>
                <h4 class="text-sm font-medium text-[var(--color-text-primary)]">执行状态</h4>
                <p class="text-[10px] text-[var(--color-text-disabled)]">当前任务运行状态</p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <span :class="['inline-block w-2 h-2 rounded-full', isRunning ? 'bg-green-500 animate-pulse' : 'bg-gray-500']" />
              <span class="text-xs text-[var(--color-text-secondary)]">{{ isRunning ? '任务运行中...' : '空闲' }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Live Log -->
    <div class="glass-card p-5">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-sm font-semibold text-[var(--color-text-primary)]">任务日志</h3>
        <button @click="logs = []" class="btn-ghost text-[10px] px-3 py-1">清空</button>
      </div>
      <div class="bg-[var(--color-bg-base)] rounded-xl p-4 h-52 overflow-y-auto font-mono text-xs space-y-1">
        <div v-if="logs.length === 0" class="text-center py-8 text-[var(--color-text-disabled)]">
          暂无日志，点击上方按钮开始任务
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
