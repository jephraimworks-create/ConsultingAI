import os
from pathlib import Path
import pytest

@pytest.fixture()
def client(tmp_path,monkeypatch):
    monkeypatch.setenv("MENSANA_DB",str(tmp_path/"test.db"))
    # Modules keep the configured path at import time, so reload for isolation.
    import importlib,app.database
    importlib.reload(app.database)
    import app.services,app.seed,app.main
    importlib.reload(app.services); importlib.reload(app.seed); importlib.reload(app.main)
    from fastapi.testclient import TestClient
    with TestClient(app.main.app) as test_client: yield test_client

def test_health_and_seed(client):
    assert client.get("/api/health").json()["status"]=="ok"
    assert client.get("/api/stats").json()["companies"]==6

def test_call_removes_company_from_new_queue(client):
    companies=client.get("/api/companies?status=NEW").json(); target=companies[0]
    response=client.post(f"/api/companies/{target['id']}/calls",json={"reached":"REACHED","opportunity":"YES","notes":"Confirmed need"})
    assert response.status_code==200
    assert target["id"] not in [c["id"] for c in client.get("/api/companies?status=NEW").json()]
    assert client.get(f"/api/companies/{target['id']}").json()["status"]=="OPPORTUNITY"

def test_no_answer_is_not_training_label(client):
    target=client.get("/api/companies?status=NEW").json()[0]
    client.post(f"/api/companies/{target['id']}/calls",json={"reached":"NO_ANSWER","opportunity":"UNKNOWN"})
    assert client.get("/api/stats").json()["labels"]==0

def test_duplicate_domain_updates_existing_company(client):
    before=client.get("/api/stats").json()["companies"]
    payload={"legal_name":"Northstar Components Incorporated","country":"CA","website":"https://example.com/northstar","phone":"+1 416 555 9999"}
    result=client.post("/api/companies",json=payload).json()
    assert result["created"] is False
    assert client.get("/api/stats").json()["companies"]==before

def test_wrong_number_is_flagged(client):
    target=client.get("/api/companies?status=NEW").json()[0]
    client.post(f"/api/companies/{target['id']}/calls",json={"reached":"WRONG_NUMBER","opportunity":"UNKNOWN"})
    assert "Invalid" in client.get(f"/api/companies/{target['id']}").json()["phone_type"]

def test_csv_import(client):
    content=b"legal_name,country,industry,website,revenue_growth,margin_change\nTest Factory,US,Manufacturing,https://factory.test,4,-3\n"
    result=client.post("/api/import/csv",files={"file":("companies.csv",content,"text/csv")}).json()
    assert result=={"created":1,"updated":0,"failed":0,"errors":[]}
