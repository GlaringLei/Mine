import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# Extra large figure with lots of vertical space
fig, ax = plt.subplots(figsize=(18, 14))
ax.set_xlim(0, 18)
ax.set_ylim(0, 14)
ax.axis('off')

# ── COLORS ──
layers = [
    {
        'cn': '交互控制层',
        'en': 'Interaction Control  ·  Vue 3 Composition API',
        'bg': '#E8F5E9', 'border': '#2E7D32',
        'items': [
            '场景交互：OrbitControls  旋转 / 缩放 / 平移',
            '视图切换：整体云图 / 剖面模式 / 等值面',
            '模型筛选：V1 / V2 / V3  运行时动态切换',
            '围压与演进：0–40 MPa  ·  播放 / 变速 / 拖拽定位',
        ]
    },
    {
        'cn': '可视化层',
        'en': 'Visualization  ·  Three.js r160+ WebGL  ·  OrbitControls + CSS2DRenderer',
        'bg': '#FFF3E0', 'border': '#E65100',
        'items': [
            '围岩数字孪生体：CylinderGeometry + 顶点着色云图 + 巷道开挖面',
            '动态特效：粒子碎片 · 应力波环 · 损伤标记 · 能量流线',
            '场量映射：七级渐变色标  反演应力场 / 损伤场 / 联合误差场',
            '空间标注：CSS2D 标注 + 色标图例 + 坐标轴指示器',
        ]
    },
    {
        'cn': '模型层',
        'en': 'Model  ·  预计算反演输出  ·  drilling_telemetry.json',
        'bg': '#E3F2FD', 'border': '#0D47A1',
        'items': [
            'V1  Multi-scale ExtraTrees     多尺度特征提取 + 极端随机树回归',
            'V2  CNN + BiLSTM                   卷积时序混合架构 · 上下文依赖建模',
            'V3  Physics Fusion                   Weibull-DP 物理先验约束融合反演',
        ]
    },
    {
        'cn': '数据层',
        'en': 'Data  ·  JSON / CSV 混合管道  ·  Pinia Store (drillingData.js)  ·  20+ Computed',
        'bg': '#F3E5F5', 'border': '#6A1B9A',
        'items': [
            '数据源：dashboard_summary.json  ·  drilling_telemetry.json  ·  experiment_manifest.csv',
            '指标：overall_metrics.csv  ·  by_file_metrics.csv  ·  VTEST_S*.csv',
            '状态管理：loadAll() 并行加载  →  Computed 响应式属性  →  Props 驱动渲染',
        ]
    },
]

# ── LAYOUT (spread across 14 units of vertical space) ──
LAYER_H = 2.0      # each layer height
LAYER_GAP = 1.1    # gap between layers (plenty of space)
START_Y = 12.2     # top of first layer
LEFT = 0.8
RIGHT = 17.2
WIDTH = RIGHT - LEFT

for idx, layer in enumerate(layers):
    y_bottom = START_Y - (idx + 1) * LAYER_H - idx * LAYER_GAP
    y_top = y_bottom + LAYER_H
    y_mid = (y_bottom + y_top) / 2

    # ── Colored background band ──
    rect = Rectangle((LEFT, y_bottom), WIDTH, LAYER_H,
                      facecolor=layer['bg'], edgecolor=layer['border'],
                      linewidth=3, alpha=0.50, zorder=1)
    ax.add_patch(rect)

    # ── Top border accent line ──
    ax.plot([LEFT, RIGHT], [y_top, y_top], color=layer['border'], linewidth=1.2, alpha=0.5, zorder=2)

    # ── Layer number badge ──
    badge = Rectangle((LEFT + 0.15, y_top - 0.7), 0.55, 0.55,
                       facecolor=layer['border'], edgecolor='none', alpha=0.9, zorder=3)
    ax.add_patch(badge)
    ax.text(LEFT + 0.425, y_top - 0.425, str(idx + 1), fontsize=14, fontweight='bold',
            color='white', ha='center', va='center', zorder=4)

    # ── Title ──
    ax.text(LEFT + 0.95, y_top - 0.35, layer['cn'], fontsize=16, fontweight='bold',
            color=layer['border'], va='center', ha='left', zorder=4)
    ax.text(LEFT + 0.95, y_top - 0.72, layer['en'], fontsize=9.5, color='#777777',
            style='italic', va='center', ha='left', zorder=4)

    # ── Item list ──
    item_start_y = y_bottom + 0.25
    for i, item in enumerate(layer['items']):
        iy = y_bottom + LAYER_H - 1.05 - i * 0.48
        # Bullet
        ax.plot(LEFT + 1.1, iy, 'o', color=layer['border'], markersize=4, zorder=4)
        ax.text(LEFT + 1.45, iy, item, fontsize=11.5, color='#222222', va='center', ha='left', zorder=4)

    # ── Down arrow ──
    if idx < len(layers) - 1:
        arrow_top = y_bottom - 0.15
        arrow_bot = y_bottom - LAYER_GAP + 0.25
        ax.annotate('', xy=(LEFT + WIDTH/2, arrow_bot), xytext=(LEFT + WIDTH/2, arrow_top),
                    arrowprops=dict(arrowstyle='->', color='#999999', lw=3.5), zorder=5)

# ── TITLE ──
ax.text(9, 13.65, '随钻围岩状态智能反演三维云图平台四层架构',
        fontsize=22, fontweight='bold', color='#111111', ha='center', va='center')
ax.text(9, 13.1, '数据流向：loadAll()  →  Computed  →  Props  →  Vertex Colors  →  User Interaction  →  Watch  →  Scene Update',
        fontsize=11, color='#666666', ha='center', va='center')

# ── RIGHT-SIDE TECH LABELS ──
techs = ['Vue 3 + Pinia', 'Three.js\nWebGL', 'ML Models\nInference', 'JSON/CSV\nPipeline']
for idx, (layer, tech) in enumerate(zip(layers, techs)):
    y_center = START_Y - (idx + 0.5) * LAYER_H - idx * LAYER_GAP
    ax.text(17.45, y_center, tech, fontsize=9, fontweight='bold',
            color=layer['border'], rotation=90, ha='center', va='center',
            bbox=dict(boxstyle='round,pad=0.25', facecolor='white',
                      edgecolor=layer['border'], linewidth=1.5, alpha=0.85), zorder=5)

plt.tight_layout(pad=0.3)
plt.savefig('architecture_diagram.png', dpi=180, bbox_inches='tight',
            facecolor='white', edgecolor='none')
plt.close()
print('Done: architecture_diagram.png')
