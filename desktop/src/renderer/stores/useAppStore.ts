import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'

export interface GameConfig {
  key: string; label: string; configPath: string;
}

const STORAGE_KEY = 'bilibili_auth'
const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8001'

function loadFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const saved = JSON.parse(raw)
      if (typeof saved.avatar === 'string' && saved.avatar.startsWith('//')) {
        saved.avatar = `https:${saved.avatar}`
      }
      return saved
    }
  } catch { /* ignore */ }
  return null
}

function normalizeUrl(url = '') {
  return url.startsWith('//') ? `https:${url}` : url
}

export const useAppStore = defineStore('app', () => {
  const saved = loadFromStorage()
  const games: GameConfig[] = [
    { key: 'genshin', label: '原神', configPath: 'bili_config_genshin.json' },
    { key: 'starrail', label: '崩铁', configPath: 'bili_config_starrail.json' },
    { key: 'zzz', label: '绝区零', configPath: 'bili_config_zzz.json' },
    { key: 'wutheringwaves', label: '鸣潮', configPath: 'bili_config_wutheringwaves.json' },
  ]
  const currentGame = ref<string>('genshin')
  const server = ref({ url: DEFAULT_API_BASE, connected: false, ntpOffset: 0 })
  const isLoggedIn = ref(saved?.isLoggedIn ?? false)
  const username = ref(saved?.username ?? '')
  const uid = ref(saved?.uid ?? '')
  const accessToken = ref(saved?.accessToken ?? '')
  const cookies = ref(saved?.cookies ?? '')
  const room_id = ref(saved?.room_id ?? '')
  const avatar = ref(saved?.avatar ?? '')
  const level = ref(saved?.level ?? 0)
  const bili_jct = ref(saved?.bili_jct ?? '')
  const globalWsStatus = ref<'idle'|'connecting'|'connected'|'disconnected'|'error'>('idle')

  // localStorage 持久化：登录后自动写入
  watch([isLoggedIn, username, uid, accessToken, cookies, room_id, avatar, level, bili_jct], () => {
    if (isLoggedIn.value && accessToken.value) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        isLoggedIn: isLoggedIn.value,
        username: username.value,
        uid: uid.value,
        accessToken: accessToken.value,
        cookies: cookies.value,
        room_id: room_id.value,
        avatar: avatar.value,
        level: level.value,
        bili_jct: bili_jct.value,
      }))
    } else {
      localStorage.removeItem(STORAGE_KEY)
    }
  }, { immediate: true })

  const apiBase = computed(() => server.value.url)

  function setGame(key: string) { currentGame.value = key }
  function setServerUrl(url: string) { server.value.url = url }
  function setNtpOffset(offset: number) { server.value.ntpOffset = offset }
  function setServerConnected(connected: boolean) { server.value.connected = connected }
  function setRoomId(roomId: string) { room_id.value = roomId }
  function setLoggedIn(name: string) { isLoggedIn.value = true; username.value = name }
  interface LoginPayload {
    token: string; username: string; uid?: string; avatar?: string; room_id?: string; cookies?: string; level?: number; bili_jct?: string;
  }
  function login(payload: LoginPayload) {
    accessToken.value = payload.token
    username.value = payload.username
    cookies.value = payload.cookies || ''
    uid.value = payload.uid || ''
    room_id.value = payload.room_id || ''
    avatar.value = normalizeUrl(payload.avatar || '')
    level.value = payload.level || 0
    bili_jct.value = payload.bili_jct || ''
    isLoggedIn.value = true
  }
  function logout() {
    isLoggedIn.value = false
    username.value = ''
    uid.value = ''
    accessToken.value = ''
    cookies.value = ''
    room_id.value = ''
    avatar.value = ''
    level.value = 0
    bili_jct.value = ''
  }

  return {
    games, currentGame, server, isLoggedIn, username, uid, accessToken, cookies, room_id, avatar, level, bili_jct, globalWsStatus, apiBase,
    setGame, setServerUrl, setNtpOffset, setServerConnected, setRoomId, setLoggedIn, login, logout,
  }
})
