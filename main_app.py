from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
from typing import Optional
from Utils.websocket_manager import ws_manager, WebSocketMessage
from agent_setup import run_agent_task, cleanup_session

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start the external WebSocket server
    background_task = asyncio.create_task(ws_manager.start_external_server())
    yield
    # Shutdown: Clean up resources
    await ws_manager.cleanup()

app = FastAPI(
    title="Agent WebSocket API",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for agent interaction"""
    # Connect to the WebSocket
    await ws_manager.connect(websocket, session_id)
    
    # Define a function to send updates
    async def send_updates(message):
        if isinstance(message, dict):
            # Create proper WebSocketMessage structure
            if "type" not in message:
                message["type"] = "status"
            if "content" not in message and isinstance(message, dict):
                content = {k: v for k, v in message.items() if k != "type" and k != "session_id"}
                ws_message = WebSocketMessage(
                    type=message["type"],
                    content=content,
                    session_id=session_id
                )
                await ws_manager.send_message(ws_message, session_id)
            else:
                await ws_manager.send_message(message, session_id)
        else:
            await ws_manager.send_message(message, session_id)
    
    try:
        # Welcome message
        await send_updates({
            "type": "status",
            "content": {
                "message": f"Connected to agent service with session ID: {session_id}",
                "status": "connected"
            }
        })
        
        # Listen for messages from the client
        while True:
            data = await websocket.receive_text()
            try:
                # Parse the message
                message = json.loads(data)
                
                # Handle different message types
                if message.get("type") == "task":
                    task = message.get("content", {}).get("task") or message.get("task")
                    if not task:
                        await send_updates({
                            "type": "error",
                            "content": {
                                "message": "No task provided",
                                "status": "error"
                            }
                        })
                        continue
                    
                    # Create and register a new task
                    agent_task = asyncio.create_task(
                        run_agent_task(task, session_id, send_updates)
                    )
                    ws_manager.register_task(session_id, agent_task)
                    
                    await send_updates({
                        "type": "status",
                        "content": {
                            "message": f"Processing task: {task}",
                            "status": "processing"
                        }
                    })
                
                elif message.get("type") == "cancel":
                    # Cancel the current task if it exists
                    task = ws_manager.get_task(session_id)
                    if task and not task.done():
                        task.cancel()
                        await send_updates({
                            "type": "status",
                            "content": {
                                "message": "Task cancelled",
                                "status": "cancelled"
                            }
                        })
                        # Clean up resources
                        await cleanup_session(session_id)
                    else:
                        await send_updates({
                            "type": "status",
                            "content": {
                                "message": "No active task to cancel",
                                "status": "info"
                            }
                        })
                
                elif message.get("type") == "user_input_response":
                    # This is handled directly by the WebSocketManager
                    request_id = message.get("request_id")
                    if request_id:
                        await send_updates({
                            "type": "status",
                            "content": {
                                "message": f"Received user input response for request: {request_id}",
                                "status": "info"
                            }
                        })
                
                else:
                    await send_updates({
                        "type": "error",
                        "content": {
                            "message": f"Unknown message type: {message.get('type')}",
                            "status": "error"
                        }
                    })
                    
            except json.JSONDecodeError:
                await send_updates({
                    "type": "error",
                    "content": {
                        "message": "Invalid JSON format",
                        "status": "error"
                    }
                })
            
            except Exception as e:
                await send_updates({
                    "type": "error",
                    "content": {
                        "message": f"Error processing message: {str(e)}",
                        "status": "error"
                    }
                })
    
    except WebSocketDisconnect:
        # Handle disconnect
        ws_manager.disconnect(websocket, session_id)
        # Clean up resources when the client disconnects
        await cleanup_session(session_id)
    
    except Exception as e:
        # Handle any other exceptions
        try:
            await send_updates({
                "type": "error",
                "content": {
                    "message": f"Unexpected error: {str(e)}",
                    "status": "error"
                }
            })
        except:
            pass
        ws_manager.disconnect(websocket, session_id)
        await cleanup_session(session_id)

@app.post("/request_input")
async def request_user_input(
    prompt: str, 
    session_id: Optional[str] = None, 
    timeout: int = 300
):
    """API endpoint to request user input"""
    try:
        result = await ws_manager.request_user_input(prompt, session_id, timeout)
        return {"status": "success", "input": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error requesting input: {str(e)}")

@app.get("/")
async def root():
    return {
        "message": "Agent WebSocket API is running.",
        "endpoints": {
            "websocket": "/ws/{session_id}",
            "request_input": "/request_input"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)