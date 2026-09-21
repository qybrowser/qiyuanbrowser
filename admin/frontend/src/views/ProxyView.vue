<template>
  <div class="page-title"><div><h1>代理管理</h1><p>管理手动代理和 API 提取代理</p></div><el-button type="primary" @click="newProxy">新增代理</el-button></div>
  <div class="panel">
    <div class="toolbar"><el-input v-model="keyword" clearable placeholder="搜索名称、地址或编码" style="width:260px" @keyup.enter="load(1)" /><el-button @click="load(1)">搜索</el-button></div>
    <el-table :data="data.items" border v-loading="loading" row-key="code">
      <el-table-column label="代理" min-width="260"><template #default="{ row }"><strong>{{ row.proxy_name || '未命名代理' }}</strong><div class="muted">{{ row.proxy_input_type === 'api' ? row.proxy_api_url : `${row.proxy_type.toUpperCase()} · ${row.proxy_addr}:${row.proxy_port}` }}</div></template></el-table-column>
      <el-table-column label="类型" width="125"><template #default="{ row }"><el-tag :type="row.proxy_input_type === 'api' ? 'warning' : 'info'">{{ row.proxy_input_type === 'api' ? 'API 提取' : '手动代理' }}</el-tag></template></el-table-column>
      <el-table-column prop="code" label="编码" min-width="170" show-overflow-tooltip />
      <el-table-column prop="create_time" label="创建时间" width="175" />
      <el-table-column label="操作" width="230"><template #default="{ row }"><el-button link type="primary" @click="edit(row.code)">编辑</el-button><el-button v-if="isClient" link type="success" :loading="checking === row.code" @click="check({ code: row.code }, row.code)">检测</el-button><el-button v-else link type="info" @click="requireClient">检测（9005）</el-button><el-button link type="danger" @click="remove(row.code)">删除</el-button></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :page-size="20" :total="data.total" layout="total, prev, pager, next" style="justify-content:flex-end;margin-top:18px" @current-change="load" />
  </div>
  <el-dialog v-model="dialog" :title="form.code ? '编辑代理' : '新增代理'" width="590px" destroy-on-close>
    <el-alert v-if="checkResult" :title="checkResult.success ? `检测成功 · ${checkResult.ip || ''} ${checkResult.country || ''} ${checkResult.city || ''} · ${checkResult.latency_ms || 0} ms` : `检测失败 · ${checkResult.error || '未知错误'}`" :type="checkResult.success ? 'success' : 'error'" style="margin-bottom:18px" />
    <el-form label-width="95px">
      <el-form-item label="代理方式"><el-radio-group v-model="form.proxy_input_type"><el-radio value="manual">手动代理</el-radio><el-radio value="api">API 提取</el-radio></el-radio-group></el-form-item>
      <el-form-item label="名称"><el-input v-model="form.proxy_name" placeholder="代理名称" /></el-form-item>
      <el-form-item label="协议"><el-select v-model="form.proxy_type"><el-option label="HTTP" value="http" /><el-option label="HTTPS" value="https" /><el-option label="SOCKS5" value="socks5" /></el-select></el-form-item>
      <template v-if="form.proxy_input_type === 'manual'">
        <el-form-item label="地址"><el-input v-model="form.proxy_addr" placeholder="IP、域名或完整代理串" @blur="parseAddress" /></el-form-item>
        <el-form-item label="端口"><el-input-number v-model="form.proxy_port" :min="1" :max="65535" :controls="false" /></el-form-item>
        <el-form-item label="用户名"><el-input v-model="form.username" /></el-form-item>
        <el-form-item label="密码"><el-input v-model="form.password" type="password" show-password /></el-form-item>
      </template>
      <el-form-item v-else label="API 链接"><el-input v-model="form.proxy_api_url" placeholder="https://example.com/get，返回 ip:port" /></el-form-item>
      <el-form-item><el-button :loading="checking === 'draft'" @click="isClient ? check(form, 'draft') : requireClient()">{{ isClient ? (form.proxy_input_type === 'api' ? '测试提取并检测' : '检测连通性') : '检测（请在 9005 操作）' }}</el-button></el-form-item>
    </el-form>
    <template #footer><el-button @click="dialog = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
  </el-dialog>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, clientProcessMessage, isClientProcess, query } from '../api/client'
import type { Page, Proxy } from '../types'

type ProxyForm = Proxy & { password: string; username: string }
const empty = (): ProxyForm => ({ code: '', proxy_name: '', proxy_type: 'http', proxy_addr: '', proxy_port: 1080, proxy_input_type: 'manual', proxy_api_url: '', username: '', password: '' })
const form = reactive<ProxyForm>(empty())
const data = ref<Page<Proxy>>({ items: [], total: 0, page: 1, page_size: 20, total_pages: 0 })
const page = ref(1), keyword = ref(''), dialog = ref(false), loading = ref(false), saving = ref(false), checking = ref('')
const checkResult = ref<(Record<string, any> & { success: boolean }) | null>(null)
const isClient = isClientProcess
function requireClient() { ElMessage.info(clientProcessMessage) }
async function load(target = page.value) {
  loading.value = true; page.value = target
  try { data.value = await api<Page<Proxy>>(query('/open/proxy/list', { page: target, page_size: 20, keyword: keyword.value })) }
  catch (error) { ElMessage.error(String(error)) }
  finally { loading.value = false }
}
function newProxy() { Object.assign(form, empty()); checkResult.value = null; dialog.value = true }
async function edit(code: string) {
  try { Object.assign(form, empty(), await api<Proxy>(query('/open/proxy/detail', { code }))); checkResult.value = null; dialog.value = true }
  catch (error) { ElMessage.error(String(error)) }
}
function parseAddress() {
  const raw = form.proxy_addr.trim()
  const uri = raw.match(/^(https?|socks5):\/\/([^@]+@)?(\[[^\]]+\]|[^:]+):(\d+)$/i)
  if (uri) {
    form.proxy_type = uri[1].toLowerCase() as Proxy['proxy_type']
    const auth = uri[2]?.slice(0, -1).split(':') || []
    form.username = auth[0] || form.username; form.password = auth.slice(1).join(':') || form.password
    form.proxy_addr = uri[3].replace(/^\[|\]$/g, ''); form.proxy_port = Number(uri[4]); return
  }
  const parts = raw.split(/[|:]/)
  if (parts.length >= 2 && /^\d+$/.test(parts[1])) {
    form.proxy_addr = parts[0]; form.proxy_port = Number(parts[1]);
    form.username = parts[2] || form.username; form.password = parts[3] || form.password
  }
}
async function check(payload: object, key: string) {
  checking.value = key
  try {
    const result = await api<Record<string, any> & { success: boolean }>('/open/proxy/check', payload)
    checkResult.value = result
    if (result.success) ElMessage.success(`代理可用 · ${result.ip || ''}`)
    else ElMessage.error(result.error || '代理不可用')
  } catch (error) { ElMessage.error(String(error)) }
  finally { checking.value = '' }
}
async function save() {
  if (!form.proxy_name.trim()) return ElMessage.warning('请输入代理名称')
  if (form.proxy_input_type === 'api' && !form.proxy_api_url?.trim()) return ElMessage.warning('请输入 API 链接')
  if (form.proxy_input_type === 'manual' && (!form.proxy_addr.trim() || !form.proxy_port)) return ElMessage.warning('请输入代理地址和端口')
  saving.value = true
  try {
    await api(form.code ? '/open/proxy/update' : '/open/proxy/create', { ...form })
    dialog.value = false; ElMessage.success('保存成功'); await load()
  } catch (error) { ElMessage.error(String(error)) }
  finally { saving.value = false }
}
async function remove(code: string) {
  try { await ElMessageBox.confirm('确认删除该代理？', '删除代理', { type: 'warning' }); await api('/open/proxy/delete', { code }); ElMessage.success('已删除'); await load() }
  catch (error) { if (error !== 'cancel') ElMessage.error(String(error)) }
}
onMounted(() => load())
</script>
