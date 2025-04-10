from langchain_google_genai import ChatGoogleGenerativeAI
from browser_use import Agent, Browser, BrowserConfig
from browser_use.browser.context import BrowserContextConfig, BrowserContext
import os
from dotenv import load_dotenv
import asyncio
from Agents import custom_controllers
from Agents.custom_controllers.base_controller import ControllerRegistry
from Agents.custom_controllers.ScreenShot_controller import TakeScreenshotParams, take_screenshot
from Agents.prompts import MySystemPrompt
from Utils.CustomBrowser import ExtendedBrowser
from Utils.CustomBrowserContext import ExtendedBrowserContext
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
import logging
# print(GOOGLE_API_KEY)

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-001",
    temperature=0,
    api_key= GOOGLE_API_KEY,
    timeout=None,
    max_retries=2,
)

browser_config = BrowserConfig(headless=False)

context_config = BrowserContextConfig(
    cookies_file="./browser-data/Cookies/cookies.json",
    wait_for_network_idle_page_load_time=3.0,
    browser_window_size={'width': 1280, 'height': 1100},
    locale='en-US',
    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36',
    highlight_elements=True,
    viewport_expansion=500,
)

browser = Browser(config=browser_config)
context = ExtendedBrowserContext(
    browser=browser, 
    config=context_config,
    screenshot_dir="agent_screenshots",  # Explicit directory
    capture_events=True,
    debug_level=logging.DEBUG  # For more verbose logging while debugging
)

# Initialize the context BEFORE creating the agent
 

# base_controller = ControllerRegistry()
# base_controller.register_action(name = "screenshot_action",
#                                 description="This function is for taking screen shots",
#                                 param_model=TakeScreenshotParams,
#                                 handler=take_screenshot)
# custom_controller = base_controller.get_controller()


async def run_search(_task :str):
    await context.initialize() 
    agent = Agent(
		browser_context=context,
		task=_task,
        # controller=custom_controller,
        system_prompt_class=MySystemPrompt,
		llm=llm)
    
    try:
        history = await agent.run()
        print(history.errors())
        await context.close()
    except Exception as e:
        await context.close()
        raise e
    # await context.close()
    
 
def main():
    task = input("Input Task : ")
    if not isinstance(task,str):
        task = str(task)
    asyncio.run(run_search(task))
    

main()