import random, math
from railmancer import (
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


def main():

    trackpack_directory = "C:/Program Files (x86)/Steam/steamapps/common/Source SDK Base 2013 Singleplayer/ep2/custom/trakpak/models/trakpak3_rsg"
    vmf_input_path = ""  # "vmf inputs/squamish.vmf"

    # Starts a few stopwatches for showing time progression.
    tools.stopwatch_click("total", "Start!")
    tools.stopwatch_click("submodule", "Start!")

    # Initializes CFG parameters for use elsewhere
    cfg.initialize("railmancer/config.json")

    # Assembles a "library" of track pieces from a directory.
    track.build_track_library(trackpack_directory, ".mdl")

    tools.stopwatch_click("submodule", "Initialization complete")

    # temporary start position for Trackhammer
    Path = []
    Path += [[[2040, -32 - 6000, 500], "0fw", -90, False]]

    trackhammer.start(Path[0], 40)

    # Step 1: Import line object from a VMF, as well as the track entities themselves.
    parser.import_track(vmf_input_path)

    tools.stopwatch_click("submodule", "Line data complete")

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
    sectors.blur_grids()

    tools.stopwatch_click("submodule", "Smoothed min-max maps done")

    heightmap.cut_and_fill_sector_heightmaps()

    tools.stopwatch_click("submodule", "Contours done")

    sectors.collapse_quantum_switchstands()

    compile.compile_sectors_to_brushes()

    tools.stopwatch_click("submodule", "Brushes and Displacements done")

    compile.scatter_placables()

    tools.stopwatch_click("submodule", "Scattering complete")

    vmfpy.write_to_vmf(f"{"railmancer"}_{random.randint(4000,4999)}{".vmf"}")

    tools.stopwatch_click("total", "Railmancer Finished")


if __name__ == "__main__":
    print("RAILMANCER ACTIVATED")
    main()
