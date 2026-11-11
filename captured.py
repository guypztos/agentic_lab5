"""Pieces for the captured-pieces sidebar."""


def captured_pieces(positions, moves):
    """Pieces taken so far, from the position before each move and the move played.

    Comparing the board with the start would count a promoted pawn as captured.
    """
    return sorted(before[0][entry["target"]] for before, entry in zip(positions, moves)
                  if entry["target"] in before[0])
