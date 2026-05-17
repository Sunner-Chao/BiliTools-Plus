<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Bell, Database, FolderOpen, Globe, RefreshCw, Save, Shield, Wrench } from 'lucide-vue-next'
import { useApi } from '@/composables/useApi'
import { useAppStore } from '@/stores/useAppStore'
import { useToast } from '@/composables/useToast'

const api = useApi()
const app = useAppStore()
const toast = useToast()

const loading = ref(false)
const saving = ref(false)
const data = ref<any>(null)
const serverUrl = ref(app.server.url)
const credentialDays = ref(14)
const requestInterval = ref(500)
const maxRetries = ref(3)
const enableSound = ref(true)
const enableDesktop = ref(true)
const logAutoScroll = ref(true)
const maxLogItems = ref(500)

function bytes(size = 0) {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function date(ts?: number) {
  return ts ? new Date(ts * 1000).toLocaleString() : '-'
}

async function load() {
  loading.value = true
  try {
    data.value = await api.get('/api/settings')
    const settings = data.value?.settings || {}
    credentialDays.value = settings.credential_valid_days ?? 14
    requestInterval.value = settings.network?.request_interval_ms ?? 500
    maxRetries.value = settings.network?.max_retries ?? data.value?.backend?.bili_max_retries ?? 3
    enableSound.value = settings.notifications?.enable_sound ?? true
    enableDesktop.value = settings.notifications?.enable_desktop ?? true
    logAutoScroll.value = settings.notifications?.log_auto_scroll ?? true
    maxLogItems.value = settings.notifications?.max_log_items ?? 500
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  app.setServerUrl(serverUrl.value)
  try {
    const res = await api.post('/api/settings', {
      credential_valid_days: credentialDays.value,
      network: { request_interval_ms: requestInterval.value, max_retries: maxRetries.value },
      notifications: {
        enable_sound: enableSound.value,
        enable_desktop: enableDesktop.value,
        log_auto_scroll: logAutoScroll.value,
        max_log_items: maxLogItems.value,
      },
    })
    if (res?.success) toast.success('设置已保存')
    await load()
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="p-6 space-y-6 main-bg min-h-full">
    <div class="flex items-center justify-between">
      <div>
        <div class="h-1 w-12 bg-gradient-to-r from-[var(--color-primary)] to-[var(--color-primary-hover)] rounded-full mb-3" />
        <h1 class="text-2xl font-bold text-[var(--color-text-primary)]">设置</h1>
        <p class="text-sm text-[var(--color-text-secondary)] mt-0.5">凭证窗口、资源目录、可执行文件与运行参数</p>
      </div>
      <div class="flex gap-2">
        <button class="btn-ghost flex items-center gap-2" :disabled="loading" @click="load">
          <RefreshCw :size="14" /> 刷新
        </button>
        <button class="btn-primary flex items-center gap-2" :disabled="saving" @click="save">
          <Save :size="14" /> {{ saving ? '保存中...' : '保存设置' }}
        </button>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="glass-card p-5 space-y-4">
        <div class="flex items-center gap-2 text-sm font-semibold text-[var(--color-text-primary)]">
          <Globe :size="16" class="text-[var(--color-primary)]" /> 服务与网络
        </div>
        <div>
          <label class="text-[11px] text-[var(--color-text-disabled)] mb-1.5 block">API 服务器地址</label>
          <input v-model="serverUrl" class="input-field w-full text-sm" />
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="text-[11px] text-[var(--color-text-disabled)] mb-1.5 block">请求间隔（毫秒）</label>
            <input v-model.number="requestInterval" type="number" min="100" class="input-field w-full text-sm" />
          </div>
          <div>
            <label class="text-[11px] text-[var(--color-text-disabled)] mb-1.5 block">最大重试</label>
            <input v-model.number="maxRetries" type="number" min="0" max="10" class="input-field w-full text-sm" />
          </div>
        </div>
        <div class="rounded-lg bg-[var(--color-bg-base)] p-3 text-xs text-[var(--color-text-secondary)]">
          后端 {{ data?.backend?.host || '-' }}:{{ data?.backend?.port || '-' }} · 数据库 {{ data?.backend?.database_url || '-' }}
        </div>
      </div>

      <div class="glass-card p-5 space-y-4">
        <div class="flex items-center gap-2 text-sm font-semibold text-[var(--color-text-primary)]">
          <Shield :size="16" class="text-[var(--color-warning)]" /> 登录凭证
        </div>
        <div>
          <label class="text-[11px] text-[var(--color-text-disabled)] mb-1.5 block">凭证过期窗口（天）</label>
          <input v-model.number="credentialDays" type="number" min="1" max="90" class="input-field w-full text-sm" />
        </div>
        <div class="rounded-lg bg-[var(--color-bg-base)] p-3 text-sm text-[var(--color-text-secondary)]">
          {{ data?.credential?.valid ? '主账号凭证有效' : '主账号凭证缺失或过期' }}
          <span v-if="data?.credential?.expires_at">，到期 {{ data.credential.expires_at }}</span>
        </div>
        <div class="text-xs text-[var(--color-text-disabled)]">账号 {{ data?.user?.uname || data?.user?.name || '未登录' }}</div>
      </div>

      <div class="glass-card p-5 space-y-4">
        <div class="flex items-center gap-2 text-sm font-semibold text-[var(--color-text-primary)]">
          <Bell :size="16" class="text-[var(--color-success)]" /> 通知与日志
        </div>
        <label class="flex items-center justify-between text-sm text-[var(--color-text-secondary)]">
          声音提醒 <input v-model="enableSound" type="checkbox" class="w-4 h-4" />
        </label>
        <label class="flex items-center justify-between text-sm text-[var(--color-text-secondary)]">
          桌面通知 <input v-model="enableDesktop" type="checkbox" class="w-4 h-4" />
        </label>
        <label class="flex items-center justify-between text-sm text-[var(--color-text-secondary)]">
          日志自动滚动 <input v-model="logAutoScroll" type="checkbox" class="w-4 h-4" />
        </label>
        <div>
          <label class="text-[11px] text-[var(--color-text-disabled)] mb-1.5 block">最大日志条数</label>
          <input v-model.number="maxLogItems" type="number" min="100" max="5000" class="input-field w-full text-sm" />
        </div>
      </div>

      <div class="glass-card p-5">
        <div class="flex items-center gap-2 mb-4 text-sm font-semibold text-[var(--color-text-primary)]">
          <Wrench :size="16" class="text-[var(--color-info)]" /> 可执行文件
        </div>
        <div class="space-y-2 max-h-72 overflow-y-auto">
          <div v-for="item in data?.resources?.executables || []" :key="item.path" class="rounded-lg bg-[var(--color-bg-base)] p-3">
            <div class="text-sm text-[var(--color-text-primary)]">{{ item.name }}</div>
            <div class="text-[11px] text-[var(--color-text-disabled)] mt-1 break-all">{{ item.path }} · {{ bytes(item.size) }}</div>
          </div>
          <div v-if="!data?.resources?.executables?.length" class="text-sm text-[var(--color-text-disabled)]">未发现 execute 可执行文件</div>
        </div>
      </div>
    </div>

    <div class="glass-card p-5">
      <div class="flex items-center gap-2 mb-4 text-sm font-semibold text-[var(--color-text-primary)]">
        <FolderOpen :size="16" class="text-[var(--color-primary)]" /> 补充资源目录
      </div>
      <div class="grid grid-cols-1 md:grid-cols-5 gap-3">
        <div v-for="(item, name) in data?.resources?.extra_dirs || {}" :key="name" class="rounded-lg bg-[var(--color-bg-base)] p-3">
          <div class="text-sm font-medium text-[var(--color-text-primary)]">{{ name }}</div>
          <div class="text-xs mt-1" :class="item.exists ? 'text-[var(--color-success)]' : 'text-[var(--color-warning)]'">{{ item.exists ? '存在' : '缺失' }}</div>
          <div class="text-[11px] text-[var(--color-text-disabled)] mt-1">{{ item.files }} 文件 · {{ bytes(item.size) }}</div>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="glass-card p-5">
        <div class="flex items-center gap-2 mb-4 text-sm font-semibold text-[var(--color-text-primary)]">
          <Database :size="16" class="text-[var(--color-primary)]" /> 配置文件
        </div>
        <div class="space-y-2 max-h-80 overflow-y-auto">
          <div v-for="item in data?.resources?.config_files || []" :key="item.path" class="rounded-lg bg-[var(--color-bg-base)] p-3">
            <div class="text-sm text-[var(--color-text-primary)]">{{ item.name }}</div>
            <div class="text-[11px] text-[var(--color-text-disabled)] mt-1">{{ bytes(item.size) }} · {{ date(item.updated_at) }}</div>
          </div>
        </div>
      </div>
      <div class="glass-card p-5">
        <div class="flex items-center gap-2 mb-4 text-sm font-semibold text-[var(--color-text-primary)]">
          <Database :size="16" class="text-[var(--color-warning)]" /> Cookie 文件
        </div>
        <div class="space-y-2 max-h-80 overflow-y-auto">
          <div v-for="item in data?.resources?.cookie_files || []" :key="item.path" class="rounded-lg bg-[var(--color-bg-base)] p-3">
            <div class="text-sm text-[var(--color-text-primary)]">{{ item.name }}</div>
            <div class="text-[11px] text-[var(--color-text-disabled)] mt-1 break-all">{{ item.path }} · {{ bytes(item.size) }} · {{ date(item.updated_at) }}</div>
          </div>
          <div v-if="!data?.resources?.cookie_files?.length" class="text-sm text-[var(--color-text-disabled)]">暂无 Cookie 文件</div>
        </div>
      </div>
    </div>
  </div>
</template>
