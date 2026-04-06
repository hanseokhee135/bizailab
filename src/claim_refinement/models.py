from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


Language = Literal["ko", "en", "mixed", "unknown"]
Platform = Literal["dcinside", "everytime", "x", "reddit", "news", "other"]
MapType = Literal["slang", "abbreviation", "metaphor", "misspelling", "other"]
DiscardReason = Literal[
    "opinion",
    "emotion",
    "insult",
    "sarcasm_without_literal_claim",
    "pure_question",
    "command",
    "non_factual",
    "other",
]
ClaimType = Literal[
    "event",
    "statistic",
    "policy",
    "quote",
    "causal",
    "identity",
    "date_time",
    "location",
    "relationship",
    "legal",
    "financial",
    "medical",
    "other",
]
Priority = Literal["high", "medium", "low"]
Verifiability = Literal["direct", "indirect", "limited", "future", "not_verifiable"]
SpeakerIntent = Literal[
    "assertion",
    "question",
    "rumor",
    "quote",
    "denial",
    "speculation",
    "sarcasm",
    "repost",
    "other",
]
Stance = Literal["endorsed", "unendorsed", "counterclaim", "unclear"]
EntityType = Literal[
    "person",
    "organization",
    "location",
    "product",
    "law",
    "dataset",
    "event",
    "other",
    "unknown",
]
AmbiguityResolution = Literal["resolved", "unresolved"]
RelationType = Literal[
    "precedes",
    "follows",
    "causes",
    "same_event",
    "same_entity",
    "supports_context_for",
    "contradicts",
    "quoted_content_of",
    "other",
]
SourceType = Literal[
    "official_release",
    "government_data",
    "law_or_regulation",
    "court_record",
    "company_filing",
    "news_archive",
    "academic_paper",
    "factcheck_db",
    "other",
]


class RefinementInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_text: str
    source_title: Optional[str] = None
    source_language: Optional[Language] = None
    platform: Optional[Platform] = None
    author: Optional[str] = None
    timestamp: Optional[str] = None
    thread_context: Optional[List[str]] = None
    quoted_context: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class SlangAbbreviationMapItem(BaseModel):
    original: str
    normalized_ko: str
    normalized_en: str
    type: MapType
    confidence: float = Field(ge=0.0, le=1.0)
    note: str


class DiscardedItem(BaseModel):
    text: str
    reason: DiscardReason
    note: str


class Attribution(BaseModel):
    claim_made_by: Optional[str] = None
    claim_about: Optional[str] = None
    quoted_speaker: Optional[str] = None
    reported_by: Optional[str] = None


class ContextFields(BaseModel):
    who: Optional[str] = None
    action_or_predicate: Optional[str] = None
    object_or_target: Optional[str] = None
    when: Optional[str] = None
    where: Optional[str] = None
    numbers_or_units: Optional[str] = None
    conditions_or_scope: Optional[str] = None
    explicit_context: List[str] = Field(default_factory=list)
    inferred_context: List[str] = Field(default_factory=list)


class EntityItem(BaseModel):
    name: str
    type: EntityType
    normalized_name: Optional[str] = None


class AmbiguityItem(BaseModel):
    text: str
    reason: str
    resolution: AmbiguityResolution
    note: str


class RelationItem(BaseModel):
    target_claim_id: str
    relation: RelationType


class SearchHints(BaseModel):
    keywords_ko: List[str] = Field(default_factory=list)
    keywords_en: List[str] = Field(default_factory=list)
    query_ko: str
    query_en: str
    recommended_source_types: List[SourceType] = Field(default_factory=lambda: ["news_archive", "other"])


class ClaimItem(BaseModel):
    claim_id: str
    parent_segment_id: str
    claim_type: ClaimType
    investigation_priority: Priority
    verifiability: Verifiability
    refinement_confidence: float = Field(ge=0.0, le=1.0)

    original_text: str
    original_language: Language
    normalized_text_ko: str
    normalized_text_en: str

    atomic_claim_ko: str
    atomic_claim_en: str

    speaker_intent: SpeakerIntent
    stance: Stance

    attribution: Attribution
    context: ContextFields
    entities: List[EntityItem] = Field(default_factory=list)
    ambiguities: List[AmbiguityItem] = Field(default_factory=list)
    relations: List[RelationItem] = Field(default_factory=list)
    search_hints: SearchHints
    notes_for_investigation: str


class RefinementOutput(BaseModel):
    task: Literal["claim_refinement"] = "claim_refinement"
    source_language: Language
    input_summary: str
    normalized_passage_ko: str
    normalized_passage_en: str
    slang_abbreviation_map: List[SlangAbbreviationMapItem] = Field(default_factory=list)
    discarded_items: List[DiscardedItem] = Field(default_factory=list)
    claims: List[ClaimItem] = Field(default_factory=list)
