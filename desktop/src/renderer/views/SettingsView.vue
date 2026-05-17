<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAppStore } from '@/stores/useAppStore'
import { useToast } from '@/composables/useToast'
import { useNtpSync } from '@/composables/useNtpSync'
import { Settings, Globe, Bell, Clock, Shield, Palette, Save, RotateCcw, CheckCircle } from 'lucide-vue-next'

const app = useAppStore()
const toast = useToast()
const { offset: ntpOffset, start: startNtpSync } = useNtpSync()

// Server settings
const serverUrl = ref(app.server.url)

// Notification settings
const enableSound = ref(true)
const enableDesktopNotification = ref(true)
const logAutoScroll = ref(true)
const maxLogItems = ref(500)

// NTP settings
const ntpEnabled = ref(true)
const ntpServer = ref('ntp.aliyun.com')
const ntpInterval = ref(30)

// Advanced settings
const requestInterval = ref(500)
const maxRetries = ref(3)
const taskTimeout = ref(30)
const debugMode = ref(false)

// Save status
const saveStatus = ref<'idle'|'saving'|'saved'|'error'>('idle')

const saveSettings = async () => {
  saveStatus.value = 'saving'
  // Apply server URL
  app.setServerUrl(serverUrl.value)
  
  // Simulate save delay
  await new Promise(resolve => setTimeout(resolve, 500))
  saveStatus.value = 'saved'
  toast.success('设置已保存')
  
  setTimeout(() => { saveStatus.value = 'idle' }, 2000)
}

const resetSettings = () => {
  serverUrl.value = 'http://127.0.0.1:8000'
  enableSound.value = true
  enableDesktopNotification.value = true
  logAutoScroll.value = true
  maxLogItems.value = 500
  ntpEnabled.value = true
  ntpServer.value = 'ntp.aliyun.com'
  ntpInterval.value = 30
  requestInterval.value = 500
  maxRetries.value = 3
  taskTimeout.value = 30
  debugMode.value = false
  toast.info('设置已重置为默认值')
}

onMounted(() => {
  startNtpSync()
})
</script>

<template>
  <div class="p-6 space-y-6 main-bg min-h-full">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <div class="h-1 w-12 bg-gradient-to-r from-[var(--color-primary)] to-[var(--color-primary-hover)] rounded-full mb-3" />
        <h1 class="text-2xl font-bold text-[var(--color-text-primary)]">设置</h1>
        <p class="text-sm text-[var(--color-text-secondary)] mt-0.5">个性化配置 · 优化你的工作流</p>
      </div>
      <div class="flex gap-3">
        <button @click="resetSettings" class="btn-ghost flex items-center gap-2">
          <RotateCcw :size="14" />
          重置默认
        </button>
        <button @click="saveSettings" :disabled="saveStatus === 'saving'" 
          :class="[
            'btn-primary flex items-center gap-2',
            saveStatus === 'saved' && '!bg-[var(--color-success)] !shadow-green-500/30'
          ]">
          <CheckCircle v-if="saveStatus === 'saved'" :size="14" />
          <Save v-else :size="14" />
          {{ saveStatus === 'saving' ? '保存中...' : saveStatus === 'saved' ? '已保存' : '保存设置' }}
        </button>
      </div>
    </div>

    <!-- Settings Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      
      <!-- Server Configuration -->
      <div class="glass-card p-6">
        <div class="flex items-center gap-2 mb-5">
          <Globe :size="16" class="text-[var(--color-primary)]" />
          <h2 class="text-sm font-semibold text-[var(--color-text-primary)]">服务器配置</h2>
        </div>
        <div class="space-y-4">
          <div>
            <label class="text-[11px] text-[var(--color-text-disabled)] mb-1.5 block">API 服务器地址</label>
            <input v-model="serverUrl" type="text" class="input-field w-full text-sm" placeholder="http://127.0.0.1:8000" />
            <p class="text-[10px] text-[var(--color-text-disabled)] mt-1.5">FastAPI 后端地址，修改后需重启应用</p>
          </div>
          <div class="bg-[var(--color-bg-base)] rounded-xl p-4 border border-white/5">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <div class="w-2 h-2 rounded-full" :class="app.server.connected ? 'bg-[var(--color-success)]' : 'bg-[var(--color-error)]'" />
                <span class="text-xs text-[var(--color-text-secondary)]">连接状态</span>
              </div>
              <span :class="['text-xs font-medium', app.server.connected ? 'text-[var(--color-success)]' : 'text-[var(--color-error)]']">
                {{ app.server.connected ? '已连接' : '未连接' }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Notification Settings -->
      <div class="glass-card p-6">
        <div class="flex items-center gap-2 mb-5">
          <Bell :size="16" class="text-[var(--color-warning)]" />
          <h2 class="text-sm font-semibold text-[var(--color-text-primary)]">通知设置</h2>
        </div>
        <div class="space-y-4">
          <div class="flex items-center justify-between py-2">
            <div>
              <div class="text-sm text-[var(--color-text-primary)]">声音提醒</div>
              <div class="text-[10px] text-[var(--color-text-disabled)]">任务完成时播放提示音</div>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
              <input v-model="enableSound" type="checkbox" class="sr-only peer" />
              <div class="w-11 h-6 bg-white/10 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[var(--color-primary)]"></div>
            </label>
          </div>
          <div class="flex items-center justify-between py-2">
            <div>
              <div class="text-sm text-[var(--color-text-primary)]">桌面通知</div>
              <div class="text-[10px] text-[var(--color-text-disabled)]">弹出系统级通知</div>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
              <input v-model="enableDesktopNotification" type="checkbox" class="sr-only peer" />
              <div class="w-11 h-6 bg-white/10 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[var(--color-primary)]"></div>
            </label>
          </div>
          <div class="flex items-center justify-between py-2">
            <div>
              <div class="text-sm text-[var(--color-text-primary)]">日志自动滚动</div>
              <div class="text-[10px] text-[var(--color-text-disabled)]">新日志出现时自动滚动到底部</div>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
              <input v-model="logAutoScroll" type="checkbox" class="sr-only peer" />
              <div class="w-11 h-6 bg-white/10 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[var(--color-primary)]"></div>
            </label>
          </div>
          <div>
            <label class="text-[11px] text-[var(--color-text-disabled)] mb-1.5 block">最大日志条数</label>
            <input v-model.number="maxLogItems" type="number" min="100" max="2000" class="input-field w-full text-sm" />
          </div>
        </div>
      </div>

      <!-- NTP Settings -->
      <div class="glass-card p-6">
        <div class="flex items-center gap-2 mb-5">
          <Clock :size="16" class="text-[var(--color-info)]" />
          <h2 class="text-sm font-semibold text-[var(--color-text-primary)]">NTP 时间同步</h2>
        </div>
        <div class="space-y-4">
          <div class="flex items-center justify-between py-2">
            <div>
              <div class="text-sm text-[var(--color-text-primary)]">启用 NTP 同步</div>
              <div class="text-[10px] text-[var(--color-text-disabled)]">与网络时间服务器同步，提高抢购精度</div>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
              <input v-model="ntpEnabled" type="checkbox" class="sr-only peer" />
              <div class="w-11 h-6 bg-white/10 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[var(--color-primary)]"></div>
            </label>
          </div>
          <div>
            <label class="text-[11px] text-[var(--color-text-disabled)] mb-1.5 block">NTP 服务器</label>
            <select v-model="ntpServer" class="input-field w-full text-sm">
              <option value="ntp.aliyun.com">阿里云 (ntp.aliyun.com)</option>
              <option value="ntp.tencent.com">腾讯云 (ntp.tencent.com)</option>
              <option value="cn.ntp.org.cn">国家授时中心 (cn.ntp.org.cn)</option>
              <option value="pool.ntp.org">国际 NTP (pool.ntp.org)</option>
            </select>
          </div>
          <div>
            <label class="text-[11px] text-[var(--color-text-disabled)] mb-1.5 block">同步间隔（秒）</label>
            <input v-model.number="ntpInterval" type="number" min="10" max="300" class="input-field w-full text-sm" />
          </div>
          <div class="bg-[var(--color-bg-base)] rounded-xl p-4 border border-white/5">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <div class="w-2 h-2 rounded-full" :class="Math.abs(ntpOffset) < 100 ? 'bg-[var(--color-success)]' : 'bg-[var(--color-warning)]'" />
                <span class="text-xs text-[var(--color-text-secondary)]">当前偏移</span>
              </div>
              <span :class="['text-xs font-mono font-medium', Math.abs(ntpOffset) < 100 ? 'text-[var(--color-success)]' : 'text-[var(--color-warning)]']">
                {{ ntpOffset ? `${ntpOffset > 0 ? '+' : ''}${ntpOffset}ms` : '同步中...' }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Advanced Settings -->
      <div class="glass-card p-6">
        <div class="flex items-center gap-2 mb-5">
          <Shield :size="16" class="text-[var(--color-error)]" />
          <h2 class="text-sm font-semibold text-[var(--color-text-primary)]">高级设置</h2>
        </div>
        <div class="space-y-4">
          <div>
            <label class="text-[11px] text-[var(--color-text-disabled)] mb-1.5 block">请求间隔（毫秒）</label>
            <input v-model.number="requestInterval" type="number" min="100" max="5000" step="100" class="input-field w-full text-sm" />
            <p class="text-[10px] text-[var(--color-text-disabled)] mt-1">控制 API 请求频率，避免被封禁</p>
          </div>
          <div>
            <label class="text-[11px] text-[var(--color-text-disabled)] mb-1.5 block">最大重试次数</label>
            <input v-model.number="maxRetries" type="number" min="1" max="10" class="input-field w-full text-sm" />
          </div>
          <div>
            <label class="text-[11px] text-[var(--color-text-disabled)] mb-1.5 block">任务超时时间（秒）</label>
            <input v-model.number="taskTimeout" type="number" min="10" max="300" class="input-field w-full text-sm" />
          </div>
          <div class="flex items-center justify-between py-2">
            <div>
              <div class="text-sm text-[var(--color-text-primary)]">调试模式</div>
              <div class="text-[10px] text-[var(--color-text-disabled)]">输出详细日志信息</div>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
              <input v-model="debugMode" type="checkbox" class="sr-only peer" />
              <div class="w-11 h-6 bg-white/10 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[var(--color-primary)]"></div>
            </label>
          </div>
        </div>
      </div>
    </div>

    <!-- About Section -->
    <div class="glass-card p-6">
      <div class="flex items-center gap-2 mb-5">
        <Palette :size="16" class="text-[var(--color-accent)]" />
        <h2 class="text-sm font-semibold text-[var(--color-text-primary)]">关于</h2>
      </div>
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div class="bg-[var(--color-bg-base)] rounded-xl p-4 border border-white/5">
          <div class="text-[10px] text-[var(--color-text-disabled)] mb-1">版本</div>
          <div class="text-sm font-medium text-[var(--color-text-primary)]">v2.0.0</div>
        </div>
        <div class="bg-[var(--color-bg-base)] rounded-xl p-4 border border-white/5">
          <div class="text-[10px] text-[var(--color-text-disabled)] mb-1">前端框架</div>
          <div class="text-sm font-medium text-[var(--color-text-primary)]">Vue 3 + Tauri</div>
        </div>
        <div class="bg-[var(--color-bg-base)] rounded-xl p-4 border border-white/5">
          <div class="text-[10px] text-[var(--color-text-disabled)] mb-1">后端框架</div>
          <div class="text-sm font-medium text-[var(--color-text-primary)]">FastAPI 0.115</div>
        </div>
        <div class="bg-[var(--color-bg-base)] rounded-xl p-4 border border-white/5">
          <div class="text-[10px] text-[var(--color-text-disabled)] mb-1">数据库</div>
          <div class="text-sm font-medium text-[var(--color-text-primary)]">SQLite + aiosqlite</div>
        </div>
      </div>
    </div>
  </div>
</template>
