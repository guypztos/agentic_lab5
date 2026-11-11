import json
from copy import deepcopy

import pytest

from game import new_position
from session import Session

OPENING = [("e2", "e4"), ("d7", "d5"), ("e4", "d5"), ("d8", "d5")]


def play(session, *moves):
    for source, target in moves:
        session.dispatch({"action": "move", "source": source, "target": target})


def undo(session):
    return session.dispatch({"action": "undo"})


def redo(session):
    return session.dispatch({"action": "redo"})


def test_redo_with_nothing_undone_does_nothing():
    session = Session()
    assert session.view()["can_redo"] is False
    view = redo(session)
    assert session.position == new_position()
    assert view["moves"] == [] and view["can_redo"] is False
    play(session, ("e2", "e4"))
    before = session.view()
    assert redo(session) == before


def test_redo_restores_the_undone_move():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"))
    undone = undo(session)
    assert undone["moves"] == ["e2-e4"] and undone["can_redo"] is True
    view = redo(session)
    assert view["moves"] == ["e2-e4", "e7-e5"]
    assert view["turn"] == "w"
    assert view["board"]["e5"] == "bP" and "e7" not in view["board"]
    assert view["can_redo"] is False and view["can_undo"] is True


def test_redo_restores_a_capture_and_its_display():
    session = Session()
    play(session, *OPENING[:3])
    undo(session)
    assert session.view()["captured"] == []
    view = redo(session)
    assert view["moves"][-1] == "e4xd5"
    assert view["board"]["d5"] == "wP" and len(view["board"]) == 31
    assert view["captured"] == ["bP"]


def test_redo_restores_a_promotion():
    session = Session()
    session.dispatch({"action": "promotion-setup"})
    session.dispatch({"action": "move", "source": "b7", "target": "a8", "promotion": "N"})
    undo(session)
    assert session.position[0]["b7"] == "wP" and session.position[0]["a8"] == "bR"
    view = redo(session)
    assert view["board"]["a8"] == "wN"
    assert view["moves"][-1] == "b7xa8=N"
    assert view["captured"] == ["bP", "bR", "wP"]


def test_several_undos_redo_in_order():
    session = Session()
    play(session, *OPENING)
    full = deepcopy(session.view())  # view() shares the live lists
    for _ in range(3):
        undo(session)
    assert session.view()["moves"] == ["e2-e4"]
    assert redo(session)["moves"] == ["e2-e4", "d7-d5"]
    assert redo(session)["moves"] == ["e2-e4", "d7-d5", "e4xd5"]
    assert redo(session) == full
    assert redo(session) == full


def test_undo_and_redo_can_alternate():
    session = Session()
    play(session, *OPENING)
    undo(session)
    undo(session)
    redo(session)
    assert session.view()["moves"] == ["e2-e4", "d7-d5", "e4xd5"]
    undo(session)
    assert session.view()["moves"] == ["e2-e4", "d7-d5"]
    redo(session)
    redo(session)
    assert session.view()["moves"] == ["e2-e4", "d7-d5", "e4xd5", "d8xd5"]


def test_a_different_move_after_undo_discards_redo():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"))
    undo(session)
    view = session.dispatch({"action": "move", "source": "c7", "target": "c5"})
    assert view["can_redo"] is False
    assert redo(session)["moves"] == ["e2-e4", "c7-c5"]


def test_a_rejected_move_after_undo_keeps_redo():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"))
    undo(session)
    with pytest.raises(ValueError):
        session.dispatch({"action": "move", "source": "e7", "target": "e4"})
    assert session.view()["can_redo"] is True
    assert redo(session)["moves"] == ["e2-e4", "e7-e5"]


def test_new_game_clears_redo():
    session = Session()
    play(session, ("e2", "e4"))
    undo(session)
    view = session.dispatch({"action": "new"})
    assert view["can_redo"] is False
    assert redo(session)["moves"] == []


def test_redo_against_the_computer_restores_both_moves_as_played():
    session = Session("computer")
    play(session, ("e2", "e4"))
    session.dispatch({"action": "computer-move"})
    played = deepcopy(session.view())  # view() shares the live lists
    view = undo(session)
    assert view["moves"] == [] and view["can_redo"] is True
    view = redo(session)
    assert view["moves"] == played["moves"]
    assert view["board"] == played["board"]
    assert view["turn"] == "w" and view["can_redo"] is False


def test_redo_against_the_computer_before_its_reply():
    session = Session("computer")
    play(session, ("e2", "e4"))
    undo(session)
    view = redo(session)
    assert view["moves"] == ["e2-e4"] and view["turn"] == "b"
    assert session.computer_to_move()


def test_computer_reply_after_a_different_move_discards_redo():
    session = Session("computer")
    play(session, ("e2", "e4"))
    session.dispatch({"action": "computer-move"})
    undo(session)
    play(session, ("d2", "d4"))
    assert session.view()["can_redo"] is False
    session.dispatch({"action": "computer-move"})
    assert len(session.view()["moves"]) == 2
    assert session.view()["can_redo"] is False


def test_save_keeps_the_undone_moves_in_redo_order(tmp_path):
    path = tmp_path / "game.save.json"
    session = Session(save_path=path)
    play(session, *OPENING)
    undo(session)
    undo(session)
    session.dispatch({"action": "save"})
    data = json.loads(path.read_text())
    assert data["moves"] == [{"source": "e2", "target": "e4"}, {"source": "d7", "target": "d5"}]
    assert data["undone"] == [{"source": "e4", "target": "d5"}, {"source": "d8", "target": "d5"}]


def test_loaded_game_can_be_redone(tmp_path):
    path = tmp_path / "game.save.json"
    first = Session(save_path=path)
    first.dispatch({"action": "promotion-setup"})
    first.dispatch({"action": "move", "source": "b7", "target": "a8", "promotion": "Q"})
    undo(first)
    undo(first)
    first.dispatch({"action": "save"})

    second = Session(save_path=path)
    view = second.dispatch({"action": "load"})
    assert view["moves"] == first.notation and view["can_redo"] is True
    assert redo(second)["moves"][-1] == "h3xg2"
    view = redo(second)
    assert view["moves"][-1] == "b7xa8=Q" and view["board"]["a8"] == "wQ"
    assert view["can_redo"] is False
    assert len(view["captured"]) == 3


def test_loaded_game_against_the_computer_redoes_both_moves(tmp_path):
    path = tmp_path / "game.save.json"
    first = Session("computer", save_path=path)
    play(first, ("e2", "e4"))
    first.dispatch({"action": "computer-move"})
    played = deepcopy(first.view())  # view() shares the live lists
    undo(first)
    first.dispatch({"action": "save"})

    second = Session(save_path=path)
    second.dispatch({"action": "load"})
    view = redo(second)
    assert view["moves"] == played["moves"] and view["board"] == played["board"]


def test_old_save_without_undone_still_loads(tmp_path):
    path = tmp_path / "game.save.json"
    path.write_text(json.dumps({"format": 1, "opponent": "human",
                                "moves": [{"source": "e2", "target": "e4"}]}))
    session = Session(save_path=path)
    view = session.dispatch({"action": "load"})
    assert view["moves"] == ["e2-e4"] and view["can_redo"] is False


@pytest.mark.parametrize("undone", [
    "not a list",
    [["e4", "d5"]],
    [{"source": "e4", "target": "e6"}],
    [{"source": "e4", "target": "d5"}, {"source": "e1", "target": "e5"}],
])
def test_bad_undone_moves_fail_and_change_nothing(tmp_path, undone):
    path = tmp_path / "game.save.json"
    path.write_text(json.dumps({"format": 1, "opponent": "human",
                                "moves": [{"source": "e2", "target": "e4"},
                                          {"source": "d7", "target": "d5"}],
                                "undone": undone}))
    session = Session(save_path=path)
    play(session, ("a2", "a3"))
    with pytest.raises(ValueError):
        session.dispatch({"action": "load"})
    assert session.view()["moves"] == ["a2-a3"]
