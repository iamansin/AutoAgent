import asyncio
import json
import logging
import uuid
from typing import Dict, List, Any, Optional, Callable
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import websockets

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("WebSocketManager")

class WebSocketMessage(BaseModel):
    type: str
    content: Dict[str, Any]
    session_id: str
    request_id: Optional[str] = None

class ConnectionManager:
    def __init__(self, external_ws_url: str = "ws://localhost:8765"):
        # Dictionary to store active connections with session_id as key (FastAPI WebSockets)
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Dictionary to store tasks for each session
        self.session_tasks: Dict[str, asyncio.Task] = {}
        # Dictionary to store pending user input requests
        self.pending_requests: Dict[str, asyncio.Future] = {}
        
        # External WebSocket server attributes
        self.external_ws_url = external_ws_url
        self.external_connections: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.external_server = None
        self.is_external_server_running = False

    # FastAPI WebSocket connection management
    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)
        logger.info(f"New FastAPI WebSocket connection established: {session_id}")
        return True

    def disconnect(self, websocket: WebSocket, session_id: str):
        if session_id in self.active_connections:
            if websocket in self.active_connections[session_id]:
                self.active_connections[session_id].remove(websocket)
                logger.info(f"FastAPI WebSocket disconnected: {session_id}")
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]
                # Cancel any running task for this session
                if session_id in self.session_tasks:
                    self.session_tasks[session_id].cancel()
                    del self.session_tasks[session_id]
                    logger.info(f"Cancelled tasks for session: {session_id}")

    async def send_message(self, message: Any, session_id: str):
        """Send message to FastAPI WebSocket clients"""
        if session_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[session_id]:
                try:
                    if isinstance(message, str):
                        await connection.send_text(message)
                    elif isinstance(message, WebSocketMessage):
                        await connection.send_json(message.model_dump())
                    else:
                        await connection.send_json(message)
                    logger.debug(f"Message sent to session {session_id}")
                except Exception as e:
                    logger.error(f"Error sending message: {e}")
                    disconnected.append(connection)
            
            # Clean up any disconnected websockets
            for conn in disconnected:
                self.disconnect(conn, session_id)
            
            return len(self.active_connections[session_id]) > 0
        return False

    def register_task(self, session_id: str, task: asyncio.Task):
        """Register an asyncio task for a specific session"""
        if session_id in self.session_tasks and not self.session_tasks[session_id].done():
            self.session_tasks[session_id].cancel()
        self.session_tasks[session_id] = task
        logger.info(f"Registered new task for session: {session_id}")

    def get_task(self, session_id: str):
        """Get the task for a specific session if it exists"""
        return self.session_tasks.get(session_id)

    # External WebSocket server methods
    async def start_external_server(self):
        """Start an external WebSocket server for non-FastAPI clients"""
        if self.is_external_server_running:
            return
            
        host, port = self.external_ws_url.replace("ws://", "").split(":")
        self.external_server = await websockets.serve(self.handle_external_connection, host, int(port))
        self.is_external_server_running = True
        logger.info(f"External WebSocket server started at {self.external_ws_url}")

    async def handle_external_connection(self, websocket, path = None):
        """Handle connections to the external WebSocket server"""
        session_id = str(uuid.uuid4())
        self.external_connections[session_id] = websocket
        logger.info(f"New external connection established: {session_id}")
        
        try:
            async for message in websocket:
                await self.process_external_message(session_id, message)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"External connection closed: {session_id}")
        finally:
            if session_id in self.external_connections:
                del self.external_connections[session_id]

    async def process_external_message(self, session_id: str, message: str):
        """Process messages from external WebSocket connections"""
        try:
            data = json.loads(message)
            message_type = data.get("type")
            content = data.get("content", {})
            request_id = data.get("request_id")
            
            logger.info(f"Received external message: {message_type} from {session_id}")
            
            if message_type == "user_input_response" and request_id in self.pending_requests:
                future = self.pending_requests[request_id]
                if not future.done():
                    future.set_result(content.get("input", ""))
                del self.pending_requests[request_id]
                
        except Exception as e:
            logger.error(f"Error processing external message: {e}")

    async def send_external_message(self, message: WebSocketMessage, session_id: Optional[str] = None):
        """Send message to external WebSocket clients"""
        if session_id and session_id in self.external_connections:
            websocket = self.external_connections[session_id]
            await websocket.send(message.model_dump_json())
            logger.debug(f"Message sent to external session {session_id}")
        else:
            # Broadcast to all external connections if no specific session_id
            for _, websocket in self.external_connections.items():
                await websocket.send(message.model_dump_json())
                logger.debug("Message broadcast to all external sessions")

    async def broadcast_message(self, message: Any):
        """Broadcast message to all clients (both FastAPI and external)"""
        # Convert message to appropriate format if needed
        ws_message = message
        if not isinstance(message, WebSocketMessage) and not isinstance(message, str):
            if isinstance(message, dict):
                session_id = message.get("session_id", str(uuid.uuid4()))
                message_type = message.get("type", "notification")
                content = message.get("content", message)
                ws_message = WebSocketMessage(
                    type=message_type,
                    content=content,
                    session_id=session_id
                )
        
        # Send to all FastAPI clients
        for session_id in self.active_connections:
            await self.send_message(ws_message, session_id)
        
        # Send to all external clients
        if isinstance(ws_message, WebSocketMessage):
            for session_id in self.external_connections:
                await self.send_external_message(ws_message, session_id)
        elif isinstance(ws_message, str):
            ws_message = WebSocketMessage(
                type="notification",
                content={"message": ws_message},
                session_id=str(uuid.uuid4())
            )
            for session_id in self.external_connections:
                await self.send_external_message(ws_message, session_id)

    async def request_user_input(self, prompt: str, session_id: Optional[str] = None, timeout: int = 300) -> str:
        """Request input from user and wait for response"""
        request_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        self.pending_requests[request_id] = future
        
        message = WebSocketMessage(
            type="user_input_request",
            content={"prompt": prompt},
            session_id=session_id or str(uuid.uuid4()),
            request_id=request_id
        )
        
        # Send to FastAPI clients
        if session_id in self.active_connections:
            await self.send_message(message, session_id)
        
        # Send to external clients
        if session_id in self.external_connections:
            await self.send_external_message(message, session_id)
        elif session_id is None:
            # Broadcast to all external clients if no specific session
            for ext_session_id in self.external_connections:
                await self.send_external_message(message, ext_session_id)
        
        try:
            # Wait for response with timeout
            logger.info(f"Waiting for user input with request ID: {request_id}")
            return await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError:
            if request_id in self.pending_requests:
                del self.pending_requests[request_id]
            logger.warning(f"User input request timed out: {request_id}")
            return ""

    async def stop_external_server(self):
        """Stop the external WebSocket server"""
        if self.external_server:
            self.external_server.close()
            await self.external_server.wait_closed()
            self.is_external_server_running = False
            logger.info("External WebSocket server stopped")

    async def cleanup(self):
        """Clean up all resources"""
        # Cancel all tasks
        for session_id, task in self.session_tasks.items():
            if not task.done():
                task.cancel()
        
        # Clear all pending requests
        for request_id, future in self.pending_requests.items():
            if not future.done():
                future.cancel()
        
        # Stop external server
        await self.stop_external_server()
        
        logger.info("WebSocket manager cleaned up")

# Create a global instance
ws_manager = ConnectionManager()