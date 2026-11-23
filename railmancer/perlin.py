"""Classic improved Perlin noise, vectorized with NumPy.

`pnoise3` matches the call the old `noise` package used: coordinates, then
octaves, persistence, lacunarity, and a `base` that picks the permutation.
The table is shuffled from `base` with the stdlib RNG, so the same base is
the same field on every machine. Values sit around -1..1 for one octave and
are centered on 0. They are not bit-identical to that package.

A scalar call returns a float. An array call returns an array of the same
shape, and each entry matches the scalar call.
"""

import random

import numpy as np

# 12 edge-midpoint gradients of the cube. The last four repeat so a nibble
# (0..15) indexes the table the way Perlin's grad() does.
_GRADS = np.array(
    [
        [1, 1, 0],
        [-1, 1, 0],
        [1, -1, 0],
        [-1, -1, 0],
        [1, 0, 1],
        [-1, 0, 1],
        [1, 0, -1],
        [-1, 0, -1],
        [0, 1, 1],
        [0, -1, 1],
        [0, 1, -1],
        [0, -1, -1],
        [1, 1, 0],
        [-1, 1, 0],
        [0, -1, 1],
        [0, -1, -1],
    ],
    dtype=float,
)

_PERMS = {}


def _permutation(base):

    # stdlib Random, not NumPy's, so the table does not move between NumPy
    # releases. `base` is the same integer pnoise3 used to offset its hash.
    key = int(base) & 0xFFFFFFFF
    cached = _PERMS.get(key)
    if cached is not None:
        return cached
    table = list(range(256))
    random.Random(key).shuffle(table)
    perm = np.asarray(table + table, dtype=np.int32)
    _PERMS[key] = perm
    return perm


def _fade(t):

    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def _lattice(coord, period):

    # Integer cell, and the fraction inside it. A positive period tiles the
    # lattice the way the old pnoise3 `repeat*` arguments did.
    base = np.floor(coord)
    frac = coord - base
    cell = base.astype(np.int64)
    if period and period > 0:
        cell = cell % int(period)
    return cell, frac


def _noise3(x, y, z, perm, repeatx, repeaty, repeatz):

    xi, xf = _lattice(x, repeatx)
    yi, yf = _lattice(y, repeaty)
    zi, zf = _lattice(z, repeatz)
    u = _fade(xf)
    v = _fade(yf)
    w = _fade(zf)

    xi = xi & 255
    yi = yi & 255
    zi = zi & 255
    x1 = (xi + 1) & 255
    y1 = (yi + 1) & 255
    z1 = (zi + 1) & 255

    def hashed(ix, iy, iz):
        return perm[perm[perm[ix] + iy] + iz] & 15

    def contrib(ix, iy, iz, dx, dy, dz):
        g = _GRADS[hashed(ix, iy, iz)]
        return g[..., 0] * dx + g[..., 1] * dy + g[..., 2] * dz

    n000 = contrib(xi, yi, zi, xf, yf, zf)
    n100 = contrib(x1, yi, zi, xf - 1.0, yf, zf)
    n010 = contrib(xi, y1, zi, xf, yf - 1.0, zf)
    n110 = contrib(x1, y1, zi, xf - 1.0, yf - 1.0, zf)
    n001 = contrib(xi, yi, z1, xf, yf, zf - 1.0)
    n101 = contrib(x1, yi, z1, xf - 1.0, yf, zf - 1.0)
    n011 = contrib(xi, y1, z1, xf, yf - 1.0, zf - 1.0)
    n111 = contrib(x1, y1, z1, xf - 1.0, yf - 1.0, zf - 1.0)

    nx00 = n000 + u * (n100 - n000)
    nx10 = n010 + u * (n110 - n010)
    nx01 = n001 + u * (n101 - n001)
    nx11 = n011 + u * (n111 - n011)
    nxy0 = nx00 + v * (nx10 - nx00)
    nxy1 = nx01 + v * (nx11 - nx01)
    return nxy0 + w * (nxy1 - nxy0)


def _as_arrays(x, y, z):

    scalar = np.isscalar(x) and np.isscalar(y) and np.isscalar(z)
    xa = np.asarray(x, dtype=float)
    ya = np.asarray(y, dtype=float)
    za = np.asarray(z, dtype=float)
    return scalar, xa, ya, za


def _fbm(noise_at, octaves, persistence, lacunarity):

    # Geometric stack, same shape as the old pnoise*: each octave is the
    # previous amplitude times persistence, and the coordinates times
    # lacunarity. The sum is not renormalized, so one octave stays in the
    # single-noise range and extra octaves can push a little past it.
    def wrapped(x, y, z, perm, repeatx, repeaty, repeatz):
        octaves_i = max(int(octaves), 1)
        amp = 1.0
        freq = 1.0
        total = np.zeros(np.broadcast(x, y, z).shape, dtype=float)
        for _ in range(octaves_i):
            total = total + amp * noise_at(
                x * freq, y * freq, z * freq, perm, repeatx, repeaty, repeatz
            )
            amp *= float(persistence)
            freq *= float(lacunarity)
        return total

    return wrapped


def pnoise3(
    x,
    y,
    z,
    octaves=1,
    persistence=0.5,
    lacunarity=2.0,
    repeatx=1024,
    repeaty=1024,
    repeatz=1024,
    base=0,
):

    scalar, xa, ya, za = _as_arrays(x, y, z)
    perm = _permutation(base)
    value = _fbm(_noise3, octaves, persistence, lacunarity)(
        xa, ya, za, perm, repeatx, repeaty, repeatz
    )
    if scalar:
        return float(np.reshape(value, ()))
    return value


def _noise2(x, y, _z, perm, repeatx, repeaty, _repeatz):

    # z is unused. pnoise2 is the 2D field the reference histogram asks for.
    xi, xf = _lattice(x, repeatx)
    yi, yf = _lattice(y, repeaty)
    u = _fade(xf)
    v = _fade(yf)
    xi = xi & 255
    yi = yi & 255
    x1 = (xi + 1) & 255
    y1 = (yi + 1) & 255

    def hashed(ix, iy):
        return perm[perm[ix] + iy] & 15

    def contrib(ix, iy, dx, dy):
        g = _GRADS[hashed(ix, iy)]
        return g[..., 0] * dx + g[..., 1] * dy

    n00 = contrib(xi, yi, xf, yf)
    n10 = contrib(x1, yi, xf - 1.0, yf)
    n01 = contrib(xi, y1, xf, yf - 1.0)
    n11 = contrib(x1, y1, xf - 1.0, yf - 1.0)
    nx0 = n00 + u * (n10 - n00)
    nx1 = n01 + u * (n11 - n01)
    return nx0 + v * (nx1 - nx0)


def pnoise2(
    x,
    y,
    octaves=1,
    persistence=0.5,
    lacunarity=2.0,
    repeatx=1024,
    repeaty=1024,
    base=0,
):

    scalar = np.isscalar(x) and np.isscalar(y)
    xa = np.asarray(x, dtype=float)
    ya = np.asarray(y, dtype=float)
    perm = _permutation(base)
    value = _fbm(_noise2, octaves, persistence, lacunarity)(
        xa, ya, xa, perm, repeatx, repeaty, 0
    )
    if scalar:
        return float(np.reshape(value, ()))
    return value
