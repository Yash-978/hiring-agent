from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_meta_reports_demo_mode_for_the_fake_provider(client: TestClient) -> None:
    response = client.get("/meta")
    assert response.status_code == 200
    assert response.json() == {
        "llm_provider": "fake",
        "llm_model": "fake",
        "demo_mode": True,
    }
