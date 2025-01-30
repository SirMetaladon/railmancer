import track, tools, random, bisect, time, math
import numpy as np
from sympy import simplify
import lines, pathways
from sympy import symbols, Eq, solve


def preprocess_invariants(invariants, targets):
    """Subtract invariant contributions from targets."""
    adjusted_targets = [
        int(target - adjust) for adjust, target in zip(invariants, targets)
    ]
    return adjusted_targets


def extract_constant_part(solution):
    """
    Extract only the constant part of each expression.
    """
    extracted = {}
    for key, value in solution.items():
        # Split the expression into constant and remaining terms
        constant_part, _ = value.as_coeff_Add()
        extracted[key] = constant_part
    return extracted


def find_solutions(slopes, targets, invariants):
    """Solve for an arbitrary number of variables given slopes and targets."""
    # Adjust targets by preprocessing invariants
    adjusted_targets = preprocess_invariants(invariants, targets)

    # Define symbolic variables dynamically based on the number of slopes
    variables = symbols(
        f"V:{len(slopes)}", integer=True, positive=True
    )  # Dynamic variables V0, V1, ...

    print(variables)
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

    # Filter for solutions meeting the constraints (positivity, integrality)
    final_solutions = []
    for solution in solutions:

        print(solution)
        free_vars = [var for var in solution.values() if not var.is_number]
        if free_vars:

            print("is it?")
            # Substitute free variables to generate specific testable solutions
            substituted_solution = extract_constant_part(solution)

            # Ensure positivity and integer constraints
            if all(
                value.is_integer and (value > 1 or value == 0)
                for value in substituted_solution.values()
            ):
                final_solutions.append(substituted_solution)
        else:
            print("why not?")
            # Check if solution is already valid
            if all(
                value.is_integer and (value > 1 or value == 0)
                for value in solution.values()
            ):
                final_solutions.append(solution)

    return final_solutions if final_solutions else None


def matrix_hash(Position, Direction, Heading):

    return f"{round(Position[0])}|{round(Position[1])}|{round(Position[2])}|{Direction}|{round(Heading)}"


def write_track(Position, NextPosition, Direction, MDL, Heading):

    global Beziers, Entities

    data = Track_Library[MDL]

    Beziers += [
        lines.bezier_curve_points(
            Position,
            NextPosition,
            tools.rot_z(track.get_heading(Direction), Heading),
            tools.rot_z(track.get_heading(data["EndDirection"]), Heading + 180),
        )
    ]

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


def update_pos(Pos, Move, Head):
    return np.round(np.add(Pos, tools.rot_z(Move, Head)))


def append_track(Model, Position, Direction, Heading):

    Data = Track_Library[Model]

    NewDirection = (
        Data["StartDirection"]
        if Data["StartDirection"][:1] != Direction[:1]
        else Data["EndDirection"]
    )

    NewHeading = Heading
    # this var is only 1 if the heading has changed in a 45 degree movement

    # this will use the new heading rotation if it's a 45, and the old one if it's a 90
    NewHand = NewDirection[1:]
    OldHand = Direction[1:]

    if Direction[:1] == "4" and NewHand != OldHand:
        NewHeading = (Heading + 90) if NewHand == "rt" else (Heading - 90)

    NewPosition = update_pos(Position, Data["Move"], NewHeading)

    # this mechanism does so for 90 degree angles
    if NewDirection == "8rt":
        NewHeading = Heading - 90
    elif NewDirection == "8lt":
        NewHeading = Heading + 90

    return NewPosition, NewDirection, NewHeading


def write_pathfinder_data(MDLList, Start):

    Position = Start[0]
    Direction = Start[1]
    Heading = Start[2]

    for Model in MDLList:

        NewPosition, NewDirection, NewHeading = append_track(
            Model, Position, Direction, Heading
        )

        # finalize track placement
        write_track(Position, NewPosition, NewDirection, Model, NewHeading)

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

    SavedDirections[Index] = Output

    return Output


def connect(Start, End):

    Head_Deflect = (End[2] - Start[2]) % 180
    X_Deflect, Y_Deflect, Z_Deflect = np.round(tools.rot_z(End[0] - Start[0], End[2]))

    Paths = pathways.get(Head_Deflect, Start[1], End[1])

    # sort slopes by how much they go towards where we are trying to go
    # Example Inputs
    for TestPath in Paths:

        invariants = TestPath[0]  # Offsets
        slopes = TestPath[1]  # Slopes for V0, V1, V2
        targets = (X_Deflect, Y_Deflect)  # Target X and Y

        print(slopes, targets, invariants)

        # Find solutions
        solutions = find_solutions(slopes, targets, invariants)

        import straight

        if not solutions:
            print(TestPath, "No solutions found.")
            continue

        for subsection in solutions[0].items():
            Sublengths = straight.decompose(subsection[1] * 16)

            return [track.length_to_model_straight(Sub, "0fw", 0) for Sub in Sublengths]
        break


def add_connector(pathnode):

    if pathnode[1] == "0fw":

        write_track(
            np.array(pathnode[0]),
            update_pos(pathnode[0], [-64, 0, 0], pathnode[2]),
            "0fw",
            track.length_to_model_straight(64, "0fw", 0),
            pathnode[2],
        )

        pathnode[0] = np.add(
            np.array(pathnode[0]), np.array(tools.rot_z([-64, 0, 0], pathnode[2]))
        )


def realize(path):

    global Entities, Track_Library, Beziers

    Beziers = []
    Entities = []
    directory = "C:/Program Files (x86)/Steam/steamapps/common/Source SDK Base 2013 Singleplayer/ep2/custom/trakpak/models/trakpak3_rsg"
    Track_Library = track.build_track_library(directory, ".mdl")

    # start transition cap for the route
    add_connector(path[0])

    for Subsolve in range(len(path) - 1):

        StartPt = path[Subsolve]
        EndPt = path[Subsolve + 1]

        PathModels = connect(StartPt, EndPt)

        if PathModels is not None:

            write_pathfinder_data(
                PathModels,
                StartPt,
            )

    # end cap for the route
    add_connector(path[-1])

    return Beziers, Entities
