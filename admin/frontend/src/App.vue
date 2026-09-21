<template>
  <div class="shell">
    <aside class="sidebar" :class="{ open: menuOpen }">
      <div class="brand"><span class="brand-mark">Q</span><div>启元浏览器<small>本地管理后台</small></div></div>
      <nav>
        <RouterLink to="/environments" @click="menuOpen = false">环境管理</RouterLink>
        <RouterLink to="/proxies" @click="menuOpen = false">代理管理</RouterLink>
        <RouterLink to="/extensions" @click="menuOpen = false">扩展管理</RouterLink>
        <RouterLink v-if="showSettings" to="/settings" @click="menuOpen = false">系统设置</RouterLink>
      </nav>
    </aside>
    <div v-if="menuOpen" class="backdrop" @click="menuOpen = false"></div>
    <main class="main">
      <header class="topbar"><el-button text class="menu-trigger" @click="menuOpen = !menuOpen">☰</el-button><span>本地浏览器管理</span><span class="topbar-right">127.0.0.1</span></header>
      <div class="page"><RouterView /></div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from './api/client'
const menuOpen = ref(false)
const showSettings = ref(false)
onMounted(async () => {
  try { const capabilities = await api<{ local_settings: boolean }>('/open/settings/capabilities'); showSettings.value = capabilities.local_settings } catch { showSettings.value = false }
})
</script>
