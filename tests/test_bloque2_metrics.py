from __future__ import annotations

from app.services.admin_service import AdminService
from app.core.security import AuthContext

def test_metrics_filters_and_series():
    auth = AuthContext(external_auth_id="t", institucion_id=1, tipo_miembro="ADMIN")
    svc = AdminService()
    # Without filters — should work
    res = svc.get_metrics(auth)
    assert hasattr(res, "series")
    assert res.desde is None
    # With range (likely empty but must not error)
    res2 = svc.get_metrics(auth, desde="2099-01-01", hasta="2099-12-31")
    assert res2.desde == "2099-01-01"
    assert res2.series == []
