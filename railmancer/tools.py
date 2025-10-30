import time, math
import numpy as np


def display_time(sec):
    mins = sec // 60
    sec = sec % 60
    hours = mins // 60
    mins = mins % 60

    return "{0}:{1}:{2}".format(int(hours), int(mins), round(sec, 3))


def stopwatch_click(name, blurb=""):
    global last_click
    try:
        last_click
    except NameError:
        last_click = {name: 0}

    if last_click.get(name, 0) == 0:
        last_click[name] = time.time()
        return 0

    else:

        sec = time.time() - last_click[name]
        last_click[name] = time.time()
        print(blurb + " in " + display_time(sec))
        return sec


def rot_z(Vector, Angle):
    math = Angle * (np.pi / 180)  # radians

    if len(Vector) == 3:
        rotator = np.array(
            [
                [np.cos(math), -np.sin(math), 0],
                [np.sin(math), np.cos(math), 0],
                [0, 0, 1],
            ]
        )
    elif len(Vector) == 2:
        rotator = np.array(
            [[np.cos(math), -np.sin(math)], [np.sin(math), np.cos(math)]]
        )

    else:
        return Vector

    return rotator @ Vector


def is_same(v1, v2):
    for entry in range(len(v1)):
        try:
            if round(v1[entry]) != round(v2[entry]):
                return False
        except:
            return False

    return True


def extract(Dict, ToInvestigate, LookingFor, Default):

    Output = []
    for Entry in ToInvestigate:
        Output += [Dict[Entry].get(LookingFor, Default)]

    return Output


def import_json(path: str):

    import json

    try:
        with open(path, "r", encoding="utf-8-sig") as JSONIn:

            content = JSONIn.read().strip()
            Dict = json.loads(content)

            print("Successfully read " + path)

            return Dict

    except UnicodeDecodeError as e:
        print(f"Encoding error: " + str(e))
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: " + str(e))
    except Exception as e:
        print(e)
        print('Read failed on "' + str(path) + '".')


def linterp(a, b, x):

    x = max(0, min(1, x))

    return a * (1 - x) + b * x


def blind_add(Dict, Key, Payload):

    Object = Dict.get(Key, [])
    Object += [Payload]
    Dict[Key] = Object


def clamped(val, limit, limit2):

    Top = max(limit, limit2)
    Bot = min(limit, limit2)

    return max(min(val, Top), Bot)


def scale(val, scale, max):
    return (val * scale) + ((max / 2) * (1 - scale))


def nudge(point, direction):

    return (
        point[0] + direction[0],
        point[1] + direction[1],
    )


def quadnudge(point, length):

    return [
        nudge(point, [length, 0]),
        nudge(point, [-length, 0]),
        nudge(point, [0, length]),
        nudge(point, [0, -length]),
    ]


def merge_grids(center, left, right, up, down, fill_value=True):
    N = len(center)  # Each sub-grid is N x N
    merged_size = 3 * N  # Final grid will be 3N x 3N

    # Initialize the full grid with the fill_value
    merged = [[fill_value] * merged_size for _ in range(merged_size)]

    # Helper function to insert a grid into a position
    def insert_grid(target, source, x_offset, y_offset):
        for i in range(N):
            for j in range(N):
                target[x_offset + i][y_offset + j] = source[i][j]

    # Place the 5 known grids into the merged grid
    insert_grid(merged, center, N, N)
    insert_grid(merged, left, 0, N)
    insert_grid(merged, right, 2 * N, N)
    insert_grid(merged, down, N, 0)
    insert_grid(merged, up, N, 2 * N)

    return merged  # The fully merged grid


def heuristic_inserter(stack, to_add):

    heuristic = to_add[1]
    for index, (_, h) in enumerate(stack):
        if heuristic > h:
            stack.insert(index, to_add)
            return
    stack.append(to_add)


def round_to_multiple(value, snapto, mode):

    if mode == "floor":
        return math.floor(value / snapto) * snapto
    else:
        return round(value / snapto) * snapto


def within2d(tuple2d, range):

    return abs(tuple2d[0]) < range and abs(tuple2d[1]) < range


def blank_list_grid(dimensions, length, contains=None):

    size = range(length)

    if dimensions == 2:
        return [[[contains] for _ in size] for _ in size]

    if dimensions == 3:
        return [[[[contains] for _ in size] for _ in size] for _ in size]
