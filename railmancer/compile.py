from scipy.spatial import cKDTree
import math, numpy as np, random
from railmancer import sectors, terrain, tools, heightmap, cfg, vmfpy

# A specialized file purposefully for handling the final steps of the Railmancer compiling process, mostly related to placing trees and gathering displacement info.


# The sky wall brush is 16 units thick, sitting on the inside of the sector
# edge (see wall()). Clearance is measured to that inner face.
_SKY_WALL_THICKNESS = 16

# Shipped sector is 3264. The old ratios were 1/3 and 1/32 of that.
_EDGE_WIDTH = 3264.0 / 3.0
_EDGE_CUTOFF = 3264.0 / 32.0


def _base_density(x, y, z):

    # Flat until terrain grows a real field of (x, y, z). The edge boost
    # below is applied on top of whatever this returns.
    return 1.0


def _edge_settings(terrain_block):

    multiplier = float(terrain_block.get("density_edge_multiplier", 6))
    width = float(terrain_block.get("density_edge_width", _EDGE_WIDTH))
    cutoff = float(terrain_block.get("density_edge_cutoff", _EDGE_CUTOFF))
    return multiplier, max(width, 0.0), max(cutoff, 0.0)


def _wall_boost(distance, multiplier, width, cutoff):

    # None means this full wall's keep-out owns the point: density is zero,
    # same as the old cutoff band. Past `width` the wall adds nothing.
    if distance < cutoff:
        return None
    if width <= 0.0 or distance >= width:
        return 0.0
    return (width - distance) / width * multiplier


def _edge_distances(x, y, sector_data, size):

    # Neighbors are N, E, S, W. Distance is to that side of this sector.
    x0 = sector_data["x"] * size
    y0 = sector_data["y"] * size
    return {
        0: (y0 + size) - y,
        1: (x0 + size) - x,
        2: y - y0,
        3: x - x0,
    }


def density_at(x, y, z, sector_data=None):

    # One number for a point in the world. A future biome field replaces
    # _base_density; the full-wall boost stays a function of the same point
    # because the sector (and its sky walls) is looked up from the position.
    if sector_data is None:
        sector_id = sectors.get_sector_id_at_position((x, y, z))
        sector_data = sectors.get(sector_id) if sector_id else None
    if not sector_data:
        return 0.0

    size = float(cfg.get("sector_real_size"))
    neighbors = sector_data.get("neighbors") or [False, False, False, False]
    multiplier, width, cutoff = _edge_settings(terrain.get())
    value = _base_density(x, y, z)
    for slot, distance in _edge_distances(x, y, sector_data, size).items():
        # A real neighbor, even one that only shares part of the height, is
        # not a map edge. Partial walls do not get this boost or this cutoff.
        if slot >= len(neighbors) or neighbors[slot] is not False:
            continue
        extra = _wall_boost(distance, multiplier, width, cutoff)
        if extra is None:
            return 0.0
        value += extra
    return max(value, 0.0)


def _peak_density(sector_data, z):

    # The boost is highest just outside the cutoff, in a corner where two
    # full walls meet. Probing those spots (and the middle) is the peak the
    # acceptance probability divides by. A flat field peaks at the base.
    size = float(cfg.get("sector_real_size"))
    x0 = sector_data["x"] * size
    y0 = sector_data["y"] * size
    _multiplier, width, cutoff = _edge_settings(terrain.get())
    inset = min(cutoff, size * 0.5)
    neighbors = sector_data.get("neighbors") or [False, False, False, False]
    probes = [(x0 + size * 0.5, y0 + size * 0.5)]
    edge_points = {
        0: (x0 + size * 0.5, y0 + size - inset),
        1: (x0 + size - inset, y0 + size * 0.5),
        2: (x0 + size * 0.5, y0 + inset),
        3: (x0 + inset, y0 + size * 0.5),
    }
    for slot, point in edge_points.items():
        if slot < len(neighbors) and neighbors[slot] is False:
            probes.append(point)
    corners = (
        (0, 3, x0 + inset, y0 + size - inset),
        (0, 1, x0 + size - inset, y0 + size - inset),
        (2, 3, x0 + inset, y0 + inset),
        (2, 1, x0 + size - inset, y0 + inset),
    )
    for north_south, east_west, px, py in corners:
        if (
            north_south < len(neighbors)
            and east_west < len(neighbors)
            and neighbors[north_south] is False
            and neighbors[east_west] is False
        ):
            probes.append((px, py))
    peak = 0.0
    for px, py in probes:
        peak = max(peak, density_at(px, py, z, sector_data))
    return peak


def _stochastic_round(expected, rng):

    # floor(expected) drops the fraction, so a small sector whose expected
    # count is 0.4 would never get a tree. The fraction is a coin flip.
    if expected <= 0.0:
        return 0
    whole = math.floor(expected)
    if rng.random() < (expected - whole):
        return whole + 1
    return whole


def _horizontal_extent(model, terrain_block):

    # No foliage model in this repo carries a real hull. If one is added as
    # bounds/hull/bbox = (minx, miny, maxx, maxy) around the origin, that
    # half-extent is the clearance. Otherwise the per-prop wall_clearance,
    # otherwise base_radius (the stump already stored on the prop), otherwise
    # the terrain-level wall_clearance.
    for key in ("bounds", "hull", "bbox"):
        box = model.get(key)
        if box and len(box) >= 4:
            reach = max(abs(float(box[0])), abs(float(box[2])))
            reach = max(reach, abs(float(box[1])), abs(float(box[3])))
            return reach
    if model.get("wall_clearance") is not None:
        return float(model["wall_clearance"])
    if model.get("base_radius") is not None:
        return float(model["base_radius"])
    return float(terrain_block.get("wall_clearance", 64))


def _clears_full_walls(x, y, sector_data, clearance):

    # The box of radius `clearance` has to sit inside the sector and off the
    # inner face of every full sky wall. Partial walls are not checked.
    size = float(cfg.get("sector_real_size"))
    neighbors = sector_data.get("neighbors") or [False, False, False, False]
    need = clearance + _SKY_WALL_THICKNESS
    for slot, distance in _edge_distances(x, y, sector_data, size).items():
        if slot < len(neighbors) and neighbors[slot] is False and distance < need:
            return False
    return True


class _Spacing:

    # Placed props, queried with a tree. The tree is rebuilt in batches; the
    # points added since the last rebuild are checked directly, so a new prop
    # still sees every neighbor.
    def __init__(self):

        self.points = []
        self.radii = []
        self.tree = None
        self.built = 0
        self.reach = 0.0

    def blocks(self, x, y, radius):

        if self.built:
            hits = self.tree.query_ball_point((x, y), max(radius, self.reach))
            for index in hits:
                limit = max(radius, self.radii[index])
                dx = x - self.points[index][0]
                dy = y - self.points[index][1]
                if dx * dx + dy * dy < limit * limit:
                    return True
        for index in range(self.built, len(self.points)):
            limit = max(radius, self.radii[index])
            dx = x - self.points[index][0]
            dy = y - self.points[index][1]
            if dx * dx + dy * dy < limit * limit:
                return True
        return False

    def add(self, x, y, radius):

        self.points.append((x, y))
        self.radii.append(radius)
        self.reach = max(self.reach, radius)
        if len(self.points) - self.built >= 24:
            self.tree = cKDTree(self.points)
            self.built = len(self.points)


def _track_blocks(x, y, model, sector_data, terrain_block, rng):

    realdist, _ = sectors.distance_to_line((x, y, 0), sector_data)
    dist = realdist - float(model.get("exclusion_radius", 0))
    hard = float(terrain_block.get("tree_hard_distance", 128))
    soft = float(terrain_block.get("tree_fade_distance", 128))
    if dist <= hard:
        return True
    if soft > hard and dist <= soft:
        if rng.random() > (dist - hard) / (soft - hard):
            return True
    return False


def _too_steep(x, y, model, sector_data):

    stump = float(model.get("base_radius", 1.0))
    if stump <= 0.0:
        stump = 1.0
    samples = heightmap.height_sample(x, y, 5, stump, sector_data)
    steep = (max(samples) - min(samples)) / (stump * 2.0)
    if steep > model.get("steepness", 999):
        return True, samples
    if steep < model.get("min_steep", -999):
        return True, samples
    return False, samples


def scatter_placables():

    ordered = list(sectors.get_all().values())
    placing = tools.progress("Scattering", len(ordered))
    for index, sector_data in enumerate(ordered, 1):
        distribute(sector_data)
        placing(index)
    placing.finish()
    tools.stopwatch_click("submodule", "Scattering complete")


def distribute(sector_data):

    # Candidates are continuous and uniform. Each one is kept with probability
    # density/peak, which is 1 where the field is strongest. The candidate
    # count is the base count times peak/open, so that coin flip leaves an
    # open area at the configured base rate instead of thinning it to feed
    # the edge. A candidate that loses the coin flip, or that hits a wall,
    # a neighbor, or the track, is dropped. Nothing is retried in its place.
    block = terrain.get()
    size = float(cfg.get("sector_real_size"))
    z_ref = sector_data["floor"] * 16
    open_level = _base_density(
        sector_data["x"] * size + size * 0.5,
        sector_data["y"] * size + size * 0.5,
        z_ref,
    )
    peak = _peak_density(sector_data, z_ref)
    if open_level <= 0.0 or peak <= 0.0:
        return

    rate = float(block.get("maximum_models_per_1kx1k", 0)) / 1000000.0
    expected = rate * size * size * (peak / open_level)
    rng = random.Random(f"{int(block.get('seed', 0) or 0)}:{sector_data['id']}")
    count = _stochastic_round(expected, rng)

    models = terrain.biome()["models"]
    choices = list(models.keys())
    weights = tools.extract(models, choices, "weight", 0)
    if not choices or sum(weights) <= 0:
        return

    x0 = sector_data["x"] * size
    y0 = sector_data["y"] * size
    spacing = _Spacing()

    for _ in range(count):
        x = rng.uniform(x0, x0 + size)
        y = rng.uniform(y0, y0 + size)
        z = heightmap.query_field("height", (x, y, 0), sector_data)
        if z == 8.8888 or z is False:
            z = z_ref
        here = density_at(x, y, z, sector_data)
        if here <= 0.0 or rng.random() >= here / peak:
            continue

        path = rng.choices(choices, weights)[0]
        model = models[path]
        spacing_radius = float(model.get("exclusion_radius", 0))
        clearance = _horizontal_extent(model, block)
        if not _clears_full_walls(x, y, sector_data, clearance):
            continue
        if spacing.blocks(x, y, spacing_radius):
            continue
        if _track_blocks(x, y, model, sector_data, block, rng):
            continue
        blocked, samples = _too_steep(x, y, model, sector_data)
        if blocked:
            continue

        spacing.add(x, y, spacing_radius)

        entity = {
            "pos": (
                x,
                y,
                min(samples) + model.get("height_offset", 0),
            ),
            "mdl": path,
            "ang": (
                rng.randrange(-4, 4),
                rng.randrange(-180, 180),
                rng.randrange(-4, 4),
            ),
            "shadows": "noself",
            "visgroup": "22",
            "disablevertexlighting": "1",
            "sector_id": sector_data["id"],
        }
        if model.get("grouping"):
            entity["grouping"] = model["grouping"]
        vmfpy.add_entity(entity)


def compile_displacement(raw_displacement, sector_data):

    X_Start, X_End, Y_Start, Y_End, Z_Start, Z_End = raw_displacement[:6]

    # 8 multiplier due to the range function below (the power of the displacement is 3, or 2^3 = 8)
    scale_x = (X_Start - X_End) / -8
    scale_y = (Y_Start - Y_End) / 8
    shift_x = X_Start
    shift_y = Y_End

    posgrid = [
        [(x * scale_x + shift_x, y * scale_y + shift_y, 0) for y in range(9)]
        for x in range(9)
    ]

    heights = [
        [
            heightmap.query_field("height", position, sector_data) - Z_End
            for position in x_layer
        ]
        for x_layer in posgrid
    ]
    # reconfigure this later to check the specific sub-biome data for this exact position
    alphas = [
        [
            heightmap.query_alpha(position, terrain.get(), sector_data)
            for position in x_layer
        ]
        for x_layer in posgrid
    ]

    return heights, alphas


def displacement_subdivisions(sector_real_size=None, target=None):
    """How many displacement brushes fit along one side of a sector.

    The count is max(1, round(sector_real_size / displacement_target_size)).
    Each brush is still a power-3 displacement (9x9 verts), set in
    vmfpy.data_to_dispinfo. This only chooses how many of those brushes
    tile the sector.

    Edges are (k / count) * sector_real_size. sector_real_size is already
    a multiple of 16, so the edges stay on that grid exactly when count
    divides sector_real_size / 16. When the rounded count does not, the
    nearest divisor of that cell count is used, preferring the piece size
    closer to the target.
    """

    if sector_real_size is None:
        sector_real_size = cfg.get("sector_real_size")
    if target is None:
        target = cfg.get("displacement_target_size")

    sector_real_size = int(sector_real_size)
    cells = max(sector_real_size // 16, 1)
    target = max(float(target), 16.0)
    ideal = max(1, int(round(float(sector_real_size) / target)))
    ideal = min(ideal, cells)
    if cells % ideal == 0:
        return ideal

    best = 1
    best_key = None
    for count in range(1, cells + 1):
        if cells % count:
            continue
        piece = float(sector_real_size) / count
        key = (abs(piece - target), abs(count - ideal), count)
        if best_key is None or key < best_key:
            best_key = key
            best = count
    return best


def sector_coords_to_subdivided_displacements(
    block_x: int, block_y: int, block_z: int, subdivision, texture
):

    Disps = [
        [
            (block_x + x / subdivision) * 16 * sector_x16_size,
            (block_x + ((x + 1) / subdivision)) * 16 * sector_x16_size,
            (block_y + y / subdivision) * 16 * sector_x16_size,
            (block_y + ((y + 1) / subdivision)) * 16 * sector_x16_size,
            (block_z) * 16,
            (block_z + 1) * 16,
            "displacement",
            texture,
        ]
        for y in range(subdivision)
        for x in range(subdivision)
    ]

    return Disps


def compile_sectors_to_brushes():

    global sector_real_size, sector_x16_size
    sector_real_size = cfg.get("sector_real_size")
    sector_x16_size = int(sector_real_size / 16)

    subdivisions = displacement_subdivisions()
    ordered = list(sectors.get_all().values())
    compiling = tools.progress("Compile", len(ordered))

    for index, sector_data in enumerate(ordered, 1):

        x, y, z = sector_data["x"], sector_data["y"], sector_data["floor"]

        create_scenery_block(sector_data)
        raw_displacements = sector_coords_to_subdivided_displacements(
            x,
            y,
            z,
            subdivisions,
            terrain.get().get("texture_ground", "dev/dev_blendmeasure"),
        )

        for raw_disp in raw_displacements:

            heights, alphas = compile_displacement(raw_disp, sector_data)

            finished_displacement = raw_disp + [
                vmfpy.data_to_dispinfo(raw_disp, heights, alphas)
            ]

            vmfpy.add_brush(finished_displacement, sector_data["id"])
        compiling(index)

    compiling.finish()
    tools.stopwatch_click("submodule", "Brushes and Displacements done")


def create_scenery_block(sector_data):
    block_x, block_y, block_floor, block_ceiling = (
        sector_data["x"],
        sector_data["y"],
        sector_data["floor"],
        sector_data["ceiling"],
    )

    real_x = block_x * sector_real_size
    real_y = block_y * sector_real_size
    real_floor = block_floor * 16
    real_ceiling = block_ceiling * 16
    group_key = sector_data["id"]

    vmfpy.floor(real_x, real_y, real_floor, sector_real_size, group_key)
    vmfpy.ceiling(real_x, real_y, real_ceiling, sector_real_size, group_key)
    # vmfpy.viscluster(real_x, real_y, real_floor, real_ceiling, sector_real_size, 128)

    for dir in range(4):

        adjacent_sector_id = sector_data["neighbors"][dir]

        adjacent_sector = sectors.get(adjacent_sector_id, False)

        if adjacent_sector is False:

            vmfpy.wall(
                real_x,
                real_y,
                real_floor,
                real_ceiling,
                dir,
                sector_real_size,
                "ceiling",
                group_key,
            )

        else:
            nearby_floor = adjacent_sector["floor"] * 16
            nearby_ceiling = adjacent_sector["ceiling"] * 16

            if nearby_floor > real_floor:

                vmfpy.wall(
                    real_x,
                    real_y,
                    nearby_floor,
                    real_floor,
                    dir,
                    sector_real_size,
                    "wall",
                    group_key,
                )

            if nearby_ceiling < real_ceiling:

                vmfpy.wall(
                    real_x,
                    real_y,
                    nearby_ceiling,
                    real_ceiling,
                    dir,
                    sector_real_size,
                    "ceiling",
                    group_key,
                )
