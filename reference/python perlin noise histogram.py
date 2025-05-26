import numpy as np
import matplotlib.pyplot as plt
from noise import pnoise2

# Configuration
width = 5000  # X samples
height = 5000  # Y samples
scale = 0.01  # Frequency of noise (lower = smoother)
bins = 100  # Number of bins from -1 to 1
curb_start = 0.4
curb_end = 0.5
curb_width = (curb_end - curb_start) * 2


"""def curb_noise_fullrange(v):
    if v < -curb_start:
        residual = (v + curb_start) * (curb_width)
        return -curb_start + residual

    elif v > curb_start:
        residual = (v - curb_start) * (curb_width)
        return curb_start + residual
    else:
        return v


def curb_noise_fullrange(v):
    if v < -0.45:
        # Remap from [-1.0, -0.45] -> [-0.5, -0.45]
        t = (v + 1.0) / (0.55)  # Map to [0,1]
        t = min(max(t, 0), 1)
        t_curbed = t * t * (3 - 2 * t)  # smoothstep
        return -0.5 + (0.05) * t_curbed  # Range width = 0.05
    elif v > 0.45:
        # Remap from [0.45, 1.0] -> [0.45, 0.5]
        t = (v - 0.45) / (0.55)  # Map to [0,1]
        t = min(max(t, 0), 1)
        t_curbed = t * t * (3 - 2 * t)
        return 0.45 + (0.05) * t_curbed
    else:
        return v"""


def curb_noise_fullrange(v):
    if v < -curb_start:
        residual = (v + curb_start) * (curb_width)
        return -curb_start + residual

    elif v > curb_start:
        residual = (v - curb_start) * (curb_width)
        return curb_start + residual
    else:
        return v


# Sample Perlin noise
values = []
for y in range(height):
    for x in range(width):
        val = pnoise2(x * scale, y * scale)
        val_curbed = curb_noise_fullrange(val)
        values.append(val_curbed)

# Create histogram
hist, bin_edges = np.histogram(values, bins=bins, range=(0.4, 0.55))

# Plot
bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
plt.figure(figsize=(10, 6))
plt.bar(bin_centers, hist, width=(2.0 / bins), edgecolor="black")
plt.title(f"Distribution of 2D Perlin Noise Values ({width}x{height} samples)")
plt.xlabel("Perlin noise value")
plt.ylabel("Frequency")
plt.grid(True)
plt.tight_layout()
plt.show()
