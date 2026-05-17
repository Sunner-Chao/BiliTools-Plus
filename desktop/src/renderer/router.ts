import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '@/views/Dashboard.vue'
import RobTask from '@/views/RobTaskView.vue'
import LiveTask from '@/views/LiveTaskView.vue'
import Accounts from '@/views/AccountsView.vue'
import Settings from '@/views/SettingsView.vue'

const MetricsView = () => import('@/views/MetricsView.vue')
const LoginView = () => import('@/views/LoginView.vue')
const DailyTaskView = () => import('@/views/DailyTaskView.vue')

const publicPaths = ['/login']

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginView, meta: { public: true } },
    { path: '/', component: Dashboard },
    { path: '/rob-task', component: RobTask },
    { path: '/live-task', component: LiveTask },
    { path: '/daily-task', component: DailyTaskView },
    { path: '/accounts', component: Accounts },
    { path: '/metrics', component: MetricsView },
    { path: '/settings', component: Settings },
  ],
})

router.beforeEach((to) => {
  const raw = localStorage.getItem('bilibili_auth')
  const saved = raw ? JSON.parse(raw) : null
  const isLoggedIn = !!(saved?.isLoggedIn && saved?.accessToken)
  if (!to.meta?.public && !isLoggedIn) {
    return '/login'
  }
  if (to.path === '/login' && isLoggedIn) {
    return '/'
  }
})

export default router
