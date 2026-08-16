# Infrastructure and deployment

当前版本支持用 Docker Compose 部署到一台 Linux 服务器：

- `web`：Nginx 托管 Vite 构建产物，并将 `/api/*` 反向代理到后端。
- `backend`：FastAPI/Uvicorn 单 Worker 服务。
- `backend_data`：保存 SQLite 数据库的 Docker volume。

## 快速部署

服务器建议使用 Ubuntu 24.04、2 vCPU、4 GB 内存和 20 GB 磁盘，并先安装 Docker Engine 与 Compose plugin。

```bash
git clone <repository-url> eufy-security-agent-platform
cd eufy-security-agent-platform
cp .env.deploy.example .env
nano .env
docker compose up -d --build
docker compose ps
curl http://127.0.0.1/api/v1/health
```

至少需要修改 `.env` 中的 `LLM_API_KEY` 和 `PUBLIC_APP_URL`。浏览器访问服务器 IP 即可使用。

## 日常运维

```bash
# 查看日志
docker compose logs -f --tail=200

# 拉取代码并滚动重建
git pull
docker compose up -d --build

# 停止服务（保留数据库）
docker compose down

# 备份 SQLite 数据卷
docker compose exec backend sh -c 'cp /var/lib/eufy/app.db /var/lib/eufy/app.db.backup'
```

不要运行 `docker compose down -v`，除非明确要删除所有任务、事件和 ProductSpec 数据。

## 生产边界

- 当前应用没有登录和权限系统，不应直接暴露给不受信任的公网用户。企业演示优先放在 VPN、内网或带身份访问控制的网关后面。
- 当前工作流依赖进程内 `BackgroundTasks`，数据库是 SQLite，因此后端有意固定为单 Worker、单副本。不要横向扩容；正式生产前应迁移到外部数据库和独立任务队列。
- Compose 只提供 HTTP。公网域名应在服务器前增加托管 HTTPS 负载均衡器、Cloudflare Tunnel/Access，或单独的 TLS 反向代理。
- SQLite 位于命名卷 `backend_data`。升级和迁移前先做卷级备份。
