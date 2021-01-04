from db import c, conn

c.execute("update seeds set generation = generation+1")
conn.commit()
