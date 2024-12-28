import time
import numpy as np


def click(name):
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

        return sec


def display_time(sec):
    mins = sec // 60
    sec = sec % 60
    hours = mins // 60
    mins = mins % 60

    return "{0}:{1}:{2}".format(int(hours), int(mins), round(sec, 3))


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


def sector_encode(X, Y):

    return str(X) + "x" + str(Y)
