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

    return (-v[0], -v[1])


def max_manhattan(v1, v2):

    return max(abs(v1[0] - v2[0]), abs(v1[1] - v2[1]))


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
    perp_vector = (perp_vector[0] * length, perp_vector[1] * length)

    # Calculate the endpoints of the perpendicular line
    start_point = (point[0] - perp_vector[0] / 2, point[1] - perp_vector[1] / 2)
    end_point = (point[0] + perp_vector[0] / 2, point[1] + perp_vector[1] / 2)

    # Draw the perpendicular line
    turtle.penup()
    turtle.goto(start_point)
    turtle.pendown()
    turtle.goto(end_point)


def nudge(point, direction):

    return (point[0] + direction[0], point[1] + direction[1])


def mark(point, length=10):
    """Draws a green cross at the specified point."""

    # Draw the perpendicular line
    turtle.penup()
    turtle.color("green")
    turtle.goto(nudge(point, [length, 0]))
    turtle.pendown()
    turtle.goto(nudge(point, [-length, 0]))
    turtle.penup()
    turtle.goto(nudge(point, [0, length]))
    turtle.pendown()
    turtle.goto(nudge(point, [0, -length]))
    turtle.penup()
    turtle.color("white")


def draw_bezier_curve(p1, p2, d1, d2):

    InterPoints = bezier_curve_points(p1, p2, d1, d2)

    control1 = InterPoints[1]
    control2 = InterPoints[2]

    mark(control1)
    mark(control2)

    turtle.penup()
    turtle.goto(p1)
    turtle.pendown()

    # Approximate with a polyline
    steps = 20
    for i in range(steps + 1):
        t = i / steps
        # Cubic Bezier formula
        x = (
            (1 - t) ** 3 * p1[0]
            + 3 * (1 - t) ** 2 * t * control1[0]
            + 3 * (1 - t) * t**2 * control2[0]
            + t**3 * p2[0]
        )
        y = (
            (1 - t) ** 3 * p1[1]
            + 3 * (1 - t) ** 2 * t * control1[1]
            + 3 * (1 - t) * t**2 * control2[1]
            + t**3 * p2[1]
        )
        turtle.goto(x, y)


def draw_line(p1, p2):
    """Draws a straight line between two points using Turtle graphics."""
    turtle.penup()
    turtle.goto(p1)
    turtle.pendown()
    turtle.goto(p2)


def bezier_curve(t, P0, P1, P2, P3):
    return (
        (1 - t) ** 3 * P0
        + 3 * (1 - t) ** 2 * t * P1
        + 3 * (1 - t) * t**2 * P2
        + t**3 * P3
    )


def bezier_curve_points(p0, p3, d0, d3):
    # Normalize direction vectors
    d0 = d0 / np.linalg.norm(d0)
    d3 = d3 / np.linalg.norm(d3)

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
            min_radius = min(min_radius, radius)

        # Return negative to maximize radius
        return -min_radius

    # Initial guess for parameter multipliers
    initial_guess = np.array([0.5, 0.5])  # Parameters for scaling d0 and d3

    dist = math.dist(p0, p3)

    # Bounds to prevent the control points from going too far
    bounds = [(dist / 5, 3000), (dist / 5, 3000)]

    # Perform optimization
    result = minimize(objective, initial_guess, bounds=bounds, method="L-BFGS-B")

    # Calculate control points based on optimized parameters
    best_params = result.x
    p1 = p0 + best_params[0] * d0
    p2 = p3 + best_params[1] * d3

    return np.array([p0, p1, p2, p3])


def main():

    screen = turtle.Screen()
    screen.colormode(255)
    screen.bgcolor("black")
    screen.setup(1300, 1000)

    turtle.speed(0)
    turtle.penup()
    # turtle.tracer(0, 0) #this controls the width of the line
    turtle.pencolor("white")
    turtle.hideturtle()

    Line = [
        [[200, 0], [0, 1]],
        [[-50, 350], [-1, 1]],
        [[-300, 450], [-1, 0]],
        [[-350, -50], [0, -1]],
        [[-200, -350], [1, 0]],
        [[200, 0], [0, 1]],
    ]

    for Node in Line:
        draw_perpendicular_line(Node[0], Node[1], 20)

    for NID in range(len(Line) - 1):

        Node1 = Line[NID]
        Node2 = Line[NID + 1]

        draw_bezier_curve(Node1[0], Node2[0], Node1[1], reverse(Node2[1]))

    turtle.done()


if __name__ == "__main__":
    main()
