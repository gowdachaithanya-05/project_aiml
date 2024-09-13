from fastapi import FastAPI, WebSocket, WebSocketDisconnect, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path
import openai
import os
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

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
    def __init__(self):
        # Load API key from environment variables
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is not set")
        openai.api_key = self.api_key

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
        self.chat_manager = OpenAIChatManager()
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

        # File upload route
        @self.app.post("/upload")
        async def upload_file(file: UploadFile = File(...)):
            return await self.file_manager.save_file(file)

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


# Instantiate the application
application = Application()
app = application.app  # Expose the FastAPI app for the server
