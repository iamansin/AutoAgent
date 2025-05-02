from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import asyncio
import uuid
import os
import base64
from datetime import datetime
import logging
from contextlib import asynccontextmanager
import traceback
import sys

# Import your agent modules
try:
    from Agents.Browser_Agent import BrowserAgentHandler
    from Agents.main_agent import AutoAgent, AutoAgentState
    from dotenv import load_dotenv
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_openai import ChatOpenAI
    from Utils.stealth_browser.CustomBrowser import StealthBrowser
    from browser_use.browser.context import BrowserContextConfig
    from browser_use import BrowserConfig
    from browser_use.agent.views import AgentHistoryList, AgentHistory, AgentState
    from Agents.custom_controllers.base_controller import ControllerRegistry
except ImportError as e:
    print(f"Failed to import required modules: {str(e)}")
    sys.exit(1)

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log")
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables with validation
try:
    load_dotenv()
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    if not GOOGLE_API_KEY:
        logger.error("GOOGLE_API_KEY environment variable not set")
        raise ValueError("GOOGLE_API_KEY environment variable not set")
    
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY environment variable not set")
        raise ValueError("OPENAI_API_KEY environment variable not set")
        
except Exception as e:
    logger.critical(f"Failed to load environment variables: {str(e)}")
    sys.exit(1)

# Global agents (initialize once)
auto_agent = None
browser_agent = None
active_tasks = {}

# WebSocket message class
class WebSocketMessage:
    def __init__(self, type: str, content: Dict[str, Any], session_id: str):
        self.type = type
        self.content = content
        self.session_id = session_id
        
    def to_dict(self):
        return {
            "type": self.type,
            "content": self.content,
            "session_id": self.session_id
        }

# User input model
class UserInput(BaseModel):
    session_id: str
    request_id: str
    input_text: str

# Task model
class TaskRequest(BaseModel):
    task: str
    session_id: str

# WebSocket manager
class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.pending_requests: Dict[str, asyncio.Future] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        try:
            await websocket.accept()
            self.active_connections[session_id] = websocket
            logger.info(f"WebSocket connection established for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to establish WebSocket connection for session {session_id}: {str(e)}")
            logger.error(traceback.format_exc())
            # Re-raise to handle in the calling function
            raise
        
    def disconnect(self, session_id: str):
        try:
            if session_id in self.active_connections:
                del self.active_connections[session_id]
                logger.info(f"WebSocket connection closed for session {session_id}")
                
                # Clean up any pending requests for this session
                requests_to_remove = [req_id for req_id, future in self.pending_requests.items() 
                                    if not future.done() and future.session_id == session_id]
                for req_id in requests_to_remove:
                    try:
                        self.pending_requests[req_id].cancel()
                        del self.pending_requests[req_id]
                    except Exception as cleanup_err:
                        logger.warning(f"Error cleaning up request {req_id}: {str(cleanup_err)}")
        except Exception as e:
            logger.error(f"Error during disconnect for session {session_id}: {str(e)}")
            logger.error(traceback.format_exc())
        
    async def send_message(self, message: WebSocketMessage, session_id: str):
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_json(message.to_dict())
                logger.debug(f"Message sent to session {session_id}: {message.type}")
            except RuntimeError as e:
                logger.error(f"RuntimeError sending message to session {session_id}: {str(e)}")
                self.disconnect(session_id)
            except ConnectionError as e:
                logger.error(f"ConnectionError sending message to session {session_id}: {str(e)}")
                self.disconnect(session_id)
            except Exception as e:
                logger.error(f"Error sending message to session {session_id}: {str(e)}")
                logger.error(traceback.format_exc())
                # Connection might be broken, clean up
                self.disconnect(session_id)
        else:
            logger.warning(f"Attempted to send message to non-existent session {session_id}")
            
    async def send_screenshot(self, session_id: str, screenshot_data: str, step: int):
        if session_id in self.active_connections:
            try:
                message = WebSocketMessage(
                    type="screenshot",
                    content={
                        "image": screenshot_data,
                        "step": step,
                        "timestamp": datetime.utcnow().isoformat()
                    },
                    session_id=session_id
                )
                await self.send_message(message, session_id)
                logger.debug(f"Screenshot sent to session {session_id} for step {step}")
            except Exception as e:
                logger.error(f"Error sending screenshot to session {session_id}: {str(e)}")
                logger.error(traceback.format_exc())
        else:
            logger.warning(f"Attempted to send screenshot to non-existent session {session_id}")
    
    async def request_user_input(self, prompt: str, session_id: str, request_id: Optional[str] = None) -> str:
        """Request input from user and wait for response"""
        if session_id not in self.active_connections:
            error_msg = f"No active connection for session {session_id}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        if request_id is None:
            request_id = str(uuid.uuid4())
            
        try:
            # Create a future to get the result later
            future = asyncio.get_running_loop().create_future()
            future.session_id = session_id  # Add session_id attribute for cleanup
            self.pending_requests[request_id] = future
            
            # Send the prompt to the client
            message = WebSocketMessage(
                type="input_request",
                content={
                    "prompt": prompt,
                    "request_id": request_id
                },
                session_id=session_id
            )
            await self.send_message(message, session_id)
            logger.info(f"Input request sent with ID {request_id} for session {session_id}")
            
            # Wait for the response
            try:
                response = await asyncio.wait_for(future, timeout=300)  # 5 minute timeout
                logger.info(f"Received response for request {request_id} from session {session_id}")
                return response
            except asyncio.TimeoutError:
                # Handle timeout
                logger.warning(f"Request {request_id} for session {session_id} timed out after 300 seconds")
                if request_id in self.pending_requests:
                    del self.pending_requests[request_id]
                return ""
            except asyncio.CancelledError:
                # Handle cancellation
                logger.info(f"Request {request_id} for session {session_id} was cancelled")
                if request_id in self.pending_requests:
                    del self.pending_requests[request_id]
                raise
        except Exception as e:
            logger.error(f"Error in request_user_input for session {session_id}: {str(e)}")
            logger.error(traceback.format_exc())
            if request_id in self.pending_requests:
                del self.pending_requests[request_id]
            raise
        
    def resolve_request(self, request_id: str, response: str):
        """Resolve a pending request with the user's response"""
        try:
            if request_id in self.pending_requests:
                future = self.pending_requests[request_id]
                if not future.done():
                    future.set_result(response)
                    logger.debug(f"Request {request_id} resolved successfully")
                del self.pending_requests[request_id]
            else:
                logger.warning(f"Received response for unknown request ID: {request_id}")
        except Exception as e:
            logger.error(f"Error resolving request {request_id}: {str(e)}")
            logger.error(traceback.format_exc())

# Global WebSocket manager
ws_manager = WebSocketManager()

# Setup agent with detailed error handling
def setup_agents():
    try:
        # Import here to avoid circular imports
        from Agents.custom_controllers.User_info_controller import get_user_info, ModelPrompt
        global auto_agent, browser_agent
        
        logger.info("Starting agent initialization...")
        
        # LLM configuration with error handling
        try:
            logger.info("Initializing Google LLM...")
            google_llm = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash-001",
                temperature=0,
                api_key=GOOGLE_API_KEY,
                timeout=None,
                max_retries=3,
            )
            logger.info("Google LLM initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Google LLM: {str(e)}")
            logger.error(traceback.format_exc())
            raise ValueError(f"Google LLM initialization failed: {str(e)}")

        try:
            logger.info("Initializing OpenAI LLM...")
            openai_llm = ChatOpenAI(
                model="gpt-4o-mini-2024-07-18",
                api_key=OPENAI_API_KEY,
                max_retries=3,
            )
            logger.info("OpenAI LLM initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI LLM: {str(e)}")
            logger.error(traceback.format_exc())
            raise ValueError(f"OpenAI LLM initialization failed: {str(e)}")

        llm_dict = {"google": google_llm, "openai": openai_llm}
        
        # Browser configuration
        try:
            logger.info("Setting up browser configurations...")
            browser_config = BrowserConfig(headless=True)
            
            context_config = BrowserContextConfig(
                cookies_file="./browser-data/Cookies/cookies.json",
                wait_for_network_idle_page_load_time=3.0,
                browser_window_size={'width': 1920, 'height': 1080},
                locale='en-US',
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36',
                highlight_elements=False,
                viewport_expansion=500,
            )
            logger.info("Browser configurations created successfully")
        except Exception as e:
            logger.error(f"Failed to set up browser configurations: {str(e)}")
            logger.error(traceback.format_exc())
            raise ValueError(f"Browser configuration failed: {str(e)}")

        # Register custom controllers
        try:
            logger.info("Registering custom controllers...")
            registry = ControllerRegistry()
            registry.register_action(
                name="user_info_helper",
                description="This method should be firstly used for getting the required info if not found",
                handler=get_user_info,
                param_model=ModelPrompt
            )
            controller = registry.get_controller()
            logger.info("Custom controllers registered successfully")
        except Exception as e:
            logger.error(f"Failed to register custom controllers: {str(e)}")
            logger.error(traceback.format_exc())
            raise ValueError(f"Controller registration failed: {str(e)}")
        
        # Initialize browser agent
        try:
            logger.info("Initializing browser agent...")
            browser_agent = BrowserAgentHandler(
                ws_manager=ws_manager,
                llm_dict=llm_dict,
                browser_config=browser_config,
                context_config=context_config,
                custom_controller=controller,
                use_planner_model=False,
                planner_model="google",
                use_agent_state=True,
                transmit_ss=True,
            )
            logger.info("Browser agent initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize browser agent: {str(e)}")
            logger.error(traceback.format_exc())
            raise ValueError(f"Browser agent initialization failed: {str(e)}")

        # Initialize auto agent
        try:
            logger.info("Initializing auto agent...")
            auto_agent = AutoAgent(
                llm_dict=llm_dict,
                fallback_llm="google",
                browser_agent=browser_agent,
                verbose=False,
            )
            logger.info("Auto agent initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize auto agent: {str(e)}")
            logger.error(traceback.format_exc())
            raise ValueError(f"Auto agent initialization failed: {str(e)}")
        
        logger.info("All agents successfully initialized")
        return True
    except Exception as e:
        logger.critical(f"Failed to initialize agents: {str(e)}")
        logger.critical(traceback.format_exc())
        return False

# Create FastAPI context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    global auto_agent, browser_agent
    
    # Setup code before the app starts
    logger.info("Starting FastAPI application")
    try:
        success = setup_agents()
        if not success:
            logger.error("Failed to initialize agents. Application may not function correctly.")
    except Exception as e:
        logger.critical(f"Critical error during application startup: {str(e)}")
        logger.critical(traceback.format_exc())
    
    yield
    
    # Cleanup code after the app stops
    logger.info("Shutting down FastAPI application")
    
    # Cancel all active tasks
    for task_id, task in active_tasks.items():
        try:
            if not task.done():
                logger.info(f"Cancelling active task {task_id}")
                task.cancel()
        except Exception as e:
            logger.error(f"Error cancelling task {task_id}: {str(e)}")
    
    # Close all browser instances
    if browser_agent:
        try:
            logger.info("Closing browser agent instances")
            await browser_agent.close_all()
            logger.info("Browser agent instances closed successfully")
        except Exception as e:
            logger.error(f"Error closing browser agent: {str(e)}")
            logger.error(traceback.format_exc())

# Initialize FastAPI app
app = FastAPI(lifespan=lifespan)

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    connection_established = False
    try:
        # Connect to websocket with error handling
        await ws_manager.connect(websocket, session_id)
        connection_established = True
        
        while True:
            try:
                data = await websocket.receive_json()
                logger.debug(f"Received WebSocket message from session {session_id}: {data['type']}")
                
                if data["type"] == "input_response":
                    try:
                        request_id = data["request_id"]
                        input_text = data["input"]
                        ws_manager.resolve_request(request_id, input_text)
                    except KeyError as e:
                        logger.error(f"Invalid input_response format: {str(e)}")
                        await websocket.send_json({
                            "type": "error", 
                            "message": f"Invalid input format: {str(e)}"
                        })
                        
                elif data["type"] == "run_task":
                    try:
                        # Launch task in background
                        task = data["task"]
                        task_id = str(uuid.uuid4())
                        logger.info(f"Creating task {task_id} for session {session_id}")
                        
                        background_task = asyncio.create_task(run_agent_task(task, session_id, task_id))
                        active_tasks[task_id] = background_task
                        
                        # Clean up completed task when done
                        background_task.add_done_callback(
                            lambda t, tid=task_id: active_tasks.pop(tid, None)
                        )
                        
                        # Acknowledge task receipt
                        await websocket.send_json({"type": "task_received", "task": task, "task_id": task_id})
                    except KeyError as e:
                        logger.error(f"Invalid run_task format: {str(e)}")
                        await websocket.send_json({
                            "type": "error", 
                            "message": f"Invalid task format: {str(e)}"
                        })
                    except Exception as e:
                        logger.error(f"Error creating task: {str(e)}")
                        logger.error(traceback.format_exc())
                        await websocket.send_json({
                            "type": "error", 
                            "message": f"Failed to create task: {str(e)}"
                        })
                else:
                    logger.warning(f"Unknown message type received: {data['type']}")
                    await websocket.send_json({
                        "type": "error", 
                        "message": f"Unknown message type: {data['type']}"
                    })
                    
            except asyncio.CancelledError:
                logger.info(f"WebSocket connection for session {session_id} cancelled")
                break
                
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON received from session {session_id}: {str(e)}")
                try:
                    await websocket.send_json({
                        "type": "error", 
                        "message": "Invalid JSON format"
                    })
                except:
                    break
                
            except Exception as e:
                logger.error(f"Error processing WebSocket message for session {session_id}: {str(e)}")
                logger.error(traceback.format_exc())
                try:
                    await websocket.send_json({
                        "type": "error", 
                        "message": f"Internal error: {str(e)}"
                    })
                except:
                    break
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"Error in websocket handler for session {session_id}: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        if connection_established:
            ws_manager.disconnect(session_id)
            logger.info(f"WebSocket connection closed for session {session_id}")

@app.post("/submit_input")
async def submit_input(user_input: UserInput):
    """Endpoint for submitting user input via HTTP (fallback)"""
    logger.info(f"Received input submission for request {user_input.request_id}, session {user_input.session_id}")
    try:
        if not user_input.request_id:
            error_msg = "Missing request_id in input submission"
            logger.error(error_msg)
            raise HTTPException(status_code=400, detail=error_msg)
            
        if not user_input.session_id:
            error_msg = "Missing session_id in input submission"
            logger.error(error_msg)
            raise HTTPException(status_code=400, detail=error_msg)
            
        ws_manager.resolve_request(user_input.request_id, user_input.input_text)
        return {"status": "success"}
    except ValueError as e:
        logger.error(f"Value error in input submission: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing input submission: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/run_task")
async def run_task(task_request: TaskRequest, background_tasks: BackgroundTasks):
    """Endpoint to run a task - can be called from Streamlit"""
    logger.info(f"Received task request: {task_request.task} for session {task_request.session_id}")
    try:
        # Validate inputs
        if not task_request.task:
            error_msg = "Task cannot be empty"
            logger.error(error_msg)
            raise HTTPException(status_code=400, detail=error_msg)
            
        if not task_request.session_id:
            error_msg = "Session ID cannot be empty"
            logger.error(error_msg)
            raise HTTPException(status_code=400, detail=error_msg)
        
        # Check if global agent is initialized
        if auto_agent is None:
            error_msg = "Auto agent not initialized"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
            
        if browser_agent is None:
            error_msg = "Browser agent not initialized"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
        
        task_id = str(uuid.uuid4())
        background_task = asyncio.create_task(run_agent_task(task_request.task, task_request.session_id, task_id))
        active_tasks[task_id] = background_task
        
        # Clean up completed task when done
        background_task.add_done_callback(
            lambda t, tid=task_id: active_tasks.pop(tid, None)
        )
        
        logger.info(f"Task {task_id} started successfully for session {task_request.session_id}")
        return {"status": "success", "message": "Task started", "task_id": task_id}
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error starting task: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to start task: {str(e)}")

async def run_agent_task(task: str, session_id: str, task_id: str):
    """Run the agent task using the global agent instance"""
    global auto_agent
    
    try:
        # Verify agents are initialized
        if auto_agent is None:
            raise ValueError("Auto agent not initialized properly")
            
        if browser_agent is None:
            raise ValueError("Browser agent not initialized properly")
        
        # Send task started message
        try:
            message = WebSocketMessage(
                type="task_status",
                content={"status": "started", "task": task, "task_id": task_id},
                session_id=session_id
            )
            await ws_manager.send_message(message, session_id)
        except Exception as msg_err:
            logger.error(f"Failed to send task started message: {str(msg_err)}")
            # Continue execution even if message sending fails
        
        # Load sensitive data with proper error handling
        try:
            gmail = os.getenv("GMAIL")
            gmail_password = os.getenv("GMAIL_PASSWORD")
            
            if not gmail:
                logger.warning("GMAIL environment variable not set")
                
            if not gmail_password:
                logger.warning("GMAIL_PASSWORD environment variable not set")
                
            sensitive_data = {
                "gmail": gmail,
                "password": gmail_password
            }
        except Exception as env_err:
            logger.error(f"Error loading sensitive data: {str(env_err)}")
            logger.error(traceback.format_exc())
            sensitive_data = {}  # Proceed with empty sensitive data
        
        # Run the agent with timing
        logger.info(f"Running agent for task: {task} (session_id: {session_id}, task_id: {task_id})")
        start_time = datetime.now()
        
        try:
            response: AutoAgentState = await auto_agent.run(
                user_task=task,
                sensitive_data=sensitive_data,
                context_id=session_id
            )
            
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"Agent execution completed in {execution_time:.2f} seconds")
            
        except asyncio.CancelledError:
            logger.info(f"Agent execution cancelled after {(datetime.now() - start_time).total_seconds():.2f} seconds")
            raise
        except Exception as agent_err:
            logger.error(f"Agent execution failed: {str(agent_err)}")
            logger.error(traceback.format_exc())
            raise ValueError(f"Agent execution failed: {str(agent_err)}")
        
        # Send task completed message
        try:
            message = WebSocketMessage(
                type="task_status",
                content={
                    "status": "completed", 
                    "task": task,
                    "task_id": task_id,
                },
                session_id=session_id
            )
            await ws_manager.send_message(message, session_id)
        except Exception as msg_err:
            logger.error(f"Failed to send task completion message: {str(msg_err)}")
            # Continue execution even if message sending fails
        
        logger.info(f"Task completed for session {session_id}, task_id: {task_id}")
        
    except asyncio.CancelledError:
        logger.info(f"Task cancelled for session {session_id}, task_id: {task_id}")
        try:
            message = WebSocketMessage(
                type="task_status",
                content={"status": "cancelled", "task": task, "task_id": task_id},
                session_id=session_id
            )
            await ws_manager.send_message(message, session_id)
        except Exception as msg_err:
            logger.error(f"Failed to send task cancellation message: {str(msg_err)}")
        raise
        
    except Exception as e:
        logger.error(f"Error running agent task: {str(e)}")
        logger.error(traceback.format_exc())
        # Send error message with specific error details
        error_details = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc()
        }
        try:
            message = WebSocketMessage(
                type="task_status",
                content={
                    "status": "error", 
                    "message": str(e),
                    "details": error_details,
                    "task": task,
                    "task_id": task_id
                },
                session_id=session_id
            )
            await ws_manager.send_message(message, session_id)
        except Exception as msg_err:
            logger.error(f"Failed to send error message: {str(msg_err)}")

if __name__ == "__main__":
    # Add missing import
    import json
    import uvicorn
    
    # Check if essential environment variables are set before starting
    missing_vars = []
    if not os.getenv("GOOGLE_API_KEY"):
        missing_vars.append("GOOGLE_API_KEY")
    if not os.getenv("OPENAI_API_KEY"):
        missing_vars.append("OPENAI_API_KEY")
        
    if missing_vars:
        logger.critical(f"Missing required environment variables: {', '.join(missing_vars)}")
        print(f"ERROR: Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)
        
    try:
        uvicorn.run(app, host="0.0.0.0", port=8000)
    except Exception as e:
        logger.critical(f"Failed to start server: {str(e)}")
        logger.critical(traceback.format_exc())
        sys.exit(1)