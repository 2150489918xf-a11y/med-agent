# MedAgent AI 快速接手文档 (AI Onboarding)

**本文档专为后续介入开发的 AI 智能体（Agent）或大语言模型（LLM）编写，而非普通终端用户。**
其核心目的是帮助新接入的 AI 快速了解本项目的真实代码结构、避免修改错误的代码分支，并精准定位真实的运行时代码。

---

## 1. 核心警告：项目的物理现实与谎言避坑 🚨

本仓库是一个 **Monorepo（单体多模块仓）**，核心业务划分为三个模块。**但在当前实际检查出的代码版本中，许多上游文档描述的架构并非完整的现实。**
在新 AI 接手或者开始编写代码前，**必须首先认清以下高危陷阱（High-Risk Pitfalls）**：

1. **错误的目录修改**：
   - ⚠️ `2_mcp_ragflow_lite/` 是当前真正在使用的轻量级 RAG 服务代码。
   - ⚠️ `2_mcp_ragflow_lite/ragflow/ragflow/` 是嵌套在内部的**上游完整 RAGFlow 源码**。请将其视为**第三方参考代码**，除非明确任务要求，否则**绝对不要**在此目录下进行日常的 Lite 服务报错修复或功能修改。
2. **轻信主目录 README 的架构图**：
   - 根目录的 `README.md` 描述了一个涉及 `3_mcp_medical_vision` 的三服务架构，但 **物理上 `3_mcp_medical_vision/` 目录在当前分支中是空的**。不要臆测该目录下有可用的代码。
   - 根目录下 `1_core_orchestrator/extensions_config.json` 实际上是空的。这意味着**默认情况下并没有挂载激活任何 MCP 微服务**，文档里描述的“医疗医学影像节点挂载”目前仅是一个占位存根 (`medical_mcp_server.py` 只提供 skeleton)。
3. **架构边界的红线**：
   - 在 `1_core_orchestrator/backend/` 后端代码中，`harness` 引擎与 `app` 业务有极其严格的边界：**`packages/harness/deerflow/` 下的代码绝对禁止从 `app/` 导入任何内容**，这是一条不可逾越的架构规则。

---

## 2. 代码活动热区 (活跃代码路径)

接手任务时，在没有明确说明的情况下，请默认在以下目录开展工作：

### 🟢 活跃核心区 (Start Here)
- **`1_core_orchestrator/`**：核心调度大脑（包含后端、前端、网关、LangGraph 等）。所有与聊天 UI、LangGraph 工作流、Agent 逻辑、多智能体交互、内存、Sandbox、上传组件、MCP 挂载相关的任务，都应在这里完成。
- **`2_mcp_ragflow_lite/`**：私有轻量级知识库检索服务。知识库 CRUD、索引建立、GraphRAG、CRAG 逻辑、Elasticsearch 相关的查询，都应在这里完成。

### 🔴 易错参考区 (Danger Zone)
- **`2_mcp_ragflow_lite/ragflow/ragflow/`**：仅当作参考，不应当作运行代码进行逻辑修复。
- 各种运行时生成的制品：如 `.next/`, `node_modules/`, `__pycache__/`, 线程生成的数据、以及依赖项缓存。

---

## 3. 关键服务入口与运行架构映射

### 3.1 Orchestrator 核心工作流 (`1_core_orchestrator`)
架构逻辑主要分为三层：
- **Web 前端 (Next.js)** 
  - 核心入口页面集成：`frontend/src/app/workspace/chats/[thread_id]/page.tsx`
  - Lifecycle Hook：`frontend/src/core/threads/hooks.ts`
- **网关 API 服务 (FastAPI)** 
  - 入口：`backend/app/gateway/app.py`
  - 负责 Model、各类技能 (Skills)、MCP、上传/制品等生命周期管理。
- **LangGraph 执行引擎** 
  - 核心组装：`backend/packages/harness/deerflow/agents/lead_agent/agent.py`
  - 入口定义详见：`backend/langgraph.json`
- **宿主机路径与沙盒映射（非常重要）**：
  引擎会将宿主机目录 (`{base_dir}/threads/{thread_id}/user-data/...`) 映射到虚拟路径系统（如 `/mnt/user-data/workspace`），处理文件上传及沙盒操作时切勿直接使用物理宿主机绝对路径。

### 3.2 轻量级 RAG 服务 (`2_mcp_ragflow_lite`)
- **API 入口**：`api/app.py`
- **依赖单例注入**：`api/deps.py` (集成了所有 ES、GraphRAG、Embedding 实例)
- **供 Agent 的检索节点入口**：`api/routes/tool.py`

### 3.3 典型的网络端口拓扑
- **LangGraph**：`:2024`
- **Nginx反向代理**：`:2026`
- **前端 Next.js**：`:3000`
- **网关 Gateway (FastAPI)**：`:8001`
- **RAGFlow Lite (FastAPI)**：`:9380`

---

## 4. 敏感情报与文档协同

- **密钥与敏感配置**：`1_core_orchestrator/config.yaml`, `1_core_orchestrator/.env` 和 `2_mcp_ragflow_lite/conf/service_conf.yaml` 都包含敏感信息。生成报告和代码或展示相关示例时，务必使用 `*.example.*` 的模板替代以防泄密。
- **双向文档更新原则**：每次您修改了涉及系统运行底层的基础代码（特别是 `1_core_orchestrator/backend/` 下的时候），务必检查并同步更新 `README.md` 与 `CLAUDE.md` / `AGENTS.md`。

---

## 5. 开发与验证基准命令

### Orchestrator Backend 测试标尺
- 进入 `1_core_orchestrator/backend` 使用 `Makefile`。
- `pytest` 测试必须通过，并确保无 `harness`/`app` 跨界导入报错。

### Orchestrator Frontend 测试标尺
- 进入 `1_core_orchestrator/frontend`：依次运行 `pnpm lint` -> `pnpm typecheck` -> `pnpm build`。

### RAGFlow Lite 测试标尺
- 进入 `2_mcp_ragflow_lite`，使用根目录自带的 `tests/` 套件：运行 `pytest`。

*(详情亦可参考本地统一的启动脚本 `1_core_orchestrator/scripts/serve.sh` 掌握整套启动流程的奥秘。)*

---

## 6. AI 每日开工自检清单 (Checklist) ✔️

在开始规划和修改代码前，**请大声问自己以下问题**：
1. **[任务归属]** 我到底该修改 `1_core_orchestrator` 还是 `2_mcp_ragflow_lite`？
2. **[路径陷阱]** 我是在碰 `2_mcp_ragflow_lite_ragflow/ragflow/` 这个不可接触的“上游黑洞”吗？
3. **[幻觉自检]** 我是不是盲从了 `README.md`，以为 `3_mcp_medical_vision` 库里有完整的视觉代码？但我查看过了吗？(其实并没有)。
4. **[边界自保]** 我要在 backend 写逻辑了，我的 import 有没有打破 `harness` 引擎层 和 `app` 业务层独立解耦的红线？
5. **[测试方式]** 修改完成后，对应目录里的 `Makefile` 或 `pytest` 能通过吗？

> **最终法则**：所有文档都可以撒谎，只有文件系统与代码本身才是唯一的现实。如果你在文档中读到的架构与现场代码冲突，**相信代码，遵循代码，修复文档。**
