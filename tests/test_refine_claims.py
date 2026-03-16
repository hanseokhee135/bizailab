import json

from claim_refinement.agent import refine_claims, serialize_output
from claim_refinement.models import RefinementInput


def _payload(text: str, lang: str | None = None) -> RefinementInput:
    return RefinementInput(
        source_text=text,
        source_language=lang,
        source_title="sample",
        platform="reddit",
        author="user1",
        timestamp="2026-01-01T00:00:00Z",
    )


def test_korean_slang_heavy_post():
    out = refine_claims(_payload("ㄹㅇ 그 회사 어제 매출 30% 떡상함"))
    assert out.slang_abbreviation_map
    assert any(c.claim_type == "statistic" for c in out.claims)


def test_english_rumor_post():
    out = refine_claims(_payload("I heard allegedly City Hall hid the report."))
    assert out.claims[0].speaker_intent == "rumor"
    assert out.claims[0].stance == "unendorsed"


def test_mixed_language_input():
    out = refine_claims(_payload("서울 market share가 12%로 올랐대", "mixed"))
    assert out.source_language == "mixed"
    assert out.claims


def test_quoted_speech_split():
    out = refine_claims(_payload('The CEO said "we shipped 2M units" last week.'))
    assert len(out.claims) >= 2
    assert any(r.relation == "quoted_content_of" for c in out.claims for r in c.relations)


def test_causal_claim_split():
    out = refine_claims(_payload("Sales dropped because the app crashed for 3 hours."))
    assert len(out.claims) >= 3
    assert any(c.claim_type == "causal" for c in out.claims)


def test_statistical_claim_preserves_number_context():
    out = refine_claims(_payload("Unemployment hit 4.2% in Seoul in 2025."))
    stat = [c for c in out.claims if c.claim_type == "statistic"][0]
    assert "4.2%" in (stat.context.numbers_or_units or "")


def test_unresolved_reference_marked():
    out = refine_claims(_payload("He took the money yesterday."))
    assert out.claims[0].ambiguities
    assert out.claims[0].ambiguities[0].resolution == "unresolved"


def test_question_form_claim_unendorsed():
    out = refine_claims(_payload("Did minister A delete the audit file?"))
    assert out.claims[0].speaker_intent == "question"
    assert out.claims[0].stance == "unendorsed"


def test_sarcasm_with_and_without_literal_claim():
    out1 = refine_claims(_payload("Great, another totally transparent cover-up happened."))
    out2 = refine_claims(_payload("lol sure best government ever!!!"))
    assert out1.claims
    assert out2.discarded_items


def test_factual_plus_opinion_mixed_post_and_serialization():
    out = refine_claims(_payload("GDP grew by 2%. This policy is stupid."))
    assert any(c.claim_type == "statistic" for c in out.claims)
    assert any(d.reason == "insult" for d in out.discarded_items)
    s = serialize_output(out)
    parsed = json.loads(s)
    assert parsed["task"] == "claim_refinement"
