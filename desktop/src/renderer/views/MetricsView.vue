<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Activity, BarChart3, Radio, RefreshCw, ShieldCheck, Users } from 'lucide-vue-next'
import { useApi } from '@/composables/useApi'

const api = useApi()
const loading = ref(false)
const summary = ref<any>(null)

const cards = computed(() => [
  { label: '抢码任务', value: summary.value?.total_tasks ?? 0, sub: `成功 ${summary.value?.completed_tasks ?? 0} / 失败 ${summary.value?.failed_tasks ?? 0}` },
  { label: '运行/等待', value: summary.value?.running_tasks ?? 0, sub: `待执行 ${summary.value?.pending_tasks ?? 0}` },
  { label: '成功率', value: `${summary.value?.success_rate ?? 0}%`, sub: '基于本地任务记录' },
  { label: '观众身份', value: `${(summary.value?.daily?.audience_slots || []).filter((s: any) => s.is_valid).length}/4`, sub: `日志 ${summary.value?.daily?.log_count ?? 0} 条` },
])

async function refresh() {
  loading.value = true
  try {
    summary.value = await api.get('/api/analytics/summary')
  } finally {
    loading.value = false
  }
}

onMounted(refresh)
</script>

<template>
  <div class="p-6 space-y-6 main-bg min-h-full">
    <div class="flex items-center justify-between">
      <div>
        <div class="h-1 w-12 bg-gradient-to-r from-[var(--color-primary)] to-[var(--color-primary-hover)] rounded-full mb-3" />
        <h1 class="text-2xl font-bold text-[var(--color-text-primary)]">数据分析</h1>
        <p class="text-sm text-[var(--color-text-secondary)] mt-0.5">基于任务、直播、凭证和观众槽位的真实运行数据</p>
      </div>
      <button class="btn-primary flex items-center gap-2" :disabled="loading" @click="refresh">
        <RefreshCw :size="14" /> {{ loading ? '刷新中...' : '刷新' }}
      </button>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
      <div v-for="card in cards" :key="card.label" class="glass-card p-5">
        <div class="text-xs text-[var(--color-text-disabled)]">{{ card.label }}</div>
        <div class="text-2xl font-bold text-[var(--color-text-primary)] mt-2">{{ card.value }}</div>
        <div class="text-xs text-[var(--color-text-secondary)] mt-1">{{ card.sub }}</div>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="glass-card p-5">
        <div class="flex items-center gap-2 mb-4 text-sm font-semibold text-[var(--color-text-primary)]">
          <BarChart3 :size="16" class="text-[var(--color-primary)]" /> 游戏任务概览
        </div>
        <div class="space-y-3">
          <div v-for="game in summary?.games || []" :key="game.id" class="rounded-lg bg-[var(--color-bg-base)] p-3">
            <div class="flex items-center justify-between text-sm">
              <span class="font-medium text-[var(--color-text-primary)]">{{ game.name }}</span>
              <span class="text-[var(--color-primary)]">{{ game.rate }}%</span>
            </div>
            <div class="mt-2 h-2 rounded-full bg-white/5 overflow-hidden">
              <div class="h-full bg-[var(--color-primary)]" :style="{ width: `${Math.min(game.rate, 100)}%` }" />
            </div>
            <div class="mt-2 text-[11px] text-[var(--color-text-disabled)]">
              已建 {{ game.created_tasks }} · 配置 {{ game.configured_tasks }} · 失败 {{ game.failed }} · 分区 {{ game.area_v2 || '未配置' }}
            </div>
          </div>
          <div v-if="!summary?.games?.length" class="text-sm text-[var(--color-text-disabled)] text-center py-8">暂无游戏配置</div>
        </div>
      </div>

      <div class="space-y-6">
        <div class="glass-card p-5">
          <div class="flex items-center gap-2 mb-4 text-sm font-semibold text-[var(--color-text-primary)]">
            <Radio :size="16" class="text-[var(--color-success)]" /> 直播推流
          </div>
          <div class="grid grid-cols-2 gap-3 text-sm">
            <div class="rounded-lg bg-[var(--color-bg-base)] p-3">
              <div class="text-[11px] text-[var(--color-text-disabled)]">状态</div>
              <div class="mt-1 text-[var(--color-text-primary)]">{{ summary?.live?.is_living ? '推流中' : '空闲' }}</div>
            </div>
            <div class="rounded-lg bg-[var(--color-bg-base)] p-3">
              <div class="text-[11px] text-[var(--color-text-disabled)]">房间号</div>
              <div class="mt-1 text-[var(--color-text-primary)]">{{ summary?.live?.room_id || '-' }}</div>
            </div>
          </div>
        </div>

        <div class="glass-card p-5">
          <div class="flex items-center gap-2 mb-4 text-sm font-semibold text-[var(--color-text-primary)]">
            <ShieldCheck :size="16" class="text-[var(--color-warning)]" /> 凭证状态
          </div>
          <div class="text-sm text-[var(--color-text-secondary)]">
            {{ summary?.credential?.valid ? '主账号凭证有效' : '主账号凭证缺失或过期' }}
            <span v-if="summary?.credential?.expires_at">，到期 {{ summary.credential.expires_at }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="glass-card p-5">
      <div class="flex items-center gap-2 mb-4 text-sm font-semibold text-[var(--color-text-primary)]">
        <Users :size="16" class="text-[var(--color-info)]" /> 观众身份槽位
      </div>
      <div class="grid grid-cols-1 md:grid-cols-4 gap-3">
        <div v-for="slot in summary?.daily?.audience_slots || []" :key="slot.slot" class="rounded-lg bg-[var(--color-bg-base)] p-3">
          <div class="text-sm font-medium text-[var(--color-text-primary)]">观众 {{ slot.slot + 1 }}</div>
          <div class="text-xs text-[var(--color-text-secondary)] mt-1">{{ slot.name || '未绑定' }}</div>
          <div class="text-[11px] mt-2" :class="slot.is_valid ? 'text-[var(--color-success)]' : 'text-[var(--color-warning)]'">
            {{ slot.is_valid ? '有效' : slot.has_cookie ? '需重新验证' : '未配置' }}
          </div>
        </div>
      </div>
    </div>

    <div class="text-xs text-[var(--color-text-disabled)]">更新于 {{ summary?.updated_at || '-' }}</div>
  </div>
</template>
