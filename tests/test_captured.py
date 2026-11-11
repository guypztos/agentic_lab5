from captured import captured_pieces
from game import new_position
from session import Session


def play(session, *moves):
    for source, target in moves:
        session.dispatch({"action": "move", "source": source, "target": target})


def captured(session):
    return session.view()["captured"]


def test_display_after_capture_and_new_game():
    session = Session()
    assert session.view()["captured"] == []
    session.play("e2", "e4")
    session.play("d7", "d5")
    session.play("e4", "d5")
    assert session.view()["captured"] == ["bP"]
    session.dispatch({"action": "new"})
    assert session.view()["captured"] == []


def test_captures_are_listed_in_order_with_their_type():
    session = Session()
    play(session, ("e2", "e4"), ("d7", "d5"), ("e4", "d5"), ("d8", "d5"),
         ("b1", "c3"), ("d5", "d2"), ("d1", "d2"))
    assert captured(session) == ["bP", "wP", "wP", "bQ"]


def test_promotion_setup_shows_both_captures():
    session = Session()
    session.dispatch({"action": "promotion-setup"})
    assert captured(session) == ["bP", "wP"]


def test_undo_removes_a_capture_from_the_display():
    session = Session()
    play(session, ("e2", "e4"), ("d7", "d5"), ("e4", "d5"))
    assert captured(session) == ["bP"]
    session.dispatch({"action": "undo"})
    assert captured(session) == []
    assert session.position[0]["d5"] == "bP"


def test_undo_of_a_quiet_move_keeps_earlier_captures():
    session = Session()
    play(session, ("e2", "e4"), ("d7", "d5"), ("e4", "d5"), ("g8", "f6"))
    session.dispatch({"action": "undo"})
    assert captured(session) == ["bP"]
    play(session, ("d8", "d5"))
    assert captured(session) == ["bP", "wP"]


def test_undo_to_the_start_clears_the_display():
    session = Session()
    play(session, ("e2", "e4"), ("d7", "d5"), ("e4", "d5"), ("d8", "d5"))
    for _ in range(4):
        session.dispatch({"action": "undo"})
    assert session.position == new_position()
    assert captured(session) == []


def test_undo_against_the_computer_removes_its_capture():
    session = Session("computer")
    # Give the computer a free pawn so its one-move lookahead must take it.
    session.position = [{"e1": "wK", "e8": "bK", "d4": "wP", "e5": "bP", "h2": "wP"}, "w"]
    play(session, ("h2", "h3"))
    session.dispatch({"action": "computer-move"})
    assert captured(session) == ["wP"]
    session.dispatch({"action": "undo"})
    assert captured(session) == []
    assert session.position[0]["d4"] == "wP"


def test_saved_game_restores_the_display_in_a_fresh_instance(tmp_path):
    path = tmp_path / "game.save.json"
    first = Session(save_path=path)
    play(first, ("e2", "e4"), ("d7", "d5"), ("e4", "d5"), ("d8", "d5"))
    first.dispatch({"action": "undo"})
    first.dispatch({"action": "save"})

    second = Session(save_path=path)
    assert second.dispatch({"action": "load"})["captured"] == ["bP"]
    second.dispatch({"action": "undo"})
    assert captured(second) == []


def test_only_what_was_taken_counts():
    # The function is driven by the recorded moves, so these cases can be checked
    # before the game itself promotes: a pawn reaching the last rank alone takes
    # nothing, and a promoted piece taken later shows as what it had become.
    promotion = [{"a7": "wP", "e1": "wK", "e8": "bK"}, "w"]
    capture_of_promoted = [{"a8": "wQ", "e1": "wK", "e8": "bK", "b8": "bR"}, "b"]
    moves = [{"source": "a7", "target": "a8"}, {"source": "b8", "target": "a8"}]
    assert captured_pieces([promotion], moves[:1]) == []
    assert captured_pieces([promotion, capture_of_promoted], moves) == ["wQ"]
    assert captured_pieces([], []) == []
