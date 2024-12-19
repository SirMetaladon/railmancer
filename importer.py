import os, math, random
import numpy as np


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

    if real_grade == 0:
        return 0
    elif abs(real_grade) < 2:
        return 1 * Sign
    elif abs(real_grade) < 2.6:
        return 2 * Sign
    else:
        return 3 * Sign


"""
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
        return (-4, 0)"""


def convertToAngle(Direction):

    Test = Direction[0]
    if Test == "0":
        return 0
    elif Test == "1":
        return 14
    elif Test == "2":
        return 26.6
    elif Test == "4":
        return 45
    elif Test == "8":
        return 90


def determine_length(StartDirection, EndDirection, Radius):

    StartAngle = convertToAngle(StartDirection)
    EndAngle = convertToAngle(EndDirection)

    Degrees = EndAngle - StartAngle

    return round(Radius * math.pi * Degrees / 180, 2)


def process_file(folder, filepath, is_arcs):

    if is_arcs == True:

        Radius = int(folder[1:])

        data = list(filepath.split("_"))

        StartDirection = data[0][1:]
        EndDirection = data[1]
        RealGrade = determine_real_grade(data[3])
        GradeLevel = determine_grade_level(RealGrade)

        Length = determine_length(StartDirection, EndDirection, Radius)

        data2 = data[4].split("x")
        ChangeX = int(data2[0])
        ChangeY = int(data2[1])
        ChangeZ = int(data2[2][:4])

        ApproxGrade = round((ChangeZ / Length) * 100, 2)

        return {
            "Length": Length,
            "Radius": Radius,
            "StartDirection": StartDirection,
            "EndDirection": EndDirection,
            "GradeLevel": GradeLevel,
            "Move": [ChangeX, ChangeY, ChangeZ],
            "ApproxGrade": ApproxGrade,
            "RealGrade": RealGrade,
        }

    elif folder == "straights":

        data = list(filepath.split("_"))
        StartDirection = data[1]
        EndDirection = data[1]
        RealGrade = determine_real_grade(data[2])
        GradeLevel = determine_grade_level(RealGrade)

        data2 = data[3].split("x")
        ChangeX = int(data2[0])
        ChangeY = int(data2[1])
        ChangeZ = int(data2[2][:4])

        Length = math.sqrt(
            math.pow(ChangeX, 2) + math.pow(ChangeY, 2) + math.pow(ChangeZ, 2)
        )

        ApproxGrade = round((ChangeZ / Length) * 100, 2)

        return {
            "Length": Length,
            "Radius": 0,
            "StartDirection": StartDirection,
            "EndDirection": EndDirection,
            "GradeLevel": GradeLevel,
            "Move": [ChangeX, ChangeY, ChangeZ],
            "ApproxGrade": ApproxGrade,
            "RealGrade": RealGrade,
        }


def build_track_library(directory, extension):

    Track_Library = []

    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(extension):
                containing_folder = os.path.basename(root)
                is_arcs = os.path.basename(os.path.dirname(root)) == "arcs"
                Entry = process_file(containing_folder, file, is_arcs)
                if Entry is not None:
                    Track_Library += [Entry]

    return Track_Library


directory = "C:/Program Files (x86)/Steam/steamapps/common/Source SDK Base 2013 Singleplayer/ep2/custom/trakpak/models/trakpak3_rsg"
Track_Library = build_track_library(directory, ".mdl")

Direction = "0fw"
Position = np.array([0, 0, 0])

for x in range(5):

    while True:

        Option = random.choice(Track_Library)

        if (
            Option["GradeLevel"] != 0
            or Option["EndDirection"] == "8lt"
            or Option["EndDirection"] == "8rt"
            or Option["Length"] > 2000
        ):
            continue

        if (
            Option["StartDirection"] != Direction
            and Option["EndDirection"] != Direction
        ):
            continue

        Direction = (
            Option["StartDirection"]
            if Option["StartDirection"] != Direction
            else Option["EndDirection"]
        )

        Position = np.add(Position, Option["Move"])

        # finish line!
        print(Option)
        break


print(Direction, Position)
