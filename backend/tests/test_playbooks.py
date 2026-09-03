import pytest

from app.playbooks import get_playbook


def test_list_playbooks_returns_all_three_verticals(client):
    res = client.get("/api/playbooks")
    assert res.status_code == 200
    body = res.json()
    verticals = {p["vertical"] for p in body}
    assert verticals == {"cable_internet", "cell_phone", "medical"}
    for playbook in body:
        assert playbook["display_name"]
        assert playbook["strategy_notes"]


def test_list_playbooks_includes_provider_specific_entries(client):
    res = client.get("/api/playbooks")
    body = res.json()
    providers = {p["provider"] for p in body if p["provider"]}
    assert providers == {"comcast", "spectrum", "cox", "verizon", "att", "tmobile"}
    # Every provider-specific entry should carry richer guidance than the
    # generic fallback layer.
    for playbook in body:
        if playbook["provider"]:
            assert playbook["trigger_phrases"]
            assert playbook["retention_routing"]


@pytest.mark.parametrize(
    "raw_provider,expected_canonical",
    [
        ("Comcast", "comcast"),
        ("Xfinity", "comcast"),
        ("Comcast Xfinity", "comcast"),
        ("Charter", "spectrum"),
        ("Spectrum", "spectrum"),
        ("AT&T", "att"),
        ("at&t", "att"),
        ("T-Mobile", "tmobile"),
        ("T Mobile", "tmobile"),
    ],
)
def test_get_playbook_matches_provider_aliases(raw_provider, expected_canonical):
    playbook = get_playbook("cable_internet" if expected_canonical in {"comcast", "spectrum", "cox"} else "cell_phone", raw_provider)
    assert playbook is not None
    assert playbook.provider == expected_canonical


def test_get_playbook_falls_back_to_generic_for_unknown_provider():
    playbook = get_playbook("cable_internet", "Some Regional ISP Nobody Has Heard Of")
    assert playbook is not None
    assert playbook.provider is None
    assert playbook.vertical == "cable_internet"


def test_get_playbook_falls_back_to_generic_when_no_provider_given():
    playbook = get_playbook("medical")
    assert playbook is not None
    assert playbook.provider is None
