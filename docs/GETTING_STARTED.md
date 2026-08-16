# 系统打开说明（新手版）

这份文档面向第一次接手这个项目的同学，目标是让你在本地把前后端都跑起来，并知道哪些配置是必须的，哪些是可选的。

## 1. 这个项目是什么

这是一个围绕 `eufy` 家庭安防场景构建的 AI 原生产品定义系统，当前仓库主要包含两部分：

- `backend/`：FastAPI 后端，负责多 Agent 研究、候选生成、ProductSpec、预验证相关 API
- `frontend/`：React + Vite 前端，负责研究输入、过程展示、候选查看、产品定义与预验证界面

本地联调时，默认端口是：

- 后端：`http://localhost:8000`
- 前端：`http://localhost:5173`
- 后端文档：`http://localhost:8000/docs`

## 2. 运行前准备

建议环境：

- Python `3.12+`
- Node.js `20+`
- npm `10+`

第一次启动前，先确认：

- 当前目录是仓库根目录
- 你有网络，便于安装 Python 和 npm 依赖
- 本机 `8000` 和 `5173` 端口没有被占用

## 3. 启动顺序

推荐顺序是：

1. 先启动后端
2. 确认后端健康检查正常
3. 再启动前端
4. 打开浏览器访问前端

原因很简单：前端很多页面依赖后端接口，后端没起来时前端会显示“未连接”或禁用开始按钮。

## 4. 后端怎么配置和启动

### 4.1 进入后端目录

```powershell
cd D:\anker\eufy\backend
```

### 4.2 创建后端环境变量文件

后端使用的是：

- `backend/.env`
- 可选的 `backend/.env.feishu`

先复制示例文件：

```powershell
Copy-Item .env.example .env
```

### 4.3 后端最小必填配置

如果你只是想把系统跑起来，最关键的是：

```dotenv
LLM_API_KEY=你的模型密钥
```

说明：

- 不填 `LLM_API_KEY`，后端依然能启动
- 但前端会识别到 `llm_configured=false`，并禁用正式发起研究

后端默认还会使用这些值，如果你不改也能跑：

```dotenv
DATABASE_URL=sqlite:///data/app.db
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
PUBLIC_APP_URL=http://localhost:5173
```

### 4.4 飞书 / Aily 配置是不是必须

不是必须。

只有你要使用飞书同步能力时，才需要配置这些字段：

```dotenv
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_BITABLE_APP_TOKEN=
FEISHU_WIKI_NODE_TOKEN=
FEISHU_BITABLE_TABLE_ID=
FEISHU_BITABLE_VIEW_ID=
FEISHU_BITABLE_URL=
```

如果不配：

- 后端可以正常启动
- 普通研究、候选生成、ProductSpec 等主流程不受影响
- 只有飞书同步相关能力不可用

### 4.5 创建虚拟环境并安装依赖

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

如果 PowerShell 不允许执行脚本，可以先运行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

### 4.6 启动后端

```powershell
python -m uvicorn eufy_security_agents.main:app --reload --port 8000
```

启动成功后，打开：

- `http://localhost:8000/docs`
- `http://localhost:8000/api/v1/health`

如果健康检查返回里有：

- `"status": "ok"`：说明后端已启动
- `"llm_configured": true`：说明模型密钥已生效
- `"feishu_configured": true/false`：说明飞书是否配置完整

## 5. 前端怎么配置和启动

### 5.1 进入前端目录

```powershell
cd D:\anker\eufy\frontend
```

### 5.2 创建前端环境变量文件

```powershell
Copy-Item .env.example .env
```

默认内容通常已经够用：

```dotenv
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

只有在下面几种情况才需要改：

- 后端不跑在 `8000`
- 你换了本机 IP 或反向代理地址
- 你要连测试环境/远程环境

### 5.3 安装依赖并启动

```powershell
npm install
npm run dev
```

启动成功后，打开：

`http://localhost:5173`

## 6. 第一次打开后你会看到什么

建议按这个顺序检查：

1. 首页是否正常打开
2. 页面顶部是否提示“后端未连接”
3. 如果后端已连通，是否还提示“LLM 未配置”
4. 最近研究列表是否能正常加载
5. 创建一个研究问题，确认能进入运行页面

如果后端正常、前端正常、`LLM_API_KEY` 也配置了，那么你应该可以完整体验：

- 研究任务创建
- 运行过程展示
- 候选结果查看
- ProductSpec 生成
- 预验证相关页面

## 7. 最常见的 4 个问题

### 7.1 前端显示“后端未连接”

优先检查：

- 后端是否真的启动了
- `VITE_API_BASE_URL` 是否还是 `http://localhost:8000/api/v1`
- 本机 8000 端口是否被别的服务占用

### 7.2 前端显示“LLM 未配置”

说明后端已经起来了，但没有读到有效的 `LLM_API_KEY`。

检查：

- 你改的是不是 `backend/.env`，不是仓库根目录 `.env`
- 字段名是不是 `LLM_API_KEY`，不是旧的 `OPENAI_API_KEY`
- 改完后有没有重启后端

### 7.3 飞书同步报错

优先检查：

- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- `FEISHU_BITABLE_APP_TOKEN` 或 `FEISHU_WIKI_NODE_TOKEN`

这几个至少要形成完整组合，否则飞书相关接口会报配置不完整。

### 7.4 页面能打开，但点击开始没反应

通常有两个原因：

- 后端没连上
- `LLM_API_KEY` 未配置，按钮被前端保护性禁用

## 8. 推荐的新手打开流程

如果你只是第一次想把系统体验起来，照下面做就够了：

### 第一步：启动后端

```powershell
cd D:\anker\eufy\backend
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m uvicorn eufy_security_agents.main:app --reload --port 8000
```

### 第二步：在 `backend/.env` 里补上模型密钥

```dotenv
LLM_API_KEY=你的模型密钥
```

### 第三步：启动前端

```powershell
cd D:\anker\eufy\frontend
Copy-Item .env.example .env
npm install
npm run dev
```

### 第四步：打开浏览器

访问：

```text
http://localhost:5173
```

## 9. 目录里最值得先看的文件

- `backend/README.md`：后端能力与接口说明
- `frontend/README.md`：前端页面与联调说明
- `backend/src/eufy_security_agents/core/config.py`：后端真实读取的配置项
- `frontend/src/lib/api/forecastApi.ts`：前端如何调用后端 API

如果你是第一次接手项目，建议先把前后端都跑起来，再去读这些文件，会更容易建立整体理解。
