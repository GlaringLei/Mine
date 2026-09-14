<template>
  <div>
    <div class="right-bar">
      <p class="text-gradient btn-hover">模型输出</p>
    </div>
    <div ref="target" class="w-full h-full"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from "vue";
import * as echarts from "echarts";
import { useCsvStore } from "../stores/csv";
import { usePreStore } from "../stores/pre";
const csvStore = useCsvStore();
const preStore = usePreStore();

// console.log(props.data);
// 1.初始化
let myChart = null;
const target = ref(null);
onMounted(() => {
  myChart = echarts.init(target.value);
  renderChart();
});

// 2.构建 option 配置对象
const renderChart = () => {
  const options = {
    toolbox: {
      show: true,
      iconStyle: {
        borderColor: 'white',
      },
      feature: {
        saveAsImage: {
        },
      }
    },
    textStyle: {
      fontSize: 14,       // 文字大小
      fontFamily: 'Arial', // 字体
      color: '#ffffff',       // 文字颜色
      fontWeight: '100',  // 字重（normal/bold/bolder/lighter/100-900）
      fontStyle: 'normals'  // 字体风格（normal/italic/oblique）
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        label: {
          backgroundColor: 'white',
          color: '#505050',
        },
      }
    },
    legend: {
      textStyle: {
        fontSize: 14,       // 文字大小
        fontFamily: 'Arial', // 字体
        color: '#ffffff',       // 文字颜色
        fontWeight: '100',  // 字重（normal/bold/bolder/lighter/100-900）
        fontStyle: 'normals'  // 字体风格（normal/italic/oblique）
      },
    },
    xAxis: {
      type: 'category',
      data: csvStore.data.map(item => item.time_index),
    },
    yAxis: {
      type: 'value',
      splitLine: {
        show: true,  // 显示网格线
        lineStyle: {
          color: '#a0a0a0',  // 浅灰色网格线
          width: 1,
          type: 'dashed'  // 虚线样式
        }
      },
    },
    grid: {
      top: '20%',
      left: '0%',
      right: '0%',
      bottom: '0%',
      containLabel: true,
    },
    series: [
      {
        lineStyle: {
          color: '#1663B8',
        },
        itemStyle: {
          color: '#1663B8',
        },
        splitLine: {
          show: true,  // 显示网格线
          lineStyle: {
            color: '#a0a0a0',  // 浅灰色网格线
            width: 1,
            type: 'dashed'  // 虚线样式
          }
        },
        name: '原始AE数据',
        type: 'line',
        data: csvStore.data.map(item => item.ae_energy),
        markPoint: {
          data: [
            { type: 'max', name: 'Max' },
            { type: 'min', name: 'Min' }
          ]
        },
        markLine: {
          data: [{ type: 'average', name: 'Avg' }]
        }
      },

      {
        lineStyle: {
          color: '#FD666D',
          type: 'dashed',
        },
        itemStyle: {
          color: '#FD666D',

        },

        name: '预测AE数据',
        type: 'line',
        data: preStore.data.map(item => item.pre_ae_energy),
        markPoint: {
          data: [{ name: '周最低', value: -2, xAxis: 1, yAxis: -1.5 }]
        },
        markLine: {
          data: [
            { type: 'average', name: 'Avg' },
            [
              {
                symbol: 'none',
                x: '90%',
                yAxis: 'max'
              },
              {
                symbol: 'circle',
                label: {
                  position: 'start',
                  formatter: 'Max'
                },
                type: 'max',
                name: '最高点'
              }
            ]
          ]
        }
      }
    ]
  };
  // 3.通过实例.setOptions(option)
  myChart.setOption(options);
};
watch(() => csvStore.data, renderChart)
</script>

<style lang="scss" scoped></style>
