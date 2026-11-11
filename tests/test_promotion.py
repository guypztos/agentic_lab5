import pytest

from computer import choose_move
from game import copy_position, legal_moves, move
from session import Session


def test_white_capture_promotion():
    session = Session()
    session.dispatch({"action": "promotion-setup"})
    legal = session.dispatch({"action": "legal", "source": "b7"})
    assert "a8" in legal["promotions"]
    session.play("b7", "a8", "Q")
    assert session.position[0]["a8"] == "wQ"
    assert session.position[1] == "b"
    session.play("g2", "h1", "N")
    assert session.position[0]["h1"] == "bN"
    assert "b7" in legal_moves(session.position, "a8")


@pytest.mark.parametrize("piece", list("QRBN"))
def test_chosen_piece_and_notation(piece):
    position = [{"a1": "wK", "h6": "bK", "d7": "wP"}, "w"]
    label = move(position, "d7", "d8", piece)
    assert position[0]["d8"] == "w" + piece
    assert label.startswith("d7-d8=" + piece)


@pytest.mark.parametrize("choice", [None, "K", "P", "X"])
def test_promotion_needs_a_valid_choice(choice):
    position = [{"a1": "wK", "h6": "bK", "d7": "wP"}, "w"]
    before = copy_position(position)
    with pytest.raises(ValueError):
        move(position, "d7", "d8", choice)
    assert position == before


def test_computer_promotes():
    position = [{"a8": "wK", "e8": "bK", "h2": "bP"}, "b"]
    assert choose_move(position) == ("h2", "h1", "Q")


def test_choice_only_on_promotion():
    session = Session()
    with pytest.raises(ValueError):
        session.play("e2", "e4", "Q")


def test_undo_turns_a_promoted_piece_back_into_a_pawn():
    session = Session()
    session.dispatch({"action": "promotion-setup"})
    session.play("b7", "a8", "Q")
    view = session.dispatch({"action": "undo"})
    assert view["board"]["b7"] == "wP"
    assert view["board"]["a8"] == "bR"
    assert view["moves"][-1] == "h3xg2"
    assert view["turn"] == "w"


def test_saved_promotion_is_replayed_on_load(tmp_path):
    first = Session(save_path=tmp_path / "game.json")
    first.dispatch({"action": "promotion-setup"})
    first.play("b7", "a8", "N")
    first.save()
    second = Session(save_path=tmp_path / "game.json")
    second.load()
    assert second.position == first.position
    assert second.position[0]["a8"] == "wN"
    assert second.notation == first.notation
    second.dispatch({"action": "undo"})
    assert second.position[0]["b7"] == "wP"


def test_promotion_is_not_counted_as_a_capture():
    session = Session()
    session.dispatch({"action": "promotion-setup"})
    # The setup took a black pawn (a6xb7) and a white pawn (h3xg2).
    assert session.view()["captured"] == ["bP", "wP"]
    session.play("b7", "a8", "Q")
    assert session.view()["captured"] == ["bP", "bR", "wP"]


def test_undo_after_the_computer_promotes():
    session = Session("computer")
    session.position = [{"a8": "wK", "e8": "bK", "h2": "bP", "c2": "wP"}, "w"]
    session.dispatch({"action": "move", "source": "c2", "target": "c3"})
    session.dispatch({"action": "computer-move"})
    assert session.position[0]["h1"] == "bQ"
    session.dispatch({"action": "undo"})
    assert session.position == [{"a8": "wK", "e8": "bK", "h2": "bP", "c2": "wP"}, "w"]
