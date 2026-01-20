"""
rough outline:

start at a position,direction, heading
randomly pick another track to add
if the endpoint lies outside the map, don't add the track and add 1 to the fail counter
after the fail counter gets higher than, like, 10, back up 1 more track and add increment the previous piece's fail counter


"""

import random, math, time
from railmancer import tools, track, cfg, lines, vmfpy
from scipy.spatial import distance
import numpy as np

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


def get_box_ids(point):

    x, y, z = point

    fx = x / BlockHorizontal
    fy = y / BlockHorizontal
    fz = z / BlockVertical

    bx = math.floor(fx)
    by = math.floor(fy)
    bz = math.floor(fz)

    # Decide which side of the box center we're on
    xs = [bx, bx + 1] if fx - bx > 0.5 else [bx - 1, bx]
    ys = [by, by + 1] if fy - by > 0.5 else [by - 1, by]
    zs = [bz, bz + 1] if fz - bz > 0.5 else [bz - 1, bz]

    return [f"{x},{y},{z}" for x in xs for y in ys for z in zs]


def boxes_new(list_of_points):

    new_boxes = []

    for point in list_of_points:
        box_ids = get_box_ids(point)

        for box in box_ids:
            if box not in Boxes:
                new_boxes += [box]
                Boxes[box] = True

    # rint("added", len(Boxes), new_boxes)

    return new_boxes


def exclude_existing():

    current_points = lines.get_all_track_points()
    new_boxes = boxes_new(current_points)
    print(f"Imported {len(current_points)} points, created {len(new_boxes)} boxes.")


def are_points_blocked(list_of_points):

    for point in list_of_points:
        box_ids = get_box_ids(point)
        for box in box_ids:
            if box in Boxes:
                return True

    return False


def boxes_remove(list_of_box_ids):

    global Boxes

    for entry in list_of_box_ids:
        if entry in Boxes:
            Boxes.pop(entry)

    # rint("removed", len(Boxes), list_of_box_ids)


def get_box_points_from_nodes(current_node, next_node):

    # laceholder, will use beziers to scan points along the way in the future - maybe not needed
    # TO IMPLEMENT
    # list_of_points = lines.convert_bezier_to_points(lines.convert_nodes_to_bezier(current_node, next_node))

    extras = []
    cutoff = BlockHorizontal * 0.85  # horizontal block dist
    dist = distance.euclidean(current_node[0], next_node[0])
    iterations = math.floor(dist / cutoff)

    start = np.asarray(current_node[0])
    end = np.asarray(next_node[0])

    if iterations > 1:
        for iter in range(1, iterations):
            extras += [tools.linterp(start, end, iter / (iterations + 1))]

    return [next_node[0]] + extras


def track_placement_is_valid(model, current_node):
    test_node = track.get_new_node_from_node_and_model(model, current_node)

    points = get_box_points_from_nodes(current_node, test_node)

    end = (int(test_node[0][0]), int(test_node[0][1]))
    valid = tools.within2d(end, cfg.get("trackhammer_border"))

    if valid:
        valid = not are_points_blocked(points)

    # if track-end is inside the box and
    return (test_node, valid, points)


# NEW FUNCTION

# start with a loop that keeps placing rails utilizing the trackhammer existing picker algorithm


def generate_selection_of_possible_tracks(node, count, params={}):

    # takes direction, minumum radius level, minimum grade level, maximum grade level
    possible_tracks = track.valid_next_tracks(node[1], params)

    # rint(possible_tracks)  # gets evens  # upbound
    return sprinkle_selector(possible_tracks, count)


def update_boxes(current_steps, boxes_step):

    current_length = current_steps[-1]["length"]

    # rint("updated boxes", len(current_steps), boxes_step)

    if boxes_step >= len(current_steps):

        print("This should not be possible!")
        return boxes_step

    else:

        distance_away = current_length - current_steps[boxes_step]["length"]
        direction_to_go = (
            "Forward" if distance_away > boxes_separation_distance else "Backward"
        )

    step_to_test = boxes_step

    if direction_to_go == "Forward":
        while (
            current_length - current_steps[step_to_test + 1]["length"]
        ) > boxes_separation_distance:

            boxes_added = boxes_new(current_steps[step_to_test]["points"])

            current_steps[step_to_test]["boxes_added"] = boxes_added + current_steps[
                step_to_test
            ].get("boxes_added", [])
            # rint("moved up", current_length, current_steps[step_to_test]["length"])
            step_to_test += 1

    if direction_to_go == "Backward":
        while (
            current_length - current_steps[step_to_test - 1]["length"]
        ) <= boxes_separation_distance and step_to_test > 0:

            boxes_remove(current_steps[step_to_test]["boxes_added"])

            current_steps[step_to_test]["boxes_added"] = []
            # rint("moved down", current_length, current_steps[step_to_test]["length"])
            step_to_test -= 1

    return step_to_test


def initialize():

    global BlockHorizontal
    global BlockVertical
    global boxes_separation_distance

    BlockHorizontal = 2000
    BlockVertical = cfg.get("sector_minimum_height") * 1.1
    boxes_separation_distance = 3000

    global Boxes
    Boxes = {}


def generate_mainline(start_node, length_target_mi, params={}):
    # FYI: Nodes are defined as [[x, y, z], "string TP3 direction", base rotation in 90 increments, IsReversed (compile relevant only)]

    boxes_remove(get_box_ids(start_node[0]))

    CountOverall = 10000000
    CountInterval = 1000
    backtrack_length = 6000
    length_target_in = length_target_mi * 5280 * 12

    rollbacks = [6]
    candidates = [40]

    random.shuffle(rollbacks)
    random.shuffle(candidates)

    tools.stopwatch_click("trackhammer")

    for Rollback in rollbacks:

        for candidates_to_generate in candidates:

            ct = 0
            boxes_step_index = 0
            logLength = 0

            def new_step(start_node, existing_length, points=[], model=""):
                return [
                    {
                        "model": model,
                        "node": start_node,
                        "length": existing_length,
                        "candidate_tracks": generate_selection_of_possible_tracks(
                            start_node, candidates_to_generate, params
                        ),  # count of these remaining = your fail counter
                        "points": points,
                        "boxes_added": [],
                    }
                ]

            steps = new_step(start_node, 0)

            while steps[-1]["length"] < length_target_in and ct < CountOverall:
                # might include a break inside, but this is a failsafe

                boxes_step_index = update_boxes(steps, boxes_step_index)

                current_step = steps[-1]

                while len(current_step["candidate_tracks"]):

                    track_to_test = current_step["candidate_tracks"][-1]

                    # rint("examined " + track_to_test + " from node " + str(len(steps)))

                    result_node, valid, points = track_placement_is_valid(
                        track_to_test, current_step["node"]
                    )

                    if valid:

                        new_length = current_step["length"] + track.get_length(
                            track_to_test
                        )
                        if ct % CountInterval == 0:
                            logLength = max(logLength, round(new_length / 12 / 5218, 3))
                            print(
                                len(steps),
                                round(new_length / 12 / 5218, 3),
                                len(current_step["candidate_tracks"]),
                                len(Boxes),
                            )
                        ct += 1

                        steps += new_step(
                            result_node, new_length, points, track_to_test
                        )
                        break

                    else:

                        current_step["candidate_tracks"].remove(track_to_test)

                if len(current_step["candidate_tracks"]) == 0:

                    """rint(
                        "Rolled back "
                        + str(min(math.floor(Rollback), len(steps) - 1))
                        + ", length is now "
                        + str(int(steps[-min(math.floor(Rollback), len(steps))]["length"]))
                    )"""
                    for _ in range(min(math.floor(Rollback), len(steps) - 1)):
                        if boxes_step_index == len(steps) - 1:
                            boxes_remove(steps[-1]["boxes_added"])
                            """rint(
                                "kicked back boxes due to rollback",
                                boxes_step_index,
                                len(steps),
                            )"""
                            boxes_step_index -= 1
                        steps.pop(-1)  # temp

            sec = tools.stopwatch_click(
                "trackhammer", f"{Rollback}, {candidates_to_generate}, {logLength}"
            )

            print(f"{logLength/sec}")

    def box_id_to_coords(box_id):

        coords = box_id.split(",")
        x = int(coords[0])
        y = int(coords[1])
        z = int(coords[2])

        return x * BlockHorizontal, y * BlockHorizontal, z * BlockVertical

    for box in Boxes:

        x, y, z = box_id_to_coords(box)

        vmfpy.add_brush(
            [
                x,
                x + BlockHorizontal,
                y,
                y + BlockHorizontal,
                z,
                z + BlockVertical,
                "dev/dev_measurewall01d",
                0,
                0,
                "24",
            ]
        )

    # rint(len(Boxes))

    tools.stopwatch_click("submodule", "Mainline generation complete")

    ModelList = []

    for Step in steps[1:]:
        ModelList += [Step["model"]]

    track.write_pathfinder_data(ModelList, start_node)

    tools.stopwatch_click("submodule", "Pathfinder data written")
