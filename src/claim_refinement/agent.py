from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import List, Sequence

from .models import (
    AmbiguityItem,
    Attribution,
    ClaimItem,
    ContextFields,
    DiscardedItem,
    EntityItem,
    RefinementInput,
    RefinementOutput,
    RelationItem,
    SearchHints,
    SlangAbbreviationMapItem,
)

KO_HINT_RE = re.compile(r"[가-힣]")
NUM_RE = re.compile(r"\b\d+(?:[.,]\d+)?%?\b")
RUMOR_MARKERS = ["allegedly", "rumor has it", "i heard", "카더라", "라고 함", "라는 말", "seems", "apparently"]
SPECULATION_MARKERS = ["maybe", "might", "possibly", "같다", "듯", "추정"]
QUESTION_RE = re.compile(r"\?$|^(did|is|are|was|were|do|does|can|could|didn\'t)\b", re.I)
CAUSAL_MARKERS = ["because", "due to", "therefore", "caused", "때문", "탓", "그래서"]
QUOTE_RE = re.compile(r'"([^"]+)"|\'([^\']+)\'|“([^”]+)”')

SLANG_MAP = {
    "ㄹㅇ": ("정말", "really", "slang"),
    "ㅇㅇ": ("응/맞음", "yes/true", "slang"),
    "tbh": ("솔직히", "to be honest", "abbreviation"),
    "imo": ("내 생각에는", "in my opinion", "abbreviation"),
    "wtf": ("말도 안 된다", "what the heck", "slang"),
    "개꿀": ("매우 유리함", "very beneficial", "slang"),
    "레전드": ("매우 이례적", "extraordinary", "slang"),
}


@dataclass
class Segment:
    idx: int
    text: str


def _detect_language(text: str, declared: str | None) -> str:
    if declared in {"ko", "en", "mixed", "unknown"}:
        return declared
    has_ko = bool(KO_HINT_RE.search(text))
    has_en = bool(re.search(r"[A-Za-z]", text))
    if has_ko and has_en:
        return "mixed"
    if has_ko:
        return "ko"
    if has_en:
        return "en"
    return "unknown"


def _split_segments(text: str) -> List[Segment]:
    chunks = [c.strip() for c in re.split(r"(?<=[.!?])\s+|\n+", text) if c.strip()]
    return [Segment(idx=i + 1, text=c) for i, c in enumerate(chunks)]


def _normalize_text(text: str):
    normalized = text
    mappings: list[SlangAbbreviationMapItem] = []
    for original, (ko, en, typ) in SLANG_MAP.items():
        if re.search(rf"\b{re.escape(original)}\b", normalized, flags=re.I):
            normalized = re.sub(rf"\b{re.escape(original)}\b", en if not KO_HINT_RE.search(text) else ko, normalized, flags=re.I)
            mappings.append(
                SlangAbbreviationMapItem(
                    original=original,
                    normalized_ko=ko,
                    normalized_en=en,
                    type=typ,  # type: ignore[arg-type]
                    confidence=0.9,
                    note="Rule-based slang/abbreviation normalization",
                )
            )
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized, mappings


def _is_discardable(segment: str):
    s = segment.lower().strip()
    if not s:
        return "non_factual", "Empty segment"
    if s.startswith("ㅋㅋ") or s.startswith("lol"):
        return "emotion", "Laughter/reaction without propositional content"
    if any(w in s for w in ["idiot", "stupid", "멍청", "바보"]):
        return "insult", "Insult without independently verifiable proposition"
    if s.endswith("!") and not NUM_RE.search(s) and not re.search(r"\b(is|was|did|했다|있다|없다)\b", s):
        return "emotion", "Exclamatory reaction with limited factual content"
    return None, ""


def _intent_and_stance(seg: str):
    low = seg.lower()
    if QUESTION_RE.search(seg.strip()):
        return "question", "unendorsed"
    if any(m in low for m in RUMOR_MARKERS):
        return "rumor", "unendorsed"
    if any(m in low for m in SPECULATION_MARKERS):
        return "speculation", "unclear"
    if "sarcasm" in low or "비꼬" in low:
        return "sarcasm", "unclear"
    return "assertion", "endorsed"


def _claim_type(seg: str):
    low = seg.lower()
    if QUOTE_RE.search(seg):
        return "quote"
    if any(m in low for m in CAUSAL_MARKERS):
        return "causal"
    if NUM_RE.search(seg):
        return "statistic"
    if any(k in low for k in ["law", "bill", "regulation", "법", "시행령"]):
        return "policy"
    return "event"


def _extract_entities(seg: str):
    entities: list[EntityItem] = []
    for token in re.findall(r"\b[A-Z][A-Za-z0-9_-]{1,}\b", seg):
        entities.append(EntityItem(name=token, type="unknown", normalized_name=None))
    for token in re.findall(r"[가-힣]{2,}(?:시|군|구|청|부|당|회사)?", seg):
        if token not in {"그리고", "하지만", "정말", "아니다"}:
            entities.append(EntityItem(name=token, type="unknown", normalized_name=None))
    seen = set()
    uniq = []
    for e in entities:
        if e.name not in seen:
            uniq.append(e)
            seen.add(e.name)
    return uniq[:8]


def _build_context(seg: str, payload: RefinementInput):
    number_match = NUM_RE.findall(seg)
    pronouns = re.findall(r"\b(he|she|they|it|this|that|그|그녀|그들|걔|얘)\b", seg, flags=re.I)
    ambiguities = []
    if pronouns:
        ambiguities.append(
            AmbiguityItem(
                text=", ".join(pronouns),
                reason="Pronoun/reference is not confidently resolvable from local context",
                resolution="unresolved",
                note="Keep unresolved for investigator follow-up",
            )
        )
    explicit = []
    if payload.source_title:
        explicit.append(f"title={payload.source_title}")
    if payload.platform:
        explicit.append(f"platform={payload.platform}")
    if payload.timestamp:
        explicit.append(f"timestamp={payload.timestamp}")
    inferred = []
    if payload.thread_context:
        inferred.append("thread_context provided")
    return ContextFields(
        who=payload.author,
        action_or_predicate=seg,
        object_or_target=None,
        when=payload.timestamp,
        where=None,
        numbers_or_units=", ".join(number_match) if number_match else None,
        conditions_or_scope=None,
        explicit_context=explicit,
        inferred_context=inferred,
    ), ambiguities


def _translation_stub(text: str, target: str) -> str:
    if target == "ko":
        return f"[KO] {text}"
    return f"[EN] {text}"


def refine_claims(payload: RefinementInput) -> RefinementOutput:
    language = _detect_language(payload.source_text, payload.source_language)
    segments = _split_segments(payload.source_text)

    all_maps: list[SlangAbbreviationMapItem] = []
    discarded: list[DiscardedItem] = []
    claims: list[ClaimItem] = []

    claim_counter = 1
    for segment in segments:
        discard_reason, note = _is_discardable(segment.text)
        if discard_reason:
            discarded.append(DiscardedItem(text=segment.text, reason=discard_reason, note=note))
            continue

        normalized, maps = _normalize_text(segment.text)
        all_maps.extend(maps)

        # quoted speech split: speech act + quoted content
        quoted_contents = [m.group(1) or m.group(2) or m.group(3) for m in QUOTE_RE.finditer(segment.text)]
        subclaims: Sequence[tuple[str, str]]
        if quoted_contents:
            subclaims = [(segment.text, "speech_act")] + [(q, "quoted_content") for q in quoted_contents]
        elif any(m in segment.text.lower() for m in CAUSAL_MARKERS):
            parts = re.split(r"\b(?:because|due to|therefore|때문에|그래서|caused by|caused)\b", segment.text, flags=re.I)
            event_parts = [p.strip(" ,") for p in parts if p.strip()]
            subclaims = [(p, "event") for p in event_parts]
            subclaims = list(subclaims) + [(segment.text, "causal_link")]
        else:
            subclaims = [(segment.text, "single")]

        for text, kind in subclaims:
            intent, stance = _intent_and_stance(text)
            ctype = "causal" if kind == "causal_link" else ("quote" if "quote" in kind or kind == "speech_act" else _claim_type(text))
            context, ambiguities = _build_context(text, payload)
            claim_id = f"C{claim_counter}"
            relations = []
            if kind == "quoted_content" and claim_counter > 1:
                relations.append(RelationItem(target_claim_id=f"C{claim_counter-1}", relation="quoted_content_of"))
            if kind == "causal_link" and claim_counter > 2:
                relations.extend(
                    [
                        RelationItem(target_claim_id=f"C{claim_counter-1}", relation="causes"),
                        RelationItem(target_claim_id=f"C{claim_counter-2}", relation="causes"),
                    ]
                )
            query = re.sub(r"[^\w\s가-힣%]", " ", text).strip()
            claims.append(
                ClaimItem(
                    claim_id=claim_id,
                    parent_segment_id=f"S{segment.idx}",
                    claim_type=ctype,  # type: ignore[arg-type]
                    investigation_priority="high" if ctype in {"statistic", "causal", "quote"} else "medium",
                    verifiability="limited" if intent in {"rumor", "speculation"} else ("indirect" if intent == "question" else "direct"),
                    refinement_confidence=0.8 if intent not in {"sarcasm"} else 0.6,
                    original_text=text,
                    original_language=language,  # type: ignore[arg-type]
                    normalized_text_ko=_translation_stub(normalized, "ko"),
                    normalized_text_en=_translation_stub(normalized, "en"),
                    atomic_claim_ko=_translation_stub(text, "ko"),
                    atomic_claim_en=_translation_stub(text, "en"),
                    speaker_intent=intent,  # type: ignore[arg-type]
                    stance=stance,  # type: ignore[arg-type]
                    attribution=Attribution(
                        claim_made_by=payload.author,
                        claim_about=None,
                        quoted_speaker=payload.author if kind == "speech_act" else None,
                        reported_by=payload.author,
                    ),
                    context=context,
                    entities=_extract_entities(text),
                    ambiguities=ambiguities,
                    relations=relations,
                    search_hints=SearchHints(
                        keywords_ko=[w for w in re.findall(r"[가-힣A-Za-z0-9%]+", text)[:8]],
                        keywords_en=[w.lower() for w in re.findall(r"[A-Za-z0-9%]+", text)[:8]],
                        query_ko=f"{query} 사실 확인",
                        query_en=f"{query} fact check",
                        recommended_source_types=["news_archive", "official_release", "factcheck_db"],
                    ),
                    notes_for_investigation="Maintain original uncertainty and verify attribution, time, location, and numeric details.",
                )
            )
            claim_counter += 1

    norm_passage, _ = _normalize_text(payload.source_text)
    summary = payload.source_text[:180] + ("..." if len(payload.source_text) > 180 else "")

    return RefinementOutput(
        source_language=language,  # type: ignore[arg-type]
        input_summary=summary,
        normalized_passage_ko=_translation_stub(norm_passage, "ko"),
        normalized_passage_en=_translation_stub(norm_passage, "en"),
        slang_abbreviation_map=all_maps,
        discarded_items=discarded,
        claims=claims,
    )


def serialize_output(output: RefinementOutput) -> str:
    """Serialize model into deterministic JSON for downstream pipelines."""
    return json.dumps(output.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
