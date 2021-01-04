#!/usr/bin/python3

import os
from db import c, conn

owner = os.environ["SUDO_USER"]
print("Welcome to your new greenhouse.")
seed = input("What would you like to sow?> ")
c.execute("INSERT INTO seeds (owner, seed) values (?,?)", (owner, seed))
conn.commit()

