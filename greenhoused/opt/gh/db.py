import sqlite3
conn = sqlite3.connect('/var/greenhouses/greenhouses.db')
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS seeds (owner VARCHAR(64), seed varchar(64), generation integer default 0);')
