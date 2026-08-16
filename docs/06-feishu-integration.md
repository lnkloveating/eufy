# 06 Feishu Integration

更新时间：2026-08-16

本文回答一个直接问题：飞书 Aily 目前到底真正接了什么。

## 结论先说

按当前仓库代码搜索结果，**没有找到成型的飞书 / Aily 集成实现**。

我检索了这些关键词：

- `feishu`
- `aily`

在 `backend/`、`frontend/`、`docs/` 范围内，没有发现真实的接口调用、SDK、Webhook、Bot、OAuth、回调处理、租户凭证或消息适配层。

## 这意味着什么

从这个 repo 本身判断：

- 当前产品主体验是 Web workbench
- 主通路是浏览器前端 <-> FastAPI 后端
- 不是“飞书里驱动一切”的产品形态

也就是说，如果有人问“飞书 Aily 已经接了吗”，更准确的回答是：

> 目前在这个代码仓库里看不到真实飞书 Aily 接入，至少主链路并不依赖飞书。

## 当前真实存在的通信方式

系统现在真正使用的是：

- HTTP API
- SSE event stream
- SQLite persistence

核心接口在：

- `backend/src/eufy_security_agents/api/routes.py`

前端消费在：

- `frontend/src/lib/api/forecastApi.ts`
- `frontend/src/lib/queries.ts`
- `frontend/src/lib/api/sse.ts`

## 没找到哪些飞书常见接入痕迹

如果已经接了飞书，通常会看到下面这些之一：

- 飞书开放平台 app id / app secret 配置
- webhook callback 路由
- Bot 消息发送器
- 飞书文档 / 表格 / 多维表格 API 适配层
- OAuth 登录
- tenant access token 刷新逻辑
- 消息卡片 schema
- Aily 工作流节点适配代码

当前仓库里没看到这些。

## 最可能的情况

结合当前代码结构，比较合理的判断是：

### 情况 1

飞书集成根本还没做。

### 情况 2

飞书相关代码不在这个 repo，而在别的服务、脚本或私有集成仓库里。

### 情况 3

目前只做了产品规划或口头方案，还没有进入代码实现。

## 如果你要把这篇文档给团队看

建议用下面这句最稳：

> 截至 2026-08-16，当前仓库未发现飞书 Aily 的真实接入代码。系统主链路运行在浏览器前端、FastAPI 后端、本地知识库与 SQLite 持久化之上。若已有飞书能力，代码应当位于本仓库之外，或尚未提交。

## 如果后面要补飞书接入，最小落地点建议

建议至少补齐这四层：

1. `backend/src/.../integrations/feishu.py`
2. `backend/src/.../api/routes_feishu.py`
3. `.env.example` 中的飞书凭证
4. `docs/06-feishu-integration.md` 改为真实链路图

### 推荐先做的接法

- 飞书消息卡片触发创建 forecast run
- 飞书里查看 run 状态和结果链接
- ProductSpec / validation finding 回传飞书会话或群

### 不建议第一步就做的

- 把完整工作台全部塞进飞书
- 让飞书承担 SSE 实时体验

更合理的方式是：

- 飞书做入口、通知、协同
- Web workbench 继续承载重交互界面

## 当前文档结论

这份文档不是“飞书怎么接”，而是明确记录：

- 当前 repo 没有真正接飞书
- 不要把外部说法当成仓库事实
