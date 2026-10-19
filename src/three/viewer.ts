import {
  AmbientLight,
  Box3,
  Color,
  DirectionalLight,
  GridHelper,
  Group,
  HemisphereLight,
  Mesh,
  Material,
  MeshLambertMaterial,
  DoubleSide,
  MeshStandardMaterial,
  PerspectiveCamera,
  PlaneGeometry,
  Raycaster,
  Scene,
  Texture,
  TextureLoader,
  Vector2,
  Vector3,
  WebGLRenderer,
  PMREMGenerator,
  type Object3D,
} from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { PARTS, type PartId } from '../data/parts'
import { LIVERIES, type Livery } from './liveries'

const HIGHLIGHT = 0xd8a94e

function idFromName(name: string): PartId | null {
  const value = name.toLowerCase()
  if (value.startsWith('flag')) return 'flag'
  if (value.startsWith('gear')) return 'landingGear'
  if (value.startsWith('wing')) return 'wing'
  if (value.startsWith('engine') || value.startsWith('pylon')) return 'engine'
  if (value.startsWith('stab') || value.startsWith('vertical') || value.startsWith('rudder') || value.startsWith('tail')) return 'tail'
  if (value.startsWith('windshield')) return 'avionics'
  if (value.startsWith('nose') || value.startsWith('brow')) return 'nose'
  if (
    value.startsWith('fuselage') ||
    value.startsWith('cheat') ||
    value.startsWith('stripe') ||
    value.startsWith('gold') ||
    value.startsWith('window') ||
    value.startsWith('title')
  ) {
    return 'fuselage'
  }
  return null
}

function slotFromMaterial(name: string) {
  const value = name.toLowerCase()
  if (value.endsWith('_metal')) return null
  if (value.startsWith('skin')) return 'skin'
  if (value.startsWith('navy')) return 'navy'
  if (value.startsWith('stripe') || value.startsWith('gold')) return 'stripe'
  if (value.startsWith('rudder')) return 'rudder'
  if (value.startsWith('enginelip')) return 'engineLip'
  if (value.startsWith('engine') || value.startsWith('pylon')) return 'engine'
  return null
}

function slotColor(slot: string, livery: Livery): number | null {
  if (slot === 'skin') return livery.fuselage
  if (slot === 'navy') return livery.accent
  if (slot === 'stripe') return livery.gold
  if (slot === 'engine') return livery.engine
  if (slot === 'engineLip') return livery.engineLip
  if (slot === 'rudder') return livery.rudder
  return null
}

function applyGlbLivery(
  root: Object3D,
  livery: Livery,
  fuselageTexCache: Map<string, Texture>,
) {
  const isComac = livery.id === 'comac'
  const whiteMappedNonSkin =
    livery.id === 'comac' || livery.id === 'airchina' || livery.id === 'donghang'
  root.traverse((obj) => {
    const mesh = obj as Mesh
    if (!mesh.isMesh) return
    const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
    for (const raw of materials) {
      const mat = raw as MeshStandardMaterial
      if (!mat.color) continue
      const slot =
        (mat.userData.liverySlot as string | undefined) ??
        slotFromMaterial(mat.name ?? '')
      if (!slot) continue
      const color = slotColor(slot, livery)
      if (color == null) continue
      const origMap = mat.userData.origMap ?? null
      const matName = (mat.name ?? '').toLowerCase()
      const isSkinFuselage = matName === 'skin_fuselage' || matName.startsWith('skin_fuselage')

      if (isSkinFuselage) {
        const fm = livery.fuselageMap
        if (fm === 'orig') {
          mat.map = origMap
          mat.color.set(0xffffff)
        } else if (typeof fm === 'string') {
          mat.map = fuselageTexCache.get(fm) ?? null
          mat.color.set(0xffffff)
        } else {
          mat.map = null
          mat.color.set(color)
        }
      } else if (origMap && matName.startsWith('skin')) {
        if (isComac) {
          mat.map = origMap
          mat.color.set(0xffffff)
        } else {
          mat.map = null
          mat.color.set(color)
        }
      } else if (origMap) {
        mat.map = origMap
        if (whiteMappedNonSkin) {
          mat.color.set(0xffffff)
        } else {
          mat.color.set(color)
        }
      } else {
        mat.color.set(color)
      }
      mat.needsUpdate = true
    }
  })
}

export interface ViewerEvents {
  onHover: (partId: PartId | null, name: string | null) => void
  onSelect: (partId: Exclude<PartId, 'flag'> | null) => void
  onLivery: (livery: Livery, index: number, story: string) => void
  onLoadProgress?: (percent: number | null) => void
  onLoadError?: (message: string) => void
  onLoadComplete?: () => void
}

export function mountAircraftViewer(canvas: HTMLCanvasElement, events: ViewerEvents) {
  const scene = new Scene()
  scene.background = new Color(0x071428)

  const camera = new PerspectiveCamera(42, 1, 0.1, 400)
  camera.position.set(28, 12, 34)

  const renderer = new WebGLRenderer({ canvas, antialias: true, alpha: false, preserveDrawingBuffer: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5))
  renderer.setClearColor(0x071428)

  const pmrem = new PMREMGenerator(renderer)
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture

  const controls = new OrbitControls(camera, canvas)
  controls.enableDamping = true
  controls.dampingFactor = 0.06
  controls.enableZoom = true
  controls.enablePan = false
  controls.minPolarAngle = 0
  controls.maxPolarAngle = Math.PI
  controls.rotateSpeed = 0.7
  controls.zoomSpeed = 0.9
  controls.autoRotate = false
  controls.autoRotateSpeed = 0
  controls.target.set(0, 0, 0)

  scene.add(new AmbientLight(0x9eb6d4, 0.45))
  const hemi = new HemisphereLight(0x8eb4ff, 0x1a1c22, 0.7)
  scene.add(hemi)
  const key = new DirectionalLight(0xffffff, 1.55)
  key.position.set(22, 28, 16)
  scene.add(key)
  const rim = new DirectionalLight(0x6ea8ff, 0.55)
  rim.position.set(-18, 10, -22)
  scene.add(rim)

  const floor = new Mesh(
    new PlaneGeometry(120, 120),
    new MeshLambertMaterial({ color: 0x0b1a33 }),
  )
  floor.rotation.x = -Math.PI / 2
  floor.position.y = -4.4
  scene.add(floor)

  const grid = new GridHelper(80, 40, 0xd8a94e, 0x16325c)
  grid.position.y = -4.38
  const gridMat = grid.material as Material
  gridMat.transparent = true
  gridMat.opacity = 0.35
  scene.add(grid)

  const aircraft = new Group()
  aircraft.name = 'C919'
  scene.add(aircraft)
  const fuselageTexCache = new Map<string, Texture>()
  const center = new Vector3()
  let radius = 30

  const frameModel = () => {
    const box = new Box3().setFromObject(aircraft)
    if (box.isEmpty()) return
    box.getCenter(center)
    const size = box.getSize(new Vector3())
    radius = Math.max(size.x, size.y, size.z) * 1.35
    controls.target.copy(center)
    controls.minDistance = radius * 0.28
    controls.maxDistance = radius * 4
    camera.position.copy(center).add(new Vector3(radius * 0.72, radius * 0.34, radius * 0.62))
    floor.position.y = box.min.y - 0.05
    grid.position.y = box.min.y
    controls.update()
  }

  const tagMesh = (mesh: Mesh) => {
    let partId: PartId | null = null
    let slot: string | null = null
    let cursor: Object3D | null = mesh
    while (cursor) {
      partId = partId ?? idFromName(cursor.name)
      const extra = cursor.userData as { partId?: PartId; liverySlot?: string }
      partId = partId ?? extra.partId ?? null
      slot = slot ?? extra.liverySlot ?? null
      cursor = cursor.parent
    }
    const source = mesh.material
    const cloned = Array.isArray(source) ? source.map((item) => item.clone()) : source.clone()
    mesh.material = cloned
    const mats = Array.isArray(cloned) ? cloned : [cloned]
    const first = mats[0]
    for (const raw of mats) {
      const mat = raw as MeshStandardMaterial
      mat.userData.origMap = mat.map ?? null
      mat.userData.liverySlot = slotFromMaterial(mat.name ?? '')
    }
    slot = slot ?? (first ? (first as MeshStandardMaterial).userData.liverySlot : null) ?? slotFromMaterial(first?.name ?? '')
    // Thin extruded surfaces (fin/wing/stab/decals) must render both faces
    const n = mesh.name.toLowerCase()
    const doubleSided =
      n.startsWith('vertical') ||
      n.startsWith('rudder') ||
      n.startsWith('wing') ||
      n.startsWith('stab') ||
      n.startsWith('title') ||
      n.startsWith('tailmark') ||
      n.startsWith('flag')
    if (doubleSided) {
      for (const raw of mats) {
        ;(raw as MeshStandardMaterial).side = DoubleSide
      }
    }
    mesh.userData.partId = partId
    mesh.userData.liverySlot = slot
  }

  events.onLoadProgress?.(0)
  new GLTFLoader().load(
    import.meta.env.BASE_URL + 'models/c919.glb',
    (gltf) => {
      aircraft.add(gltf.scene)
      aircraft.traverse((obj) => {
        const mesh = obj as Mesh
        if (mesh.isMesh) tagMesh(mesh)
      })

      const skinState: { orig: Texture | null } = { orig: null }
      aircraft.traverse((obj) => {
        const mesh = obj as Mesh
        if (!mesh.isMesh) return
        const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
        for (const raw of mats) {
          const mat = raw as MeshStandardMaterial
          const n = (mat.name ?? '').toLowerCase()
          if (n === 'skin_fuselage' || n.startsWith('skin_fuselage')) {
            skinState.orig = (mat.userData.origMap as Texture | null) ?? null
          }
        }
      })

      const texLoader = new TextureLoader()
      const maxAniso = renderer.capabilities.getMaxAnisotropy()
      for (const liv of LIVERIES) {
        if (typeof liv.fuselageMap !== 'string') continue
        const url = liv.fuselageMap
        if (fuselageTexCache.has(url)) continue
        const t = texLoader.load(import.meta.env.BASE_URL + url)
        const o = skinState.orig
        if (o) {
          t.flipY = o.flipY
          t.colorSpace = o.colorSpace
          t.wrapS = o.wrapS
          t.wrapT = o.wrapT
          if ('channel' in o) (t as Texture & { channel: number }).channel = (o as Texture & { channel: number }).channel
        }
        t.anisotropy = maxAniso
        fuselageTexCache.set(url, t)
      }

      applyGlbLivery(aircraft, LIVERIES[0], fuselageTexCache)
      frameModel()
      events.onLoadProgress?.(100)
      events.onLoadComplete?.()
    },
    (xhr) => {
      if (xhr.lengthComputable && xhr.total > 0) {
        events.onLoadProgress?.(Math.min(99, Math.round((xhr.loaded / xhr.total) * 100)))
      } else {
        events.onLoadProgress?.(null)
      }
    },
    (err) => {
      console.error('[C919] GLB load failed', err)
      events.onLoadError?.('模型加载失败：无法读取 models/c919.glb，请检查文件是否存在后刷新重试。')
    },
  )

  const raycaster = new Raycaster()
  const pointer = new Vector2()
  let hovered: Mesh | null = null
  let selectedId: PartId | null = null
  let liveryIndex = 0
  const pointerDown = { x: 0, y: 0 }

  const pickable = (obj: Object3D): Mesh | null => {
    let cur: Object3D | null = obj
    while (cur) {
      if ((cur as Mesh).isMesh && cur.userData.partId) return cur as Mesh
      cur = cur.parent
    }
    return null
  }

  const setEmissive = (mesh: Mesh, hex: number, intensity: number) => {
    const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
    for (const raw of mats) {
      const mat = raw as MeshStandardMaterial
      if (!mat.emissive) continue
      mat.emissive = new Color(hex)
      mat.emissiveIntensity = intensity
    }
  }

  const highlightPart = (partId: PartId | null, extra: Mesh | null) => {
    aircraft.traverse((obj) => {
      const m = obj as Mesh
      if (!m.isMesh) return
      const on = partId && m.userData.partId === partId
      setEmissive(m, on ? HIGHLIGHT : 0x000000, on ? 0.42 : 0)
    })
    if (extra && extra.userData.partId === 'flag') setEmissive(extra, HIGHLIGHT, 0.55)
  }

  const partName = (id: PartId | null) => {
    if (!id) return null
    if (id === 'flag') return '机身国旗 · 涂装彩蛋'
    return PARTS[id].name
  }

  const intersect = (event: PointerEvent) => {
    const rect = canvas.getBoundingClientRect()
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
    pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
    raycaster.setFromCamera(pointer, camera)
    const hits = raycaster.intersectObject(aircraft, true)
    return hits[0] ? pickable(hits[0].object) : null
  }

  const onPointerMove = (event: PointerEvent) => {
    if (event.buttons) return
    const hit = intersect(event)
    if (hovered === hit) return
    hovered = hit
    const id = (hit?.userData.partId as PartId | undefined) ?? null
    canvas.style.cursor = id ? 'pointer' : 'grab'
    events.onHover(id, partName(id))
    highlightPart(id ?? selectedId, hit)
  }

  const onPointerDown = (event: PointerEvent) => {
    pointerDown.x = event.clientX
    pointerDown.y = event.clientY
  }

  const onPointerUp = (event: PointerEvent) => {
    const dx = event.clientX - pointerDown.x
    const dy = event.clientY - pointerDown.y
    if (dx * dx + dy * dy > 16) return
    const hit = intersect(event)
    const id = hit?.userData.partId as PartId | undefined
    if (!id) {
      selectPart(null)
      return
    }
    if (id === 'flag') {
      cycleLivery()
      highlightPart('flag', hit)
      return
    }
    selectPart(id)
  }

  function selectPart(id: Exclude<PartId, 'flag'> | null) {
    selectedId = id
    highlightPart(id, null)
    events.onSelect(id)
  }

  function cycleLivery() {
    liveryIndex = (liveryIndex + 1) % LIVERIES.length
    const livery = LIVERIES[liveryIndex]
    applyGlbLivery(aircraft, livery, fuselageTexCache)
    events.onLivery(livery, liveryIndex, livery.name)
  }

  const onPointerLeave = () => {
    hovered = null
    events.onHover(null, null)
    highlightPart(selectedId, null)
  }

  canvas.addEventListener('pointermove', onPointerMove)
  canvas.addEventListener('pointerdown', onPointerDown)
  canvas.addEventListener('pointerup', onPointerUp)
  canvas.addEventListener('pointerleave', onPointerLeave)
  canvas.style.cursor = 'grab'

  const setView = (kind: 'front' | 'side' | 'top' | 'iso') => {
    controls.minPolarAngle = 0
    controls.maxPolarAngle = Math.PI
    const offset = {
      front: new Vector3(0, radius * 0.15, -radius * 1.7),
      side: new Vector3(radius * 1.7, radius * 0.2, 0),
      top: new Vector3(0, radius * 1.9, 0.02),
      iso: new Vector3(radius, radius * 0.42, radius * 0.2),
    }[kind]
    camera.position.copy(center).add(offset)
    controls.target.copy(center)
    controls.update()
  }

  const resize = () => {
    const { clientWidth, clientHeight } = canvas
    if (clientWidth === 0 || clientHeight === 0) return
    camera.aspect = clientWidth / clientHeight
    camera.updateProjectionMatrix()
    renderer.setSize(clientWidth, clientHeight, false)
  }

  const ro = new ResizeObserver(resize)
  ro.observe(canvas)
  resize()

  let frame = 0
  const tick = () => {
    frame = requestAnimationFrame(tick)
    controls.update()
    renderer.render(scene, camera)
  }
  tick()

  const setLiveryCam = (kind: 'leftFront' | 'rightFront') => {
    const sx = kind === 'leftFront' ? 0.72 : -0.72
    camera.position.copy(center).add(new Vector3(radius * sx, radius * 0.34, radius * 0.62))
    controls.target.copy(center)
    controls.update()
    renderer.render(scene, camera)
  }

  const api = {
    setView,
    selectPart,
    cycleLivery,
    setLiveryCam,
    dispose() {
      cancelAnimationFrame(frame)
      ro.disconnect()
      canvas.removeEventListener('pointermove', onPointerMove)
      canvas.removeEventListener('pointerdown', onPointerDown)
      canvas.removeEventListener('pointerup', onPointerUp)
      canvas.removeEventListener('pointerleave', onPointerLeave)
      controls.dispose()
      renderer.dispose()
    },
  }
  ;(window as unknown as { __c919Viewer?: typeof api }).__c919Viewer = api
  return api
}
