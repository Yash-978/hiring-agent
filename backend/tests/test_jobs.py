import logging
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.models import Application, ApplicationStatus, AuditLog, Job
from app.services import job_service


def test_create_job_happy_path(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
    session: Session,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    payload = {
        "title": "Senior Backend Engineer",
        "description": "Python, FastAPI, SQLModel expert needed",
        "status": "open",
    }
    response = client.post("/jobs", headers=tenant_a["headers"], json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == payload["title"]
    assert data["description"] == payload["description"]
    assert data["status"] == "open"
    assert "id" in data
    assert "created_at" in data

    # Verify audit log was recorded
    audit = session.exec(
        select(AuditLog).where(
            AuditLog.tenant_id == tenant_a["tenant"].id,
            AuditLog.action == "create_job",
            AuditLog.entity_id == data["id"],
        )
    ).first()
    assert audit is not None
    assert audit.actor_name == tenant_a["user"].email
    assert audit.details["title"] == payload["title"]


def test_list_and_get_jobs(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    # Create two jobs
    r1 = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "DevOps Engineer", "description": "K8s, AWS"},
    )
    r2 = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Product Designer", "description": "Figma, UI/UX"},
    )
    j1_id = r1.json()["id"]
    j2_id = r2.json()["id"]

    # List jobs
    list_res = client.get("/jobs", headers=tenant_a["headers"])
    assert list_res.status_code == 200
    job_ids = [j["id"] for j in list_res.json()]
    assert j1_id in job_ids
    assert j2_id in job_ids

    # Get one job
    get_res = client.get(f"/jobs/{j1_id}", headers=tenant_a["headers"])
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "DevOps Engineer"


def test_cross_tenant_job_isolation(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]
    tenant_b = two_tenants["tenant_b"]

    # Tenant A creates a job
    res = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Secret Project Lead", "description": "Top secret"},
    )
    job_a_id = res.json()["id"]

    # Tenant B tries to GET Tenant A's job -> 404
    cross_res = client.get(f"/jobs/{job_a_id}", headers=tenant_b["headers"])
    assert cross_res.status_code == 404
    assert "not found" in cross_res.json()["detail"].lower()

    # Tenant B lists jobs -> should not contain Tenant A's job
    list_b = client.get("/jobs", headers=tenant_b["headers"])
    assert list_b.status_code == 200
    assert job_a_id not in [j["id"] for j in list_b.json()]


LONG_RESUME = (
    "Senior backend engineer with five years of hands-on experience building "
    "production services in Python and FastAPI. Comfortable with PostgreSQL "
    "and Docker, and used to owning services end to end including tests, "
    "deployment and on-call. Led a small team and mentored two junior "
    "engineers. Strong background in API design, data modelling and "
    "performance tuning. Available to start within four weeks."
)


def test_create_job_with_requirements_fields(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    payload = {
        "title": "Platform Engineer",
        "description": "Build and run the platform",
        "must_have_skills": ["Go", "Kubernetes"],
        "nice_to_have_skills": ["Terraform"],
        "min_years_experience": 4.0,
    }
    resp = client.post("/jobs", headers=tenant_a["headers"], json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["must_have_skills"] == ["Go", "Kubernetes"]
    assert data["nice_to_have_skills"] == ["Terraform"]
    assert data["min_years_experience"] == 4.0

    get_res = client.get(f"/jobs/{data['id']}", headers=tenant_a["headers"])
    assert get_res.status_code == 200
    got = get_res.json()
    assert got["must_have_skills"] == ["Go", "Kubernetes"]
    assert got["nice_to_have_skills"] == ["Terraform"]
    assert got["min_years_experience"] == 4.0


def test_create_job_requirements_default_to_empty(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    resp = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Product Designer", "description": "Figma work"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["must_have_skills"] == []
    assert data["nice_to_have_skills"] == []
    assert data["min_years_experience"] is None


def test_analyze_application_extracts_job_requirements_when_empty(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    cand = client.post(
        "/candidates",
        headers=tenant_a["headers"],
        json={"full_name": "Alice Smith", "email": "alice.extract@example.com"},
    ).json()
    job = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={
            "title": "Backend Engineer",
            "description": "Python, FastAPI, PostgreSQL experience required",
        },
    ).json()
    assert job["must_have_skills"] == []

    app = client.post(
        "/applications",
        headers=tenant_a["headers"],
        json={"candidate_id": cand["id"], "job_id": job["id"]},
    ).json()

    files = {"file": ("resume.txt", LONG_RESUME, "text/plain")}
    resp = client.post(
        f"/applications/{app['id']}/analyze",
        headers=tenant_a["headers"],
        files=files,
    )
    assert resp.status_code == 200

    filled = client.get(
        f"/jobs/{job['id']}", headers=tenant_a["headers"]
    ).json()
    assert filled["must_have_skills"] == ["Python", "FastAPI", "PostgreSQL"]
    assert filled["nice_to_have_skills"] == ["Docker"]
    assert filled["min_years_experience"] == 3.0


def test_analyze_application_keeps_existing_job_requirements(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    cand = client.post(
        "/candidates",
        headers=tenant_a["headers"],
        json={"full_name": "Bob Jones", "email": "bob.extract@example.com"},
    ).json()
    job = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={
            "title": "Backend Engineer",
            "description": "Python, FastAPI, PostgreSQL experience required",
            "must_have_skills": ["Rust"],
            "nice_to_have_skills": ["Elixir"],
            "min_years_experience": 8.0,
        },
    ).json()

    app = client.post(
        "/applications",
        headers=tenant_a["headers"],
        json={"candidate_id": cand["id"], "job_id": job["id"]},
    ).json()

    files = {"file": ("resume.txt", LONG_RESUME, "text/plain")}
    resp = client.post(
        f"/applications/{app['id']}/analyze",
        headers=tenant_a["headers"],
        files=files,
    )
    assert resp.status_code == 200

    unchanged = client.get(
        f"/jobs/{job['id']}", headers=tenant_a["headers"]
    ).json()
    assert unchanged["must_have_skills"] == ["Rust"]
    assert unchanged["nice_to_have_skills"] == ["Elixir"]
    assert unchanged["min_years_experience"] == 8.0


def _analyze_for_job(
    client: TestClient,
    headers: dict[str, str],
    job_id: int,
    name: str,
    email: str,
) -> dict[str, Any]:
    """Create a candidate and application for the job, analyze it, return the app."""
    cand = client.post(
        "/candidates",
        headers=headers,
        json={"full_name": name, "email": email},
    ).json()
    app = client.post(
        "/applications",
        headers=headers,
        json={"candidate_id": cand["id"], "job_id": job_id},
    ).json()
    files = {"file": ("resume.txt", LONG_RESUME, "text/plain")}
    resp = client.post(
        f"/applications/{app['id']}/analyze",
        headers=headers,
        files=files,
    )
    assert resp.status_code == 200
    return app


def test_compare_job_candidates_includes_unanalyzed_last(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    job = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Backend Engineer", "description": "Python, FastAPI, Docker"},
    ).json()

    analyzed = _analyze_for_job(
        client, tenant_a["headers"], job["id"], "Alice Smith", "alice.compare@example.com"
    )

    # A second application for the same job that was never analyzed.
    cand_b = client.post(
        "/candidates",
        headers=tenant_a["headers"],
        json={"full_name": "Unanalyzed Ursula", "email": "ursula.compare@example.com"},
    ).json()
    unanalyzed = client.post(
        "/applications",
        headers=tenant_a["headers"],
        json={"candidate_id": cand_b["id"], "job_id": job["id"]},
    ).json()

    resp = client.get(f"/jobs/{job['id']}/compare", headers=tenant_a["headers"])
    assert resp.status_code == 200
    data = resp.json()

    assert data["job"]["id"] == job["id"]
    assert data["job"]["title"] == "Backend Engineer"
    assert data["job"]["must_have_skills"] == ["Python", "FastAPI", "PostgreSQL"]
    assert data["job"]["nice_to_have_skills"] == ["Docker"]
    assert data["counts"] == {"total": 2, "scored": 1}

    # The analyzed candidate ranks first; the unscored one is always last.
    assert [c["name"] for c in data["candidates"]] == [
        "Alice Smith",
        "Unanalyzed Ursula",
    ]

    candidate = data["candidates"][0]
    assert candidate["application_id"] == analyzed["id"]
    assert candidate["recommendation"] == "shortlist"
    assert candidate["confidence"] == "high"
    assert isinstance(candidate["score"], float)
    assert isinstance(candidate["flags"], list)
    assert set(candidate["breakdown"].keys()) == {
        "must_have",
        "nice_to_have",
        "experience",
    }
    assert all(isinstance(v, float) for v in candidate["breakdown"].values())
    assert len(candidate["criteria"]) == 4
    assert set(candidate["criteria"][0].keys()) == {"criterion", "kind", "verdict"}

    # The unscored application is still listed, with no score or detail.
    unscored = data["candidates"][1]
    assert unscored["application_id"] == unanalyzed["id"]
    assert unscored["score"] is None
    assert unscored["criteria"] == []
    assert unscored["flags"] == []


def test_compare_job_candidates_with_no_applications_is_empty(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    job = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Backend Engineer", "description": "Python, FastAPI"},
    ).json()

    resp = client.get(f"/jobs/{job['id']}/compare", headers=tenant_a["headers"])
    assert resp.status_code == 200
    assert resp.json()["candidates"] == []
    assert resp.json()["counts"] == {"total": 0, "scored": 0}


def test_compare_job_candidates_sorted_by_score_descending(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
    session: Session,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    job = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Backend Engineer", "description": "Python, FastAPI, Docker"},
    ).json()

    low = _analyze_for_job(
        client, tenant_a["headers"], job["id"], "Low Score", "low.compare@example.com"
    )
    high = _analyze_for_job(
        client, tenant_a["headers"], job["id"], "High Score", "high.compare@example.com"
    )

    # A third application with no score must always land last.
    cand = client.post(
        "/candidates",
        headers=tenant_a["headers"],
        json={"full_name": "Unscored", "email": "unscored.compare@example.com"},
    ).json()
    client.post(
        "/applications",
        headers=tenant_a["headers"],
        json={"candidate_id": cand["id"], "job_id": job["id"]},
    )

    # Force distinct scores so the ordering is unambiguous.
    for app_id, forced in ((low["id"], 40.0), (high["id"], 95.0)):
        row = session.get(Application, app_id)
        assert row is not None
        row.score = forced
        session.add(row)
    session.commit()

    resp = client.get(f"/jobs/{job['id']}/compare", headers=tenant_a["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert [c["score"] for c in data["candidates"]] == [95.0, 40.0, None]
    assert [c["name"] for c in data["candidates"]] == [
        "High Score",
        "Low Score",
        "Unscored",
    ]
    assert data["counts"] == {"total": 3, "scored": 2}


def test_compare_job_candidates_includes_rejected_but_not_withdrawn(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
    session: Session,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    job = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Backend Engineer", "description": "Python, FastAPI"},
    ).json()

    rejected = _analyze_for_job(
        client, tenant_a["headers"], job["id"], "Rejected Rita", "rita@example.com"
    )
    withdrawn = _analyze_for_job(
        client, tenant_a["headers"], job["id"], "Withdrawn Wanda", "wanda@example.com"
    )

    rejected_row = session.get(Application, rejected["id"])
    assert rejected_row is not None
    rejected_row.status = ApplicationStatus.SHORTLIST_REJECTED
    session.add(rejected_row)

    withdrawn_row = session.get(Application, withdrawn["id"])
    assert withdrawn_row is not None
    withdrawn_row.status = "withdrawn"
    session.add(withdrawn_row)
    session.commit()

    resp = client.get(f"/jobs/{job['id']}/compare", headers=tenant_a["headers"])
    assert resp.status_code == 200
    data = resp.json()
    names = [c["name"] for c in data["candidates"]]
    assert names == ["Rejected Rita"]
    assert data["counts"] == {"total": 1, "scored": 1}


def test_compare_job_candidates_isolated_per_job_and_tenant(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]
    tenant_b = two_tenants["tenant_b"]

    job_a = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Backend Engineer", "description": "Python, FastAPI"},
    ).json()
    other_job = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Data Engineer", "description": "SQL, pipelines"},
    ).json()
    job_b = client.post(
        "/jobs",
        headers=tenant_b["headers"],
        json={"title": "Backend Engineer", "description": "Python, FastAPI"},
    ).json()

    _analyze_for_job(client, tenant_a["headers"], job_a["id"], "Alice A", "alice.a@example.com")
    _analyze_for_job(client, tenant_a["headers"], other_job["id"], "Bob B", "bob.b@example.com")
    _analyze_for_job(client, tenant_b["headers"], job_b["id"], "Carol C", "carol.c@example.com")

    resp = client.get(f"/jobs/{job_a['id']}/compare", headers=tenant_a["headers"])
    assert resp.status_code == 200
    data = resp.json()
    # Only this job's applications, and only this tenant's.
    assert [c["name"] for c in data["candidates"]] == ["Alice A"]
    assert data["counts"] == {"total": 1, "scored": 1}


def test_compare_job_candidates_cross_tenant_is_404(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]
    tenant_b = two_tenants["tenant_b"]

    job = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Backend Engineer", "description": "Python, FastAPI"},
    ).json()

    resp = client.get(f"/jobs/{job['id']}/compare", headers=tenant_b["headers"])
    assert resp.status_code == 404


def test_list_and_get_jobs_include_candidate_count(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    busy = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Backend Engineer", "description": "Python, FastAPI"},
    ).json()
    empty = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Designer", "description": "Figma"},
    ).json()

    _analyze_for_job(client, tenant_a["headers"], busy["id"], "Alice", "alice.count@example.com")
    cand = client.post(
        "/candidates",
        headers=tenant_a["headers"],
        json={"full_name": "Bob", "email": "bob.count@example.com"},
    ).json()
    client.post(
        "/applications",
        headers=tenant_a["headers"],
        json={"candidate_id": cand["id"], "job_id": busy["id"]},
    )

    jobs = client.get("/jobs", headers=tenant_a["headers"]).json()
    by_id = {job["id"]: job for job in jobs}
    assert by_id[busy["id"]]["candidate_count"] == 2
    assert by_id[empty["id"]]["candidate_count"] == 0

    single = client.get(f"/jobs/{busy['id']}", headers=tenant_a["headers"]).json()
    assert single["candidate_count"] == 2


# --- Unique job titles (TASK 4) -------------------------------------------


def test_create_job_duplicate_title_returns_409(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    first = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Mobile App Developer", "description": "iOS and Android"},
    )
    assert first.status_code == 201
    first_id = first.json()["id"]

    # Same title, different case and extra whitespace.
    dup = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "  mobile   app developer ", "description": "Duplicate"},
    )
    assert dup.status_code == 409
    assert dup.json()["detail"] == "A job with this title already exists"
    assert dup.json()["existing_job_id"] == first_id

    jobs = client.get("/jobs", headers=tenant_a["headers"]).json()
    assert len(jobs) == 1


def test_same_job_title_allowed_across_tenants(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]
    tenant_b = two_tenants["tenant_b"]

    a = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Data Analyst", "description": "SQL and dashboards"},
    )
    b = client.post(
        "/jobs",
        headers=tenant_b["headers"],
        json={"title": "data   analyst", "description": "SQL and dashboards"},
    )
    assert a.status_code == 201
    assert b.status_code == 201
    assert a.json()["id"] != b.json()["id"]


def test_patch_job_updates_fields_and_logs_audit(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
    session: Session,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    job = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Support Engineer", "description": "Helpdesk"},
    ).json()

    resp = client.patch(
        f"/jobs/{job['id']}",
        headers=tenant_a["headers"],
        json={
            "title": "Senior Support Engineer",
            "must_have_skills": ["Zendesk"],
            "min_years_experience": 2.0,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Senior Support Engineer"
    assert data["description"] == "Helpdesk"  # untouched by a partial update
    assert data["must_have_skills"] == ["Zendesk"]
    assert data["min_years_experience"] == 2.0

    audit = session.exec(
        select(AuditLog).where(
            AuditLog.action == "update_job",
            AuditLog.entity_id == job["id"],
        )
    ).first()
    assert audit is not None
    assert audit.actor_name == tenant_a["user"].email


def test_patch_job_to_duplicate_title_returns_409(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    first = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "QA Engineer", "description": "Testing"},
    ).json()
    second = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Site Reliability Engineer", "description": "On-call"},
    ).json()

    resp = client.patch(
        f"/jobs/{second['id']}",
        headers=tenant_a["headers"],
        json={"title": " qa   engineer "},
    )
    assert resp.status_code == 409
    assert resp.json()["existing_job_id"] == first["id"]

    # The rename was rejected, so the job keeps its original title.
    still = client.get(f"/jobs/{second['id']}", headers=tenant_a["headers"]).json()
    assert still["title"] == "Site Reliability Engineer"


def test_patch_job_cross_tenant_is_404(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]
    tenant_b = two_tenants["tenant_b"]

    job = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Growth Marketer", "description": "Campaigns"},
    ).json()

    resp = client.patch(
        f"/jobs/{job['id']}",
        headers=tenant_b["headers"],
        json={"title": "Hijacked"},
    )
    assert resp.status_code == 404


def _fresh_engine() -> Any:
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_ensure_job_unique_index_backfills_and_creates_index() -> None:
    engine = _fresh_engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Job(tenant_id=1, title="  Mobile  App Developer ", description="x")
        )
        session.commit()

    job_service.ensure_job_unique_index(engine)

    with Session(engine) as session:
        job = session.exec(select(Job)).one()
        assert job.title_key == "mobile app developer"

    index_names = {i["name"] for i in sa_inspect(engine).get_indexes("job")}
    assert job_service.JOB_TITLE_INDEX_NAME in index_names


def test_ensure_job_unique_index_skips_index_when_duplicates_exist(
    caplog: Any,
) -> None:
    engine = _fresh_engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Job(tenant_id=1, title="Mobile App Developer", description="a"))
        session.add(Job(tenant_id=1, title="mobile   app developer", description="b"))
        session.commit()

    with caplog.at_level(logging.WARNING, logger="app.services.job_service"):
        job_service.ensure_job_unique_index(engine)

    index_names = {i["name"] for i in sa_inspect(engine).get_indexes("job")}
    assert job_service.JOB_TITLE_INDEX_NAME not in index_names
    assert "duplicate job title" in caplog.text
    assert "dedupe_jobs" in caplog.text


def test_ensure_job_unique_index_adds_missing_column() -> None:
    """Existing databases predate title_key, so it must be added in place."""
    engine = _fresh_engine()
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE job ("
                "id INTEGER PRIMARY KEY, tenant_id INTEGER, "
                "title VARCHAR NOT NULL, description VARCHAR NOT NULL)"
            )
        )
        connection.execute(
            text("INSERT INTO job (tenant_id, title, description) VALUES (1, 'Ops Lead', 'x')")
        )

    job_service.ensure_job_unique_index(engine)

    columns = {c["name"] for c in sa_inspect(engine).get_columns("job")}
    assert "title_key" in columns
    with engine.begin() as connection:
        row = connection.execute(text("SELECT title_key FROM job")).fetchone()
    assert row is not None and row[0] == "ops lead"

