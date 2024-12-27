import importer, tools, random, bisect, time
import numpy as np


def matrix_hash(Position, Direction, Heading):

    return f"{round(Position[0])}|{round(Position[1])}|{round(Position[2])}|{Direction}|{round(Heading)}"


def write_track(Position, NextPosition, Direction, MDL, Heading):

    global Line, Entities

    data = Track_Library[MDL]

    Line += [[NextPosition, tools.rot_z(importer.get_heading(Direction), Heading)]]

    if Direction != data["EndDirection"] and data["EndDirection"][:1] != "8":
        ModelPos = NextPosition
        RotFix = 180
    else:
        ModelPos = Position
        RotFix = 0

    Entities += [
        {
            "pos-x": ModelPos[0],
            "pos-y": ModelPos[1],
            "pos-z": ModelPos[2],
            "mdl": MDL,
            "ang-yaw": Heading + RotFix,
        }
    ]


def append_track(Model, Position, Direction, Heading):

    Data = Track_Library[Model]

    NewDirection = (
        Data["StartDirection"]
        if Data["StartDirection"][:1] != Direction[:1]
        else Data["EndDirection"]
    )

    NewHeading = Heading
    # this var is only 1 if the heading has changed in a 45 degree movement
    Reorient = 0

    # this mechanism accounts for changing headings on a 45-degree angle
    NewHand = NewDirection[1:]
    OldHand = Direction[1:]

    if Direction[:1] == "4" and NewHand != OldHand:

        NewHeading = (Heading + 90) if NewHand == "rt" else (Heading - 90)
        Reorient = 1

    # this will use the new heading rotation if it's a 45, and the old one if it's a 90, as it should be
    NewPosition = np.round(np.add(Position, tools.rot_z(Data["Move"], NewHeading)))

    # this mechanism does so for 90 degree angles
    if NewDirection == "8rt":
        NewHeading = Heading - 90
    elif NewDirection == "8lt":
        NewHeading = Heading + 90

    return NewPosition, NewDirection, NewHeading, Reorient


def write_pathfinder_data(MDLList, StartPos, StartHeading):

    global Line, Entities

    Position = StartPos
    Direction = "0fw"
    Heading = StartHeading

    for Model in MDLList:

        NewPosition, NewDirection, NewHeading, Reorient = append_track(
            Model, Position, Direction, Heading
        )

        # finalize track placement
        Angle = Heading if Reorient == 0 else NewHeading
        write_track(Position, NewPosition, NewDirection, Model, Angle)

        if NewDirection[:1] == "8":
            NewDirection = "0fw"

        Position = NewPosition
        Heading = NewHeading
        Direction = NewDirection


def valid_next_tracks(Direction, MinimumRadiusLevel):

    global SavedDirections

    Index = Direction + str(MinimumRadiusLevel)

    if SavedDirections.get(Index, []):

        return SavedDirections[Index]

    Output = []

    Radii = [2048, 3072, 4096, 6144, 8192, 0]

    AllowedRadii = Radii[MinimumRadiusLevel:]

    for Track in list(Track_Library.items()):

        if Track[1]["GradeLevel"] != 0:
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

        Output += [Track]

    # random.shuffle(Output)

    SavedDirections[Index] = Output

    return Output


def new_position_valid(Position, Direction, Heading):

    Print = False

    if (
        PreExploredMatrix.get(matrix_hash(Position, Direction, Heading), False)
        or Heading != -90
    ):
        if Print:
            print(f"I've been here, or {Heading}")
        return False  # already explored here

    # if it meets the requirements
    """
    #rotating in a NEGATIVE direction is CLOCKWISE
    scenario: start heading is -90, end heading is 0 (pointing left, -x direction)
    position of start is x = 2040, y = -32, z = 208
    position of end is x = 0, y = 3072, z = 208

    position deflection is (0-2040,3072- (-32),208-208)
    (-2040,3104,0)
    from the perspective of the endpoint, the correct deflections are 2040 x, 3104 y
    #ok we need to clarify that NEGATIVE NUMBERS MEAN YOU HAVE GONE TOO FAR, for X at least
    #is the sign of Y relevant? Yes, because the angles are sensitive to it.

    if the end heading was 180, the coordinates would be -2040 x, -3104 y"""

    Head_Deflect = (EndPt[1] - Heading) % 90
    Pos_Deflect = np.round(tools.rot_z(EndPt[0] - Position, EndPt[1]))
    X_Deflect = Pos_Deflect[0]
    Y_Deflect = Pos_Deflect[1]

    # if Print:
    # print(f"Position {Position} and Deflection {Pos_Deflect}")

    # need some code here to determine what curvature level we're at right now and how to factor that in - don't think we're safe if the radius is higher

    Realignments = {
        0: {
            "0fw": [
                [704 * 2, 96 * 2, "abs", 1 / 4],
                [1056 * 2, 256 * 2, "abs", 1 / 2],
                [1568 * 2, 640 * 2, "abs", 1],
            ],
            "1rt": [[704, 96, "right", 1 / 4]],
            "1lt": [[704, 96, "left", 1 / 4]],
            "2rt": [[1056, 256, "right", 1 / 2]],
            "2lt": [[1056, 256, "left", 1 / 2]],
            "4rt": [[1568, 640, "right", 1]],
            "4lt": [[1568, 640, "left", 1]],
        }
    }

    if Head_Deflect == 0 and Direction == "0fw" and Y_Deflect == 0:
        # if you're straight on AND you've passed the actual end

        if Print:
            print(f"Straight on?")
        if X_Deflect < 0:
            if Print:
                print(f"Straight passby, apparently.")
            return False
        else:
            if Print:
                print(f"Good to go straight.")
            return True

    else:  # if not straight on

        # guilty until proven innocent
        for Option in Realignments[Head_Deflect][Direction]:

            # if Print:
            # print(f"Option chosen: {Option}")

            X_Remains = X_Deflect - Option[0]

            if X_Remains < 0:
                if Print:
                    print(f"too far ig")
                continue

            if Option[2] == "abs":

                Y_Remains = abs(Y_Deflect) - Option[1]
                if Print:
                    print(f"ABS: {Y_Remains}")

            elif Option[2] == "left":

                Y_Remains = Y_Deflect - Option[1]
                if Print:
                    print(f"Left: {Y_Remains}")

            elif Option[2] == "right":
                Y_Remains = -Y_Deflect - Option[1]
                if Print:
                    print(f"Right: {Y_Remains}")

            if X_Remains == 0 and Y_Remains == 0:
                if Print:
                    print(f"Exacto!")
                return True
            elif X_Remains == 0:
                if Print:
                    print(f"infinite slope")
                continue

            if (Y_Remains / X_Remains) < Option[3] and Y_Remains > 0:

                if Print:
                    print(
                        "correct",
                        Y_Deflect,
                        X_Deflect,
                        Option,
                        Y_Remains,
                        X_Remains,
                        (Y_Remains / X_Remains),
                    )
                return True

            else:

                if Print:
                    print(
                        "fail",
                        Y_Deflect,
                        X_Deflect,
                        Option,
                        Y_Remains,
                        X_Remains,
                        (Y_Remains / X_Remains),
                    )

    # if you didn't fnd a valid option
    if Print:
        print(f"No valid options.")
    return False


def recursive_track_explorer(PosIn, DirIn, HeadIn, SoFarIn):

    global PreExploredMatrix, SavedDirections

    PreExploredMatrix = dict()
    SavedDirections = dict()

    ToEvaluate = [(PosIn, DirIn, HeadIn, SoFarIn, 100000)]
    Ticker = 0

    while len(ToEvaluate) & Ticker < 1000000:

        Current = ToEvaluate.pop(0)
        # print(Current)
        Direction = Current[1]

        Ticker += 1

        if (
            # heading check
            Current[2] == EndPt[1]
            # position check
            and tools.is_same(Current[0], EndPt[0])
            # guarenteed end direction for now
            and Direction == "0fw"
        ):
            print("WINNAR", Current[3])
            return Current[3]

        Choices = valid_next_tracks(Direction, 1)

        for Track in Choices:

            Position = np.copy(Current[0])
            Direction = Current[1]
            Heading = Current[2]
            SoFar = Current[3].copy()
            Model = Track[0]

            NewPosition, NewDirection, NewHeading, Reorient = append_track(
                Model, Position, Direction, Heading
            )

            if NewDirection[:1] == "8":
                NewDirection = "0fw"

            if new_position_valid(NewPosition, NewDirection, NewHeading):

                LastRadius = Track_Library[Track[0]]["Radius"]
                if LastRadius == 0:
                    LastRadius = 10000

                LengthBias = np.linalg.norm(Position - NewPosition) * 0.01

                Score = min(Current[4], LastRadius) + (
                    LengthBias
                    if LastRadius == 10000
                    # a minor bias against curved pieces
                    else LengthBias * 0.8
                )

                PreExploredMatrix[
                    matrix_hash(NewPosition, NewDirection, NewHeading)
                ] = True

                bisect.insort(
                    ToEvaluate,
                    (NewPosition, NewDirection, NewHeading, SoFar + [Track[0]], Score),
                    key=lambda x: -x[4],
                )

        if len(ToEvaluate) == 0:
            print("orly")
            return Current[3]

    print(f"Pathfinder gave up after {Ticker} iterations!")

    return ToEvaluate[0][3] if len(ToEvaluate) > 0 else []


def solve(path):

    global Line, Entities, Track_Library, StartPt, EndPt
    Line = [[np.array(path[0][0]), tools.rot_z([-1, 0], path[0][1])]]
    Entities = []
    directory = "C:/Program Files (x86)/Steam/steamapps/common/Source SDK Base 2013 Singleplayer/ep2/custom/trakpak/models/trakpak3_rsg"
    Track_Library = importer.build_track_library(directory, ".mdl")

    write_track(
        np.array(path[0][0]),
        np.add(np.array(path[0][0]), np.array(tools.rot_z([-64, 0, 0], path[0][1]))),
        "0fw",
        "models/trakpak3_rsg/straights/s0064_0fw_0pg_+0064x00000x0000.mdl",
        path[0][1],
    )

    path[0][0] = np.add(
        np.array(path[0][0]), np.array(tools.rot_z([-64, 0, 0], path[0][1]))
    )

    for Subsolve in range(len(path) - 1):

        Direction = "0fw"  # this will always be true... for now

        StartPt = path[Subsolve]
        EndPt = path[Subsolve + 1]

        write_pathfinder_data(
            recursive_track_explorer(StartPt[0], Direction, StartPt[1], []),
            StartPt[0],
            StartPt[1],
        )

    write_track(
        np.array(path[-1][0]),
        np.add(np.array(path[-1][0]), np.array(tools.rot_z([-64, 0, 0], path[-1][1]))),
        Direction,
        "models/trakpak3_rsg/straights/s0064_0fw_0pg_+0064x00000x0000.mdl",
        path[-1][1],
    )

    return Line, Entities
