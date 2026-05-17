import { ref } from 'vue'

/**
 * 音频通知 composable
 * 浏览器要求用户首次交互后才能 autoplay，用 unlock() 解锁
 */
export function useSoundNotification() {
  const unlocked = ref(false)
  let audioCtx: AudioContext | null = null

  /** 用户首次点击时调用，解锁音频播放 */
  function unlock() {
    if (unlocked.value) return
    try {
      audioCtx = new AudioContext()
      const buffer = audioCtx.createBuffer(1, 1, 22050)
      const source = audioCtx.createBufferSource()
      source.buffer = buffer
      source.connect(audioCtx.destination)
      source.start(0)
      unlocked.value = true
    } catch {
      // 静默降级
    }
  }

  /** 播放提示音（Web Audio API 合成，无需外部文件） */
  function playStockAlert() {
    if (!audioCtx || !unlocked.value) return
    try {
      const osc = audioCtx.createOscillator()
      const gain = audioCtx.createGain()
      osc.connect(gain)
      gain.connect(audioCtx.destination)
      osc.frequency.value = 880
      gain.gain.value = 0.3
      osc.start(audioCtx.currentTime)
      osc.stop(audioCtx.currentTime + 0.15)
      gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.3)
    } catch {
      // 静默降级
    }
  }

  return { unlocked, unlock, playStockAlert }
}
