let chatHistory = [];
let currentChatIndex = -1;
let websocket;
let isProcessing = false; // To track if a message is being processed
let existingFiles = [];

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

function checkScriptLoaded() {
    if (typeof sendMessage === 'undefined') {
        console.error('script.js failed to load properly');
        showError("Failed to load necessary scripts. Please refresh the page or check your network.");
    }
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

function showFileGroupModal() {
    document.getElementById("fileGroupModal").style.display = "block";
    loadExistingFiles();
  }
  
  function hideFileGroupModal() {
    document.getElementById("fileGroupModal").style.display = "none";
  }
  
  function loadExistingFiles() {
    fetch('/get-existing-files')
      .then(response => response.json())
      .then(files => {
        existingFiles = files;
        displayExistingFiles();
      })
      .catch(error => console.error('Error loading existing files:', error));
  }
  
  function displayExistingFiles() {
    const container = document.getElementById('existingFiles');
    container.innerHTML = '';
    existingFiles.forEach(file => {
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.id = file;
      checkbox.name = 'existingFile';
      checkbox.value = file;
  
      const label = document.createElement('label');
      label.htmlFor = file;
      label.appendChild(document.createTextNode(file));
  
      container.appendChild(checkbox);
      container.appendChild(label);
      container.appendChild(document.createElement('br'));
    });
  }
  
  document.getElementById('fileGroupForm').addEventListener('submit', function(event) {
    event.preventDefault();
    const groupName = document.getElementById('groupName').value;
    const selectedFiles = [...document.querySelectorAll('input[name="existingFile"]:checked')].map(el => el.value);

    const formData = new FormData();
    formData.append('group_name', groupName);
    selectedFiles.forEach(file => formData.append('files', file));

    fetch('/create-file-group', {
        method: 'POST',
        body: formData
    })
    .then(response => {
        // Check if the response is OK (HTTP status 200-299)
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json(); // Attempt to parse JSON response
    })
    .then(data => {
        // Check if data is valid (not null or undefined) before accessing properties
        if (data && typeof data === 'object') {
            if (data.success) {
                alert('File group created successfully!');
                hideFileGroupModal();
                loadFileGroups();
            } else {
                alert('Error creating file group: ' + (data.error || 'Unknown error'));
            }
        } else {
            throw new Error('Invalid response format received from the server.');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('An error occurred: ' + error.message);
    });
});


  function updateFileList(newFiles) {
    existingFiles = [...new Set([...existingFiles, ...newFiles])];
    if (document.getElementById("fileGroupModal").style.display === "block") {
      displayExistingFiles();
    }
  }

// Process file input and handle validation
async function uploadDocument(event) {
    const files = event.target.files;
  
    if (files && files.length > 0) {
      const formData = new FormData();
  
      for (const file of files) {
        formData.append('files', file);
      }
  
      try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        if (data && data.success) {
            alert(`Files uploaded successfully. Details: ${data.details.join(', ')}`);
            updateFileList(data.details); // Update the file list with new files
        } else {
            alert('Failed to upload the files. Error: ' + (data.error || data.message || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error uploading files:', error);
        alert('An error occurred while uploading the files: ' + error.message);
    }
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

function toggleFilterDialog() {
    const dialog = document.getElementById('filterDialog');
    dialog.style.display = dialog.style.display === 'none' ? 'block' : 'none';
    
    if (dialog.style.display === 'block') {
      // Reset to default state when opening
      document.querySelector('input[name="filter"][value="all"]').checked = true;
      document.getElementById('groupListContainer').style.display = 'none';
      document.getElementById('applyFilter').style.display = 'none';
    }
  }
  
  function showGroupList() {
    const groupListContainer = document.getElementById('groupListContainer');
    const applyButton = document.getElementById('applyFilter');
    
    if (document.querySelector('input[name="filter"][value="group"]').checked) {
      groupListContainer.style.display = 'flex';
      applyButton.style.display = 'block';
      loadFileGroups();
    } else {
      groupListContainer.style.display = 'none';
      applyButton.style.display = 'none';
    }
  }
  
  function loadFileGroups() {
    fetch('/get-file-groups')
      .then(response => response.json())
      .then(groups => {
        displayFileGroups(groups);
      })
      .catch(error => console.error('Error loading file groups:', error));
  }
  
  function displayFileGroups(groups) {
    const container = document.getElementById('groupListContainer');
    if (!container) return;
  
    container.innerHTML = '';
    groups.forEach(group => {
      const groupItem = document.createElement('div');
      
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.id = `group-${group.id}`;
      checkbox.name = 'fileGroup';
      checkbox.value = group.id;
  
      const label = document.createElement('label');
      label.htmlFor = `group-${group.id}`;
      label.appendChild(document.createTextNode(group.group_name));
  
      groupItem.appendChild(checkbox);
      groupItem.appendChild(label);
  
      container.appendChild(groupItem);
    });
  }
  
  // Add event listeners
  document.addEventListener('DOMContentLoaded', function() {
    const filterForm = document.getElementById('filterForm');
    filterForm.addEventListener('change', function(event) {
      if (event.target.name === 'filter') {
        showGroupList();
      }
    });
  
    const applyButton = document.getElementById('applyFilter');
    applyButton.addEventListener('click', function() {
      // Here you can add the logic to apply the selected filters
      console.log('Applying filters...');
      // TODO: Implement filter application logic
      toggleFilterDialog(); // Close the dialog after applying
    });
  });

// Initialize WebSocket connection when the page loads
window.onload = function() {
    connectWebSocket();
};
