<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAppStore } from '@/stores/useAppStore'
import { useTheme } from '@/composables/useTheme'
import StatusBadge from '@/components/StatusBadge.vue'
import ToastContainer from '@/components/ToastContainer.vue'
import ErrorBoundary from '@/components/ErrorBoundary.vue'
import { LayoutDashboard, Crosshair, Radio, UserCog, Settings, Activity, Sun, Moon, CalendarCheck } from 'lucide-vue-next'

const router = useRouter()
const app = useAppStore()
const { theme, toggle: toggleTheme } = useTheme()

const navItems = [
  { path: '/',          label: '仪表盘', icon: LayoutDashboard },
  { path: '/rob-task',  label: '抢码任务', icon: Crosshair },
  { path: '/live-task', label: '直播推流', icon: Radio },
  { path: '/daily-task',label: '每日任务', icon: CalendarCheck },
  { path: '/accounts',  label: '账号管理', icon: UserCog },
  { path: '/metrics',   label: '监控面板', icon: Activity },
  { path: '/settings',  label: '设置',    icon: Settings },
]
</script>

<template>
  <div class="flex h-screen overflow-hidden">
    <!-- Sidebar -->
    <aside class="w-64 flex-shrink-0 border-r border-white/5 bg-[var(--color-bg-elevated)]/80 backdrop-blur-xl flex flex-col relative overflow-hidden">
      <!-- Ambient orbs -->
      <div class="absolute -top-20 -right-20 w-40 h-40 rounded-full bg-[var(--color-primary)]/10 blur-2xl pointer-events-none" />
      <div class="absolute -bottom-10 left-0 w-32 h-32 rounded-full bg-purple-500/5 blur-2xl pointer-events-none" />

      <!-- Logo -->
      <div class="px-5 py-5 border-b border-white/5">
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-[var(--color-primary-active)] via-[var(--color-primary)] to-[var(--color-primary-hover)] flex items-center justify-center text-white font-bold text-sm shadow-lg shadow-indigo-500/20 ring-1 ring-indigo-400/10">
            B
          </div>
          <div>
            <h1 class="text-base font-bold text-[var(--color-text-primary)] tracking-wide">Bili-Tools</h1>
            <p class="text-[10px] text-[var(--color-text-secondary)]">手游自动化工具 v2.0</p>
          </div>
        </div>
      </div>

      <!-- Game selector -->
      <div class="px-4 pt-4 pb-2">
        <div class="flex flex-wrap gap-1.5">
          <button
            v-for="g in app.games" :key="g.key"
            @click="app.setGame(g.key)"
            :class="[
              'px-2.5 py-1 rounded-full text-[11px] font-medium transition-all',
              app.currentGame === g.key
                ? 'bg-[var(--color-primary)]/20 text-[var(--color-primary)] ring-1 ring-[var(--color-primary)]/30'
                : 'text-[var(--color-text-disabled)] hover:text-[var(--color-text-secondary)]'
            ]"
          >{{ g.label }}</button>
        </div>
      </div>

      <!-- Navigation -->
      <nav class="flex-1 px-3 py-3 space-y-0.5">
        <button
          v-for="item in navItems" :key="item.path"
          @click="router.push(item.path)"
          :class="[
            'w-full text-left px-4 py-2.5 rounded-xl text-sm transition-all flex items-center gap-3 relative overflow-hidden',
            router.currentRoute.value.path === item.path
              ? 'bg-[var(--color-primary)]/10 text-[var(--color-primary)] font-semibold shadow-sm shadow-[var(--color-primary)]/5 before:absolute before:left-0 before:top-1/4 before:bottom-1/4 before:w-0.5 before:bg-[var(--color-primary)] before:rounded-r-full'
              : 'text-[var(--color-text-secondary)] hover:bg-white/5 hover:text-[var(--color-text-primary)]'
          ]"
        >
          <component :is="item.icon" :size="16" class="shrink-0" />
          <span>{{ item.label }}</span>
        </button>
      </nav>

      <!-- User profile when logged in -->
      <div v-if="app.isLoggedIn" class="px-4 py-3 border-t border-white/5">
        <div class="flex items-center gap-3 p-2 rounded-xl bg-white/5">
          <img v-if="app.avatar" :src="app.avatar" alt="头像" class="w-10 h-10 rounded-full ring-2 ring-[var(--color-primary)]/30" />
          <div v-else class="w-10 h-10 rounded-full bg-gradient-to-br from-[var(--color-primary)] to-[#0066cc] flex items-center justify-center text-white font-bold text-sm">
            {{ app.username?.charAt(0)?.toUpperCase() ?? '?' }}
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-semibold text-[var(--color-text-primary)] truncate">{{ app.username }}</p>
            <p v-if="app.room_id" class="text-[10px] text-[var(--color-text-secondary)]">房间号: {{ app.room_id }}</p>
            <p v-if="app.uid" class="text-[10px] text-[var(--color-text-secondary)]">UID: {{ app.uid }}</p>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="px-5 py-4 border-t border-white/5 space-y-2.5">
        <div class="flex items-center justify-between text-xs">
          <span class="text-[var(--color-text-secondary)]">服务状态</span>
          <StatusBadge :status="app.globalWsStatus" :pulse="app.globalWsStatus === 'connecting'" />
        </div>
        <!-- Theme toggle -->
        <div class="flex items-center justify-between text-xs">
          <span class="text-[var(--color-text-secondary)]">主题</span>
          <button
            @click="toggleTheme"
            class="p-1 rounded-lg hover:bg-white/10 transition-colors"
            :aria-label="theme === 'dark' ? '切换为浅色模式' : '切换为深色模式'"
            :aria-pressed="theme === 'dark'"
          >
            <Sun v-if="theme === 'dark'" :size="14" class="text-yellow-400" />
            <Moon v-else :size="14" class="text-[var(--color-text-secondary)]" />
          </button>
        </div>
      </div>
    </aside>

    <!-- Main content -->
    <main class="flex-1 overflow-auto bg-[var(--color-bg-base)]">
      <router-view v-slot="{ Component }">
        <ErrorBoundary>
          <Transition name="page" mode="out-in">
            <component :is="Component" />
          </Transition>
        </ErrorBoundary>
      </router-view>
    </main>

    <ToastContainer />
  </div>
</template>

<style scoped>
.page-enter-active { transition: all 0.2s ease-out; }
.page-leave-active { transition: all 0.15s ease-in; }
.page-enter-from { opacity: 0; transform: translateY(8px); }
.page-leave-to   { opacity: 0; transform: translateY(-4px); }
</style>
