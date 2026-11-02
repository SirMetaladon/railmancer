import os, math, re, random
import numpy as np
from railmancer import lines, vmfpy, tools

# Contains everything to do with the Track Library, which is a dictionary of conversions between modelpaths and physical dimensions / extracted information.

track_model_library: dict = {}
valid_tracks_cache: dict = {}
track_straight_cache: dict = {}
straight_decomposition_cache: dict = {}


def determine_real_grade(raw_grade):
    if raw_grade == "0pg":
        return 0

    number_string = raw_grade[: len(raw_grade) - 2]

    return (
        int(
            number_string + ("0" * (3 + int("-" in number_string) - len(number_string)))
        )
        / 100
    )


def determine_grade_level(real_grade):

    Sign = 1 if real_grade >= 0 else -1

    if real_grade == 0:
        return 0
    elif abs(real_grade) < 2:
        return 1 * Sign
    elif abs(real_grade) < 2.6:
        return 2 * Sign
    else:
        return 3 * Sign


def get_heading(raw_direction):

    if raw_direction == "0fw":
        return (-4, 0, 0)
    elif raw_direction == "1rt":
        return (-4, 1, 0)
    elif raw_direction == "1lt":
        return (-4, -1, 0)
    elif raw_direction == "2rt":
        return (-4, 2, 0)
    elif raw_direction == "2lt":
        return (-4, -2, 0)

    elif raw_direction == "4rt":
        return (-4, 4, 0)
    elif raw_direction == "4lt":
        return (-4, -4, 0)
    elif raw_direction == "8rt":
        return (0, 4, 0)
    elif raw_direction == "8lt":
        return (0, -4, 0)

    elif raw_direction == "6rt":
        return (-2, 4, 0)
    elif raw_direction == "6lt":
        return (2, -4, 0)
    elif raw_direction == "7rt":
        return (-1, 4, 0)
    elif raw_direction == "7lt":
        return (1, -4, 0)
    else:
        print(raw_direction)


def direction_to_angle(Direction) -> float:

    Test = Direction[0]
    Handedness = 1 if "lt" in Direction else -1

    if Test == "0":
        return 0
    elif Test == "1":
        return 14 * Handedness
    elif Test == "2":
        return 26.6 * Handedness
    elif Test == "4":
        return 45 * Handedness
    elif Test == "8":
        return 90 * Handedness
    elif Test == "6":
        return 90 - 26.6 * Handedness
    elif Test == "7":
        return 90 - 14 * Handedness

    else:
        print(Direction)
        return 0


def determine_length(StartDirection, EndDirection, Radius):

    start_angle = direction_to_angle(StartDirection)
    end_angle = direction_to_angle(EndDirection)

    Degrees = abs(end_angle - start_angle)

    Length = round(Radius * math.pi * Degrees / 180, 2)

    if Length == 0:
        print("Failed determine length?", StartDirection, EndDirection, Radius)

    return Length


def extract_digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def process_arc(path):

    # example input: models/trakpak3_rsg/arcs/r6144s/a0fw_8lt_left_236pg_+6144x-6144x+228up.mdl

    folder = path[-2]
    Radius = int(extract_digits(folder))

    filename = path[-1]
    data = list(filename.split("_"))

    StartDirection = data[0][1:]
    EndDirection = data[1]
    RealGrade = determine_real_grade(data[3])
    GradeLevel = determine_grade_level(RealGrade)

    Length = determine_length(StartDirection, EndDirection, Radius)

    data2 = data[4].split("x")
    ChangeX = int(data2[0])
    ChangeY = int(data2[1])
    ChangeZ = int(data2[2][:4])

    ApproxGrade = round((ChangeZ / Length) * 100, 2)

    return [
        {
            "Length": Length,
            "Radius": Radius,
            "StartDirection": StartDirection,
            "EndDirection": EndDirection,
            "GradeLevel": GradeLevel,
            "Move": [-ChangeX, ChangeY, ChangeZ],
            "ApproxGrade": ApproxGrade,
            "RealGrade": RealGrade,
        }
    ]


def process_banked(path):

    # example input: models/trakpak3_rsg/banked/r4480/ab4lt_4rt_right_227pg_4h_48s_0f12_12f0_+6336x00000x+160up.mdl

    folder = path[-2]
    Radius = int(extract_digits(folder))

    filename = path[-1]
    data = list(filename.split("_"))

    StartDirection = data[0][2:]
    EndDirection = data[1]
    RealGrade = determine_real_grade(data[3])
    GradeLevel = determine_grade_level(RealGrade)

    Length = determine_length(StartDirection, EndDirection, Radius)

    data2 = data[-1].split("x")
    ChangeX = int(data2[0])
    ChangeY = int(data2[1])
    ChangeZ = int(data2[2][:4])

    ApproxGrade = round((ChangeZ / Length) * 100, 2)

    return [
        {
            "Length": Length,
            "Radius": Radius,
            "StartDirection": StartDirection,
            "EndDirection": EndDirection,
            "GradeLevel": GradeLevel,
            "Move": [-ChangeX, ChangeY, ChangeZ],
            "ApproxGrade": ApproxGrade,
            "RealGrade": RealGrade,
        }
    ]


def process_straight(path, model):

    global track_straight_cache

    data = list(path[-1].split("_"))
    StartDirection = data[1]
    EndDirection = data[1]
    RealGrade = determine_real_grade(data[2])
    GradeLevel = determine_grade_level(RealGrade)

    data2 = data[3].split("x")
    ChangeX = int(data2[0])
    ChangeY = int(data2[1])
    ChangeZ = int(data2[2][:4])

    Length = math.sqrt(
        math.pow(ChangeX, 2) + math.pow(ChangeY, 2) + math.pow(ChangeZ, 2)
    )

    ApproxGrade = round((ChangeZ / Length) * 100, 2)

    track_straight_cache[str(ChangeX) + "|" + EndDirection] = track_straight_cache.get(
        str(ChangeX) + "|" + EndDirection, {}
    )
    track_straight_cache[str(ChangeX) + "|" + EndDirection][GradeLevel] = model

    return [
        {
            "Length": Length,
            "Radius": 0,
            "StartDirection": StartDirection,
            "EndDirection": EndDirection,
            "GradeLevel": GradeLevel,
            # for some reason, TP3 tracks are like this;
            # the default (0 yaw) direction is -x, BUT
            # the Y value from that position is still
            # correct in the modelname. They're
            # mirrored around X = 0, basically.
            "Move": [-ChangeX, ChangeY, ChangeZ],
            "ApproxGrade": ApproxGrade,
            "RealGrade": RealGrade,
        }
    ]


def process_turnout(path):

    data = list(path[-1].split("_"))
    StartDirection = data[0][1:]
    EndDirection = data[1]

    data2 = data[3].split("x")
    ChangeX = int(data2[0])
    ChangeY = int(data2[1])

    data3 = data[4].split("x")
    ChangeX2 = int(data3[0])
    ChangeY2 = int(data3[1])

    # I may come back and allow the pathfinder to use these, but I highly doubt it
    # Much more likely I just use symbolic pieces and swap them in on compile.

    return [
        {
            "Length": 0,
            "Radius": 0,
            "StartDirection": StartDirection,
            "EndDirection": StartDirection,
            "GradeLevel": 0,
            "Move": [-ChangeX, ChangeY, 0],
            "ApproxGrade": 0,
            "RealGrade": 0,
        },
        {
            "Length": 0,
            "Radius": 0,
            "StartDirection": StartDirection,
            "EndDirection": EndDirection,
            "GradeLevel": 0,
            "Move": [-ChangeX2, ChangeY2, 0],
            "ApproxGrade": 0,
            "RealGrade": 0,
        },
    ]


def process_siding(path):

    data = list(path[-1].split("_"))
    StartDirection = data[0][1:]

    data2 = data[3].split("x")
    ChangeX = int(data2[0])
    ChangeY = int(data2[1])

    data3 = data[4].split("x")
    ChangeX2 = int(data3[0])
    ChangeY2 = int(data3[1])

    return [
        {
            "Length": 0,
            "Radius": 0,
            "StartDirection": StartDirection,
            "EndDirection": StartDirection,
            "GradeLevel": 0,
            "Move": [-ChangeX, ChangeY, 0],
            "ApproxGrade": 0,
            "RealGrade": 0,
        },
        {
            "Length": 0,
            "Radius": 0,
            "StartDirection": StartDirection,
            "EndDirection": StartDirection,
            "GradeLevel": 0,
            "Move": [-ChangeX2, ChangeY2, 0],
            "ApproxGrade": 0,
            "RealGrade": 0,
        },
    ]


def process_xover(path):

    data = list(path[-1].split("_"))

    # x0fw left minr2048 +0768x00000 +1536x-0192 dv
    StartDirection = data[0][1:]

    data2 = data[3].split("x")
    ChangeX = int(data2[0])
    ChangeY = int(data2[1])

    data3 = data[4].split("x")
    ChangeX2 = int(data3[0])
    ChangeY2 = int(data3[1])

    return [
        {
            "Length": 0,
            "Radius": 0,
            "StartDirection": StartDirection,
            "EndDirection": StartDirection,
            "GradeLevel": 0,
            "Move": [-ChangeX, ChangeY, 0],
            "ApproxGrade": 0,
            "RealGrade": 0,
        },
        {
            "Length": 0,
            "Radius": 0,
            "StartDirection": StartDirection,
            "EndDirection": StartDirection,
            "GradeLevel": 0,
            "Move": [-ChangeX2, ChangeY2, 0],
            "ApproxGrade": 0,
            "RealGrade": 0,
        },
    ]


def process_wye(path):

    data = list(path[-1].split("_"))

    # w0fw 1lt 1rt r2048 +0704x-0096 +0704x+0096 dv
    StartDirection = data[0][1:]
    EndDirection1 = data[1]
    EndDirection2 = data[2]

    data2 = data[4].split("x")
    ChangeX = int(data2[0])
    ChangeY = int(data2[1])

    data3 = data[5].split("x")
    ChangeX2 = int(data3[0])
    ChangeY2 = int(data3[1])

    return [
        {
            "Length": 0,
            "Radius": 0,
            "StartDirection": StartDirection,
            "EndDirection": EndDirection1,
            "GradeLevel": 0,
            "Move": [-ChangeX, ChangeY, 0],
            "ApproxGrade": 0,
            "RealGrade": 0,
        },
        {
            "Length": 0,
            "Radius": 0,
            "StartDirection": StartDirection,
            "EndDirection": EndDirection2,
            "GradeLevel": 0,
            "Move": [-ChangeX2, ChangeY2, 0],
            "ApproxGrade": 0,
            "RealGrade": 0,
        },
    ]


def process_file(model):

    path = model.split("/")

    if path[2] == "arcs":

        return process_arc(path)

    elif path[2] == "banked":

        return process_banked(path)

    elif path[-2] == "straights":

        return process_straight(path, model)

    elif path[3] == "turnouts":

        return process_turnout(path)

    elif path[3] == "sidings":

        return process_siding(path)

    elif path[3] == "xovers":

        return process_xover(path)

    elif path[3] == "wyes":

        return process_wye(path)

    else:

        print(f"No track-processing support for {model}")

    return []


def build_track_library(directory, extension):

    global track_model_library

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(extension):

                # why did I do it like this? dunno, it works
                model = "models" + ((root + "/" + file).split("models")[1]).replace(
                    "\\", "/"
                )

                track_data = process_file(model)

                if len(track_data) == 1:
                    # more than 1 is a switch, less than 1 is an invalid model
                    track_model_library[model] = track_data[0]

    tools.stopwatch_click("submodule", "Track Library init complete")


def length_to_model_straight(length, direction, gradelevel):

    if direction == "4lt":
        direction = "4rt"

    return track_straight_cache.get(f"{length}|{direction}", {}).get(gradelevel, "")


def add_lines_from_track(pos, track_object, heading):

    EndPos = pos + tools.rot_orth(track_object["Move"], heading)

    lines.write_bezier_points(
        pos,
        EndPos,
        tools.rot_orth(get_heading(track_object["StartDirection"]), heading),
        tools.rot_orth(get_heading(track_object["EndDirection"]), heading + 180),
    )


def write_track(model, pos, yaw):

    add_lines_from_track(pos, track_model_library[model], yaw)

    vmfpy.add_entity(
        {
            "pos": pos,
            "mdl": model,
            "ang": (0, yaw, 0),
            "visgroup": "23",
        }
    )


def updated_position(position, jump, heading):

    return np.round(np.add(position, tools.rot_orth(jump, heading)))


def move_in_trackspace(length_forward, direction, tracks_over_right=0):

    if direction == "1rt":
        return (
            -length_forward + tracks_over_right * 48,
            length_forward * 0.25 + tracks_over_right * 192,
            0,
        )
    if direction == "2rt":
        return (
            -length_forward + tracks_over_right * 96,
            length_forward * 0.5 + tracks_over_right * 192,
            0,
        )
    if direction == "4rt":
        return (
            -length_forward + tracks_over_right * 144,
            length_forward + tracks_over_right * 144,
            0,
        )
    if direction == "6rt":
        return (
            -length_forward * 0.5 + tracks_over_right * 192,
            length_forward + tracks_over_right * 96,
            0,
        )
    if direction == "8rt":
        return (tracks_over_right * 192, length_forward, 0)
    if direction == "1lt":
        return (
            -length_forward - tracks_over_right * 48,
            -length_forward * 0.25 + tracks_over_right * 192,
            0,
        )
    if direction == "2lt":
        return (
            -length_forward - tracks_over_right * 96,
            -length_forward * 0.5 + tracks_over_right * 192,
            0,
        )
    if direction == "4lt":
        return (
            -length_forward - tracks_over_right * 144,
            -length_forward + tracks_over_right * 144,
            0,
        )
    if direction == "6lt":
        return (
            -length_forward * 0.5 - tracks_over_right * 192,
            -length_forward + tracks_over_right * 96,
            0,
        )
    if direction == "8lt":
        return (-tracks_over_right * 192, -length_forward, 0)

    # 0fw
    return (-length_forward, tracks_over_right * 192, 0)


def get_end_direction(model, current_direction):

    track_data = track_model_library[model]
    start_direction = track_data["StartDirection"]
    end_direction = track_data["EndDirection"]

    # Exact end wins over the 45° hand swap. Otherwise a 4lt→4rt piece
    # cannot tell "entered at the 4rt end" from "entered at the 4lt start".
    if current_direction == start_direction:
        return end_direction
    if current_direction == end_direction and start_direction != end_direction:
        return start_direction
    if start_direction[:1] == "4" and current_direction[:1] == "4":
        return end_direction
    if end_direction[:1] == "4" and current_direction[:1] == "4":
        return start_direction
    return start_direction


def get_new_node_from_node_and_model(
    Model, Node, ReverseStraight=False, AddStart=0, AddEnd=0
):

    Position, current_direction, Heading, _ = Node  # I don't even use it here what
    # EDITORS NOTE THE 4th SLOT IS FOR MODEL REVERSING (does not effect the jump, only rotation of the model)

    track_data = track_model_library[Model]

    NewDirection = get_end_direction(Model, current_direction)

    # Hand of the authored direction we are entering through. On a reversed
    # piece that is the end, not the start — using the start hand there leaves
    # a 45° diagonal yawed 90° off the node. An exact match beats the 4lt/4rt
    # swap, so a piece that really ends on 4rt is not treated as starting on 4lt.
    if current_direction == track_data["StartDirection"] or (
        track_data["StartDirection"][:1] == "4"
        and current_direction[:1] == "4"
        and current_direction != track_data["EndDirection"]
    ):
        entry_direction = track_data["StartDirection"]
    else:
        entry_direction = track_data["EndDirection"]
    NewHand = entry_direction[1:] if entry_direction[1:] != "fw" else ""
    OldHand = current_direction[1:]

    IsReversed = (
        NewDirection != track_data["EndDirection"]
        and track_data["EndDirection"][:1] != "8"
    ) or (
        track_data["EndDirection"] == track_data["StartDirection"]
        and ReverseStraight != False
    )

    move_x, move_y, move_z = track_data["Move"]

    if IsReversed:
        final_move = (move_x, move_y, -move_z)
        additional_move = np.add(
            move_in_trackspace(AddStart, track_data["EndDirection"]),
            move_in_trackspace(AddEnd, track_data["StartDirection"]),
        )
    else:
        final_move = (move_x, move_y, move_z)
        # Filler lengths are solved in the model's own directions. On a 45°
        # hand change the node direction is the other diagonal (4rt vs 4lt);
        # rotating the model's direction by the adjusted heading is what lines
        # up with that node, not the node's direction string at the new yaw.
        additional_move = np.add(
            move_in_trackspace(AddStart, track_data["StartDirection"]),
            move_in_trackspace(AddEnd, track_data["EndDirection"]),
        )

    final_move = np.add(final_move, additional_move)

    NewHeading = Heading
    if current_direction[:1] == "4" and (NewHand != OldHand):
        # if old hand is lt and
        if NewHand == "rt":
            NewHeading = Heading + 90
        # if old hand is rt and
        elif NewHand == "lt":
            NewHeading = Heading - 90
        # else, if 0fw, do nothing (as the heading has not changed)

    NewPosition = updated_position(Position, final_move, NewHeading)

    # 90° pieces swing the outgoing heading. Apply that on top of any 45°
    # hand change already stored in NewHeading; using the original Heading
    # here drops the hand change and points the next piece the wrong way.
    if NewDirection == "8rt":
        NewHeading = NewHeading - 90
    elif NewDirection == "8lt":
        NewHeading = NewHeading + 90

    if NewDirection[:1] == "8":
        NewDirection = "0fw"

    return NewPosition, NewDirection, NewHeading, IsReversed


def create_straight(StartPosition, Distance, Direction, Heading):

    if Distance < 0:

        print(StartPosition, Distance, Direction, Heading)
        raise ValueError()

    elif Distance > 0:

        # for each
        lengths = decompose_length_to_straights(Distance)
        total = 0

        for length in lengths:
            move = move_in_trackspace(total, Direction)
            final_position = updated_position(StartPosition, move, Heading)
            total += length
            write_track(
                convert_length_to_mdl(length, Direction),
                final_position,
                Heading,
            )


def _model_yaw(track_data, is_reversed, new_heading):

    # Heading stored on the outgoing node is the heading AFTER a 90° exit
    # swing. The model itself is still in the pre-swing frame. Recover that
    # frame from whichever authored direction we actually left through.
    outgoing = (
        track_data["StartDirection"] if is_reversed else track_data["EndDirection"]
    )
    if outgoing == "8lt":
        heading = new_heading - 90
    elif outgoing == "8rt":
        heading = new_heading + 90
    else:
        heading = new_heading
    if is_reversed:
        heading += 180
    return heading


def _parallel_fillers(direction_in, direction_out, mode):

    left, right = mode
    if (left + right) <= 0:
        return {0: (0, 0)}

    per_in, per_out = get_offset_forward_for_parallel_on_right(
        direction_in, direction_out
    )
    push_in, push_out = get_addlength(direction_in, direction_out, mode)
    return {
        track: (push_in + per_in * track, push_out + per_out * track)
        for track in range(-int(left), int(right) + 1)
    }


def write_track_from_trackhammer_steps(steps):

    prev_node = None
    prev_run = None

    for step in steps:

        model = step["model"]
        new_node = step["node"]

        # (array([-15232.,  -3664., -12556.]), '1rt', 90, True)
        # models/trakpak3_rsg/arcs/r4096/a1rt_2rt_right_-328pg_+1024x+0384x-036dn.mdl'

        if model == "":
            prev_node = new_node
            prev_run = step["current_run"]
            continue

        # This model was spaced with the run we were still in when it was
        # chosen (the previous step). The node we just arrived on may already
        # be the next run, which is the far end of a parallel section.
        track_mode = prev_run[0]
        track_data = track_model_library[model]
        is_reversed = new_node[3]

        if is_reversed:
            along_in = track_data["EndDirection"]
            along_out = track_data["StartDirection"]
        else:
            along_in = track_data["StartDirection"]
            along_out = track_data["EndDirection"]

        d_in, h_in = prev_node[1], prev_node[2]
        d_out, h_out = new_node[1], new_node[2]
        origin = prev_node[0]
        destination = new_node[0]
        yaw = _model_yaw(track_data, is_reversed, new_node[2])

        for track, (fore, rear) in _parallel_fillers(
            along_in, along_out, track_mode
        ).items():

            fore = int(fore)
            rear = int(rear)
            entrance = updated_position(
                origin, move_in_trackspace(0, d_in, track), h_in
            )

            if is_reversed:
                # Reversed props sit on the exit end of the mesh and point
                # back down the piece, so the exit filler is the shift from
                # this node and the entrance filler runs forward to the mesh.
                model_pos = updated_position(
                    destination, move_in_trackspace(-rear, d_out, track), h_out
                )
                exit_origin = model_pos
            else:
                model_pos = updated_position(
                    origin, move_in_trackspace(fore, d_in, track), h_in
                )
                exit_origin = np.add(model_pos, tools.rot_orth(track_data["Move"], yaw))

            write_track(model, model_pos, yaw)
            if fore > 0:
                create_straight(entrance, fore, d_in, h_in)
            if rear > 0:
                create_straight(exit_origin, rear, d_out, h_out)

        prev_node = new_node
        prev_run = step["current_run"]


def valid_next_tracks(Direction, params={}):

    MinimumRadiusLevel = params.get("min_radius", 0)
    MinimumGradeLevel = params.get("min_grade", False)
    MaximumGradeLevel = params.get("max_grade", False)

    global valid_tracks_cache

    Index = (
        Direction
        + str(MinimumRadiusLevel)
        + str(MinimumGradeLevel)
        + str(MaximumGradeLevel)
    )

    if valid_tracks_cache.get(Index, []):

        return valid_tracks_cache[Index]

    Output = []

    Radii = [2048, 3072, 4096, 6144, 8192, 0]

    AllowedRadii = Radii[MinimumRadiusLevel:]

    for Track in list(track_model_library.items()):

        if Track[1]["StartDirection"] != Direction or (
            Direction[:1] == "4" and Track[1]["StartDirection"][:1] == "4"
        ):
            Reversed = -1
        else:
            Reversed = 1

        if (
            MinimumGradeLevel != False
            and (Track[1]["GradeLevel"] * Reversed) < MinimumGradeLevel
        ):
            continue
        if (
            MaximumGradeLevel != False
            and (Track[1]["GradeLevel"] * Reversed) > MaximumGradeLevel
        ):
            continue

        if Track[1]["Radius"] not in AllowedRadii:
            continue

        if (
            Track[1]["StartDirection"] != Direction
            and Track[1]["EndDirection"] != Direction
            and not (
                (Direction[:1] == "4")
                and (
                    Track[1]["StartDirection"][:1] == "4"
                    or Track[1]["EndDirection"][:1] == "4"
                )
            )
        ):

            continue

        to_add = [Track, Track[1]["Length"]]

        tools.heuristic_inserter(Output, to_add)

    Output2 = [item[0][0] for item in Output]
    valid_tracks_cache[Index] = Output2

    return Output2


def get_length(model):

    return track_model_library[model]["Length"]


def decompose_length_to_straights(target):

    if target in straight_decomposition_cache:
        output = straight_decomposition_cache[target]
        random.shuffle(output)
        return output

    print("processing", target)

    def create_new_card(current_state, new_piece, target):
        """Create a new state with the given piece added."""
        new_total = current_state[0] + new_piece
        new_pieces = current_state[1] + [new_piece]
        heuristic = new_total if new_total <= target else 0
        return (new_total, new_pieces), heuristic

    if target % 16 != 0:
        print(f"Not divisible! length: {target}")
        return []

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

            tools.heuristic_inserter(cards, new_card)

    if cards:

        straight_decomposition_cache[target] = cards[0][0][1]
        random.shuffle(cards[0][0][1])
        return cards[0][0][1]

    else:
        print(f"Invalid decomposition length: {target}")
        return []


def convert_length_to_mdl(length, direction):

    if direction == "8lt":
        direction = "0fw"
    elif direction == "8rt":
        direction = "0fw"
    extra = "0" * (4 - len(str(length)))
    over = int(move_in_trackspace(length, direction)[1])
    minus = "-" if over < 0 else "+"
    extra2 = "0" * (4 - len(str(abs(over))))
    if over == 0:
        minus = "0"

    return f"models/trakpak3_rsg/straights/s{extra}{length}_{direction}_0pg_+{extra}{length}x{minus}{extra2}{abs(over)}x0000.mdl"


def _direction_axes(direction):

    # (forward per length-unit, one track to the right), both in heading-0 space.
    forward = move_in_trackspace(1, direction, 0)
    right = move_in_trackspace(0, direction, 1)
    return (float(forward[0]), float(forward[1])), (float(right[0]), float(right[1]))


def get_offset_forward_for_parallel_on_right(start_direction, end_direction):

    # Longitudinal stagger, in length-units, of one track to the right of main.
    # Same curve model on every track: shift it along the entry tangent and
    # make the exit gap up with a straight. a * fwd(start) + b * fwd(end)
    # = right(end) - right(start). Arguments are the travel directions, in
    # travel order — not sorted by angle number.
    if start_direction == end_direction:
        return 0, 0

    fwd_s, right_s = _direction_axes(start_direction)
    fwd_e, right_e = _direction_axes(end_direction)
    rhs_x = right_e[0] - right_s[0]
    rhs_y = right_e[1] - right_s[1]
    det = fwd_s[0] * fwd_e[1] - fwd_s[1] * fwd_e[0]
    if abs(det) < 1e-8:
        # Tangents are parallel: a straight, or a 180° pair such as 8rt→8lt.
        # Straight fillers cannot close a lateral change along one tangent.
        return 0, 0

    along_start = (rhs_x * fwd_e[1] - rhs_y * fwd_e[0]) / det
    along_end = (fwd_s[0] * rhs_y - fwd_s[1] * rhs_x) / det
    return int(round(along_start)), int(round(along_end))


def get_addlength(start_direction, end_direction, mode):

    tracks_left = mode[0]
    tracks_right = mode[1]

    if (tracks_left + tracks_right) <= 0:
        return 0, 0

    per_start, per_end = get_offset_forward_for_parallel_on_right(
        start_direction, end_direction
    )

    # Push main forward until the track that hangs back the furthest still
    # has a non-negative filler. Left of main is a negative track index.
    start_push = -min(0, tracks_right * per_start, -tracks_left * per_start)
    end_push = -min(0, tracks_right * per_end, -tracks_left * per_end)

    return start_push, end_push
