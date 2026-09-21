<template>
  <el-drawer v-model="visible" :title="form.code ? '编辑环境' : '创建环境'" size="min(1050px, 100%)" destroy-on-close>
    <div class="section-nav"><button v-for="part in sections" :key="part.id" @click="jump(part.id)">{{ part.label }}</button></div>
    <el-form label-width="112px">
      <div id="env-basic" class="section-title">基本信息</div>
      <el-form-item label="环境名称"><el-input v-model="form.name" placeholder="请输入环境名称" /></el-form-item>
      <el-form-item label="浏览器内核"><el-radio-group v-model="form.browser_kernel" @change="changeKernel"><el-radio value="chrome">Chromium</el-radio><el-radio value="firefox">Firefox</el-radio></el-radio-group></el-form-item>
      <el-form-item label="内核版本"><el-select v-model="form.browser_version" style="width:100%"><el-option v-for="version in kernelVersions" :key="version" :label="version" :value="version" /></el-select></el-form-item>
      <el-form-item label="操作系统"><el-select v-model="form.platform" style="width:100%" @change="changePlatform"><el-option label="Windows" value="Win32" /><el-option label="macOS" value="MacIntel" /><el-option label="Linux" value="Linux x86_64" /></el-select></el-form-item>
      <el-form-item label="备注"><el-input v-model="form.remark" type="textarea" :rows="2" /></el-form-item>
      <div id="env-proxy" class="section-title">代理设置</div>
      <el-form-item label="代理方式"><el-radio-group v-model="form.proxy_mode"><el-radio value="no_proxy">不使用代理</el-radio><el-radio value="existing">选择已有代理</el-radio><el-radio value="custom">自定义代理</el-radio></el-radio-group></el-form-item>
      <el-form-item v-if="form.proxy_mode === 'existing'" label="选择代理"><el-select v-model="form.proxy_code" filterable style="width:100%" placeholder="选择代理"><el-option v-for="proxy in proxies" :key="proxy.code" :label="`${proxy.proxy_name} · ${proxy.proxy_addr || proxy.proxy_api_url}`" :value="proxy.code" /></el-select></el-form-item>
      <template v-if="form.proxy_mode === 'custom'">
        <el-form-item label="代理协议"><el-select v-model="form.custom_proxy_type"><el-option label="HTTP" value="http" /><el-option label="HTTPS" value="https" /><el-option label="SOCKS5" value="socks5" /></el-select></el-form-item>
        <el-form-item label="地址"><el-input v-model="form.custom_proxy_addr" /></el-form-item>
        <el-form-item label="端口"><el-input-number v-model="form.custom_proxy_port" :min="1" :max="65535" :controls="false" /></el-form-item>
        <el-form-item label="用户名"><el-input v-model="form.custom_proxy_username" /></el-form-item>
        <el-form-item label="密码"><el-input v-model="form.custom_proxy_password" type="password" show-password /></el-form-item>
      </template>
      <div id="env-tabs" class="section-title">标签页与启动</div>
      <el-form-item label="启动标签页"><el-switch v-model="form.enable_tabs" /></el-form-item>
      <el-form-item v-if="form.enable_tabs" label="标签页 URL"><el-input v-model="form.tabs" type="textarea" :rows="3" placeholder="每行一个 URL" /><div class="muted">每行填写一个完整 URL；启动时打开。</div></el-form-item>
      <el-form-item label="启动首页"><el-switch v-model="form.open_home_page" /></el-form-item>
      <el-form-item label="启动参数"><el-input v-model="form.launch_args" placeholder="可选，空格分隔" /></el-form-item>
      <el-form-item label="Cookie"><el-input v-model="form.cookie" type="textarea" :rows="3" placeholder='JSON 数组，例如 [{"domain":".example.com","name":"key","value":"value"}]' /><div class="muted">可选；使用 JSON 数组格式，留空表示不导入 Cookie。</div></el-form-item>
      <div id="env-fingerprint" class="section-title">指纹设置</div>
      <el-collapse v-model="fingerprintOpen"><el-collapse-item name="fingerprint" title="展开指纹设置（可选）">
        <div class="toolbar"><el-button :loading="randomizing" @click="randomize">生成随机指纹</el-button><span class="muted">不修改时使用默认随机指纹。</span></div>
        <el-form-item label="User Agent"><el-input v-model="form.user_agent" type="textarea" :rows="2" placeholder="留空自动生成" /></el-form-item>
        <FingerprintFields :fp="form.fingerprint" :platform="form.platform" :kernel="form.browser_kernel" />
      </el-collapse-item></el-collapse>
    </el-form>
    <template #footer><div class="drawer-footer"><el-button @click="visible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">{{ form.code ? '保存修改' : '创建环境' }}</el-button></div></template>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, query } from '../api/client'
import type { Environment, Kernel, KernelCatalog, Page, Proxy } from '../types'
import FingerprintFields from './FingerprintFields.vue'

type Form = { code: string; name: string; browser_kernel: Kernel; browser_version: string; platform: string; remark: string;
  proxy_mode: 'no_proxy' | 'existing' | 'custom'; proxy_code: string; custom_proxy_type: string; custom_proxy_addr: string;
  custom_proxy_port: number; custom_proxy_username: string; custom_proxy_password: string; enable_tabs: boolean; tabs: string;
  open_home_page: boolean; launch_args: string; cookie: string; user_agent: string; fingerprint: Record<string, any> }
const blank = (): Form => ({ code: '', name: '', browser_kernel: 'chrome', browser_version: '', platform: 'Win32', remark: '',
  proxy_mode: 'no_proxy', proxy_code: '', custom_proxy_type: 'http', custom_proxy_addr: '', custom_proxy_port: 1080,
  custom_proxy_username: '', custom_proxy_password: '', enable_tabs: false, tabs: '', open_home_page: true,
  launch_args: '', cookie: '', user_agent: '', fingerprint: {} })
const form = reactive<Form>(blank())
const visible = ref(false), saving = ref(false), randomizing = ref(false), fingerprintOpen = ref<string[]>([])
const kernels = ref<KernelCatalog | null>(null), proxies = ref<Proxy[]>([])
const sections = [{ id: 'env-basic', label: '基本信息' }, { id: 'env-proxy', label: '代理设置' }, { id: 'env-tabs', label: '标签页与启动' }, { id: 'env-fingerprint', label: '指纹设置' }]
const kernelVersions = computed(() => kernels.value?.[form.browser_kernel]?.versions || [])
function jump(id: string) { document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' }) }
function changeKernel() { form.browser_version = kernels.value?.[form.browser_kernel]?.default_version || ''; form.user_agent = '' }
async function changePlatform() { form.user_agent = ''; await randomize() }
async function references() {
  const [catalog, page] = await Promise.all([
    api<KernelCatalog>('/open/settings/kernels'),
    api<Page<Proxy>>(query('/open/proxy/list', { page: 1, page_size: 100, keyword: '' })),
  ])
  kernels.value = catalog; proxies.value = page.items
}
async function create() {
  Object.assign(form, blank()); fingerprintOpen.value = []
  try { await references(); changeKernel(); form.fingerprint = await api<Record<string, any>>('/open/fingerprint/draft', { platform: form.platform }); form.fingerprint.webgl_type = 'real'; form.fingerprint.webgpu_type = 'real'; form.fingerprint.speech_voices = true; visible.value = true }
  catch (error) { ElMessage.error(String(error)) }
}
async function edit(code: string) {
  try {
    const [detail] = await Promise.all([api<Environment>(query('/open/env/detail', { code })), references()])
    const fingerprint = { ...(detail.fingerprint || {}) }
    Object.assign(form, blank(), detail, { proxy_code: detail.proxy_code || '', fingerprint })
    fingerprintOpen.value = []; visible.value = true
  } catch (error) { ElMessage.error(String(error)) }
}
async function randomize() {
  randomizing.value = true
  try { form.fingerprint = await api<Record<string, any>>('/open/fingerprint/draft', { platform: form.platform }); ElMessage.success('已生成随机指纹，保存后生效') }
  catch (error) { ElMessage.error(String(error)) }
  finally { randomizing.value = false }
}
const emit = defineEmits<{ saved: [] }>()
async function save() {
  if (!form.name.trim()) return ElMessage.warning('请输入环境名称')
  if (!form.browser_version) return ElMessage.warning('请选择内核版本')
  if (form.proxy_mode === 'existing' && !form.proxy_code) return ElMessage.warning('请选择代理')
  if (form.proxy_mode === 'custom' && (!form.custom_proxy_addr || !form.custom_proxy_port)) return ElMessage.warning('请填写代理地址和端口')
  if (form.cookie.trim()) {
    try { if (!Array.isArray(JSON.parse(form.cookie))) return ElMessage.warning('Cookie 必须是 JSON 数组') }
    catch { return ElMessage.warning('Cookie JSON 格式不正确') }
  }
  saving.value = true
  try {
    const keys = ['code', 'name', 'browser_kernel', 'browser_version', 'platform', 'remark', 'proxy_mode', 'proxy_code',
      'custom_proxy_type', 'custom_proxy_addr', 'custom_proxy_port', 'custom_proxy_username', 'custom_proxy_password',
      'enable_tabs', 'tabs', 'open_home_page', 'launch_args', 'cookie', 'user_agent'] as const
    const payload: Record<string, any> = Object.fromEntries(keys.map(key => [key, form[key]]))
    payload.fingerprint = { ...form.fingerprint, platform: form.platform }
    if (!payload.user_agent) delete payload.user_agent
    await api(form.code ? '/open/env/update' : '/open/env/create', payload)
    visible.value = false; ElMessage.success('环境已保存'); emit('saved')
  } catch (error) { ElMessage.error(String(error)) }
  finally { saving.value = false }
}
defineExpose({ create, edit })
</script>
