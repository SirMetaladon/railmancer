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

    # Some input information. One contains the directory for building the Track Library, the other is the VMF for the importer.
    trackpack_directory = "C:/Program Files (x86)/Steam/steamapps/common/Source SDK Base 2013 Singleplayer/ep2/custom/trakpak/models/trakpak3_rsg"
    vmf_input_path = "vmf inputs/squamish exit.vmf"

    # Starts a few stopwatches for showing time progression.
    tools.stopwatch_click("total", "Start!")
    tools.stopwatch_click("submodule", "Start!")

    # Initializes CFG parameters for use elsewhere
    cfg.initialize("railmancer/config.json")
    vmfpy.initialize()

    # Assembles a "library" of track pieces from a directory.
    track.build_track_library(trackpack_directory, ".mdl")

    # Import line objects from a VMF, as well as the track entities themselves.
    parser.import_track(vmf_input_path)
    tools.stopwatch_click("submodule", "Import complete")

    # Generate a mapping for finding the closest point relative to an existing point.
    lines.encode_lines()  # required for exclusion to work
    Vancouver_Start = [[7568, 3552, -12540 - 1500], "0fw", -90, False]  #
    Squamish_Start = [[7072, 3888, 512], "0fw", -90, False]  #

    # Starting from a node, procedurally move forward and place track, finding a path that fits the parameters.
    trackhammer.initialize()
    trackhammer.exclude_existing()
    """trackhammer.generate_mainline(
        Vancouver_Start, 8, {"min_radius": 1, "min_grade": 2, "max_grade": 2}
    )
    trackhammer.generate_mainline(
        Squamish_Start, 9.5, {"min_radius": 0, "min_grade": 2, "max_grade": 3}
    )"""

    Start_Node = [[80, 2432, -96], "0fw", 0, False]  #
    trackhammer.generate_mainline(
        Start_Node, 2, {"min_radius": 1, "min_grade": -3, "max_grade": -3}
    )
    Start_Node = [[3936, -6736, 416], "0fw", 180, False]  #
    trackhammer.generate_mainline(
        Start_Node, 2, {"min_radius": 0, "min_grade": 3, "max_grade": 3}
    )

    # 2nd number is distance in miles, will keep going until it's over this value
    # 3rd number is minumum radius, 1 = 3072
    # 4th number is minimum grade level, in this case 0 is level
    # 5th number is maximum grade level, in this case 2.5%

    # Generate KDTree for distance to this line; speeds up later processes compared to doing it manually
    lines.encode_lines()
    # these values are stored as global variables in the lines module.
    tools.stopwatch_click("submodule", "Encoding and collapse done")

    # Build a sector-map from the blocklist. Dict instead of a list; tells you where the walls are. Also contains a map for "what block is next to this one"
    sectors.initialize()
    sectors.build_fit()
    sectors.link()
    tools.stopwatch_click("submodule", "Sector framework completed")

    # Takes points and puts them in buckets for sector processing.
    sectors.assign_points_to_sectors()

    # From the height-buckets, create sectors that adhere to CFG parameters.
    heightmap.generate_sector_heightmaps()
    tools.stopwatch_click("submodule", "Sector Generation done")

    # From the sector-heightmaps, go through and apply the merging process that allows sectors to communicate.
    sectors.merge_edges()
    tools.stopwatch_click("submodule", "Merge edges complete")

    # Blur heightmaps according to Gaussian blurring mechanisms, constraining min and max grids.
    profile.start()
    sectors.blur_min_max_grids(15)
    # iteration count
    profile.end()
    tools.stopwatch_click("submodule", "Blur min-max done")

    # Apply the cut and fill relative to track that ensures terrain is not occluded.
    heightmap.cut_and_fill_sector_heightmaps()
    tools.stopwatch_click("submodule", "Contours done")

    # Blur the main heightmap to reduce jagged edges on mountains and near cuts/fill
    sectors.blur_heightmap_grid()
    tools.stopwatch_click("submodule", "Smoothed heightmap")

    # Apply cut-and-fill process again to prevent smoothing from occluding the rails.
    heightmap.cut_and_fill_sector_heightmaps()
    tools.stopwatch_click("submodule", "Second pass Contours done")

    # Scan all entities for switch stands, determine which side of them is less blocked, place accordingly
    sectors.collapse_quantum_switchstands()

    profile.start()
    # Turn the raw sector and heightmap data into brushes and displacements.
    compile.compile_sectors_to_brushes()
    tools.stopwatch_click("submodule", "Brushes and Displacements done")
    profile.end()

    # For each sector, apply the scattering algorithm that places trees, rocks, bushes, etc.
    # compile.scatter_placables()
    tools.stopwatch_click("submodule", "Scattering complete")

    """points = lines.get_all_track_points()
    for entry in points:
        vmfpy.frog(entry)

    # Places Frogs at all track-points around the map, for debugging purposes.
    tools.stopwatch_click("submodule", "Frogging the Track, done")"""

    # Compile brush, entity, and brushentity data into a VMF text file and save.
    vmfpy.write_to_vmf(f"{"railmancer"}_{random.randint(4000,4999)}{".vmf"}")

    tools.stopwatch_click("total", "Railmancer Finished")


if __name__ == "__main__":
    print("RAILMANCER ACTIVATED")
    main()
