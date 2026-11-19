import random
from railmancer import (
    lines,
    tools,
    vmfpy,
    parser,
    sectors,
    track,
    cfg,
)

# This is where it all comes together. Each step of the process accomplishes a major part of the overall product. Mostly for clarity of flow.


def main():

    # Some input information. One contains the directory for building the Track Library, the other is the VMF for the importer.
    trackpack_directory = "C:/Program Files (x86)/Steam/steamapps/common/Source SDK Base 2013 Singleplayer/ep2/custom/trakpak/models/trakpak3_rsg"
    # vmf_input_path = "vmf inputs/squamish test.vmf"
    vmf_input_path = "vmf inputs/hb_terminal_track.vmf"

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
