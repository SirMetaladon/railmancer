from railmancer import lines, vmfpy


def collapse_quantum_switchstands():

    global Entities

    for ID in range(len(Entities)):

        Ent = Entities[ID]

        try:
            if Ent[0][0] == "collapse":
                Collapse = 1
            else:
                Collapse = 0
        except:
            Collapse = 0

        if Collapse:

            sector_data = None  # error so I fix it later

            FirstDistance, _ = lines.distance_to_line(
                Ent[0][1][0], Ent[0][1][1], sector_data
            )
            SecondDistance, _ = lines.distance_to_line(
                Ent[0][2][0], Ent[0][2][1], sector_data
            )

            if FirstDistance > SecondDistance:
                Entities[ID] = Ent[1]
            else:
                Entities[ID] = Ent[2]


def add(Ent):

    global Entities

    try:

        Entities += [Ent]

    except:

        Entities = [Ent]


def frog(pos, ang=[0, 0, 0]):

    add(vmfpy.blank_entity(pos, "models/props_2fort/frog.mdl", ang))


def get():

    return Entities
