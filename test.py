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
# from Agents.custom_controllers.GoogleAuth_controller import get_user_info
import json
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

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

llm_dict = {"google" : google_llm, "openai" : openai_llm}
browser_config = BrowserConfig(headless=False,
                               disable_security=True)

context_config = BrowserContextConfig(
    cookies_file="./browser-data/Cookies/cookies.json",
    wait_for_network_idle_page_load_time=3.0,
    browser_window_size={'width': 500, 'height': 350},
    locale='en-US',
    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36',
    highlight_elements=False,
    viewport_expansion=500,
)

registry = ControllerRegistry()

registry.register_action(name="user_info_helper",
                         description="This method should be firstly used for getting the required info if not found",
                         handler= get_user_info,
                         param_model=ModelPrompt
                         )

controller = registry.get_controller()
browser_agent = BrowserAgentHandler(
    llm_dict= llm_dict,
    browser_config= browser_config,
    context_config=context_config,
    custom_controller=controller,
    use_planner_model=True,
    planner_model="google"
)

autoagent = AutoAgent(
    llm_dict=llm_dict,
    fallback_llm="google",
    browser_agent=browser_agent,
    verbose=True,
)

async def test_agent(task:str):
    
    try:
        response : AutoAgentState= await autoagent.run(user_task=task, context_id = "test112")
        print(response)
        
    except Exception as e:
        raise e
    
    finally:
        print("now waiting before closing context.")
        await asyncio.sleep(5)
        await browser_agent.close_all()
        
    
    
query =  input("Enter Task that you want to perform: ")
asyncio.run(test_agent(query))