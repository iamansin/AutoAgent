
from langchain.prompts import PromptTemplate
from pydantic import Field, BaseModel
from sqlalchemy import true
from Agents.custom_controllers.User_info_controller import get_user_info, ModelPrompt
from Agents.Browser_Agent import BrowserAgentHandler
from Agents.main_agent import AutoAgent, AutoAgentState
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from Utils.stealth_browser.CustomBrowser import StealthBrowser
from browser_use.browser.context import BrowserContextConfig
from browser_use import BrowserConfig
from browser_use.agent.views import AgentHistoryList, AgentHistory, AgentState
import os 
import asyncio
from langgraph.checkpoint.memory import InMemorySaver
from Agents.custom_controllers.base_controller import ControllerRegistry
from typing_extensions import Dict, Optional
from browser_use import Browser
# from Agents.custom_controllers.GoogleAuth_controller import exit_current_context
# from Agents.custom_controllers.GoogleAuth_controller import get_user_info
import json
from textwrap import dedent
load_dotenv()
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

google_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-preview-04-17",
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
browser_config = BrowserConfig(headless=True)
#    chrome_instance_path=Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"))

context_config = BrowserContextConfig(
    cookies_file="./browser-data/Cookies/cookies.json",
    wait_for_network_idle_page_load_time=3.0,
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
    use_planner_model=False,
    planner_model="google",
    use_agent_state=True
)


browser = Browser(config=browser_config)
# autoagent = AutoAgent(
#     llm_dict=llm_dict,
#     fallback_llm="openai",
#     browser_agent=browser_agent,
#     verbose=False,
# )


# Instructions = dedent("""
# You must search for the form and then extract all the fields, their input type, fiels type (i.e. radio, dropdown etc.), field options if any from the provided form.
# You Must return the output as json format. Do not extract any information other than the form.""")

# go to this website and extract all the fields present in the provided form there. Extract all the fields, their types, data type they accepts in a proper strucutred json ouput. The url for the form is : "https://qavalidation.com/demo-form/".

async def test_agent(task:str):
    
    try:
        response = await browser_agent.run_task(
            context_id = "123",
            task = f"The task is : {task}",
            # browser = browser
        )
        # content = response.extracted_content()[-1]
    except Exception as e:
        raise e
    
    finally:
        print("now waiting before closing context.")
        await asyncio.sleep(5)
        await browser_agent.close_all()
        
    
    
query =  input("Enter Task that you want to perform: ")

    
asyncio.run(test_agent(query))
