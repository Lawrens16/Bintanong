"""Read-only view of the reviewed document chunks: short ids, topics and readable passage text."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable

TITLE_FIELDS = ('service_title_and_description', 'service_title')
LABEL_LENGTH = 120


@dataclass(frozen=True)
class Passage:
    short_id: str
    chunk_id: str
    title: str
    source: str
    page: int | None
    text: str
    limits: tuple[str, ...]
    neighbour_ids: tuple[str, ...]


@dataclass(frozen=True)
class Topic:
    topic_id: str
    label: str
    passage_ids: tuple[str, ...]


def _fields(chunk: dict) -> list[dict]:
    return json.loads(chunk['text']).get('fields', [])


def _topic_id(type_fields: dict) -> str:
    group = type_fields.get('service_group')
    if isinstance(group, dict) and group.get('logical_step_id'):
        return group['logical_step_id']
    reading_id = type_fields['reading_id']
    return re.sub(r'\d+$', '', reading_id) or reading_id


def _limit_text(limit) -> str:
    return limit if isinstance(limit, str) else limit.get('message') or limit.get('issue', '')


def _passage_text(chunk: dict, limits: tuple[str, ...]) -> str:
    lines = []
    for field in _fields(chunk):
        value = field.get('value')
        if field.get('source_blank'):
            value = '(blank in the source)'
        elif not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False)
        lines.append(f"{field['name']}: {value}")
    if limits:
        lines.append('Source limits:')
        lines.extend('- ' + limit for limit in limits)
    return '\n'.join(lines)


def _topic_label(topic_id: str, chunks: list[dict]) -> str:
    for chunk in chunks:
        for field in _fields(chunk):
            if field.get('name') in TITLE_FIELDS and isinstance(field.get('value'), str):
                title = ' '.join(field['value'].split())[:LABEL_LENGTH]
                if title:
                    return title
    return re.sub(r'[-_]+', ' ', topic_id)


class Corpus:
    def __init__(self, passages: tuple[Passage, ...], topics: tuple[Topic, ...]):
        self.passages, self.topics = passages, topics
        self._by_short_id = {p.short_id: p for p in passages}

    @classmethod
    def from_snapshot(cls, snapshot: dict) -> 'Corpus':
        chunks = sorted(snapshot['chunks'], key=lambda chunk: chunk['chunk_id'])
        short_ids = {chunk['chunk_id']: f'C{number:03d}' for number, chunk in enumerate(chunks, 1)}
        by_topic: dict[str, list[dict]] = {}
        for chunk in chunks:
            by_topic.setdefault(_topic_id(chunk['type_fields']), []).append(chunk)
        labels = {topic_id: _topic_label(topic_id, group) for topic_id, group in by_topic.items()}
        passages = []
        for topic_id, group in by_topic.items():
            for chunk in group:
                type_fields = chunk['type_fields']
                limits = tuple(_limit_text(limit) for limit in type_fields.get('source_limits', []))
                spans = chunk.get('spans') or []
                passages.append(Passage(
                    short_ids[chunk['chunk_id']], chunk['chunk_id'], labels[topic_id], chunk['source_label'],
                    spans[0].get('page') if spans else None, _passage_text(chunk, limits), limits,
                    tuple(short_ids[n] for n in type_fields.get('required_neighbor_chunk_ids', []) if n in short_ids)))
        topics = tuple(Topic(topic_id, labels[topic_id], tuple(short_ids[c['chunk_id']] for c in group))
                       for topic_id, group in sorted(by_topic.items()))
        return cls(tuple(sorted(passages, key=lambda p: p.short_id)), topics)

    def get(self, short_id: str) -> Passage:
        return self._by_short_id[short_id]

    def with_neighbours(self, short_ids: Iterable[str]) -> tuple[Passage, ...]:
        ordered: dict[str, Passage] = {}
        for short_id in short_ids:
            passage = self.get(short_id)
            for member in (passage, *(self.get(n) for n in passage.neighbour_ids)):
                ordered.setdefault(member.short_id, member)
        return tuple(ordered.values())

    def directory(self) -> str:
        return '\n'.join(f"{topic.topic_id}: {topic.label} ({', '.join(topic.passage_ids)})"
                         for topic in self.topics)
