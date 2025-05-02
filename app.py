import streamlit as st
import websocket
import json
import threading
import time
import base64
from io import BytesIO
import requests
from PIL import Image
import uuid

# Configuration
WEBSOCKET_URL = "ws://localhost:8000/ws/"
API_URL = "http://localhost:8000"

# Initialize session state
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())  # Generate unique session ID

if 'screenshots' not in st.session_state:
    st.session_state.screenshots = []
    
if 'current_prompt' not in st.session_state:
    st.session_state.current_prompt = None
    
if 'current_request_id' not in st.session_state:
    st.session_state.current_request_id = None
    
if 'ws_connected' not in st.session_state:
    st.session_state.ws_connected = False

if 'messages' not in st.session_state:
    st.session_state.messages = []
    
if 'current_task_id' not in st.session_state:
    st.session_state.current_task_id = None
    
if 'agent_busy' not in st.session_state:
    st.session_state.agent_busy = False

if 'current_screenshot_index' not in st.session_state:
    st.session_state.current_screenshot_index = 0

# WebSocket handlers
def on_message(ws, message):
    try:
        data = json.loads(message)
        message_type = data.get('type')
        
        if message_type == 'screenshot':
            # Process screenshot data
            screenshot_data = data.get('content', {}).get('image')
            step = data.get('content', {}).get('step', 0)
            timestamp = data.get('content', {}).get('timestamp', "")
            
            if screenshot_data:
                st.session_state.screenshots.append({
                    "image": screenshot_data,
                    "step": step,
                    "timestamp": timestamp
                })
                # Set the current index to the latest screenshot
                st.session_state.current_screenshot_index = len(st.session_state.screenshots) - 1
            
        elif message_type == 'input_request':
            # Store the prompt and request ID
            content = data.get('content', {})
            st.session_state.current_prompt = content.get('prompt')
            st.session_state.current_request_id = content.get('request_id')
            
            # Add the prompt to messages
            st.session_state.messages.append({"role": "agent", "content": content.get('prompt')})
            
        elif message_type == 'task_status':
            content = data.get('content', {})
            status = content.get('status')
            
            if status == 'started':
                st.session_state.agent_busy = True
                st.session_state.messages.append({
                    "role": "system", 
                    "content": f"Agent has started working on your task."
                })
                
            elif status in ['completed', 'error', 'cancelled']:
                st.session_state.agent_busy = False
                if status == 'error':
                    error_msg = content.get('message', 'Unknown error occurred')
                    st.session_state.messages.append({
                        "role": "system", 
                        "content": f"Task failed: {error_msg}"
                    })
                elif status == 'completed':
                    st.session_state.messages.append({
                        "role": "system", 
                        "content": "Task completed successfully!"
                    })
                elif status == 'cancelled':
                    st.session_state.messages.append({
                        "role": "system", 
                        "content": "Task was cancelled."
                    })
                
                st.session_state.current_task_id = None
                
        # Force a rerun to update the UI
        st.rerun()
    except Exception as e:
        print(f"Error processing WebSocket message: {e}")

def on_error(ws, error):
    print(f"WebSocket error: {error}")
    st.session_state.ws_connected = False

def on_close(ws, close_status_code, close_msg):
    st.session_state.ws_connected = False
    print(f"WebSocket connection closed: {close_status_code} {close_msg}")
    # Attempt to reconnect
    time.sleep(2)
    connect_websocket()

def on_open(ws):
    st.session_state.ws_connected = True
    print("WebSocket connection established")

def connect_websocket():
    """Connect to the WebSocket server"""
    ws_url = f"{WEBSOCKET_URL}{st.session_state.session_id}"
    
    try:
        ws = websocket.WebSocketApp(
            ws_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )
        
        wst = threading.Thread(target=ws.run_forever)
        wst.daemon = True
        wst.start()
        
        # Wait a moment to confirm connection
        time.sleep(1)
        return ws
    except Exception as e:
        print(f"Error connecting to WebSocket: {e}")
        return None

def send_task(task_text):
    """Send a task to the agent"""
    try:
        # First try WebSocket if connected
        if st.session_state.ws_connected:
            ws_data = {
                "type": "run_task",
                "task": task_text
            }
            # In a production app, you would send this via the WebSocket
            
        # Always use HTTP endpoint as reliable method
        response = requests.post(
            f"{API_URL}/run_task",
            json={
                "task": task_text,
                "session_id": st.session_state.session_id
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            task_id = data.get("task_id")
            st.session_state.current_task_id = task_id
            st.session_state.agent_busy = True
            st.session_state.messages.append({"role": "user", "content": task_text})
            return True
        else:
            st.error(f"Error submitting task: {response.status_code}")
            return False
            
    except Exception as e:
        st.error(f"Error submitting task: {e}")
        return False

def submit_user_input(input_text, request_id):
    """Submit user input in response to an agent request"""
    try:
        # In a production app, you could send this via the WebSocket
        response = requests.post(
            f"{API_URL}/submit_input",
            json={
                "session_id": st.session_state.session_id,
                "request_id": request_id,
                "input_text": input_text
            }
        )
        
        if response.status_code == 200:
            # Add user's response to messages
            st.session_state.messages.append({"role": "user", "content": input_text})
            
            # Clear the current prompt
            st.session_state.current_prompt = None
            st.session_state.current_request_id = None
            return True
        else:
            st.error(f"Error submitting input: {response.status_code}")
            return False
    except Exception as e:
        st.error(f"Error submitting input: {e}")
        return False

# Connect to WebSocket when the app starts
if not st.session_state.ws_connected:
    ws = connect_websocket()

# App UI
st.title("Web Automation Agent")

# Connection status indicator
col1, col2 = st.columns([6, 1])
with col2:
    if st.session_state.ws_connected:
        st.success("Connected")
    else:
        st.error("Disconnected")
        if st.button("Reconnect"):
            ws = connect_websocket()
            if st.session_state.ws_connected:
                st.success("Reconnected!")
                st.rerun()

# Single input element for both task and responses
with st.container():
    # Display chat messages
    st.subheader("Conversation")
    chat_container = st.container()
    
    with chat_container:
        for message in st.session_state.messages:
            role = message["role"]
            content = message["content"]
            
            if role == "agent":
                st.info(f"🤖 **Agent**: {content}")
            elif role == "user":
                st.write(f"👤 **You**: {content}")
            elif role == "system":
                st.warning(content)
                
    # Single input area for both task and responses
    with st.form(key="input_form", clear_on_submit=True):
        if st.session_state.current_prompt:
            placeholder_text = f"Respond to: {st.session_state.current_prompt}"
            input_label = "Your response"
            button_text = "Submit Response"
        else:
            placeholder_text = "Enter a task for the agent..."
            input_label = "Task or response"
            button_text = "Send" if not st.session_state.agent_busy else "Agent is busy..."
        
        user_input = st.text_area(input_label, placeholder=placeholder_text, key="user_text_input")
        submit_button = st.form_submit_button(button_text, disabled=st.session_state.agent_busy and not st.session_state.current_prompt)
        
        if submit_button and user_input:
            if st.session_state.current_prompt and st.session_state.current_request_id:
                # Submit response to agent's prompt
                success = submit_user_input(user_input, st.session_state.current_request_id)
                if success:
                    st.rerun()
            elif not st.session_state.agent_busy:
                # Submit new task
                success = send_task(user_input)
                if success:
                    st.rerun()

# Screenshot carousel
if st.session_state.screenshots:
    st.subheader("Screenshots")
    
    # Create columns for the carousel navigation
    col1, col2, col3 = st.columns([1, 10, 1])
    
    # Previous button
    with col1:
        if st.button("←") and st.session_state.current_screenshot_index > 0:
            st.session_state.current_screenshot_index -= 1
            st.rerun()
    
    # Current screenshot display
    with col2:
        current_index = st.session_state.current_screenshot_index
        if 0 <= current_index < len(st.session_state.screenshots):
            screenshot = st.session_state.screenshots[current_index]
            try:
                st.image(
                    screenshot["image"], 
                    caption=f"Step {screenshot['step']} - {screenshot['timestamp']}", 
                    use_column_width=True
                )
                # Display screenshot position
                st.caption(f"Screenshot {current_index + 1} of {len(st.session_state.screenshots)}")
            except Exception as e:
                st.error(f"Error displaying screenshot: {e}")
    
    # Next button
    with col3:
        if st.button("→") and st.session_state.current_screenshot_index < len(st.session_state.screenshots) - 1:
            st.session_state.current_screenshot_index += 1
            st.rerun()
else:
    st.info("No screenshots available yet. Submit a task to get started.")