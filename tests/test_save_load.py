import json
import threading
import urllib.request

import pytest

from game import new_position
from server import make_server
from session import Session

OPENING = [("e2", "e4"), ("d7", "d5"), ("e4", "d5"), ("d8", "d5")]


def play(session, moves):
    for source, target in moves:
        session.dispatch({"action": "move", "source": source, "target": target})


def test_saved_game_lists_the_moves(tmp_path):
    session = Session(save_path=tmp_path / "game.save.json")
    play(session, OPENING)
    session.dispatch({"action": "save"})
    data = json.loads((tmp_path / "game.save.json").read_text())
    assert data["opponent"] == "human"
    assert data["moves"] == [{"source": s, "target": t} for s, t in OPENING]


def test_load_restores_a_fresh_instance(tmp_path):
    path = tmp_path / "game.save.json"
    first = Session(save_path=path)
    play(first, OPENING)
    first.dispatch({"action": "save"})

    second = Session(save_path=path)
    view = second.dispatch({"action": "load"})
    assert second.position == first.position
    assert view["moves"] == ["e2-e4", "d7-d5", "e4xd5", "d8xd5"]
    assert view["turn"] == "w"
    assert view["status"] is None
    # The replayed moves are recorded again, so a later undo has them.
    assert second.history == first.history


def test_load_restores_the_computer_opponent(tmp_path):
    path = tmp_path / "game.save.json"
    first = Session("computer", save_path=path)
    first.dispatch({"action": "move", "source": "e2", "target": "e4"})
    first.dispatch({"action": "computer-move"})
    first.dispatch({"action": "save"})

    second = Session(save_path=path)
    view = second.dispatch({"action": "load"})
    assert view["opponent"] == "computer"
    assert second.position == first.position
    assert len(view["moves"]) == 2
    with pytest.raises(ValueError):
        second.dispatch({"action": "move", "source": "e7", "target": "e5"})


def test_load_replaces_the_game_in_progress(tmp_path):
    path = tmp_path / "game.save.json"
    session = Session(save_path=path)
    play(session, OPENING[:2])
    session.dispatch({"action": "save"})
    session.dispatch({"action": "new", "opponent": "computer"})
    session.dispatch({"action": "move", "source": "a2", "target": "a3"})

    view = session.dispatch({"action": "load"})
    assert view["opponent"] == "human"
    assert view["moves"] == ["e2-e4", "d7-d5"]
    assert session.save_path == path


def test_save_overwrites_the_previous_save(tmp_path):
    path = tmp_path / "game.save.json"
    session = Session(save_path=path)
    play(session, OPENING[:1])
    session.dispatch({"action": "save"})
    play(session, OPENING[1:])
    session.dispatch({"action": "save"})
    assert len(json.loads(path.read_text())["moves"]) == 4


def test_new_game_keeps_the_save_file(tmp_path):
    path = tmp_path / "game.save.json"
    session = Session(save_path=path)
    play(session, OPENING)
    session.dispatch({"action": "save"})
    session.dispatch({"action": "new"})
    assert session.position == new_position()
    session.dispatch({"action": "load"})
    assert len(session.notation) == 4


def test_load_without_a_save_fails_and_changes_nothing(tmp_path):
    session = Session(save_path=tmp_path / "missing.json")
    play(session, OPENING[:1])
    with pytest.raises(ValueError, match="no saved game"):
        session.dispatch({"action": "load"})
    assert session.notation == ["e2-e4"]


@pytest.mark.parametrize("content", [
    "not json",
    json.dumps([]),
    json.dumps({"format": 99, "opponent": "human", "moves": []}),
    json.dumps({"format": 1, "opponent": "robot", "moves": []}),
    json.dumps({"format": 1, "opponent": "human"}),
    json.dumps({"format": 1, "opponent": "human", "moves": [["e2", "e4"]]}),
    json.dumps({"format": 1, "opponent": "human",
                "moves": [{"source": "e2", "target": "e5"}]}),
    json.dumps({"format": 1, "opponent": "human",
                "moves": [{"source": "e2", "target": "e4", "extra": 1}]}),
])
def test_bad_save_file_fails_and_changes_nothing(tmp_path, content):
    path = tmp_path / "game.save.json"
    path.write_text(content)
    session = Session(save_path=path)
    play(session, OPENING[:2])
    with pytest.raises(ValueError):
        session.dispatch({"action": "load"})
    assert session.notation == ["e2-e4", "d7-d5"]
    assert session.opponent == "human"


def test_sessions_default_to_one_shared_file(tmp_path):
    assert Session().save_path == Session.save_path
    assert Session.save_path.name == "game.save.json"


def serve(tmp_path):
    server = make_server(0, save_path=tmp_path / "game.save.json")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}"


def post(url, action):
    request = urllib.request.Request(
        url + "/api/action", json.dumps(action).encode(),
        {"Content-Type": "application/json"})
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())


def test_server_restart_loads_the_saved_game(tmp_path):
    server, url = serve(tmp_path)
    try:
        post(url, {"action": "new", "opponent": "computer"})
        post(url, {"action": "move", "source": "e2", "target": "e4"})
        saved = post(url, {"action": "save"})
    finally:
        server.shutdown()
        server.server_close()

    server, url = serve(tmp_path)
    try:
        with urllib.request.urlopen(url + "/api/state") as response:
            assert json.loads(response.read())["moves"] == []
        loaded = post(url, {"action": "load"})
        assert loaded == saved
        assert loaded["opponent"] == "computer"
        assert loaded["board"]["e4"] == "wP"
    finally:
        server.shutdown()
        server.server_close()


def test_save_after_undo_leaves_out_the_undone_move(tmp_path):
    path = tmp_path / "game.save.json"
    session = Session(save_path=path)
    play(session, OPENING)
    session.dispatch({"action": "undo"})
    session.dispatch({"action": "save"})
    assert json.loads(path.read_text())["moves"] == [
        {"source": s, "target": t} for s, t in OPENING[:3]]


def test_loaded_game_can_be_undone(tmp_path):
    path = tmp_path / "game.save.json"
    first = Session(save_path=path)
    play(first, OPENING)
    first.dispatch({"action": "save"})

    second = Session(save_path=path)
    view = second.dispatch({"action": "load"})
    assert view["can_undo"] is True
    view = second.dispatch({"action": "undo"})
    assert view["moves"] == ["e2-e4", "d7-d5", "e4xd5"]
    assert view["board"]["d8"] == "bQ"
    assert view["turn"] == "b"
    for _ in range(3):
        second.dispatch({"action": "undo"})
    assert second.position == new_position()
    assert second.dispatch({"action": "undo"})["can_undo"] is False


def test_undo_against_the_computer_after_load(tmp_path):
    path = tmp_path / "game.save.json"
    first = Session("computer", save_path=path)
    first.dispatch({"action": "move", "source": "e2", "target": "e4"})
    first.dispatch({"action": "computer-move"})
    first.dispatch({"action": "save"})

    second = Session(save_path=path)
    second.dispatch({"action": "load"})
    view = second.dispatch({"action": "undo"})
    assert view["moves"] == []
    assert view["turn"] == "w"
    assert second.position == new_position()
