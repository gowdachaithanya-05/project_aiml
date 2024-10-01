# check.py

import chromadb
from chromadb.errors import InvalidCollectionException
from logging_config import get_logger  # Ensure this exists and is correctly configured

logger = get_logger('check')

# Initialize ChromaDB client with persistent storage
client = chromadb.PersistentClient(persist_directory="./chroma_db")
collection_name = "court_cases"

try:
    collection = client.get_collection(name=collection_name)
    logger.info(f"ChromaDB collection '{collection_name}' fetched successfully.")
except InvalidCollectionException:
    collection = client.create_collection(name=collection_name)
    logger.info(f"ChromaDB collection '{collection_name}' created successfully.")

# Optionally, you can add a sample document to verify
sample_doc = {
    "id": "sample_doc",
    "text": "This is a sample document for testing."
}

try:
    collection.add(
        ids=[sample_doc["id"]],
        embeddings=[[0.1, 0.2, 0.3]],  # Sample embedding vector
        metadatas=[{"text": sample_doc["text"]}]
    )
    logger.info(f"Sample document '{sample_doc['id']}' added to ChromaDB.")
except Exception as e:
    logger.error(f"Error adding sample document: {e}")
