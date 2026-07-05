import json
from fastapi import WebSocket
from typing import Dict


class ConnectionManager:
    def __init__(self):
        # Dictionary mapping the WebSocket object to the user's email
        self.active_connections: Dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, email: str):
        # We assume websocket.accept() is handled in the router
        self.active_connections[websocket] = email
        await self.broadcast_online_users()

    async def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            del self.active_connections[websocket]
            await self.broadcast_online_users()

    async def broadcast_online_users(self):
        # Extract unique emails (in case one user has multiple tabs open)
        online_emails = list(set(self.active_connections.values()))

        # Format it exactly how the frontend expects it
        message = json.dumps({
            "action": "ONLINE_USERS",
            "users": online_emails
        })
        await self.broadcast(message)

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