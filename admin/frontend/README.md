# 管理界面

Vue 3 + Vite + TypeScript + Element Plus。页面按功能拆分到 `src/views/`；API 请求统一在 `src/api/client.ts`。

```powershell
cd admin/frontend
npm install
npm run build
```

构建产物写入 `admin/static/dist/`。启动 `python -m admin.server` 后，`/` 使用新界面。开发时运行 `npm run dev`，Vite 会将 `/open` 与 `/api` 请求代理到 `127.0.0.1:9003`。

客户端设置由根目录的 `browser-config-client.json` 提供，服务端设置由 `browser-config-server.json` 提供。客户端进程启动时会创建浏览器应用数据目录的 `client`、`config`、`extends` 空目录；内核通过系统设置上传，运行时 URL 配置会生成到应用数据目录的 `config/config.json`。
