
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path
import openai
from fastapi import FastAPI, File, UploadFile
import os

app = FastAPI()

openai.api_key = os.getenv("OPENAI_API_KEY")
# Directory to store uploaded files
UPLOAD_FOLDER = "./uploads"

# Automatically create the uploads folder if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

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

        # Return a success message with the file name
        return {"success": True, "filename": file.filename}

    except Exception as e:
        # Handle exceptions and return error message
        return {"success": False, "error": str(e)}

# Serve the main HTML file
@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_path = Path(__file__).parent / "templates/index.html"
    with open(index_path, "r") as file:
        return HTMLResponse(content=file.read())

# WebSocket endpoint for chat
@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Receive a message from the client
            data = await websocket.receive_text()
            
            # Send the message to OpenAI's API
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": data}],
                max_tokens=150
            )
            
            # Extract the answer from OpenAI's response
            answer = response.choices[0].message['content'].strip()
            
            # Send the answer back to the client
            await websocket.send_text(answer)
    except WebSocketDisconnect:
        print("Client disconnected")
