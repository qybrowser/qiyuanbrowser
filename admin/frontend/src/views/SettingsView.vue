<template>
  <div class="page-title"><div><h1>系统设置</h1><p>浏览器资源目录与已安装内核</p></div></div>
  <div class="panel">
    <div class="section-title">浏览器应用数据目录</div>
    <el-input v-model="path" placeholder="%USERPROFILE%\.qiyuan" style="max-width:720px" />
    <p class="muted">默认目录为用户目录下的 .qiyuan；自定义目录需包含 client、config、extends。</p>
    <div class="toolbar"><el-button type="primary" :loading="saving" @click="save">保存并检测</el-button><el-button @click="restore">恢复默认目录</el-button><el-button @click="load">重新检测</el-button></div>
    <el-alert v-if="settings" :title="settings.valid ? '目录可用' : '目录缺少必需资源'" :type="settings.valid ? 'success' : 'warning'" :closable="false" />
    <div v-if="settings" class="section-title">内核版本</div>
    <el-table v-if="settings" :data="kernelRows" border>
      <el-table-column prop="label" label="内核" width="150" />
      <el-table-column prop="configured" label="配置版本" />
      <el-table-column prop="installed" label="已安装版本" />
      <el-table-column prop="defaultVersion" label="默认版本" />
    </el-table>
    <p v-if="settings?.missing_versions.length" class="muted">缺失：{{ settings.missing_versions.join('、') }}</p>
    <div class="section-title">更新内核</div>
    <el-form inline>
      <el-form-item label="内核"><el-select v-model="kernel" style="width:140px"><el-option label="Chromium" value="chrome" /><el-option label="Firefox" value="firefox" /></el-select></el-form-item>
      <el-form-item label="版本"><el-input v-model="version" placeholder="例如 150.0.7871.116" /></el-form-item>
      <el-form-item><el-checkbox v-model="setDefault">设为默认版本</el-checkbox></el-form-item>
      <el-form-item><input ref="fileInput" type="file" accept=".zip,application/zip" @change="selectFile" /></el-form-item>
      <el-form-item><el-button type="primary" :loading="uploading" :disabled="!file" @click="upload">上传并安装</el-button></el-form-item>
    </el-form>
    <p class="muted">上传 ZIP 后会解压到浏览器应用数据目录的 client/&lt;版本&gt;；同版本允许覆盖，但运行中的内核不应覆盖。</p>
    <div class="section-title">客户端 Token</div>
    <el-input v-model="token" type="password" show-password placeholder="输入客户端 Token" style="max-width:480px" />
    <div class="toolbar"><el-button type="primary" :loading="tokenSaving" @click="saveToken">更新 Token</el-button></div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, apiForm } from '../api/client'
import type { BrowserSettings, Kernel } from '../types'

const path = ref('')
const settings = ref<BrowserSettings | null>(null)
const saving = ref(false)
const kernelRows = computed(() => (['chrome', 'firefox'] as Kernel[]).map(kernel => ({
  label: kernel === 'chrome' ? 'Chromium' : 'Firefox',
  configured: settings.value?.kernels[kernel].versions.join('、') || '—',
  installed: settings.value?.kernels[kernel].installed_versions.join('、') || '未安装',
  defaultVersion: settings.value?.kernels[kernel].default_version || '—',
})))
const kernel = ref<Kernel>('chrome')
const version = ref('')
const setDefault = ref(false)
const file = ref<File | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const token = ref('')
const tokenSaving = ref(false)
function selectFile(event: Event) { file.value = (event.target as HTMLInputElement).files?.[0] || null }
async function upload() {
  if (!file.value || !version.value.trim()) { ElMessage.warning('请选择 ZIP 并填写版本号'); return }
  uploading.value = true
  try { const form = new FormData(); form.append('kernel', kernel.value); form.append('version', version.value.trim()); form.append('set_default', String(setDefault.value)); form.append('file', file.value); settings.value = await apiForm<BrowserSettings>('/open/settings/kernels/upload', form); ElMessage.success('内核安装成功'); file.value = null; if (fileInput.value) fileInput.value.value = '' }
  catch (error) { ElMessage.error(String(error)) }
  finally { uploading.value = false }
}
async function saveToken() {
  if (!token.value.trim()) { ElMessage.warning('Token 不能为空'); return }
  tokenSaving.value = true
  try { await api('/open/settings/token', { token: token.value.trim() }); ElMessage.success('Token 已更新') }
  catch (error) { ElMessage.error(String(error)) }
  finally { tokenSaving.value = false }
}
async function load() {
  try {
    const [browser, tokenData] = await Promise.all([
      api<BrowserSettings>('/open/settings/browser'),
      api<{ token: string }>('/open/settings/token'),
    ])
    settings.value = browser
    path.value = browser.browser_app_data_dir
    token.value = tokenData.token || ''
  }
  catch (error) { ElMessage.error(String(error)) }
}
async function save() {
  saving.value = true
  try { settings.value = await api<BrowserSettings>('/open/settings/browser', { browser_app_data_dir: path.value }); ElMessage.success('设置已保存') }
  catch (error) { ElMessage.error(String(error)) }
  finally { saving.value = false }
}
async function restore() { path.value = ''; await save(); if (settings.value) path.value = settings.value.browser_app_data_dir }
onMounted(load)
</script>
