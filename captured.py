"""The captured-pieces sidebar: pieces actually taken, as they were when taken."""


def captured_pieces(positions, moves):
    """The piece each move removed from the board, in the order they were taken.

    positions[i] is the position before moves[i], so whatever stood on the target
    square at that moment is what the move captured. Nothing is stored, so the list
    is always in step with undo, load and new game. A pawn that only promotes takes
    nothing, and a promoted piece that is later taken shows as what it had become.
    """
    return [before[0][entry["target"]] for before, entry in zip(positions, moves)
            if entry["target"] in before[0]]
