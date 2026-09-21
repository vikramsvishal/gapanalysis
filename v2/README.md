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
  hardware_governance.py Stable hardware-governance service seam
  catalog_matching.py   Extracted V1.4.1 hardware catalog matching engine
```

## Hardware catalog matching extraction

The current `HardwareCatalogMatcher` is intentionally behavior-preserving. It extracts the V1.4.1 `_hw_index()` and `hardware_match()` behavior into a deterministic, independently testable component.

The extracted engine currently preserves:

- indexed hardware-model matching
- server manufacturer + model matching
- model-only matching
- legacy composite-index behavior
- token-overlap candidate matching
- ambiguity detection
- V1.4.1 status/detail/score values

It is **not yet the governance authority**. The protected V1.4.1 engine remains authoritative for end-to-end hardware governance until the full domain is regression-covered. The catalog identity resolution seam is now explicit through `AuthoritativeHardwareCatalogResolver`. It consumes matcher candidates but enforces the governance distinction between candidate identity and authorized catalog value:

- exact catalog identity can be load-authorized;
- partial/similarity candidates remain review-only;
- ambiguous candidates remain blocked/review-only;
- no-match conditions remain catalog-update-required.

The resolver is exposed by `HardwareGovernanceService.resolve_catalog_identity()`, but the protected V1.4.1 end-to-end hardware workflow still remains the execution oracle. The next extraction step is category presence/dependency governance, followed by shadow equivalence against V1.4.1 before any execution path is switched.

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

## Enterprise UI

The V2 branch includes a React + Vite enterprise UI under `web/`. The UI is intentionally an application shell over the governance engine, not a second implementation of business rules. Current screens cover the portal shell, governance overview, reconciliation workspace, governance decisions, jobs, exceptions and audit/evidence areas. The HTTP API seam is defined separately so real execution can be wired without moving governance logic into the browser.
