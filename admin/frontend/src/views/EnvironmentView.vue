<template>
  <div class="page-title"><div><h1>环境管理</h1><p>管理浏览器环境、内核与启动状态</p></div><el-button type="primary" @click="drawer?.create()">新增环境</el-button></div>
  <div class="panel">
    <div class="toolbar"><el-input v-model="keyword" clearable placeholder="搜索名称或编码" style="width:260px" @keyup.enter="load(1)" /><el-button @click="load(1)">搜索</el-button><el-button @click="load()">刷新</el-button></div>
    <el-table :data="data.items" border v-loading="loading" row-key="code">
      <el-table-column label="环境" min-width="230"><template #default="{ row }"><strong>{{ row.name }}</strong><div class="muted">{{ row.code }}</div></template></el-table-column>
      <el-table-column label="内核" width="180"><template #default="{ row }">{{ row.browser_kernel === 'firefox' ? 'Firefox' : 'Chromium' }} {{ row.browser_version }}</template></el-table-column>
      <el-table-column prop="platform" label="系统" width="125" />
      <el-table-column label="状态" width="110"><template #default="{ row }"><el-tag :type="row.status === 'running' ? 'success' : 'info'">{{ row.status === 'running' ? '运行中' : '已停止' }}</el-tag></template></el-table-column>
      <el-table-column prop="remark" label="备注" min-width="130" show-overflow-tooltip />
      <el-table-column label="操作" min-width="285" fixed="right"><template #default="{ row }"><el-button v-if="isClient" link :type="row.status === 'running' ? 'warning' : 'success'" :loading="acting === row.code" @click="toggle(row)">{{ row.status === 'running' ? '关闭' : '打开' }}</el-button><el-button v-else link type="info" @click="requireClient">{{ row.status === 'running' ? '关闭' : '打开' }}（9005）</el-button><el-button link type="primary" @click="drawer?.edit(row.code)">编辑</el-button><el-button v-if="isClient" link @click="clearCache(row.code)">清理缓存</el-button><el-button v-else link type="info" @click="requireClient">清理缓存（9005）</el-button><el-button link type="danger" @click="remove(row.code)">删除</el-button></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :page-size="20" :total="data.total" layout="total, prev, pager, next" style="justify-content:flex-end;margin-top:18px" @current-change="load" />
  </div>
  <EnvironmentDrawer ref="drawer" @saved="load()" />
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, clientProcessMessage, isClientProcess, query } from '../api/client'
import type { Environment, Page } from '../types'
import EnvironmentDrawer from './EnvironmentDrawer.vue'

const drawer = ref<InstanceType<typeof EnvironmentDrawer>>()
const data = ref<Page<Environment>>({ items: [], total: 0, page: 1, page_size: 20, total_pages: 0 })
const page = ref(1), keyword = ref(''), loading = ref(false), acting = ref('')
const isClient = isClientProcess
function requireClient() { ElMessage.info(clientProcessMessage) }
async function load(target = page.value) {
  loading.value = true; page.value = target
  try { data.value = await api<Page<Environment>>(query('/open/env/list', { page: target, page_size: 20, keyword: keyword.value })) }
  catch (error) { ElMessage.error(String(error)) }
  finally { loading.value = false }
}
async function toggle(row: Environment) {
  if (!isClient) return requireClient()
  acting.value = row.code
  try {
    if (row.status === 'running') await api('/open/env/close', { code: row.code })
    else await api('/open/env/open', { code: row.code, needDebugPort: false })
    ElMessage.success(row.status === 'running' ? '环境已关闭' : '环境已打开'); await load()
  } catch (error) { ElMessage.error(String(error)) }
  finally { acting.value = '' }
}
async function clearCache(code: string) {
  if (!isClient) return requireClient()
  try { await ElMessageBox.confirm('清理该环境的浏览器缓存？', '清理缓存'); await api('/open/env/clear_cache', { code }); ElMessage.success('缓存已清理') }
  catch (error) { if (error !== 'cancel') ElMessage.error(String(error)) }
}
async function remove(code: string) {
  try { await ElMessageBox.confirm('确认删除该环境？此操作不可撤销。', '删除环境', { type: 'warning' }); await api('/open/env/delete', { code }); ElMessage.success('已删除'); await load() }
  catch (error) { if (error !== 'cancel') ElMessage.error(String(error)) }
}
onMounted(() => load())
let refreshTimer: number | undefined
onMounted(() => {
  if (isClient) refreshTimer = window.setInterval(() => load(), 3000)
})
onUnmounted(() => {
  if (refreshTimer !== undefined) window.clearInterval(refreshTimer)
})
</script>
