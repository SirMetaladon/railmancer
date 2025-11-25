"""
rough outline:

start at a position,direction, heading
randomly pick another track to add
if the endpoint lies outside the map, don't add the track and add 1 to the fail counter
after the fail counter gets higher than, like, 10, back up 1 more track and add increment the previous piece's fail counter


"""

import random
from railmancer import tools, track, cfg

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


def track_placement_is_valid(model, current_node):
    print(model, current_node)
    test_node = track.get_new_node_from_node_and_model(model, current_node)

    end = (test_node[0][0], test_node[0][1])

    # if track-end is inside the box
    return tools.within2d(end, cfg.get("trackhammer_boxsize"))


"""
# needs a baseline initiator to make CFG things global variables to prevent overhead


# this entire function needs to be rewritten
def start(start_node, piece_count):
    # FYI: Nodes are defined as [[x, y, z], "string TP3 direction", base rotation in 90 increments, IsReversed (compile relevant only)]
    # what if I separated the track list and the node list? capital

    current_list_of_track_models = []
    current_chain_of_nodes = {}
    current_chain_of_nodes[0] = start_node

    while (
        len(current_list_of_track_models) < piece_count
    ):  # main loop for overall length (change to be distance-based)

        current_explore = current_chain_of_nodes[len(current_list_of_track_models)]

        possible_tracks = track.valid_next_tracks(current_explore["node"][1], 0)

        # why does it only sample a portion of it? what's with the magic number
        # oh I see why: it's to limit the number of retests in situations where finding the right piece is unlikely. If you can't find a valid one in 1/3rd of the cases, you are probably too close to existing track
        current_explore["tracks_to_test"] = sprinkle_selector(
            possible_tracks, int(len(possible_tracks) * 1 / 3), 15
        )

        failure = 2

        for test_track in current_explore["tracks_to_test"]:

            current_node = current_explore["node"]

            if track_placement_is_valid(current_node, test_track[0]):

                current_list_of_track_models += [test_track[0]]
                current_chain_of_nodes[len(current_list_of_track_models)][
                    "node"
                ] = test_node
                failure = 0
                break

        for _ in range(failure):
            if len(current_list_of_track_models):
                current_list_of_track_models.pop(-1)

    track.write_pathfinder_data(
        current_list_of_track_models,
        start_node,
    )"""


# NEW FUNCTION

# start with a loop that keeps placing rails utilizing the trackhammer existing picker algorithm


def generate_selection_of_possible_tracks(current_end_node):
    # takes direction, minumum radius level, minimum grade level, maximum grade level
    possible_tracks = track.valid_next_tracks(current_end_node[1], 0, 2)  # upbound
    random.shuffle(possible_tracks)
    return possible_tracks


def generate_mainline(start_node, length_target_in_miles):
    # FYI: Nodes are defined as [[x, y, z], "string TP3 direction", base rotation in 90 increments, IsReversed (compile relevant only)]
    list_of_track_models = []
    list_of_nodes = [start_node]
    list_of_generated_possible_tracks = []
    line_length_inches = 0
    list_of_fails_at_node = []
    fails_until_backup = 15
    backup_once_failed = 2
    length_target_in_inches = length_target_in_miles

    while line_length_inches < length_target_in_inches:

        index = len(list_of_track_models)  # address the current end node

        current_end_node = list_of_nodes[index]

        # if this is a fresh node, generate selection of options and save it, and reset the fail counter
        if len(list_of_fails_at_node) <= index or list_of_fails_at_node[index] is False:

            while len(list_of_generated_possible_tracks) <= index:
                list_of_generated_possible_tracks += [[]]

            list_of_generated_possible_tracks[index] = (
                generate_selection_of_possible_tracks(current_end_node)
            )

            while len(list_of_fails_at_node) <= index:
                list_of_fails_at_node += [0]
            list_of_fails_at_node[index] = fails_until_backup

        print(list_of_generated_possible_tracks)

        for track_to_test in list_of_generated_possible_tracks[index]:

            result_node = track_placement_is_valid(track_to_test, current_end_node)

            if result_node is not False:

                list_of_track_models += [track_to_test]
                list_of_nodes[index + 1]["node"] = result_node
                line_length_inches += track.get_length(track_to_test)

            else:

                list_of_fails_at_node[index] -= 1

            if list_of_fails_at_node[index] == 0:

                for back in range(backup_once_failed):

                    line_length_inches -= track.get_length(list_of_track_models[-1])
                    list_of_track_models.pop(-1)
                    list_of_fails_at_node[index - back - 1] = False

                break
