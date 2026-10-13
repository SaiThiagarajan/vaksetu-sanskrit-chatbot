"""Integration tests for the Flask routes in app.py."""

import pytest

from app import app
from sanskrit_engine import VERSION


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


def test_home_page_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "वाक्सेतुः".encode("utf-8") in response.data


def test_health_endpoint(client):
    data = client.get("/health").get_json()
    assert data["status"] == "ok"
    assert data["version"] == VERSION


def test_chat_endpoint(client):
    response = client.post("/api/chat", json={"message": "sandhi deva + ālaya", "language": "en"})
    assert response.status_code == 200
    data = response.get_json()
    assert data["intent"] == "sandhi"
    assert "देवालय" in data["reply"]


def test_empty_message_is_rejected(client):
    response = client.post("/api/chat", json={"message": "   "})
    assert response.status_code == 400
