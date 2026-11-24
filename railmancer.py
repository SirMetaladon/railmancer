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
    consolidate_straights,
    settings,
)

# This is where it all comes together. Each step of the process accomplishes a major part of the overall product. Mostly for clarity of flow.


def main():

    # Track library and the input VMF. settings.local.json or the
    # RAILMANCER_* variables override these; otherwise Isaiah's paths.
    trackpack_directory = settings.get("track_library")
    vmf_input_path = settings.get("vmf_input")

    # Starts a few stopwatches for showing time progression.
    tools.stopwatch_click("total", "Start!")
    tools.stopwatch_click("submodule", "Start!")

    # Initializes CFG parameters for use elsewhere
    with tools.stage("Reading config"):
        cfg.initialize("railmancer/config.json")

    # Assembles a "library" of track pieces from a directory.
    with tools.stage("Building the track library"):
        track.build_track_library(trackpack_directory, ".mdl")

    # Import line objects from a VMF, as well as the track entities themselves.
    with tools.stage("Importing the VMF"):
        parser.import_track(vmf_input_path)

    # Starting from a node, procedurally move forward and place track, finding a path that fits the parameters.
    with tools.stage("Preparing trackhammer"):
        trackhammer.initialize()
        trackhammer.exclude_existing()

    Vancouver_Start = [(7568, 3552, -14040), "0fw", -90, False]
    Squamish_Start = [(5504, -3600, -2218), "0fw", 0, False]  #
    # Each run is (tracks left, tracks right), miles, parameters.
    # "join" says how this run attaches to the previous one. Leave it out
    # and both sides get switches. "stub" ends or starts that side with no
    # switch. A dict sets the sides separately, for example
    # {"left": "stub", "right": "switch"}.
    with tools.stage("Generating the mainline"):
        """trackhammer.generate_mainline(
            Vancouver_Start,
            [
                [
                    (0, 0),
                    2,
                    {"min_radius": 2, "min_grade": 1, "max_grade": 2},
                ],
                [
                    (0, 1),
                    0.4,
                    {"min_radius": 2, "min_grade": 1, "max_grade": 2},
                ],
                [
                    (0, 2),
                    0.07,
                    {"min_radius": 2, "min_grade": 1, "max_grade": 2},
                ],
                [
                    (0, 0),
                    0.75,
                    {"min_radius": 2, "min_grade": 1, "max_grade": 2},
                ],
                [
                    (0, 1),
                    0.6,
                    {"min_radius": 2, "min_grade": 1, "max_grade": 2},
                ],
                [
                    (0, 2),
                    0.07,
                    {"min_radius": 2, "min_grade": 1, "max_grade": 2},
                ],
                [
                    (0, 0),
                    2,
                    {"min_radius": 2, "min_grade": 1, "max_grade": 2},
                ],
            ],
        )"""

        trackhammer.generate_mainline(
            Squamish_Start,
            [
                [
                    (0, 0),
                    1,
                    {"min_radius": 2, "min_grade": 1, "min_grade": 2},
                ],
                [  # Paradise Valley Siding
                    (0, 1),
                    0.4,
                    {"min_radius": 2, "min_grade": 1, "min_grade": 2},
                ],
                [
                    (0, 0),
                    1,
                    {"min_radius": 2, "min_grade": 1, "min_grade": 2},
                ],
                [  # Garibaldi Siding
                    (0, 1),
                    0.3,
                    {"min_radius": 2, "min_grade": 1, "min_grade": 2},
                ],
                [  # Garibaldi Siding
                    (0, 2),
                    0.1,
                    {"min_radius": 2, "min_grade": 1, "min_grade": 2},
                ],
                [  # Garibaldi Siding
                    (0, 1),
                    0.3,
                    {"min_radius": 2, "min_grade": 1, "min_grade": 2},
                ],
                [
                    (0, 0),
                    1,
                    {"min_radius": 2, "min_grade": 1, "min_grade": 2},
                ],
                [  # Mons Siding
                    (0, 1),
                    0.4,
                    {"min_radius": 2, "min_grade": 1, "min_grade": 2},
                ],
                [  # MOW and Tanker siding
                    (0, 3),
                    0.1,
                    {"min_radius": 2, "min_grade": 0, "max_grade": 0},
                ],
                [  # end siding
                    (0, 1),
                    0.005,
                    {
                        "min_radius": 2,
                        "min_grade": 0,
                        "max_grade": 0,
                        "join": {"right": "stub"},
                    },
                ],
                [
                    (0, 0),
                    2.125,
                    {"min_radius": 2, "min_grade": 1, "min_grade": 2},
                ],
                [
                    (1, 0),  # Alta Lake MOW Stub
                    0.1,
                    {"min_radius": 2, "min_grade": 1, "min_grade": 2},
                ],
                [
                    (0, 0),
                    1,
                    {"min_radius": 2, "min_grade": 1, "min_grade": 2, "join": "stub"},
                ],
                [  # Pemberton Siding
                    (0, 1),
                    0.4,
                    {"min_radius": 2, "min_grade": 1, "min_grade": 2},
                ],
                [  # Pemberton Siding
                    (0, 3),
                    0.2,
                    {"min_radius": 2, "min_grade": 1, "min_grade": 2},
                ],
                [
                    (0, 0),
                    0.005,
                    {"min_radius": 2, "min_grade": 1, "min_grade": 2},
                ],
                [
                    (1, 0),  # Mt. Currie Pole Guy
                    0.1,
                    {"min_radius": 2, "min_grade": 0, "max_grade": 0},
                ],
                [
                    (0, 0),
                    1,
                    {"min_radius": 2, "min_grade": 1, "min_grade": 2, "join": "stub"},
                ],
                [  # Creekside
                    (0, 1),
                    0.4,
                    {"min_radius": 2, "min_grade": 1, "max_grade": 2},
                ],
                [
                    (0, 2),
                    0.07,
                    {"min_radius": 2, "min_grade": 1, "max_grade": 2},
                ],
                [
                    (0, 0),
                    2,
                    {"min_radius": 2, "min_grade": 1, "min_grade": 2},
                ],
                [  # D'Arcy
                    (0, 1),
                    0.6,
                    {"min_radius": 2, "min_grade": 1, "max_grade": 2},
                ],
                [
                    (0, 2),
                    0.07,
                    {"min_radius": 2, "min_grade": 1, "max_grade": 2},
                ],
                [
                    (0, 0),
                    2,
                    {"min_radius": 2, "min_grade": 1, "min_grade": 2, "join": "stub"},
                ],
            ],
        )

        """

            #D'Arcy to Seton Portage
            2.125 mi 1 track

            #McGillivray
            0.1 mi 1 track (optional abandoned/remnant)

            #Seton Portage Siding
            0.6 mi 2 tracks
            0.3 mi South-facing car-storage stub

            #Seton Portage to Retakit
            1.125 mi 1 track

            #Retakit Siding
            0.4 mi 2 tracks
            0.2 mi Additional short track
            0.3 mi Additional long track
            0.2 mi Car storage track

            #Retakit to Lillooet
            1.25 mi 1 track

            #Lillooet
            Terminal / local yard"""

    # 2nd number is distance in miles, will keep going until it's over this value
    # 3rd number is minumum radius, 1 = 3072
    # 4th number is minimum grade level, in this case 0 is level
    # 5th number is maximum grade level, in this case 2.5%

    # Merge collinear straights before anything samples the rail. Smooth grade
    # rewrites rises; consolidate_inplace rebuilds lines.Beziers from the props
    # so switch stands, heightmaps, and sectors see the regraded profile.
    with tools.stage("Consolidating straights"):
        consolidate_straights.consolidate_inplace(smooth_grade=True)

    # Generate KDTree for distance to this line; speeds up later processes compared to doing it manually
    with tools.stage("Encoding lines"):
        lines.encode_lines()
    # these values are stored as global variables in the lines module.

    # Scan all entities for switch stands, determine which side of them is less blocked, place accordingly.
    # Before staged ground hints are inserted: the stand pass measures track only.
    with tools.stage("Placing switch stands"):
        sectors.collapse_quantum_switchstands()

    # takes staged building foundation points and makes them ignore sector creation while still being a part of sectors
    with tools.stage("Inserting staged points"):
        lines.insert_staged_points()

    # Build a sector-map from the blocklist. Dict instead of a list; tells you where the walls are. Also contains a map for "what block is next to this one"
    with tools.stage("Fitting sectors"):
        sectors.build_fit()
    with tools.stage("Linking sectors"):
        sectors.link()

    # Takes points and puts them in buckets for sector processing.
    with tools.stage("Assigning points to sectors"):
        sectors.assign_points_to_sectors()

    # Floor/ceiling limits on each node. Not the ramp; the ramp is cut-and-fill.
    with tools.stage("Generating heightmaps"):
        heightmap.generate_sector_heightmaps()

    # Share edge vertices, including the diagonal corner, so displacements meet.
    with tools.stage("Merging edges"):
        sectors.merge_edges()
    """
    # Spread those limits across sector borders at noise_floor_ceiling_spillover_slope
    # until the slope has settled, instead of stopping after a fixed 5 passes.
    with tools.stage("Spreading floor and ceiling"):
        sectors.blur_min_max_grids()

    # Slope-limited ramp off the smooth track field, then the rail carve.
    with tools.stage("Contours"):
        heightmap.cut_and_fill_sector_heightmaps()

    # Blur and re-clamp to the envelope and the carve, once per pass, so the
    # average cannot lift ground over a rail or out through the floor/ceiling.
    with tools.stage("Relaxing the heightmap"):
        heightmap.relax_heightmaps()
    """
    # profile.start()
    # Turn the raw sector and heightmap data into brushes and displacements.
    with tools.stage("Compiling sectors"):
        compile.compile_sectors_to_brushes()
    # profile.end()

    # For each sector, apply the scattering algorithm that places trees, rocks, bushes, etc.
    # with tools.stage("Scattering props"):
    # compile.scatter_placables()

    """points = lines.get_all_track_points()
    for entry in points:
        vmfpy.frog(entry)

    # Places Frogs at all track-points around the map, for debugging purposes.
    tools.stopwatch_click("submodule", "Frogging the Track, done")"""

    # with tools.stage("Adding the light"):
    # vmfpy.add_light_environment()

    # Compile brush, entity, and brushentity data into a VMF text file and save.
    with tools.stage("Writing the VMF"):
        vmfpy.write_to_vmf(f"{"railmancer"}_{random.randint(5000,5999)}{".vmf"}")

    tools.stopwatch_click("total", "Railmancer Finished")


if __name__ == "__main__":
    print("RAILMANCER ACTIVATED")
    main()
