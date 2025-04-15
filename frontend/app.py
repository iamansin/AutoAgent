import streamlit as st
import websockets.client
import websockets.exceptions
import asyncio
import json
import base64
from PIL import Image
import io
import os
import uuid
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("browser_agent.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("browser_agent_frontend")

# Constants
WEBSOCKET_URI = "ws://localhost:8000/ws"  # Updated to match FastAPI endpoint
RECONNECT_DELAY = 5  # seconds
SCREENSHOT_DIR = "screenshots"
MAX_RECONNECT_ATTEMPTS = 5

# Create directories to store session data
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

class WebSocketManager:
    """Manages WebSocket connections and communication"""
    
    def __init__(self, uri: str, session_id: str, on_message_callback, on_status_change):
        self.uri = uri
        self.session_id = session_id
        self.websocket = None
        self.connected = False
        self.on_message_callback = on_message_callback
        self.on_status_change = on_status_change
        self.reconnect_attempts = 0
        self.running = False
        self.connection_thread = None
        self.message_queue = asyncio.Queue()
    
    async def connect(self):
        """Establish a WebSocket connection with retry logic"""
        self.running = True
        while self.running and self.reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
            try:
                logger.info(f"Connecting to WebSocket server at {self.uri}")
                self.websocket = await websockets.client.connect(self.uri)
                self.connected = True
                self.reconnect_attempts = 0
                self.on_status_change(True)
                
                # Send session ID to establish identity
                await self.send_message({
                    "type": "session_init",
                    "content": {"session_id": self.session_id},
                    "session_id": self.session_id
                })
                
                # Handle message queue and incoming messages in parallel
                await asyncio.gather(
                    self._process_message_queue(),
                    self._receive_messages()
                )
            
            except Exception as e:
                if isinstance(e, websockets.exceptions.WebSocketException) or "closed" in str(e).lower():
                    logger.warning(f"WebSocket connection closed: {str(e)}")
                else:
                    logger.error(f"WebSocket error: {str(e)}", exc_info=True)
                
                self._handle_disconnection()
            
            # If still running, attempt to reconnect after delay
            if self.running:
                await asyncio.sleep(RECONNECT_DELAY)
        
        if self.reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
            logger.error("Maximum reconnection attempts reached")
            self.on_status_change(False, "Failed to connect after multiple attempts")
    
    async def _receive_messages(self):
        """Listen for incoming messages"""
        while self.connected and self.websocket:
            try:
                message = await self.websocket.recv()
                await self._handle_message(message)
            except Exception as e:
                logger.error(f"Error receiving message: {str(e)}", exc_info=True)
                break
    
    async def _process_message_queue(self):
        """Process queued messages"""
        while self.connected and self.websocket:
            try:
                message = await self.message_queue.get()
                await self.websocket.send(json.dumps(message))
                self.message_queue.task_done()
            except Exception as e:
                logger.error(f"Error processing message queue: {str(e)}", exc_info=True)
                break
    
    async def _handle_message(self, message: str):
        """Process an incoming message"""
        try:
            data = json.loads(message)
            await self.on_message_callback(data)
        except json.JSONDecodeError:
            logger.error(f"Received invalid JSON: {message}")
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}", exc_info=True)
    
    def _handle_disconnection(self):
        """Handle WebSocket disconnection"""
        self.connected = False
        self.websocket = None
        self.reconnect_attempts += 1
        self.on_status_change(False)
        logger.info(f"Disconnected. Reconnect attempt {self.reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS}")
    
    async def send_message(self, message: Dict[str, Any]):
        """Send a message to the WebSocket server"""
        if not isinstance(message, dict):
            raise ValueError("Message must be a dictionary")
        
        # Ensure required fields are present
        if "type" not in message:
            raise ValueError("Message must have a 'type' field")
        
        if "content" not in message:
            message["content"] = {}
            
        # Add session ID and timestamp
        message["session_id"] = self.session_id
        message["timestamp"] = datetime.now().isoformat()
        
        if self.websocket and self.connected:
            await self.websocket.send(json.dumps(message))
        else:
            await self.message_queue.put(message)
            
    def queue_message(self, message: Dict[str, Any]):
        """Queue a message from the main thread"""
        asyncio.run_coroutine_threadsafe(
            self.send_message(message), 
            asyncio.get_event_loop()
        )
    
    def start(self):
        """Start the WebSocket manager in a separate thread"""
        def run_async_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.connect())
        
        self.connection_thread = threading.Thread(target=run_async_loop, daemon=True)
        self.connection_thread.start()
    
    def stop(self):
        """Stop the WebSocket manager"""
        self.running = False
        self.connected = False
        # Thread will terminate once running is set to False

class ScreenshotManager:
    """Manages screenshot storage and retrieval"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.session_dir = os.path.join(SCREENSHOT_DIR, session_id)
        os.makedirs(self.session_dir, exist_ok=True)
        self.screenshots = []  # List of (image, timestamp, step) tuples
    
    def save_screenshot(self, image_data: str, step: Optional[int] = None) -> Optional[Image.Image]:
        """Save a base64-encoded screenshot and return PIL Image"""
        try:
            # Decode base64 image
            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))
            
            # Generate timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Save to filesystem
            step_str = f"_step{step}" if step is not None else ""
            filename = f"screenshot{step_str}_{timestamp}.png"
            filepath = os.path.join(self.session_dir, filename)
            image.save(filepath)
            
            # Add to in-memory collection
            self.screenshots.append((image, timestamp, step))
            
            logger.info(f"Saved screenshot to {filepath}")
            return image
        
        except Exception as e:
            logger.error(f"Error saving screenshot: {str(e)}", exc_info=True)
            return None
    
    def get_recent_screenshots(self, count: int = 6) -> List[tuple]:
        """Return the most recent screenshots with their metadata"""
        return self.screenshots[-count:]
    
    def get_latest_screenshot(self) -> Optional[Image.Image]:
        """Return the latest screenshot, or None if none exists"""
        if self.screenshots:
            return self.screenshots[-1][0]
        return None

# UI Component functions
def render_connection_status(connected: bool, message: Optional[str] = None):
    """Render WebSocket connection status"""
    status_container = st.empty()
    
    if connected:
        status_container.success("✅ Connected to WebSocket Server")
    else:
        if message:
            status_container.error(f"❌ Not Connected: {message}")
        else:
            status_container.warning("⚠️ Not Connected")
    
    return status_container

def render_task_input():
    """Render the task input form"""
    with st.form("task_form", clear_on_submit=True):
        task = st.text_input("Enter task for the browser agent:", 
                            placeholder="e.g., Search for news about AI")
        user_id = st.text_input("User ID (optional):", value="default", key="user_id_input")
        submit_task = st.form_submit_button("Send Task")
        
        if submit_task and task:
            return {"task": task, "user_id": user_id}
    return None

def render_user_response_input(prompt: str, request_id: str):
    """Render a form for user to respond to agent prompts"""
    with st.form("response_form", clear_on_submit=True):
        st.write(f"**Agent is asking:** {prompt}")
        response = st.text_input("Your response:", key="user_response")
        submit_response = st.form_submit_button("Send Response")
        
        if submit_response:
            return {"response": response, "request_id": request_id}
    return None

def render_screenshot_display(screenshot: Optional[Image.Image]):
    """Render the latest screenshot display area"""
    screenshot_container = st.empty()
    
    if screenshot:
        screenshot_container.image(screenshot, caption="Current Browser View", use_column_width=True)
    else:
        screenshot_container.info("No screenshots available yet. Start a task to see browser activity.")
    
    return screenshot_container

def render_screenshot_gallery(screenshots: List[tuple]):
    """Render a gallery of recent screenshots"""
    if not screenshots:
        return
    
    st.subheader("Recent Activity")
    
    # Calculate number of columns based on number of screenshots
    num_cols = min(3, len(screenshots))
    if num_cols == 0:
        return
    
    cols = st.columns(num_cols)
    
    for idx, (screenshot, timestamp, step) in enumerate(screenshots):
        with cols[idx % num_cols]:
            step_text = f"Step {step}" if step is not None else f"Screenshot {idx + 1}"
            st.image(screenshot, caption=f"{step_text} - {timestamp}", use_column_width=True)

def render_session_info(session_id: str):
    """Render session information"""
    with st.expander("Session Information"):
        st.code(session_id, language="text")
        st.caption("This is your session ID. Keep it if you need to reference this session later.")

def main():
    """Main Streamlit application"""
    # Page config
    st.set_page_config(
        page_title="Browser Agent Control Panel",
        page_icon="🌐",
        layout="wide",
    )
    
    # Initialize session state
    if 'session_id' not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    
    if 'screenshot_manager' not in st.session_state:
        st.session_state.screenshot_manager = ScreenshotManager(st.session_state.session_id)
    
    if 'websocket_manager' not in st.session_state:
        st.session_state.websocket_manager = None
    
    if 'connected' not in st.session_state:
        st.session_state.connected = False
    
    if 'awaiting_response' not in st.session_state:
        st.session_state.awaiting_response = False
    
    if 'response_prompt' not in st.session_state:
        st.session_state.response_prompt = None
    
    if 'request_id' not in st.session_state:
        st.session_state.request_id = None
    
    if 'task_running' not in st.session_state:
        st.session_state.task_running = False
        
    # App title and description
    st.title("🌐 Browser Agent Control Panel")
    st.markdown("""
    This interface allows you to control a browser agent that performs tasks on your behalf.
    Enter a task below, and the agent will navigate the web accordingly.
    """)
    
    # Session info
    render_session_info(st.session_state.session_id)
    
    # Connection status
    status_container = render_connection_status(st.session_state.connected)
    
    # Initialize WebSocket connection if not already done
    if not st.session_state.websocket_manager:
        async def on_message(data: Dict[str, Any]):
            """Handle incoming WebSocket messages"""
            try:
                message_type = data.get("type")
                content = data.get("content", {})
                
                if message_type == "screenshot":
                    # Process and display screenshot
                    image_data = content.get("image")
                    step = content.get("step")
                    if image_data:
                        image = st.session_state.screenshot_manager.save_screenshot(image_data, step)
                        if image:
                            st.session_state.latest_screenshot = image
                            # Use rerun to update the UI with new screenshot
                            st.rerun()
                
                elif message_type == "user_input_request":
                    # Agent is asking for user input
                    st.session_state.awaiting_response = True
                    st.session_state.response_prompt = content.get("prompt", "")
                    st.session_state.request_id = content.get("request_id")
                    st.rerun()
                
                elif message_type == "status":
                    # Status update from agent
                    status = content.get("status", "")
                    if status == "started":
                        st.session_state.task_running = True
                        st.toast(f"Task started: {content.get('task', '')}", icon="🚀")
                    elif status == "completed":
                        st.session_state.task_running = False
                        st.toast("Task completed successfully!", icon="✅")
                    elif status == "error":
                        st.session_state.task_running = False
                        st.toast(f"Error: {content.get('error', 'Unknown error')}", icon="❌")
                    else:
                        st.toast(status, icon="ℹ️")
                
                else:
                    logger.info(f"Received message of type: {message_type}")
                
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}", exc_info=True)
        
        def on_status_change(connected: bool, message: Optional[str] = None):
            """Handle WebSocket connection status changes"""
            st.session_state.connected = connected
            # This will update on next rerun
        
        # Create and start WebSocket manager
        st.session_state.websocket_manager = WebSocketManager(
            WEBSOCKET_URI,
            st.session_state.session_id,
            on_message,
            on_status_change
        )
        st.session_state.websocket_manager.start()
    
    # Layout the main content areas
    col1, col2 = st.columns([3, 2])
    
    with col1:
        # Task status indicator
        if st.session_state.task_running:
            st.info("🔄 Task is currently running...")
        
        # Screenshot display
        screenshot_container = render_screenshot_display(
            getattr(st.session_state, 'latest_screenshot', None)
        )
        
        # User response area - show only when agent is awaiting response
        if st.session_state.awaiting_response and st.session_state.response_prompt:
            user_input = render_user_response_input(
                st.session_state.response_prompt,
                st.session_state.request_id
            )
            
            if user_input:
                # Send response back to agent
                if st.session_state.websocket_manager:
                    st.session_state.websocket_manager.queue_message({
                        "type": "user_input_response",
                        "content": {
                            "input": user_input["response"],
                            "request_id": user_input["request_id"]
                        }
                    })
                    st.session_state.awaiting_response = False
                    st.session_state.response_prompt = None
                    st.session_state.request_id = None
                    st.success("Response sent!")
                    time.sleep(1)  # Give UI time to update
                    st.rerun()
    
    with col2:
        # Task input
        task_info = render_task_input()
        
        if task_info:
            if st.session_state.websocket_manager and st.session_state.connected:
                # Send task to agent
                st.session_state.websocket_manager.queue_message({
                    "type": "agent_task",
                    "content": {
                        "task": task_info["task"],
                        "user_id": task_info["user_id"]
                    }
                })
                st.success(f"Task sent: {task_info['task']}")
                st.session_state.task_running = True
            else:
                st.error("Cannot send task: Not connected to WebSocket server")
        
        # Recent screenshots gallery
        screenshots = st.session_state.screenshot_manager.get_recent_screenshots()
        render_screenshot_gallery(screenshots)
    
    # Footer
    st.divider()
    st.caption("© 2025 Browser Agent - Powered by Streamlit and WebSockets")

if __name__ == "__main__":
    main()