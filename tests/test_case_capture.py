"""Tests for per-case RAG capture helpers."""

from __future__ import annotations

from app.services.case_capture import build_rag_preview, save_generation_case


def test_build_rag_preview_extracts_names() -> None:
    knowledge = {
        "duration_days": 2,
        "meta": {"rag_status": "ok", "source": "retriever"},
        "clusters": [
            {
                "cluster_id": 0,
                "theme": "Jerash · history",
                "pois": [
                    {
                        "poi": {"name": "Jerash Heritage Souk", "role": "anchor"},
                        "restaurants": [{"name": "Jerash Oasis Grill"}],
                    }
                ],
                "hotels": [{"name": "The Olive Branch Hotel"}],
                "events": [{"name": "Jordan Summer Festival - Jerash"}],
            }
        ],
    }
    preview = build_rag_preview(knowledge)
    assert preview["status"] == "ok"
    assert preview["cluster_count"] == 1
    assert preview["clusters"][0]["poi_names"] == ["Jerash Heritage Souk"]
    assert preview["clusters"][0]["hotel_names"] == ["The Olive Branch Hotel"]
    assert preview["clusters"][0]["sample_restaurants"] == ["Jerash Oasis Grill"]


def test_save_generation_case_writes_folder(tmp_path, monkeypatch) -> None:
    import app.services.case_capture as cc

    monkeypatch.setattr(cc, "_CASES_ROOT", tmp_path / "cases")
    monkeypatch.setattr(cc, "_INDEX_PATH", tmp_path / "cases" / "index.jsonl")
    monkeypatch.setattr(cc, "_LAST_RAG", tmp_path / "last_retriever_response.json")

    knowledge = {
        "duration_days": 2,
        "meta": {"rag_status": "ok", "source": "retriever"},
        "clusters": [{"cluster_id": 0, "theme": "Ajloun", "pois": [], "hotels": [], "events": []}],
    }
    case_id = save_generation_case(
        request_payload={"trip": {"duration": "2"}},
        knowledge=knowledge,
        package={"trip_title": "Ajloun Test"},
        metadata={"model": "test"},
        case_id="20260101-test-ajloun",
    )
    assert case_id == "20260101-test-ajloun"
    case_dir = tmp_path / "cases" / case_id
    assert (case_dir / "02_retriever.json").exists()
    assert (case_dir / "02_retriever_preview.json").exists()
    assert (case_dir / "manifest.json").exists()
