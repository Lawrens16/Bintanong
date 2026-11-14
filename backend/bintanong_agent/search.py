"""Read-only passage search: plain-Python BM25 and the existing hosted vector read RPC."""
from __future__ import annotations

import asyncio
import math
import re
from collections import Counter
from typing import Protocol

from backend.bintanong_retrieval.query import configuration_identity

from .corpus import Corpus, Passage

MAX_TOP_K = 8
BM25_K1, BM25_B = 1.5, 0.75
MIN_SIMILARITY = 0.5  # the retrieval default (RetrievalSettings.min_similarity)


def _clamp(top_k: int) -> int:
    return max(1, min(MAX_TOP_K, top_k))


def _tokens(text: str) -> list[str]:
    return re.findall(r'\w+', text.casefold())


class SearchBackend(Protocol):
    async def search(self, query: str, *, top_k: int = MAX_TOP_K) -> tuple[Passage, ...]: ...


class KeywordSearch:
    def __init__(self, corpus: Corpus):
        self._passages = corpus.passages
        self._term_counts = [Counter(_tokens(p.title + ' ' + p.text)) for p in self._passages]
        self._lengths = [sum(counts.values()) for counts in self._term_counts]
        self._average_length = sum(self._lengths) / len(self._lengths) if self._lengths else 0.0
        self._document_frequency = Counter(term for counts in self._term_counts for term in counts)

    def _score(self, index: int, terms: set[str]) -> float:
        total, counts = len(self._passages), self._term_counts[index]
        score = 0.0
        for term in terms & counts.keys():
            df = self._document_frequency[term]
            idf = math.log(1 + (total - df + 0.5) / (df + 0.5))
            tf = counts[term]
            norm = 1 - BM25_B + BM25_B * self._lengths[index] / self._average_length
            score += idf * tf * (BM25_K1 + 1) / (tf + BM25_K1 * norm)
        return score

    async def search(self, query: str, *, top_k: int = MAX_TOP_K) -> tuple[Passage, ...]:
        terms = set(_tokens(query))
        scored = [(self._score(i, terms), p) for i, p in enumerate(self._passages)]
        ranked = sorted((s for s in scored if s[0] > 0), key=lambda s: (-s[0], s[1].short_id))
        return tuple(p for _, p in ranked[:_clamp(top_k)])


class VectorSearch:
    def __init__(self, corpus: Corpus, encoder, client, release_id: str):
        self._corpus, self._encoder, self._client, self._release_id = corpus, encoder, client, release_id
        self._by_chunk_id = {p.chunk_id: p for p in corpus.passages}

    def _read(self, query: str, top_k: int) -> dict:
        params = dict(p_release_id=self._release_id, p_config=configuration_identity(self._encoder.config),
                      query_embedding=list(self._encoder.encode(query)), p_top_k=top_k,
                      p_min_similarity=MIN_SIMILARITY)
        return self._client.rpc('retrieve_context', params, role='runtime')

    async def search(self, query: str, *, top_k: int = MAX_TOP_K) -> tuple[Passage, ...]:
        top_k = _clamp(top_k)
        result = await asyncio.to_thread(self._read, query, top_k)
        if result.get('status') != 'ok':
            raise ValueError(result.get('status', 'storage_error'))
        found = (self._by_chunk_id.get(row['chunk']['chunk_id']) for row in result['items'])
        return tuple(p for p in found if p is not None)[:top_k]
