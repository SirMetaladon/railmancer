"""Small named noise fields.

A terrain block can carry several fields under "noise_fields". Each one is a
spec dict. Sample any of them by name from a world position. The same helper
is what heightmaps use for mountains, terrace warp, and surface grit, and it
is the thing to call later for biome masks.

Spec keys (all optional except a scale):

    scale            long-axis wavelength, in map units
    scale_sectors    long-axis wavelength, in sectors (used when scale is absent)
    anisotropy       short axis / long axis. 1 is round. 0.25 is a ridge four
                     times longer than it is wide (a 2-sector mountain with
                     this anisotropy is about 0.5 by 2 sectors).
    octaves          fbm octaves (default 1)
    persistence      fbm persistence (default 0.5)
    lacunarity       fbm lacunarity (default 2)
    warp             domain-warp strength, in fractions of the long wavelength
    rotation_sectors wavelength of the angle field, in sectors. 0 keeps the
                     long axis pointed along world X. The angle itself comes
                     from low-frequency noise, so neighboring ridges do not
                     share a heading.
    seed_offset      added to the terrain seed so two fields do not repeat

sample_spec / sample_named return the raw fbm value, roughly -1 to 1.
"""

import math

from railmancer.perlin import pnoise3

from railmancer import cfg


def sample_named(terrain, name, x, y, z=0.0):

    fields = terrain.get("noise_fields") or {}
    spec = fields.get(name)
    if not spec:
        return 0.0
    return sample_spec(spec, terrain.get("seed", 0), x, y, z)


def sample_spec(spec, seed, x, y, z=0.0):

    long_scale = _long_scale(spec)
    anisotropy = max(float(spec.get("anisotropy", 1.0)), 0.05)
    short_scale = long_scale * anisotropy

    octaves = max(int(spec.get("octaves", 1)), 1)
    persistence = float(spec.get("persistence", 0.5))
    lacunarity = float(spec.get("lacunarity", 2.0))
    warp = float(spec.get("warp", 0.0))
    base = _base(seed, spec.get("seed_offset", 0))

    angle = 0.0
    rotation_sectors = float(spec.get("rotation_sectors", 0.0))
    if rotation_sectors > 0.0:
        rotation_scale = max(rotation_sectors * _sector_size(), 1.0)
        # pnoise is about -1..1, so this swings most of a half-turn either way.
        angle = (
            pnoise3(
                x / rotation_scale,
                y / rotation_scale,
                0.17,
                octaves=1,
                base=base + 101,
            )
            * math.pi
        )

    ca = math.cos(angle)
    sa = math.sin(angle)
    xr = (x * ca - y * sa) / long_scale
    yr = (x * sa + y * ca) / short_scale
    zr = z / long_scale

    if warp != 0.0:
        wx = pnoise3(xr + 3.1, yr + 1.7, zr + 0.2, octaves=1, base=base + 203)
        wy = pnoise3(xr + 8.2, yr + 4.4, zr + 0.9, octaves=1, base=base + 307)
        xr += warp * wx
        yr += warp * wy

    return pnoise3(
        xr,
        yr,
        zr + 0.37,
        octaves=octaves,
        persistence=persistence,
        lacunarity=lacunarity,
        base=base + 409,
    )


def _long_scale(spec):

    if spec.get("scale") is not None:
        return max(float(spec["scale"]), 1.0)
    return max(float(spec.get("scale_sectors", 1.0)) * _sector_size(), 1.0)


def _sector_size():

    try:
        size = float(cfg.get("sector_real_size"))
    except Exception:
        size = 3264.0
    return max(size, 1.0)


def _base(seed, offset):

    try:
        value = int(seed) + int(offset)
    except (TypeError, ValueError):
        value = int(offset)
    # The noise permutation table is indexed with this int. Keep it positive.
    return abs(value) % 65536
