"""Route contract: endpoints authenticate through get_current_active_user.

get_current_user resolves the token but does not reject disabled accounts;
get_current_active_user (and the CurrentUser alias) does. An endpoint that
depends on get_current_user directly lets a disabled account through (#501,
the class of bug #439 fixed for artifacts, programs and grants).
@verified 41de99362
"""
import pytest
from fastapi.routing import APIRoute

from api.app.dependencies.auth import get_current_active_user, get_current_user
from api.app.main import app


def _api_routes(routes):
    """Yield every APIRoute, unwrapping included routers.

    FastAPI 0.141 keeps an included router as a single _IncludedRouter entry
    in app.routes instead of flattening its routes; original_router holds
    them, with the router prefix already applied to each path.
    """
    for r in routes:
        if isinstance(r, APIRoute):
            yield r
        elif hasattr(r, "original_router"):
            yield from _api_routes(r.original_router.routes)


def _direct_calls(route: APIRoute):
    return [d.call for d in route.dependant.dependencies]


@pytest.mark.unit
@pytest.mark.security
def test_no_endpoint_depends_on_get_current_user_directly():
    offenders = [
        f"{sorted(r.methods)} {r.path}"
        for r in _api_routes(app.routes)
        if get_current_user in _direct_calls(r)
    ]
    assert len(list(_api_routes(app.routes))) > 100, "route walk found too few routes"
    assert offenders == [], (
        "use get_current_active_user / CurrentUser so disabled accounts are "
        f"rejected: {offenders}"
    )


@pytest.mark.unit
@pytest.mark.security
def test_query_definition_endpoints_require_an_active_user():
    routes = [
        r for r in _api_routes(app.routes)
        if r.path.startswith("/query-definitions")
    ]
    assert routes, "query-definition routes not registered"
    for r in routes:
        assert get_current_active_user in _direct_calls(r), r.path
