import { useAppStore } from '@/stores/useAppStore'
import { useToast } from '@/composables/useToast'

/** 后端统一响应协议 */
export interface ApiResponse<T = unknown> {
  code: number
  msg: string
  data: T
}

/** 业务错误码映射 */
export const ErrorCode = {
  SUCCESS: 0,
  BAD_REQUEST: 400,
  AUTH_TOKEN_EXPIRED: 2001,
  AUTH_TOKEN_INVALID: 2002,
  FORBIDDEN: 4003,
  RATE_LIMITED: 3001,
  SERVER_ERROR: 5000,
} as const

export function useApi() {
  const app = useAppStore()
  const toast = useToast()

  /** 处理业务错误码，返回 true 表示已处理（调用方应停止） */
  function handleBusinessCode(resp: ApiResponse): boolean {
    if (resp.code === ErrorCode.SUCCESS) return false

    switch (resp.code) {
      case ErrorCode.AUTH_TOKEN_EXPIRED:
      case ErrorCode.AUTH_TOKEN_INVALID:
        toast.error('登录已过期，请重新登录')
        app.logout()
        // 跳转登录页 — 由路由守卫兜底
        window.location.hash = '#/settings'
        return true
      case ErrorCode.RATE_LIMITED:
        toast.warning('请求过于频繁，请稍后再试')
        return true
      case ErrorCode.FORBIDDEN:
        toast.error('权限不足')
        return true
      case ErrorCode.BAD_REQUEST:
        toast.warning(resp.msg || '请求参数有误')
        return true
      case ErrorCode.SERVER_ERROR:
        toast.error(resp.msg || '服务器内部错误')
        return true
      default:
        toast.error(resp.msg || `未知错误 (${resp.code})`)
        return true
    }
  }

  async function request<T = any>(path: string, options: RequestInit = {}): Promise<any | null> {
    try {
      const res = await fetch(path, {
        headers: {
          'Content-Type': 'application/json',
          ...(app.accessToken ? { Authorization: `Bearer ${app.accessToken}` } : {}),
          ...options.headers,
        },
        ...options,
      })

      // HTTP 层错误 — 非 2xx
      if (!res.ok) {
        // 尝试解析后端返回的业务错误体
        try {
          const body = await res.json() as ApiResponse
          if (handleBusinessCode(body)) return null
        } catch {
          // 无法解析 body，走 HTTP 状态码兜底
          if (res.status === 401) {
            toast.error('登录已过期，请重新登录')
            app.logout()
            window.location.hash = '#/settings'
          } else if (res.status === 429) {
            toast.warning('请求过于频繁，请稍后再试')
          } else if (res.status >= 500) {
            toast.error('服务器异常，请稍后再试')
          } else {
            toast.error(`请求失败 (${res.status})`)
          }
        }
        return null
      }

      const body = await res.json()
      if (typeof body?.code === 'number') {
        if (handleBusinessCode(body as ApiResponse)) return null
        const data = body.data ?? body
        return typeof data === 'object' && data !== null
          ? { ...data, code: body.code, msg: body.msg, data }
          : data
      }
      return typeof body === 'object' && body !== null ? { ...body, data: body } : body
    } catch (err) {
      toast.error('网络连接失败，请检查后端服务')
      return null
    }
  }

  async function get<T = any>(path: string): Promise<any | null> {
    return request<T>(path, { method: 'GET' })
  }

  async function post<T = any>(path: string, body?: unknown): Promise<any | null> {
    return request<T>(path, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    })
  }

  async function del<T = any>(path: string): Promise<any | null> {
    return request<T>(path, { method: 'DELETE' })
  }

  return { request, get, post, del, ErrorCode }
}
