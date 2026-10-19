export type PartId =
  | 'nose'
  | 'fuselage'
  | 'wing'
  | 'tail'
  | 'engine'
  | 'landingGear'
  | 'avionics'
  | 'flag'

export interface PartInfo {
  id: PartId
  name: string
  subtitle: string
  points: string[]
  autonomy: string
}

export const PARTS: Record<Exclude<PartId, 'flag'>, PartInfo> = {
  nose: {
    id: 'nose',
    name: '机头',
    subtitle: '双人制驾驶舱 · 综合显示',
    points: [
      '采用双人制驾驶舱，主飞控显示与导航信息集中在大屏幕上。',
      '风挡与雷达罩外形经过多次风洞迭代，兼顾视野、雷达性能与气动阻力。',
      '人机界面按中文操作习惯设计，降低机组认知负荷。',
    ],
    autonomy: '中文人机交互与航电显示逻辑由国内团队自主定义。',
  },
  fuselage: {
    id: 'fuselage',
    name: '机身',
    subtitle: '3-3 座椅布局 · 铝锂合金 / 复合材料',
    points: [
      '标准客舱为 3-3 窄体布局，座位 158–168 座，机身长约 38.9 米。',
      '主承力结构使用铝锂合金，部分口盖与整流罩采用复合材料减重。',
      '剖面与对接精度直接决定密封、疲劳寿命与总装效率。',
    ],
    autonomy: '铝锂合金加工与复材构件工艺是机体结构国产化的关键一步。',
  },
  wing: {
    id: 'wing',
    name: '机翼',
    subtitle: '超临界翼型 · 翼梢小翼',
    points: [
      '超临界翼型让巡航时激波更弱，同样油耗下飞得更远。',
      '翼梢小翼削弱翼尖涡，进一步减阻。',
      '从气动外形到结构铺层，机翼是 C919 完全自主设计的核心。',
    ],
    autonomy: '完全自主设计，历时约 5 年、上千次风洞试验。',
  },
  tail: {
    id: 'tail',
    name: '尾翼',
    subtitle: '常规布局 · 舵面控制',
    points: [
      '采用常规尾翼：垂尾保证航向稳定，平尾提供俯仰配平与操纵。',
      '舵面由电传飞控驱动，飞行员指令经飞控计算机分配到作动器。',
      '尾锥还布置 APU，为地面供电与空中备份提供能源。',
    ],
    autonomy: '舵面控制律与飞控余度管理按适航条款自主完成。',
  },
  engine: {
    id: 'engine',
    name: '发动机',
    subtitle: 'LEAP-1C · 长江-1000 展望',
    points: [
      '现役动力为 CFM LEAP-1C 涡扇发动机，大涵道比、低油耗。',
      '短舱、吊挂与推力系统集成需要与机翼气动、结构反复协调。',
      '国产长江-1000（CJ-1000A）正在研制，是动力自主的下一程。',
    ],
    autonomy: '现役为国际合作动力；长江系列指向真正的发动机自主。',
  },
  landingGear: {
    id: 'landingGear',
    name: '起落架',
    subtitle: '前三点式 · 收放与缓冲',
    points: [
      '前三点式布局：前轮转向，主轮承担着陆冲击。',
      '收放机构、舱门时序和缓冲支柱必须在极限载荷下可靠工作。',
      '起落架是典型的高安全、高疲劳件，国产化攻关周期长。',
    ],
    autonomy: '起落架系统国产化是机体配套产业的硬骨头。',
  },
  avionics: {
    id: 'avionics',
    name: '航电系统',
    subtitle: '综合航电 · 电传操纵',
    points: [
      '综合模块化航电把显示、通信、导航与监视放进统一架构。',
      '电传操纵（fly-by-wire）用数字指令代替传统钢索，飞控计算机实时保护包线。',
      '软件与接口需要通过适航审定，是“看不见的自主”。',
    ],
    autonomy: '全中文自主航电软件与飞控控制律是系统级突破。',
  },
}

export const LIVERY_STORIES = [
  '商飞原厂：蓝金线条，对应研制与试飞阶段的“大飞机”身份。',
  '国航·国旗：机身贴国航国旗标，垂尾纯白。',
  '东航：全球首架交付客户涂装，C919 进入航线运营。',
  '自主：深蓝特别涂装，把“自主”写上垂尾。',
]
