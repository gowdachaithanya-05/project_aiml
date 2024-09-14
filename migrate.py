from sqlalchemy import create_engine, MetaData
from database import DATABASE_URL  # Ensure the `database.py` file contains this constant
from models import meta_table  # Ensure the `models.py` defines the `meta_table`

# Create the engine and bind the metadata to it
engine = create_engine(DATABASE_URL)
metadata = MetaData()

# Create the meta_table in the database
metadata.create_all(engine)

if __name__ == "__main__":
    print("Meta table created successfully.")
