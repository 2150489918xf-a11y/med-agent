# RAGFlow Lite AI 快速接手文档 (AI Onboarding)

**本文档专为接手 `2_mcp_ragflow_lite` 目录开发（即本项目的知识库服务模块）的 AI 智能体或 LLM 编写。**
它提炼了该子服务的核心架构设计、最容易踩坑的物理代码边界，以及你必须遵循的开发准则。

## 1. ⚠️ 第一铁律与致命雷区 (The Absolute Red Line)

**认清你所在的物理代码路径：**
- **✅ `2_mcp_ragflow_lite/`（当前根目录）**：这就是你主要工作的**实际微服务活跃代码区**。核心逻辑、路由和检索引擎全在此处。
- **🚫 `2_mcp_ragflow_lite/ragflow/ragflow/`**：这是嵌套在此处用作参考的完整的、上游庞大的开源 RAGFlow 代码库。**绝对禁止**擅自修改该目录下的任何文件，除非用户明确下达“修改上层完整庞大源码对应的 MCP”这种极为罕见的指令。如果你在修复普通的 Lite 服务接口错漏或配置 Bug 时打开了该深层目录下的文件，你 100% 走错了路！

## 2. 核心架构与请求流转溯源 (Architecture Flow)

现在的 Lite 服务**不是**一个简单的调用外壳，而是将繁重的 Docker 环境剥离后，提炼出的高度定制化、可移植的核心 RAG 检索引擎。

### API 链路追溯指南
当主调度器大脑（Orchestrator）或前端发起检索与管理请求时：
1. **统一入口**：`api/app.py`（FastAPI 应用根）。
2. **全局依赖与单例**：所有核心组件（Elasticsearch 连接器、LLM 客户端工厂、Embedding 服务等）统一在 `api/deps.py` 内部初始化注册，并以依赖注入形式提供给下方路由。
3. **四大核心路由区**：
   - 📁 **资源管理类（CRUD）**：负责知识库及虚拟文件夹层级、树状管理，查阅 `api/routes/kb.py` 和 `api/routes/doc.py`。
   - 🔍 **复合业务检索类**：负责带评判或图谱增强的重度检索组合请求，查阅 `api/routes/search.py`（这是 GraphRAG，混合检索等技术栈最终融合的地方）。
   - 🤖 **Agent 工具对接类 (Agent Tool API)**：如果你修复的是“Agent 调用工具后报参数格式错误”等问题，首要检查 `api/routes/tool.py`。这是专门为接驳外部 Function Calling 系统设计、最干净的原子检索接口。

### 底层分析分块链 (`rag/` 与 `deepdoc/`)
- **视觉版面解构**：重度 PDF 及表格识别由 `deepdoc/` 接管。
- **文档分块控制台**：`rag/app/chunking.py` 是包含 `qa`, `naive`, `laws` 等不同专业分块策略算法的核心路由点。

## 3. 统一规范的插件注册器机制 (The Plugin Registry Mandate) 🔌

该微服务所有功能组件实现了高度解耦的统一注册。这决定了你**拓展系统功能时的唯一合法手法**！

### 强制开发准则（No Hardcoded If-Else）
如果在代码中遇到需要新增一种“文档存储”（比如用 Milvus 替换 ES）、“大模型连接”或者“切分器”的需求，**严禁**在调用层写死如 `if backend == "milvus"` 这样丑陋的硬编码分支！
- **✅ 正确做法是**：在对应模块下编写一个具体的实现类并继承公共的 `ABC`（例如 `DocStoreConnection` 或 `BaseChatClient`），随后使用装饰器 **`@***_registry.register("your_backend_name")`** 将其注册进系统。
- 业务调用方会极其优雅地通过工厂方法自动动态加载 `conf/service_conf.yaml` 里填写的名称对应的实例实体。参考 `common/registry.py` 获得总览。

## 4. 全局配置与虚拟文件管理 (Configs & Filesystem)

1. **脱离环境变量约束**：与外部采用 `.env` 不同，这里的微服务**唯一的真理级配置文件是 `conf/service_conf.yaml`**。`rag/settings.py` 文件全盘掌管并且通过验证了该 YAML 结构内的参数，切不可用 `os.getenv` 自定隐蔽读取通道。
2. **树形文件夹结构实现**：不同于简单 KV 的知识库挂载，本项目支持“真实 PC 文件夹式的层级潜逃”。由于并未接入真的关系数据库，此类知识点通常依靠内部如 `conf/folders.json` 的管理方式或 ES 组合键实现，遇到相关的视图层级错乱可优先排查这里。

## 5. 常规排障与修 Bug 起手式 (Troubleshooting Playbook)

### 场景 1：核心大脑报工具检索结果为空或者返回解析 JSON 失败
立刻前往 `api/routes/tool.py` 中寻找 `/api/tool/retrieve` 接口端点。先确认出参 `data["answer_context"]` 是否被正确组装，或者再往下沉至 `rag/nlp/search.py` 观察混合检索的粗排和打分截断是否有强硬的拦截门槛。

### 场景 2：外部更换了新的国内特供版兼容大模型底座
可前往 `rag/llm/chat.py` 观察封装逻辑。多数情况下直接修改 YAML 填入类似 DeepSeek 等完全兼容 OpenAI 规范的 Endpoint 即完美工作（因其内置实现了 openai_chat 的注册逻辑），只有极少数如不标准流式吐字模型需要重新写一个适配子类打上 registry 即可。

### 场景 3：检索与入库链路底层报错，由于无端环境无法重现
**利用提供的离线命令行大棒！** 不必生硬等待 Web 服务器跑偏日志：
```bash
python scripts/build_index.py --kb_id test_kb --docs_dir ./your_docs_folder
```
用这个直接走通从 `deepdoc` 切分解析，到 Embeddings，再入 ES 的全部动作，定位精确至函数内部。

---
> 💡 **最后的叮嘱**：不知道某个类或基建如何被实例化调用的？立刻搜索并查看 `tests/` 目录下（共有80+项用例），它们是项目最高价值的、随时更新的 API 用法教科书！
