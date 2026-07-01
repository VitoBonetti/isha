from fastapi import WebSocket
from typing import Dict

class ConnectionManager:
    def __init__(self):
        # Dictionary mapping the WebSocket object to the user's email
        self.active_connections: Dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, email: str):
        # We assume websocket.accept() is handled in the router
        self.active_connections[websocket] = email
        # Broadcast that the user joined using the new 'email' key
        await self.broadcast(f'{{"action": "USER_JOINED", "email": "{email}"}}')

    async def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            email = self.active_connections.pop(websocket)
            # Broadcast that the user left using the new 'email' key
            await self.broadcast(f'{{"action": "USER_LEFT", "email": "{email}"}}')

    async def broadcast(self, message: str):
        # If a change happens, send a message to all connected browsers
        for connection in list(self.active_connections.keys()):
            try:
                await connection.send_text(message)
            except Exception:
                # If a connection is dead but not yet removed, ignore the error
                pass

# Make a single, global instance of the manager
manager = ConnectionManager()