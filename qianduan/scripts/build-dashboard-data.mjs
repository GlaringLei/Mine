import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'

const root = process.cwd()
const projectData = path.join(root, '随钻参数处理与状态反演prj', 'processed_dataset_Vtest3')
const outputDir = path.join(root, 'public', 'data')
const predictionsPath = path.join(projectData, 'reports', 'all_model_predictions.csv')
const stressLevels = [0, 10, 20, 30, 40]
const modelIds = {
  advancedV1_multiscale_extratrees: 'v1',
  advancedV2_cnn_bilstm: 'v2',
  advancedV3_physics_fusion: 'v3'
}

function parseRows(text) {
  const lines = text.trim().split(/\r?\n/)
  const headers = lines.shift().split(',')
  return lines.map((line) => {
    const values = line.split(',')
    return Object.fromEntries(headers.map((header, index) => [header, values[index] ?? '']))
  })
}

function number(value, digits) {
  const result = Number(value)
  return Number.isFinite(result) ? Number(result.toFixed(digits)) : null
}

const predictionRows = parseRows(await readFile(predictionsPath, 'utf8'))
const predictionIndex = new Map()

for (const row of predictionRows) {
  if (row.source_file.includes('_1.csv')) continue
  const modelId = modelIds[row.model]
  if (!modelId) continue
  const key = `${row.source_file}|${row.sample_index}`
  if (!predictionIndex.has(key)) predictionIndex.set(key, {})
  predictionIndex.get(key)[modelId] = {
    damage: Number(row.state_head_damage_level || row.pred_damage_level),
    stress: Number(row.state_head_stress_mpa || row.pred_stress_mpa),
    state: row.pred_state_label,
    confidence: row.state_confidence ? number(row.state_confidence, 4) : null,
    correct: row.state_correct === 'True'
  }
}

const series = {}
const sourceFiles = []

for (const stress of stressLevels) {
  const fileName = `VTEST_S${String(stress).padStart(2, '0')}.csv`
  const sourcePath = path.join(projectData, 'csv_by_stress', fileName)
  const sourceRows = parseRows(await readFile(sourcePath, 'utf8'))
  const selected = sourceRows.filter((row, index) => {
    const sampleIndex = Number(row.sample_index)
    const isBoundary = sampleIndex === 199 || sampleIndex === sourceRows.length - 1 || sampleIndex % 25 === 0
    return sampleIndex >= 199 && isBoundary
  })

  series[String(stress)] = selected.map((row) => {
    const key = `${fileName}|${row.sample_index}`
    return {
      sample: Number(row.sample_index),
      cumulativeDepth: number(row.cumulative_depth_cm, 3),
      depth: number(row.depth_cm, 3),
      torque: number(row.torque_nm, 4),
      thrust: number(row.thrust_kn, 5),
      actualDamage: Number(row.true_damage_level),
      actualStress: Number(row.true_stress_mpa),
      actualState: row.true_state_label,
      segment: Number(row.segment_index),
      predictions: predictionIndex.get(key) || {}
    }
  })

  sourceFiles.push({
    file: fileName,
    rawRows: sourceRows.length,
    displayedRows: series[String(stress)].length
  })
}

const output = {
  meta: {
    title: 'Vtest3 随钻参数与状态反演展示数据',
    source: 'processed_dataset_Vtest3/csv_by_stress + reports/all_model_predictions.csv',
    generatedAt: new Date().toISOString(),
    sampling: 'sample_index >= 199，按 25 点等间隔抽样并保留边界点',
    depthRangeCm: [0, 125],
    stressLevels,
    sourceFiles
  },
  series
}

await mkdir(outputDir, { recursive: true })
await writeFile(path.join(outputDir, 'drilling_telemetry.json'), `${JSON.stringify(output)}\n`, 'utf8')
console.log(`Wrote ${stressLevels.length} stress series / ${Object.values(series).reduce((sum, rows) => sum + rows.length, 0)} samples`)
