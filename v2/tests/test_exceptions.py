from v2.exceptions import ExceptionStore


def test_exception_lifecycle(tmp_path):
    store = ExceptionStore(tmp_path / "exceptions.json")
    item = store.create(
        "RES-1",
        "CATALOG_AMBIGUOUS",
        "Catalog match requires review",
        "Multiple authoritative catalog candidates remain.",
        severity="HIGH",
        recommendation="Review the candidate and select an authorized catalog value.",
        evidence_ids=["EVD-1"],
    )
    assert item.status == "OPEN"
    assert item.evidence_ids == ["EVD-1"]

    resolved = store.resolve(item.exception_id, "reviewer", "Approved candidate CATALOG-42")
    assert resolved.status == "RESOLVED"
    assert resolved.resolved_by == "reviewer"

    restored = ExceptionStore(tmp_path / "exceptions.json")
    assert restored.get(item.exception_id).resolution == "Approved candidate CATALOG-42"
