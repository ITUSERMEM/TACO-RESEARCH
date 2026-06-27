"""Bridge between research-wiki (file-based) and Redis AgentMemory (vector-searchable).

Provides PaperMemory class for semantic paper storage and retrieval,
syncing with the file-based research-wiki knowledge base.

Usage:
    from lit_researcher_bridge import PaperMemory

    pm = PaperMemory()
    pm.add_paper(slug='vaswani2017_attention', title='Attention Is All You Need', ...)
    results = pm.search_papers('transformer architecture')
"""

import json
import os
import re
import struct
import time
from datetime import datetime, timezone
from typing import Any, Optional

import yaml
from redis import Redis

from agent_memory import _embed, VECTOR_DIM, _ensure_index

_INDEX_PAPER = """
FT.CREATE idx:paper ON JSON PREFIX 1 paper: SCHEMA
    $.slug            AS slug            TAG     SORTABLE
    $.title           AS title           TEXT    SORTABLE
    $.authors[*]      AS authors         TAG     SORTABLE
    $.year            AS year            NUMERIC SORTABLE
    $.venue           AS venue           TAG     SORTABLE
    $.arxiv_id        AS arxiv_id        TAG
    $.tags[*]         AS tags            TAG
    $.memory_type     AS memory_type     TAG     SORTABLE
    $.owner_id        AS owner_id        TAG     SORTABLE
    $.timestamp       AS timestamp       NUMERIC SORTABLE
    $.embedding       AS embedding       VECTOR FLAT 6 TYPE FLOAT32 DIM 384 DISTANCE_METRIC COSINE
    $.content         AS content         TEXT
"""

_RESERVED_META_KEYS = {'type', 'node_id', 'title', 'authors', 'year', 'venue',
                       'external_ids', 'tags', 'added'}


class PaperMemory:
    """Vector-searchable paper knowledge base backed by Redis Stack."""

    def __init__(
        self,
        redis_url: str = 'redis://localhost:6379',
        namespace: str = 'academic',
        owner_id: str = 'literature-researcher',
    ):
        self.r = Redis.from_url(redis_url, decode_responses=True)
        self.namespace = namespace
        self.owner_id = owner_id
        _ensure_index(self.r, _INDEX_PAPER)

    # ---- CRUD ----

    def add_paper(
        self,
        slug: str,
        title: str,
        authors: Optional[list[str]] = None,
        year: Optional[int] = None,
        venue: str = 'arXiv',
        arxiv_id: Optional[str] = None,
        doi: Optional[str] = None,
        tags: Optional[list[str]] = None,
        content: str = '',
        abstract: str = '',
        sections: Optional[dict[str, str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Store or update a paper in Redis with embedding for semantic search."""
        key = f'paper:{slug}'
        now = time.time()

        doc = {
            'slug': slug,
            'title': title,
            'authors': authors or [],
            'year': year or 0,
            'venue': venue,
            'arxiv_id': arxiv_id or '',
            'doi': doi or '',
            'tags': tags or [],
            'memory_type': 'paper',
            'owner_id': self.owner_id,
            'namespace': self.namespace,
            'timestamp': now,
            'embedding': _embed(f'{title}. {abstract or content}'),
            'content': content or f'{title}. Authors: {", ".join(authors or [])}.',
            'abstract': abstract,
            'sections': sections or {},
            'metadata': metadata or {},
        }

        self.r.json().set(key, '$', doc)
        return key

    def get_paper(self, slug: str) -> Optional[dict[str, Any]]:
        key = f'paper:{slug}'
        raw = self.r.json().get(key)
        if raw is None:
            return None
        raw.pop('embedding', None)
        return raw

    def delete_paper(self, slug: str) -> bool:
        key = f'paper:{slug}'
        return bool(self.r.delete(key))

    # ---- Search ----

    def search_papers(
        self,
        query: str = '*',
        k: int = 10,
        tags: Optional[list[str]] = None,
        authors: Optional[list[str]] = None,
        venue: Optional[str] = None,
        year_min: Optional[int] = None,
        year_max: Optional[int] = None,
        owner_id: Optional[str] = None,
        hybrid: bool = False,
    ) -> list[dict[str, Any]]:
        """Search papers by semantic similarity + optional tag filters.

        Args:
            query: Semantic search query text (ignored if '*')
            k: Max results
            tags: Filter by tags (OR logic)
            authors: Filter by authors (OR logic)
            venue: Filter by venue (exact match)
            year_min/year_max: Numeric year range
            owner_id: Filter by owner
            hybrid: If False, use tag-only search (FT.SEARCH).
                    If True, use KNN + tag hybrid.

        Returns:
            List of paper dicts sorted by relevance (KNN distance or recency).
        """
        filters = []

        if tags:
            escaped = [t.replace('-', '\\-') for t in tags]
            filters.append(f'@tags:{{{" | ".join(escaped)}}}')

        if authors:
            escaped = [a.replace('-', '\\-') for a in authors]
            filters.append(f'@authors:{{{" | ".join(escaped)}}}')

        if venue:
            filters.append(f'@venue:{{{venue.replace("-", "\\-")}}}')

        if year_min is not None or year_max is not None:
            lo = year_min or 0
            hi = year_max or 9999
            filters.append(f'@year:[{lo} {hi}]')

        if owner_id:
            filters.append(f'@owner_id:{{{owner_id}}}')

        filter_expr = ' '.join(filters) if filters else '*'

        try:
            if hybrid and query and query != '*':
                vec_blob = struct.pack(f'{VECTOR_DIM}f', *_embed(query))
                result = self.r.execute_command(
                    'FT.SEARCH', 'idx:paper',
                    f'{filter_expr}=>[KNN {k} @embedding $vec AS embedding_score]',
                    'PARAMS', '2', 'vec', vec_blob,
                    'SORTBY', 'embedding_score', 'ASC',
                    'RETURN', '9', 'slug', 'title', 'authors', 'year', 'venue',
                    'arxiv_id', 'tags', 'content', 'embedding_score',
                    'DIALECT', '2',
                    'LIMIT', '0', str(k),
                )
            else:
                order = 'DESC' if not hybrid else 'DESC'
                result = self.r.execute_command(
                    'FT.SEARCH', 'idx:paper', filter_expr,
                    'SORTBY', 'timestamp', order,
                    'RETURN', '8', 'slug', 'title', 'authors', 'year', 'venue',
                    'arxiv_id', 'tags', 'content',
                    'LIMIT', '0', str(k),
                )
        except Exception:
            return []

        papers = []
        if result and result[0] > 0:
            for i in range(1, len(result), 2):
                key = result[i]
                fields = result[i + 1]
                entry = {}
                for j in range(0, len(fields), 2):
                    entry[fields[j]] = fields[j + 1]
                entry['_key'] = key
                papers.append(entry)

        return papers

    def count(self) -> int:
        try:
            info = self.r.execute_command('FT.INFO', 'idx:paper')
            for i in range(0, len(info), 2):
                k = info[i].decode() if isinstance(info[i], bytes) else info[i]
                v = info[i + 1].decode() if isinstance(info[i + 1], bytes) else info[i + 1]
                if k == 'num_docs':
                    return int(v)
        except Exception:
            pass
        return 0

    # ---- Research-Wiki Sync ----

    def sync_from_research_wiki(
        self,
        wiki_path: str = 'research-wiki',
        max_papers: int = 0,
    ) -> int:
        """Scan research-wiki/papers/*.md and sync each into Redis.

        Args:
            wiki_path: Path to research-wiki directory.
            max_papers: Max papers to sync (0 = all).

        Returns:
            Number of papers synced.
        """
        papers_dir = os.path.join(wiki_path, 'papers')
        if not os.path.isdir(papers_dir):
            return 0

        synced = 0
        for fname in sorted(os.listdir(papers_dir)):
            if not fname.endswith('.md'):
                continue
            if max_papers and synced >= max_papers:
                break

            fpath = os.path.join(papers_dir, fname)
            try:
                parsed = self._parse_paper_md(fpath)
                if parsed:
                    self.add_paper(**parsed)
                    synced += 1
            except Exception:
                continue

        return synced

    @staticmethod
    def _parse_paper_md(fpath: str) -> Optional[dict[str, Any]]:
        """Parse a research-wiki paper markdown file into add_paper kwargs."""
        with open(fpath, 'r', encoding='utf-8') as f:
            text = f.read()

        meta = {}
        body = text

        if text.startswith('---'):
            parts = text.split('---', 2)
            if len(parts) >= 3:
                try:
                    meta = yaml.safe_load(parts[1]) or {}
                except Exception:
                    meta = {}
                body = parts[2].strip()

        slug_raw = meta.get('node_id', '')
        slug = slug_raw.replace('paper:', '') if slug_raw else os.path.splitext(os.path.basename(fpath))[0]

        title = meta.get('title', slug)
        authors = meta.get('authors', [])
        year = meta.get('year')
        venue = meta.get('venue', 'arXiv')

        ext = meta.get('external_ids', {}) or {}
        arxiv_id = ext.get('arxiv', '')
        doi = ext.get('doi', '')

        tags = meta.get('tags', [])

        title_h1 = ''
        sections: dict[str, str] = {}
        current_section = 'abstract'
        current_lines: list[str] = []

        for line in body.split('\n'):
            if line.startswith('# ') and not line.startswith('## '):
                title_h1 = line.lstrip('# ').strip()
            elif line.startswith('## '):
                if current_lines:
                    sections[current_section] = '\n'.join(current_lines).strip()
                current_section = line.lstrip('## ').strip().lower().replace(' ', '_')
                current_lines = []
            else:
                current_lines.append(line)

        if current_lines:
            sections[current_section] = '\n'.join(current_lines).strip()

        abstract = sections.get('abstract', '')
        if not abstract and 'one-line_thesis' in sections:
            abstract = sections['one-line_thesis']

        section_order = ['one-line_thesis', 'problem_gap', 'method', 'key_results',
                         'assumptions', 'limitations_failure_modes',
                         'reusable_ingredients', 'open_questions', 'claims',
                         'connections', 'relevance_to_this_project',
                         'abstract_original']
        ordered_content_parts: list[str] = []
        for sec in section_order:
            if sec in sections and sections[sec]:
                label = sec.replace('_', ' ').title()
                ordered_content_parts.append(f'{label}:\n{sections[sec]}')

        content = '\n\n'.join(ordered_content_parts)

        return {
            'slug': slug,
            'title': title_h1 or title,
            'authors': authors if isinstance(authors, list) else [authors],
            'year': year,
            'venue': venue,
            'arxiv_id': arxiv_id,
            'doi': doi,
            'tags': tags,
            'content': content or abstract or title,
            'abstract': abstract,
            'sections': sections,
            'metadata': {k: v for k, v in meta.items() if k not in _RESERVED_META_KEYS},
        }
