import os
import sys
import asyncio
import logging
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from browser_use import Agent, Browser, BrowserConfig, Controller, ActionResult
from browser_use.browser.context import BrowserContextConfig, BrowserContext
from Agents import custom_controllers
from Utils.prompts import MySystemPrompt
from Utils.stealth_browser.CustomBrowser import StealthBrowser, StealthBrowserConfig
from Utils.stealth_browser.CustomBrowserContext import ExtendedContext
# from Utils.CustomBrowserContext import ExtendedBrowserContext
# from Agents.custom_controllers.Interrup_controller import get_human_in_loop, HumanInput
from Agents.custom_controllers.ScreenShot_controller import on_step_screenshot
# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-001",
    temperature=0,
    api_key=GOOGLE_API_KEY,
    timeout=None,
    max_retries=2,
)

# browser_config = BrowserConfig(headless=False,
#                                disable_security=True)

# context_config = BrowserContextConfig(
#     cookies_file="./browser-data/Cookies/cookies.json",
#     wait_for_network_idle_page_load_time=3.0,
#     browser_window_size={'width': 900, 'height': 750},
#     locale='en-US',
#     user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36',
#     highlight_elements=False,
#     viewport_expansion=500,
# )

# Create Browser and Context objects
# browser = Browser(config=browser_config)
# config = StealthBrowserConfig(
#             headless=False,
#             locale="en-US",
#             timezone_id="America/New_York",
#             viewport={"width": 1920, "height": 1080},
#             minimum_wait_page_load_time=1.0

browser_config = BrowserConfig(
    chrome_instance_path="C:\Program Files\Google\Chrome\Application\chrome.exe",
    
)
#         )
browser =  Browser(config=browser_config)
context = BrowserContext(browser=browser)
# context = ExtendedContext(
#     browser=browser
# )

# context = ExtendedBrowserContext(
#     browser=browser, 
#     config=context_config,
#     screenshot_dir="agent_screenshots",  # Explicit directory
#     screenshot_interval=2.5,             # Take a screenshot every 1.5 seconds
#     transmit=False, 
#     debug_level=logging.WARNING  # For more verbose logging while debugging
# )


# registry = ControllerRegistry()
# registry.register_action(name = "human_in_loop",
#                                   description="This tool is for taking input from the user, you must provide question to ask the user.",
#                                   param_model=HumanInput,
#                                   handler=get_human_in_loop
#                                   )

# custom_controller = registry.get_controller()
# custom_controller = Controller()



async def run_search(task1: str):
    try:
        # Initialize context
        # await context.initialize()
        # context = await browser.new_context()
        # Create and run first agent
        agent1 : Agent = Agent(
            browser_context= context,
            task=task1,
            system_prompt_class=MySystemPrompt,
            llm=llm,
            register_new_step_callback = on_step_screenshot,
        )
        
        logger.info("Running first task...")
        history1 = await agent1.run()
        
        # # Create and run second agent
        # logger.info("Running second task...")
        # agent2 = Agent(
        #     browser_context=context,
        #     task=task2,
        #     system_prompt_class=MySystemPrompt,
        #     llm=llm
        # )
        
        # history2 = await agent2.run()
        
        # Process resultsc 

        
        logger.info("Tasks completed")
        return history1
        
    except Exception as e:
        logger.error(f"Error during task execution: {str(e)}")
        raise
    finally:
        try:
            # Ensure context and browser cleanup
            # await context.close()
            await browser.close()
        except Exception as cleanup_error:
            logger.error(f"Error during cleanup: {str(cleanup_error)}")

def main():
    # On Windows, set the event loop policy to ProactorEventLoopPolicy which supports subprocesses
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    try:
        # Get user inputs
        task1 = input("Input Task 1: ").strip()
        # task2 = input("Input Task 2: ").strip()
        
        # if not task1 or not task2:
        #     raise ValueError("Tasks cannot be empty")
        
        # Create new event loop and run tasks
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        history = loop.run_until_complete(run_search(task1))
        
        # Print results
        print("Results from Task 1- >Extracted content :", history.extracted_content())
        print("Results from Task 1:", history)
        # print("Results from Task 2:", errors2)
        
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
    finally:
        try:
            loop.close()
        except Exception as loop_close_error:
            logger.error(f"Error closing event loop: {str(loop_close_error)}")

if __name__ == "__main__":
    main()