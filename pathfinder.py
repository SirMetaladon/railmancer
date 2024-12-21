import importer, tools, random, bisect, time
import numpy as np


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
    if Direction != "0fw" and NewDirection != "0fw":
        NewHand = NewDirection[1:]
        OldHand = Direction[1:]

        if NewHand != OldHand:
            NewHeading = (Heading + 90) if NewHand == "rt" else (Heading - 90)
            Reorient = 1

    # this will use the new heading rotation if it's a 45, and the old one if it's a 90, as it should be
    NewPosition = np.add(Position, tools.rot_z(Data["Move"], NewHeading))

    # this mechanism does so for 90 degree angles
    if NewDirection == "8rt":
        NewHeading = Heading - 90
    elif NewDirection == "8lt":
        NewHeading = Heading + 90

    return np.copy(NewPosition), NewDirection, NewHeading, Reorient


def lineout(MDLList):

    global Line, Entities

    Position = StartPt[0]
    Direction = "0fw"
    Heading = StartPt[1]

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

    return Line, Entities


def valid_next_tracks(Direction):

    Output = []

    for Track in list(Track_Library.items()):

        if Track[1]["GradeLevel"] != 0:
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

    random.shuffle(Output)

    return Output


def recursive_track_explorer(PosIn, DirIn, HeadIn, SoFarIn):

    ToEvaluate = [(PosIn, DirIn, HeadIn, SoFarIn, 0)]
    Ticker = 0

    while len(ToEvaluate) and Ticker < 5000:

        Current = ToEvaluate.pop(0)
        Direction = Current[1]

        Choices = valid_next_tracks(Direction)

        print(Current)
        time.sleep(1)

        for Track in Choices:

            Position = np.copy(Current[0])
            Direction = Current[1]
            Heading = Current[2]
            SoFar = Current[3].copy()
            Model = Track[0]

            NewPosition, NewDirection, NewHeading, Reorient = append_track(
                Model, Position, Direction, Heading
            )

            # here you get to decide if you want to keep it, but for now we keep all - no heuristics yet

            if NewDirection[:1] == "8":
                NewDirection = "0fw"

            Position = NewPosition
            Heading = NewHeading
            Direction = NewDirection

            NewFar = SoFar + [Track[0]]

            # print(len(NewFar), Position)

            if (
                Heading == EndPt[1]
                and tools.is_same(Position, EndPt[0]) == "yes"
                and Direction == "0fw"  # guarenteed end direction for now
            ):
                print("WINNAR", NewFar)
                return lineout(NewFar)

            else:
                # if it meets the requirements

                """
                HeadingDeflection = EndPt[1]-Direction

                PositionDeflection = tools.rot_z(EndPt[0]-Position,HeadingDeflection)

                if HeadingDeflection == 0:
                    #else, you can slip 2 2048 1rt turns in and correct it
                    if "horizontal deflection" > 0 and "less than" < 192:
                        continue"""

                Score = np.linalg.norm(EndPt[0] - Position)

                # print(Position, Direction, Heading, NewFar, Score)

                bisect.insort(
                    ToEvaluate,
                    (Position, Direction, Heading, NewFar, Score),
                    key=lambda x: x[4],
                )

    print(f"Pathfinder gave up after {Ticker} iterations!")
    return lineout(ToEvaluate[0][3])


def solve(start_pos, start_heading, end_pos, end_heading):

    global Line, Entities, Track_Library, StartPt, EndPt
    Line = [[np.array(start_pos), tools.rot_z([-1, 0], start_heading)]]
    Entities = []

    directory = "C:/Program Files (x86)/Steam/steamapps/common/Source SDK Base 2013 Singleplayer/ep2/custom/trakpak/models/trakpak3_rsg"
    Track_Library = importer.build_track_library(directory, ".mdl")

    Direction = "0fw"  # this will always be true... for now
    Radius = 0  # starting radius
    Position = np.add(
        np.array(start_pos), np.array(tools.rot_z([-64, 0, 0], start_heading))
    )

    print(Position)
    GradeLevel = 0  # starting grade level

    StartPt = [Position, start_heading]
    EndPt = [end_pos, end_heading]

    write_track(
        np.array(start_pos),
        Position,
        Direction,
        "models/trakpak3_rsg/straights/s0064_0fw_0pg_+0064x00000x0000.mdl",
        start_heading,
    )

    return recursive_track_explorer(Position, Direction, start_heading, [])
