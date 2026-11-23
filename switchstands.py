import random
from railmancer import (
    lines,
    tools,
    vmfpy,
    parser,
    sectors,
    track,
    cfg,
    settings,
)

# This is where it all comes together. Each step of the process accomplishes a major part of the overall product. Mostly for clarity of flow.


def main():

    # Track library and the input VMF. settings.local.json or the
    # RAILMANCER_SWITCHSTANDS_* variables override these.
    trackpack_directory = settings.get("switchstands_track_library")
    vmf_input_path = settings.get("switchstands_vmf_input")

    # Starts a few stopwatches for showing time progression.
    tools.stopwatch_click("total", "Start!")
    tools.stopwatch_click("submodule", "Start!")

    # Initializes CFG parameters for use elsewhere
    cfg.initialize("railmancer/config.json")

    # Assembles a "library" of track pieces from a directory.
    track.build_track_library(trackpack_directory, ".mdl")

    # Import line objects from a VMF, as well as the track entities themselves.
    parser.import_track(vmf_input_path)

    # Track samples only. Ground hints are staged by the import and are not inserted here.
    lines.encode_lines()

    # Which side of each stand is farther from the rails. Track points only, no sector map.
    sectors.collapse_quantum_switchstands()

    # Compile brush, entity, and brushentity data into a VMF text file and save.
    vmfpy.write_to_vmf("switchstands_output.vmf")

    tools.stopwatch_click("total", "Railmancer Finished")


if __name__ == "__main__":
    print("RAILMANCER ACTIVATED")
    main()
