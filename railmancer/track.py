import os, math, re
import numpy as np
from railmancer import lines, vmfpy, tools

# Contains everything to do with the Track Library, which is a dictionary of conversions between modelpaths and physical dimensions / extracted information.


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
        return (-4, 0)
    elif raw_direction == "1rt":
        return (-4, 1)
    elif raw_direction == "1lt":
        return (-4, -1)
    elif raw_direction == "2rt":
        return (-4, 2)
    elif raw_direction == "2lt":
        return (-4, -2)

    elif raw_direction == "4rt":
        return (-4, 4)
    elif raw_direction == "4lt":
        return (-4, -4)
    elif raw_direction == "8rt":
        return (0, 4)
    elif raw_direction == "8lt":
        return (0, -4)

    elif raw_direction == "6rt":
        return (-2, 4)
    elif raw_direction == "6lt":
        return (2, -4)
    elif raw_direction == "7rt":
        return (-1, 4)
    elif raw_direction == "7lt":
        return (1, -4)
    else:
        print(raw_direction)


def direction_to_angle(Direction):

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

    try:
        track_straight_cache
    except:
        track_straight_cache = {}

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

    # print(f"No support for {model}")

    return []


def build_track_library(directory, extension):

    global track_model_library

    track_model_library = {}

    for root, dirs, files in os.walk(directory):
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


def length_to_model_straight(length, direction, gradelevel):

    if direction == "4lt":
        direction = "4rt"

    return track_straight_cache.get(f"{length}|{direction}", {}).get(gradelevel, "")


def add_track(pos, track_object, heading):

    EndPos = pos + tools.rot_z(track_object["Move"], heading)

    lines.write_bezier_points(
        pos,
        EndPos,
        tools.rot_z(get_heading(track_object["StartDirection"]), heading),
        tools.rot_z(get_heading(track_object["EndDirection"]), heading + 180),
    )


def write_track(
    model,
    prev_node,
    new_node,
):

    track_data = track_model_library[model]

    if new_node[3]:  # if it's reversed
        ModelPos = new_node[0]
        RotFix = 180
    else:
        ModelPos = prev_node[0]
        RotFix = 0

    ModelHeading = (
        new_node[2] if track_data["EndDirection"][:1] != "8" else prev_node[2]
    )

    add_track(ModelPos, track_data, ModelHeading + RotFix)

    vmfpy.add_entity(
        {
            "pos-x": ModelPos[0],
            "pos-y": ModelPos[1],
            "pos-z": ModelPos[2],
            "mdl": model,
            "ang-yaw": ModelHeading + RotFix,
            "visgroup": "23",
        }
    )


def updated_position(position, jump, heading):

    return np.round(np.add(position, tools.rot_z(jump, heading)))


"""
def add_connector(pathnode):

    import numpy as np

    if pathnode[1] == "0fw":

        new_pos = updated_position(pathnode[0], [-64, 0, 0], pathnode[2])

        write_track(
            np.array(pathnode[0]),
            "0fw",
            length_to_model_straight(64, "0fw", 0),
            pathnode[2],
            pathnode[2],
        )

        pathnode[0] = new_pos"""


def append_track(Model, Node, ReverseStraight=False):

    Position, Direction, Heading, _ = Node

    track_data = track_model_library[Model]

    NewDirection = (
        track_data["StartDirection"]
        if track_data["StartDirection"][:1] != Direction[:1]
        else track_data["EndDirection"]
    )

    # this will use the new heading rotation if it's a 45, and the old one if it's a 90
    NewHand = (
        track_data["StartDirection"][1:]
        if track_data["StartDirection"][1:] != "fw"
        else track_data["EndDirection"][1:]
    )
    OldHand = Direction[1:]

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
    else:
        final_move = (move_x, move_y, move_z)

    NewHeading = Heading
    if Direction[:1] == "4" and (NewHand != OldHand):
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


def write_pathfinder_data(model_list, start_node):

    prev_node = start_node

    for model in model_list:

        new_node = append_track(model, prev_node)

        # finalize track placement
        write_track(model, prev_node, new_node)

        prev_node = new_node


def valid_next_tracks(Direction, MinimumRadiusLevel):

    global valid_tracks_cache

    try:
        valid_tracks_cache
    except:
        valid_tracks_cache = {}

    Index = Direction + str(MinimumRadiusLevel)

    if valid_tracks_cache.get(Index, []):

        return valid_tracks_cache[Index]

    Output = []

    Radii = [2048, 3072, 4096, 6144, 8192, 0]

    AllowedRadii = Radii[MinimumRadiusLevel:]

    for Track in list(track_model_library.items()):

        if Track[1]["GradeLevel"] < 2:
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

    Output = [item[0] for item in Output]
    valid_tracks_cache[Index] = Output

    return Output
