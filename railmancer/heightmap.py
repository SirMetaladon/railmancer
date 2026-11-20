import numpy as np
import matplotlib.pyplot as plt
import random, itertools, math, time
from railmancer import lines, sectors, tools, terrain, cfg, noisefield

# Grid helpers plus the sector height field.
# Each grid value lives in a one-element list so sectors.merge_edges can make
# two sectors share a vertex by sharing the list. The height itself is a
# slope-limited ramp away from a smooth track field, inside the floor/ceiling
# envelope. Query helpers (query_field, query_alpha) still interpolate those grids.


def get_four_nearest_noise_values(
    grid, LeftXCoord, RightXCoord, TopYCoord, BottomYCoord
):

    Limit = len(grid)

    if LeftXCoord < 0 or LeftXCoord > Limit:
        return False
    if RightXCoord < 0 or RightXCoord > Limit:
        return False
    if TopYCoord < 0 or TopYCoord > Limit:
        return False
    if BottomYCoord < 0 or BottomYCoord > Limit:
        return False

    BottomLeftCornerAlpha = grid[LeftXCoord][BottomYCoord][0]
    TopLeftCornerAlpha = grid[LeftXCoord][TopYCoord][0]
    BottomRightCornerAlpha = grid[RightXCoord][BottomYCoord][0]
    TopRightCornerAlpha = grid[RightXCoord][TopYCoord][0]

    if BottomLeftCornerAlpha is False:
        return False
    if TopLeftCornerAlpha is False:
        return False
    if BottomRightCornerAlpha is False:
        return False
    if TopRightCornerAlpha is False:
        return False

    return (
        BottomLeftCornerAlpha,
        TopLeftCornerAlpha,
        BottomRightCornerAlpha,
        TopRightCornerAlpha,
    )


def field_interpolator(sector_object, field, noise_x, noise_y):

    if sector_object is None:
        return False

    LeftXCoord = min(math.floor(noise_x), 23)
    BottomYCoord = min(math.floor(noise_y), 23)

    RightXCoord, TopYCoord = LeftXCoord + 1, BottomYCoord + 1

    Corners = get_four_nearest_noise_values(
        sector_object["grid"][field], LeftXCoord, RightXCoord, TopYCoord, BottomYCoord
    )

    if Corners == False:
        return False

    (
        BottomLeftCornerAlpha,
        TopLeftCornerAlpha,
        BottomRightCornerAlpha,
        TopRightCornerAlpha,
    ) = Corners

    interp_ratio_x = noise_x - LeftXCoord
    interp_ratio_y = noise_y - BottomYCoord

    interpolated_x_start = BottomLeftCornerAlpha + interp_ratio_x * (
        BottomRightCornerAlpha - BottomLeftCornerAlpha
    )
    interpolated_x_end = TopLeftCornerAlpha + interp_ratio_x * (
        TopRightCornerAlpha - TopLeftCornerAlpha
    )

    output = interpolated_x_start + interp_ratio_y * (
        interpolated_x_end - interpolated_x_start
    )

    return output


def display_perlin_layers(layers, cmap="viridis"):
    """Display multiple layers of Perlin noise."""
    num_layers = len(layers)
    fig, axs = plt.subplots(1, num_layers, figsize=(15, 5))
    for i, layer in enumerate(layers):
        axs[i].imshow(layer, cmap=cmap)
        axs[i].set_title(f"Layer {i + 1}")
        axs[i].axis("off")
    plt.tight_layout()
    plt.show()


def rescale_heightmap(arr, new_min, new_max):

    current_min = np.min(arr)
    current_max = np.max(arr)

    # Rescale to percentile range [0, 1]
    arr_normalized = (arr - current_min) / (current_max - current_min)

    current_min = np.min(arr_normalized)
    current_max = np.max(arr_normalized)

    # Scale to the new range [new_min, new_max]
    arr_rescaled = arr_normalized * (new_max - new_min) + new_min

    return arr_rescaled


def bleed(data, dir, strength=0.2, iterations=30, size=1):
    # I forgot I made this! Correlary in sectors.py that concerns the same process.

    data = np.array(data, dtype=float)  # Convert to float for incremental changes
    rows, cols = data.shape
    for _ in range(iterations):
        # Copy the current state to a new array for updates
        new_data = data.copy()
        for i in range(0, rows):
            for j in range(0, cols):
                # Neighbor values
                neighbors = data[
                    max(i - size, 0) : min(i + 1 + size, rows),
                    max(j - size, 0) : min(j + 1 + size, cols),
                ]
                # Propagate higher values only
                # high_values = neighbors[neighbors > data[i, j]]
                nearby = list(itertools.chain(*neighbors))
                if len(nearby):
                    highest_value = min(nearby) if dir == "min" else max(nearby)

                    increment = strength * (highest_value - data[i, j])
                    new_data[i, j] += increment
        data = new_data  # Update the data for the next iteration
    return data


def convert_noise_to_real_pos(noise_x, noise_y, sector_data):

    sector_x, sector_y = sector_data["x"], sector_data["y"]

    # sector x/y are integers relative to the overall grid (-3 to 4)
    # virtual x/y are floats fractions within the sector (0 to 1)
    # noise x/y are integers related to points within the sector (0 to span-1)

    virtual_x = noise_x / (cfg.get("noise_grid_per_sector") - 1)
    virtual_y = noise_y / (cfg.get("noise_grid_per_sector") - 1)

    real_x = (sector_x + virtual_x) * cfg.get("sector_real_size")
    real_y = (sector_y + virtual_y) * cfg.get("sector_real_size")

    return real_x, real_y


def convert_real_to_noise_pos(position, sector_data):

    sector_x, sector_y = sector_data["x"], sector_data["y"]
    real_x, real_y, _ = position

    # sector x/y are integers relative to the overall grid (-3 to 4)
    # virtual x/y are floats fractions within the sector (0 to 1)
    # noise x/y are integers related to points within the sector (0 to span-1)

    virtual_x = (real_x / cfg.get("sector_real_size")) - sector_x
    virtual_y = (real_y / cfg.get("sector_real_size")) - sector_y

    noise_x = virtual_x * (cfg.get("noise_grid_per_sector") - 1)
    noise_y = virtual_y * (cfg.get("noise_grid_per_sector") - 1)

    return noise_x, noise_y


def sector_vertical_limits(sector_data, terrain_block):

    # Floor and ceiling are brushes. The displacement has to stay inside them
    # or the corner of the sector shows the void. These are limits, not targets.
    lo = sector_data["floor"] * 16 + terrain_block["height_terrain_minimum_to_floor"]
    hi = sector_data["ceiling"] * 16 - terrain_block["height_terrain_minimum_to_ceiling"]
    if hi < lo:
        hi = lo
    return lo, hi


def generate_sector_heightmaps():

    # minmap / maxmap start as the local floor and ceiling limits. They are
    # not a ramp. The ramp is built later, inside those limits. Spreading
    # (sectors.blur_min_max_grids) then pulls a high floor or a low ceiling
    # across the border at the configured slope.

    terrain_block = terrain.get()
    span = cfg.get("noise_grid_per_sector")

    for sector_data in sectors.get_all().values():

        sector_data["grid"]["minmap"] = tools.blank_list_grid(2, span, 0)
        sector_data["grid"]["maxmap"] = tools.blank_list_grid(2, span, 0)
        sector_data["grid"]["height"] = tools.blank_list_grid(2, span, 0)

        lo, hi = sector_vertical_limits(sector_data, terrain_block)

        for noise_x in range(span):
            for noise_y in range(span):
                sector_data["grid"]["minmap"][noise_x][noise_y][0] = lo
                sector_data["grid"]["maxmap"][noise_x][noise_y][0] = hi

    tools.stopwatch_click("submodule", "Sector Generation done")


def _track_samples(sector_data, x, y, radius, scan_cap):

    # Samples inside a radius, nearest first. A fixed k of 6-8 only reaches
    # a couple of hundred units along the near rail, so the other rail pops
    # into the set already closer than the near one and the blended z jumps.
    # The radius is chosen by the caller from the nearest hit. scipy's ball
    # query is the whole neighborhood; the cap is only a safety stop.
    tree = sector_data.get("kdtree")
    points = sector_data.get("points")
    if points is None:
        points = sector_data.get("kdtree_data")
    if tree is None or points is None or len(points) == 0:
        return []

    if len(points) == 1:
        point = points[0]
        dist = math.hypot(float(point[0]) - x, float(point[1]) - y)
        return [(dist, float(point[0]), float(point[1]), float(point[2]))]

    idxs = tree.query_ball_point((x, y), radius)
    if not idxs:
        dist, idx = tree.query((x, y))
        idxs = [int(idx)]
        dists = [float(dist)]
    else:
        dists = None

    samples = []
    for n, idx in enumerate(idxs):
        idx = int(idx)
        if idx < 0 or idx >= len(points):
            continue
        point = points[idx]
        px, py, pz = float(point[0]), float(point[1]), float(point[2])
        if dists is None:
            dist = math.hypot(px - x, py - y)
        else:
            dist = dists[n]
        if not math.isfinite(dist):
            continue
        samples.append((dist, px, py, pz))

    samples.sort(key=lambda sample: sample[0])
    cap = int(scan_cap)
    if cap > 0 and len(samples) > cap:
        samples = samples[:cap]
    return samples


def _smooth_min_pair(a, b, blend):

    # Polynomial smooth-min. Outside `blend` it is exactly min(a, b), so a
    # far rail does not pull the distance down. Inside the blend the crease
    # is rounded; when a == b the result is min - blend/4, a shallow saddle
    # rather than a V. Log-sum-exp is not used: with a pile of samples it
    # subtracts log(n)/sharpness and the distance collapses to 0.
    if blend <= 0.0:
        return a if a < b else b
    diff = abs(a - b)
    if diff >= blend:
        return a if a < b else b
    h = (blend - diff) / blend
    smaller = a if a < b else b
    return smaller - h * h * blend * 0.25


def _smooth_min_tracks(distances, blend):

    if not distances:
        return 0.0
    ordered = sorted(distances)
    acc = ordered[0]
    for dist in ordered[1:]:
        acc = _smooth_min_pair(acc, dist, blend)
    return acc


def _blended_track_z(tracks, power):

    # One weight per rail, not per sample. On the midline the two distances
    # match and z is the average. A rail under the query owns the answer.
    power = max(float(power), 0.01)
    touching = [track[3] for track in tracks if track[0] <= 1.0]
    if touching:
        return sum(touching) / len(touching)

    total = 0.0
    weight_sum = 0.0
    for dist, _x, _y, z in tracks:
        weight = 1.0 / (max(dist, 1.0) ** power)
        total += weight * z
        weight_sum += weight
    return total / weight_sum


def _distinct_tracks(samples, cluster_xy, cluster_z, limit, blend):

    # Chain samples into rails. Comparing only against the nearest sample of
    # a rail splits one tangent into several "tracks" once the chain is longer
    # than cluster_xy; comparing against every accepted sample lets the chain
    # run. Stop once we already have enough rails and the next sample is past
    # the saddle blend — anything further cannot move the smooth distance.
    tracks = []
    members = []

    for dist, x, y, z in samples:
        same_track = False
        for _md, mx, my, mz in members:
            if abs(z - mz) <= cluster_z and math.hypot(x - mx, y - my) <= cluster_xy:
                same_track = True
                break
        members.append((dist, x, y, z))
        if same_track:
            continue
        tracks.append((dist, x, y, z))
        if len(tracks) >= limit and dist > tracks[0][0] + blend:
            break
        if len(tracks) >= max(limit, 1) * 3:
            break
    return tracks


def track_field(sector_data, x, y, terrain_block):

    # Smooth distance and a blended rail height, plus the distinct nearby
    # rails the carve has to clear. No samples → "this node is not near track".
    tree = sector_data.get("kdtree")
    points = sector_data.get("points")
    if points is None:
        points = sector_data.get("kdtree_data")
    if tree is None or points is None or len(points) == 0:
        return {"distance": 1e10, "z": None, "tracks": [], "nearest": 1e10}

    nearest_dist, _idx = tree.query((x, y))
    nearest_dist = float(nearest_dist)
    if not math.isfinite(nearest_dist):
        return {"distance": 1e10, "z": None, "tracks": [], "nearest": 1e10}

    blend = max(float(terrain_block.get("track_smooth_length", 240)), 1.0)
    ratio = max(float(terrain_block.get("track_blend_ratio", 4.0)), 1.0)
    # Far enough that a second rail still in the saddle blend is in the ball,
    # including when we are sitting on the near rail (nearest ≈ 0).
    radius = max(nearest_dist * ratio, nearest_dist + blend, blend)
    samples = _track_samples(
        sector_data,
        x,
        y,
        radius,
        terrain_block.get("track_field_scan_cap", 96),
    )
    if not samples:
        return {"distance": 1e10, "z": None, "tracks": [], "nearest": nearest_dist}

    tracks = _distinct_tracks(
        samples,
        float(terrain_block.get("track_cluster_distance", 200)),
        float(terrain_block.get("track_cluster_height", 64)),
        int(terrain_block.get("track_carve_count", 3)),
        blend,
    )
    if not tracks:
        return {"distance": 1e10, "z": None, "tracks": [], "nearest": nearest_dist}

    distance = _smooth_min_tracks([track[0] for track in tracks], blend)
    return {
        "distance": max(0.0, distance),
        "z": _blended_track_z(tracks, terrain_block.get("track_z_power", 2)),
        "tracks": tracks,
        "nearest": nearest_dist,
    }


def ramp_rise(run, target_rise, near_slope, flank_slope, near_run):

    # Height above the rail bed after `run` units of horizontal travel.
    #
    # The slope envelope starts at near_slope (the cut shoulder, 2:1 in the
    # shipped config — the same rise/run as noise_floor_ceiling_spillover_slope)
    # and eases down toward flank_slope (about 1:1, gentler than the cut).
    # That envelope is integrated into u(run). The actual rise is
    # target * (1 - exp(-u / target)): derivative at the rail is near_slope,
    # it never exceeds the envelope, and it eases off to 0 as it approaches
    # the target instead of riding a straight line into the ceiling.
    #
    # A short sector has a small target, so the exp term dies quickly and the
    # horizon is up within a sector. A tall sector has a large target, so the
    # same shoulder slope only covers a fraction of the headroom and the rest
    # of the hillside stays near flank_slope. No cliff, no squashed short sector.
    if run <= 0.0 or target_rise <= 0.0:
        return 0.0

    near_slope = max(float(near_slope), 0.0)
    flank_slope = min(max(float(flank_slope), 0.0), near_slope)
    near_run = max(float(near_run), 1.0)

    extra = near_slope - flank_slope
    decay = math.exp(-run / near_run)
    integrated = flank_slope * run + extra * near_run * (1.0 - decay)
    return target_rise * (1.0 - math.exp(-integrated / target_rise))


def _slope_cap(terrain_block):

    # Reuse the existing cut steepness when a terrain block does not say.
    # noise_floor_ceiling_spillover_slope is 2 in the shipped config: 2 up, 1 across.
    if "ramp_near_slope" in terrain_block:
        return float(terrain_block["ramp_near_slope"])
    return float(cfg.get("noise_floor_ceiling_spillover_slope"))


def carve_deviation(distance, terrain_block, slope_cap):

    # How far above or below the rail bed the ground is allowed to be.
    # The power curve is the old cut: flat across cut_basewidth, then
    # steepening. A pointwise min() against `slope * run` does not actually
    # cap the slope — the curve sits under the line and then catches up in
    # one steep step. Instead, follow the power curve only while its
    # derivative is under the cap, and continue in a straight line at
    # slope_cap after that. The trench wall eases up to the cut slope
    # (2:1 in the shipped config) and never goes past it.
    run = max(0.0, distance - terrain_block["cut_basewidth"])
    scale = float(terrain_block["cut_scale"])
    if scale <= 0.0 or run <= 0.0:
        return 0.0

    power = float(terrain_block["cut_power"])
    slump = float(terrain_block["cut_slump"])
    raw = math.pow(run / scale, power) * scale * slump
    if slope_cap <= 0.0:
        return raw

    if power <= 1.0:
        return min(raw, run * slope_cap)

    # raw'(run) = power * slump * (run/scale)^(power-1)
    deriv = power * slump * math.pow(run / scale, power - 1.0)
    if deriv <= slope_cap:
        return raw

    ratio = slope_cap / (power * slump)
    run_hit = scale * math.pow(ratio, 1.0 / (power - 1.0))
    raw_hit = math.pow(run_hit / scale, power) * scale * slump
    return raw_hit + slope_cap * (run - run_hit)


def carve_to_tracks(height, tracks, terrain_block):

    # Every distinct nearby rail contributes a window around its own bed.
    # The ground has to sit in ALL of those windows. The upper edge is what
    # stops a second, lower rail from being buried. If the windows do not
    # overlap (two rails at very different heights in the same cut), the
    # upper edge wins: leave the higher rail in the air rather than fill
    # over the lower one.
    if not tracks:
        return height

    slope_cap = _slope_cap(terrain_block)
    offset = terrain_block["height_track_to_terrain"]
    lower = None
    upper = None

    for dist, _x, _y, z in tracks:
        bed = z + offset
        deviation = carve_deviation(dist, terrain_block, slope_cap)
        low = bed - deviation
        high = bed + deviation
        lower = low if lower is None else max(lower, low)
        upper = high if upper is None else min(upper, high)

    if lower > upper:
        lower = upper
    return min(max(height, lower), upper)


def _node_limits(sector_data, noise_x, noise_y, terrain_block):

    local_lo, local_hi = sector_vertical_limits(sector_data, terrain_block)
    lo = sector_data["grid"]["minmap"][noise_x][noise_y][0]
    hi = sector_data["grid"]["maxmap"][noise_x][noise_y][0]
    lo = max(lo, local_lo)
    hi = min(hi, local_hi)
    if lo > hi:
        # A high floor spreading in from one neighbor and a low ceiling from
        # another can cross. Fall back to this sector's own box; the clamp
        # pass then projects shared nodes into every sector that owns them.
        return local_lo, local_hi
    return lo, hi


def _mountain_mask(terrain_block, x, y, z):

    raw = noisefield.sample_named(terrain_block, "mountain", x, y, z)
    raw = tools.clamped(raw, -1.0, 1.0)
    coverage = float(terrain_block.get("mountain_coverage", 0.45))
    gain = float(terrain_block.get("mountain_gain", 1.35))
    # Bias the signed field so `coverage` is roughly how much of the map is
    # mountainous, then smoothstep it into a 0..1 mask. This is a bias, not
    # an exact area fraction — the warp and the octaves move it around.
    shifted = raw * gain + (coverage - 0.5) * 2.0
    unit = tools.clamped(shifted * 0.5 + 0.5, 0.0, 1.0)
    return unit * unit * (3.0 - 2.0 * unit)


def _terrace_run(run, terrain_block, x, y, z):

    # Move the distance the ramp is evaluated at. Where the noise rises along
    # the slope the ramp is sampled further ahead (a steeper pitch); where it
    # falls, the ramp is sampled behind (a bench / a hold). The amplitude is
    # in map units and is meant to stay under about a sixth of the terrace
    # wavelength, so the warp is mostly monotone as you walk away from the rail.
    amplitude = float(terrain_block.get("terrace_distance", 0.0))
    if amplitude == 0.0 or run <= 0.0:
        return run
    noise = tools.clamped(
        noisefield.sample_named(terrain_block, "terrace", x, y, z), -1.0, 1.0
    )
    # Full warp is reached over one amplitude of travel. A node just outside
    # the flat pad is not thrown hundreds of units up the ramp.
    fade = min(1.0, run / amplitude)
    return max(0.0, run + amplitude * noise * fade)


def height_at_node(sector_data, noise_x, noise_y, terrain_block):

    real_x, real_y = convert_noise_to_real_pos(noise_x, noise_y, sector_data)
    # Stacked sectors must not sample the same horizontal slice of noise.
    noise_z = sector_data["floor"] * 16
    info = track_field(sector_data, real_x, real_y, terrain_block)
    lo, hi = _node_limits(sector_data, noise_x, noise_y, terrain_block)

    if info["z"] is None:
        bed = lo
    else:
        bed = info["z"] + terrain_block["height_track_to_terrain"]
    bed = tools.clamped(bed, lo, hi)

    headroom = hi - bed
    mask = _mountain_mask(terrain_block, real_x, real_y, noise_z)
    fraction = tools.linterp(
        float(terrain_block.get("flat_horizon_fraction", 0.3)),
        float(terrain_block.get("mountain_horizon_fraction", 0.95)),
        mask,
    )
    target = headroom * fraction

    flat = float(terrain_block.get("height_terrain_flat_in_radius_around_track", 0.0))
    run = max(0.0, info["distance"] - flat)
    run = _terrace_run(run, terrain_block, real_x, real_y, noise_z)
    rise = ramp_rise(
        run,
        target,
        _slope_cap(terrain_block),
        float(terrain_block.get("ramp_flank_slope", 1.0)),
        float(terrain_block.get("ramp_near_run", 512)),
    )

    detail = float(terrain_block.get("detail_amplitude", 0.0))
    if detail != 0.0:
        grit = noisefield.sample_named(terrain_block, "detail", real_x, real_y, noise_z)
        rise += detail * grit

    height = tools.clamped(bed + rise, lo, hi)
    height = carve_to_tracks(height, info["tracks"], terrain_block)
    return tools.clamped(height, lo, hi)


def clamp_existing_height(sector_data, noise_x, noise_y, terrain_block, height):

    # Used after a blur pass. The blurred value is kept; it is only pulled
    # back into the floor/ceiling envelope and into every nearby rail's carve.
    # Doing this every pass is what makes the neighbors slope into the cut
    # instead of the average lifting the ground back over the rails.
    real_x, real_y = convert_noise_to_real_pos(noise_x, noise_y, sector_data)
    info = track_field(sector_data, real_x, real_y, terrain_block)
    lo, hi = _node_limits(sector_data, noise_x, noise_y, terrain_block)
    height = tools.clamped(height, lo, hi)
    height = carve_to_tracks(height, info["tracks"], terrain_block)
    return tools.clamped(height, lo, hi)


def cut_and_fill_sector_heightmaps():

    terrain_block = terrain.get()

    for sector_data in sectors.get_all().values():

        height = sector_data["grid"]["height"]
        span = range(len(height))

        for noise_x in span:
            for noise_y in span:
                height[noise_x][noise_y][0] = height_at_node(
                    sector_data, noise_x, noise_y, terrain_block
                )

    tools.stopwatch_click("submodule", "Contours Pass completed")


def clamp_heightmaps(terrain_block=None):

    if terrain_block is None:
        terrain_block = terrain.get()

    for sector_data in sectors.get_all().values():

        height = sector_data["grid"]["height"]
        span = range(len(height))

        for noise_x in span:
            for noise_y in span:
                height[noise_x][noise_y][0] = clamp_existing_height(
                    sector_data,
                    noise_x,
                    noise_y,
                    terrain_block,
                    height[noise_x][noise_y][0],
                )


def relax_heightmaps():

    # Blur, then re-clamp, and repeat. The clamp writes back into the shared
    # edge cells, so the next blur sees the cut and the floor/ceiling and
    # pulls the neighbors toward them.
    terrain_block = terrain.get()
    passes = max(int(terrain_block.get("height_blur_passes", 3)), 0)

    for _ in range(passes):
        sectors.blur_heightmap_grid(announce=False)
        clamp_heightmaps(terrain_block)

    clamp_heightmaps(terrain_block)
    tools.stopwatch_click("submodule", "Heightmap relaxed")


def query_field(field, position, sector_data=None) -> float:

    if sector_data is None:

        sector_data = sectors.get(sectors.get_sector_id_at_position(position))

    if sector_data is None:
        return 8.8888  # special "this value does not exist" float

    else:

        noise_x, noise_y = convert_real_to_noise_pos(position, sector_data)

        height = field_interpolator(sector_data, field, noise_x, noise_y)

        return height


def curb_noise(v):
    """if v < -curb_start:
        residual = (v + curb_start) * (curb_width)
        return -curb_start + residual

    elif v > curb_start:
        residual = (v - curb_start) * (curb_width)
        return curb_start + residual
    else:
        return v"""
    if v > 0.5 or v < -0.5:
        return -v
    else:
        return v


def sample_realspace_noise(position):

    # Surface grit. The big mountain shape is the "mountain" field; this is
    # the small roughness added on top of the ramp. Kept as a function because
    # older call sites asked for "the" realspace noise.
    x, y, z = position
    return noisefield.sample_named(terrain.get(), "detail", x, y, z)


def height_sample(real_x, real_y, samples, radius, sector_data) -> list[float]:

    guess_z = query_field("height", (real_x, real_y, 0), sector_data)

    # start with one in the center for good measure
    Heights = [guess_z]

    SectorSize = 360 / samples
    Arm = [radius, 0]

    for Slice in range(samples):

        offset = tools.rot2(Arm, Slice * SectorSize)

        Example = query_field(
            "height", (real_x + offset[0], real_y + offset[1], guess_z)
        )

        if Example != 8.8888:
            Heights += [Example]

    return Heights


def query_alpha(position, Terrain, sector_data):

    Radius = 20
    MaxAlpha = 255

    Distance_To_Line, _ = sectors.distance_to_line(position, sector_data)

    HeightSamples = height_sample(position[0], position[1], 6, Radius, sector_data)

    # remake this to calculate the slope between the 2 steepest entries
    LocalSlope = (max(HeightSamples) - min(HeightSamples)) / (Radius * 2)
    SlopeTarget = Terrain.get("alpha_steepness_cutoff", 0.75)
    TransitionLength = Terrain.get("alpha_steepness_transition", 0.75)

    if TransitionLength == 0:
        SlopeMetric = 1 if LocalSlope < SlopeTarget else 0
    else:
        SlopeMetric = 0.5 - (LocalSlope - SlopeTarget) / TransitionLength

    DistanceMetric = (
        max(Distance_To_Line - Terrain.get("ballast_alpha_distance", 96), 0)
        / Terrain.get("ballast_alpha_slope", 200)
    ) * MaxAlpha
    SteepnessMetric = SlopeMetric * MaxAlpha
    NoiseMetric = random.uniform(-0.5, 0.5) * Terrain.get(
        "alpha_from_noise_multiplier", 50
    )
    TerrainMult = Terrain.get("alpha_multiplier", 1)

    BaseAlpha = min(DistanceMetric, SteepnessMetric)
    AdjustedAlpha = tools.scale(BaseAlpha, TerrainMult, MaxAlpha)

    return tools.clamped(AdjustedAlpha + NoiseMetric, 0, MaxAlpha)
