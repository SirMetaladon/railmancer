import numpy as np
from scipy.spatial import KDTree


def point_generator(
    density_field,
    bounds,
    num_dots,
    minimum_spacing,
    resolution=1000,
):
    """
    Generate dots distributed according to a density field, with improved apportioning.

    Parameters:
        density_field: function that takes (x, y) and returns the density value.
        bounds: tuple of ((x_min, x_max), (y_min, y_max)) for the plane bounds.
        num_dots: int, the number of dots to generate.
        resolution: int, the grid resolution for sampling probabilities.

    Returns:
        np.ndarray of shape (N, 2) with dot coordinates.
    """
    x_min, x_max = bounds[0]
    y_min, y_max = bounds[1]

    # Create a grid over the plane
    x_vals = np.linspace(x_min, x_max, resolution)
    y_vals = np.linspace(y_min, y_max, resolution)
    xx, yy = np.meshgrid(x_vals, y_vals)

    # Compute density values on the grid
    density_grid = np.vectorize(density_field)(xx, yy)
    density_grid = np.maximum(density_grid, 0)  # Ensure no negative densities

    # Normalize density values to create a probability distribution
    density_sum = np.sum(density_grid)
    if density_sum == 0:
        raise ValueError("Density field integrates to zero; no dots can be placed.")
    density_prob = density_grid / density_sum

    # Flatten grid for sampling
    flat_prob = density_prob.flatten()
    flat_x = xx.flatten()
    flat_y = yy.flatten()

    # Sample indices from the flattened grid based on the density probabilities
    sampled_indices = np.random.choice(len(flat_prob), size=num_dots, p=flat_prob)
    sampled_points = np.column_stack((flat_x[sampled_indices], flat_y[sampled_indices]))

    # Enforce minimum distance constraint using KD-tree
    dots = []
    kdtree = None
    for x, y in sampled_points:
        density = density_field(x, y)
        if density <= 0:
            continue

        if kdtree:
            distances, _ = kdtree.query([x, y], k=1)
            if distances < minimum_spacing:
                continue

        # Accept the point
        dots.append((x, y))
        kdtree = KDTree(dots)

    return np.array(dots)


# Example usage
def density_field(x, y):
    """A sample density field: higher density near the origin."""
    return max(
        (1 / x) + (1 / y) + (1 / abs(4080 - (x))) + (1 / abs(4080 - (y))),
        0,
    )  # max(1 - 1 * (math.sin(y) + math.sin(x)*0.5 + math.cos(x+y/3)), 0)


"""
bounds = ((30, 4050), (30, 4050))
num_dots = 250

dots = point_generator(density_field, bounds, num_dots)


# Plot the result
import matplotlib.pyplot as plt

# Plot the result
plt.figure(figsize=(8, 8))
plt.scatter(dots[:, 0], dots[:, 1], s=2, c="blue", alpha=0.7)
plt.title("Improved Dot Distribution Based on Density Field")
plt.xlabel("x")
plt.ylabel("y")
plt.show()"""
