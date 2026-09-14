import sys
sys.stdout.reconfigure(encoding='utf-8')
from docx import Document
from docx.shared import Pt, Inches, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
import os

doc = Document()

style = doc.styles['Normal']
font = style.font
font.name = '宋体'
font.size = Pt(12)
style.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')

# ── helper: insert figure with image + caption in thesis format ──
def insert_figure(doc, img_path, caption, width_inches=5.8):
    """Insert centered image + centered caption (图 X ...)"""
    if not os.path.exists(img_path):
        print(f'WARNING: image not found: {img_path}')
        return
    # image paragraph
    p_img = doc.add_paragraph()
    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p_img.add_run()
    run.add_picture(img_path, width=Inches(width_inches))
    # caption paragraph
    p_cap = doc.add_paragraph()
    p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_cap = p_cap.add_run(caption)
    run_cap.font.size = Pt(9)
    run_cap.font.name = '宋体'
    run_cap.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
    # small gap after caption
    doc.add_paragraph()

# Chapter Title
doc.add_heading('7 随钻围岩状态智能反演三维云图平台构建', level=1)

doc.add_paragraph(
    '本章节主要阐述面向深部钻进过程中围岩状态实时反演、三维可视化与多模型对比分析的实验平台开发工作。'
    '在前文损伤本构建模（第4章）、多场耦合分析（第5章）与深度学习预测模型（第6章）的研究基础上，'
    '本章将前述理论成果进行工程化集成，构建了一套以"随钻参数驱动—围岩状态反演—三维云图呈现—多模型精度对比"'
    '为核心技术路径的一体化数字孪生平台。与前期版本相比，本版本平台在以下方面实现了重要升级：'
    '（1）引入基于Three.js的三维围岩数字孪生体，以顶点着色云图方式实时呈现损伤场、应力场及联合误差场的空间分布；'
    '（2）构建钻进工作面动态演进系统，通过粒子碎片、应力波传播环与损伤区域标记等视觉元素，直观刻画钻头推进过程中围岩状态的动态响应；'
    '（3）建立三模型并行反演精度对比框架，支持损伤、应力、状态三个维度的实时精度评估与模型切换。'
)

# 7.1
doc.add_heading('7.1 平台总体架构设计', level=2)
doc.add_heading('7.1.1 平台定位与设计目标', level=3)

doc.add_paragraph(
    '本平台定位于"随钻参数围岩状态智能反演三维云图"（SRDT, Surrounding Rock Digital Twin），'
    '其核心设计理念是实现从"钻进参数采集 → 多模型联合反演 → 三维云图呈现 → 精度对比决策"的全流程闭环。'
    '平台面向深部煤矿井下钻进作业场景，通过对钻进扭矩、推力、围压等随钻参数的实时采集与智能分析，'
    '反演围岩当前的损伤程度、应力状态及其空间分布特征，并以三维云图的方式在数字孪生体中呈现，'
    '为工程技术人员提供直观、高效的围岩状态感知与决策支持工具。'
)

doc.add_paragraph('平台的设计目标包括：')
for g in [
    '实时性：支持秒级数据刷新，三维云图随钻进进程动态更新，可视化延迟不超过1秒；',
    '多维性：同时呈现反演应力场、损伤场与联合误差场三个维度的围岩状态信息，支持一键切换；',
    '对比性：内置三种不同技术路线的反演模型（V1多尺度ExtraTrees、V2 CNN-BiLSTM、V3 Physics Fusion），支持同一数据源下的模型精度横向对比；',
    '交互性：提供整体云图、剖面模式、等值面三种视图模式，支持旋转、缩放、剖切等多维度交互操作；',
    '演进性：支持钻进全过程的动态回放，可变速播放（0.5x/1x/2x），并支持手动拖拽定位与步进控制。'
]:
    doc.add_paragraph(g, style='List Bullet')

# 7.1.2
doc.add_heading('7.1.2 四层技术架构', level=3)
doc.add_paragraph('平台采用"数据层—模型层—可视化层—交互控制层"四层架构，各层职责明确、接口规范，确保系统的可维护性与可扩展性。')

layers_text = [
    ('数据层（Data Layer）：', '负责多源异构数据的统一接入、解析与状态管理。主要数据源包括：（1）仪表板概览数据（dashboard_summary.json），包含实验统计信息、模型元数据、应力/损伤等级等全局配置；（2）实验清单数据（experiment_manifest.csv），包含各实验样本的围压、损伤等级、源类型等元信息；（3）模型指标数据（overall_metrics.csv / by_file_metrics.csv），包含三模型在各样本上的损伤准确率、应力准确率、状态准确率及F1分数等评价指标；（4）钻进遥测数据（drilling_telemetry.json），为平台核心时序数据源，包含按应力水平（0/20/40 MPa）组织的逐点钻进参数（扭矩、推力、累计钻深、实测损伤、实测应力）与三模型反演输出（预测损伤、预测应力、预测状态、置信度）。以上数据通过Pinia状态管理库中的drillingData Store进行统一加载与响应式管理。'),
    ('模型层（Model Layer）：', '集成三种不同技术路线的反演模型输出结果。V1模型（advancedV1_multiscale_extratrees）基于多尺度特征提取与极端随机树回归，擅长捕捉钻进参数与围岩状态之间的非线性映射关系；V2模型（advancedV2_cnn_bilstm）采用卷积神经网络与双向长短期记忆网络的混合架构，充分利用时序数据的上下文依赖关系；V3模型（advancedV3_physics_fusion）在前两者基础上引入物理约束机制，通过融合Weibull-DP损伤本构的先验知识，确保预测结果不偏离煤岩力学边界。三模型的预测结果已预先计算并存储于遥测数据中，平台通过模型选择器实现运行时切换与对比。'),
    ('可视化层（Visualization Layer）：', '基于Three.js构建三维围岩数字孪生场景，采用圆柱隧道几何体模拟井下巷道与围岩结构，通过逐顶点色彩映射（vertex color mapping）将反演场量数据转换为空间连续的颜色分布。场景中包含巷道开挖面、围岩外壳、当前钻深径向切面、纵向反演剖切带、钻进工作面动态特效（发光环、粒子碎片、应力波传播环、损伤区域标记环、能量流线）以及AE传感器节点、加载方向指示箭头等辅助元素。同时集成了CSS2D空间标注系统，在三维场景中的关键位置实时显示切面数据、钻进数据及各分段的量化指标。色彩映射采用七级渐变色标（由深蓝至红色），分别对应不同的损伤/应力/误差等级。场景外围配置坐标轴指示器、色标图例、场景数据条与模型标签等辅助信息组件。'),
    ('交互控制层（Interaction Control Layer）：', '提供丰富的用户交互手段。三维场景支持OrbitControls（拖拽旋转、滚轮缩放、右键平移），支持自动旋转模式；视图切换支持整体云图、剖面模式与等值面三种显示模式；剖切控制滑块支持0%至100%的渐进式剖面切割；模型选择器与应力水平选择器支持运行时动态切换数据源；钻进演进控制提供播放/暂停、速度调节（0.5x/1x/2x）、时间轴拖拽定位、损伤等级标记点对齐等交互功能。')
]
for title_text, content_text in layers_text:
    p = doc.add_paragraph()
    run = p.add_run(title_text)
    run.bold = True
    p.add_run(content_text)

# ── 图1: architecture diagram ──
insert_figure(doc, 'screenshots/architecture_diagram.png',
              '图 1  平台四层技术架构图', width_inches=5.8)

# 7.2
doc.add_heading('7.2 三维围岩状态云图可视化', level=2)
doc.add_paragraph(
    '三维围岩数字孪生体是平台的核心可视化载体。围岩外壳采用Three.js的CylinderGeometry构建圆柱隧道几何体'
    '（半径3.18单位，长度10.2单位，周向144段，轴向64段），对每个顶点施加正弦微扰位移形成自然岩体表面起伏，'
    '采用MeshPhysicalMaterial材质并启用顶点颜色、双面渲染与半透明效果。场景中还包含巷道开挖面内壁、'
    '当前钻深径向切面（由内径1.08至外径3.2单位的同心环面构成）、纵向反演剖切带（两条80等分段带状面）'
    '及五个损伤等级分段标记环等几何结构。'
)

# ── 图2: main dashboard ──
insert_figure(doc, 'screenshots/screenshot-main.png',
              '图 2  平台主界面——围岩应力场三维云图（整体云图模式，V3模型，围压20 MPa）', width_inches=5.8)
doc.add_paragraph(
    '平台支持反演应力场、损伤场与联合误差场三种场量模式，通过metric参数切换。应力场将0–40 MPa归一化至七级渐变色标'
    '（深蓝至红色），损伤场采用相反色序（红高损伤至蓝低损伤），联合误差场综合损伤与应力预测偏差。'
    '云图颜色随钻进进程动态更新的核心逻辑基于"钻头扰动"假说——钻头前方围岩呈深蓝色原岩状态，'
    '后方按模型反演结果着色，前后之间设平滑过渡带，使围岩状态的"揭露"过程具有物理合理性。'
)
doc.add_paragraph(
    '钻进工作面采用发光环、外晕环及半透明圆盘三层结构作为视觉焦点，配合600粒子碎片系统（模拟岩屑飞溅）、'
    '5个应力波传播环（向外周期性膨胀扩散）、损伤区域标记环（透明度按钻头距离动态变化）及8条能量流线等动态特效，'
    '增强钻头推进过程的表现力与信息传达。平台提供整体云图、剖面模式与等值面三种视图模式，支持OrbitControls旋转缩放、'
    'clippingPlane剖切（0–100%）及CSS2D空间标注（切面数据与分段模型反演值），场景配备色标图例与数据概览条。'
)

# ── 图3: section mode ──
insert_figure(doc, 'screenshots/screenshot-section-mode.png',
              '图 3  剖面模式——径向切面与纵向反演剖切带联合展示', width_inches=5.8)

# 7.3
doc.add_heading('7.3 多模型反演精度评估与交互控制', level=2)
doc.add_paragraph(
    '平台内置V1（多尺度ExtraTrees）、V2（CNN-BiLSTM）与V3（物理融合Physics Fusion）三种反演模型，'
    '以损伤准确率、应力准确率、状态准确率及宏平均F1分数为核心性能指标。'
    '精度仪表盘以三个同心环形进度条分别展示三维度精度，模型对比列表以表格形式并列展示各模型关键指标，'
    '当前选中模型以高亮背景与绿色指示灯标识，切换模型时三维云图、精度仪表盘及场景数据条同步更新。'
    '平台支持按围压（0/20/40 MPa）和损伤等级（D0–D80）联动筛选，'
    '右侧面板设置"关键发现"模块基于模型精度动态评估风险等级（稳定/关注/危险）并自动轮播。'
)

# ── 图4: damage metric + model comparison ──
insert_figure(doc, 'screenshots/screenshot-damage.png',
              '图 4  损伤场模式——三模型精度对比与反演损伤云图（V1模型，围压20 MPa）', width_inches=5.8)

# 7.4
doc.add_heading('7.4 钻进演进控制与数据交互', level=2)
doc.add_paragraph(
    '平台以"钻进深度驱动的数据演进"为核心交互范式，用户通过底部时间轴控制钻进进程（0–125 cm钻深范围），'
    '所有可视化组件同步响应。支持自动播放/暂停（约104秒完成全长回放）、三档变速（0.5x/1x/2x）及手动拖拽定位，'
    '时间轴上设D80–D0五个损伤等级标记点提供关键节点视觉参考。左侧KPI面板实时显示当前扭矩、推力、围压三项参数'
    '（图标+电子字体+动态指示条），SVG趋势图展示扭矩随深度变化（渐变面积+发光折线+光标标记）。'
    '遥测数据通过drillingData Store的computed属性（currentSample/currentPrediction等）实现响应式同步，'
    '围压切换时所有组件自动刷新。'
)

# 7.5
doc.add_heading('7.5 平台技术实现', level=2)
doc.add_paragraph(
    '平台前端基于Vue 3（Composition API）+ Vite + Pinia + Three.js（r160+）+ Tailwind CSS技术栈构建，'
    '路由采用Hash模式（/主页面、/m移动端、/detail多样本对比）。核心代码组织为：'
    'drillingData.js（约180行Pinia Store，管理summary/telemetry等状态及20余个computed属性）、'
    'index.vue（约770行主仪表板，三栏网格布局）及RockCloud3D.vue（约1180行三维场景核心，'
    '含几何构建、动态特效、空间标注、动画循环与资源生命周期管理）。数据流为单向——'
    'loadAll()→computed→props→vertex colors渲染→用户交互→computed更新→watch触发场景刷新。'
    '性能方面实施了颜色更新节流（约20fps）、AdditiveBlending混合、pixelRatio上限限制及完整的onBeforeUnmount dispose流程。'
)

# 7.6
doc.add_heading('7.6 典型应用与效果验证', level=2)
doc.add_paragraph(
    '平台配套dashboard_summary.json、drilling_telemetry.json（按0/20/40 MPa组织的遥测时序数据，含三模型预测输出）、'
    'experiment_manifest.csv及模型指标CSV等预置数据集。运行流程为：启动后并行加载数据并初始化Three.js场景，'
    '用户可切换围压与模型、调整场量与视图模式进行数据探索，通过播放演进回放观察围岩状态动态变化，'
    '暂停后利用悬停标注、旋转剖切、时间轴拖拽等手段进行深度分析。'
    '效果验证表明，V3模型在围压20 MPa条件下输出的损伤场沿钻进方向呈逐级衰减梯度（D80红→D0蓝），'
    '与物理预期一致；扭矩趋势曲线中高损伤区域对应较大钻进阻力（最大约80–90 N·m），符合工程经验规律。'
)

# 7.7
doc.add_heading('7.7 本章小结', level=2)
doc.add_paragraph(
    '本章以Vue3 + Three.js + Pinia为核心技术栈，构建了"数据接入—模型反演—三维可视化—交互控制"的四层架构'
    '随钻围岩状态智能反演三维云图平台。平台通过顶点着色围岩数字孪生体、钻进工作面动态特效及空间标注系统，'
    '实现了围岩损伤场/应力场的多维动态可交互呈现；建立了三模型并行精度评估框架，支持实时对比与联动筛选；'
    '设计了钻进深度驱动的时间轴演进机制。平台集成了前文损伤本构模型、多场耦合分析与深度学习预测模型的输出结果，'
    '为深部煤矿随钻围岩状态智能感知与风险预警提供了工程化技术手段。'
)

# Save
output_path = '新第7章-随钻围岩状态智能反演三维云图平台构建_v2.docx'
doc.save(output_path)
print(f'Word document saved to: {output_path}')
