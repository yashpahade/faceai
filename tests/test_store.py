import numpy as np

from faceai.store.db import Database
from faceai.store.index import VectorIndex
from tests.fakes import DIM, identity_vector


def test_db_person_lifecycle_and_cascade(tmp_path):
    db = Database(tmp_path / "t.db")
    p = db.create_person("Asha")
    e1 = db.add_embedding(p.id, "m1", identity_vector(1), 0.9, 100.0)
    e2 = db.add_embedding(p.id, "m1", identity_vector(2), 0.9, 100.0)
    assert db.get_person(p.id).num_faces == 2

    removed = db.delete_person(p.id)
    assert sorted(removed) == [e1, e2]
    assert db.get_person(p.id) is None
    ids, _, _ = db.load_embeddings("m1")
    assert len(ids) == 0  # ON DELETE CASCADE ne embeddings bhi hata di


def test_db_embeddings_filtered_by_model(tmp_path):
    db = Database(tmp_path / "t.db")
    p = db.create_person("Ravi")
    db.add_embedding(p.id, "old-model", identity_vector(1), 0.9, 100.0)
    db.add_embedding(p.id, "new-model", identity_vector(2), 0.9, 100.0)
    ids, pids, vecs = db.load_embeddings("new-model")
    assert len(ids) == 1 and pids[0] == p.id
    np.testing.assert_allclose(vecs[0], identity_vector(2))
    assert db.count_other_models("new-model") == 1


def test_db_persists_across_reopen(tmp_path):
    Database(tmp_path / "t.db").create_person("Zoya")
    assert [p.name for p in Database(tmp_path / "t.db").list_persons()] == ["Zoya"]


def test_index_aggregates_by_person_and_removes():
    idx = VectorIndex(DIM)
    a, b = identity_vector(1), identity_vector(2)
    noisy_a = a + 0.05 * identity_vector(3)
    idx.add(
        np.array([1, 2, 3]),
        np.array(["A", "A", "B"], dtype=object),
        np.stack([a, noisy_a / np.linalg.norm(noisy_a), b]),
    )

    res = idx.search_persons(a)
    assert res[0][0] == "A" and res[0][1] > 0.99
    assert [pid for pid, _ in res] == ["A", "B"]  # A ek hi baar (best score)

    idx.remove([1, 2])
    assert [pid for pid, _ in idx.search_persons(a)] == ["B"]


def test_index_empty_search():
    assert VectorIndex(DIM).search_persons(identity_vector(1)) == []
