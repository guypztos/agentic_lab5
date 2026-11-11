from session import Session


def test_display_after_capture_and_new_game():
    session = Session()
    assert session.view()["captured"] == []
    session.play("e2", "e4")
    session.play("d7", "d5")
    session.play("e4", "d5")
    assert session.view()["captured"] == ["bP"]
    session.dispatch({"action": "new"})
    assert session.view()["captured"] == []


def test_undo_returns_a_captured_piece_to_the_board():
    session = Session()
    session.play("e2", "e4")
    session.play("d7", "d5")
    session.play("e4", "d5")
    view = session.dispatch({"action": "undo"})
    assert view["captured"] == []
    assert view["board"]["d5"] == "bP"


def test_loaded_game_shows_its_captures(tmp_path):
    first = Session(save_path=tmp_path / "game.json")
    first.play("e2", "e4")
    first.play("d7", "d5")
    first.play("e4", "d5")
    first.save()
    second = Session(save_path=tmp_path / "game.json")
    second.load()
    assert second.view()["captured"] == ["bP"]
