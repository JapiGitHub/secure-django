#sqlite3 usage python script
import sqlite3

connection = sqlite3.connect('db.sqlite3')

cursor = connection.cursor()

cursor.execute("SELECT * FROM *")

print(cursor.fetchall())