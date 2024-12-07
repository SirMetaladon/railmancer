import os, math


def determine_real_grade(raw_grade):
    if raw_grade == "0pg":
        return 0

    number_string = raw_grade[: len(raw_grade) - 2]

    return (
        int(
            number_string + ("0" * (3 + int("-" in number_string) - len(number_string)))
        )
        / 100
    )


def determine_grade_level(real_grade):

    Sign = 1 if real_grade >= 0 else -1

    if abs(real_grade) < 2:
        return 1 * Sign
    elif abs(real_grade) < 2.6:
        return 2 * Sign
    else:
        return 3 * Sign


def get_direction(raw_direction):

    if raw_direction == "0fw":
        return (0, 4)
    elif raw_direction == "1rt":
        return (1, 4)
    elif raw_direction == "1lt":
        return (-1, 4)
    elif raw_direction == "2rt":
        return (2, 4)
    elif raw_direction == "2lt":
        return (-2, 4)
    elif raw_direction == "4rt" or raw_direction == "4lt":
        return (4, 4)
    elif raw_direction == "8rt":
        return (4, 0)
    elif raw_direction == "8lt":
        return (-4, 0)


def convertToAngle(Direction):

    Test = abs(Direction[0])
    if Test is 0:
        return 0
    elif Test is 1:
        return 14
    elif Test is 2:
        return 26.6
    elif Test is 4:
        if Direction[1] is 0:
            return 90
        else:
            return 45


def determine_length(StartDirection, EndDirection, Radius):

    StartAngle = convertToAngle(StartDirection)
    EndAngle = convertToAngle(EndDirection)

    Degrees = EndAngle - StartAngle

    return round(Radius * math.pi * Degrees / 180, 2)


def process_file(folder, filepath):
    # Replace with your specific processing code
    print(f"Processing file: {filepath}")

    Radius = int(folder[1:])

    data = list(filepath.split("_"))

    StartDirection = get_direction(data[0][1:])
    EndDirection = get_direction(data[1])
    OverallDirection = data[2]
    RealGrade = determine_real_grade(data[3])
    GradeLevel = determine_grade_level(RealGrade)

    Length = determine_length(StartDirection, EndDirection, Radius)

    data2 = data[4].split("x")
    ChangeX = int(data2[0])
    ChangeY = int(data2[1])
    ChangeZ = int(data2[2][:4])

    ApproxGrade = round((ChangeZ / Length) * 100, 2)

    print(
        Length,
        Radius,
        StartDirection,
        EndDirection,
        OverallDirection,
        GradeLevel,
        ChangeX,
        ChangeY,
        ChangeZ,
        ApproxGrade,
        RealGrade,
    )


def find_files_with_extension(directory, extension):
    # Iterate through all directories and subdirectories
    for root, dirs, files in os.walk(directory):
        for file in files:
            # Check if file ends with the desired extension
            if file.endswith(extension):
                # Get the full file path
                full_path = os.path.join(root, file)

                # get the containing folder
                containing_folder = os.path.basename(root)
                process_file(containing_folder, file)

                # process_file(containing_folder + os.path(file))


# Usage example
directory = "C:/Program Files (x86)/Steam/steamapps/common/Source SDK Base 2013 Singleplayer/ep2/custom/trakpak/models/trakpak3_rsg/arcs"  # Replace with your directory path
extension = ".mdl"  # Replace with your desired extension
find_files_with_extension(directory, extension)
