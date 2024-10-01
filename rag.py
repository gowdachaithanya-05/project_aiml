# rag.py

from fastapi import HTTPException
import openai
import chromadb
import fitz  # For PDF processing
from docx import Document  # For Word document processing
import os
from logging_config import get_logger
import numpy as np
from typing import List, Tuple
from chromadb.errors import InvalidCollectionException  # Correctly import the exception

logger = get_logger('rag')

# Set OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")
if openai.api_key:
    logger.info("OpenAI API key loaded.")
else:
    logger.error("OpenAI API key not found in environment variables.")

# Initialize ChromaDB client
client = chromadb.Client()
collection_name = "court_cases"

# Check if collection exists, else create
try:
    collection = client.get_collection(name=collection_name)
    logger.info(f"ChromaDB collection '{collection_name}' fetched successfully.")
except InvalidCollectionException:
    collection = client.create_collection(name=collection_name)
    logger.info(f"ChromaDB collection '{collection_name}' created successfully.")

def get_openai_embeddings(texts: List[str]) -> List[List[float]]:
    """Generates embeddings for a list of texts using OpenAI's Embedding API."""
    if not texts:
        raise ValueError("No texts provided for embedding.")
    try:
        logger.info(f"Generating embeddings for {len(texts)} text(s)...")
        response = openai.Embedding.create(
            model="text-embedding-ada-002",
            input=texts  # Ensure this is a list of strings
        )
        embeddings = [data['embedding'] for data in response['data']]
        logger.info("Embeddings successfully generated.")
        return embeddings
    except Exception as e:
        logger.error(f"Error generating embeddings: {str(e)}")
        raise

def read_text_file(file_path: str) -> str:
    """Reads and returns text from a .txt file."""
    try:
        logger.info(f"Reading text file: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        logger.error(f"Error reading text file: {file_path}, Error: {str(e)}")
        raise

def read_pdf_file(file_path: str) -> str:
    """Reads and returns text from a PDF file."""
    try:
        logger.info(f"Reading PDF file: {file_path}")
        document = fitz.open(file_path)
        text = ""
        for page in document:
            text += page.get_text()
        document.close()
        logger.info(f"Successfully read PDF file: {file_path}")
        return text
    except Exception as e:
        logger.error(f"Error reading PDF file: {file_path}, Error: {str(e)}")
        raise

def read_word_file(file_path: str) -> str:
    """Reads and returns text from a Word (.docx) file."""
    try:
        logger.info(f"Reading Word file: {file_path}")
        doc = Document(file_path)
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        logger.info(f"Successfully read Word file: {file_path}")
        return text
    except Exception as e:
        logger.error(f"Error reading Word file: {file_path}, Error: {str(e)}")
        raise

def process_file(file_path: str):
    """Processes a file based on its type and adds it to ChromaDB."""
    try:
        logger.info(f"Processing file: {file_path}")
        file_extension = file_path.split('.')[-1].lower()

        if file_extension == 'txt':
            text = read_text_file(file_path)
        elif file_extension == 'pdf':
            text = read_pdf_file(file_path)
        elif file_extension == 'docx':
            text = read_word_file(file_path)
        else:
            logger.warning(f"Unsupported file type for file: {file_path}")
            return

        # Generate embeddings
        embeddings = get_openai_embeddings([text])

        # Insert into ChromaDB
        doc_id = os.path.basename(file_path)  # Using filename as document ID
        # Check if document already exists to prevent duplication
        if is_document_present(doc_id):
            logger.info(f"Document '{doc_id}' already exists in ChromaDB. Skipping insertion.")
            return

        collection.add(
            ids=[doc_id],             # Unique identifier for each document
            embeddings=embeddings,    # List of embeddings
            metadatas=[{"text": text}]  # Metadata for each document
        )
        logger.info(f"Data from {file_path} inserted into ChromaDB successfully.")
    except Exception as e:
        logger.error(f"Error processing file: {file_path}, Error: {str(e)}")
        raise

def is_document_present(doc_id: str) -> bool:
    """Checks if a document with the given ID exists in ChromaDB."""
    try:
        result = collection.get(ids=[doc_id])
        exists = bool(result.get('ids') and len(result['ids']) > 0 and result['ids'][0] == doc_id)
        logger.info(f"Document '{doc_id}' presence in ChromaDB: {exists}")
        return exists
    except Exception as e:
        logger.error(f"Error checking document presence for '{doc_id}': {str(e)}")
        return False

def query_cases(query_text: str, n_results: int = 3) -> Tuple[List[str], List[str], List[float]]:
    """Queries ChromaDB for similar cases based on the input text."""
    try:
        logger.info(f"Querying cases with text: '{query_text}'")
        query_embedding = get_openai_embeddings([query_text])[0]
        query_embedding_np = np.array(query_embedding)
        query_embedding_np /= np.linalg.norm(query_embedding_np)  # Normalize

        results = collection.query(
            query_embeddings=[query_embedding_np.tolist()],
            n_results=n_results,
            include=["distances", "metadatas"]
        )

        logger.info(f"Results from ChromaDB: {results}")

        if 'ids' in results and len(results['ids']) > 0:
            similar_cases_ids = results['ids'][0]
            similar_cases_texts = [meta['text'] for meta in results['metadatas'][0]]
            similar_cases_distances = results['distances'][0]
            # Convert distances to similarity scores
            similar_cases_similarities = [1 / (1 + d) for d in similar_cases_distances]
            logger.info(f"Query successful, found {len(similar_cases_ids)} matching case(s).")
        else:
            similar_cases_ids = []
            similar_cases_texts = []
            similar_cases_similarities = []
            logger.info("No matching cases found.")

        return similar_cases_ids, similar_cases_texts, similar_cases_similarities
    except Exception as e:
        logger.error(f"Error querying cases: {str(e)}")
        raise

# rag.py

def query_cases_by_group(file_names: List[str], query_text: str, threshold: float, n_results: int = 3) -> Tuple[List[str], List[str], List[float]]:
    """Queries ChromaDB for similar cases within specific file groups based on the input text."""
    try:
        logger.info(f"Querying cases for files {file_names} with text: '{query_text}'")
        query_embedding = get_openai_embeddings([query_text])[0]
        query_embedding_np = np.array(query_embedding)
        query_embedding_np /= np.linalg.norm(query_embedding_np)  # Normalize

        # Fetch embeddings and metadata for the specified file_names
        group_docs = collection.get(ids=file_names, include=["embeddings", "metadatas"])

        if not group_docs.get('ids'):
            logger.info("No matching cases found for the selected group(s).")
            return [], [], []

        # Correctly assign fetched data
        fetched_ids = group_docs['ids']
        fetched_metadatas = group_docs['metadatas']
        fetched_embeddings = group_docs['embeddings']

        if not fetched_ids:
            logger.info("No matching cases found for the selected group(s).")
            return [], [], []

        if not (len(fetched_ids) == len(fetched_metadatas) == len(fetched_embeddings)):
            logger.error("Mismatch in lengths of ids, metadatas, and embeddings from ChromaDB.")
            return [], [], []

        # Compute cosine similarity between query_embedding and each document embedding
        similarities = []
        for doc_embedding in fetched_embeddings:
            doc_embedding_np = np.array(doc_embedding)
            norm = np.linalg.norm(doc_embedding_np)
            if norm == 0:
                similarity = 0.0
            else:
                doc_embedding_np /= norm  # Normalize
                similarity = float(np.dot(query_embedding_np, doc_embedding_np))
            similarities.append(similarity)

        # Combine into list of tuples
        combined = list(zip(fetched_ids, [meta['text'] for meta in fetched_metadatas], similarities))

        # Filter based on threshold
        filtered = [doc for doc in combined if doc[2] >= threshold]

        if not filtered:
            logger.info("No documents with similarity above the threshold.")
            return [], [], []

        # Sort by similarity descending
        filtered.sort(key=lambda x: x[2], reverse=True)

        # Select top N
        top_docs = filtered[:n_results]

        ids = [doc[0] for doc in top_docs]
        texts = [doc[1] for doc in top_docs]
        sims = [doc[2] for doc in top_docs]

        logger.info(f"Top {len(top_docs)} similar documents: {ids} with similarities: {sims}")

        return ids, texts, sims

    except Exception as e:
        logger.error(f"Error querying cases by group: {str(e)}")
        raise
