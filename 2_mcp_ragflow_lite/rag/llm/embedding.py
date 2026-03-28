"""
远程 Embedding 客户端
支持 OpenAI 兼容协议的远程 Embedding API
"""
import logging
from collections import OrderedDict

import numpy as np
from openai import OpenAI

from rag.nlp import truncate
from rag.llm.base import BaseEmbedding
from common.registry import embedding_registry

logger = logging.getLogger(__name__)


@embedding_registry.register("openai")
class RemoteEmbedding(BaseEmbedding):
    """
    OpenAI 兼容协议的 Embedding 客户端
    支持 SiliconFlow / OpenAI / 其他兼容 API
    """

    # 查询向量缓存配置
    _QUERY_CACHE_MAX = 4096

    def __init__(self, api_key, model_name, base_url="https://api.openai.com/v1"):
        if not base_url:
            base_url = "https://api.openai.com/v1"
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model_name = model_name
        self.max_length = 8191
        # LRU 缓存: OrderedDict 用于 encode_queries 的结果缓存
        # key = text.strip(), value = (np.ndarray, int)
        self._query_cache: OrderedDict[str, tuple] = OrderedDict()

    def encode(self, texts: list) -> tuple:
        """
        批量编码
        返回 (向量矩阵 np.ndarray, token消耗 int)
        """
        batch_size = 16
        texts = [truncate(t, self.max_length) for t in texts]
        # 确保没有空文本
        texts = [t if t and t.strip() else " " for t in texts]

        ress = []
        total_tokens = 0

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                res = self.client.embeddings.create(
                    input=batch,
                    model=self.model_name,
                    encoding_format="float",
                )
                ress.extend([d.embedding for d in res.data])
                total_tokens += res.usage.total_tokens if res.usage else 0
            except Exception as e:
                logger.error(f"Embedding encode error: {e}")
                raise

        return np.array(ress), total_tokens

    def encode_queries(self, text: str) -> tuple:
        """
        查询编码（带 LRU 缓存）
        返回 (向量 np.ndarray, token消耗 int)

        缓存策略: 使用 OrderedDict 实现 LRU 淘汰，最多缓存 _QUERY_CACHE_MAX 条。
        相同文本的重复查询直接从内存返回，避免远程 API 调用（~200ms → <0.01ms）。
        """
        # 先 truncate 再算 cache_key，确保 key 与实际 API 调用的文本一致
        text = truncate(text, self.max_length) if text else ""
        if not text or not text.strip():
            text = " "
        cache_key = text.strip()

        # 缓存命中
        if cache_key in self._query_cache:
            self._query_cache.move_to_end(cache_key)  # 刷新为最近使用
            logger.debug(f"Embedding cache HIT: {cache_key[:30]}...")
            return self._query_cache[cache_key]

        # 缓存未命中 → 调用远程 API
        try:
            res = self.client.embeddings.create(
                input=[text],
                model=self.model_name,
                encoding_format="float",
            )
            result = (np.array(res.data[0].embedding), res.usage.total_tokens if res.usage else 0)
        except Exception as e:
            logger.error(f"Embedding encode_queries error: {e}")
            raise

        # 写入缓存（LRU 淘汰: 满了删最老的）
        self._query_cache[cache_key] = result
        if len(self._query_cache) > self._QUERY_CACHE_MAX:
            self._query_cache.popitem(last=False)

        return result
