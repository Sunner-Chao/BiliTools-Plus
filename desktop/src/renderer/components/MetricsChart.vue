<template>
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
    <h3 class="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">{{ title }}</h3>
    <div v-if="hasData" ref="chartRef" class="w-full h-64" :aria-label="`${title}趋势图`"></div>
    <div v-else class="w-full h-64 flex items-center justify-center text-gray-400 dark:text-gray-500 text-sm" role="status" aria-live="polite">
      <svg class="animate-spin h-5 w-5 mr-2" viewBox="0 0 24 24" fill="none"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
      数据采集中，约 5 分钟后展示
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'
import type { MetricsHistory } from '@/composables/useMetrics'

const props = defineProps<{
  title: string
  data: MetricsHistory | null
  series: Array<{
    name: string
    key: keyof Omit<MetricsHistory, 'timeline'>
    color: string
  }>
}>()

const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

const hasData = computed(() =>
  props.data?.timeline && props.data.timeline.length > 0
)

function initChart() {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)
  updateChart()
}

function updateChart() {
  if (!chart || !props.data) return

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
    },
    legend: {
      data: props.series.map(s => s.name),
      bottom: 0,
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      top: '10%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: props.data.timeline,
    },
    yAxis: {
      type: 'value',
    },
    series: props.series.map(s => ({
      name: s.name,
      type: 'line' as const,
      smooth: true,
      data: props.data![s.key],
      itemStyle: { color: s.color },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: s.color + '80' },
          { offset: 1, color: s.color + '10' },
        ]),
      },
    })),
  }

  chart.setOption(option)
}

watch(() => props.data, updateChart, { deep: true })

watch(hasData, (val) => {
  if (val) {
    // 数据到达后初始化图表（首次为空时不渲染）
    setTimeout(() => initChart(), 50)
  }
})

onMounted(() => {
  initChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
})

function handleResize() {
  chart?.resize()
}
</script>
