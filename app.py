from fastapi import FastAPI, WebSocket, WebSocketDisconnect, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pathlib import Path
import os
import openai
import logging
import asyncio
from rag import process_hardcoded_folder, query_cases  # Import functions from rag.py
from rag import process_file  # Import file processing function
import re

# Initialize logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

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

    async def save_file(self, file: UploadFile) -> dict:
        """Saves an uploaded file to the server."""
        try:
            file_location = os.path.join(self.upload_folder, file.filename)
            with open(file_location, "wb") as f:
                f.write(await file.read())
            logging.info("File uploaded successfully: %s", file.filename)

            # Process the uploaded file using process_file function from rag.py
            process_file(file_location)

            return {"success": True, "filename": file.filename}
        except Exception as e:
            logging.error("Error uploading file: %s", str(e))
            return {"success": False, "error": str(e)}



class WebSocketManager:
    """Handles WebSocket connections for chat interactions."""
    def __init__(self, chat_manager: OpenAIChatManager):
        self.chat_manager = chat_manager

    async def handle_websocket(self, websocket: WebSocket):
        """Manages the WebSocket lifecycle and communication."""
        await websocket.accept()
        logging.info("WebSocket connection accepted")
        try:
            while True:
                data = await websocket.receive_text()
                logging.debug(f"Received message: {data}")

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


class Application:
    """Encapsulates the entire FastAPI application logic."""
    def __init__(self):
        # Instantiate FastAPI app
        self.app = FastAPI()

        # Initialize components
        self.file_manager = FileManager(upload_folder="./uploads")
        self.chat_manager = OpenAIChatManager(api_key=os.getenv("OPENAI_API_KEY"))
        self.websocket_manager = WebSocketManager(chat_manager=self.chat_manager)

        # Path to your custom frontend
        self.frontend_path = Path("./templates/index.html")

        # Add the folder path where your case files are stored
        self.folder_path = r"C:\Users\chait\OneDrive\Documents\RAG\cases"

        # Set up middleware and routes
        self._setup_middleware()
        self._setup_routes()

        # Register the startup event to process the folder asynchronously
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

        # Root route to serve your chat UI
        @self.app.get("/", response_class=HTMLResponse)
        async def get_index():
            return FileResponse(self.frontend_path)

        # File upload route
        @self.app.post("/upload")
        async def upload_file(file: UploadFile = File(...)):
            return await self.file_manager.save_file(file)

        # Add an endpoint to process the folder on demand
        @self.app.post("/process-folder/")
        async def process_folder():
            await self.process_folder_async()
            return {"message": "Files processed successfully."}

        # WebSocket route for chat
        @self.app.websocket("/ws/chat")
        async def websocket_endpoint(websocket: WebSocket):
            await self.websocket_manager.handle_websocket(websocket)

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

# Instantiate the application
application = Application()
app = application.app  # Expose the FastAPI app for the server
