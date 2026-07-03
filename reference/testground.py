"""def aggregate(track_profile):

    print(track_profile)

    Total = 0
    Lengths = track_profile[1::2]
    Incrementor = 1

    for Entry in Lengths:
        track_profile[Incrementor] = Entry + Total

        Total += Entry
        Incrementor += 2

    print(track_profile)

    return track_profile


aggregate(["main", 0.5, "left", 1, "main", 0.5])
"""

DIRECTIONS = {
    "0fw": (1, 0),
    "1lt": (1, 1 / 4),
    "2lt": (1, 1 / 2),
    "4lt": (1, 1),
    "8lt": (0, 1),
    "1rt": (1, -1 / 4),
    "2rt": (1, -1 / 2),
    "4rt": (1, -1),
    "8rt": (0, -1),
}

# the spacings going RIGHTWARD from Main - so turning right takes you "backwards", turning left takes you "forwards"
TRACK_SPACING = {
    "0fw": (0, 192),
    "1lt": (48, 192),
    "2lt": (96, 192),
    "4lt": (144, 144),
    "8lt": (192, 0),
    "1rt": (-48, 192),
    "2rt": (-96, 192),
    "4rt": (-144, 144),
    "8rt": (-192, 0),
}


def solve_first_offset(start_direction, end_direction):
    start_dir_x, start_dir_y = DIRECTIONS[start_direction]
    end_dir_x, end_dir_y = DIRECTIONS[end_direction]

    start_spacing_x, start_spacing_y = TRACK_SPACING[start_direction]
    end_spacing_x, end_spacing_y = TRACK_SPACING[end_direction]

    # Find where these two offset track centerlines intersect:
    #
    # start_offset + start_distance * start_direction
    # end_offset   + end_distance   * end_direction

    delta_x = end_spacing_x - start_spacing_x
    delta_y = end_spacing_y - start_spacing_y

    determinant = (start_dir_x * -end_dir_y) - (-end_dir_x * start_dir_y)

    if abs(determinant) < 1e-8:
        # raise ValueError("Start and end directions are parallel.")
        return start_spacing_x, start_spacing_y

    start_distance = ((delta_x * -end_dir_y) - (-end_dir_x * delta_y)) / determinant

    intersection_x = start_spacing_x + start_distance * start_dir_x
    intersection_y = start_spacing_y + start_distance * start_dir_y

    return intersection_x, intersection_y


def boundary_shift(offsets, start_direction, end_direction):
    dx, dy = DIRECTIONS[start_direction]

    farthest_back_distance = min(x * dx + y * dy for x, y, _ in offsets)

    print(farthest_back_distance)

    if farthest_back_distance >= 0:  # if there's no infringement

        output = offsets
        startshift = 0

    else:

        denom = dx * dx + dy * dy

        startshift = -farthest_back_distance / denom

        shift_x = startshift * dx
        shift_y = startshift * dy

        output = [(x + shift_x, y + shift_y, z) for x, y, z in offsets]

    dx, dy = DIRECTIONS[end_direction]
    farthest_forward_distance = max(x * dx + y * dy for x, y, _ in offsets)
    print(farthest_forward_distance)

    if (
        farthest_forward_distance <= 0
    ):  # if the main isn't pushing the node forward at all (unlikely)
        endshift = 0

    else:

        denom = dx * dx + dy * dy

        endshift = -farthest_forward_distance / denom

    return output, startshift, endshift


def generate_offsets(start_direction, end_direction, tracks_left, tracks_right):

    first_x, first_y = solve_first_offset(start_direction, end_direction)

    offsets = []
    offsets.append((0.0, 0.0, 0.0))

    for n in range(tracks_right, 0, -1):
        offsets.append((first_x * n, first_y * n, 0.0))

    for n in range(1, tracks_left + 1):
        offsets.append((-first_x * n, -first_y * n, 0.0))

    return boundary_shift(offsets, start_direction, end_direction)


print(generate_offsets("0fw", "4rt", 0, 1))
