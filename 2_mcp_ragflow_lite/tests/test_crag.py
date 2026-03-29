"""
CRAG 路由器单测 — 验证三路状态机 (Correct / Incorrect / Ambiguous) 和超时降级
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from rag.crag.router import CRAGRouter


@pytest.fixture
def mock_chat():
    return MagicMock()


@pytest.fixture
def router(mock_chat):
    """构造一个 CRAGRouter，内部的 evaluator / refiner / web_searcher 全部 mock"""
    r = CRAGRouter(chat_client=mock_chat)
    r.evaluator = MagicMock()
    r.refiner = MagicMock()
    r.web_searcher = MagicMock()
    return r


SAMPLE_CHUNKS = [
    {"chunk_id": "c1", "content": "糖尿病是一种慢性代谢性疾病", "similarity": 0.9},
    {"chunk_id": "c2", "content": "二型糖尿病的主要治疗方式包括...", "similarity": 0.85},
]


class TestCRAGRouterCorrect:
    """🟢 Correct → 直接放行"""

    @pytest.mark.asyncio
    async def test_correct_passthrough(self, router):
        router.evaluator.evaluate = AsyncMock(return_value={
            "score": "Correct", "reason": "本地知识充足", "search_query": "",
        })

        result = await router.route("什么是糖尿病", SAMPLE_CHUNKS, graph_context="图谱数据")

        assert result["crag_score"] == "Correct"
        assert result["chunks"] == SAMPLE_CHUNKS  # 原样返回
        assert result["graph_context"] == "图谱数据"  # 图谱保留
        assert "PASS_THROUGH" in result["crag_action"]


class TestCRAGRouterIncorrect:
    """🔴 Incorrect → 焦土政策"""

    @pytest.mark.asyncio
    async def test_incorrect_web_search(self, router):
        router.evaluator.evaluate = AsyncMock(return_value={
            "score": "Incorrect", "reason": "与问题无关", "search_query": "糖尿病最新治疗",
        })
        web_chunks = [{"chunk_id": "w1", "content": "web result", "source_type": "web"}]
        router.web_searcher.search = AsyncMock(return_value=web_chunks)

        result = await router.route("什么是糖尿病", SAMPLE_CHUNKS, graph_context="图谱数据")

        assert result["crag_score"] == "Incorrect"
        assert result["graph_context"] == ""  # 图谱被清空
        assert result["chunks"] == web_chunks  # 换成外搜结果
        assert "SCORCHED_EARTH" in result["crag_action"]

    @pytest.mark.asyncio
    async def test_incorrect_web_search_disabled(self, router):
        router.evaluator.evaluate = AsyncMock(return_value={
            "score": "Incorrect", "reason": "无关", "search_query": "q",
        })

        result = await router.route("什么是糖尿病", SAMPLE_CHUNKS,
                                    enable_web_search=False)

        # 网搜关闭，应降级返回原始数据
        assert result["chunks"] == SAMPLE_CHUNKS
        assert "WEB_SEARCH_DISABLED" in result["crag_action"]

    @pytest.mark.asyncio
    async def test_incorrect_web_search_fails(self, router):
        router.evaluator.evaluate = AsyncMock(return_value={
            "score": "Incorrect", "reason": "无关", "search_query": "q",
        })
        router.web_searcher.search = AsyncMock(return_value=[])  # 外搜无结果

        result = await router.route("什么是糖尿病", SAMPLE_CHUNKS)

        # 外搜也失败，应降级
        assert result["chunks"] == SAMPLE_CHUNKS
        assert "FALLBACK" in result["crag_action"]


class TestCRAGRouterAmbiguous:
    """🟡 Ambiguous → 双管齐下"""

    @pytest.mark.asyncio
    async def test_ambiguous_dual_augment(self, router):
        router.evaluator.evaluate = AsyncMock(return_value={
            "score": "Ambiguous", "reason": "信息不完整", "search_query": "糖尿病并发症",
        })
        refined = [{"chunk_id": "r1", "content": "refined"}]
        web = [{"chunk_id": "w1", "content": "web"}]
        router.refiner.refine = AsyncMock(return_value=refined)
        router.web_searcher.search = AsyncMock(return_value=web)

        result = await router.route("糖尿病有哪些并发症", SAMPLE_CHUNKS)

        assert result["crag_score"] == "Ambiguous"
        assert result["chunks"] == refined + web  # 合并
        assert "DUAL_AUGMENT" in result["crag_action"]

    @pytest.mark.asyncio
    async def test_ambiguous_refine_only(self, router):
        router.evaluator.evaluate = AsyncMock(return_value={
            "score": "Ambiguous", "reason": "partial", "search_query": "q",
        })
        refined = [{"chunk_id": "r1", "content": "refined"}]
        router.refiner.refine = AsyncMock(return_value=refined)

        result = await router.route("q", SAMPLE_CHUNKS, enable_web_search=False)

        assert result["chunks"] == refined
        assert "REFINE_ONLY" in result["crag_action"]


class TestCRAGRouterEdgeCases:
    """边界情况"""

    @pytest.mark.asyncio
    async def test_unknown_score_fallback(self, router):
        router.evaluator.evaluate = AsyncMock(return_value={
            "score": "UnknownValue", "reason": "???", "search_query": "",
        })

        result = await router.route("q", SAMPLE_CHUNKS)

        assert result["chunks"] == SAMPLE_CHUNKS
        assert "UNKNOWN_FALLBACK" in result["crag_action"]

    @pytest.mark.asyncio
    async def test_latency_recorded(self, router):
        router.evaluator.evaluate = AsyncMock(return_value={
            "score": "Correct", "reason": "ok", "search_query": "",
        })

        result = await router.route("q", SAMPLE_CHUNKS)

        assert "latency_ms" in result
        assert isinstance(result["latency_ms"], int)
