import numpy as np
import matplotlib.pyplot as plt
from noise import pnoise2

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
                base=seed
            )
    return noise_array

def display_perlin_layers(layers, cmap='viridis'):
    """Display multiple layers of Perlin noise."""
    num_layers = len(layers)
    fig, axs = plt.subplots(1, num_layers, figsize=(15, 5))
    for i, layer in enumerate(layers):
        axs[i].imshow(layer, cmap=cmap)
        axs[i].set_title(f'Layer {i + 1}')
        axs[i].axis('off')
    plt.tight_layout()
    plt.show()

# Parameters
width = 256
height = 256
scale = 50.0
octaves_list = [1, 2, 4]
persistence = 0.5
lacunarity = 2.0
seed = 42

# Generate layers of Perlin noise
layers = [
    generate_perlin_noise(width, height, scale, octaves, persistence, lacunarity, seed)
    for octaves in octaves_list
]

# Display the layers
display_perlin_layers(layers)
