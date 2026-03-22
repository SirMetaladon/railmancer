import cProfile
import pstats
from typing import Optional

profiler: Optional[cProfile.Profile] = None


def start() -> None:
    global profiler

    profiler = cProfile.Profile()
    profiler.enable()
    print("Profile started.")


def end() -> bool:
    global profiler

    if profiler is None:
        print("No profile started!")
        return False

    profiler.disable()

    stats = pstats.Stats(profiler)
    stats.sort_stats("cumtime")
    stats.print_stats(15)

    profiler = None  # reset state

    return True
