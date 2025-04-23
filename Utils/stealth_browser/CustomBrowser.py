from math import e
from playwright.async_api import async_playwright
from playwright.async_api import Browser as PlaywrightBrowser
from browser_use import BrowserConfig, Browser
import asyncio
import random
import logging
from proto import Field
from pydantic import BaseModel,Field
from typing import Optional, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)



class StealthBrowser(Browser):
    def __init__(self, config : BrowserConfig):
        super().__init__()
        # self.playwright = None
        # self.playwright_browser = None
        self.context = None
        self.page = None
        self.config = config

    async def _init(self):
        try:
            self.playwright = await async_playwright().start()
            
            # Launch browser with stealth configurations
            self.playwright_browser= await self.playwright.chromium.launch(
                headless=self.config.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-site-isolation-trials',
                    '--disable-features=UserAgentClientHint',
                    '--no-sandbox',
                    '--disable-webgl',
                    '--disable-threaded-scrolling',
                    '--disable-threaded-animation',
                    '--disable-extensions'
                ]
            )
        except Exception as e:
            raise e 
        
    async def get_playwright_browser(self) -> PlaywrightBrowser:
        if self.playwright_browser is None:
            await self._init()
        
        return self.playwright_browser
    
    async def create_stealth_context(self):
        """Create a stealth browser context with anti-detection measures"""
            # Create context with stealth configurations
            
        try:
            self.context = await self.playwright_browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                device_scale_factor=1,
                has_touch=False,
                is_mobile=False,
                locale='en-US',
                timezone_id='America/New_York',
                permissions=['geolocation'],
                java_script_enabled=True,
                bypass_csp=True,
                geolocation={'latitude': 40.7128, 'longitude': -74.0060},
            )

            # Add script to modify navigator properties
            await self.context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        {
                            name: 'Chrome PDF Plugin',
                            description: 'Portable Document Format',
                            filename: 'internal-pdf-viewer'
                        }
                    ]
                });
            """)

            return self.context

        except Exception as e:
            logger.error(f"Error creating stealth context: {str(e)}")
            await self.cleanup()
            raise

    async def random_delay(self, min_seconds: float = 1, max_seconds: float = 3):
        """Add random delay to mimic human behavior"""
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)
        return delay

    async def human_like_typing(self, element, text: str):
        """Type text with random delays between keystrokes"""
        for char in text:
            await element.type(char, delay=random.randint(50, 150))
            await self.random_delay(0.1, 0.3)

    async def login_to_gmail(self, email: str, password: str):
        """Perform Gmail login with stealth measures"""
        try:
            self.page = await self.context.new_page()
            
            # Navigate to Gmail
            logger.info("Navigating to Gmail...")
            await self.page.goto('https://gmail.com', wait_until='networkidle')
            await self.random_delay()

            # Handle email input
            logger.info("Entering email...")
            email_input = await self.page.wait_for_selector('input[type="email"]')
            await self.human_like_typing(email_input, email)
            await self.random_delay()
            
            # Click next after email
            await self.page.click('#identifierNext')
            await self.random_delay(2, 4)

            # Handle password input
            logger.info("Entering password...")
            password_input = await self.page.wait_for_selector('input[type="password"]', timeout=5000)
            await self.human_like_typing(password_input, password)
            await self.random_delay()

            # Click next after password
            await self.page.click('#passwordNext')

            # Wait for Gmail to load
            logger.info("Waiting for Gmail to load...")
            await self.page.wait_for_selector('div[role="main"]', timeout=10000)
            logger.info("Successfully logged into Gmail")

            # Add additional wait time to ensure everything loads
            await self.random_delay(3, 5)

        except Exception as e:
            logger.error(f"Error during login: {str(e)}")
            raise

    async def cleanup(self):
        """Clean up browser resources"""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.playwright_browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

async def main():
    gmail_browser = GmailStealthBrowser()
    await gmail_browser.get_playwright_browser()
    try:
        # Create stealth context
        await gmail_browser.create_stealth_context()
        
        # Replace with your credentials
        email = "amanragu2002@gmail.com"
        password = "your-password"
        
        # Perform login
        await gmail_browser.login_to_gmail(email, password)
        
        # Keep the browser open for a while
        await asyncio.sleep(5)
        
    except Exception as e:
        logger.error(f"Main execution error: {str(e)}")
    finally:
        await gmail_browser.cleanup()

if __name__ == "__main__":
    asyncio.run(main())