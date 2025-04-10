
from typing import Dict, Optional, List, Any
import os
import json
from datetime import datetime
from playwright.async_api import async_playwright, Browser, Page, BrowserContext, Playwright, Error as PlaywrightError
from datetime import datetime
from typing import Optional, List, Callable, Any

from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from .CustomBrowserContext import ExtendedBrowserContext

class ExtendedBrowser(Browser):
    """
    Extended Browser class with automatic screenshot capabilities.
    Takes screenshots automatically at key interaction points.
    """

    def __init__(
        self,
        config: Optional[BrowserConfig] = None,
        screenshot_dir: str = "screenshots",
        capture_events: bool = True
    ):
        """
        Initialize the AutoScreenshotBrowser.
        
        Args:
            config: BrowserConfig for the browser
            screenshot_dir: Directory to store screenshots
            capture_events: Whether to enable automatic event capturing
        """
        super().__init__(config)
        self.screenshot_dir = screenshot_dir
        self.capture_events = capture_events
        self.screenshot_count = 0
        
        # Ensure screenshot directory exists
        os.makedirs(self.screenshot_dir, exist_ok=True)
    
    async def new_context(self, config: BrowserContextConfig | None = None) -> "ExtendedBrowserContext":
        """Create an auto-screenshot browser context"""
        # Use the parent class to create the original context
        original_context = await super().new_context(config=config or self.config.new_context_config)
        
        # Wrap the original context with our auto-screenshot context
        return ExtendedBrowserContext(
            original_context=original_context,
            browser=self,
            screenshot_dir=self.screenshot_dir,
            capture_events=self.capture_events
        )
    
    async def take_screenshot(self, event_name: str = "") -> str:
        """
        Take a screenshot of the current active page.
        
        Args:
            event_name: Optional event name to include in the filename
            
        Returns:
            Path to the saved screenshot file
        """
        try:
            # Get the browser instance
            browser = await self.get_playwright_browser()
            
            # Get all contexts
            contexts = browser.contexts
            if not contexts:
                return ""  # Silently return if no contexts available
            
            # Get the first context
            context = contexts[0]
            
            # Get all pages in the context
            pages = context.pages
            if not pages:
                return ""  # Silently return if no pages
            
            # Get the active page
            page = pages[0]
            
            # Generate filename
            self.screenshot_count += 1
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            event_part = f"_{event_name}" if event_name else ""
            filename = f"screenshot_{self.screenshot_count:04d}{event_part}_{timestamp}.png"
            
            # Create full path
            filepath = os.path.join(self.screenshot_dir, filename)
            
            # Take the screenshot
            await page.screenshot(path=filepath)
            
            return filepath
        except Exception as e:
            # Don't crash the main functionality if screenshots fail
            print(f"Screenshot failed: {str(e)}")
            return ""
