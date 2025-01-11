import track, tools, random, bisect, time, math
import numpy as np
from sympy import simplify


def matrix_hash(Position, Direction, Heading):

    return f"{round(Position[0])}|{round(Position[1])}|{round(Position[2])}|{Direction}|{round(Heading)}"


def write_track(Position, NextPosition, Direction, MDL, Heading):

    global Line, Entities

    data = Track_Library[MDL]

    Line += [[NextPosition, tools.rot_z(track.get_heading(Direction), Heading)]]

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


def new_position_valid(Position, Direction, Heading, OldPos):

    global Bad

    Print = False

    if PreExploredMatrix.get(matrix_hash(Position, Direction, Heading), False):
        if Print:
            print(f"I've been here.")
        return False  # already explored here

    Head_Deflect = (EndPt[1] - Heading) % 180
    Pos_Deflect = np.round(tools.rot_z(EndPt[0] - Position, EndPt[1]))
    X_Deflect = Pos_Deflect[0]
    Y_Deflect = Pos_Deflect[1]

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
        },
        90: {
            "0fw": [[2048, 2048, "right", 9999999]],
            "1rt": [[2048 + 704, 2048 - 96, "right", 1 / 4]],
            "1lt": [[1120 + 640, 608 + 1568, "left", 1 / 4]],
            "2rt": [[2048 + 1056, 2048 - 256, "right", 1 / 2]],
            "2lt": [[736 + 640, 512 + 1568, "left", 1 / 2]],
            "4rt": [[2048 + 1568, 2048 - 640, "right", 1]],
            "4lt": [[640, 1568, "left", 1]],
        },
    }


def recursive_track_explorer(PosIn, DirIn, HeadIn, SoFarIn):

    global PreExploredMatrix, SavedDirections, Bad

    PreExploredMatrix = dict()
    SavedDirections = dict()

    Scatter = []
    Bad = []

    ToEvaluate = [(PosIn, DirIn, HeadIn, SoFarIn, 100000)]
    Ticker = 0

    while len(ToEvaluate) & Ticker < 100000:

        Current = ToEvaluate.pop(0)
        # print(Current)
        Direction = Current[1]

        Scatter.append((Current[0][0], Current[0][1]))

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

        Choices = valid_next_tracks(Direction, 0)

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

            if new_position_valid(NewPosition, NewDirection, NewHeading, Position):

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

    import matplotlib.pyplot as plt

    Scatter = np.array(Scatter)
    Bad = np.array(Bad)

    # Plot the result
    plt.figure(figsize=(8, 8))
    plt.scatter(Scatter[:, 0], Scatter[:, 1], s=2, c="blue", alpha=0.7)
    plt.scatter(Bad[:, 0], Bad[:, 1], s=2, c="red", alpha=0.7)
    plt.xlabel("x")
    plt.ylabel("y")
    plt.show()

    print(f"Pathfinder gave up after {Ticker} iterations!")

    return ToEvaluate[0][3] if len(ToEvaluate) > 0 else []


def solve(path, Sectors):

    global Line, Entities, Track_Library, StartPt, EndPt, SectorData

    SectorData = Sectors
    Line = [[np.array(path[0][0]), tools.rot_z([-1, 0], path[0][1])]]
    Entities = []
    directory = "C:/Program Files (x86)/Steam/steamapps/common/Source SDK Base 2013 Singleplayer/ep2/custom/trakpak/models/trakpak3_rsg"
    Track_Library = track.build_track_library(directory, ".mdl")

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


from sympy import symbols, Eq, solve


def preprocess_invariants(invariants, targets):
    """Subtract invariant contributions from targets."""
    adjusted_targets = [
        target - invariants.get(label, 0) for label, target in zip(["X", "Y"], targets)
    ]
    return adjusted_targets


def extract_constant_part(solution, free_vars):
    """
    Extract only the constant part of each expression.
    """
    extracted = {}
    for key, value in solution.items():
        # Split the expression into constant and remaining terms
        constant_part, _ = value.as_coeff_Add()
        extracted[key] = constant_part
    return extracted


def find_solution_with_arbitrary_slopes(slopes, targets, invariants):
    """Solve for an arbitrary number of variables given slopes and targets."""
    # Adjust targets by preprocessing invariants
    adjusted_targets = preprocess_invariants(invariants, targets)

    # Define symbolic variables dynamically based on the number of slopes
    variables = symbols(
        f"V:{len(slopes)}", integer=True, positive=True
    )  # Dynamic variables V0, V1, ...

    # Build equations for X and Y based on slopes
    equations = [
        Eq(
            sum(slope[i] * variables[j] for j, slope in enumerate(slopes)),
            adjusted_targets[i],
        )
        for i in range(len(adjusted_targets))  # Iterate for dimensions (X, Y, etc.)
    ]

    # Solve the equations
    solutions = solve(equations, variables, dict=True)

    print(solutions)

    # Filter for solutions meeting the constraints (positivity, integrality)
    final_solutions = []
    for solution in solutions:
        free_vars = [var for var in solution.values() if not var.is_number]
        if free_vars:
            # Substitute free variables to generate specific testable solutions
            substituted_solution = extract_constant_part(solution, free_vars)

            print(substituted_solution)
            # Ensure positivity and integer constraints
            if all(
                value.is_integer and (value > 1 or value == 0)
                for value in substituted_solution.values()
            ):
                final_solutions.append(substituted_solution)
        else:
            # Check if solution is already valid
            if all(
                value.is_integer and (value > 1 or value == 0)
                for value in solution.values()
            ):
                final_solutions.append(solution)

    return final_solutions if final_solutions else None


# Example Inputs
invariants = {"X": 8320, "Y": 8320}  # Offsets
slopes = [(0, 16), (16, 16)]  # Slopes for V0, V1, V2
targets = (10160, 14240)  # Target X and Y


"""quick math:

10168, 14248
10168-8320, 14248 - 8320
1848, 5828



"""

# Find solutions
solutions = find_solution_with_arbitrary_slopes(slopes, targets, invariants)


import straight

print(solutions)

for subsection in solutions[0].items():
    print(subsection)
    print(straight.decompose(subsection[1] * 16))

if solutions:
    print("Solutions found:")
    for sol in solutions:
        print(sol)
else:
    print("No solutions found.")
