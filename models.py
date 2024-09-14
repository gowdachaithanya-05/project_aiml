from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String
from database import DATABASE_URL

# Define metadata and table
metadata = MetaData()

meta_table = Table(
    'file_meta',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('file_name', String(255), nullable=False),
    Column('file_size', Integer, nullable=False),
    Column('upload_timestamp', String(255), nullable=False),
    Column('user', String(255), nullable=True)
)

# Create engine and execute the table creation
engine = create_engine(DATABASE_URL)
metadata.create_all(engine)

if __name__ == "__main__":
    print("file_meta table created successfully.")
