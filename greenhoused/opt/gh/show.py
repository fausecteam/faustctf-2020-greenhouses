#!/usr/bin/python3

import os
import random

N = 20

WATER = 100

NATURE = [
        ["  "],
        ["\x1b[33m. "],
        ["\x1b[32m* "],
        ["\x1b[34m* "],
        ["\x1b[31mo "],
        ]


def newfield():
    return [[(0,"  ") for j in range(20)] for i in range(20)]

def change(rand, field):
    for _ in range(WATER):
        row = rand.randrange(N)
        col = rand.randrange(N)
        level,_ = field[row][col]
        level += 1
        plant = rand.choice(NATURE[level % len(NATURE)])
        field[row][col] = (level,plant)


def genpic(seed, generation):
    f = newfield()
    for g in range(generation):
        rand = random.Random(seed + "-" + str(g))
        change(rand, f)
    res = ["Seed: %s\n"%seed, "Generation: %d\n"%generation]
    res.append("+" + (2*N) * "-" + "+\n")
    for line in f:
        res.append("|")
        for (_,plant) in line:
            res.append(plant)
        res.append("\x1b(B\x1b[m|\n")
    res.append("+" + (2*N) * "-" + "+\n")
    return "".join(res)

if __name__ == "__main__":
    from db import c
    owner = os.environ["SUDO_USER"]
    for (seed, generation) in c.execute("SELECT seed, generation from seeds where owner = ? order by seed", [owner]):
        print(genpic(seed, generation))

