from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

from rwi_bot.services.language import expand_aliases, normalize_text

_STOP_WORDS = {
    "a",
    "about",
    "all",
    "an",
    "and",
    "are",
    "can",
    "compare",
    "current",
    "do",
    "does",
    "explain",
    "for",
    "get",
    "have",
    "how",
    "i",
    "in",
    "is",
    "it",
    "know",
    "me",
    "of",
    "the",
    "their",
    "to",
    "what",
    "where",
    "which",
    "with",
    "work",
    "working",
    "works",
    "versus",
    "vs",
}
_TOKEN = re.compile(r"[a-z0-9][a-z0-9+'-]*", re.IGNORECASE)
_CATEGORY_TERMS = {
    "augment",
    "augments",
    "attribute",
    "attributes",
    "backpack",
    "chest",
    "exotic",
    "gear",
    "named",
    "skill",
    "skills",
    "specialization",
    "talent",
    "talents",
    "weapon",
    "weapons",
}
_GENERIC_REFERENCE_NAMES = {
    "accuracy",
    "armor",
    "damage",
    "gear",
    "health",
    "magazine size",
    "reload speed",
    "skill",
    "stability",
    "talent",
    "weapon",
    "weapon damage",
}


@dataclass(frozen=True, slots=True)
class ReferenceSnapshot:
    source: str
    commit: str
    committed_at: str
    license: str
    attribution: str
    record_count: int
    trust_boundary: str


@dataclass(frozen=True, slots=True)
class ReferenceRecord:
    source_file: str
    row_number: int
    name: str
    data: dict[str, str]
    search_text: str


@dataclass(frozen=True, slots=True)
class ReferenceHit:
    record: ReferenceRecord
    score: float
    match_kind: str = "overlap"


class Division2ReferenceCatalog:
    """Pinned low-trust data used to improve discovery, never as verified knowledge."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.snapshot = _load_snapshot(root / "SNAPSHOT.json")
        self.records = tuple(_load_records(root))

    @classmethod
    def packaged(cls) -> Division2ReferenceCatalog:
        root = Path(__file__).resolve().parents[1] / "data" / "div2hub_snapshot"
        return cls(root)

    def search(self, query: str, *, limit: int = 8) -> list[ReferenceHit]:
        if limit < 1:
            raise ValueError("Reference result limit must be positive.")
        normalized = expand_aliases(query)
        terms = _meaningful_terms(normalized)
        if not terms:
            return []
        specific_terms = terms - _CATEGORY_TERMS
        name_fragment = " ".join(
            token for token in _TOKEN.findall(normalized) if token in specific_terms
        )

        hits: list[ReferenceHit] = []
        for record in self.records:
            name = normalize_text(record.name)
            record_terms = _meaningful_terms(record.search_text)
            overlap = terms & record_terms
            category_match = _category_match(terms, record)
            exact_name = bool(name and re.search(rf"(?<!\w){re.escape(name)}(?!\w)", normalized))
            fuzzy_name = (
                fuzz.WRatio(name_fragment, name) / 100
                if name and len(name_fragment.replace(" ", "")) >= 4
                else 0.0
            )
            typo_name = (
                bool(specific_terms)
                and not overlap.intersection(specific_terms)
                and fuzzy_name >= 0.82
            )
            if not overlap and not category_match and not typo_name:
                continue
            if (
                specific_terms
                and not exact_name
                and not overlap.intersection(specific_terms)
                and not typo_name
            ):
                continue
            fuzzy = fuzz.token_set_ratio(normalized, name) / 100 if name else 0.0
            coverage = len(overlap) / len(terms)
            score = max(0.55 + 0.45 * coverage if exact_name else 0.0, 0.7 * coverage + 0.3 * fuzzy)
            if category_match:
                score = max(score, 0.45 + 0.25 * coverage)
            match_kind = "exact" if exact_name else "fuzzy" if typo_name else "overlap"
            if typo_name:
                score = max(score, fuzzy_name * 0.92)
            if score >= 0.42:
                hits.append(
                    ReferenceHit(
                        record=record,
                        score=min(score, 1.0),
                        match_kind=match_kind,
                    )
                )
        hits.sort(key=lambda hit: (-hit.score, hit.record.name, hit.record.source_file))
        return hits[:limit]


def reference_scope_prompt(hits: list[ReferenceHit], snapshot: ReferenceSnapshot) -> str | None:
    if not hits:
        return None
    rows: list[str] = []
    for hit in hits:
        compact = {key: value for key, value in hit.record.data.items() if value and value != "N/A"}
        rendered = json.dumps(compact, sort_keys=True, ensure_ascii=False)
        rows.append(
            f"- {hit.record.source_file}:{hit.record.row_number} ({hit.score:.2f}) {rendered[:900]}"
        )
    return (
        "LOCAL COMMUNITY RESEARCH SNAPSHOT — discovery hints only, not verified evidence. "
        "Use these rows to identify exact search terms and relationships, then verify every "
        "material current claim with the normal Red Horizon evidence rules. Source: "
        f"{snapshot.source}@{snapshot.commit[:12]} ({snapshot.license}).\n" + "\n".join(rows)
    )


def is_specific_reference_hit(hit: ReferenceHit) -> bool:
    return normalize_text(hit.record.name) not in _GENERIC_REFERENCE_NAMES


def _load_snapshot(path: Path) -> ReferenceSnapshot:
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return ReferenceSnapshot(
        source=str(payload["source"]),
        commit=str(payload["commit"]),
        committed_at=str(payload["committed_at"]),
        license=str(payload["license"]),
        attribution=str(payload["attribution"]),
        record_count=int(payload["record_count"]),
        trust_boundary=str(payload["trust_boundary"]),
    )


def _load_records(root: Path) -> list[ReferenceRecord]:
    records: list[ReferenceRecord] = []
    for path in sorted(root.rglob("*.csv")):
        source_file = path.relative_to(root).as_posix()
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row_number, row in enumerate(csv.DictReader(handle), start=2):
                data = {str(key): str(value or "").strip() for key, value in row.items() if key}
                name = data.get("name") or data.get("stat_name") or data.get("id") or source_file
                search_text = normalize_text(" ".join((source_file, *data.values())))
                records.append(
                    ReferenceRecord(
                        source_file=source_file,
                        row_number=row_number,
                        name=name,
                        data=data,
                        search_text=search_text,
                    )
                )
    return records


def _meaningful_terms(text: str) -> set[str]:
    return {
        token
        for token in _TOKEN.findall(normalize_text(text))
        if len(token) >= 2 and token not in _STOP_WORDS
    }


def _category_match(terms: set[str], record: ReferenceRecord) -> bool:
    path = record.source_file
    data = record.data
    if "exotic" in terms and data.get("is_exotic", "").casefold() == "true":
        return True
    if "named" in terms and data.get("is_named", "").casefold() == "true":
        return True
    categories = {
        "augment": "augments.csv",
        "augments": "augments.csv",
        "attribute": "attributes.csv",
        "attributes": "attributes.csv",
        "gear": "gear/",
        "skill": "skills/",
        "skills": "skills/",
        "specialization": "specializations/",
        "talent": "talents.csv",
        "talents": "talents.csv",
        "weapon": "weapons/",
        "weapons": "weapons/",
    }
    return any(term in categories and categories[term] in path for term in terms)
