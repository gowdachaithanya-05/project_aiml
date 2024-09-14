from sqlalchemy import create_engine, MetaData
from databases import Database

# Replace 'your_password' with the actual password for your 'postgres' user
DATABASE_URL = "postgresql://postgres:7722@localhost:5432/doc_db"

engine = create_engine(DATABASE_URL)
metadata = MetaData()

# Initialize the Database object for async DB operations
database = Database(DATABASE_URL)
