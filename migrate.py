# # # migrate.py

# # from sqlalchemy import create_engine, MetaData
# # from database import DATABASE_URL
# # from models import meta_table  # Ensure the `models.py` defines the `meta_table`

# # # Create the engine and bind the metadata to it
# # engine = create_engine(DATABASE_URL)
# # metadata = MetaData()

# # # Create the meta_table in the database
# # metadata.create_all(engine)

# # if __name__ == "__main__":
# #     print("Meta table created successfully.")


# # migrate.py

# from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Text, DateTime, ForeignKey, Boolean
# from database import DATABASE_URL
# from models import meta_table, sessions  # Ensure to import sessions

# # Create the engine and bind the metadata to it
# engine = create_engine(DATABASE_URL)
# metadata = MetaData()

# metadata.bind = engine
# metadata.reflect()

# # Check if 'session_name' column exists, if not, add it
# if not hasattr(sessions.c, 'session_name'):
#     with engine.connect() as connection:
#         alter_table_query = "ALTER TABLE sessions ADD COLUMN session_name VARCHAR(255);"
#         connection.execute(alter_table_query)
#         print("Added 'session_name' column to 'sessions' table.")
# else:
#     print("'session_name' column already exists in 'sessions' table.")


# migrate.py

from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, DateTime, Boolean
from database import DATABASE_URL
from models import sessions  # Ensure sessions are imported

# Create the engine and bind the metadata to it
engine = create_engine(DATABASE_URL)
metadata = MetaData()

metadata.bind = engine
metadata.reflect()

# Function to check and add a column if it doesn't exist
def add_column_if_not_exists(table, column):
    if not hasattr(table.c, column.name):
        with engine.connect() as connection:
            alter_table_query = f"ALTER TABLE {table.name} ADD COLUMN {column.name} {column.type} DEFAULT {column.default.arg} NOT NULL;"
            connection.execute(alter_table_query)
            print(f"Added '{column.name}' column to '{table.name}' table.")
    else:
        print(f"'{column.name}' column already exists in '{table.name}' table.")

# Define the new columns
is_archived_column = Column('is_archived', Boolean, default=False, nullable=False)
session_name_column = Column('session_name', String(255), nullable=True, server_default='Chat')

# Add 'is_archived' column
add_column_if_not_exists(sessions, is_archived_column)

# Add 'session_name' column (if not already handled)
if not hasattr(sessions.c, 'session_name'):
    with engine.connect() as connection:
        alter_table_query = "ALTER TABLE sessions ADD COLUMN session_name VARCHAR(255) DEFAULT 'Chat';"
        connection.execute(alter_table_query)
        print("Added 'session_name' column to 'sessions' table.")
else:
    print("'session_name' column already exists in 'sessions' table.")
