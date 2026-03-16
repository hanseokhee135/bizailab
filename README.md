# Claim Refinement Agent

Production-ready claim refinement module for a multi-agent fact-checking pipeline.

## What it does
- Accepts Korean, English, and mixed-language posts.
- Normalizes informal slang/abbreviations.
- Extracts verification-worthy atomic claims.
- Preserves uncertainty, attribution, negation, and numeric details.
- Outputs strict JSON-compatible data via typed Pydantic v2 models.

## Structure
- `src/claim_refinement/prompt.py`: runtime system prompt.
- `src/claim_refinement/models.py`: input/output schema models.
- `src/claim_refinement/agent.py`: `refine_claims` and deterministic serializer.
- `tests/test_refine_claims.py`: required scenario tests.

## Usage

```python
from claim_refinement import RefinementInput, refine_claims, serialize_output

payload = RefinementInput(
    source_text="I heard allegedly the city hid the report.",
    source_language="en",
    platform="x",
)

result = refine_claims(payload)
json_output = serialize_output(result)
print(json_output)
```

## Run tests

```bash
python -m pytest -q
```
