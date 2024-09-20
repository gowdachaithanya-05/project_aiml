from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, File, UploadFile, Query, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path
from database import Database, database  # Make sure this exists
from models import meta_table, sessions, questions, file_groups, group_files # Make sure this exists
import openai
import os
import logging
from datetime import datetime
from typing import List
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
import asyncio
from rag import process_hardcoded_folder, query_cases  # Import functions from rag.py
from rag import process_file  # Import file processing function
import re
import uuid

# Utility function for consistent JSON responses
def create_json_response(success: bool, message: str, details: dict = None):
    return JSONResponse(content={"success": success, "message": message, "details": details})

# Load environment variables from .env file
load_dotenv()

# Initialize logging
# logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

log_filename = "./logs/document_service.log"

# Ensure the log file exists, create it if it doesn't
if not os.path.exists(log_filename):
    # Create the file
    with open(log_filename, 'w') as f:
        pass  # Just create an empty file
    
log_handler = RotatingFileHandler(log_filename, maxBytes=5 * 1024 * 1024, backupCount=3)  # 5MB log size with 3 backups
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[log_handler]
)

class OpenAIChatManager:
    """Handles communication with the OpenAI API."""
    def __init__(self, api_key: str):
        openai.api_key = api_key

    def get_response(self, user_input: str) -> str:
        """Fetches the response from OpenAI for a given input."""
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": user_input}],
                max_tokens=150
            )
            return response.choices[0].message['content'].strip()
        except Exception as e:
            logging.error("Error getting OpenAI response: %s", str(e))
            return "Error getting response"


class FileManager:
    """Manages file uploads to the server."""
    def __init__(self, upload_folder: str):
        self.upload_folder = upload_folder
        self._ensure_upload_folder()

    def _ensure_upload_folder(self):
        """Creates the upload folder if it doesn't exist."""
        if not os.path.exists(self.upload_folder):
            os.makedirs(self.upload_folder)
            logging.info("Created uploads folder: %s", self.upload_folder)

    async def get_existing_files(self) -> List[str]:
        """Returns a list of existing files in the upload folder."""
        return [f for f in os.listdir(self.upload_folder) if os.path.isfile(os.path.join(self.upload_folder, f))]
    
    async def save_files(self, files: List[UploadFile]) -> dict:
        """Saves uploaded files to the server, stores metadata in the database, and processes for ChromaDB."""
        try:
            for file in files:
                file_location = os.path.join(self.upload_folder, file.filename)
                
                # Save the file to the filesystem
                with open(file_location, "wb") as f:
                    f.write(await file.read())
                logging.info("File uploaded successfully: %s", file.filename)

                # Get file metadata
                file_size = os.path.getsize(file_location)
                upload_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Insert file metadata into the database
                query = meta_table.insert().values(
                    file_name=file.filename,
                    file_size=file_size,
                    upload_timestamp=upload_timestamp,
                    user=None  # Assuming no user info for now
                )
                await database.execute(query)
                logging.info("File metadata stored in the database for: %s", file.filename)

                # Process the file for ChromaDB
                try:
                    process_file(file_location)
                    logging.info(f"File {file.filename} processed and added to ChromaDB")
                except Exception as e:
                    logging.error(f"Error processing file {file.filename} for ChromaDB: {str(e)}")

            return {"success": True, "details": [file.filename for file in files]}

        except Exception as e:
            logging.error("Error uploading files, saving metadata, or processing for ChromaDB: %s", str(e))
            return {"success": False, "error": f"Failed to upload: {str(e)}"}
        
        
class WebSocketManager:
    """Handles WebSocket connections for chat interactions."""
    def __init__(self, chat_manager: OpenAIChatManager):
        self.chat_manager = chat_manager

    async def handle_websocket(self, websocket: WebSocket):
        """Manages the WebSocket lifecycle and communication."""
        await websocket.accept()
        session_id = str(uuid.uuid4())  # Generate a new session ID
        await self.store_session(session_id)  # Store the session ID in the database
        logging.info("WebSocket connection accepted")
        try:
            while True:
                data = await websocket.receive_text()
                logging.debug(f"Received message: {data}")
                question_id = str(uuid.uuid4())  # Generate a unique question ID
                await self.store_question(session_id, question_id, data)  # Store the question

                # Query ChromaDB for relevant cases
                ids, texts = query_cases(data)

                if texts and len(texts) > 0:  # Relevant cases are found
                    logging.info(f"ChromaDB found results: {texts}")
                    
                    # Check if the results seem relevant enough (e.g., by thresholding length)
                    if len(texts[0]) > 50:  # Assuming a case result should have more than 50 characters
                        combined_query = f"User query: {data}\nRelevant cases: {texts[0]}"
                        openai_response = self.chat_manager.get_response(combined_query)
                        answer = f"Relevant Case IDs: {ids}\nText: {texts[0]}\n\nOpenAI Response: {openai_response}"
                    else:
                        logging.info("ChromaDB returned results but not relevant, querying OpenAI directly.")
                        openai_response = self.chat_manager.get_response(f"{data}\nNo relevant cases found.")
                        answer = f"AI Response: {openai_response}"

                else:  # No relevant cases found
                    logging.info("No relevant cases found in ChromaDB, querying OpenAI.")
                    # Send the original query and mention that no relevant cases were found
                    openai_response = self.chat_manager.get_response(f"{data}\nNo relevant cases found.")
                    answer = f"AI Response: {openai_response}"

                logging.info(f"Sending answer: {answer}")
                await websocket.send_text(answer)
        except WebSocketDisconnect:
            logging.warning("WebSocket client disconnected")
        except Exception as e:
            logging.error(f"WebSocket error: {str(e)}")
    async def store_session(self, session_id: str):
        query = "INSERT INTO sessions (session_id) VALUES (:session_id)"
        await database.execute(query, values={"session_id": session_id})

    async def store_question(self, session_id: str, question_id: str, question_text: str):
        query = "INSERT INTO questions (session_id, question_id, question_text) VALUES (:session_id, :question_id, :question_text)"
        await database.execute(query, values={"session_id": session_id, "question_id": question_id, "question_text": question_text})

    async def get_chat_history(self, session_id: str):
        query = "SELECT question_id, question_text FROM questions WHERE session_id = :session_id"
        results = await database.fetch_all(query, values={"session_id": session_id})
        return results


class Application:
    """Encapsulates the entire FastAPI application logic."""
    def __init__(self):
        # Instantiate FastAPI app
        self.app = FastAPI()

        # Initialize components
        self.file_manager = FileManager(upload_folder="./uploads")
        self.chat_manager = OpenAIChatManager(api_key=os.getenv("OPENAI_API_KEY"))
        self.websocket_manager = WebSocketManager(chat_manager=self.chat_manager)

        self.folder_path = r"./uploads"

        # Set up middleware and routes
        self._setup_middleware()
        self._setup_routes()
        
        @self.app.on_event("startup")
        async def startup_event():
            logging.info("Server startup: processing folder.")
            asyncio.create_task(self.process_folder_async())

    def _setup_middleware(self):
        """Sets up CORS middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_routes(self):
        """Defines API routes for the application."""
        # Serve static files
        self.app.mount("/static", StaticFiles(directory="static"), name="static")

        @self.app.get("/get-existing-files")
        async def get_existing_files():
            return await self.file_manager.get_existing_files()

        @self.app.get("/get-file-groups")
        async def get_file_groups():
            query = file_groups.select()
            results = await database.fetch_all(query)
            return [{"id": row['id'], "group_name": row['group_name']} for row in results]

        
        @self.app.post("/create-file-group")
        async def create_file_group(
            group_name: str = Form(...), 
            files: List[str] = Form(...)
        ):
            if not group_name or len(files) == 0:
                raise HTTPException(status_code=400, detail="Group name and at least one file must be provided.")

            try:
                # Insert the new group into the database
                query = file_groups.insert().values(group_name=group_name)
                result = await database.execute(query)
                group_id = result

                # Check if group_id was created successfully
                if not group_id:
                    raise HTTPException(status_code=500, detail="Failed to create file group.")

                # Associate files with the group
                for file in files:
                    query = group_files.insert().values(group_id=group_id, file_name=file)
                    await database.execute(query)

                return {"success": True, "message": "File group created successfully."}
            
            except Exception as e:
                logging.error(f"Error creating file group: {str(e)}")
                # Returning a more generic error message to the client
                raise HTTPException(status_code=500, detail="An error occurred while creating the file group.")


        # File upload route for handling multiple files
        @self.app.post("/upload")
        async def upload_files(files: List[UploadFile] = File(...)):
            result = await self.file_manager.save_files(files)
            if result["success"]:
                return create_json_response(True, "Files uploaded and processed successfully", {"files": result["details"]})
            else:
                return create_json_response(False, "Error occurred during upload or processing", {"error": result["error"]})
        
        # Serve the main HTML page
        @self.app.get("/", response_class=HTMLResponse)
        async def get_index():
            index_path = Path(__file__).parent / "templates/index.html"
            try:
                with open(index_path, "r") as file:
                    logging.info("Served index.html")
                    return HTMLResponse(content=file.read())
            except Exception as e:
                logging.error("Error serving index.html: %s", str(e))
                return HTMLResponse(content="Error loading index.html", status_code=500)

        # Add an endpoint to process the folder on demand
        @self.app.post("/process-folder/")
        async def process_folder():
            await self.process_folder_async()
            return {"message": "Files processed successfully."}
        
        # WebSocket route for chat
        @self.app.websocket("/ws/chat")
        async def websocket_endpoint(websocket: WebSocket):
            await self.websocket_manager.handle_websocket(websocket)

        @self.app.get("/get-chat-history")
        async def get_chat_history(session_id: str):
        #Fetches the entire chat history for a given session ID.
            history = await self.websocket_manager.get_chat_history(session_id)
            return [{"question_id": row.question_id, "question_text": row.question_text} for row in history]

    async def process_folder_async(self):
        """Process folder asynchronously without blocking the server."""
        try:
            logging.info(f"Starting to process folder: {self.folder_path}")
            for filename in os.listdir(self.folder_path):
                file_path = os.path.join(self.folder_path, filename)
                if os.path.isfile(file_path):
                    process_file(file_path)  # Process each file
            logging.info("Finished processing all files in folder.")
        except Exception as e:
            logging.error(f"Error processing folder: {str(e)}")
    
    async def startup(self):
        """Connect to the database on app startup."""
        await database.connect()
        logging.info("Database connected")

    async def shutdown(self):
        """Disconnect from the database on app shutdown."""
        await database.disconnect()
        logging.info("Database disconnected")


# Instantiate the application
application = Application()
app = application.app  # Expose the FastAPI app for the server

# Add startup and shutdown events
@app.on_event("startup")
async def startup():
    await application.startup()

@app.on_event("shutdown")
async def shutdown():
    await application.shutdown()
