import tools


def get(HeadingDeflection, StartDirection, EndDirection):

    # this will be replaced with a builder algoritm in the fututure, I manually keyed it in for now

    """},
        90: {
            "0fw": [[2048, 2048, "right", 9999999]],
            "1rt": [[2048 + 704, 2048 - 96, "right", 1 / 4]],
            "1lt": [[1120 + 640, 608 + 1568, "left", 1 / 4]],
            "2rt": [[2048 + 1056, 2048 - 256, "right", 1 / 2]],
            "2lt": [[736 + 640, 512 + 1568, "left", 1 / 2]],
            "4rt": [[2048 + 1568, 2048 - 640, "right", 1]],
            "4lt": [[640, 1568, "left", 1]],
        },
    }"""

    Paths = {}

    # format is 0 implied start heading, whatever ending heading, start dir, end dir
    tools.blind_add(Paths, "0|0fw|0fw", [(0, 0), [(16, 0)]])
    tools.blind_add(
        Paths,
        "0|0fw|0fw",
        [
            (-704 * 2, 96 * 2),
            [
                (16, 0),
                (16, 4),
                (16, 0),
            ],
            [
                "models/trakpak3_rsg/arcs/r2048/a0fw_1rt_right_0pg_+0704x+0096x0000.mdl",
                "models/trakpak3_rsg/arcs/r2048/a0fw_1rt_right_0pg_+0704x+0096x0000.mdl",
            ],
        ],
    )
    tools.blind_add(
        Paths,
        "0|0fw|0fw",
        [
            (-1056 * 2, 256 * 2),
            [
                (16, 0),
                (16, 8),
                (16, 0),
            ],
            [
                "models/trakpak3_rsg/arcs/r2048/a0fw_2rt_right_0pg_+1056x+0256x0000.mdl",
                "models/trakpak3_rsg/arcs/r2048/a0fw_2rt_right_0pg_+1056x+0256x0000.mdl",
            ],
        ],
    )
    tools.blind_add(
        Paths,
        "0|0fw|0fw",
        [
            (-1568 * 2, 640 * 2),
            [
                (16, 0),
                (16, 16),
                (16, 0),
            ],
            [
                "models/trakpak3_rsg/arcs/r2048/a0fw_4rt_right_0pg_+1568x+0640x0000.mdl",
                "models/trakpak3_rsg/arcs/r2048/a0fw_4rt_right_0pg_+1568x+0640x0000.mdl",
            ],
        ],
    )
    tools.blind_add(
        Paths,
        "0|0fw|0fw",
        [
            (-704 * 2, -96 * 2),
            [
                (16, 0),
                (16, -4),
                (16, 0),
            ],
            [
                "models/trakpak3_rsg/arcs/r2048/a0fw_1lt_left_0pg_+0704x-0096x0000.mdl",
                "models/trakpak3_rsg/arcs/r2048/a0fw_1lt_left_0pg_+0704x-0096x0000.mdl",
            ],
        ],
    )
    tools.blind_add(
        Paths,
        "0|0fw|0fw",
        [
            (-1056 * 2, -256 * 2),
            [
                (16, 0),
                (16, -8),
                (16, 0),
            ],
            [
                "models/trakpak3_rsg/arcs/r2048/a0fw_2lt_left_0pg_+1056x-0256x0000.mdl",
                "models/trakpak3_rsg/arcs/r2048/a0fw_2lt_left_0pg_+1056x-0256x0000.mdl",
            ],
        ],
    )
    tools.blind_add(
        Paths,
        "0|0fw|0fw",
        [
            (-1568 * 2, -640 * 2),
            [
                (16, 0),
                (16, -16),
                (16, 0),
            ],
            [
                "models/trakpak3_rsg/arcs/r2048/a0fw_4lt_left_0pg_+1568x-0640x0000.mdl",
                "models/trakpak3_rsg/arcs/r2048/a0fw_4lt_left_0pg_+1568x-0640x0000.mdl",
            ],
        ],
    )

    tools.blind_add(
        Paths,
        "0|0fw|1rt",
        [
            (-704, 96),
            [
                (16, 0),
                (16, 4),
            ],
            [
                "models/trakpak3_rsg/arcs/r2048/a0fw_1rt_right_0pg_+0704x+0096x0000.mdl",
            ],
        ],
    )
    tools.blind_add(
        Paths,
        "0|0fw|1lt",
        [
            (-704, -96),
            [
                (16, 0),
                (16, -4),
            ],
            [
                "models/trakpak3_rsg/arcs/r2048/a0fw_1lt_left_0pg_+0704x-0096x0000.mdl",
            ],
        ],
    )

    tools.blind_add(
        Paths,
        "0|0fw|2rt",
        [
            (-1056, 256),
            [
                (16, 0),
                (16, 8),
            ],
            [
                "models/trakpak3_rsg/arcs/r2048/a0fw_2rt_right_0pg_+1056x+0256x0000.mdl",
            ],
        ],
    )
    tools.blind_add(
        Paths,
        "0|0fw|2lt",
        [
            (-1056, -256),
            [
                (16, 0),
                (16, -8),
            ],
            [
                "models/trakpak3_rsg/arcs/r2048/a0fw_2lt_left_0pg_+1056x-0256x0000.mdl",
            ],
        ],
    )

    tools.blind_add(
        Paths,
        "0|0fw|4rt",
        [
            (1568, 640),
            [
                (16, 0),
                (16, 16),
            ],
            [
                "models/trakpak3_rsg/arcs/r2048/a0fw_4rt_right_0pg_+1568x+0640x0000.mdl",
            ],
        ],
    )
    tools.blind_add(
        Paths,
        "0|0fw|4lt",
        [
            (-1568, -640),
            [
                (16, 0),
                (16, -16),
            ],
            [
                "models/trakpak3_rsg/arcs/r2048/a0fw_4lt_left_0pg_+1568x-0640x0000.mdl",
            ],
        ],
    )

    return Paths[str(HeadingDeflection) + "|" + StartDirection + "|" + EndDirection]
