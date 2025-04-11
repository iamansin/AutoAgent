import asyncio
import websockets
import json
import logging
import uuid
from asyncio import Future
from typing import Optional, Dict, Any
from contextlib import AsyncExitStack
from pydantic import BaseModel, Field
from browser_use import ActionResult
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("HumanInTheLoop")

# Global state to manage WebSocket server
_websocket_server = None
_connected_clients = set()
_pending_requests: Dict[str, Future] = {}

class HumanInput(BaseModel):
    input :Dict = Field(default_factory = dict)

async def _handle_client(websocket, path):
    """
    Handle a connected WebSocket client.
    
    Args:
        websocket: WebSocket connection
        path: Connection path
    """
    client_id = str(uuid.uuid4())[:8]
    logger.info(f"Client connected [ID: {client_id}]")
    _connected_clients.add(websocket)
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                message_type = data.get("type")
                
                if message_type == "input_response":
                    request_id = data.get("request_id")
                    input_value = data.get("value")
                    
                    if request_id in _pending_requests:
                        future = _pending_requests[request_id]
                        if not future.done():
                            future.set_result(input_value)
                            logger.info(f"Input received for request {request_id}: {input_value}")
                        del _pending_requests[request_id]
                    else:
                        logger.warning(f"Received response for unknown request: {request_id}")
                else:
                    logger.warning(f"Unknown message type: {message_type}")
            except json.JSONDecodeError:
                logger.error("Invalid JSON message received")
            except Exception as e:
                logger.error(f"Error processing message: {e}")
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Client disconnected [ID: {client_id}]")
    except Exception as e:
        logger.error(f"Error handling client: {e}")
    finally:
        _connected_clients.discard(websocket)

async def _ensure_websocket_server(port: int = 8765) -> None:
    """
    Ensure the WebSocket server is running.
    
    Args:
        port: Port for the WebSocket server
    """
    global _websocket_server
    
    if _websocket_server is None:
        try:
            logger.info(f"Starting WebSocket server on port {port}")
            _websocket_server = await websockets.serve(_handle_client, "0.0.0.0", port)
            logger.info(f"WebSocket server running on port {port}")
        except Exception as e:
            logger.error(f"Failed to start WebSocket server: {e}")
            raise RuntimeError(f"WebSocket server startup failed: {e}")

async def _broadcast_to_clients(message: Dict[str, Any]) -> None:
    """
    Broadcast a message to all connected clients.
    
    Args:
        message: Message to broadcast
    """
    if not _connected_clients:
        logger.warning("No clients connected to receive broadcast")
        return
        
    disconnected = set()
    message_json = json.dumps(message)
    
    for client in _connected_clients:
        try:
            await client.send(message_json)
        except websockets.exceptions.ConnectionClosed:
            disconnected.add(client)
        except Exception as e:
            logger.error(f"Error sending message to client: {e}")
            disconnected.add(client)
    
    # Remove disconnected clients
    for client in disconnected:
        _connected_clients.discard(client)

async def get_human_in_loop(question: str, timeout: float = 300.0, port: int = 8765, metadata: Optional[Dict[str, Any]] = None) -> str:
    """
    Request input from a human through a WebSocket connection.
    This function sends a question to connected clients and waits for a response.
    The automation process will pause until input is received or the timeout is reached.
    
    Args:
        question: The question to ask the human
        timeout: Timeout in seconds for waiting for input (default: 5 minutes)
        port: Port for the WebSocket server
        metadata: Optional metadata to send with the question
    
    Returns:
        The human's response as a string
        
    Raises:
        asyncio.TimeoutError: If no response is received within the timeout period
        RuntimeError: If the WebSocket server fails to start or other errors occur
    """
    try:
        # Ensure the WebSocket server is running
        await _ensure_websocket_server(port)
        
        if not _connected_clients:
            logger.warning("No clients connected to receive the question")
            # We'll still continue and wait for clients to connect
        
        # Generate a unique ID for this request
        request_id = str(uuid.uuid4())
        
        # Create a future to be resolved when the input is received
        input_future = asyncio.Future()
        _pending_requests[request_id] = input_future
        
        # Prepare the question message
        message = {
            "type": "input_request",
            "request_id": request_id,
            "question": question
        }
        
        # Add metadata if provided
        if metadata:
            message["metadata"] = metadata
            
        # Send the question to all connected clients
        await _broadcast_to_clients(message)
        logger.info(f"Input request sent [ID: {request_id}]: {question}")
        
        try:
            # Wait for the response with timeout
            response = await asyncio.wait_for(input_future, timeout=timeout)
            return ActionResult(extracted_content=response)
        
        except asyncio.TimeoutError:
            # Remove the pending request if timeout occurs
            if request_id in _pending_requests:
                del _pending_requests[request_id]
            logger.error(f"Timeout waiting for input [ID: {request_id}]")
            raise asyncio.TimeoutError(f"No response received for question within {timeout} seconds")
    except Exception as e:
        if isinstance(e, asyncio.TimeoutError):
            raise
        logger.error(f"Error in get_human_in_loop: {e}")
        raise RuntimeError(f"Failed to get human input: {e}")

# Helper function to stop the WebSocket server
async def stop_websocket_server():
    """Stop the WebSocket server if it's running."""
    global _websocket_server
    
    if _websocket_server:
        # Cancel any pending requests
        for request_id, future in list(_pending_requests.items()):
            if not future.done():
                future.set_exception(asyncio.CancelledError("WebSocket server shutting down"))
        
        # Close all client connections
        for client in list(_connected_clients):
            try:
                await client.close()
            except Exception:
                pass
        
        # Close the server
        _websocket_server.close()
        await _websocket_server.wait_closed()
        _websocket_server = None
        _connected_clients.clear()
        _pending_requests.clear()
        logger.info("WebSocket server stopped")

