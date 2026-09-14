# V2 Architecture Build

V2 is being built beside `WPP_CMDB_IS_Gap_Analysis_V1_4_1_Consolidated.py`.

## Golden rule

V1.4.1 remains the golden business-behavior baseline. V2 changes must not modify the V1.4.1 file until regression coverage demonstrates equivalent decisions for the affected capability.

## Current alpha structure

```text
v2/
  domain.py             Canonical governance contracts
  policies.py           Explicit deterministic governance policies
  legacy_adapter.py     Transitional access to V1.4.1 logic
  normalization.py      V2 facade over golden normalization behavior
  catalog.py            Deterministic authoritative catalog resolver
```

## Migration strategy

1. Protect V1.4.1.
2. Capture golden behavior in tests.
3. Introduce explicit domain contracts.
4. Extract one deterministic service at a time.
5. Keep Excel/file handling as adapters.
6. Introduce web/API execution only after domain behavior is stable.
7. Add agent orchestration around deterministic services.
8. Add AI only where it provides measurable value without becoming the authority for governed decisions.

## Non-negotiable governance rules

- Catalog-controlled values must resolve to an authoritative catalog record before load.
- Similarity is a candidate mechanism, not load authorization.
- Ambiguous matches are blocked/reviewed.
- No-match conditions can produce a catalog-update-required state.
- FQDN requirements remain policy-driven and human-in-the-loop where required.
- Source evidence, normalized evidence, current IS state, required value and load value remain separate concepts.
