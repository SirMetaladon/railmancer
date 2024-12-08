import turtle
import math
import numpy as np
from scipy.optimize import minimize


def get_perpendicular_vec2d(v):
    """Returns a perpendicular vector to the given vector."""
    return (-v[1], v[0])


def vector_length(v):
    """Returns the length of the vector."""
    return math.sqrt(v[0] ** 2 + v[1] ** 2)


def normalize_vec2d(v):
    """Normalizes the given vector to a unit vector."""
    length = vector_length(v)
    if length == 0:
        return (0, 0)
    return (v[0] / length, v[1] / length)


def reverse(v):

    Out = []
    for entry in v:
        Out += [-entry]
    return Out


def max_manhattan(v1, v2):

    return max(abs(v1[0] - v2[0]), abs(v1[1] - v2[1]))


def determine_constants(Extents: list = [0, 0, 0, 0]):

    global canvas_scale, canvas_offset
    canvas_scale = 0.22
    canvas_offset = (-2040, -2048)


def canvas(Point):
    return (
        (Point[0] + canvas_offset[0]) * canvas_scale,
        (Point[1] + canvas_offset[1]) * canvas_scale,
    )


def draw_perpendicular_line(point, direction, length=50):
    """Draws a perpendicular line at a given point and direction using Turtle graphics.

    Args:
        point (tuple): The (x, y) coordinates of the starting point.
        direction (tuple): The direction vector (dx, dy) along which the perpendicular is calculated.
        length (float): The length of the perpendicular line to draw. Default is 50 units.
    """
    # Get a perpendicular vector to the direction
    perp_vector = get_perpendicular_vec2d(direction)

    # Normalize the perpendicular vector
    perp_vector = normalize_vec2d(perp_vector)

    # Scale the perpendicular vector to the desired length
    perp_vector = (
        perp_vector[0] * length / canvas_scale,
        perp_vector[1] * length / canvas_scale,
    )

    # Calculate the endpoints of the perpendicular line
    start_point = (
        (point[0] - perp_vector[0] / 2),
        (point[1] - perp_vector[1] / 2),
    )
    end_point = (
        (point[0] + perp_vector[0] / 2),
        (point[1] + perp_vector[1] / 2),
    )

    # Draw the perpendicular line
    turtle.penup()
    turtle.goto(canvas(start_point))
    turtle.pendown()
    turtle.goto(canvas(end_point))


def nudge(point, direction):

    return (
        point[0] + direction[0],
        point[1] + direction[1],
    )


def mark(point, length=8):
    """Draws a green cross at the specified point."""

    # Draw the perpendicular line
    turtle.penup()
    turtle.color("green")
    turtle.goto(canvas(nudge(point, [length / canvas_scale, 0])))
    turtle.pendown()
    turtle.goto(canvas(nudge(point, [-length / canvas_scale, 0])))
    turtle.penup()
    turtle.goto(canvas(nudge(point, [0, length / canvas_scale])))
    turtle.pendown()
    turtle.goto(canvas(nudge(point, [0, -length / canvas_scale])))
    turtle.penup()
    turtle.color("white")


def draw_bezier_curve(Bez: list):

    mark(Bez[1])
    mark(Bez[2])

    turtle.penup()
    turtle.goto(canvas(Bez[0]))
    turtle.pendown()

    # Approximate with a polyline
    steps = 20
    for i in range(steps + 1):
        t = i / steps
        # Cubic Bezier formula
        x = (
            (1 - t) ** 3 * Bez[0][0]
            + 3 * (1 - t) ** 2 * t * Bez[1][0]
            + 3 * (1 - t) * t**2 * Bez[2][0]
            + t**3 * Bez[3][0]
        )
        y = (
            (1 - t) ** 3 * Bez[0][1]
            + 3 * (1 - t) ** 2 * t * Bez[1][1]
            + 3 * (1 - t) * t**2 * Bez[2][1]
            + t**3 * Bez[3][1]
        )

        turtle.goto(canvas((x, y)))
        # THING TO DO: MAKE THIS CHANGE COLOR WITH Z-VALUE


def draw_line(p1, p2):
    """Draws a straight line between two points using Turtle graphics."""
    turtle.penup()
    turtle.goto(canvas(p1))
    turtle.pendown()
    turtle.goto(canvas(p2))


def bezier_curve(t, P0, P1, P2, P3):
    return (
        (1 - t) ** 3 * P0
        + 3 * (1 - t) ** 2 * t * P1
        + 3 * (1 - t) * t**2 * P2
        + t**3 * P3
    )


def bezier_curve_points(p0, p3, d0, d3):

    # Convert to 2 dimensions, as the bezier pathing does not concern height (and it makes the math easier)
    p0 = np.array([p0[0], p0[1]])
    p3 = np.array([p3[0], p3[1]])

    # Normalize direction vectors
    d0 = d0 / np.linalg.norm(d0)
    d3 = d3 / np.linalg.norm(d3)

    # Check if the direction vectors are collinear
    cross_directions = np.cross(d0, d3)
    is_collinear_directions = np.isclose(cross_directions, 0)

    # Check if the points are aligned along the direction vector
    p3_p0 = p3 - p0
    p3_p0_dir = p3_p0 / np.linalg.norm(p3_p0)  # Unit vector in the direction of P3 - P0
    cross_points = np.cross(d0, p3_p0_dir)
    is_aligned_points = np.isclose(cross_points, 0)

    if is_collinear_directions and is_aligned_points:
        # Control points the midpoint should work, right?
        p1 = p0 + d0 * np.linalg.norm(p3 - p0) / 2
        p2 = p1
        return np.array([p0, p1, p2, p3])

    # Function to calculate the radius of curvature
    def curvature_radius(p0, p1, p2, p3, t):
        """Calculates the radius of curvature of a cubic Bezier curve at parameter t."""
        # First derivative
        d1 = 3 * (p1 - p0)
        d2 = 3 * (p2 - p1)
        d3 = 3 * (p3 - p2)

        dP = (1 - t) ** 2 * d1 + 2 * (1 - t) * t * d2 + t**2 * d3

        # Second derivative
        ddP = 6 * ((1 - t) * (p2 - 2 * p1 + p0) + t * (p3 - 2 * p2 + p1))

        # Radius of curvature formula
        numerator = np.linalg.norm(dP) ** 3
        denominator = np.abs(np.cross(dP, ddP))
        if denominator == 0:  # To avoid division by zero
            return np.inf
        return numerator / denominator

    # Objective function: Minimize the negative minimum radius of curvature (maximize radius)
    def objective(params):
        p1 = p0 + params[0] * d0
        p2 = p3 + params[1] * d3
        min_radius = np.inf

        # Sample at multiple points along the curve to estimate the minimum radius
        for t in np.linspace(0, 1, 20):
            radius = curvature_radius(p0, p1, p2, p3, t)
            if np.isnan(radius) or np.isinf(radius):
                print(f"Invalid radius at t={t}: {radius}")
            min_radius = min(min_radius, radius)

        # Return negative to maximize radius
        return -min_radius

    # Initial guess for parameter multipliers
    initial_guess = np.array([0.5, 0.5])  # Parameters for scaling d0 and d3

    dist = math.dist(p0, p3)

    # Bounds to prevent the control points from going too far
    bounds = [(dist / 5, 30000), (dist / 5, 30000)]

    # Perform optimization
    result = minimize(objective, initial_guess, bounds=bounds, method="L-BFGS-B")

    # Calculate control points based on optimized parameters
    best_params = result.x
    p1 = p0 + best_params[0] * d0
    p2 = p3 + best_params[1] * d3

    return np.array([p0, p1, p2, p3])


def display_path(BezList: list, Line: list):

    screen = turtle.Screen()
    screen.colormode(255)
    screen.bgcolor("black")
    screen.setup(1300, 1000)

    turtle.speed(0)
    turtle.penup()
    # turtle.tracer(0, 0) #this controls the width of the line
    turtle.pencolor("white")
    turtle.hideturtle()

    for Node in Line:
        draw_perpendicular_line(Node[0], Node[1], 20)

    for Plot in BezList:
        draw_bezier_curve(Plot)


def generate_line(Line):

    Extents = [0, 0, 0, 0]
    determine_constants(Extents)
    Beziers = []

    for NID in range(len(Line) - 1):

        Node1 = Line[NID]
        Node2 = Line[NID + 1]

        Beziers += [
            bezier_curve_points(Node1[0], Node2[0], Node1[1], reverse(Node2[1]))
        ]

    display_path(Beziers, Line)

    return Beziers
