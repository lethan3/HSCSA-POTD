import psycopg2
import os
import time
from datetime import datetime

from collections import namedtuple
from dotenv import load_dotenv

class Database:
    def __init__(self):
        load_dotenv('.env')
        self.conn = psycopg2.connect(database=os.environ.get("DB_NAME"), user=os.environ.get("DB_USERNAME"),
                                     password=os.environ.get("DB_PASSWORD"), host="127.0.0.1", port="5432")
        self.make_tables()
    def make_tables(self):
        cmds = []
        cmds.append("""
                        CREATE TABLE IF NOT EXISTS handles(
                           guild BIGINT,
                           discord_id BIGINT,
                           cf_handle TEXT,
                           rating INT
                    )
                    """)
        cmds.append("""
                        CREATE TABLE IF NOT EXISTS problems(
                            id INT,
                            index TEXT,
                            name TEXT,
                            type TEXT,
                            rating INT,
                            tags TEXT,
                            used BOOLEAN
                    )
                    """)
        cmds.append("""
                        CREATE TABLE IF NOT EXISTS contests(
                            id INT, 
                            name TEXT
                    )
                    """)
        cmds.append("""
                        CREATE TABLE IF NOT EXISTS potds(
                            id INT,
                            index TEXT,
                            name TEXT,
                            use_date DATE
                    )
                    """)
        try:
            curr = self.conn.cursor()
            for x in cmds:
                curr.execute(x)
            curr.close()
            self.conn.commit()
        except Exception:
            print("Error while making tables")

    def get_handle(self, guild, discord_id):
        query = f"""
                    SELECT cf_handle FROM handles
                    WHERE
                    guild = %s AND
                    discord_id = %s
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, discord_id))
        data = curr.fetchone()
        curr.close()
        if not data:
            return None
        return data[0]

    def add_handle(self, guild, discord_id, cf_handle, rating):
        query = f"""
                    INSERT INTO handles
                    (guild, discord_id, cf_handle, rating)
                    VALUES
                    (%s, %s, %s, %s)
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, discord_id, cf_handle, rating))
        self.conn.commit()
        curr.close()

    def get_all_handles(self, guild=None):
        query = f"""
                    SELECT * FROM handles
                """
        if guild is not None:
            query += f" WHERE guild = {guild}"
        curr = self.conn.cursor()
        curr.execute(query)
        data = curr.fetchall()
        curr.close()
        return data

    def remove_handle(self, guild, discord_id):
        query = f"""
                    DELETE from handles
                    WHERE
                    guild = %s AND
                    discord_id = %s
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, discord_id))
        self.conn.commit()
        curr.close()

    def get_problems(self, id=None):
        curr = self.conn.cursor()
        if not id:
            query = """
                        SELECT * FROM problems
                    """
            curr.execute(query)
        else:
            query = """
                        SELECT * FROM problems
                        WHERE
                        id = %s AND index = %s
                    """
            curr.execute(query, (id.split('/')[0], id.split('/')[1]))

        res = curr.fetchall()
        Problem = namedtuple('Problem', 'id index name type rating used')
        curr.close()
        data = []
        for x in res:
            data.append(Problem(x[0], x[1], x[2], x[3], x[4], x[5]))
        return data
    
    def get_contests_id(self):
        query = f"""
                    SELECT id from contests
                """
        curr = self.conn.cursor()
        curr.execute(query)
        data = curr.fetchall()
        curr.close()
        return data

    def get_contest_name(self, contest_id):
        query = f"""
                    SELECT name FROM contests
                    WHERE
                    id = %s 
                """
        curr = self.conn.cursor()
        curr.execute(query, (contest_id,))
        data = curr.fetchone()
        curr.close()
        #  print(id)
        if len(data) == 0:
            return "No data"
        return data[0]

    def add_problem(self, id, index, name, type, rating, used):
        query = f"""
                    INSERT INTO problems
                    (id, index, name, type, rating, used)
                    VALUES
                    (%s, %s, %s, %s, %s, %s)
                """
        curr = self.conn.cursor()
        curr.execute(query, (id, index, name, type, rating, used))
        self.conn.commit()
        curr.close()

    def add_potd(self, id, index, name):
        query = f"""
                    ALTER TABLE handles
                    ADD %s BOOLEAN DEFAULT false
                """
        curr = self.conn.cursor()
        curr.execute(query % ('"' + 'solved_' + datetime.today().strftime('%Y-%m-%d') + '"',))
        self.conn.commit()
        curr.close()

        query = f"""
                    INSERT INTO potds
                    (id, index, name, use_date)
                    VALUES
                    (%s, %s, %s, %s)
                """
        curr = self.conn.cursor()
        curr.execute(query, (id, index, name, datetime.today().strftime('%Y-%m-%d')))
        self.conn.commit()
        curr.close()

    def get_potd(self):
        query = f"""
                    SELECT * FROM potds
                    WHERE
                    use_date=%s
                """
        curr = self.conn.cursor()
        curr.execute(query, (datetime.today().strftime('%Y-%m-%d'),))
        data = curr.fetchall()
        curr.close()

        Problem = namedtuple('Problem', 'id index name')
        if len(data) == 0:
            return None
        return Problem(data[-1][0], data[-1][1], data[-1][2])

    def check_user_potd(self, cf_handle):
        query = f"""
                    SELECT * FROM handles
                    WHERE cf_handle=%s
                """
        curr = self.conn.cursor()
        curr.execute(query, (cf_handle,))
        data = curr.fetchone()
        curr.close()
        return data[-1]
    
    def set_user_potd(self, cf_handle):
        query = f"""
                    UPDATE handles
                    SET %s = true
                    WHERE cf_handle=%s
                """
        curr = self.conn.cursor()
        curr.execute(query % ('"' + 'solved_' + datetime.today().strftime('%Y-%m-%d') + '"', "'" + cf_handle + "'"))
        self.conn.commit()
        curr.close()

    def set_used(self, id, index, name):
        query = f"""
                    UPDATE problems
                    SET used=True
                    WHERE id = %s AND index = %s AND name = %s
                """
        curr = self.conn.cursor()
        curr.execute(query, (id, index, name))
        self.conn.commit()
        curr.close()

    def add_contest(self, id, name):
        query = f"""
                    INSERT INTO contests
                    (id, name)
                    VALUES
                    (%s, %s)
                """
        curr = self.conn.cursor()
        curr.execute(query, (id, name))
        self.conn.commit()
        curr.close()



