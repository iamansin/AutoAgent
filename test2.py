import asyncio
import logging
import sys
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import BrowserContextConfig
from Utils.CustomBrowserContext import ExtendedBrowserContext  # Import the enhanced context

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("screenshot_test")

async def test_screenshots():
    logger.info("Starting screenshot test")
    
    try:
        # Create browser with default config
        browser = Browser()
        logger.info("Browser instance created")
        
        # Create extended context with explicit screenshot settings
        context = ExtendedBrowserContext(
            browser=browser,
            config=BrowserContextConfig(),
            screenshot_dir="test_screenshots",
            capture_events=True,  # Important: Enable automatic screenshots
            debug_level=logging.DEBUG  # Set to DEBUG for verbose logging
        )
        logger.info("Extended context created")
        
        # Initialize the context
        await context.initialize()
        logger.info("Context initialized")
        
        # Navigate to a test page
        logger.info("Navigating to example.com")
        await context.navigate_to("https://www.google.com")
        
        # Wait for page to fully load
        logger.info("Waiting for page to load")
        await asyncio.sleep(3)
        
        # Explicitly take a screenshot to test basic functionality
        # logger.info("Taking explicit screenshot")
        # screenshot_path = await context.capture_screenshot("manual_test")
        # logger.info(f"Screenshot saved to: {screenshot_path}")
        
        # # Try clicking on a link (should trigger click screenshots)
        # try:
        #     logger.info("Attempting to click on a link")
        #     await context._click_element_node("a")
        #     logger.info("Click completed")
        #     await asyncio.sleep(3)  # Wait for page to load after click
        # except Exception as e:
        #     logger.error(f"Click operation failed: {e}")
        
        # # Final explicit screenshot
        # logger.info("Taking final screenshot")
        # final_path = await context.capture_screenshot("final_state")
        # logger.info(f"Final screenshot saved to: {final_path}")
        
        # Close browser
        logger.info("Closing browser")
        await browser.close()
        
        logger.info("Test completed successfully")
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        raise

if __name__ == "__main__":
    logger.info("Running screenshot test script")
    asyncio.run(test_screenshots())