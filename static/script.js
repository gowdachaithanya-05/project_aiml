
let chatHistory = [];
let currentChatIndex = -1;
let websocket;

// WebSocket setup
function connectWebSocket() {
    websocket = new WebSocket('ws://127.0.0.1:8000/ws/chat');

    // Connection established
    websocket.onopen = () => {
        console.log('Connected to WebSocket');
    };

    // Receive message from WebSocket server (OpenAI response)
    websocket.onmessage = (event) => {
        const chatArea = document.getElementById("chatArea");
        const botChatBubble = document.createElement("div");
        botChatBubble.classList.add("chat-bubble", "bot");  
        botChatBubble.textContent = `Bot: ${event.data}`;
        chatArea.appendChild(botChatBubble);

        // Scroll to the bottom after receiving message
        chatArea.scrollTop = chatArea.scrollHeight;
    };

    // Handle WebSocket errors
    websocket.onerror = (error) => {
        console.error('WebSocket Error:', error);
    };

    // Handle WebSocket closing
    websocket.onclose = () => {
        console.log('WebSocket connection closed');
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
        websocket.send(messageInput);

        // Scroll to the bottom after sending message
        chatArea.scrollTop = chatArea.scrollHeight;
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
    newChatItem.innerHTML = `Chat ${chatList.children.length + 1} <span class="dots-menu" onclick="showOptions(this)">...</span>`;
    newChatItem.onclick = (event) => loadChat(event, chatList.children.length);
    chatList.appendChild(newChatItem);

    document.getElementById("chatArea").innerHTML = '';
    currentChatIndex = chatHistory.length;
    chatHistory.push('');
}

// Load a previous chat
function loadChat(event, index) {
    const target = event.target;
    if (target.classList.contains('dots-menu')) {
        return; 
    }
    document.getElementById("chatArea").innerHTML = chatHistory[index];
    currentChatIndex = index;
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

        // Add the menu to the body (not inside the chat item to avoid layout changes)
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

document.addEventListener('click', function(event) {
    const menu = document.querySelector('.chat-options-menu');
    if (menu && !menu.contains(event.target) && !event.target.classList.contains('dots-menu')) {
        menu.remove(); 
    }
});





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

// Upload document
function uploadDocument(event) {
    const file = event.target.files[0];
    
    if (file) {
        // Create FormData object to hold the file
        const formData = new FormData();
        formData.append('file', file);

        // Send the file to the backend using Fetch API
        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(`Document "${file.name}" uploaded successfully.`);
            } else {
                alert('Failed to upload the document.');
            }
        })
        .catch(error => {
            console.error('Error uploading document:', error);
            alert('An error occurred while uploading the document.');
        });
    }
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
