let chatHistory = [];
let currentChatIndex = -1;
let websocket;
let isProcessing = false; // To track if a message is being processed

// WebSocket setup
function connectWebSocket() {
    websocket = new WebSocket('ws://127.0.0.1:8000/ws/chat');

    // Connection established
    websocket.onopen = () => {
        console.log('Connected to WebSocket');
        document.getElementById('errorMessage').style.display = 'none'; // Hide error on successful connection
    };

    // Receive message from WebSocket server (OpenAI response)
    websocket.onmessage = (event) => {
        const chatArea = document.getElementById("chatArea");
        const botChatBubble = document.createElement("div");
        botChatBubble.classList.add("chat-bubble", "bot");
        botChatBubble.textContent = `Bot: ${event.data}`;
        chatArea.appendChild(botChatBubble);

        // Hide the spinner when the response is received
        hideSpinner();
        isProcessing = false;

        // Scroll to the bottom after receiving message
        chatArea.scrollTop = chatArea.scrollHeight;
    };

    // Handle WebSocket errors
    websocket.onerror = (error) => {
        console.error('WebSocket Error:', error);
        showError("WebSocket error. Please check your connection or try again later.");
    };

    // Handle WebSocket closing
    websocket.onclose = () => {
        console.log('WebSocket connection closed');
        showError("WebSocket connection closed. Please refresh the page or check your network.");
    };
}

// Send message through WebSocket
async function sendMessage() {
    const chatArea = document.getElementById("chatArea");
    const messageInput = document.getElementById("chatMessage").value;

    if (messageInput.trim()) {
        // Display user's message
        const userChatBubble = document.createElement("div");
        userChatBubble.classList.add("chat-bubble", "user");
        userChatBubble.textContent = `You: ${messageInput}`;
        chatArea.appendChild(userChatBubble);
        document.getElementById("chatMessage").value = ''; 

        // Send the message to the backend via WebSocket
        if (websocket.readyState === WebSocket.OPEN) {
            showSpinner(); // Show spinner when processing starts
            isProcessing = true;
            websocket.send(messageInput);
        } else {
            showError("WebSocket is not connected. Please try again later.");
        }

        // Scroll to the bottom after sending message
        chatArea.scrollTop = chatArea.scrollHeight;

        // If the response takes too long, show an error after a timeout (optional)
        setTimeout(() => {
            if (isProcessing) {
                hideSpinner();
                showError("The response is taking longer than expected. Please check your connection.");
                isProcessing = false;
            }
        }, 10000); // 10 seconds timeout for slow response
    }
}

// Start a new chat
function startNewChat() {
    if (currentChatIndex !== -1) {
        chatHistory[currentChatIndex] = document.getElementById("chatArea").innerHTML;
    }

    const chatList = document.getElementById("chatList");
    const newChatItem = document.createElement("li");
    newChatItem.classList.add('chat-item');
    const sessionId = uuidv4(); // Generate a new session ID or retrieve from your logic
    newChatItem.setAttribute("data-session-id", sessionId); // Set data attribute for session ID
    newChatItem.innerHTML = `Chat ${chatList.children.length + 1} <span class="dots-menu" onclick="showOptions(this)">...</span>`;
    newChatItem.onclick = (event) => loadChat(event, chatList.children.length);
    chatList.appendChild(newChatItem);

    document.getElementById("chatArea").innerHTML = '';
    currentChatIndex = chatHistory.length;
    chatHistory.push('');
}

// Load a previous chat
async function loadChat(event, index) {
    const target = event.target;
    if (target.classList.contains('dots-menu')) {
        return;
    }
    const chatArea = document.getElementById("chatArea");
  chatArea.innerHTML = ''; // Clear current chat area

  // Fetch chat history for the selected session
  const response = await fetch(`/get-chat-history?session_id=${target.getAttribute("data-session-id")}`);
  const chatHistoryData = await response.json();

  // Display questions and answers in the chat area
  chatHistoryData.forEach(chat => {
    const chatBubble = document.createElement("div");
    chatBubble.classList.add("chat-bubble");

    if (chat.is_user_message) {
      chatBubble.classList.add("user");
      chatBubble.textContent = `You: ${chat.message_text}`;
    } else {
      chatBubble.classList.add("bot");
      chatBubble.textContent = `Bot: ${chat.message_text}`;
    }

    chatArea.appendChild(chatBubble);
  });

  currentChatIndex = index; // Set current index to the loaded chat
}

// Show options when clicking on dots menu
function showOptions(dotsElement) {
    const existingMenu = document.querySelector('.chat-options-menu');
    if (existingMenu) existingMenu.remove();

    const menu = document.createElement('div');
    menu.className = 'chat-options-menu';

    const chatItem = dotsElement.closest('.chat-item');
    const chatIndex = Array.from(chatItem.parentElement.children).indexOf(chatItem);

    dotsElement.style.visibility = 'hidden';
    menu.innerHTML = `
        <ul>
            <li onclick="renameChat(${chatIndex})">Rename</li>
            <li onclick="exportChat(${chatIndex})">Export</li>
            <li onclick="deleteChat(${chatIndex})">Delete</li>
            <li onclick="archiveChat(${chatIndex})">Archive</li>
        </ul>
    `;

    // Add the menu to the body
    document.body.appendChild(menu);

    // Position the menu at the dots' position
    const dotsRect = dotsElement.getBoundingClientRect();
    menu.style.position = 'absolute';
    menu.style.top = `${dotsRect.bottom + window.scrollY}px`;
    menu.style.left = `${dotsRect.left + window.scrollX}px`;

    // Close the menu and show the dots again when clicking outside
    const closeMenu = function(event) {
        if (!menu.contains(event.target) && !event.target.classList.contains('dots-menu')) {
            menu.remove(); // Remove menu
            dotsElement.style.visibility = 'visible'; // Show the dots again
            document.removeEventListener('click', closeMenu); // Remove listener
        }
    };

    document.addEventListener('click', closeMenu);
}

// Rename chat
function renameChat(index) {
    const newName = prompt("Enter new name for chat:");
    if (newName) {
        document.getElementById("chatList").children[index].firstChild.nodeValue = newName + " ";
    }
}

// Export chat
function exportChat(index) {
    const chatData = chatHistory[index];
    if (!chatData) {
        alert('No data to export.');
        return;
    }
    const blob = new Blob([chatData], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    a.download = `chat_${index + 1}.txt`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
}

// Delete chat
function deleteChat(index) {
    if (confirm("Are you sure you want to delete this chat?")) {
        chatHistory.splice(index, 1);
        document.getElementById("chatList").children[index].remove();
        if (index === currentChatIndex) {
            document.getElementById("chatArea").innerHTML = '';
            currentChatIndex = -1;
        }
    }
}

// Archive chat
function archiveChat(index) {
    alert(`Chat ${index + 1} archived.`);
}


function showUploadModal() {
    document.getElementById("uploadModal").style.display = "block";
}

// Hide the upload modal
function hideUploadModal() {
    document.getElementById("uploadModal").style.display = "none";
}

// Allow drop event
function allowDrop(event) {
    event.preventDefault();
}

// Handle drop event
function handleDrop(event) {
    event.preventDefault();
    const files = event.dataTransfer.files;
    uploadFiles(files);
}

// Handle drag over
function handleDragOver(event) {
    event.preventDefault();
    document.getElementById('dropZone').classList.add('dragover');
}

// Handle file drop
function handleDrop(event) {
    event.preventDefault();
    document.getElementById('dropZone').classList.remove('dragover');

    const files = event.dataTransfer.files;
    processFiles(files);
}

// Process file input and handle validation
function uploadDocument(event) {
    const files = event.target.files;

    if (files && files.length > 0) {
        const formData = new FormData();

        // Add multiple files to the FormData
        for (const file of files) {
            formData.append('files', file);
        }

        // Send the files to the backend using Fetch API
        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(`Files uploaded successfully.Details: ${data.details.join(', ')}`);
            } else {
                alert('Failed to upload the files. Error: ${data.error || data.message}');
            }
        })
        .catch(error => {
            console.error('Error uploading files:', error);
            alert('An error occurred while uploading the files.');
        });
    }
}


// Handle file validation and upload
function processFiles(files) {
    if (files.length > 10) {
        alert('You can upload a maximum of 10 files at a time.');
        return;
    }

    let totalSize = 0;
    for (let i = 0; i < files.length; i++) {
        totalSize += files[i].size;
        if (files[i].size > 500 * 1024 * 1024) {
            alert(`File "${files[i].name}" exceeds the 500MB size limit.`);
            return;
        }
    }

    if (totalSize > 500 * 1024 * 1024) {
        alert('Total file size exceeds the 500MB limit.');
        return;
    }

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
        formData.append('file', files[i]);
    }

    // Send the file to the backend using Fetch API
    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Files uploaded successfully.');
        } else {
            alert('Failed to upload the files.');
        }
    })
    .catch(error => {
        console.error('Error uploading files:', error);
        alert('An error occurred while uploading the files.');
    });
}

// Show the spinner
function showSpinner() {
    document.getElementById("spinner").style.display = "block";
}

// Hide the spinner
function hideSpinner() {
    document.getElementById("spinner").style.display = "none";
}

// Display error message on the UI
function showError(message) {
    const errorMessageElement = document.getElementById("errorMessage");
    errorMessageElement.textContent = message;
    errorMessageElement.style.display = "block";
}

// Sending message on pressing Enter
document.getElementById("chatMessage").addEventListener("keydown", function(event) {
    if (event.key === "Enter") {
        event.preventDefault();
        sendMessage();
    }
});

// Click outside to close the options menu
document.addEventListener('click', function(event) {
    const menu = document.querySelector('.chat-options-menu');
    if (menu && !menu.contains(event.target) && !event.target.classList.contains('dots-menu')) {
        menu.remove();
    }
});

// Initialize WebSocket connection when the page loads
window.onload = function() {
    connectWebSocket();
};