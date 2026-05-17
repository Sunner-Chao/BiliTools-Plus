/** Dark / Light theme toggle composable with localStorage persistence */
import { ref, watchEffect } from 'vue'

type Theme = 'light' | 'dark'

const STORAGE_KEY = 'bitools-theme'

const theme = ref<Theme>(
  (localStorage.getItem(STORAGE_KEY) as Theme) || 'light',
)

function applyTheme(t: Theme) {
  const root = document.documentElement
  if (t === 'dark') {
    root.classList.add('dark')
  } else {
    root.classList.remove('dark')
  }
  root.setAttribute('data-theme', t)
  localStorage.setItem(STORAGE_KEY, t)
}

// Initialize on load
applyTheme(theme.value)

watchEffect(() => applyTheme(theme.value))

export function useTheme() {
  function toggle() {
    theme.value = theme.value === 'light' ? 'dark' : 'light'
  }

  return {
    theme,
    toggle,
    isDark: () => theme.value === 'dark',
  }
}
