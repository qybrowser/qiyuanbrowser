import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import EnvironmentView from './views/EnvironmentView.vue'
import ProxyView from './views/ProxyView.vue'
import ExtensionsView from './views/ExtensionsView.vue'
import SettingsView from './views/SettingsView.vue'
import './style.css'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/environments' },
    { path: '/environments', component: EnvironmentView },
    { path: '/proxies', component: ProxyView },
    { path: '/extensions', component: ExtensionsView },
    { path: '/settings', component: SettingsView },
  ],
})

createApp(App).use(router).use(ElementPlus).mount('#app')
