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

    StartAngle = direction_to_angle(StartDirection)
    EndAngle = direction_to_angle(EndDirection)

    Degrees = abs(EndAngle - StartAngle)

    Length = round(Radius * math.pi * Degrees / 180, 2)

    if Length == 0:
        print(StartDirection, EndDirection, Radius)

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


def convert_model_nodes_to_real_pos_and_angle(
    model,
    prev_node,
    new_node,
    shift,
):

    if new_node[3]:  # if it's reversed AHA IT DOES DO SOMETHING
        ModelPos = new_node[0]
        RotFix = 180
    else:
        ModelPos = prev_node[0]
        RotFix = 0

    ModelHeading = (
        new_node[2]
        if track_model_library[model]["EndDirection"][:1] != "8"
        else prev_node[2]
    )

    Angle = ModelHeading + RotFix
    ModelPos = tools.add(ModelPos, shift)

    return ModelPos, Angle


def write_track(model, ModelPos, Angle):

    add_lines_from_track(ModelPos, track_model_library[model], Angle)

    vmfpy.add_entity(
        {
            "pos-x": ModelPos[0],
            "pos-y": ModelPos[1],
            "pos-z": ModelPos[2],
            "mdl": model,
            "ang-yaw": Angle,
            "visgroup": "23",
        }
    )


def updated_position(position, jump, heading):

    return np.round(np.add(position, tools.rot_orth(jump, heading)))


def straight_convert_to_move(length, direction):

    if direction == "1rt":
        return (-length, length * 0.25, 0)
    if direction == "2rt":
        return (-length, length * 0.5, 0)
    if direction == "4rt":
        return (-length, length, 0)
    if direction == "6rt":
        return (-length * 0.5, length, 0)
    if direction == "8rt":
        return (0, length, 0)
    if direction == "1lt":
        return (-length, -length * 0.25, 0)
    if direction == "2lt":
        return (-length, -length * 0.5, 0)
    if direction == "4lt":
        return (-length, -length, 0)
    if direction == "6lt":
        return (-length * 0.5, -length, 0)
    if direction == "8lt":
        return (0, -length, 0)

    # 0fw
    return (-length, 0, 0)


def get_end_direction(model, current_direction):

    track_data = track_model_library[model]

    return (
        track_data["StartDirection"]
        if track_data["StartDirection"][:1] != current_direction[:1]
        else track_data["EndDirection"]
    )


def get_new_node_from_node_and_model(
    Model, Node, ReverseStraight=False, AddStart=0, AddEnd=0
):

    Position, current_direction, Heading, _ = Node  # I don't even use it here what
    # EDITORS NOTE THE 4th SLOT IS FOR MODEL REVERSING (does not effect the jump, only rotation of the model)

    track_data = track_model_library[Model]

    NewDirection = get_end_direction(Model, current_direction)

    # this will use the new heading rotation if it's a 45, and the old one if it's a 90
    NewHand = (
        track_data["StartDirection"][1:]
        if track_data["StartDirection"][1:] != "fw"
        else track_data["EndDirection"][1:]
    )
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
            straight_convert_to_move(AddStart, track_data["EndDirection"]),
            straight_convert_to_move(AddEnd, track_data["StartDirection"]),
        )
    else:
        final_move = (move_x, move_y, move_z)
        additional_move = np.add(
            straight_convert_to_move(AddStart, current_direction),
            straight_convert_to_move(AddEnd, NewDirection),
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

    # this mechanism does so for 90 degree angles

    if NewDirection == "8rt":
        NewHeading = Heading - 90
    elif NewDirection == "8lt":
        NewHeading = Heading + 90

    if NewDirection[:1] == "8":
        NewDirection = "0fw"

    return NewPosition, NewDirection, NewHeading, IsReversed


def write_track_from_trackhammer_steps(steps):

    for step in steps:

        for model in step["models"]:
            mdl, pos, yaw = model
            # finalize track placement
            write_track(mdl, pos, yaw)


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
    over = int(straight_convert_to_move(length, direction)[1])
    minus = "-" if over < 0 else "+"
    extra2 = "0" * (4 - len(str(abs(over))))
    if over == 0:
        minus = "0"
    if direction[0] == "4":
        direction = "4lt"
        minus = "-"

    return f"models/trakpak3_rsg/straights/s{extra}{length}_{direction}_0pg_+{extra}{length}x{minus}{extra2}{abs(over)}x0000.mdl"
