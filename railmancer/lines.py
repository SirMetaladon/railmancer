import numpy as np
from railmancer import tools, cfg

# Handles extraction of line and point data from given lists of track-objects. Handles everything related to said lists of points.

Beziers: list = []
sampled_points = []
staged_points = []


def bezier_3d(t, Bez) -> tuple[float, float, float]:

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

    return x, y, Bez[0][2] + (Bez[3][2] - Bez[0][2]) * t



def convert_nodes_to_bezier(
    start_position, end_position, start_direction, end_direction
) -> list:

    # Convert to 2 dimensions, as the bezier pathing does not concern height (and it makes the math easier)
    p0 = np.array([start_position[0], start_position[1]])
    p3 = np.array([end_position[0], end_position[1]])

    # two dimensionalize
    dir1 = np.array([start_direction[0], start_direction[1]])
    dir2 = np.array([end_direction[0], end_direction[1]])

    # Normalize direction vectors
    d0 = dir1 / np.linalg.norm(dir1)
    d3 = -dir2 / np.linalg.norm(dir2)

    # z-component of the cross product. np.cross no longer accepts 2-vectors.
    cross_directions = d0[0] * d3[1] - d0[1] * d3[0]
    is_collinear_directions = np.isclose(cross_directions, 0)

    # Check if the points are aligned along the direction vector
    p3_p0 = p3 - p0
    p3_p0_dir = p3_p0 / np.linalg.norm(p3_p0)  # Unit vector in the direction of P3 - P0
    cross_points = d0[0] * p3_p0_dir[1] - d0[1] * p3_p0_dir[0]
    is_aligned_points = np.isclose(cross_points, 0)

    if is_collinear_directions and is_aligned_points:
        # make an attempt at a straight line
        p1 = p0 + d0 * np.linalg.norm(p3 - p0) / 2
        p2 = p1
        return [
            (
                start_position,
                p0 * (2 / 3) + p3 * (1 / 3),
                p0 * (1 / 3) + p3 * (2 / 3),
                end_position,
            )
        ]

    else:

        v = p3 - p0
        L = np.linalg.norm(v)

        # Angle between tangents
        dot = np.clip(np.dot(d0, d3), -1.0, 1.0)
        theta = np.arccos(dot)

        # Handle length for max-radius curve
        if theta < 1e-3:
            h = L / 2
        else:
            # this is a chatGPT component - I do not understand it.
            h = (2 * L / 3) * (1 - np.cos(theta / 2)) / (np.sin(theta / 2) ** 2)

        # Optional clamp (replaces optimizer bounds)
        h = np.clip(h, L / 5, 30000)

        p1 = p0 + h * d0
        p2 = p3 - h * d3

        return [(start_position, p1, p2, end_position)]


def write_bezier_points(start_position, end_position, start_direction, end_direction):

    global Beziers
    Beziers += convert_nodes_to_bezier(
        start_position, end_position, start_direction, end_direction
    )



def convert_bezier_to_points(Segment, line_maximum_poll_point_distance):
    ts = np.linspace(
        0,
        1,
        int(np.linalg.norm(Segment[0] - Segment[3]) / line_maximum_poll_point_distance)
        + 1,
    )

    return [(bezier_3d(t, Segment)) for t in ts]


def stage_points(more_points):

    global staged_points
    staged_points += more_points


def insert_staged_points():

    global sampled_points
    sampled_points += staged_points


def encode_lines():

    global sampled_points

    line_maximum_poll_point_distance = cfg.get("line_maximum_poll_point_distance")

    if not len(Beziers):
        # placeholder value for maps with no track
        sampled_points = [[100000, 100000, 100000]]
    else:
        sampled_points = []

    for Segment in Beziers:

        sampled_points += convert_bezier_to_points(
            Segment, line_maximum_poll_point_distance
        )

    tools.stopwatch_click("submodule", "Encoded lines done")


def get_all_track_points():

    return sampled_points


def get_terrain_points_from_sample(points_to_analyze):
    # gets non-bridge from a list of points

    from scipy.spatial import cKDTree

    """
    Optimized separation of points into two lists using a cKDTree.
    A: points that have another point in a 4/1 slope cone below them
    B: points that do not
    """
    pts = np.array(points_to_analyze)  # shape (n, 3)

    if not hasattr(pts, "ndim") or pts.ndim != 2:
        print(
            "DEBUG: pts has wrong shape",
            type(pts),
            getattr(pts, "shape", None),
            repr(pts)[:500],
        )

    xy = pts[:, :2]  # (x, y)
    all_points_z_values = pts[:, 2]  # z values

    cone_slope = 1.5

    tree = cKDTree(xy)

    non_bridge_points = []

    for i, (x, y, current_point_height) in enumerate(pts):
        # candidate points must be below in z
        below_mask = all_points_z_values < current_point_height
        # aha! It's needed because being the lowest point breaks the other system (division by 0?)
        if not np.any(below_mask):
            non_bridge_points.append(tuple(pts[i]))
            continue

        # farthest possible radius we might need: cone_slope * (current_point_height - min(z_below))
        max_vert_diff = current_point_height - np.min(all_points_z_values[below_mask])
        search_radius = max_vert_diff / cone_slope

        # query candidates within this XY radius
        idxs = tree.query_ball_point([x, y], search_radius)

        found = False
        for j in idxs:
            if all_points_z_values[j] < current_point_height:
                lateral_dist = np.hypot(x - pts[j, 0], y - pts[j, 1])
                vertical_diff = current_point_height - all_points_z_values[j]
                if (lateral_dist * cone_slope) < vertical_diff:
                    found = True
                    break

        if found is False:
            non_bridge_points.append(tuple(pts[i]))

    return non_bridge_points
