// server/web/app/static/js/main.js
const chatHistory = document.getElementById("chat-history");
const chatForm = document.getElementById("chat-form");
const messageInput = document.getElementById("message-input");

let sessionId = null;
let socket = null;

async function createSession() {
    const response = await fetch("/api/chat/session", {
        method: "POST",
    });
    const data = await response.json();
    sessionId = data.session_id;
    socket = new WebSocket(`ws://localhost:8000/ws/chat/${sessionId}`);
    socket.onmessage = (event) => {
        appendMessage("AI", event.data);
    };
}

function sendMessage(prompt) {
    socket.send(prompt);
}

function appendMessage(sender, text) {
    const messageElement = document.createElement("div");
    messageElement.innerHTML = `<strong>${sender}:</strong> ${text}`;
    chatHistory.appendChild(messageElement);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = messageInput.value;
    messageInput.value = "";
    appendMessage("You", message);
    sendMessage(message);
});

createSession();
