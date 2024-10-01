
let chatHistory = {};
let currentSessionId = null;
let websocket;
let isProcessing = false; // To track if a message is being processed
let existingFiles = [];
let selectedGroupIds = []; // Global variable to store selected group IDs
let currentChatIndex = -1;

// WebSocket setup
function connectWebSocket() {
  websocket = new WebSocket("ws://127.0.0.1:8000/ws/chat");

  // Connection established
  websocket.onopen = () => {
    console.log("Connected to WebSocket");
    document.getElementById("errorMessage").style.display = "none"; // Hide error on successful connection
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
    console.error("WebSocket Error:", error);
    showError(
      "WebSocket error. Please check your connection or try again later."
    );
  };

  // Handle WebSocket closing
  websocket.onclose = () => {
    console.log("WebSocket connection closed");
    showError(
      "WebSocket connection closed. Please refresh the page or check your network."
    );
  };
}

function checkScriptLoaded() {
  if (typeof sendMessage === 'undefined') {
      console.error('script.js failed to load properly');
      showError("Failed to load necessary scripts. Please refresh the page or check your network.");
  }
}

function formatTimestamp(datetimeString) {
  const date = new Date(datetimeString);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
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

    // Update local chat history
    if (currentSessionId) {
      if (!chatHistory[currentSessionId]) {
        chatHistory[currentSessionId] = '';
      }
      chatHistory[currentSessionId] += `\nYou: ${messageInput}`;
    } else {
      // Start a new chat if no session is active
      startNewChat();
      chatHistory[currentSessionId] = `You: ${messageInput}`;
    }

    // Send the message to the backend via WebSocket
    if (websocket.readyState === WebSocket.OPEN) {
      showSpinner(); // Show spinner when processing starts
      isProcessing = true;

      // Prepare the message as a JSON string
      const messageData = {
        session_id: currentSessionId,
        message: messageInput,
        group_ids: selectedGroupIds // Include selected group IDs
      };

      console.log("Sending message:", messageData); // Log the message data

      websocket.send(JSON.stringify(messageData));
    } else {
      showError("WebSocket is not connected. Please try again later.");
    }

    // Scroll to the bottom after sending message
    chatArea.scrollTop = chatArea.scrollHeight;

    // If the response takes too long, show an error after a timeout
    setTimeout(() => {
      if (isProcessing) {
        hideSpinner();
        showError(
          "The response is taking longer than expected. Please check your connection."
        );
        isProcessing = false;
      }
    }, 10000); // 10 seconds timeout for slow response
  }
}

// Start a new chat
function uuidv4() {
  return ([1e7] + -1e3 + -4e3 + -8e3 + -1e11).replace(/[018]/g, (c) =>
    (
      c ^
      (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (c / 4)))
    ).toString(16)
  );
}

function startNewChat() {
  if (currentSessionId && chatHistory[currentSessionId] && chatHistory[currentSessionId].trim() !== '') {
    if (!confirm("Are you sure you want to start a new chat? Your current chat will be saved.")) {
      return;
    }
  }

  // Reset chat area
  const chatArea = document.getElementById("chatArea");
  chatArea.innerHTML = '';

  // Generate a new session ID using UUID
  const sessionId = uuidv4();
  currentSessionId = sessionId; // Set current session ID

  // Add the new session to the chat list
  const chatList = document.getElementById("chatList");
  const newChatItem = document.createElement("li");
  newChatItem.classList.add('chat-item');
  newChatItem.setAttribute("data-session-id", sessionId);

  const chatCount = document.querySelectorAll('.chat-item').length + 1; // Adjust chat count
  newChatItem.innerHTML = `Chat ${chatCount} <span class="dots-menu" onclick="showOptions(this)">...</span>`;

  newChatItem.onclick = (event) => loadChat(event, sessionId);
  chatList.insertBefore(newChatItem, chatList.firstChild); // Insert at the top

  // Initialize chat history for the new session
  chatHistory[sessionId] = '';

  // Select the new chat session
  newChatItem.click();
}

// Load a previous chat
async function loadChat(event, sessionId) {
  const target = event.target;
  if (target.classList.contains('dots-menu')) {
    return;
  }
  const chatArea = document.getElementById("chatArea");
  chatArea.innerHTML = ''; // Clear current chat area

  currentSessionId = sessionId; // Set current session ID

  // Fetch chat history for the selected session
  const response = await fetch(`/get-chat-history?session_id=${sessionId}`);
  const chatHistoryData = await response.json();

  // Display messages in the chat area
  chatHistoryData.forEach(chat => {
    const chatBubble = document.createElement("div");
    chatBubble.classList.add("chat-bubble");
    chatBubble.classList.add(chat.sender === 'user' ? 'user' : 'bot');
    chatBubble.textContent = `${chat.sender === 'user' ? 'You' : 'Bot'}: ${chat.message}`;
    chatArea.appendChild(chatBubble);
  });

  // Update local chat history
  chatHistory[currentSessionId] = chatHistoryData.map(chat => `${chat.sender}: ${chat.message}`).join('\n');

  // Scroll to the bottom after loading chat history
  chatArea.scrollTop = chatArea.scrollHeight;
}

async function loadSessions() {
  const activeSessionsResponse = await fetch("/get-active-sessions/");
  const archivedSessionsResponse = await fetch("/get-archived-sessions/");

  const activeData = await activeSessionsResponse.json();
  const archivedData = await archivedSessionsResponse.json();

  const chatList = document.getElementById("chatList");
  chatList.innerHTML = ""; // Clear existing list

  let hasChats = false; // Initialize the flag

  // Add Active Sessions
  if (activeData.length > 0) {
    hasChats = true;

    const activeHeader = document.createElement("li");
    activeHeader.textContent = "Active Chats";
    activeHeader.style.fontWeight = "bold";
    activeHeader.style.marginTop = "10px";
    chatList.appendChild(activeHeader);

    activeData.forEach((session, index) => {
      const chatItem = document.createElement("li");
      chatItem.classList.add("chat-item");
      chatItem.setAttribute("data-session-id", session.session_id);

      // Fetch session name if available, else default to "Chat X"
      const displayName = session.session_name
        ? session.session_name
        : `Chat ${index + 1}`;

      chatItem.innerHTML = `${displayName} <span class="dots-menu" onclick="showOptions(this)">...</span>`;
      chatItem.onclick = (event) => loadChat(event, session.session_id);
      chatList.appendChild(chatItem);
    });
  }

  // Add Archived Sessions
  if (archivedData.length > 0) {
    const archivedHeader = document.createElement("li");
    archivedHeader.textContent = "Archived Chats";
    archivedHeader.style.fontWeight = "bold";
    archivedHeader.style.marginTop = "20px";
    chatList.appendChild(archivedHeader);

    archivedData.forEach((session, index) => {
      const chatItem = document.createElement("li");
      chatItem.classList.add("chat-item", "archived");
      chatItem.setAttribute("data-session-id", session.session_id);

      // Fetch session name if available, else default to "Chat X (Archived)"
      const displayName = session.session_name
        ? session.session_name
        : `Chat ${index + 1} (Archived)`;

      chatItem.innerHTML = `${displayName} <span class="dots-menu" onclick="showOptions(this)">...</span>`;
      chatItem.onclick = (event) => loadChat(event, session.session_id);
      chatList.appendChild(chatItem);
    });
  }

  if (!hasChats && currentSessionId) {
    currentSessionId = null;
    document.getElementById("chatArea").innerHTML = '';
  }
}

// Show options when clicking on dots menu
function showOptions(dotsElement) {
  const existingMenu = document.querySelector(".chat-options-menu");
  if (existingMenu) existingMenu.remove();

  const menu = document.createElement("div");
  menu.className = "chat-options-menu";

  const chatItem = dotsElement.closest(".chat-item");
  const sessionId = chatItem.getAttribute("data-session-id");
  const isArchived = chatItem.classList.contains("archived");

  dotsElement.style.visibility = "hidden";
  menu.innerHTML = `
        <ul>
            <li onclick="renameChat('${sessionId}')">Rename</li>
            <li onclick="exportChat('${sessionId}')">Export</li>
            <li onclick="deleteChat('${sessionId}')">Delete</li>
            <li onclick="${
              isArchived
                ? `unarchiveChat('${sessionId}')`
                : `archiveChat('${sessionId}')`
            }">${isArchived ? "Unarchive" : "Archive"}</li>
        </ul>
    `;

  // Add the menu to the body
  document.body.appendChild(menu);

  // Position the menu at the dots' position
  const dotsRect = dotsElement.getBoundingClientRect();
  menu.style.position = "absolute";
  menu.style.top = `${dotsRect.bottom + window.scrollY}px`;
  menu.style.left = `${dotsRect.left + window.scrollX}px`;

  // Close the menu and show the dots again when clicking outside
  const closeMenu = function (event) {
    if (
      !menu.contains(event.target) &&
      !event.target.classList.contains("dots-menu")
    ) {
      menu.remove(); // Remove menu
      dotsElement.style.visibility = "visible"; // Show the dots again
      document.removeEventListener("click", closeMenu); // Remove listener
    }
  };

  document.addEventListener("click", closeMenu);
}

// Rename chat
function renameChat(sessionId) {
  const newName = prompt("Enter new name for the chat:");
  if (newName) {
    const formData = new FormData();
    formData.append('session_id', sessionId);
    formData.append('new_name', newName);

    fetch('/rename-session/', {
      method: 'POST',
      body: formData
    })
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        alert('Chat renamed successfully!');
        // Update the chat name in the chat list
        const chatItem = document.querySelector(`.chat-item[data-session-id='${sessionId}']`);
        if (chatItem) {
          chatItem.innerHTML = `${newName} <span class="dots-menu" onclick="showOptions(this)">...</span>`;
        }
      } else {
        alert('Error renaming chat: ' + (data.details && data.details.error ? data.details.error : 'Unknown error'));
      }
    })
    .catch(error => {
      console.error('Error renaming chat:', error);
      alert('An error occurred while renaming the chat.');
    });
  }
}

// Export chat
function exportChat(sessionId) {
  fetch(`/get-chat-history?session_id=${sessionId}`)
    .then(response => response.json())
    .then(chatHistoryData => {
      if (chatHistoryData && chatHistoryData.length > 0) {
        let exportContent = '';
        chatHistoryData.forEach(chat => {
          const sender = chat.sender === 'user' ? 'You' : 'Bot';
          exportContent += `${sender}: ${chat.message}\n`;
        });

        // Create a Blob from the content
        const blob = new Blob([exportContent], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);

        // Create a temporary link to trigger download
        const a = document.createElement('a');
        a.href = url;
        a.download = `chat_${sessionId}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);

        // Revoke the object URL after download
        URL.revokeObjectURL(url);
      } else {
        alert('No chat history to export.');
      }
    })
    .catch(error => {
      console.error('Error exporting chat:', error);
      alert('An error occurred while exporting the chat.');
    });
}

// Delete chat
function deleteChat(sessionId) {
  if (confirm("Are you sure you want to delete this chat?")) {
    fetch("/delete-session/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ session_id: sessionId }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          alert("Chat deleted successfully!");
          loadSessions(); // Refresh the chat list
          // Optionally, clear chat area if the current chat was deleted
          if (currentSessionId === sessionId) {
            document.getElementById("chatArea").innerHTML = '';
            currentSessionId = null;
          }
        } else {
          alert('Error deleting chat: ' + (data.error || 'Unknown error'));
        }
      })
      .catch((error) => {
        console.error("Error deleting chat:", error);
        alert("Failed to delete chat: " + error.message);
      });
  }
}

// Archive chat
function archiveChat(sessionId) {
  if (confirm("Are you sure you want to archive this chat?")) {
    const formData = new FormData();
    formData.append('session_id', sessionId);

    fetch('/archive-session/', {
      method: 'POST',
      body: formData
    })
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        alert('Chat archived successfully!');
        loadSessions(); // Refresh the chat list
        // Optionally, clear chat area if the current chat was archived
        if (currentSessionId === sessionId) {
          document.getElementById("chatArea").innerHTML = '';
          currentSessionId = null;
        }
      } else {
        alert('Error archiving chat: ' + (data.error || 'Unknown error'));
      }
    })
    .catch(error => {
      console.error('Error archiving chat:', error);
      alert('An error occurred while archiving the chat.');
    });
  }
}

function unarchiveChat(sessionId) {
  if (confirm("Are you sure you want to unarchive this chat?")) {
    const formData = new FormData();
    formData.append('session_id', sessionId);

    fetch('/unarchive-session/', {
      method: 'POST',
      body: formData
    })
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        alert('Chat unarchived successfully!');
        loadSessions(); // Refresh the chat list
      } else {
        alert('Error unarchiving chat: ' + (data.error || 'Unknown error'));
      }
    })
    .catch(error => {
      console.error('Error unarchiving chat:', error);
      alert('An error occurred while unarchiving the chat.');
    });
  }
}

function showUploadModal() {
  document.getElementById("uploadModal").style.display = "block";
  updateModalZIndex('uploadModal');
}

// Hide the upload modal
function hideUploadModal() {
  document.getElementById("uploadModal").style.display = "none";
}

function updateModalZIndex(activeModalId) {
const modals = ['uploadModal', 'fileGroupModal'];
const baseZIndex = 1000;

modals.forEach((modalId, index) => {
  const modal = document.getElementById(modalId);
  if (modalId === activeModalId) {
    modal.style.zIndex = baseZIndex + modals.length;
  } else {
    modal.style.zIndex = baseZIndex + index;
  }
});
}
// Allow drop event
function allowDrop(event) {
  event.preventDefault();
}

// Handle drag over
function handleDragOver(event) {
  event.preventDefault();
  document.getElementById("dropZone").classList.add("dragover");
}

// Handle file drop
function handleDrop(event) {
  event.preventDefault();
  document.getElementById("dropZone").classList.remove("dragover");

  const files = event.dataTransfer.files;
  processFiles(files);
}

function showFileGroupModal() {
  document.getElementById("fileGroupModal").style.display = "block";
  updateModalZIndex('fileGroupModal');
  loadExistingFiles();
  loadFileGroups();
}

function hideFileGroupModal() {
  document.getElementById("fileGroupModal").style.display = "none";
}

function loadExistingFiles() {
  fetch("/get-existing-files")
    .then((response) => response.json())
    .then((files) => {
      existingFiles = files;
      displayExistingFiles();
    })
    .catch((error) => console.error("Error loading existing files:", error));
}

function displayExistingFiles() {
  const container = document.getElementById("existingFiles");
  container.innerHTML = "";
  existingFiles.forEach((file) => {
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.id = file;
    checkbox.name = "existingFile";
    checkbox.value = file;

    const label = document.createElement("label");
    label.htmlFor = file;
    label.appendChild(document.createTextNode(file));

    container.appendChild(checkbox);
    container.appendChild(label);
    container.appendChild(document.createElement("br"));
  });
}

document
  .getElementById("fileGroupForm")
  .addEventListener("submit", function (event) {
    event.preventDefault();
    const groupName = document.getElementById("groupName").value;
    const selectedFiles = [
      ...document.querySelectorAll('input[name="existingFile"]:checked'),
    ].map((el) => el.value);

    const formData = new FormData();
    formData.append("group_name", groupName);
    selectedFiles.forEach((file) => formData.append("files", file));

    fetch("/create-file-group", {
      method: "POST",
      body: formData,
    })
      .then((response) => {
        // Check if the response is OK (HTTP status 200-299)
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json(); // Attempt to parse JSON response
      })
      .then((data) => {
        // Check if data is valid (not null or undefined) before accessing properties
        if (data && typeof data === "object") {
          if (data.success) {
            alert("File group created successfully!");
            loadFileGroups();
          } else {
            alert(
              "Error creating file group: " + (data.error || "Unknown error")
            );
          }
        } else {
          throw new Error("Invalid response format received from the server.");
        }
      })
      .catch((error) => {
        console.error("Error:", error);
        alert("An error occurred: " + error.message);
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

      const uploadModal = document.getElementById('uploadModal');
      if (uploadModal) {
          uploadModal.style.display = 'none'; // Hide the upload modal
      }

      // Show the spinner dialog
      const spinnerDialog = document.getElementById('spinnerDialog');
      spinnerDialog.style.display = 'block'; // Show spinner

      try {
          const response = await fetch('/upload', {
              method: 'POST',
              body: formData
          });

          if (!response.ok) {
              throw new Error(`HTTP error! status: ${response.status}`);
          }

          const data = await response.json();
          // Hide the spinner dialog before showing alert
          spinnerDialog.style.display = 'none'; 

          if (data && data.success) {
              let details = 'Files uploaded successfully.';
              if (Array.isArray(data.details)) {
                  details += ' Details: ' + data.details.join(', ');
              } else if (typeof data.details === 'string') {
                  details += ' Details: ' + data.details;
              }
              alert(details);
              updateFileList(Array.isArray(data.details) ? data.details : [data.details]); // Update the file list with new files
          } else {
              alert('Failed to upload the files. Error: ' + (data.error || data.message || 'Unknown error'));
          }
      } catch (error) {
          console.error('Error uploading files:', error);
          // Hide the spinner dialog before showing alert
          spinnerDialog.style.display = 'none'; 
          alert('An error occurred while uploading the files: ' + error.message);
      } finally {
          // No need to hide the spinner dialog here, as it's already handled above
      }
  }
}

// Handle file validation and upload
function processFiles(files) {
  if (files.length > 10) {
    alert("You can upload a maximum of 10 files at a time.");
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
    alert("Total file size exceeds the 500MB limit.");
    return;
  }

  const formData = new FormData();
  for (let i = 0; i < files.length; i++) {
    formData.append("file", files[i]);
  }

  // Send the file to the backend using Fetch API
  fetch("/upload", {
    method: "POST",
    body: formData,
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        alert("Files uploaded successfully.");
      } else {
        alert("Failed to upload the files.");
      }
    })
    .catch((error) => {
      console.error("Error uploading files:", error);
      alert("An error occurred while uploading the files.");
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
document
  .getElementById("chatMessage")
  .addEventListener("keydown", function (event) {
    if (event.key === "Enter") {
      event.preventDefault();
      sendMessage();
    }
  });

// Click outside to close the options menu
document.addEventListener("click", function (event) {
  const menu = document.querySelector(".chat-options-menu");
  if (
    menu &&
    !menu.contains(event.target) &&
    !event.target.classList.contains("dots-menu")
  ) {
    menu.remove();
  }
});

// Show Group List when "Query by Groups" is selected
function showGroupList() {
  const groupListContainer = document.getElementById('groupListContainer');
  const applyButton = document.getElementById('applyFilter');
  
  if (document.querySelector('input[name="filter"][value="group"]').checked) {
    groupListContainer.style.display = 'block';
    applyButton.style.display = 'block';
    loadFileGroups();
  } else {
    groupListContainer.style.display = 'none';
    applyButton.style.display = 'none';
  }
}
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
  });
});

// Load and display groups
function loadFileGroups() {
  return fetch('/get-file-groups')
    .then(response => response.json())
    .then(data => {
      if (Array.isArray(data)) {
        displayGroupDropdown(data);
        displayGroupTiles(data);
        return data;
      } else {
        console.error('Unexpected data format:', data);
        return [];
      }
    })
    .catch(error => {
      console.error('Error loading file groups:', error);
      return [];
    });
}
document.addEventListener('DOMContentLoaded', function () {
  // Ensure the DOM is fully loaded before accessing elements
  createCustomSelect(); 
  const groups = loadFileGroups();
  displayGroupDropdown(groups); // Only call this after the DOM is ready
});

// Function to display groups in a dropdown format
function displayGroupDropdown(groups) {
  let selectItems = document.querySelector('.select-items');
  if (!selectItems) {
    const customSelect = document.createElement('div');
    customSelect.className = 'custom-select';
    customSelect.innerHTML = `
      <div class="select-selected">Select the group</div>
      <div class="select-items select-hide"></div>
    `;
    const container = document.getElementById('groupListContainer');
    if (container) {
      container.appendChild(customSelect);
      selectItems = customSelect.querySelector('.select-items');
    } else {
      console.error('Group list container not found');
      return;
    }
  }

  selectItems.innerHTML = '';

  if (Array.isArray(groups)) {
    groups.forEach(group => {
      const groupItem = document.createElement('div');
      groupItem.innerHTML = `
        <label>
          <input type="checkbox" name="fileGroup" value="${group.id}">
          ${group.group_name}
        </label>
      `;
      selectItems.appendChild(groupItem);
    });
  } else {
    console.error('Groups is not an array:', groups);
    selectItems.innerHTML = '<div>No groups available</div>';
  }

  // Add event listeners for the custom dropdown
  const select = document.querySelector('.custom-select');
  const selectSelected = select ? select.querySelector('.select-selected') : null;

  if (selectSelected) {
    selectSelected.addEventListener('click', function(e) {
      e.stopPropagation();
      const nextSibling = this.nextElementSibling;
      if (nextSibling) {
        nextSibling.classList.toggle('select-hide');
      }
      this.classList.toggle('select-arrow-active');
    });
  }

  document.addEventListener('click', closeAllSelect);

  // Add event listeners for checkboxes
  const checkboxes = selectItems.querySelectorAll('input[type="checkbox"]');
  checkboxes.forEach(checkbox => {
    checkbox.addEventListener('change', updateSelectedGroups);
  });
}

// Function to update the selected groups display
function updateSelectedGroups() {
  const selectSelected = document.querySelector('.select-selected');
  if (!selectSelected) return;

  const selectedGroups = [...document.querySelectorAll('.select-items input:checked')]
    .map(checkbox => checkbox.parentNode.textContent.trim());

  if (selectedGroups.length > 0) {
    selectSelected.textContent = selectedGroups.join(', ');
  } else {
    selectSelected.textContent = 'Select the group';
  }
}

// Function to close all select boxes in the document, except the current select box
function closeAllSelect(elmnt) {
  const selectItems = document.getElementsByClassName('select-items');
  const selectSelected = document.getElementsByClassName('select-selected');
  for (let i = 0; i < selectSelected.length; i++) {
    if (elmnt == selectSelected[i]) continue;
    selectSelected[i].classList.remove('select-arrow-active');
    if (selectItems[i]) selectItems[i].classList.add('select-hide');
  }
}

// Function to display file groups in the dropdown
function displayFileGroups(groups) {
  const container = document.querySelector('.select-items');

  if (!container) {
    console.error("Error: select-items container not found.");
    return;
  }

  // Clear previous content
  container.innerHTML = "";

  if (groups.length === 0) {
    container.innerHTML = "<p>No groups available.</p>";
    return;
  }

  // Loop through groups and create checkboxes with IDs
  groups.forEach((group) => {
    const groupItem = document.createElement("div");
    groupItem.style.marginBottom = "5px"; // Optional styling for better visibility

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.id = `group-${group.id}`; // Updated ID syntax
    checkbox.name = "fileGroup";
    checkbox.value = group.id; // Set the group ID as the value

    const label = document.createElement("label");
    label.htmlFor = `group-${group.id}`; // Updated HTMLFor syntax
    label.textContent = ` ${group.group_name} (ID: ${group.id})`; // Show the group name and ID

    groupItem.appendChild(checkbox);
    groupItem.appendChild(label);
    container.appendChild(groupItem);
  });

  console.log("Displayed file groups in the dropdown with IDs.");
}

// ME HP
// Function to show error messages
function showErrors(message) {
  const errorContainer = document.getElementById('errorContainer');
  if (errorContainer) {
    errorContainer.textContent = message;
    errorContainer.style.display = 'block';
  }
}

// Function to clear error messages
function clearErrors() {
  const errorContainer = document.getElementById('errorContainer');
  if (errorContainer) {
    errorContainer.textContent = '';
    errorContainer.style.display = 'none';
  }
}

// ME HP

// Apply Filters
document.getElementById("applyFilter").addEventListener("click", function () {
  const selectedGroups = [
    ...document.querySelectorAll('.select-items input[name="fileGroup"]:checked')
  ].map(el => parseInt(el.value)); // Convert selected group values to integers (IDs)

  console.log("Applying filter with groups:", selectedGroups);

  // Update the global variable
  selectedGroupIds = selectedGroups;

  console.log("Selected group IDs:", selectedGroupIds);

  if (selectedGroupIds.length === 0) {
    showErrors("Please select at least one group.");
  } else {
    // ME HP
    clearErrors(); // Clear the error message if valid groups are selected
    // ME HP
    alert(`Filter applied with groups: ${selectedGroupIds.join(", ")}`);
  }

  // Call the backend function here, if necessary
  // sendToBackend(selectedGroupIds); // Uncomment and implement this function for backend logic
  // ME HP
  // Collapse the group selection after applying the filter
  document.getElementById('groupListContainer').style.display = 'none'; // Hide the group selection container
  document.getElementById('applyFilter').style.display = 'none'; // Hide the apply button
  //  ME HP

  toggleFilterDialog();  // Close the dialog after applying
});

// Toggle visibility of group list when "Query by Groups" is selected
document.querySelectorAll('input[name="filter"]').forEach((radio) => {
  radio.addEventListener('change', function() {
    if (this.value === 'group') {
      document.getElementById('groupListContainer').style.display = 'block'; // Show group selection container
      document.getElementById('applyFilter').style.display = 'block'; // Show apply button
    } else {
      document.getElementById('groupListContainer').style.display = 'none'; // Hide group selection container
      document.getElementById('applyFilter').style.display = 'none'; // Hide apply button
    }
  });
});

function displayGroupTiles(groups) {
  const container = document.getElementById('groupTiles');
  container.innerHTML = '';
  groups.forEach(group => {
    const tile = document.createElement('div');
    tile.className = 'group-tile';
    tile.setAttribute('data-group-id', group.id);
    tile.innerHTML = `
      <div class="group-tile-content">
        <h3>${group.group_name}</h3>
      </div>
      <div class="group-tile-options">
        <!-- Icons for Rename, Edit, and Delete -->
        <span class="icon" onclick="renameGroup(${group.id})" title="Rename">
          <img src="https://cdn.iconscout.com/icon/premium/png-256-thumb/pencil-tool-1-623277.png?f=webp&w=256" alt="Rename" title="Rename">
        </span>
        <span class="icon" onclick="editGroup(${group.id})" title="Edit">
          <img src="https://static-00.iconduck.com/assets.00/plus-icon-512x512-1ksw3ncc.png" alt="Edit" title="Edit">
        </span>
        <span class="icon" onclick="deleteGroup(${group.id})" title="Delete">
          <img src="https://cdn-icons-png.freepik.com/512/1345/1345874.png" alt="Delete" title="Delete">
        </span>
      </div>
    `;
    container.appendChild(tile);
  });
}

/*function displayFileGroups(groups) {
  const container = document.getElementById('groupListContainer');
  if (!container) 
  {
    console.error("Error: groupListContainer not found.");
    return;
  };

  container.innerHTML = '';
  if (groups.length === 0) {
    container.innerHTML = "<p>No groups available.</p>";
    return;
  }

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
});*/

async function renameGroup(groupId) {
  const groupTile = document.querySelector(`[data-group-id="${groupId}"]`); // Check if the group tile exists

  if (!groupTile) {
    console.error(`Group tile with ID ${groupId} not found.`);
    return;
  }

  const groupNameElement = groupTile.querySelector('h3'); // The <h3> element containing the group name
  if (!groupNameElement) {
    console.error('Group name element not found.');
    return;
  }

  const currentGroupName = groupNameElement.textContent;

  // Replace the group name with an input box
  groupNameElement.innerHTML = `<input type="text" value="${currentGroupName}" class="rename-input">`;

  const inputElement = groupNameElement.querySelector('.rename-input');
  if (!inputElement) {
    console.error('Input element not found.');
    return;
  }

  inputElement.focus(); // Automatically focus on the input box
  inputElement.select(); // Select the current text for easy editing

  // Listen for the 'Enter' keypress
  inputElement.addEventListener('keydown', async function (event) {
    if (event.key === 'Enter') {
      const newName = inputElement.value;

      if (newName && newName !== currentGroupName) {
        try {
          const response = await fetch('/rename-group', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ group_id: groupId, new_name: newName }),
          });

          const data = await response.json();
          if (data.success) {
            // Replace input with the new group name
            groupNameElement.innerHTML = newName;
            alert('Group renamed successfully!');
          } else {
            alert('Failed to rename group: ' + data.error);
            groupNameElement.innerHTML = currentGroupName; // Revert to old name on failure
          }
        } catch (error) {
          console.error('Error:', error);
          alert('An error occurred while renaming the group.');
          groupNameElement.innerHTML = currentGroupName; // Revert to old name on error
        }
      } else {
        // If the new name is the same or empty, revert to the old name
        groupNameElement.innerHTML = currentGroupName;
      }
    }
  });
}
document.addEventListener('DOMContentLoaded', function () {
  // Call your function or initialize elements here after DOM is loaded
  loadFileGroups(); // For example, calling your function that loads the groups
});  

async function deleteGroup(groupId) {
  if (confirm("Are you sure you want to delete this group?")) {
    try {
      const response = await fetch('/delete-group', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ group_id: groupId }),
      });
      const data = await response.json();
      if (data.success) {
        alert('Group deleted successfully!');
        loadFileGroups(); // Refresh the group list
      } else {
        alert('Failed to delete group: ' + data.error);
      }
    } catch (error) {
      console.error('Error:', error);
      alert('An error occurred while deleting the group.');
    }
  }
}

function editGroup(groupId) {
  fetch(`/get-group-files/${groupId}`)
    .then(response => response.json())
    .then(data => {
      showEditGroupModal(groupId, data.group_name, data.group_files, data.all_files);
    })
    .catch(error => {
      console.error('Error fetching group files:', error);
      alert('An error occurred while fetching group files.');
    });
}

function showEditGroupModal(groupId, groupName, groupFiles, allFiles) {
  const modal = document.createElement('div');
  modal.className = 'modal edit';
  modal.id = 'editGroupModal';

  const modalContent = document.createElement('div');
  modalContent.className = 'modal-content cedit';

  modalContent.innerHTML = `
      <span class="close" onclick="hideEditGroupModal()">&times;</span>
      <h2>Edit Group: ${groupName}</h2><br>
      <form id="editGroupForm">
          <input type="hidden" id="editGroupId" value="${groupId}">
          <input type="hidden" id="editGroupName" value="${groupName}">
          <p>Add or delete files for this group:</p>
          <div id="editGroupFiles" style="max-height: 200px; overflow-y: auto; border: 1px solid #ccc; padding: 10px;">
              ${allFiles.map(file => `
                  <label>
                      <input type="checkbox" name="groupFile" value="${file}" ${groupFiles.includes(file) ? 'checked' : ''}>
                      ${file}
                  </label><br>
              `).join('')}
          </div>
          <button type="submit" class="updategbutton">Update</button>
      </form>
  `;

  modal.appendChild(modalContent);
  document.body.appendChild(modal);

  document.getElementById('editGroupForm').addEventListener('submit', function(event) {
      event.preventDefault();
      updateGroup();
  });

  modal.style.display = 'block';
}

// Function to update the group
function updateGroup() {
  const groupId = document.getElementById('editGroupId').value;
  const groupName = document.getElementById('editGroupName').value;
  const selectedFiles = [...document.querySelectorAll('#editGroupFiles input[name="groupFile"]:checked')].map(el => el.value);

  const formData = new FormData();
  formData.append('group_id', groupId);
  formData.append('group_name', groupName);
  selectedFiles.forEach(file => formData.append('files', file));

  fetch('/update-group', {
      method: 'POST',
      body: formData
  })
  .then(response => response.json())
  .then(data => {
      if (data.success) {
          alert('Group updated successfully!');
          hideEditGroupModal();
          loadFileGroups();
      } else {
          alert('Failed to update group: ' + (data.error || 'Unknown error'));
      }
  })
  .catch(error => {
      console.error('Error:', error);
      alert('An error occurred while updating the group.');
  });
}

function showGroupDropdown() {
  const groupListContainer = document.getElementById('groupListContainer');
  const applyButton = document.getElementById('applyFilter');

  if (!groupListContainer) {
    console.error('Group list container not found');
    return;
  }

  if (document.querySelector('input[name="filter"][value="group"]').checked) {
    // Create the dropdown container if it doesn't exist
    let dropdownContainer = document.getElementById('groupDropdownContainer');
    if (!dropdownContainer) {
      dropdownContainer = document.createElement('div');
      dropdownContainer.id = 'groupDropdownContainer';
      dropdownContainer.innerHTML = `
        <div class="custom-select">
          <div class="select-selected">Select the group</div>
          <div class="select-items select-hide"></div>
        </div>
      `;
      groupListContainer.appendChild(dropdownContainer);
    }
    
    groupListContainer.style.display = 'block';
    if (applyButton) {
      applyButton.style.display = 'block';
      applyButton.style.float = 'right';
    }
    loadFileGroups();
  } else {
    groupListContainer.style.display = 'none';
    if (applyButton) applyButton.style.display = 'none';
  }
}

// Function to hide the edit group modal
function hideEditGroupModal() {
  const modal = document.getElementById('editGroupModal');
  if (modal) {
      modal.remove();
  }
}

function createCustomSelect() {
  var customSelect = document.getElementsByClassName("custom-select");
  for (var i = 0; i < customSelect.length; i++) {
    var selectSelected = customSelect[i].getElementsByClassName("select-selected")[0];
    var selectItems = customSelect[i].getElementsByClassName("select-items")[0];

    if (selectSelected) {
      selectSelected.addEventListener("click", function(e) {
        e.stopPropagation();
        closeAllSelect(this);
        selectItems.classList.toggle("select-hide");
        this.classList.toggle("select-arrow-active");
      });
    }

    if (selectItems) {
      var items = selectItems.getElementsByTagName("div");
      for (var j = 0; j < items.length; j++) {
        items[j].addEventListener("click", function(e) {
          var selectSelected = this.parentNode.previousSibling;
          selectSelected.innerHTML = this.innerHTML;
          selectSelected.click();
        });
      }
    }
  }
}

function closeAllSelect(elmnt) {
  var selectItems = document.getElementsByClassName("select-items");
  var selectSelected = document.getElementsByClassName("select-selected");
  for (var i = 0; i < selectSelected.length; i++) {
    if (elmnt != selectSelected[i]) {
      selectSelected[i].classList.remove("select-arrow-active");
    }
  }
  for (var i = 0; i < selectItems.length; i++) {
  
    if (elmnt != selectItems[i] && elmnt != selectSelected[i]) {
      selectItems[i].classList.add("select-hide");
    }
  }
}

// Close dropdowns when clicking outside
document.addEventListener("click", closeAllSelect);

// Call createCustomSelect when the DOM is fully loaded
document.addEventListener("DOMContentLoaded", createCustomSelect);
  

// Initialize WebSocket connection and load sessions when the page loads
window.onload = function () {
  connectWebSocket();
  loadSessions().then(() => {
    const chatItems = document.querySelectorAll(".chat-item");
    if (chatItems.length > 0) {
      chatItems[0].click(); // Load the first chat
    } else {
      // No existing chats, start a new chat
      startNewChat();
    }
  });

  loadFileGroups()
    .then(groups => {
      // The groups are already displayed by the loadFileGroups function
      // You can do additional operations with the groups here if needed
      console.log('Groups loaded:', groups);
    })
    .catch(error => {
      console.error('Error in window.onload:', error);
    });

  // Add event listeners to radio buttons for filter options
  document.querySelectorAll('input[name="filter"]').forEach((elem) => {
    elem.addEventListener("change", showGroupList);
  });
};