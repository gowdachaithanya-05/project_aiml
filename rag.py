from fastapi import HTTPException
import openai
import chromadb
import fitz  # For PDF processing
from docx import Document  # For Word document processing
import os
import logging

# Initialize logging with detailed format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log"),  # Logs will be written to app.log
        logging.StreamHandler()  # Logs will also be output to the console
    ]
)

# Set OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")
logging.info("OpenAI API key loaded.")

# Initialize ChromaDB client
client = chromadb.Client()
collection = client.create_collection(name="court_cases")
logging.info("ChromaDB collection 'court_cases' created or fetched.")

# Function to generate embeddings using OpenAI
def get_openai_embeddings(texts):
    try:
        logging.info(f"Generating embeddings for {len(texts)} text(s)...")
        response = openai.Embedding.create(
            model="text-embedding-ada-002",  # OpenAI's embedding model
            input=texts
        )
        embeddings = [data['embedding'] for data in response['data']]
        logging.info("Embeddings successfully generated.")
        return embeddings
    except Exception as e:
        logging.error(f"Error generating embeddings: {str(e)}")
        raise

# Function to process all files in a given folder
def process_hardcoded_folder(folder_path):
    try:
        logging.info(f"Starting to process folder: {folder_path}")
        # Iterate over all files in the folder
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            if os.path.isfile(file_path):  # Ensure it's a file
                process_file(file_path)  # Process each file
        logging.info("Finished processing all files in folder.")
    except Exception as e:
        logging.error(f"Error processing hardcoded folder: {str(e)}")
        raise

# Function to read text from a .txt file
def read_text_file(file_path):
    try:
        logging.info(f"Reading text file: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        logging.error(f"Error reading text file: {file_path}, Error: {str(e)}")
        raise

# Function to read text from a PDF file
def read_pdf_file(file_path):
    try:
        logging.info(f"Reading PDF file: {file_path}")
        document = fitz.open(file_path)
        text = ""
        for page in document:
            text += page.get_text()
        document.close()
        logging.info(f"Successfully read PDF file: {file_path}")
        return text
    except Exception as e:
        logging.error(f"Error reading PDF file: {file_path}, Error: {str(e)}")
        raise

# Function to read text from a Word document
def read_word_file(file_path):
    try:
        logging.info(f"Reading Word file: {file_path}")
        doc = Document(file_path)
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        logging.info(f"Successfully read Word file: {file_path}")
        return text
    except Exception as e:
        logging.error(f"Error reading Word file: {file_path}, Error: {str(e)}")
        raise

# Function to process a file and add it to ChromaDB
def process_file(file_path):
    try:
        logging.info(f"Processing file: {file_path}")
        file_extension = file_path.split('.')[-1].lower()

        if file_extension == 'txt':
            text = read_text_file(file_path)
        elif file_extension == 'pdf':
            text = read_pdf_file(file_path)
        elif file_extension == 'docx':
            text = read_word_file(file_path)
        else:
            logging.warning(f"Unsupported file type for file: {file_path}")
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
        logging.info(f"Data from {file_path} inserted into ChromaDB successfully.")
    except Exception as e:
        logging.error(f"Error processing file: {file_path}, Error: {str(e)}")
        raise

# Function to query cases from ChromaDB
def query_cases(query_text, n_results=3):
    try:
        logging.info(f"Querying cases with text: '{query_text}'")
        query_embedding = get_openai_embeddings([query_text])[0]
        logging.info(f"Query embedding: {query_embedding}")

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )

        logging.info(f"Results from ChromaDB: {results}")

        # Extract document IDs and metadata (text snippets)
        try:
            if 'ids' in results and len(results['ids']) > 0:
                similar_cases_ids = results['ids'][0]  # Extracts the first list of IDs
                similar_cases_texts = [meta['text'] for meta in results['metadatas'][0]]  # Extract text metadata
                logging.info(f"Query successful, found {len(similar_cases_ids)} matching case(s).")
            else:
                similar_cases_ids = []
                similar_cases_texts = []
                logging.info("No matching cases found.")
        except IndexError:
            similar_cases_ids = []
            similar_cases_texts = []
            logging.info("No matching cases found (IndexError).")

        return similar_cases_ids, similar_cases_texts
    except Exception as e:
        logging.error(f"Error querying cases: {str(e)}")
        raise
