from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Text, DateTime, ForeignKey
from database import DATABASE_URL
from sqlalchemy.sql import func

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

sessions = Table(
    'sessions',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('session_id', String(255), unique=True, nullable=False),
    Column('created_at', DateTime, server_default=func.now())
)

questions = Table(
    'questions',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('session_id', String(255), ForeignKey('sessions.session_id'), nullable=False),
    Column('question_id', String(255), unique=True, nullable=False),
    Column('question_text', Text, nullable=False),
    Column('created_at', DateTime, server_default=func.now())
)

file_groups = Table(
    'file_groups',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('group_name', String(255), nullable=False),
    Column('created_at', DateTime, server_default=func.now())
)

group_files = Table(
    'group_files',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('group_id', Integer, ForeignKey('file_groups.id'), nullable=False),
    Column('file_name', String(255), nullable=False),
    Column('added_at', DateTime, server_default=func.now())
)

# Create engine and execute the table creation
engine = create_engine(DATABASE_URL)
metadata.create_all(engine)

if __name__ == "__main__":
    print("file_meta table created successfully.")
