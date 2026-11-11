"""The captured-pieces sidebar: pieces actually taken, as they were when taken."""


def captured_pieces(positions, moves):
    """The pieces the moves removed from the board, grouped by colour and type.

    positions[i] is the position before moves[i], so whatever stood on the target
    square at that moment is what the move captured. Nothing is stored, so the list
    is always in step with undo, load and new game. Comparing the board with the
    start would count a promoted pawn as captured; here a pawn that only promotes
    takes nothing, and a promoted piece that is later taken shows as what it had become.
    """
    return sorted(before[0][entry["target"]]
                  for before, entry in zip(positions, moves, strict=True)
                  if entry["target"] in before[0])
