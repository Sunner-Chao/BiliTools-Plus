import { ref } from 'vue'
const toasts = ref<{ id: number; type: string; message: string }[]>([])
let nextId = 1

export function useToast() {
  function add(type: string, message: string, duration = 3500) {
    const id = nextId++
    toasts.value.push({ id, type, message })
    setTimeout(() => remove(id), duration)
  }
  function remove(id: number) {
    toasts.value = toasts.value.filter(t => t.id !== id)
  }
  return {
    toasts,
    success: (msg: string) => add('success', msg),
    error: (msg: string) => add('error', msg, 5000),
    warning: (msg: string) => add('warning', msg),
    info: (msg: string) => add('info', msg),
    remove,
  }
}
