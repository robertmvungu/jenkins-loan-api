import pytest

from app.main import create_app, monthly_payment


@pytest.fixture
def client():
    return create_app().test_client()


# ---- unit tests: calculation logic ----
def test_monthly_payment_standard():
    # 1,000,000 at 12% p.a. over 12 months
    assert monthly_payment(1_000_000, 12, 12) == 88848.79


def test_monthly_payment_zero_interest():
    assert monthly_payment(1200, 0, 12) == 100.0


@pytest.mark.parametrize("p,r,m", [(0, 10, 12), (1000, 10, 0), (1000, -1, 12)])
def test_monthly_payment_rejects_bad_input(p, r, m):
    with pytest.raises(ValueError):
        monthly_payment(p, r, m)


# ---- API tests ----
def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"


def test_quote_ok(client):
    res = client.post("/api/v1/quote", json={"principal": 1_000_000, "annual_rate": 12, "months": 12})
    body = res.get_json()
    assert res.status_code == 200
    assert body["monthly_payment"] == 88848.79
    assert body["total_interest"] == pytest.approx(66185.48, abs=0.01)


def test_quote_missing_field(client):
    res = client.post("/api/v1/quote", json={"principal": 1000})
    assert res.status_code == 400
    assert "missing field" in res.get_json()["error"]


def test_quote_invalid_value(client):
    res = client.post("/api/v1/quote", json={"principal": 1000, "annual_rate": 5, "months": 0})
    assert res.status_code == 400
