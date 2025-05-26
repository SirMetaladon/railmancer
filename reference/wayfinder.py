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


def realize(path):

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
