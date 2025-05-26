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

            FirstDistance, _ = lines.distance_to_line(Ent[0][1][0], Ent[0][1][1])
            SecondDistance, _ = lines.distance_to_line(Ent[0][2][0], Ent[0][2][1])

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


def frog(x, y, z):

    add(vmfpy.blank_entity([x, y, z], "models/props_2fort/frog.mdl", [0, 0, 0]))


def get():

    return Entities
