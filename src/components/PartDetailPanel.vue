<script setup lang="ts">
import { PARTS, type PartId } from '../data/parts'

defineProps<{
  partId: Exclude<PartId, 'flag'> | null
}>()

const emit = defineEmits<{
  close: []
}>()
</script>

<template>
  <aside v-if="partId" class="panel">
    <header>
      <p class="kicker">部件科普</p>
      <h2>{{ PARTS[partId].name }}</h2>
      <p class="sub">{{ PARTS[partId].subtitle }}</p>
      <button type="button" class="close" aria-label="关闭" @click="emit('close')">×</button>
    </header>
    <ul>
      <li v-for="point in PARTS[partId].points" :key="point">{{ point }}</li>
    </ul>
    <p class="autonomy">自主性看点 · {{ PARTS[partId].autonomy }}</p>
  </aside>
</template>

<style scoped>
.panel {
  width: min(360px, 92vw);
  background: linear-gradient(180deg, rgba(10, 42, 94, 0.92), rgba(7, 20, 40, 0.94));
  border: 1px solid rgba(216, 169, 78, 0.35);
  color: #f5f7fa;
  padding: 22px 22px 20px;
  backdrop-filter: blur(12px);
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.35);
}
header {
  position: relative;
  padding-right: 28px;
}
.kicker {
  margin: 0;
  letter-spacing: 0.28em;
  font-size: 11px;
  color: #d8a94e;
  text-transform: uppercase;
}
h2 {
  margin: 8px 0 4px;
  font-size: 28px;
  font-family: 'Songti SC', 'Source Han Serif SC', serif;
  color: #fff;
}
.sub {
  margin: 0 0 12px;
  color: #c9d4e5;
  font-size: 13px;
}
.close {
  position: absolute;
  right: 0;
  top: 0;
  border: 0;
  background: transparent;
  color: #f5f7fa;
  font-size: 22px;
  cursor: pointer;
}
ul {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 8px;
  font-size: 14px;
  line-height: 1.55;
  color: #e6edf7;
}
.autonomy {
  margin: 16px 0 0;
  padding-top: 12px;
  border-top: 1px solid rgba(216, 169, 78, 0.25);
  font-size: 13px;
  color: #d8a94e;
  line-height: 1.55;
}
</style>
