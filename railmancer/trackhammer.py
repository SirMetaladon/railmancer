"""
rough outline:

start at a position,direction, heading
randomly pick another track to add
if the endpoint lies outside the map, don't add the track and add 1 to the fail counter
after the fail counter gets higher than, like, 10, back up 1 more track and add increment the previous piece's fail counter


"""

from railmancer import tools, track

# This is an algoritm for pathing a mainline through the playable area without bumping into itself. Last part pending.


def sprinkle_selector(list, variance, count):

    import random

    output = []
    fail = 0

    while count and fail < 100:

        new = list[random.randint(0, variance)]

        if new not in output:
            output += [new]
            count -= 1
        else:
            fail += 1

    return output


def start(start_node, piece_count):

    track_path_models = []
    exploration = [{} for _ in range(piece_count + 1)]
    exploration[0]["node"] = start_node

    while len(track_path_models) < piece_count:

        current_explore = exploration[len(track_path_models)]

        possible_tracks = track.valid_next_tracks(current_explore["node"][1], 0)

        current_explore["tracks_to_test"] = sprinkle_selector(
            possible_tracks, int(len(possible_tracks) * 1 / 3), 15
        )

        failure = 2

        for test_track in current_explore["tracks_to_test"]:

            current_node = current_explore["node"]

            test_node = track.append_track(test_track[0], current_node)

            end = (test_node[0][0], test_node[0][1])

            # if track-end is inside the box
            if tools.within2d(end, 15000):

                track_path_models += [test_track[0]]
                exploration[len(track_path_models)]["node"] = test_node
                failure = 0
                break

        for _ in range(failure):
            if len(track_path_models):
                track_path_models.pop(-1)

    track.write_pathfinder_data(
        track_path_models,
        start_node,
    )
