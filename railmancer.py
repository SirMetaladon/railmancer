import random
from railmancer import (
    profile,
    heightmap,
    lines,
    compile,
    tools,
    vmfpy,
    parser,
    sectors,
    terrain,
    track,
    trackhammer,
    cfg,
)

# This is where it all comes together. Each step of the process accomplishes a major part of the overall product. Mostly for clarity of flow.


def main():

    trackpack_directory = "C:/Program Files (x86)/Steam/steamapps/common/Source SDK Base 2013 Singleplayer/ep2/custom/trakpak/models/trakpak3_rsg"
    vmf_input_path = "vmf inputs/vancouver_cutoff_test.vmf"

    # Starts a few stopwatches for showing time progression.
    tools.stopwatch_click("total", "Start!")
    tools.stopwatch_click("submodule", "Start!")

    # Initializes CFG parameters for use elsewhere
    cfg.initialize("railmancer/config.json")

    # Assembles a "library" of track pieces from a directory.
    track.build_track_library(trackpack_directory, ".mdl")

    tools.stopwatch_click("submodule", "Initialization complete")

    # Step 1: Import line object from a VMF, as well as the track entities themselves.
    parser.import_track(vmf_input_path)

    tools.stopwatch_click("submodule", "Import complete")

    lines.encode_lines()  # required for exclusion to work
    Start_Node = [[7568, 3552, 1460], "0fw", -90, False]

    trackhammer.initialize()
    trackhammer.exclude_existing()
    trackhammer.generate_mainline(
        Start_Node, 0.5, {"min_radius": 1, "min_grade": 1, "max_grade": 3}
    )
    # 2nd number is distance in miles, will keep going until it's over this value
    # 3rd number is minumum radius, 1 = 3072
    # 4th number is minimum grade level, in this case 0 is level
    # 5th number is maximum grade level, in this case 2.5%

    # Step 2: Generate KDTree for distance to this line; speeds up later processes compared to doing it manually
    lines.encode_lines()
    # these values are stored as global variables in the lines module.

    tools.stopwatch_click("submodule", "Encoding and collapse done")

    # Step 4: Build a sector-map from the blocklist. Dict instead of a list; tells you where the walls are. Also contains a map for "what block is next to this one"
    sectors.initialize()
    sectors.build_fit()
    sectors.link()

    tools.stopwatch_click("submodule", "Sector framework completed")

    sectors.assign_points_to_sectors()

    heightmap.generate_sector_heightmaps()

    tools.stopwatch_click("submodule", "Sector Generation done")

    sectors.merge_edges()

    tools.stopwatch_click("submodule", "Merge edges complete")

    profile.start()
    sectors.blur_min_max_grids()
    profile.end()

    tools.stopwatch_click("submodule", "Blur min-max done")

    heightmap.cut_and_fill_sector_heightmaps()

    tools.stopwatch_click("submodule", "Contours done")

    sectors.blur_heightmap_grid()

    tools.stopwatch_click("submodule", "Smoothed heightmap")

    heightmap.cut_and_fill_sector_heightmaps()

    tools.stopwatch_click("submodule", "Second pass Contours done")

    sectors.collapse_quantum_switchstands()

    profile.start()
    compile.compile_sectors_to_brushes()

    tools.stopwatch_click("submodule", "Brushes and Displacements done")
    profile.end()

    compile.scatter_placables()

    tools.stopwatch_click("submodule", "Scattering complete")

    """points = lines.get_all_track_points()
    for entry in points:
        vmfpy.frog(entry)

    tools.stopwatch_click("submodule", "Frogging the Track, done")"""

    vmfpy.write_to_vmf(f"{"railmancer"}_{random.randint(4000,4999)}{".vmf"}")

    tools.stopwatch_click("total", "Railmancer Finished")


if __name__ == "__main__":
    print("RAILMANCER ACTIVATED")
    main()
