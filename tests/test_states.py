def test_states_no_auth_required(client):
    resp = client.get("/states")
    assert resp.status_code == 200


def test_states_returns_all_four(client):
    resp = client.get("/states")
    data = resp.json()
    codes = [s["code"] for s in data["supported_states"]]
    assert "CA" in codes
    assert "TX" in codes
    assert "FL" in codes
    assert "NY" in codes


def test_states_structure(client):
    resp = client.get("/states")
    data = resp.json()
    for state in data["supported_states"]:
        assert "code" in state
        assert "name" in state
        assert "agency" in state
        assert "license_types" in state
        assert "status" in state
        assert "source_url" in state


def test_states_ca_has_license_types(client):
    resp = client.get("/states")
    data = resp.json()
    ca = next(s for s in data["supported_states"] if s["code"] == "CA")
    assert len(ca["license_types"]) > 0


def test_states_ny_is_coming_soon(client):
    resp = client.get("/states")
    data = resp.json()
    ny = next(s for s in data["supported_states"] if s["code"] == "NY")
    assert ny["status"] == "coming_soon"


def test_states_active_states(client):
    resp = client.get("/states")
    data = resp.json()
    active = [s for s in data["supported_states"] if s["status"] == "active"]
    active_codes = {s["code"] for s in active}
    assert "CA" in active_codes
    assert "TX" in active_codes
    assert "FL" in active_codes
