<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { LIVERY_STORIES, PARTS, type PartId } from '../data/parts'
import { mountAircraftViewer } from '../three/viewer'
import PartDetailPanel from './PartDetailPanel.vue'

const canvas = ref<HTMLCanvasElement | null>(null)
const hoverName = ref<string | null>(null)
const selectedId = ref<Exclude<PartId, 'flag'> | null>(null)
const toast = ref<string | null>(null)
const loadMessage = ref<string | null>('模型加载中…')
const loadFailed = ref(false)
let api: ReturnType<typeof mountAircraftViewer> | null = null
let toastTimer = 0

function showToast(message: string, ms = 4200) {
  toast.value = message
  window.clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => {
    toast.value = null
  }, ms)
}

onMounted(() => {
  if (!canvas.value) return
  api = mountAircraftViewer(canvas.value, {
    onHover(_partId, name) {
      hoverName.value = name
    },
    onSelect(partId) {
      selectedId.value = partId
    },
    onLivery(next, index) {
      showToast(`${next.name}（${LIVERY_STORIES[index]}）`)
    },
    onLoadProgress(percent) {
      if (loadFailed.value) return
      loadMessage.value = percent == null ? '模型加载中…' : `模型加载中 ${percent}%`
    },
    onLoadComplete() {
      loadFailed.value = false
      loadMessage.value = null
    },
    onLoadError(message) {
      loadFailed.value = true
      loadMessage.value = message
      showToast(message, 8000)
    },
  })
})

onBeforeUnmount(() => {
  window.clearTimeout(toastTimer)
  api?.dispose()
})

const partIds = Object.keys(PARTS) as Array<Exclude<PartId, 'flag'>>

function setView(kind: 'front' | 'side' | 'top' | 'iso') {
  api?.setView(kind)
}

function pickPart(id: Exclude<PartId, 'flag'>) {
  api?.selectPart(id)
}

function clearPart() {
  api?.selectPart(null)
}

function cycleLivery() {
  api?.cycleLivery()
}
</script>

<template>
  <section class="stage">
    <canvas ref="canvas" class="view" />

    <div class="hud top-left">
      <p class="chapter">第二章 · 大国之翼</p>
      <h1>C919 三维结构</h1>
      <p class="hint">拖拽可 360° 查看 · 滚轮缩放 · 点击部件弹出说明 · 「国旗涂装」轮换：商飞原厂 → 国航·国旗 → 东航 → 自主</p>
    </div>

    <div class="hud parts">
      <button
        v-for="id in partIds"
        :key="id"
        type="button"
        :class="{ on: selectedId === id }"
        @click="pickPart(id)"
      >
        {{ PARTS[id].name }}
      </button>
      <button type="button" class="egg" @click="cycleLivery">国旗涂装</button>
    </div>

    <div class="hud views">
      <button type="button" @click="setView('iso')">斜视</button>
      <button type="button" @click="setView('front')">前视</button>
      <button type="button" @click="setView('side')">侧视</button>
      <button type="button" @click="setView('top')">俯视</button>
    </div>

    <p v-if="loadMessage" class="hud load" :class="{ error: loadFailed }">{{ loadMessage }}</p>
    <p v-if="hoverName && !loadMessage" class="hud hover">{{ hoverName }}</p>
    <p v-if="toast" class="hud toast">{{ toast }}</p>

    <div class="hud panel-wrap">
      <PartDetailPanel :part-id="selectedId" @close="clearPart" />
    </div>
  </section>
</template>

<style scoped>
.stage {
  position: relative;
  width: 100%;
  height: 100svh;
  overflow: hidden;
  background: #071428;
}
.view {
  width: 100%;
  height: 100%;
  display: block;
}
.hud {
  position: absolute;
  z-index: 2;
  pointer-events: none;
}
.top-left {
  left: 28px;
  top: 24px;
  color: #f5f7fa;
}
.chapter {
  margin: 0;
  letter-spacing: 0.32em;
  font-size: 12px;
  color: #d8a94e;
}
h1 {
  margin: 8px 0 6px;
  font-size: 36px;
  font-family: 'Songti SC', 'Source Han Serif SC', serif;
  font-weight: 600;
  color: #fff;
}
.hint {
  margin: 0;
  max-width: 420px;
  color: #c5d0e0;
  font-size: 13px;
  line-height: 1.5;
}
.parts,
.views {
  display: flex;
  gap: 8px;
  pointer-events: auto;
}
.parts {
  left: 28px;
  top: 148px;
  flex-wrap: wrap;
  max-width: 420px;
}
.parts button,
.views button {
  border: 1px solid rgba(216, 169, 78, 0.45);
  background: rgba(10, 42, 94, 0.72);
  color: #f5f7fa;
  padding: 8px 14px;
  cursor: pointer;
  letter-spacing: 0.12em;
  font-size: 12px;
}
.parts button.on {
  background: #d8a94e;
  color: #071428;
}
.parts button.egg {
  border-color: #d6392f;
}
.views {
  left: 28px;
  bottom: 28px;
}
.hover {
  left: 50%;
  bottom: 32px;
  transform: translateX(-50%);
  margin: 0;
  padding: 8px 14px;
  border: 1px solid rgba(216, 169, 78, 0.4);
  background: rgba(7, 20, 40, 0.72);
  color: #d8a94e;
  font-size: 13px;
}
.load {
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  margin: 0;
  max-width: 420px;
  padding: 14px 20px;
  border: 1px solid rgba(216, 169, 78, 0.45);
  background: rgba(7, 20, 40, 0.88);
  color: #d8a94e;
  font-size: 14px;
  line-height: 1.5;
  letter-spacing: 0.08em;
  text-align: center;
}
.load.error {
  border-color: rgba(214, 57, 47, 0.7);
  background: rgba(214, 57, 47, 0.92);
  color: #fff;
}
.toast {
  right: 28px;
  top: 24px;
  left: auto;
  margin: 0;
  max-width: 360px;
  padding: 12px 16px;
  background: rgba(214, 57, 47, 0.9);
  color: #fff;
  font-size: 13px;
  line-height: 1.45;
}
.panel-wrap {
  right: 24px;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: auto;
}
@media (max-width: 720px) {
  .top-left,
  .views {
    left: 16px;
  }
  h1 {
    font-size: 26px;
  }
  .panel-wrap {
    right: 12px;
    left: 12px;
    top: auto;
    bottom: 72px;
    transform: none;
  }
}
</style>
