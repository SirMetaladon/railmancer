import numpy as np
from noise import pnoise2
import matplotlib.pyplot as plt
import random


def bilinear_interpolation(Z, x, y):

    if len(Z) <= 1:
        return 0

    x = max(min(0.999, x), 0) * (len(Z) - 1)
    y = max(min(0.999, y), 0) * (len(Z[0]) - 1)

    # 1, 1 on a 3x3 grid
    # 1 * 3-1 = 1
    # let's get the outcome straight
    # 1,1 should refer to the 2nd-to-last vertex (so the last vertex can interpolate)
    # 0,0 should refer to the first vertex (0)

    # convert x,y 0-1 to grid co-ords relative to the size of Z + bounding
    x0 = int(x)
    y0 = int(y)

    # let's think for a second
    # gridsize = 30
    # 30 * 1 (farthest extent)
    # 30 + 1
    # remove 1, which means it breaks in the case of 1, but that's not even a case where you can interpolate
    # might add an edgecase check for it, why not

    # apparently it needs 2? one for the overflow, one for the +1? idk

    x1, y1 = x0 + 1, y0 + 1

    # Corner values
    Q00 = Z[x0][y0]
    Q01 = Z[x0][y1]
    Q10 = Z[x1][y0]
    Q11 = Z[x1][y1]

    # Interpolation weights
    # situation with the very end; x0 is x-1, so alphax = 1 = most interp possible
    alpha_x = (x) - x0
    alpha_y = (y) - y0

    # Interpolate along x for y0 and y1
    R0 = Q00 + alpha_x * (Q10 - Q00)
    R1 = Q01 + alpha_x * (Q11 - Q01)

    # Interpolate along y
    P = R0 + alpha_y * (R1 - R0)

    return P


def generate_perlin_noise(width, height, scale, octaves, persistence, lacunarity, seed):
    """Generate a 2D array of Perlin noise."""
    noise_array = np.zeros((height, width))
    for y in range(height):
        for x in range(width):
            noise_array[y][x] = pnoise2(
                x / scale,
                y / scale,
                octaves=octaves,
                persistence=persistence,
                lacunarity=lacunarity,
                repeatx=width,
                repeaty=height,
                base=seed,
            )
    return noise_array


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
