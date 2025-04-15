from enum import auto
from wsgiref.util import application_uri
from Agents.custom_controllers.User_info_controller import get_user_info, ModelPrompt
from Agents.Browser_Agent import BrowserAgentHandler
from Agents.main_agent import AutoAgent, AutoAgentState
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from browser_use import BrowserConfig
from browser_use.browser.context import BrowserContextConfig
import os 
import asyncio
from langgraph.checkpoint.memory import InMemorySaver
from Agents.custom_controllers.base_controller import ControllerRegistry
from Utils.websocket_manager import ws_manager, WebSocketMessage
import json

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize language models
google_llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-001",
    temperature=0,
    api_key=GOOGLE_API_KEY,
    timeout=None,
    max_retries=2,
)

openai_llm = ChatOpenAI(
    model = "gpt-4o-mini-2024-07-18",
    api_key=OPENAI_API_KEY,
)

llm_dict = {"google": google_llm, "openai": openai_llm}

# Configure browser settings
browser_config = BrowserConfig(headless=False,
                            disable_security=True)

context_config = BrowserContextConfig(
    cookies_file="./browser-data/Cookies/cookies.json",
    wait_for_network_idle_page_load_time=3.0,
    browser_window_size={'width': 500, 'height': 350},
    locale='en-US',
    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36', 
    highlight_elements=True,
    viewport_expansion=500,
)

# Set up controller registry
registry = ControllerRegistry()

registry.register_action(name="user_info_helper",
                       description="This method should be firstly used for getting the required info if not found",
                       handler=get_user_info,  # Use WebSocket version
                       param_model=ModelPrompt
                       )

controller = registry.get_controller()

# Dictionary to store browser agents for each session
browser_agents = {}

# Dictionary to store auto agents for each session
auto_agents = {}

def get_or_create_agents(session_id):
    """Get or create browser and auto agents for a session"""
    if session_id not in browser_agents:
        # Create new browser agent
        browser_agent = BrowserAgentHandler(
            llm_dict=llm_dict,
            browser_config=browser_config,
            context_config=context_config,
            custom_controller=controller,
            use_planner_model=True,
            planner_model="google"
        )
        browser_agents[session_id] = browser_agent
        
        # Create new auto agent
        auto_agent = AutoAgent(
            llm_dict=llm_dict,
            fallback_llm="google",
            browser_agent=browser_agent,
            verbose=True,
        )
        auto_agents[session_id] = auto_agent
    
    return auto_agents[session_id], browser_agents[session_id]

class AgentProgress:
    """Class to track agent progress and send updates"""
    def __init__(self, session_id, send_updates_func):
        self.session_id = session_id
        self.send_updates = send_updates_func
        self.step = 0
        
    async def update(self, message, status="running", step_increment=True):
        if step_increment:
            self.step += 1
        
        await self.send_updates({
            "type": "agent_update",
            "content": {
                "step": self.step,
                "message": message,
                "status": status
            }
        })

async def run_agent_task(task, session_id, send_updates):
    """Run agent task and send updates to client"""
    auto_agent, browser_agent = get_or_create_agents(session_id)
    progress = AgentProgress(session_id, send_updates)
    
    try:
        # Send initial message
        await progress.update("Agent started processing your task...", step_increment=False)
        
        # You could also ask for additional information before starting
        # For example:
        # user_preference = await ws_manager.request_user_input(
        #     "Would you like me to use Google or OpenAI for this task?", 
        #     session_id
        # )
        
        # Run the agent
        await progress.update("Initializing agent...")
        response: AutoAgentState = await auto_agent.run(user_task=task, context_id=session_id)
        
        # Process and send the response
        await progress.update("Task completed, preparing results...")
        
        # Convert complex objects to string representation if needed
        result_data = {}
        if hasattr(response, "dict"):
            try:
                result_data = response.dict()
            except:
                result_data = {"result": str(response)}
        else:
            result_data = {"result": str(response)}
            
        result = {
            "type": "result",
            "content": {
                "message": "Task completed",
                "status": "completed",
                "result": result_data
            }
        }
        await send_updates(result)
        
    except Exception as e:
        # Send error message
        error_msg = {
            "type": "error",
            "content": {
                "message": f"Error occurred: {str(e)}",
                "status": "error"
            }
        }
        await send_updates(error_msg)
        raise e
    
    finally:
        # Closing message before browser cleanup
        await progress.update("Cleaning up browser resources...", status="cleaning")
        
        # Close browser contexts after a delay
        await asyncio.sleep(5)
        await browser_agent.close_all()
        
        # Final completion message
        await progress.update("Session completed and resources released", status="completed")

async def cleanup_session(session_id):
    """Clean up resources for a session"""
    if session_id in browser_agents:
        await browser_agents[session_id].close_all()
        del browser_agents[session_id]
    
    if session_id in auto_agents:
        del auto_agents[session_id]

# Direct execution for testing
async def test_agent(task: str):
    session_id = "test_session"
    
    async def print_update(message):
        print(f"UPDATE: {message}")
    
    try:
        await run_agent_task(task, session_id, print_update)
    finally:
        await cleanup_session(session_id)

if __name__ == "__main__":
    query = input("Enter Task that you want to perform: ")
    asyncio.run(test_agent(query))