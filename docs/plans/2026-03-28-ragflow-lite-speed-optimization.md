# RAG Speed Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 通过引入 LRU 嵌入式缓存（Embedding Cache）和 Reranker 快速通道跳过机制，优化 RAG 检索速度。

**Architecture:** 
1. 针对 `BGEEmbedding` 对象，将其单条文本的向量化请求（API 调用）用 `functools.lru_cache` 包裹，确保重复查询实现毫秒级响应。
2. 在 `tool.py` 中，检查从 ES 检索返回结果（`es_result["chunks"]`）中的最高得分。如果该分数超过严格的相似度阈值（例如 >0.85），则直接采纳结果，完全跳过极其耗时的 Python 重排序循环或外部 Reranker API 调用。

**Tech Stack:** Python 3.12, FastAPI, functools.lru_cache，pytest

---

### Task 1: 在 Embedding 模块中实现 LRU 缓存

**Files:**
- Modify: `2_mcp_ragflow_lite/rag/llm/embedding.py`
- Test: `2_mcp_ragflow_lite/tests/test_nlp.py`

**Step 1: Write the failing test (编写失败的测试)**

```python
# 在 `2_mcp_ragflow_lite/tests/test_nlp.py` 中添加
def test_embedding_lru_cache(mocker):
    from rag.llm.embedding import BGEEmbedding
    emb = BGEEmbedding(api_key="test", model_name="test")
    
    # Mock requests.post 底层调用
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"data": [{"embedding": [0.1, 0.2]}]}

    # 对相同的查询执行两次请求
    res1, _ = emb.encode(["cached query"])
    res2, _ = emb.encode(["cached query"])
    
    # 期望由于缓存的存在，requests.post 仅被实际调用 1 次
    assert mock_post.call_count == 1
    assert res1[0] == res2[0] == [0.1, 0.2]
```

**Step 2: Run test to verify it fails (运行并验证失败)**

Run: `pytest 2_mcp_ragflow_lite/tests/test_nlp.py::test_embedding_lru_cache -v`
Expected: FAIL（失败原因是 `requests.post` 被调用了 2 次而不是 1 次）。

**Step 3: Write minimal implementation (实现最简代码)**

修改 `2_mcp_ragflow_lite/rag/llm/embedding.py`，添加一个带缓存的辅助方法。

```python
import functools
import requests

class BGEEmbedding:
    # ... 保留现有的 __init__ 等代码 ...

    @functools.lru_cache(maxsize=1024)
    def _encode_single_query(self, query: str) -> tuple:
        # 将针对单条文本查询的 API 调用抽离至此，以供缓存拦截
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"model": self.model_name, "input": query}
        response = requests.post(f"{self.base_url}/embeddings", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        return tuple(data["data"][0]["embedding"])

    def encode(self, texts: list[str]):
        # 若只包含单条字符串请求，则尝试走缓存分支
        if len(texts) == 1:
            try:
                emb = self._encode_single_query(texts[0])
                return [list(emb)], 0
            except Exception as e:
                import logging
                logging.warning(f"Embedding 缓存降级: {e}")
        # 若是批量请求或发生异常，退回到标准的批量处理逻辑
        # ... 保留现有的请求组装逻辑 ...
        
    def encode_queries(self, queries: list[str]):
        return self.encode(queries)
```

**Step 4: Run test to verify it passes (运行并验证通过)**

Run: `pytest 2_mcp_ragflow_lite/tests/test_nlp.py::test_embedding_lru_cache -v`
Expected: PASS

**Step 5: Commit (提交代码)**

```bash
git add 2_mcp_ragflow_lite/rag/llm/embedding.py 2_mcp_ragflow_lite/tests/test_nlp.py
git commit -m "perf(rag): implement LRU cache for embedding queries"
```

---

### Task 2: 在 tool.py 中实现 Reranker 快速通道绕过机制

**Files:**
- Modify: `2_mcp_ragflow_lite/api/routes/tool.py`

**Step 1: Write the failing test (编写失败的测试)**

```python
# 在 `2_mcp_ragflow_lite/tests/test_tool_api.py` 中添加
def test_tool_retrieve_fast_path_bypass(mocker, setup_client):
    from api.routes import tool
    
    # Mock ES 检索返回结果：设定一个超高相似度得分（大于 0.85）
    mock_dealer = mocker.AsyncMock()
    mock_dealer.retrieval.return_value = {
        "total": 1,
        "chunks": [{"chunk_id": "1", "content_with_weight": "exact match", "similarity": 0.95}]
    }
    mocker.patch("api.routes.tool.get_dealer", return_value=mock_dealer)
    
    # Mock Reranker 监控是否被多余地调用
    mock_reranker = mocker.Mock()
    mocker.patch("api.routes.tool.get_reranker", return_value=mock_reranker)
    
    client = setup_client
    resp = client.post("/api/tool/retrieve", json={"query": "exact match", "mode": "fast"})
    
    assert resp.status_code == 200
    # 因为首项匹配度 0.95 > 0.85，所以 Reranker 不应被触发
    mock_reranker.rerank_chunks.assert_not_called()
```

**Step 2: Run test to verify it fails (运行并验证失败)**

Run: `pytest 2_mcp_ragflow_lite/tests/test_tool_api.py::test_tool_retrieve_fast_path_bypass -v`
Expected: FAIL（失败原因是 `mock_reranker.rerank_chunks` 不幸地被调用了）。

**Step 3: Write minimal implementation (实现最简代码)**

修改 `2_mcp_ragflow_lite/api/routes/tool.py`，在 `get_reranker()` 逻辑前方加入拦截：

```python
    # ── Step 1: ES 混合检索 ──
    es_result = await dealer.retrieval(...)
    chunks = es_result.get("chunks", [])
    total = es_result.get("total", 0)

    # 快速通道机制：若打分最高的 chunk 分数远高于置信阈值，则跳过重排步骤
    fast_path_triggered = False
    if chunks and chunks[0].get("similarity", 0.0) > 0.85:
        fast_path_triggered = True

    # ── Step 2: Reranker 精排 ──
    reranker = get_reranker()
    if reranker and chunks and not fast_path_triggered:
        try:
            chunks = reranker.rerank_chunks(req.query, chunks, top_n=req.top_k)
        except Exception as e:
            logger.warning(f"Reranker failed: {e}")
            chunks = chunks[:req.top_k]
    else:
        chunks = chunks[:req.top_k]
```

**Step 4: Run test to verify it passes (运行并验证通过)**

Run: `pytest 2_mcp_ragflow_lite/tests/test_tool_api.py::test_tool_retrieve_fast_path_bypass -v`
Expected: PASS

**Step 5: Commit (提交代码)**

```bash
git add 2_mcp_ragflow_lite/api/routes/tool.py 2_mcp_ragflow_lite/tests/test_tool_api.py
git commit -m "perf(api): add fast-path bypass to skip reranking for exact matches"
```
