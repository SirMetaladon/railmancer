import numpy as np
from noise import pnoise2
import matplotlib.pyplot as plt
import random


def bilinear_interpolation(Z, x, y):
    # Grid point coordinates
    x0, y0 = int(x), int(y)
    x1, y1 = x0 + 1, y0 + 1

    print(x0, y0, x1, y1)

    # Ensure indices are within bounds
    if x1 >= len(Z) or y1 >= len(Z[0]):
        raise ValueError("Query point is outside the grid bounds")

    # Corner values
    Q00 = Z[x0][y0]
    Q01 = Z[x0][y1]
    Q10 = Z[x1][y0]
    Q11 = Z[x1][y1]

    # Interpolation weights
    alpha_x = x - x0
    alpha_y = y - y0

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
