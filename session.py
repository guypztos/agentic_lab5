"""Application actions and information shown beside the board."""

import json
from pathlib import Path

from captured import captured_pieces
from computer import choose_move
from game import (
    copy_position,
    legal_moves,
    move,
    new_position,
    promotes,
    status,
    winner,
)

# Legal from the standard starting position under this game's rules.
# Next move: b7-a8, capturing a rook and reaching the last rank.
PROMOTION_SETUP = [
    ("a2", "a4"), ("h7", "h5"),
    ("a4", "a5"), ("h5", "h4"),
    ("a5", "a6"), ("h4", "h3"),
    ("a6", "b7"), ("h3", "g2"),
]

SAVE_FORMAT = 1


class Session:
    # Where "save" writes and "load" reads. Tests give each session its own file.
    save_path = Path(__file__).parent / "game.save.json"

    def __init__(self, opponent="human", save_path=None):
        if opponent not in ("human", "computer"):
            raise ValueError("Unknown opponent")
        self.position = new_position()
        self.notation = []
        # Position before each move, so undo can restore it exactly.
        self.positions = []
        # Each move played, as "save" writes it. Undo removes the move again.
        self.history = []
        # Moves taken back by undo, most recent last; redo replays the last one.
        self.undone = []
        self.opponent = opponent
        # "new" re-runs __init__ without a path, so an instance keeps the one it has.
        if save_path is not None:
            self.save_path = Path(save_path)

    def play(self, source, target, promotion=None):
        """Play a new move. It starts a different continuation, so redo is discarded."""
        self.apply(source, target, promotion)
        self.undone = []

    def apply(self, source, target, promotion=None):
        before = copy_position(self.position)
        label = move(self.position, source, target, promotion)
        self.positions.append(before)
        self.notation.append(label)
        entry = {"source": source, "target": target}
        if promotion is not None:
            entry["promotion"] = promotion
        self.history.append(entry)
        self.after_move()

    def undo(self):
        """Take back the last move; against the computer, also your move before it.

        Against the computer, moves are taken back until it is White's turn again, so
        after its reply both its move and yours are undone. At the start, nothing happens.
        """
        if not self.positions:
            return
        self.undo_one()
        while (self.opponent == "computer" and self.position[1] != "w"
               and self.positions):
            self.undo_one()

    def undo_one(self):
        self.position = self.positions.pop()
        self.notation.pop()
        self.undone.append(self.history.pop())

    def redo(self):
        """Replay the last undone move; against the computer, the reply it had too.

        The mirror of undo: moves are restored until it is White's turn again, so the
        computer's move comes back as it was played rather than being chosen afresh.
        With nothing undone, nothing happens.
        """
        if not self.undone:
            return
        self.redo_one()
        while (self.opponent == "computer" and self.position[1] != "w"
               and self.undone):
            self.redo_one()

    def redo_one(self):
        self.apply(**self.undone.pop())

    def after_move(self):
        pass

    def view(self):
        return {
            "board": self.position[0],
            "turn": self.position[1],
            "moves": self.notation,
            "can_undo": bool(self.positions),
            "can_redo": bool(self.undone),
            "opponent": self.opponent,
            "status": status(self.position),
            "winner": winner(self.position),
            **self.sidebar(),
        }

    def computer_to_move(self):
        return (self.opponent == "computer" and self.position[1] == "b"
                and status(self.position) not in ("checkmate", "stalemate"))

    def sidebar(self):
        # Worked out from the recorded moves, so it stays right after undo and load.
        return {"captured": captured_pieces(self.positions, self.history)}

    def to_dict(self):
        """The saved form: the opponent, every move played, and the moves undone.

        Replaying the moves rebuilds everything else, including whatever later
        features derive from the moves, so this is also enough to undo them. The
        undone moves follow in the order they would be redone, so "moves" and
        "undone" together read as one line of play.
        """
        return {"format": SAVE_FORMAT,
                "opponent": self.opponent,
                "moves": [dict(entry) for entry in self.history],
                "undone": [dict(entry) for entry in reversed(self.undone)]}

    @classmethod
    def from_dict(cls, data, save_path=None):
        """A fresh session with the saved game replayed into it."""
        if not isinstance(data, dict) or data.get("format") != SAVE_FORMAT:
            raise ValueError("That is not a saved game from this program")
        moves = data.get("moves")
        undone = data.get("undone", [])
        for entries in (moves, undone):
            if not isinstance(entries, list) or not all(isinstance(m, dict) for m in entries):
                raise ValueError("The saved game has no move list")
        session = cls(data.get("opponent"), save_path)
        try:
            # Playing the undone moves too checks they are legal continuations;
            # taking them back again leaves them ready to redo.
            for entry in moves + undone:
                session.apply(**entry)
        except (TypeError, ValueError) as error:
            raise ValueError(f"The saved game contains an invalid move: {error}") from error
        for _ in undone:
            session.undo_one()
        return session

    def save(self):
        self.save_path.write_text(json.dumps(self.to_dict(), indent=2) + "\n")

    def load(self):
        """Replace this game with the saved one. On any error the game is unchanged."""
        try:
            data = json.loads(self.save_path.read_text())
        except FileNotFoundError:
            raise ValueError("There is no saved game") from None
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"The saved game could not be read: {error}") from error
        loaded = Session.from_dict(data, self.save_path)
        vars(self).update(vars(loaded))

    def dispatch(self, action):
        command = action.get("action")
        if command == "move":
            if self.computer_to_move():
                raise ValueError("Wait for the computer's move")
            self.play(action.get("source"), action.get("target"), action.get("promotion"))
        elif command == "computer-move":
            if not self.computer_to_move():
                raise ValueError("It is not the computer's turn")
            self.play(*choose_move(self.position))
        elif command == "undo":
            self.undo()
        elif command == "redo":
            self.redo()
        elif command == "legal":
            source = action.get("source")
            targets = legal_moves(self.position, source)
            return {"targets": targets,
                    "promotions": [t for t in targets if promotes(self.position, source, t)]}
        elif command == "new":
            self.__init__(action.get("opponent", "human"))
        elif command == "promotion-setup":
            self.__init__()
            for source, target in PROMOTION_SETUP:
                self.play(source, target)
        elif command == "save":
            self.save()
        elif command == "load":
            self.load()
        else:
            raise ValueError("Unknown action")
        return self.view()
