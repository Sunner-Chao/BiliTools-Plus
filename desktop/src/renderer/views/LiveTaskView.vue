<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useAppStore } from '@/stores/useAppStore'
import StatusBadge from '@/components/StatusBadge.vue'
import ToastContainer from '@/components/ToastContainer.vue'
import { Radio, Video, Settings2, Play, Pause, RefreshCw, Monitor, Smartphone, Signal, FolderOpen, Upload, Check } from 'lucide-vue-next'
import { useApi } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'

const api = useApi()
const toast = useToast()
const appStore = useAppStore()

const isLive = ref(false)
const liveStatus = ref<'idle'|'running'|'error'>('idle')

// Live config
const selectedVideo = ref('')
const selectedVideoPath = ref('')
const roomId = ref(appStore.room_id || '')
const qualityMode = ref<'原画'|'高清'|'流畅'>('原画')
const bitrate = ref(4000)
const fps = ref(30)
const resolution = ref('1920x1080')
const rtmpUrl = ref('rtmp://live-push.bilivideo.com/live-bvc/')
const streamKey = ref('')
const scheduledStart = ref('')
const durationSec = ref(0)
const uploadInput = ref<HTMLInputElement | null>(null)

// Upload progress
const uploading = ref(false)
const uploadProgressPercent = ref(0)
const uploadFileName = ref('')
const localFilePath = ref('')
const usingLocalPath = ref(false)

const hasVideo = computed(() => !!selectedVideoPath.value)
const effectiveRoomId = computed(() => (roomId.value || appStore.room_id || '').trim())

const videos = ref<Array<{ id: string; name: string; path: string; size: string }>>([])

const qualityPresets: Record<string, { bitrate: number; fps: number; resolution: string }> = {
  '原画': { bitrate: 8000, fps: 60, resolution: '1920x1080' },
  '高清': { bitrate: 4000, fps: 30, resolution: '1280x720' },
  '流畅': { bitrate: 1500, fps: 25, resolution: '854x480' },
}

const setQuality = (q: string) => {
  qualityMode.value = q as typeof qualityMode.value
  const preset = qualityPresets[q]
  if (preset) { bitrate.value = preset.bitrate; fps.value = preset.fps; resolution.value = preset.resolution }
  toast.success(`已切换至${q}模式`)
}

const fetchStreamKey = async () => {
  if (!effectiveRoomId.value && !appStore.cookies) { toast.warning('请先登录或手动输入直播间号'); return }
  toast.info('正在从B站获取推流信息...')
  try {
    const res = await api.post<any>('/api/live/stream_key', {
      room_id: effectiveRoomId.value,
      cookies: appStore.cookies || '',
      csrf: appStore.bili_jct || '',
    })
    const data = res?.data ?? res
    if (data?.rtmp_url) {
      if (effectiveRoomId.value) appStore.setRoomId(effectiveRoomId.value)
      rtmpUrl.value = data.rtmp_url
      streamKey.value = data.stream_key || ''
      toast.success('推流信息获取成功')
      appendLiveLog('success', `推流地址已更新: ${data.rtmp_url}`)
      if (data.title) appendLiveLog('info', `直播间标题: ${data.title}`)
      if (data.area_name) appendLiveLog('info', `分区: ${data.parent_area_name || ''} / ${data.area_name}`)
    } else {
      toast.error(data?.msg || '获取推流信息失败，请检查登录状态')
    }
  } catch {
    toast.error('获取推流信息失败')
  }
}

const appendLiveLog = (level: string, msg: string) => {
  logs.value.unshift({ time: new Date().toLocaleTimeString(), level, msg })
  if (logs.value.length > 100) logs.value.pop()
}

const liveStats = ref({
  duration: '00:00:00',
  bitrate: 0,
  fps: 0,
  viewers: 0,
  likes: 0,
})

let statsInterval: ReturnType<typeof setInterval> | null = null
let logsInterval: ReturnType<typeof setInterval> | null = null

const startLive = async () => {
  if (!selectedVideoPath.value) { toast.warning('请先选择一个视频'); return }
  if (!effectiveRoomId.value && !appStore.cookies) { toast.warning('请先登录或手动输入直播间号'); return }
  liveStatus.value = 'running'
  toast.success('正在启动直播推流...')

  // 质量映射：前端显示名 → 后端参数值
  const qualityMap: Record<string, string> = { '原画': '高', '高清': '中', '流畅': '低' }
  const biliQuality = qualityMap[qualityMode.value] || '中'

  try {
    const res = await api.post<any>('/api/live/start', {
      room_id: effectiveRoomId.value,
      video_file: selectedVideoPath.value,
      rtmp_url: rtmpUrl.value,
      stream_key: streamKey.value,
      quality: biliQuality,
      cookies: appStore.cookies || '',
      csrf: appStore.bili_jct || '',
      csrf_token: appStore.bili_jct || '',
      scheduled_start: scheduledStart.value,
      duration_sec: durationSec.value,
    })
    const status = res?.data?.status ?? res?.status
    if (status === 'started' || status === 'scheduled') {
      if (res?.data?.room_id) appStore.setRoomId(String(res.data.room_id))
      isLive.value = true
      liveStatus.value = 'running'
      toast.success(status === 'scheduled' ? '定时推流已创建' : '直播推流已启动')
      startStatsPolling()
      startLogsPolling()
    } else {
      toast.error(res?.msg || '启动失败')
      liveStatus.value = 'error'
    }
  } catch {
    toast.error('启动失败，请检查推流配置')
    liveStatus.value = 'error'
  }
}

const uploadVideo = (event: Event) => {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return

  uploading.value = true
  uploadProgressPercent.value = 0
  uploadFileName.value = file.name

  const form = new FormData()
  form.append('file', file)

  const xhr = new XMLHttpRequest()
  xhr.open('POST', `${appStore.apiBase}/api/live/videos/upload`)

  xhr.upload.onprogress = (e) => {
    if (e.lengthComputable) {
      uploadProgressPercent.value = Math.round((e.loaded / e.total) * 100)
    }
  }

  xhr.onload = async () => {
    uploading.value = false
    try {
      const body = JSON.parse(xhr.responseText)
      if (body.code === 0) {
      selectedVideo.value = body.data.name
      selectedVideoPath.value = body.data.path
      localFilePath.value = body.data.path
        usingLocalPath.value = false
        toast.success('视频已导入')
        await loadVideos()
      } else {
        toast.error(body.msg || '视频导入失败')
      }
    } catch {
      toast.error('视频导入失败')
    }
  }

  xhr.onerror = () => {
    uploading.value = false
    toast.error('上传失败，请检查网络连接')
  }

  xhr.send(form)
}

const useLocalPath = async () => {
  const path = localFilePath.value.trim()
  if (!path) { toast.warning('请输入视频文件路径'); return }

  // Verify the path exists via backend
  const res = await api.post<any>('/api/live/videos/local', { path })
  if (res?.success || res?.code === 0) {
    selectedVideo.value = res.data?.name || path.split(/[/\\]/).pop() || path
    selectedVideoPath.value = res.data?.path || path
    usingLocalPath.value = true
    uploadProgressPercent.value = 100
    toast.success('本地路径已设置，无需复制文件')
    await loadVideos()
  } else {
    toast.error(res?.msg || '文件不存在或无法访问')
  }
}

const setScheduledAfter = (seconds: number) => {
  const date = new Date(Date.now() + seconds * 1000)
  scheduledStart.value = date.toISOString().slice(0, 16)
  toast.info(`已设置 ${seconds < 60 ? `${seconds}秒` : `${Math.floor(seconds / 60)}分钟`} 后开始`)
}

const loadVideos = async () => {
  const res = await api.get<any>('/api/live/videos')
  if (res?.data && Array.isArray(res.data)) {
    videos.value = res.data
    if (res.data.length > 0 && !selectedVideoPath.value) {
      selectedVideo.value = res.data[0].name
      selectedVideoPath.value = res.data[0].path
    }
  }
}

const stopLive = async () => {
  toast.warning('正在停止推流...')
  try {
    await api.post('/api/live/stop', {
      room_id: effectiveRoomId.value,
      cookies: appStore.cookies || '',
      csrf: appStore.bili_jct || '',
      csrf_token: appStore.bili_jct || '',
    })
  } catch { /* 忽略错误 */ }
  isLive.value = false
  liveStatus.value = 'idle'
  liveStats.value = { duration: '00:00:00', bitrate: 0, fps: 0, viewers: 0, likes: 0 }
  if (statsInterval) { clearInterval(statsInterval); statsInterval = null }
  if (logsInterval) { clearInterval(logsInterval); logsInterval = null }
  toast.warning('直播推流已停止')
}

const startStatsPolling = () => {
  statsInterval = setInterval(async () => {
    try {
      const res = await api.get<any>('/api/live/status')
      const data = res?.data ?? res
      if (data) {
        const dur = data.duration || 0
        const h = String(Math.floor(dur / 3600)).padStart(2, '0')
        const m = String(Math.floor((dur % 3600) / 60)).padStart(2, '0')
        const s = String(dur % 60).padStart(2, '0')
        liveStats.value.duration = `${h}:${m}:${s}`
        liveStats.value.bitrate = bitrate.value
        liveStats.value.fps = fps.value
        if (!data.is_living) {
          // Stream ended
          isLive.value = false
          liveStatus.value = 'idle'
          if (statsInterval) { clearInterval(statsInterval); statsInterval = null }
          if (logsInterval) { clearInterval(logsInterval); logsInterval = null }
          toast.warning('直播已结束')
        }
      }
    } catch { /* ignore */ }
  }, 2000)
}

const startLogsPolling = () => {
  logsInterval = setInterval(async () => {
    try {
      const res = await api.get<any>('/api/live/ffmpeg_logs?limit=20')
      if (res?.data && Array.isArray(res.data)) {
        const newLogs = res.data.map((l: any) => ({
          time: l.time || new Date().toLocaleTimeString(),
          level: l.level || 'info',
          msg: l.msg || '',
        }))
        if (newLogs.length) logs.value = newLogs
      }
    } catch { /* 忽略轮询错误 */ }
  }, 3000)
}

const logs = ref<Array<{ time: string; level: string; msg: string }>>([
  { time: new Date().toLocaleTimeString(), level: 'info', msg: '推流服务就绪，请选择视频开始直播' },
])

onMounted(async () => {
  roomId.value = appStore.room_id || roomId.value
  // 获取视频列表
  try {
    await loadVideos()
  } catch { /* 忽略 */ }

  // 获取推流状态
  try {
    const st = await api.get<any>('/api/live/status')
    if (st?.is_living) {
      isLive.value = true; liveStatus.value = 'running'
      startStatsPolling()
      startLogsPolling()
    }
  } catch { /* 忽略 */ }
})

watch(() => appStore.room_id, (next) => {
  if (next && !roomId.value) roomId.value = next
})

onUnmounted(() => {
  if (statsInterval) clearInterval(statsInterval)
  if (logsInterval) clearInterval(logsInterval)
})

const selectVideo = (video: typeof videos.value[0]) => {
  selectedVideo.value = video.name
  selectedVideoPath.value = video.path
  localFilePath.value = video.path
  usingLocalPath.value = false
  toast.info(`已选择: ${video.name}`)
}

const levelColors: Record<string, string> = {
  info: 'text-[var(--color-text-secondary)]',
  success: 'text-[var(--color-success)]',
  error: 'text-[var(--color-error)]',
  warn: 'text-[var(--color-warning)]',
  warning: 'text-[var(--color-warning)]',
}
</script>

<template>
  <div class="p-6 space-y-6 main-bg min-h-full">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <div class="h-1 w-12 bg-gradient-to-r from-[var(--color-primary)] to-[var(--color-primary-hover)] rounded-full mb-3" />
        <h1 class="text-2xl font-bold text-[var(--color-text-primary)]">直播推流</h1>
        <p class="text-sm text-[var(--color-text-secondary)] mt-0.5">自动化 · 多平台 · 高画质推流</p>
      </div>
      <div class="flex items-center gap-3">
        <StatusBadge :status="isLive ? 'running' : 'idle'" :pulse="isLive">
          {{ isLive ? '直播中' : '未开播' }}
        </StatusBadge>
        <div v-if="isLive" class="flex items-center gap-1 text-xs text-[var(--color-error)]">
          <span class="inline-block w-2 h-2 rounded-full bg-red-500 animate-pulse" />
          LIVE
        </div>
      </div>
    </div>

    <!-- Live Stats (when running) -->
    <div v-if="isLive" class="grid grid-cols-2 lg:grid-cols-5 gap-4 animate-slide-up">
      <div class="stat-card p-4">
        <div class="text-[10px] text-[var(--color-text-disabled)] uppercase tracking-wider mb-1">直播时长</div>
        <div class="text-lg font-bold text-[var(--color-text-primary)] font-mono">{{ liveStats.duration }}</div>
      </div>
      <div class="stat-card p-4">
        <div class="text-[10px] text-[var(--color-text-disabled)] uppercase tracking-wider mb-1">观看人数</div>
        <div class="text-lg font-bold text-[var(--color-info)]">{{ liveStats.viewers }}</div>
      </div>
      <div class="stat-card p-4">
        <div class="text-[10px] text-[var(--color-text-disabled)] uppercase tracking-wider mb-1">点赞数</div>
        <div class="text-lg font-bold text-[var(--color-error)]">{{ liveStats.likes }}</div>
      </div>
      <div class="stat-card p-4">
        <div class="text-[10px] text-[var(--color-text-disabled)] uppercase tracking-wider mb-1">码率</div>
        <div class="text-lg font-bold text-[var(--color-warning)]">{{ liveStats.bitrate }} kbps</div>
      </div>
      <div class="stat-card p-4">
        <div class="text-[10px] text-[var(--color-text-disabled)] uppercase tracking-wider mb-1">帧率</div>
        <div class="text-lg font-bold text-[var(--color-primary)]">{{ liveStats.fps }} fps</div>
      </div>
    </div>

    <!-- Video Selector + Quality -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Video List -->
      <div class="lg:col-span-2 glass-card p-5">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-sm font-semibold text-[var(--color-text-primary)]">选择视频</h3>
          <div class="flex items-center gap-2">
            <input ref="uploadInput" type="file" accept="video/*" class="hidden" @change="uploadVideo" />
            <button @click="uploadInput?.click()" :disabled="uploading" class="btn-ghost text-[10px] px-3 py-1 flex items-center gap-1">
              <Upload :size="12" /> 浏览文件
            </button>
            <span class="text-[10px] text-[var(--color-text-disabled)]">{{ videos.length }} 个视频</span>
          </div>
        </div>

        <!-- Upload Progress Bar -->
        <div v-if="uploading" class="mb-4 animate-slide-up">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs text-[var(--color-text-secondary)] truncate max-w-60">{{ uploadFileName }}</span>
            <span class="text-xs font-mono text-[var(--color-primary)]">{{ uploadProgressPercent }}%</span>
          </div>
          <div class="h-2 rounded-full bg-white/5 overflow-hidden">
            <div class="h-full bg-gradient-to-r from-[var(--color-primary)] to-[var(--color-primary-hover)] rounded-full transition-all duration-300"
              :style="{ width: `${uploadProgressPercent}%` }" />
          </div>
        </div>

        <!-- Local Path Input -->
        <div class="mb-4 flex gap-2">
          <div class="flex-1 relative">
            <FolderOpen :size="14" class="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-disabled)]" />
            <input v-model="localFilePath" type="text" placeholder="或输入本地视频路径 (如 D:\videos\demo.mp4)" class="input-field w-full pl-9 text-xs" @keyup.enter="useLocalPath" />
          </div>
          <button @click="useLocalPath" :disabled="!localFilePath.trim()" class="btn-ghost text-xs px-3 py-1.5 flex items-center gap-1 shrink-0">
            <Check :size="14" /> 使用
          </button>
        </div>
        <div class="space-y-2">
          <div v-for="video in videos" :key="video.id"
            @click="selectVideo(video)"
            :class="[
              'flex items-center gap-3 px-4 py-3 rounded-xl border transition-all cursor-pointer',
              selectedVideo === video.name
                ? 'border-[var(--color-primary)]/40 bg-[var(--color-primary)]/5'
                : 'border-white/5 bg-[var(--color-bg-base)]/50 hover:border-white/10'
            ]">
            <div :class="[
              'w-8 h-8 rounded-lg flex items-center justify-center shrink-0 transition-all',
              selectedVideo === video.name ? 'bg-[var(--color-primary)]/20' : 'bg-white/5'
            ]">
              <Video :size="14" :class="selectedVideo === video.name ? 'text-[var(--color-primary)]' : 'text-[var(--color-text-disabled)]'" />
            </div>
            <div class="flex-1 min-w-0">
              <div class="text-xs font-medium text-[var(--color-text-primary)] truncate">{{ video.name }}</div>
              <div class="text-[10px] text-[var(--color-text-disabled)] mt-0.5">{{ video.size }}</div>
            </div>
            <div v-if="selectedVideo === video.name && !usingLocalPath" class="w-2 h-2 rounded-full bg-[var(--color-primary)] shrink-0" />
            <span v-if="selectedVideo === video.name && usingLocalPath" class="text-[10px] text-[var(--color-primary)] shrink-0">本地</span>
          </div>
        </div>
      </div>

      <!-- Quality Settings -->
      <div class="glass-card p-5">
        <div class="flex items-center gap-2 mb-4">
          <Settings2 :size="14" class="text-[var(--color-primary)]" />
          <h3 class="text-sm font-semibold text-[var(--color-text-primary)]">画质设置</h3>
        </div>
        <div class="flex gap-1.5 mb-4">
          <button v-for="q in (['原画','高清','流畅'] as const)" :key="q"
            @click="setQuality(q)"
            :class="[
              'flex-1 py-2 rounded-lg text-xs font-medium transition-all',
              qualityMode === q
                ? 'bg-[var(--color-primary)] text-white shadow-md'
                : 'bg-white/5 text-[var(--color-text-secondary)] hover:bg-white/10'
            ]">
            {{ q }}
          </button>
        </div>
        <div class="space-y-4">
          <div>
            <label class="text-[10px] text-[var(--color-text-disabled)] mb-1.5 block">码率 (kbps)</label>
            <input v-model.number="bitrate" type="number" class="input-field w-full text-sm" />
          </div>
          <div>
            <label class="text-[10px] text-[var(--color-text-disabled)] mb-1.5 block">帧率 (fps)</label>
            <input v-model.number="fps" type="number" class="input-field w-full text-sm" />
          </div>
          <div>
            <label class="text-[10px] text-[var(--color-text-disabled)] mb-1.5 block">分辨率</label>
            <select v-model="resolution" class="input-field w-full text-sm">
              <option>1920x1080</option>
              <option>1280x720</option>
              <option>854x480</option>
            </select>
          </div>
          <div>
            <label class="text-[10px] text-[var(--color-text-disabled)] mb-1.5 block">直播间号</label>
            <input v-model="roomId" type="text" class="input-field w-full text-sm" placeholder="登录后自动填充，也可手动输入" />
          </div>
          <div>
            <label class="text-[10px] text-[var(--color-text-disabled)] mb-1.5 block">RTMP 地址</label>
            <input v-model="rtmpUrl" type="text" class="input-field w-full text-xs" />
          </div>
          <div>
            <label class="text-[10px] text-[var(--color-text-disabled)] mb-1.5 block">推流密钥</label>
            <input v-model="streamKey" type="password" class="input-field w-full text-xs" />
          </div>
          <button @click="fetchStreamKey" class="btn-ghost w-full flex items-center justify-center gap-1.5 text-sm">
            <RefreshCw :size="14" /> 获取推流信息
          </button>
          <div>
            <label class="text-[10px] text-[var(--color-text-disabled)] mb-1.5 block">定时开始</label>
            <input v-model="scheduledStart" type="datetime-local" class="input-field w-full text-xs" />
            <div class="flex gap-1.5 mt-2">
              <button @click="setScheduledAfter(10)" class="btn-ghost text-[10px] px-2 py-1">10秒后</button>
              <button @click="setScheduledAfter(60)" class="btn-ghost text-[10px] px-2 py-1">1分钟后</button>
              <button @click="setScheduledAfter(300)" class="btn-ghost text-[10px] px-2 py-1">5分钟后</button>
            </div>
          </div>
          <div>
            <label class="text-[10px] text-[var(--color-text-disabled)] mb-1.5 block">自动关播（秒）</label>
            <input v-model.number="durationSec" type="number" min="0" class="input-field w-full text-sm" />
          </div>
          <button @click="isLive ? stopLive() : startLive()"
            :class="isLive ? 'btn-ghost w-full flex items-center justify-center gap-2 text-[var(--color-error)]' : 'btn-primary w-full flex items-center justify-center gap-2'">
            <Pause v-if="isLive" :size="14" /> <Play v-else :size="14" />
            {{ isLive ? '停止推流' : '开始推流' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Connection Info -->
    <div class="glass-card p-5">
      <h3 class="text-sm font-semibold text-[var(--color-text-primary)] mb-4">推流信息</h3>
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div class="bg-[var(--color-bg-base)] rounded-xl p-4 border border-white/5">
          <div class="flex items-center gap-2 mb-2">
            <Signal :size="12" class="text-[var(--color-success)]" />
            <span class="text-[10px] text-[var(--color-text-disabled)]">连接状态</span>
          </div>
          <div :class="['text-sm font-medium', isLive ? 'text-[var(--color-success)]' : 'text-[var(--color-text-disabled)]']">
            {{ isLive ? '已连接' : '未连接' }}
          </div>
        </div>
        <div class="bg-[var(--color-bg-base)] rounded-xl p-4 border border-white/5">
          <div class="flex items-center gap-2 mb-2">
            <Monitor :size="12" class="text-[var(--color-info)]" />
            <span class="text-[10px] text-[var(--color-text-disabled)]">分辨率</span>
          </div>
          <div class="text-sm font-medium text-[var(--color-text-primary)]">{{ resolution }}</div>
        </div>
        <div class="bg-[var(--color-bg-base)] rounded-xl p-4 border border-white/5">
          <div class="flex items-center gap-2 mb-2">
            <Signal :size="12" class="text-[var(--color-warning)]" />
            <span class="text-[10px] text-[var(--color-text-disabled)]">码率</span>
          </div>
          <div class="text-sm font-medium text-[var(--color-text-primary)]">{{ bitrate }} kbps</div>
        </div>
        <div class="bg-[var(--color-bg-base)] rounded-xl p-4 border border-white/5">
          <div class="flex items-center gap-2 mb-2">
            <Smartphone :size="12" class="text-[var(--color-primary)]" />
            <span class="text-[10px] text-[var(--color-text-disabled)]">帧率</span>
          </div>
          <div class="text-sm font-medium text-[var(--color-text-primary)]">{{ fps }} fps</div>
        </div>
      </div>
    </div>

    <!-- Live Log -->
    <div class="glass-card p-5">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-sm font-semibold text-[var(--color-text-primary)]">推流日志</h3>
        <button @click="logs = []" class="btn-ghost text-[10px] px-3 py-1">清空</button>
      </div>
      <div class="bg-[var(--color-bg-base)] rounded-xl p-4 h-44 overflow-y-auto font-mono text-xs space-y-1">
        <div v-for="(log, i) in logs" :key="i" :class="['flex gap-3', levelColors[log.level] ?? 'text-[var(--color-text-secondary)]']">
          <span class="text-[var(--color-text-disabled)] shrink-0">{{ log.time }}</span>
          <span>[{{ log.level.toUpperCase() }}]</span>
          <span class="text-[var(--color-text-primary)]">{{ log.msg }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
