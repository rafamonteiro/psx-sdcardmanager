"""
Sqlite3 database functions
"""
import logging
# System imports
import sys
from os import remove
from os.path import exists, join, abspath, dirname
from pathlib import Path
from sqlite3 import connect, Error

DATABASE_PATH = join(Path(abspath(dirname(sys.argv[0]))), 'data')
DATABASE_FILE = 'psio_assist.db'
DATABASE_FULL_PATH = join(DATABASE_PATH, DATABASE_FILE)

logger = logging.getLogger(__name__)


# Function that ensures the database file exists and has been merged
def ensure_database_exists():
    if not exists(DATABASE_FULL_PATH):
        if _database_splits_exist():
            _merge_database()
            if not exists(DATABASE_FULL_PATH):
                logging.log(logging.ERROR, 'Unable to merge database file!')
                sys.exit()
        else:
            logging.log(logging.ERROR, 'Database split-files not found!')
            sys.exit()


def select(select_query):
    rows = []
    try:
        conn = _create_connection(DATABASE_FULL_PATH)
        cursor = conn.cursor()
        cursor.execute(select_query)
        rows = cursor.fetchall()
        cursor.close()
    except Error as error:
        logging.log(logging.ERROR, error)
    finally:
        if conn:
            conn.close()

    return rows


def _create_connection(db_file):
    conn = None
    try:
        conn = connect(db_file)
        return conn
    except Error as error:
        logging.log(logging.ERROR, error)

    return conn


def extract_game_cover_blob(row_id, image_out_path):
    try:
        conn = _create_connection(DATABASE_FULL_PATH)
        cursor = conn.cursor()

        with open(image_out_path, 'wb') as output_file:
            cursor.execute(f'SELECT psio FROM covers WHERE id = {row_id};')
            ablob = cursor.fetchone()
            output_file.write(ablob[0])

        cursor.close()
    except Error as error:
        logging.log(logging.ERROR, error)
    finally:
        if conn:
            conn.close()


# Function that checks if each of the database split-files exist
def _database_splits_exist():
    for i in range(1, 5):  # Adjust the range if you have more split files
        if not exists(join(DATABASE_PATH, f'psio_assist_{i}.db')):
            return False
    return True


# Function that deletes the database split-files
def _delete_database_splits():
    for i in range(1, 5):  # Adjust the range if you have more split files
        if exists(join(DATABASE_PATH, f'psio_assist_{i}.db')):
            remove(join(DATABASE_PATH, f'psio_assist_{i}.db'))


# Function that merges the split database files
def _merge_database():
    # List of source databases
    source_dbs = [join(DATABASE_PATH, f'psio_assist_{i}.db') for i in range(1, 5)]  # Adjust the range if needed

    # Connect to the destination database
    destination_conn = connect(DATABASE_FULL_PATH)
    destination_cursor = destination_conn.cursor()

    # Function to copy table structure and data
    def copy_table_structure_and_data(source_cursor, destination_cursor, table_name):
        # Get the table structure
        source_cursor.execute(f"PRAGMA table_info({table_name})")
        columns = source_cursor.fetchall()
        column_names = [col[1] for col in columns]

        # Check if the table already exists in the destination database
        destination_cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        if not destination_cursor.fetchone():
            # Create table in the destination database
            source_cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'")
            create_table_sql = source_cursor.fetchone()[0]
            destination_cursor.execute(create_table_sql)

        # Copy data
        source_cursor.execute(f"SELECT * FROM {table_name}")
        rows = source_cursor.fetchall()
        placeholders = ', '.join('?' * len(column_names))
        destination_cursor.executemany(f"INSERT INTO {table_name} VALUES ({placeholders})", rows)

    # Process each source database
    for source_db in source_dbs:
        source_conn = connect(source_db)
        source_cursor = source_conn.cursor()

        # Get the list of tables in the source database
        source_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = source_cursor.fetchall()

        # Copy each table
        for table in tables:
            table_name = table[0]
            copy_table_structure_and_data(source_cursor, destination_cursor, table_name)

        # Close the source database connection
        source_conn.close()

    # Commit changes and close the destination database connection
    destination_conn.commit()
    destination_conn.close()

    _delete_database_splits()
