# app.py

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path
import logging
from database import Database, database
from models import meta_table, sessions, questions, file_groups, group_files, chat_history
import openai
import os
from logging_config import get_logger
from datetime import datetime
from typing import List, Optional, Tuple
from dotenv import load_dotenv
import asyncio
from rag import query_cases, query_cases_by_group, process_file, is_document_present
from sqlalchemy import insert, select
import uuid
import json
from pydantic import BaseModel
import traceback
from logging.handlers import RotatingFileHandler
from concurrent.futures import ThreadPoolExecutor
from elasticapm.contrib.starlette import ElasticAPM, make_apm_client
from elasticapm import capture_span
from elasticapm.handlers.logging import LoggingFilter


# Utility function for consistent JSON responses
def create_json_response(success: bool, message: str, details: dict = None):
    return JSONResponse(content={"success": success, "message": message, "details": details})

# Load environment variables from .env file
load_dotenv()

# Initialize logging
logger = get_logger('app')

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
            logger.error("Error getting OpenAI response: %s", str(e))
            return "I'm sorry, I couldn't process your request at the moment."

class FileManager:
    """Manages file uploads to the server."""
    def __init__(self, upload_folder: str):
        self.upload_folder = upload_folder
        self._ensure_upload_folder()

    def _ensure_upload_folder(self):
        """Creates the upload folder if it doesn't exist."""
        if not os.path.exists(self.upload_folder):
            os.makedirs(self.upload_folder)
            logger.info("Created uploads folder: %s", self.upload_folder)

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
                logger.info("File uploaded successfully: %s", file.filename)

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
                logger.info("File metadata stored in the database for: %s", file.filename)

                # Process the file for ChromaDB
                try:
                    process_file(file_location)
                    logger.info(f"File {file.filename} processed and added to ChromaDB")
                except Exception as e:
                    logger.error(f"Error processing file {file.filename} for ChromaDB: {str(e)}")

            return {"success": True, "details": [file.filename for file in files]}

        except Exception as e:
            logger.error("Error uploading files, saving metadata, or processing for ChromaDB: %s", str(e))
            return {"success": False, "error": f"Failed to upload: {str(e)}"}
        

class WebSocketManager:
    """Handles WebSocket connections for chat interactions."""
    def __init__(self, chat_manager: OpenAIChatManager):
        self.chat_manager = chat_manager

    async def handle_websocket(self, websocket: WebSocket):
        """Manages the WebSocket lifecycle and communication."""
        await websocket.accept()
        logger.info("WebSocket connection accepted")
        try:
            while True:
                data = await websocket.receive_text()
                logger.debug(f"Received message: {data}")

                # Parse the JSON message to extract session_id, message, and group_ids
                try:
                    message_data = json.loads(data)
                    session_id = message_data.get('session_id')
                    message = message_data.get('message')
                    group_ids = message_data.get('group_ids')  # Get group IDs if provided
                except json.JSONDecodeError:
                    logger.error("Invalid JSON received")
                    continue

                if not session_id:
                    # Generate a new session ID if not provided
                    session_id = str(uuid.uuid4())
                    await self.store_session(session_id)
                else:
                    # Check if the session exists; if not, create it
                    existing_session = await self.get_session(session_id)
                    if not existing_session:
                        await self.store_session(session_id)

                question_id = str(uuid.uuid4())  # Generate a unique question ID
                await self.store_question(session_id, question_id, message)  # Store the question

                # Store user message in chat_history
                await self.store_chat_message(session_id, 'user', message)

                # Retrieve last N messages for context (e.g., last 5 messages)
                chat_history_records = await self.get_recent_chat_history(session_id, limit=5)
                context = "\n".join([
                    f"{record['sender'].capitalize()}: {record['message']}" for record in chat_history_records
                ])

                # Prepare the prompt with context
                prompt = f"{context}\nUser: {message}\nAI:"

                # Initialize variables for ChromaDB results
                ids = []
                texts = []
                similarities = []

                # Handle group-based queries
                if group_ids:
                    # Fetch the file names associated with the group IDs from the database
                    query = group_files.select().where(group_files.c.group_id.in_(group_ids))
                    group_file_records = await database.fetch_all(query)
                    file_names = [record['file_name'] for record in group_file_records]

                    # Log the file names fetched
                    logger.info(f"Fetched file names for group IDs {group_ids}: {file_names}")

                    if not file_names:
                        logger.error("No files found for the selected groups.")
                        # Instead of sending a static message, generate a response via OpenAI
                        openai_prompt = f"{context}\nYou mentioned specific groups, but no documents were found associated with those groups.\n\nPlease provide an appropriate response based on the available information."
                        openai_response = self.chat_manager.get_response(openai_prompt)
                        answer = openai_response
                        logger.info(f"Sending answer: {answer}")
                        await websocket.send_text(answer)
                        # Store bot response in chat_history
                        await self.store_chat_message(session_id, 'bot', answer)
                        continue

                    # Now check if these documents are in ChromaDB, and process if not
                    missing_files = []
                    for file_name in file_names:
                        if not is_document_present(file_name):
                            missing_files.append(file_name)
                            logger.info(f"Document '{file_name}' is missing from ChromaDB and will be processed.")

                    if missing_files:
                        logger.info(f"Processing missing files: {missing_files}")
                        for file_name in missing_files:
                            file_path = os.path.join("./uploads", file_name)
                            if os.path.exists(file_path):
                                try:
                                    # Run process_file in an executor to avoid blocking
                                    loop = asyncio.get_event_loop()
                                    await loop.run_in_executor(None, process_file, file_path)
                                    logger.info(f"Processed and added '{file_name}' to ChromaDB.")
                                except Exception as e:
                                    logger.error(f"Failed to process '{file_name}': {str(e)}")
                            else:
                                logger.error(f"File '{file_name}' does not exist in uploads folder.")

                    # Now all documents should be in ChromaDB
                    # Proceed to query ChromaDB with these documents
                    existing_files = []
                    for file_name in file_names:
                        if is_document_present(file_name):
                            existing_files.append(file_name)
                        else:
                            logger.warning(f"Document '{file_name}' is still missing from ChromaDB after processing.")

                    if not existing_files:
                        logger.error("No documents found in ChromaDB after processing.")
                        # Generate response via OpenAI
                        openai_prompt = f"{context}\nYou attempted to query specific groups, but no relevant documents were found in ChromaDB after processing.\n\nPlease provide an appropriate response based on the available information."
                        openai_response = self.chat_manager.get_response(openai_prompt)
                        answer = openai_response
                        logger.info(f"Sending answer: {answer}")
                        await websocket.send_text(answer)
                        # Store bot response in chat_history
                        await self.store_chat_message(session_id, 'bot', answer)
                        continue

                    # Query ChromaDB with the existing files
                    ids, texts, similarities = query_cases_by_group(existing_files, message, threshold=0.8)

                    if not ids:
                        logger.error("No documents found with the given criteria after querying ChromaDB.")
                        # Generate response via OpenAI
                        openai_prompt = f"{context}\nYou queried specific groups, but ChromaDB returned no relevant documents.\n\nPlease provide an appropriate response based on the available information."
                        openai_response = self.chat_manager.get_response(openai_prompt)
                        answer = openai_response
                        logger.info(f"Sending answer: {answer}")
                        await websocket.send_text(answer)
                        # Store bot response in chat_history
                        await self.store_chat_message(session_id, 'bot', answer)
                        continue

                    # Log the query results
                    logger.info(f"Query results: IDs={ids}, Similarities={similarities}")

                else:
                    # Query ChromaDB for relevant cases
                    ids, texts, similarities = query_cases(message)

                # At this point, regardless of query type, we have ids, texts, similarities
                # Now generate a unified response using OpenAI
                if texts and len(texts) > 0:
                    # Combine all relevant information into a prompt for OpenAI
                    chroma_info = "\n".join([
                        f"Case ID: {id_}\nText: {text}\nSimilarity: {similarity}"
                        for id_, text, similarity in zip(ids, texts, similarities)
                    ])
                    combined_prompt = f"{context}\nRelevant Cases:\n{chroma_info}\n\nPlease provide a refined response based on the above information."

                    openai_response = self.chat_manager.get_response(combined_prompt)
                    answer = openai_response
                else:
                    # No relevant cases found, prompt OpenAI accordingly
                    openai_prompt = f"{context}\nNo relevant cases found for your query.\n\nPlease provide a response based on the available information."
                    openai_response = self.chat_manager.get_response(openai_prompt)
                    answer = openai_response

                logger.info(f"Sending answer: {answer}")
                await websocket.send_text(answer)

                # Store bot response in chat_history
                await self.store_chat_message(session_id, 'bot', answer)


        except WebSocketDisconnect:
            logger.warning("WebSocket client disconnected")
        except Exception as e:
            logger.error(f"WebSocket error: {str(e)}")

    async def get_session(self, session_id: str):
        """Checks if a session exists in the database."""
        query = select(sessions).where(sessions.c.session_id == session_id)
        result = await database.fetch_one(query)
        return result

    async def store_session(self, session_id: str):
        """Stores a new chat session in the database."""
        query = insert(sessions).values(
            session_id=session_id,
            is_archived=False  # Ensure that is_archived is set to False for new sessions
        )
        await database.execute(query)

    async def store_question(self, session_id: str, question_id: str, question_text: str):
        """Stores a question in the database."""
        query = "INSERT INTO questions (session_id, question_id, question_text) VALUES (:session_id, :question_id, :question_text)"
        await database.execute(query, values={"session_id": session_id, "question_id": question_id, "question_text": question_text})

    async def get_chat_history(self, session_id: str):
        """Fetches the entire chat history for a given session ID."""
        query = select(chat_history).where(chat_history.c.session_id == session_id).order_by(chat_history.c.timestamp)
        results = await database.fetch_all(query)
        return results

    async def store_chat_message(self, session_id: str, sender: str, message: str):
        """Stores a chat message in the chat_history table."""
        query = chat_history.insert().values(
            session_id=session_id,
            sender=sender,
            message=message,
            timestamp=datetime.now()
        )
        await database.execute(query)

    async def get_recent_chat_history(self, session_id: str, limit: int = 5):
        """Retrieves the most recent chat messages for a session."""
        query = select(chat_history).where(chat_history.c.session_id == session_id).order_by(chat_history.c.timestamp.desc()).limit(limit)
        results = await database.fetch_all(query)
        # Reverse to maintain chronological order
        return results[::-1]

class Application:
    """Encapsulates the entire FastAPI application logic."""
    def __init__(self):
        # Instantiate FastAPI app
        self.app = FastAPI()

        # Elastic APM integration
        apm_config = {
            'SERVICE_NAME': 'projects_trace',
            'SERVER_URL': 'http://apm-server:8200',  # Ensure this matches your APM server URL (use apm-server in Docker)
            'ENVIRONMENT': 'production',
            'DEBUG': True,  # Set this to True to help with any issues while debugging
            'TRANSACTION_SAMPLE_RATE': 1.0  # Capture all transactions
        }
        self.apm_client = make_apm_client(apm_config)
        self.app.add_middleware(ElasticAPM, client=self.apm_client)

        # Initialize components
        self.file_manager = FileManager(upload_folder="./uploads")
        self.chat_manager = OpenAIChatManager(api_key=os.getenv("OPENAI_API_KEY"))
        self.websocket_manager = WebSocketManager(chat_manager=self.chat_manager)

        self.folder_path = r"./uploads"

        # Initialize a ThreadPoolExecutor for running synchronous tasks
        self.executor = ThreadPoolExecutor(max_workers=5)

        # Set up middleware and routes
        self._setup_middleware()
        self._setup_routes()
        
        @self.app.on_event("startup")
        async def startup_event():
            logger.info("Server startup: processing folder.")
            asyncio.create_task(self.process_folder_async())

    def _setup_middleware(self):
        """Sets up CORS middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Adjust as needed for security
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_routes(self):
        """Defines API routes for the application."""
        # Serve static files
        self.app.mount("/static", StaticFiles(directory="static"), name="static")
        
        @self.app.get("/get-group-files/{group_id}")
        async def get_group_files(group_id: int):
            try:
                # Get the group name
                group_query = file_groups.select().where(file_groups.c.id == group_id)
                group = await database.fetch_one(group_query)
                if not group:
                    raise HTTPException(status_code=404, detail="Group not found")
                
                # Get the files in the group
                files_query = group_files.select().where(group_files.c.group_id == group_id)
                group_files_result = await database.fetch_all(files_query)
                group_file_names = [row['file_name'] for row in group_files_result]
                
                # Get all files in the database
                all_files_query = meta_table.select()
                all_files_result = await database.fetch_all(all_files_query)
                all_file_names = [row['file_name'] for row in all_files_result]
                
                return {
                    "group_name": group['group_name'],
                    "group_files": group_file_names,
                    "all_files": all_file_names
                }
            except Exception as e:
                logging.error(f"Error getting group files: {str(e)}")
                raise HTTPException(status_code=500, detail="An error occurred while fetching group files")

        @self.app.post("/update-group")
        async def update_group(
            group_id: int = Form(...),
            group_name: str = Form(...),
            files: List[str] = Form(...)
        ):
            try:
                # Update group name
                update_group_query = file_groups.update().where(file_groups.c.id == group_id).values(group_name=group_name)
                await database.execute(update_group_query)
                
                # Delete existing file associations
                delete_files_query = group_files.delete().where(group_files.c.group_id == group_id)
                await database.execute(delete_files_query)
                
                # Add new file associations
                for file in files:
                    insert_file_query = group_files.insert().values(group_id=group_id, file_name=file)
                    await database.execute(insert_file_query)
                
                return JSONResponse(content={"success": True, "message": "Group updated successfully"})
            except Exception as e:
                logging.error(f"Error updating group: {str(e)}")
                return JSONResponse(content={"success": False, "error": "An error occurred while updating the group"})
        
        @self.app.post("/rename-group")
        async def rename_group(group_data: dict):
            group_id = group_data.get('group_id')
            new_name = group_data.get('new_name')
            
            if not group_id or not new_name:
                raise HTTPException(status_code=400, detail="Group ID and new name are required.")
            
            try:
                query = file_groups.update().where(file_groups.c.id == group_id).values(group_name=new_name)
                await database.execute(query)
                return {"success": True, "message": "Group renamed successfully."}
            except Exception as e:
                logging.error(f"Error renaming group: {str(e)}")
                raise HTTPException(status_code=500, detail="An error occurred while renaming the group.")

        @self.app.post("/delete-group")
        async def delete_group(group_data: dict):
            group_id = group_data.get('group_id')
            
            if not group_id:
                raise HTTPException(status_code=400, detail="Group ID is required.")
            
            try:
                # First, delete associated files from group_files table
                delete_files_query = group_files.delete().where(group_files.c.group_id == group_id)
                await database.execute(delete_files_query)
                
                # Then, delete the group from file_groups table
                delete_group_query = file_groups.delete().where(file_groups.c.id == group_id)
                await database.execute(delete_group_query)
                
                return {"success": True, "message": "Group deleted successfully."}
            except Exception as e:
                logging.error(f"Error deleting group: {str(e)}")
                raise HTTPException(status_code=500, detail="An error occurred while deleting the group.")
        
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
                existing_files = await self.file_manager.get_existing_files()
                if not all(file in existing_files for file in files):
                    raise HTTPException(status_code=400, detail="One or more selected files do not exist in the database.")
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
                    logger.info("Served index.html")
                    return HTMLResponse(content=file.read())
            except Exception as e:
                logger.error("Error serving index.html: %s", str(e))
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

        # Define /get-chat-history endpoint once
        @self.app.get("/get-chat-history")
        async def get_chat_history(session_id: str):
            history = await self.websocket_manager.get_chat_history(session_id)
            return [{"sender": row.sender, "message": row.message, "timestamp": row.timestamp} for row in history]
        
        @self.app.post("/archive-session/")
        async def archive_session(session_id: str = Form(...)):
            """Archives a chat session."""
            query = sessions.update().where(sessions.c.session_id == session_id).values(is_archived=True)
            result = await database.execute(query)
            if result:
                logger.info(f"Session {session_id} archived successfully.")
                return create_json_response(True, "Session archived successfully.")
            else:
                logger.error(f"Failed to archive session {session_id}.")
                return create_json_response(False, "Failed to archive session.")

        @self.app.post("/unarchive-session/")
        async def unarchive_session(session_id: str = Form(...)):
            """Unarchives a chat session."""
            query = sessions.update().where(sessions.c.session_id == session_id).values(is_archived=False)
            result = await database.execute(query)
            if result:
                logger.info(f"Session {session_id} unarchived successfully.")
                return create_json_response(True, "Session unarchived successfully.")
            else:
                logger.error(f"Failed to unarchive session {session_id}.")
                return create_json_response(False, "Failed to unarchive session.")

        @self.app.get("/get-active-sessions/")
        async def get_active_sessions():
            """Fetches all active (non-archived) chat sessions."""
            query = sessions.select().where(sessions.c.is_archived == False).order_by(sessions.c.created_at.desc())
            results = await database.fetch_all(query)
            return [{"session_id": row['session_id'], "created_at": row['created_at']} for row in results]

        @self.app.get("/get-archived-sessions/")
        async def get_archived_sessions():
            """Fetches all archived chat sessions."""
            query = sessions.select().where(sessions.c.is_archived == True).order_by(sessions.c.created_at.desc())
            results = await database.fetch_all(query)
            return [{"session_id": row['session_id'], "created_at": row['created_at']} for row in results]
        
        @self.app.post("/rename-session/")
        async def rename_session(session_id: str = Form(...), new_name: str = Form(...)):
            """Renames a chat session."""
            try:
                query = sessions.update().where(sessions.c.session_id == session_id).values(session_name=new_name)
                result = await database.execute(query)
                if result:
                    logger.info(f"Session {session_id} renamed to {new_name} successfully.")
                    return create_json_response(True, "Session renamed successfully.")
                else:
                    logger.error(f"Failed to rename session {session_id}.")
                    return create_json_response(False, "Failed to rename session.")
            except Exception as e:
                logger.error(f"Error renaming session {session_id}: {str(e)}")
                return create_json_response(False, "Failed to rename session.", {"error": str(e)})

        # The /query endpoint is no longer needed for this process
        # All processing happens when a prompt is sent via WebSocket

    async def process_folder_async(self):
        """Process folder asynchronously without blocking the server."""
        try:
            logger.info(f"Starting to process folder: {self.folder_path}")
            for filename in os.listdir(self.folder_path):
                file_path = os.path.join(self.folder_path, filename)
                if os.path.isfile(file_path):
                    # Run the synchronous process_file in a separate thread
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(self.executor, process_file, file_path)
            logger.info("Finished processing all files in folder.")
        except Exception as e:
            logger.error(f"Error processing folder: {str(e)}")

    async def startup(self):
        """Connect to the database on app startup."""
        await database.connect()
        logger.info("Database connected")

    async def shutdown(self):
        """Disconnect from the database on app shutdown."""
        await database.disconnect()
        logger.info("Database disconnected")

# Instantiate the application
application = Application()
app = application.app  # Expose the FastAPI app for the server

# Add startup and shutdown events
@app.on_event("startup")
async def startup_event():
    await application.startup()

@app.on_event("shutdown")
async def shutdown_event():
    await application.shutdown()
