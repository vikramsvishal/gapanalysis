from v2.application import ApplicationService

def test_application_service_health():
    health=ApplicationService().health()
    assert health["application"]=="CMDB_IS_GOVERNANCE"
    assert health["golden_version"]=="1.4.1"
    assert health["mode"]=="LOCAL"
    assert health["status"]=="READY"
