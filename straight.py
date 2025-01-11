import random, time


def create_new_card(current_state, new_piece, target):
    """Create a new state with the given piece added."""
    new_total = current_state[0] + new_piece
    new_pieces = current_state[1] + [new_piece]
    heuristic = new_total if new_total <= target else 0
    return (new_total, new_pieces), heuristic


def insert_card(cards, new_card):
    """Insert the new card into the list, maintaining heuristic order."""
    heuristic = new_card[1]
    for index, (_, h) in enumerate(cards):
        if heuristic > h:
            if heuristic == 5920:
                print(index)
            cards.insert(index, new_card)
            return
    cards.append(new_card)


def decompose(target):

    if target % 16 != 0:
        return None

    lengths = [
        32,
        48,
        64,
        96,
        128,
        192,
        256,
        384,
        512,
        768,
        1024,
        1536,
        2048,
        3072,
        4096,
        6144,
        8192,
    ]

    # Initialize the starting state
    initial_state = (0, [])
    cards = [(initial_state, 0)]

    while cards and cards[0][0][0] != target:
        current_state = cards.pop(0)
        for length in lengths:
            new_card = create_new_card(current_state[0], length, target)

            insert_card(cards, new_card)

    if cards:
        random.shuffle(cards[0][0][1])
        return cards[0][0][1]

    else:
        return None
