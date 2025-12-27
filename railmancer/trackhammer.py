"""
rough outline:

start at a position,direction, heading
randomly pick another track to add
if the endpoint lies outside the map, don't add the track and add 1 to the fail counter
after the fail counter gets higher than, like, 10, back up 1 more track and add increment the previous piece's fail counter


"""

import random, math
from railmancer import tools, track, cfg, lines

# This is an algoritm for pathing a mainline through the playable area without bumping into itself. Last part pending.


def sprinkle_selector(list, count):

    import random

    output = []
    working = list[:]
    for _ in range(count):
        choice = random.choice(working)
        working.remove(choice)
        output += [choice]
        if count == len(output) or len(working) == 0:
            break

    return output


def get_box_id(point):

    horizontal_gap = 2048
    vertical_gap = 2048

    block_size_xy = horizontal_gap / 1
    block_size_z = vertical_gap / 1

    x, y, z = point

    block_x = math.floor(x / block_size_xy)
    block_y = math.floor(y / block_size_xy)
    block_z = math.floor(z / block_size_z)

    block_id = str(block_x) + "," + str(block_y) + "," + str(block_z)

    print(point, block_id)

    return block_id


def boxes_new(list_of_points):

    global boxes

    try:
        boxes
    except:
        boxes = {}

    new_boxes = []

    for point in list_of_points:
        box_id = get_box_id(point)

        if box_id not in boxes:
            new_boxes += [box_id]

    return new_boxes


def boxes_remove(list_of_indexes):

    global boxes

    for entry in list_of_indexes:
        boxes.pop(entry)


def track_placement_is_valid(model, current_node, old_points):
    test_node = track.get_new_node_from_node_and_model(model, current_node)

    end = (int(test_node[0][0]), int(test_node[0][1]))
    valid = tools.within2d(end, cfg.get("trackhammer_boxsize") / 2)

    new_boxes = []

    if valid:
        new_boxes = boxes_new(old_points)

    # if track-end is inside the box
    return (test_node, len(new_boxes) != 0, [test_node[0]])


# NEW FUNCTION

# start with a loop that keeps placing rails utilizing the trackhammer existing picker algorithm


def generate_selection_of_possible_tracks(node, count):
    # takes direction, minumum radius level, minimum grade level, maximum grade level
    possible_tracks = track.valid_next_tracks(node[1], 0, 2)

    # print(possible_tracks)  # gets evens  # upbound
    return sprinkle_selector(possible_tracks, count)


def generate_mainline(start_node, length_target_mi):
    # FYI: Nodes are defined as [[x, y, z], "string TP3 direction", base rotation in 90 increments, IsReversed (compile relevant only)]

    global boxes

    candidates_to_generate = 15
    backtrack_length = 6000
    length_target_in = length_target_mi * 5280 * 12

    def new_step(start_node, existing_length, points=[], model=""):
        return [
            {
                "model": model,
                "node": start_node,
                "length": existing_length,
                "candidate_tracks": generate_selection_of_possible_tracks(
                    start_node, candidates_to_generate
                ),  # count of these remaining = your fail counter
                "points": points,
            }
        ]

    steps = new_step(start_node, 0)

    while steps[-1]["length"] < length_target_in:
        # might include a break inside, but this is a failsafe

        current_step = steps[-1]

        # take current endmost node

        # iterate through the forked node and find a potential new one

        # if more than max_fails finds do not work, roll back to the node backtrack_steps away and go back to step 1

        while len(current_step["candidate_tracks"]):

            track_to_test = current_step["candidate_tracks"][-1]

            print("examined " + track_to_test + " from node " + str(len(steps)))

            old_points = []
            if len(steps) > 3:
                old_points = steps[-4]["points"]

            result_node, valid, new_points = track_placement_is_valid(
                track_to_test, current_step["node"], old_points
            )

            if valid is not False:

                new_length = current_step["length"] + track.get_length(track_to_test)
                # TO IMPLEMENT
                # list_of_points = lines.convert_bezier_to_points(lines.convert_nodes_to_bezier(result_node, blabla))
                if len(steps) > 3:
                    for entry in steps[-4]:
                        boxes[entry] = True

                steps += new_step(result_node, new_length, new_points, track_to_test)
                break

            else:

                current_step["candidate_tracks"].remove(track_to_test)

        if len(current_step["candidate_tracks"]) == 0:

            print("Rolled back 4, length is now " + str(len(steps)))
            for _ in range(min(4, len(steps) - 1)):
                if len(steps) > 3:
                    boxes_remove(steps[-4]["boxes"])
                steps.pop(-1)  # temp

    ModelList = []

    for Step in steps[1:]:
        ModelList += [Step["model"]]

    track.write_pathfinder_data(ModelList, start_node)


"""for back in range(backtrack_steps):

    current_length -= track.get_length(track_models[-1])
    track_models.pop(-1)
    list_of_fails_at_node[index - back - 1] = False

break"""
