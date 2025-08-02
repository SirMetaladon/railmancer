import turtle, math, numpy as np
from scipy.optimize import minimize
from railmancer import tools, cfg


def bezier(t, Bez, dimensions):

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

    if dimensions == 2:
        return x, y
    else:
        # more calculations needed for precision, but for now:
        return x, y, Bez[0][2] + (Bez[3][2] - Bez[0][2]) * t


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


def canvas(Point):
    return (
        (Point[0] + canvas_offset[0]) * canvas_scale,
        (Point[1] + canvas_offset[1]) * canvas_scale,
    )


def draw_perpendicular_line(point1, point2, distance=50):

    x1, y1 = point1[0], point1[1]
    x2, y2 = point2[0], point2[1]

    # Compute the vector from point1 to point2
    dx, dy = x2 - x1, y2 - y1

    # Normalize the vector
    length = math.sqrt(dx**2 + dy**2)
    if length != 0:

        dx /= length
        dy /= length

        # Find the perpendicular vector
        perp_dx = -dy
        perp_dy = dx

        # Compute the two equidistant perpendicular points
        pointA = (x1 + perp_dx * distance, y1 + perp_dy * distance)
        pointB = (x1 - perp_dx * distance, y1 - perp_dy * distance)

        # Draw the perpendicular line
        turtle.penup()
        turtle.goto(canvas(pointA))
        turtle.pendown()
        turtle.goto(canvas(pointB))


def mark(point, length=8):
    """Draws a green cross at the specified point."""

    Points = tools.quadnudge(point, length / canvas_scale)

    # Draw the perpendicular line
    turtle.penup()
    turtle.color("green")
    turtle.goto(canvas(Points[0]))
    turtle.pendown()
    turtle.goto(canvas(Points[1]))
    turtle.penup()
    turtle.goto(canvas(Points[2]))
    turtle.pendown()
    turtle.goto(canvas(Points[3]))
    turtle.penup()
    turtle.color("white")


def draw_bezier_curve(Bez: list):

    mark(Bez[1])
    mark(Bez[2])
    draw_perpendicular_line(Bez[3], Bez[2])

    turtle.penup()
    turtle.goto(canvas(Bez[0]))
    turtle.pendown()

    # Approximate with a polyline
    steps = 20
    for i in range(steps + 1):
        t = i / steps
        # Cubic Bezier formula

        x, y = bezier(t, Bez, 2)

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


def write_bezier_points(start_position, end_position, start_direction, end_direction):

    global Beziers

    try:
        Beziers
    except:
        Beziers = []

    # Convert to 2 dimensions, as the bezier pathing does not concern height (and it makes the math easier)
    p0 = np.array([start_position[0], start_position[1]])
    p3 = np.array([end_position[0], end_position[1]])

    # Normalize direction vectors
    d0 = start_direction / np.linalg.norm(start_direction)
    d3 = end_direction / np.linalg.norm(end_direction)

    # Check if the direction vectors are collinear
    cross_directions = np.cross(d0, d3)
    is_collinear_directions = np.isclose(cross_directions, 0)

    # Check if the points are aligned along the direction vector
    p3_p0 = p3 - p0
    p3_p0_dir = p3_p0 / np.linalg.norm(p3_p0)  # Unit vector in the direction of P3 - P0
    cross_points = np.cross(d0, p3_p0_dir)
    is_aligned_points = np.isclose(cross_points, 0)

    if is_collinear_directions and is_aligned_points:
        # make an attempt at a straight line
        p1 = p0 + d0 * np.linalg.norm(p3 - p0) / 2
        p2 = p1
        Beziers += [
            (
                start_position,
                np.array(start_position) * (2 / 3) + np.array(end_position) * (1 / 3),
                np.array(start_position) * (1 / 3) + np.array(end_position) * (2 / 3),
                end_position,
            )
        ]

    else:

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
                if not (np.isnan(radius) or np.isinf(radius)):
                    min_radius = min(min_radius, radius)
                """else:
                    print(
                        f"Invalid radius at t={t}: {radius}, {start_position}, {end_position}"
                    )"""

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

        Beziers += [(start_position, p1, p2, end_position)]


def display_path(BezList: list, Extents):

    global canvas_scale, canvas_offset

    screen = turtle.Screen()
    screen.colormode(255)
    screen.bgcolor("black")
    screen.setup(1300, 1000)

    # convert extents into these values
    canvas_scale = 0.11  # 0.22 = 1 block is on screen
    canvas_offset = (-2040, -2048)

    turtle.speed(0)
    turtle.penup()
    # turtle.tracer(0, 0) #this controls the width of the line
    turtle.pencolor("white")
    turtle.hideturtle()

    draw_perpendicular_line(BezList[0][0], BezList[0][1])

    for Plot in BezList:
        draw_bezier_curve(Plot)


"""depreciated 1-11-25: line format is being removed in favor of beziers only, the interrim format was for input ease only
def generate_line(Line):

    Beziers = []

    for NID in range(len(Line) - 1):

        Node1 = Line[NID]
        Node2 = Line[NID + 1]


        write_bezier_points(Node1[0], Node2[0], Node1[1], reverse(Node2[1]))
        

    return Beziers"""


def encode_lines():

    global sampled_points
    line_maximum_poll_point_distance = cfg.get("line_maximum_poll_point_distance")

    if not len(Beziers):
        # placeholder value for maps with no track
        sampled_points = [[100000, 100000, 100000]]
    else:
        sampled_points = []

    for Subsegment in Beziers:
        ts = np.linspace(
            0,
            1,
            int(
                np.linalg.norm(Subsegment[0] - Subsegment[3])
                / line_maximum_poll_point_distance
            )
            + 1,
        )

        sampled_points += [(bezier(t, Subsegment, 3)) for t in ts]


def get_sampled_points():

    try:
        return sampled_points
    except:
        return []
