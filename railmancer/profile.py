import cProfile, pstats


def start():
    global profiler
    profiler = cProfile.Profile()
    profiler.enable()
    print("Profile started.")


def end():

    try:
        profiler
    except:
        print("No profile started!")
        return False

    stats = pstats.Stats(profiler)
    stats.sort_stats(
        "cumtime"
    )  # 'cumtime' = total time spent in function (including subcalls)
    stats.print_stats(30)

    profiler.disable()
