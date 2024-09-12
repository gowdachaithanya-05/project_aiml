
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path
import openai
import os
import logging

# Initialize logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI()

openai.api_key = os.getenv("OPENAI_API_KEY")

# Directory to store uploaded files
UPLOAD_FOLDER = "./uploads"

# Automatically create the uploads folder if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    logging.info("Created uploads folder: %s", UPLOAD_FOLDER)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this to allow only specific origins if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        # Define the full file path
        file_location = os.path.join(UPLOAD_FOLDER, file.filename)

        # Write the file contents to disk
        with open(file_location, "wb") as f:
            f.write(await file.read())

        # Log file upload success
        logging.info("File uploaded successfully: %s", file.filename)

        # Return a success message with the file name
        return {"success": True, "filename": file.filename}

    except Exception as e:
        # Log file upload error
        logging.error("Error uploading file: %s", str(e))

        # Handle exceptions and return error message
        return {"success": False, "error": str(e)}

# Serve the main HTML file
@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_path = Path(__file__).parent / "templates/index.html"
    try:
        with open(index_path, "r") as file:
            logging.info("Served index.html")
            return HTMLResponse(content=file.read())
    except Exception as e:
        logging.error("Error serving index.html: %s", str(e))
        return HTMLResponse(content="Error loading index.html", status_code=500)

# WebSocket endpoint for chat
@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logging.info("WebSocket connection accepted")
    try:
        while True:
            # Receive a message from the client
            data = await websocket.receive_text()
            logging.info("Received message from client: %s", data)
            
            # Send the message to OpenAI's API
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": data}],
                max_tokens=150
            )
            
            # Extract the answer from OpenAI's response
            answer = response.choices[0].message['content'].strip()
            logging.info("Response from OpenAI: %s", answer)
            
            # Send the answer back to the client
            await websocket.send_text(answer)
            logging.info("Sent message to client: %s", answer)

    except WebSocketDisconnect:
        logging.warning("WebSocket client disconnected")
    except Exception as e:
        logging.error("Error in WebSocket communication: %s", str(e))
