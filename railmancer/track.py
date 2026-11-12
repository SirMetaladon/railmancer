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

    # Any 4 chains with any other 4 (same diagonal, yaw differs by 90).
    # 1lt is not 1rt, and 2lt is not 2rt — those are mirror curves, so an
    # exact end has to win or the segment gap is computed for the wrong end.
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

    # Hand of the authored end we are actually entering. On a reverse entry
    # that is the piece's end (including the other 45° diagonal). Using the
    # start hand there yaws the joint 90° off the previous segment.
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
        additional_move = np.add(
            move_in_trackspace(AddStart, current_direction),
            move_in_trackspace(AddEnd, NewDirection),
        )

    NewHeading = Heading
    if current_direction[:1] == "4" and (NewHand != OldHand):
        # if old hand is lt and
        if NewHand == "rt":
            NewHeading = Heading + 90
        # if old hand is rt and
        elif NewHand == "lt":
            NewHeading = Heading - 90
        # else, if 0fw, do nothing (as the heading has not changed)

    if IsReversed or NewHeading == Heading:
        final_move = np.add(final_move, additional_move)
        NewPosition = updated_position(Position, final_move, NewHeading)
    else:
        # 45° hand change: the entrance filler stays in the incoming frame so
        # it meets the previous segment. The mesh and the exit filler use the
        # turned heading.
        entrance_move = move_in_trackspace(AddStart, current_direction)
        exit_move = move_in_trackspace(AddEnd, NewDirection)
        NewPosition = updated_position(Position, entrance_move, Heading)
        NewPosition = updated_position(NewPosition, final_move, NewHeading)
        NewPosition = updated_position(NewPosition, exit_move, NewHeading)

    # 90° exit, applied on top of any 45° hand change already in NewHeading.
    # Using the original Heading here drops that hand change, so the next
    # segment's sideways step is 90° off this one.
    if NewDirection == "8rt":
        NewHeading = NewHeading - 90
    elif NewDirection == "8lt":
        NewHeading = NewHeading + 90

    if NewDirection[:1] == "8":
        NewDirection = "0fw"

    return NewPosition, NewDirection, NewHeading, IsReversed


def straight_prop_yaw(direction, heading):

    # There is no 4rt straight; it would duplicate 4lt. Working in 4rt
    # track space means the 4lt prop, turned 90° so its mesh follows the
    # 4rt step. Origins are still stepped in 4rt space at `heading`.
    if direction == "4rt":
        return heading - 90
    return heading


def _as_track_length(distance):

    # Straights exist only on the 16-unit grid. A negative length means the
    # filler was measured backwards; that is a placement bug, not a piece.
    value = float(distance)
    nearest = int(round(value))
    if abs(value - nearest) > 1e-6:
        print(distance)
        raise ValueError(f"track length {distance} is not a whole number")
    if nearest < 0:
        print(nearest)
        raise ValueError(f"track length {nearest} is negative")
    if nearest % 16 != 0:
        print(nearest)
        raise ValueError(f"track length {nearest} is not a multiple of 16")
    return nearest


def create_straight(StartPosition, Distance, Direction, Heading):

    Distance = _as_track_length(Distance)

    if Distance > 0:

        # for each
        lengths = decompose_length_to_straights(Distance)
        total = 0
        prop_yaw = straight_prop_yaw(Direction, Heading)

        for length in lengths:
            move = move_in_trackspace(total, Direction)
            final_position = updated_position(StartPosition, move, Heading)
            total += length
            write_track(
                convert_length_to_mdl(length, Direction),
                final_position,
                prop_yaw,
            )


def _travel_stagger(direction_in, direction_out):

    # Same low-to-high table as get_addlength, expressed along this traversal.
    along_low, along_high = get_offset_forward_for_parallel_on_right(
        direction_in, direction_out
    )
    if int(direction_in[0]) > int(direction_out[0]):
        return -along_high, -along_low
    return along_low, along_high


def _place_reversed_piece(model, prev_node, new_node, yaw, track_mode):

    track_data = track_model_library[model]
    per_in, per_out = _travel_stagger(
        track_data["EndDirection"], track_data["StartDirection"]
    )
    left, right = track_mode
    indices = list(range(-int(left), int(right) + 1))
    push_in = -min([0] + [per_in * track for track in indices])
    push_out = -min([0] + [per_out * track for track in indices])
    mesh = track_data["Move"]
    h_in, h_out = prev_node[2], new_node[2]
    d_in, d_out = prev_node[1], new_node[1]

    for track in indices:
        gap_in = int(push_in + per_in * track)
        gap_out = int(push_out + per_out * track)
        entrance = updated_position(
            prev_node[0], move_in_trackspace(0, d_in, track), h_in
        )
        mesh_end = updated_position(entrance, move_in_trackspace(gap_in, d_in), h_in)
        model_pos = np.subtract(mesh_end, tools.rot_orth(mesh, yaw))
        write_track(model, model_pos, yaw)
        if gap_in > 0:
            create_straight(entrance, gap_in, d_in, h_in)
        if gap_out > 0:
            create_straight(model_pos, gap_out, d_out, h_out)


def write_track_from_trackhammer_steps(steps):

    prev_node = ["", "0fw"]
    prev_run = None

    for step in steps:

        model = step["model"]
        new_node = step["node"]

        # (array([-15232.,  -3664., -12556.]), '1rt', 90, True)
        # models/trakpak3_rsg/arcs/r4096/a1rt_2rt_right_-328pg_+1024x+0384x-036dn.mdl'

        if step.get("tangent_fill"):
            run_mode = prev_run[0] if prev_run else (0, 0)
            for track_index in range(-int(run_mode[0]), int(run_mode[1]) + 1):
                create_straight(
                    updated_position(
                        prev_node[0],
                        move_in_trackspace(0, prev_node[1], track_index),
                        prev_node[2],
                    ),
                    step["tangent_fill"],
                    prev_node[1],
                    prev_node[2],
                )
            prev_node = new_node
            prev_run = step["current_run"]
            continue

        if step.get("switch_zone"):
            from railmancer import switches

            before, after = step["switch_zone"]
            switches.place_transition(
                prev_node[0],
                prev_node[1],
                prev_node[2],
                before,
                after,
            )
            prev_node = new_node
            prev_run = step["current_run"]
            continue

        if model == "":
            prev_node = new_node
            prev_run = step["current_run"]
            continue

        IsReversed = new_node[3]  # if it's reversed AHA IT DOES DO SOMETHING

        if IsReversed:
            base_pos_of_section = new_node[0]
            RotFix = 180
            Direction = new_node[1]
            base_of_far_side = prev_node[0]
            far_direction = prev_node[1]
        else:
            base_pos_of_section = prev_node[0]
            RotFix = 0
            Direction = prev_node[1]
            far_direction = new_node[1]
            base_of_far_side = new_node[0]

        TrackEndDirection = track_model_library[model]["EndDirection"]

        # Whichever authored direction we leave through, if it is an 8 the
        # stored heading already includes that ±90. The prop is drawn in the
        # frame before the turn. Undo it, then add 180 when the prop is reversed.
        outgoing = (
            track_model_library[model]["StartDirection"]
            if IsReversed
            else TrackEndDirection
        )
        if outgoing == "8rt":
            ModelHeading = new_node[2] + 90
        elif outgoing == "8lt":
            ModelHeading = new_node[2] - 90
        else:
            ModelHeading = new_node[2]

        Heading = int(ModelHeading) + RotFix

        forward_per_track, rear_per_track = get_offset_forward_for_parallel_on_right(
            track_model_library[model]["StartDirection"], TrackEndDirection
        )
        # The table is stored low-angle to high-angle. A piece authored the
        # other way (and not model-reversed) has to put that stagger on the
        # opposite end, or it will not meet the segment on either side.
        if not IsReversed and int(
            track_model_library[model]["StartDirection"][0]
        ) > int(TrackEndDirection[0]):
            forward_per_track, rear_per_track = (
                -rear_per_track,
                -forward_per_track,
            )

        # This piece was spaced while we were still in the previous step's
        # run. The step we just arrived on may already be the next run.
        track_mode = prev_run[0] if prev_run else (0, 0)
        # tuple like (1,3), which means 1 track to left, 3 tracks to right for a total of 5 including main

        tracks = tools.tuple_to_range_list(track_mode, IsReversed)

        farthest_back = min(
            tracks[0] * forward_per_track, tracks[-1] * forward_per_track
        )

        # A reversed prop is yawed 180° and its step-over index is mirrored.
        # That lines the copy up with the previous segment only when both
        # ends share a heading. Place every reversed piece from the incoming
        # joint instead, so the straights meet the segment on either side.
        if IsReversed:
            _place_reversed_piece(
                model,
                prev_node,
                new_node,
                Heading,
                track_mode,
            )
            prev_node = new_node
            prev_run = step["current_run"]
            continue

        # Forward piece. Curves sit in the incoming frame so a 45° hand
        # change does not swing the entrance step off the previous segment.
        # Assembly order: center and parallel curves, shim at the start node,
        # then the exit shim unless it is zero.
        step_heading = prev_node[2]
        join_heading = new_node[2]
        farthest_rear_back = min(
            tracks[0] * rear_per_track, tracks[-1] * rear_per_track
        )
        piece = track_model_library[model]

        for track in tracks:

            fore_aft = -farthest_back + forward_per_track * track
            rear = -farthest_rear_back + rear_per_track * track

            final_move = move_in_trackspace(fore_aft, Direction, track)
            curve_pos = updated_position(base_pos_of_section, final_move, step_heading)
            write_track(model, curve_pos, Heading)

            if fore_aft > 0:
                station = updated_position(
                    base_pos_of_section,
                    move_in_trackspace(0, Direction, track),
                    step_heading,
                )
                create_straight(station, fore_aft, Direction, step_heading)

            if rear > 0:
                curve_end = np.add(curve_pos, tools.rot_orth(piece["Move"], Heading))
                create_straight(curve_end, rear, far_direction, join_heading)

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

    # 8lt/8rt straights are 0fw props; the heading carries the corner.
    # 4rt is the 4lt prop (see straight_prop_yaw). The filename has to be
    # the real 4lt piece, whose Y step is the opposite of 4rt's.
    if direction == "8lt" or direction == "8rt":
        direction = "0fw"
    elif direction == "4rt":
        direction = "4lt"
    extra = "0" * (4 - len(str(length)))
    over = int(move_in_trackspace(length, direction)[1])
    minus = "-" if over < 0 else "+"
    extra2 = "0" * (4 - len(str(abs(over))))
    if over == 0:
        minus = "0"

    return f"models/trakpak3_rsg/straights/s{extra}{length}_{direction}_0pg_+{extra}{length}x{minus}{extra2}{abs(over)}x0000.mdl"


def get_offset_forward_for_parallel_on_right(start_direction, end_direction):

    if start_direction == end_direction:

        return 0, 0

    if start_direction[0] == end_direction[0]:

        # Same angle number, other hand (1lt↔1rt, 4lt↔4rt, 8lt↔8rt).
        # Not the same direction, so the sideways step changes. Snap that
        # stagger onto the 16-unit grid. For 8lt↔8rt the nearest value is 0.
        return _grid_stagger(start_direction, end_direction)

    first_direction, second_direction = (
        (start_direction, end_direction)
        if int(end_direction[0]) > int(start_direction[0])
        else (end_direction, start_direction)
    )

    handedness_mult = -1 if second_direction[1] == "r" else 1

    # The table assumes one hand for the whole turn (or a start at 0fw).
    # A mirror pair such as 1lt→4rt is a different stagger; snap that instead.
    first_hand = "" if first_direction == "0fw" else first_direction[1:]
    second_hand = "" if second_direction == "0fw" else second_direction[1:]
    if first_hand and second_hand and first_hand != second_hand:
        return _grid_stagger(first_direction, second_direction)

    if first_direction == "0fw":

        if second_direction[0] == "1":
            return 48 * handedness_mult, 0
        elif second_direction[0] == "2":
            return 96 * handedness_mult, 0
        elif second_direction[0] == "4":
            return (
                96 * handedness_mult,
                48 * handedness_mult,
            )

        elif second_direction[0] == "8":
            return (
                192 * handedness_mult,
                192 * handedness_mult,
            )

    elif first_direction[0] == "1":

        if second_direction[0] == "2":
            return (
                96 * handedness_mult,
                -48 * handedness_mult,  # apparently that IS reversed
            )
        elif second_direction[0] == "4":
            return (64 * handedness_mult, 32 * handedness_mult)

    elif first_direction[0] == "2":

        if second_direction[0] == "4":
            return 0, 48 * handedness_mult

    # Not in the hand-tuned table. Snap the same stagger equation onto the
    # 16-unit grid the props have to sit on. Close is enough; it will not be exact.
    return _grid_stagger(first_direction, second_direction)


def _snap_track_grid(value):

    return int(round(float(value) / 16.0) * 16)


def _grid_stagger(start_direction, end_direction):

    # (along start, along end) for one track to the right. Directions are
    # already in the table's low-angle, high-angle order.
    forward_start = move_in_trackspace(1, start_direction, 0)
    forward_end = move_in_trackspace(1, end_direction, 0)
    right_start = move_in_trackspace(0, start_direction, 1)
    right_end = move_in_trackspace(0, end_direction, 1)
    rhs_x = float(right_end[0] - right_start[0])
    rhs_y = float(right_end[1] - right_start[1])
    start_x, start_y = float(forward_start[0]), float(forward_start[1])
    end_x, end_y = float(forward_end[0]), float(forward_end[1])
    determinant = start_x * end_y - start_y * end_x
    if abs(determinant) < 1e-8:
        # Opposite orthogonals (8lt↔8rt): both tangents run the same way,
        # so a straight filler cannot cancel the side step. Nearest grid is 0.
        return 0, 0
    along_start = (rhs_x * end_y - rhs_y * end_x) / determinant
    along_end = (start_x * rhs_y - start_y * rhs_x) / determinant
    return _snap_track_grid(along_start), _snap_track_grid(along_end)


def get_addlength(start_direction, end_direction, mode):

    tracks_left = mode[0]
    tracks_right = mode[1]

    if (tracks_left + tracks_right) <= 0:
        return 0, 0

    per_righthand_blue_base, per_righthand_green_end = (
        get_offset_forward_for_parallel_on_right(start_direction, end_direction)
    )

    is_reversed = int(start_direction[0]) > int(end_direction[0])

    # since, if reversed, left becomes right; the values flip with track number
    first_offset_relative_to_main = (
        per_righthand_blue_base if not is_reversed else -per_righthand_green_end
    )
    second_offset_relative_to_main = (
        per_righthand_green_end if not is_reversed else -per_righthand_blue_base
    )

    first_offset_push_forward = -min(
        0,
        tracks_right * first_offset_relative_to_main,
        -tracks_left * first_offset_relative_to_main,
    )

    second_offset_push_forward = -min(
        0,
        tracks_right * second_offset_relative_to_main,
        -tracks_left * second_offset_relative_to_main,
    )

    return first_offset_push_forward, second_offset_push_forward
