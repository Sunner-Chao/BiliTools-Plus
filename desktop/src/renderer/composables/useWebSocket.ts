import { ref, onUnmounted } from 'vue'
import { useAppStore } from '@/stores/useAppStore'
import { useToast } from '@/composables/useToast'

export interface LogMessage { level: string; message: string; timestamp?: string; task_id?: string; type?: string; }

/** WebSocket 事件类型定义 — 与后端 schema 对齐 */
export interface TaskProgressEvent {
  event: 'task_progress'
  task_id: string
  progress: number
  status: 'running' | 'paused' | 'completed'
}

export interface ErrorAlertEvent {
  event: 'error_alert'
  code: number
  msg: string
}

export interface TokenExpiredEvent {
  event: 'token_expired'
  code: number
  msg: string
  new_token_available?: boolean
  new_token?: string   // JWT 签名值，前端透传用于重连
}

export interface TaskCompleteEvent {
  event: 'task_complete'
  task_id: string
  result: unknown
}

export interface StockChangeEvent {
  event: 'stock_change'
  product_id: string
  product_name: string
  new_stock: number
  price: number
  timestamp: number
}

export type WsEvent = TaskProgressEvent | ErrorAlertEvent | TokenExpiredEvent | TaskCompleteEvent | StockChangeEvent | RequestRejectedEvent | LogMessage

export interface RequestRejectedEvent {
  event: 'request_rejected'
  reason: string
}

export interface WsHandlers {
  onTaskProgress?: (e: TaskProgressEvent) => void
  onErrorAlert?: (e: ErrorAlertEvent) => void
  onTokenExpired?: (e: TokenExpiredEvent) => void
  onTaskComplete?: (e: TaskCompleteEvent) => void
  onStockChange?: (e: StockChangeEvent) => void
  onRequestRejected?: (e: RequestRejectedEvent) => void
  onLog?: (msg: LogMessage) => void
  onStatusChange?: (s: string) => void
}

const MAX_RECONNECT_ATTEMPTS = 8
const BASE_RECONNECT_DELAY = 1000   // 1s
const MAX_RECONNECT_DELAY = 30000   // 30s

/** 200ms 防闪烁 toast：仅当操作耗时 > 200ms 才展示 */
function useDeferredToast() {
  let timer: ReturnType<typeof setTimeout> | null = null
  let dismissed = false

  function show(toastFn: () => void, delay = 200) {
    dismissed = false
    timer = setTimeout(() => {
      if (!dismissed) toastFn()
    }, delay)
  }

  function cancel() {
    dismissed = true
    if (timer) { clearTimeout(timer); timer = null }
  }

  return { show, cancel }
}

export function useWebSocket(url: string, handlers: WsHandlers = {}) {
  const app = useAppStore()
  const toast = useToast()
  const status = ref<'connecting' | 'connected' | 'disconnected' | 'error'>('connecting')
  let ws: WebSocket | null = null
  let currentUrl = url
  let reconnectAttempts = 0
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let intentionalClose = false
  const deferredToast = useDeferredToast()

  function routeEvent(raw: unknown) {
    if (typeof raw !== 'object' || raw === null) return
    const evt = raw as Record<string, unknown>

    switch (evt.event) {
      case 'task_progress':
        handlers.onTaskProgress?.(evt as unknown as TaskProgressEvent)
        break
      case 'error_alert':
        handlers.onErrorAlert?.(evt as unknown as ErrorAlertEvent)
        toast.warning((evt as unknown as ErrorAlertEvent).msg || '服务异常')
        break
      case 'token_expired': {
        const tokenEvt = evt as unknown as TokenExpiredEvent
        handlers.onTokenExpired?.(tokenEvt)
        if (tokenEvt.new_token_available && tokenEvt.new_token) {
          // 无感重连：带新 JWT token 重建连接
          const deferredToast = useDeferredToast()
          deferredToast.show(() => toast.info('正在切换线路…'))
          disconnect()
          intentionalClose = false
          currentUrl = `${url.split('?')[0]}?token=${tokenEvt.new_token}`
          reconnectAttempts = 0
          connect()
          deferredToast.cancel()
        } else {
          toast.error('登录已过期，请重新登录')
          app.logout()
          window.location.hash = '#/settings'
        }
        break
      }
      case 'task_complete':
        handlers.onTaskComplete?.(evt as unknown as TaskCompleteEvent)
        break
      case 'stock_change':
        handlers.onStockChange?.(evt as unknown as StockChangeEvent)
        break
      case 'request_rejected':
        handlers.onRequestRejected?.(evt as unknown as RequestRejectedEvent)
        toast.warning((evt as unknown as RequestRejectedEvent).reason || '操作过于频繁')
        break
      default:
        // 兼容旧版日志消息
        handlers.onLog?.(raw as LogMessage)
        break
    }
  }

  function connect() {
    intentionalClose = false
    clearReconnectTimer()
    status.value = 'connecting'

    try {
      ws = new WebSocket(url)
    } catch {
      status.value = 'error'
      app.globalWsStatus = 'error'
      scheduleReconnect()
      return
    }

    ws.onopen = () => {
      status.value = 'connected'
      app.globalWsStatus = 'connected'
      reconnectAttempts = 0
      handlers.onStatusChange?.('connected')
    }

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        routeEvent(msg)
      } catch {
        // 非 JSON 消息忽略
      }
    }

    ws.onclose = (event) => {
      status.value = 'disconnected'
      app.globalWsStatus = 'disconnected'
      handlers.onStatusChange?.('disconnected')

      // 4001 = token 失效 / 4003 = JWT 签名失败 → 不重连，直接跳登录
      if (event.code === 4001 || event.code === 4003) {
        toast.error('登录已过期，请重新登录')
        app.logout()
        window.location.hash = '#/settings'
        return
      }

      if (!intentionalClose) scheduleReconnect()
    }

    ws.onerror = () => {
      status.value = 'error'
      app.globalWsStatus = 'error'
      handlers.onStatusChange?.('error')
    }
  }

  function clearReconnectTimer() {
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  /** 指数退避重连：1s → 2s → 4s → 8s → 16s → 30s → 30s... */
  function scheduleReconnect() {
    if (intentionalClose) return
    if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      toast.error('连接已断开，请刷新页面重试')
      return
    }

    const delay = Math.min(
      BASE_RECONNECT_DELAY * Math.pow(2, reconnectAttempts),
      MAX_RECONNECT_DELAY
    )
    reconnectAttempts++

    reconnectTimer = setTimeout(() => {
      connect()
    }, delay)
  }

  function disconnect() {
    intentionalClose = true
    clearReconnectTimer()
    ws?.close()
    ws = null
    status.value = 'disconnected'
    app.globalWsStatus = 'disconnected'
  }

  function send(data: unknown) {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data))
    }
  }

  /** 通过 WebSocket 发送抢购请求（绕过 HTTP 1 RTT 延迟） */
  function sendRequestSnipe(productId: string) {
    send({ event: 'request_snipe', product_id: productId })
  }

  connect()

  // 组件卸载时自动断开
  onUnmounted(() => {
    disconnect()
  })

  return { status, disconnect, send, sendRequestSnipe }
}
