# frontend — 排轴工具前端（Vue3 + Vite）

浏览器端的「排轴工具」页面：读取主程序导出的代理序列/操作记录，可视化
时间轴与干员部署。由 `backend/build_exe.py` 构建并内嵌进桌面程序。

```bash
npm install
npm run build        # 产物输出到 backend/app/static
```

版本号在 `package.json` 的 `version` 字段（与后端 `backend/app/version.py`
各自维护）。`src/` 为源码，`dist/`/`standalone/` 为构建产物。
