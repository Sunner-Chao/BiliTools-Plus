import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface Task {
  id: string
  name: string
  description: string
  game?: string
  account?: string
  status?: 'pending' | 'running' | 'success' | 'fail' | 'idle'
}

export const useTaskStore = defineStore('tasks', () => {
  const tasks = ref<Task[]>([])
  const selectedTaskIds = ref<Set<string>>(new Set())
  const robPeriod = ref(0.3)
  const robHoldtime = ref(30)
  const robMode = ref('普通模式')
  const logs = ref<Record<string, any[]>>({})

  const selectedTasks = computed(() => tasks.value.filter(t => selectedTaskIds.value.has(t.id)))

  function setTasks(list: Task[]) { tasks.value = list }
  function toggleTask(id: string) {
    if (selectedTaskIds.value.has(id)) selectedTaskIds.value.delete(id)
    else selectedTaskIds.value.add(id)
  }
  function selectAll() { tasks.value.forEach(t => selectedTaskIds.value.add(t.id)) }
  function clearSelection() { selectedTaskIds.value.clear() }
  function appendLog(taskId: string, msg: any) {
    if (!logs.value[taskId]) logs.value[taskId] = []
    logs.value[taskId].push(msg)
  }

  return { tasks, selectedTaskIds, robPeriod, robHoldtime, robMode, logs, selectedTasks, setTasks, toggleTask, selectAll, clearSelection, appendLog }
})
