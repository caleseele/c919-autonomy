export type LiveryId = 'comac' | 'airchina' | 'donghang' | 'autonomy'

export interface Livery {
  id: LiveryId
  name: string
  fuselage: number
  accent: number
  gold: number
  cheatline: number
  engine: number
  engineLip: number
  rudder: number
  tailMark: string
  /** 'orig' = packed glb map; string = public URL; null = solid color */
  fuselageMap: 'orig' | string | null
}

const COMAC_SLOTS = {
  fuselage: 0xf4f7fb,
  accent: 0x0a2a5e,
  gold: 0xd8a94e,
  cheatline: 0x0a2a5e,
  engine: 0xcfd6de,
  engineLip: 0x1a1d24,
} as const

export const LIVERIES: Livery[] = [
  {
    id: 'comac',
    name: '中国商飞原厂涂装',
    ...COMAC_SLOTS,
    rudder: 0x56a73c,
    tailMark: 'COMAC',
    fuselageMap: 'orig',
  },
  {
    id: 'airchina',
    name: '国航·国旗',
    ...COMAC_SLOTS,
    rudder: 0xffffff,
    tailMark: 'CA',
    fuselageMap: 'tex/c919_livery_airchina.jpg',
  },
  {
    id: 'donghang',
    name: '东航交付涂装',
    ...COMAC_SLOTS,
    rudder: 0xffffff,
    tailMark: 'MU',
    fuselageMap: 'tex/c919_livery_donghang.jpg',
  },
  {
    id: 'autonomy',
    name: '「自主」特别涂装',
    fuselage: 0x0d2248,
    accent: 0xd8a94e,
    gold: 0xd6392f,
    cheatline: 0xd8a94e,
    engine: 0x1c2430,
    engineLip: 0xd8a94e,
    rudder: 0xd8a94e,
    tailMark: '自主',
    fuselageMap: null,
  },
]
