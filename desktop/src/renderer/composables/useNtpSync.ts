import { ref, onUnmounted } from 'vue'
import { useAppStore } from '@/stores/useAppStore'

export function useNtpSync() {
  const app = useAppStore()
  const offset = ref(0)
  let timer: ReturnType<typeof setInterval> | null = null

  function start() {
    sync()
    timer = setInterval(sync, 30000)
  }
  function stop() { if (timer) { clearInterval(timer); timer = null } }

  async function sync() {
    try {
      const start = Date.now()
      const res = await fetch(`${app.apiBase}/api/health`)
      const rtt = Date.now() - start
      if (res.ok) { offset.value = Math.round(rtt / 2); app.setNtpOffset(offset.value) }
    } catch { /* silent */ }
  }

  onUnmounted(stop)
  return { offset, start, stop }
}
