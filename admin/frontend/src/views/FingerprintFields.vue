<template>
  <div class="fingerprint-fields">
    <el-divider content-position="left">网络与位置</el-divider>
    <el-form-item label="WebRTC"><el-select v-model="fp.webrtc"><el-option label="基于 IP" value="ip" /><el-option label="真实" value="real" /><el-option label="禁用" value="disabled" /><el-option label="转发" value="transform_google" /></el-select></el-form-item>
    <el-form-item label="时区"><el-select v-model="fp.timezone_type"><el-option label="基于 IP" value="ip" /><el-option label="真实" value="real" /><el-option label="自定义" value="custom" /></el-select></el-form-item>
    <el-form-item v-if="fp.timezone_type === 'custom'" label="时区值"><el-input v-model="fp.timezone_value" placeholder="如 Asia/Singapore" /></el-form-item>
    <el-form-item label="地理位置"><el-select v-model="fp.geo_location_type"><el-option label="基于 IP" value="ip" /><el-option label="真实" value="real" /><el-option label="自定义" value="custom" /></el-select></el-form-item>
    <el-form-item v-if="fp.geo_location_type === 'custom'" label="经纬度"><el-input v-model="longitude" placeholder="经度" /><el-input v-model="latitude" placeholder="纬度" style="margin-top:6px" /></el-form-item>
    <el-form-item label="语言"><el-select v-model="fp.language_type"><el-option label="基于 IP" value="ip" /><el-option label="真实" value="real" /><el-option label="自定义" value="custom" /></el-select></el-form-item>
    <el-form-item v-if="fp.language_type === 'custom'" label="语言列表"><el-input v-model="fp.language_value" placeholder="zh-CN,en-US，英文逗号分隔" /></el-form-item>
    <el-form-item label="界面语言"><el-select v-model="fp.ui_language_type"><el-option label="基于语言" value="language" /><el-option label="真实" value="real" /><el-option label="自定义" value="custom" /></el-select></el-form-item>
    <el-form-item v-if="fp.ui_language_type === 'custom'" label="界面语言值"><el-input v-model="fp.ui_language_value" placeholder="如 zh-CN" /></el-form-item>
    <el-divider content-position="left">图形与显示</el-divider>
    <el-form-item label="WebGL"><el-select v-model="fp.webgl_type"><el-option label="真实" value="real" /><el-option label="自定义" value="custom" /><el-option label="禁用" value="disabled" /></el-select></el-form-item>
    <template v-if="fp.webgl_type === 'custom'">
      <el-form-item label="WebGL Vendor"><el-select v-model="vendor" filterable allow-create default-first-option placeholder="选择或输入厂商" @change="pickVendor"><el-option v-for="item in gpuVendors" :key="item.webgl_vendor" :label="item.webgl_vendor" :value="item.webgl_vendor" /></el-select></el-form-item>
      <el-form-item label="WebGL Renderer"><el-select v-model="renderer" filterable allow-create default-first-option placeholder="选择或输入渲染器" @change="pickRenderer"><el-option v-for="item in gpuRenderers" :key="item.webgl_renderer" :label="item.webgl_renderer" :value="item.webgl_renderer" /></el-select></el-form-item>
    </template>
    <el-form-item label="WebGPU"><el-select v-model="fp.webgpu_type"><el-option label="基于 WebGL" value="basegl" /><el-option label="真实" value="real" /><el-option label="自定义" value="custom" /><el-option label="禁用" value="disabled" /></el-select></el-form-item>
    <template v-if="fp.webgpu_type === 'custom'">
      <el-form-item label="GPU 厂商"><el-input v-model="gpuVendor" /></el-form-item><el-form-item label="GPU 架构"><el-input v-model="gpuArchitecture" /></el-form-item>
      <el-form-item label="GPU 设备"><el-input v-model="gpuDevice" /></el-form-item><el-form-item label="GPU 描述"><el-input v-model="gpuDescription" /></el-form-item>
    </template>
    <el-form-item label="屏幕分辨率"><el-select v-model="fp.screen_resolution_type"><el-option label="真实" value="real" /><el-option label="自定义" value="custom" /></el-select></el-form-item>
    <el-form-item v-if="fp.screen_resolution_type === 'custom'" label="分辨率值"><el-select v-model="fp.screen_resolution_value" filterable allow-create default-first-option placeholder="如 1920|1080"><el-option v-for="resolution in resolutions" :key="resolution" :label="resolution.replace('|', ' × ')" :value="resolution" /></el-select></el-form-item>
    <el-divider content-position="left">噪声与设备</el-divider>
    <el-form-item v-for="field in noiseFields" :key="field.key" :label="field.label"><el-select :model-value="noiseMode(field.key)" @change="setNoise(field.key, $event)"><el-option label="随机" value="random" /><el-option label="关闭" value="disabled" /></el-select></el-form-item>
    <el-form-item label="语音列表"><el-switch v-model="fp.speech_voices" /></el-form-item>
    <el-form-item label="媒体设备"><el-select :model-value="noiseMode('media_devices')" @change="setNoise('media_devices', $event)"><el-option label="随机" value="random" /><el-option label="关闭" value="disabled" /></el-select></el-form-item>
    <el-form-item label="字体列表"><el-select :model-value="noiseMode('font_list')" @change="setNoise('font_list', $event)"><el-option label="随机" value="random" /><el-option label="关闭" value="disabled" /></el-select></el-form-item>
    <el-form-item label="Do Not Track"><el-select v-model="fp.do_not_track"><el-option label="开启" :value="1" /><el-option label="关闭" :value="0" /></el-select></el-form-item>
    <el-form-item label="端口扫描保护"><el-select v-model="portMode"><el-option label="关闭" value="all" /><el-option label="开启" value="none" /><el-option label="白名单" value="whitelist" /></el-select></el-form-item>
    <el-form-item v-if="portMode === 'whitelist'" label="端口白名单"><el-input v-model="portWhitelist" placeholder="1080,7890" /></el-form-item>
    <el-form-item label="CPU 核心数"><el-select v-model="cpu"><el-option label="真实" value="real" /><el-option v-for="n in [2,4,6,8,10,12,16,20,24,32]" :key="n" :label="String(n)" :value="String(n)" /></el-select></el-form-item>
    <el-form-item label="内存 (GB)"><el-select v-model="memory"><el-option label="真实" value="real" /><el-option v-for="n in [2,4,8,16,32,64,128]" :key="n" :label="String(n)" :value="String(n)" /></el-select></el-form-item>
    <el-form-item label="TLS"><el-select v-model="fp.tls_type"><el-option label="启用" value="enabled" /><el-option label="关闭" value="disabled" /></el-select></el-form-item>
    <el-form-item v-if="fp.tls_type === 'enabled'" label="TLS 特征"><el-input v-model="fp.tls_value" type="textarea" :rows="2" placeholder="逗号分隔的禁用特征" /></el-form-item>
    <el-form-item v-if="kernel === 'firefox'" label="原生指纹保护"><el-switch v-model="nativeProtection" /></el-form-item>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { api, clientProcessMessage, isClientProcess } from '../api/client'
import type { Kernel } from '../types'
const props = defineProps<{ fp: Record<string, any>; platform: string; kernel: Kernel }>()
const isClient = isClientProcess
const noiseFields = [{ key: 'font', label: '字体' }, { key: 'canvas', label: 'Canvas' }, { key: 'audio', label: '音频' }, { key: 'client_rects', label: 'ClientRects' }]
const resolutions = ['1920|1080', '2560|1440', '3840|2160', '1366|768', '1440|900', '1536|864', '1600|900', '1680|1050', '1280|720', '1280|800', '1280|1024', '2048|1152', '2560|1080', '3440|1440']
type GpuRenderer = { webgl_renderer: string; webgpu: { vendor: string; architecture: string; device: string; description: string } }
type GpuVendor = { webgl_vendor: string; renderers: GpuRenderer[] }
const gpuOptions = ref<{ platforms: Record<string, string[]>; vendors: Record<string, GpuVendor> } | null>(null)
const gpuVendors = computed(() => (gpuOptions.value?.platforms[props.platform] || []).map(brand => gpuOptions.value?.vendors[brand]).filter((value): value is GpuVendor => Boolean(value)))
const gpuRenderers = computed(() => gpuVendors.value.find(item => item.webgl_vendor === vendor.value)?.renderers || [])
watch(() => props.fp.webgl_type, (value, oldValue) => {
  if (value === 'custom' && oldValue !== 'custom') props.fp.webgpu_type = 'basegl'
})
function part(key: string, index: number) { return computed({ get: () => String(props.fp[key] || '').split('|')[index] || '', set: (value: string) => { const parts = String(props.fp[key] || '').split('|'); parts[index] = value; props.fp[key] = parts.join('|') } }) }
const vendor = part('webgl_value', 0), renderer = part('webgl_value', 1)
const gpuVendor = part('webgpu_value', 0), gpuArchitecture = part('webgpu_value', 1), gpuDevice = part('webgpu_value', 2), gpuDescription = part('webgpu_value', 3)
function pickVendor() { renderer.value = ''; }
function pickRenderer() {
  const selected = gpuRenderers.value.find(item => item.webgl_renderer === renderer.value)
  if (selected) props.fp.webgpu_value = [selected.webgpu.vendor, selected.webgpu.architecture, selected.webgpu.device, selected.webgpu.description].join('|')
}
const longitude = part('geo_location_value', 0), latitude = part('geo_location_value', 1)
const portMode = computed({ get: () => { const value = props.fp.local_port_access || 'all'; return value === 'all' || value === 'none' ? value : 'whitelist' }, set: (value: string) => { props.fp.local_port_access = value === 'whitelist' ? '1080' : value } })
const portWhitelist = computed({ get: () => props.fp.local_port_access === 'all' || props.fp.local_port_access === 'none' ? '' : String(props.fp.local_port_access || ''), set: (value: string) => { props.fp.local_port_access = value } })
const cpu = computed({ get: () => String(props.fp.hardware_info?.cpu_cores || 'real'), set: (value: string) => { props.fp.hardware_info = { color_depth: '24', ...(props.fp.hardware_info || {}), cpu_cores: value === 'real' ? undefined : value } } })
const memory = computed({ get: () => String(props.fp.hardware_info?.memory_gb || 'real'), set: (value: string) => { props.fp.hardware_info = { color_depth: '24', ...(props.fp.hardware_info || {}), memory_gb: value === 'real' ? undefined : value } } })
const nativeProtection = computed({ get: () => Boolean(props.fp.native_fp_protection), set: (value: boolean) => { props.fp.native_fp_protection = value ? 1 : 0 } })
function noiseMode(key: string) { const value = props.fp[key]; return value === 0 || value === null || (Array.isArray(value) && !value.length) ? 'disabled' : 'random' }
async function setNoise(key: string, mode: string) {
  if (mode === 'disabled') { props.fp[key] = key === 'media_devices' || key === 'font_list' ? null : 0; return }
  if (!isClient) { ElMessage.info(clientProcessMessage); return }
  const draft = await api<Record<string, any>>('/open/fingerprint/draft', { platform: props.platform })
  props.fp[key] = draft[key]
}
onMounted(async () => { if (!isClient) return; try { gpuOptions.value = await api('/open/gpu-options') } catch { /* Free-text GPU input remains available. */ } })
</script>
