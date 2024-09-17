# from fastapi import FastAPI, WebSocket, WebSocketDisconnect, File, UploadFile
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.staticfiles import StaticFiles
# from fastapi.responses import HTMLResponse
# from pathlib import Path
# import openai
# import os
# import logging
# from  src.logging_config import setup_logger  # Use absolute import

# import logging_config as lc

# # Initialize the logger

# logger = lc.setup_logger()
# # logger = setup_logger()

# app = FastAPI()

# # Set OpenAI API key from environment variable
# openai.api_key = os.getenv("OPENAI_API_KEY")
# print(openai.api_key) 

# # Directory to store uploaded files
# UPLOAD_FOLDER = "./uploads"
# if not os.path.exists(UPLOAD_FOLDER):
#     os.makedirs(UPLOAD_FOLDER)

# # Add CORS middleware for security
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # Adjust for specific origins if necessary
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # Serve static files
# app.mount("/static", StaticFiles(directory="static"), name="static")

# # WebSocket endpoint for chat
# @app.websocket("/ws/chat")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     try:
#         while True:
#             # Receive a message from the client
#             data = await websocket.receive_text()

#             # Log the received message
#             logger.info(f"Received WebSocket message: {data}")

#             response = openai.ChatCompletion.create(
#                 model="gpt-3.5-turbo",
#                 messages=[{"role": "user", "content": data}],
#                 max_tokens=150
#             )
#             answer = response.choices[0].message['content'].strip()

#             # Log the response
#             logger.info(f"Sending WebSocket response: {answer}")

#             await websocket.send_text(answer)
#     except WebSocketDisconnect:
#         logger.info("Client disconnected")

# # File upload route
# @app.post("/upload")
# async def upload_file(file: UploadFile = File(...)):
#     try:
#         file_location = os.path.join(UPLOAD_FOLDER, file.filename)
#         with open(file_location, "wb") as f:
#             f.write(await file.read())
#         logger.info(f"File uploaded successfully: {file.filename}")
#         return {"success": True, "filename": file.filename}
#     except Exception as e:
#         logger.error(f"Error uploading file: {str(e)}")
#         return {"success": False, "error": str(e)}

# # Serve main HTML page
# @app.get("/", response_class=HTMLResponse)
# async def get_index():
#     index_path = Path(__file__).parent / "templates/index.html"
#     with open(index_path, "r") as file:
#         logger.info("Serving the main HTML page")
#         return HTMLResponse(content=file.read())
