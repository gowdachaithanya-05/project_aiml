#embedding_independent.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import openai
import chromadb
import fitz  # For PDF processing
from docx import Document  # For Word document processing
import os
from logging_config import get_logger

# Initialize logging
# logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = get_logger('embedding_independent')

# Set OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Initialize FastAPI app
app = FastAPI()

# Initialize ChromaDB client
client = chromadb.Client()

# Create or get a collection in ChromaDB
collection = client.create_collection(name="court_cases")  # Collection for court cases

# Hardcoded folder path
HARD_CODED_FOLDER_PATH = r"C:\Users\Alwis\Desktop\Sidrah\Degreed Project\tosid\cases"  # Replace with the actual path

# Function to generate embeddings using OpenAI
def get_openai_embeddings(texts):
    try:
        response = openai.Embedding.create(
            model="text-embedding-ada-002",  # OpenAI's embedding model
            input=texts
        )
        embeddings = [data['embedding'] for data in response['data']]
        return embeddings
    except Exception as e:
        logger.error("Error generating embeddings: %s", str(e))
        raise

# Function to read text from a .txt file
def read_text_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        logger.error("Error reading text file: %s", str(e))
        raise

# Function to read text from a PDF file
def read_pdf_file(file_path):
    try:
        document = fitz.open(file_path)
        text = ""
        for page in document:
            text += page.get_text()
        document.close()
        return text
    except Exception as e:
        logger.error("Error reading PDF file: %s", str(e))
        raise

# Function to read text from a Word document
def read_word_file(file_path):
    try:
        doc = Document(file_path)
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        return text
    except Exception as e:
        logger.error("Error reading Word file: %s", str(e))
        raise

# Function to process a file and add it to ChromaDB
def process_file(file_path):
    try:
        file_extension = file_path.split('.')[-1].lower()
        
        if file_extension == 'txt':
            text = read_text_file(file_path)
        elif file_extension == 'pdf':
            text = read_pdf_file(file_path)
        elif file_extension == 'docx':
            text = read_word_file(file_path)
        else:
            logger.warning("Unsupported file type for file: %s", file_path)
            return
        
        # Generate embeddings
        embedding = get_openai_embeddings([text])[0]
        
        # Insert into ChromaDB
        doc_id = os.path.basename(file_path)  # Using filename as document ID
        collection.add(
            ids=[doc_id],          # Unique identifier for each document
            embeddings=[embedding], # Embedding vector
            metadatas=[{"text": text}]  # Metadata for each document
        )
        logger.info("Data from %s inserted into ChromaDB successfully.", file_path)
    except Exception as e:
        logger.error("Error processing file: %s", str(e))
        raise

# Function to process all files in the hardcoded folder
def process_hardcoded_folder():
    try:
        for filename in os.listdir(HARD_CODED_FOLDER_PATH):
            file_path = os.path.join(HARD_CODED_FOLDER_PATH, filename)
            if os.path.isfile(file_path):
                process_file(file_path)
    except Exception as e:
        logger.error("Error processing hardcoded folder: %s", str(e))
        raise

# Function to query cases from ChromaDB
def query_cases(query_text, n_results=1):
    try:
        query_embedding = get_openai_embeddings([query_text])[0]

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )

        # Extract document IDs and metadata (text snippets)
        try:
            similar_cases_ids = results['ids'][0]  # Extracts the first list of IDs
            similar_cases_texts = [meta['text'] for meta in results['metadatas'][0]]  # Extract text metadata
        except IndexError:
            similar_cases_ids = []
            similar_cases_texts = []

        return similar_cases_ids, similar_cases_texts
    except Exception as e:
        logger.error("Error querying cases: %s", str(e))
        raise

# Endpoint to process files in the hardcoded folder
@app.post("/process-folder/")
async def process_folder_endpoint():
    try:
        process_hardcoded_folder()
        return {"message": "Files processed successfully."}
    except Exception as e:
        logger.error("Error processing folder endpoint: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))

# Endpoint to query cases
class QueryRequest(BaseModel):
    query: str

@app.post("/query/")
async def query_endpoint(request: QueryRequest):
    try:
        ids, texts = query_cases(request.query)
        return {"ids": ids, "answer": texts}
    except Exception as e:
        logger.error("Error querying endpoint: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))

# To run the server: uvicorn 5c:app --reload
