from fastapi import FastAPI, WebSocket, WebSocketDisconnect, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path
from database import database  # Make sure this exists
from models import meta_table  # Make sure this exists
import openai
import os
import logging
from datetime import datetime
from typing import List

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

    async def save_files(self, files: List[UploadFile]) -> dict:
        """Saves uploaded files to the server and stores metadata in the database."""
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

            return {"success": True, "details": [file.filename for file in files]}

        except Exception as e:
            logging.error("Error uploading files or saving metadata: %s", str(e))
            return {"success": False, "error": f"Failed to upload: {str(e)}"}


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
                logging.info("Received message from client: %s", data)
                answer = self.chat_manager.get_response(data)
                await websocket.send_text(answer)
                logging.info("Sent message to client: %s", answer)
        except WebSocketDisconnect:
            logging.warning("WebSocket client disconnected")
        except Exception as e:
            logging.error("Error in WebSocket communication: %s", str(e))


class Application:
    """Encapsulates the entire FastAPI application logic."""
    def __init__(self):
        # Instantiate FastAPI app
        self.app = FastAPI()

        # Initialize components
        self.file_manager = FileManager(upload_folder="./uploads")
        self.chat_manager = OpenAIChatManager(api_key=os.getenv("OPENAI_API_KEY"))
        self.websocket_manager = WebSocketManager(chat_manager=self.chat_manager)

        # Set up middleware and routes
        self._setup_middleware()
        self._setup_routes()

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

        # File upload route for handling multiple files
        @self.app.post("/upload")
        async def upload_files(files: List[UploadFile] = File(...)):
            return await self.file_manager.save_files(files)

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

        # WebSocket route for chat
        @self.app.websocket("/ws/chat")
        async def websocket_endpoint(websocket: WebSocket):
            await self.websocket_manager.handle_websocket(websocket)

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
