from railmancer import vmfpy


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
