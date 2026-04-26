def aggregate(track_profile):

    print(track_profile)

    Total = 0
    Lengths = track_profile[1::2]
    Incrementor = 1

    for Entry in Lengths:
        track_profile[Incrementor] = Entry + Total

        Total += Entry
        Incrementor += 2

    print(track_profile)

    return track_profile


aggregate(["main", 0.5, "left", 1, "main", 0.5])
