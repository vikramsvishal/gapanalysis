from v2.shadow_migration import ShadowMigrationStore
from pathlib import Path

def test_shadow_classification_is_persistent(tmp_path: Path):
    store = ShadowMigrationStore(tmp_path / "shadow.json")
    record = store.upsert("RES-1", 3, "recommended_action", "POLICY_QUESTION", "Golden behavior differs", "architect")
    assert record.status == "POLICY_QUESTION"

    reloaded = ShadowMigrationStore(tmp_path / "shadow.json")
    summary = reloaded.summary("RES-1")
    assert summary["counts"]["POLICY_QUESTION"] == 1
    assert summary["classifications"][0]["owner"] == "architect"

def test_shadow_classification_rejects_unknown_status(tmp_path: Path):
    store = ShadowMigrationStore(tmp_path / "shadow.json")
    try:
        store.upsert("RES-1", 1, "field", "UNKNOWN")
        assert False, "expected ValueError"
    except ValueError:
        pass
