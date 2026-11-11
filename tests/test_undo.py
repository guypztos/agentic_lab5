from game import new_position
from session import Session


def play(session, *moves):
    for source, target in moves:
        session.dispatch({"action": "move", "source": source, "target": target})


def undo(session):
    return session.dispatch({"action": "undo"})


def test_undo_at_the_start_does_nothing():
    session = Session()
    view = undo(session)
    assert session.position == new_position()
    assert view["moves"] == []
    assert view["turn"] == "w"
    assert view["can_undo"] is False


def test_undo_reverses_the_last_move_turn_and_notation():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"))
    view = undo(session)
    assert view["moves"] == ["e2-e4"]
    assert view["turn"] == "b"
    assert view["board"]["e7"] == "bP"
    assert "e5" not in view["board"]
    assert view["can_undo"] is True


def test_undo_restores_a_captured_piece():
    session = Session()
    play(session, ("e2", "e4"), ("d7", "d5"), ("e4", "d5"))
    assert len(session.position[0]) == 31
    view = undo(session)
    assert view["board"]["d5"] == "bP"
    assert view["board"]["e4"] == "wP"
    assert len(view["board"]) == 32
    assert view["moves"] == ["e2-e4", "d7-d5"]
    assert view["turn"] == "w"


def test_repeated_undo_reaches_the_start_and_stops():
    session = Session()
    session.dispatch({"action": "promotion-setup"})
    for _ in range(8):
        undo(session)
    assert session.position == new_position()
    assert session.notation == []
    view = undo(session)
    assert session.position == new_position()
    assert view["can_undo"] is False


def test_undo_restores_check_status():
    session = Session()
    # Fool's mate, then take back the mating move.
    play(session, ("f2", "f3"), ("e7", "e5"), ("g2", "g4"), ("d8", "h4"))
    assert session.view()["status"] == "checkmate"
    view = undo(session)
    assert view["status"] is None
    assert view["winner"] is None
    assert view["turn"] == "b"


def test_play_continues_after_undo():
    session = Session()
    play(session, ("e2", "e4"))
    undo(session)
    play(session, ("d2", "d4"))
    assert session.notation == ["d2-d4"]
    assert session.position[0]["d4"] == "wP"
    assert "e4" not in session.position[0]


def test_undo_against_the_computer_reverts_both_moves():
    session = Session("computer")
    play(session, ("e2", "e4"))
    session.dispatch({"action": "computer-move"})
    play(session, ("d2", "d4"))
    session.dispatch({"action": "computer-move"})
    assert len(session.notation) == 4
    view = undo(session)
    assert view["moves"] == session.notation[:2] and len(view["moves"]) == 2
    assert view["turn"] == "w"
    assert view["board"]["d2"] == "wP"
    view = undo(session)
    assert session.position == new_position()
    assert view["moves"] == []
    view = undo(session)
    assert session.position == new_position()


def test_undo_against_the_computer_before_its_reply_reverts_your_move():
    session = Session("computer")
    play(session, ("e2", "e4"))
    view = undo(session)
    assert session.position == new_position()
    assert view["turn"] == "w"


def test_undo_against_the_computer_after_you_checkmate_it():
    # Your mating move leaves the computer no reply; undo takes back just that move.
    session = Session("computer")
    session.position = [{"g1": "wK", "a1": "wR", "g8": "bK",
                         "f7": "bP", "g7": "bP", "h7": "bP"}, "w"]
    play(session, ("a1", "a8"))
    assert session.view()["status"] == "checkmate"
    view = undo(session)
    assert view["board"]["a1"] == "wR"
    assert view["turn"] == "w"
    assert view["moves"] == []


def test_new_game_clears_undo_history():
    session = Session()
    play(session, ("e2", "e4"))
    view = session.dispatch({"action": "new"})
    assert view["can_undo"] is False
    undo(session)
    assert session.position == new_position()
