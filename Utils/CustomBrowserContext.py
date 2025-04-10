from datetime import datetime
import os
import logging
import asyncio
from typing import Optional, Dict, Any

from browser_use.browser.context import BrowserContext, BrowserContextConfig, BrowserContextState
from playwright.async_api import ElementHandle, Page

# Set up detailed logging
logger = logging.getLogger(__name__)

class ExtendedBrowserContext(BrowserContext):
    """
    A class that extends BrowserContext to add automatic screenshot capabilities.
    Inherits all base functionality while adding screenshot features.
    
    Last Updated: 2025-04-10 01:25:10 UTC
    Author: iamansin
    """
    
    def __init__(
        self,
        browser,
        config: BrowserContextConfig | None = None,
        state: Optional[BrowserContextState] = None,
        screenshot_dir: Optional[str] = "screenshot-dir",
        capture_events: bool = False,
        debug_level: int = logging.INFO
    ):
        """
        Initialize ExtendedBrowserContext with additional screenshot capabilities.
        
        Args:
            browser: The browser instance
            config: Browser context configuration
            state: Browser context state
            screenshot_dir: Directory to store screenshots
            capture_events: Whether to enable automatic event capturing
            debug_level: Logging level for screenshot operations
        """
        # Set up logging for this instance
        self._setup_logging(debug_level)
        
        logger.info("Initializing ExtendedBrowserContext")

        # Initialize parent BrowserContext
        super().__init__(browser, config, state)
        
        # Initialize screenshot-specific attributes
        self.screenshot_dir = screenshot_dir
        self.capture_events = capture_events
        self._screenshot_count = 0
        self._listeners_initialized = False
        self.session = None  # Will be initialized in initialize()

        logger.info(f"Screenshot settings - Directory: {screenshot_dir}, Capture events: {capture_events}")

        if screenshot_dir:
            # Create screenshot directory if it doesn't exist
            try:
                os.makedirs(screenshot_dir, exist_ok=True)
                logger.info(f"📸 Screenshot directory created/confirmed: {screenshot_dir}")
            except Exception as e:
                logger.error(f"❌ Failed to create screenshot directory: {str(e)}")
    
    def _setup_logging(self, level):
        """Set up logging with appropriate formatting"""
        # Configure logger if not already configured
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(levelname)s - [%(name)s] - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        logger.setLevel(level)
        logger.info("Logger configured for ExtendedBrowserContext")
    
    async def initialize(self):
        """Initialize the context and set up event listeners"""
        logger.info("Beginning context initialization")
        
        try:
            # Call parent initialization to set up session
            await self._initialize_session()
            logger.info("Parent context initialization completed")
            
            # Setup event listeners if not already done
            if self.capture_events and not self._listeners_initialized:
                await self._setup_event_listeners()
            
            logger.info("Context initialization completed successfully")
        except Exception as e:
            logger.error(f"❌ Context initialization failed: {str(e)}")
            raise
        
    async def _setup_event_listeners(self):
        """Set up event listeners for automatic screenshots"""
        logger.info("Setting up page event listeners")
        
        try:
            # Initialize session if not already done
            if not self.session:
                await self._initialize_session()
                
            if not self.session or not self.session.context:
                logger.warning("Context not available for event listeners setup")
                return
            
            # Add listeners to all pages
            for page in self.session.context.pages:
                logger.info(f"Adding event listeners to page: {page.url}")
                
                # Define event handlers
                async def on_load():
                    logger.debug("Page load event detected")
                    await self._capture_event_screenshot("page_load")
                
                async def on_dom_content_loaded():
                    logger.debug("DOM content loaded event detected")
                    await self._capture_event_screenshot("dom_content_loaded")
                
                async def on_popup(popup):
                    logger.debug("Popup detected")
                    await self._capture_event_screenshot("popup_opened")
                
                async def on_dialog(dialog):
                    logger.debug(f"Dialog detected: {dialog.type}")
                    await self._capture_event_screenshot(f"dialog_{dialog.type}")
                
                async def on_console(msg):
                    if msg.type == "error":
                        logger.debug("Console error detected")
                        await self._capture_event_screenshot("console_error")
                
                async def on_pageerror(error):
                    logger.debug("Page error detected")
                    await self._capture_event_screenshot("page_error")
                
                async def on_request(request):
                    if request.resource_type == "document":
                        logger.debug(f"Main document request: {request.url}")
                        await self._capture_event_screenshot("page_request")
                
                async def on_response(response):
                    if response.request.resource_type == "document":
                        logger.debug(f"Main document response: {response.url}, status: {response.status}")
                        if response.status >= 400:
                            await self._capture_event_screenshot(f"error_response_{response.status}")
                
                # Add all event listeners
                page.on("load", lambda: asyncio.ensure_future(on_load()))
                page.on("domcontentloaded", lambda: asyncio.ensure_future(on_dom_content_loaded()))
                page.on("popup", lambda popup: asyncio.ensure_future(on_popup(popup)))
                page.on("dialog", lambda dialog: asyncio.ensure_future(on_dialog(dialog)))
                page.on("console", lambda msg: asyncio.ensure_future(on_console(msg)))
                page.on("pageerror", lambda error: asyncio.ensure_future(on_pageerror(error)))
                page.on("request", lambda req: asyncio.ensure_future(on_request(req)))
                page.on("response", lambda res: asyncio.ensure_future(on_response(res)))
                
            self._listeners_initialized = True
            logger.info("Event listeners setup completed")
        except Exception as e:
            logger.error(f"❌ Failed to set up event listeners: {str(e)}")

    async def capture_screenshot(self, name: str, full_page: bool = False, element: Optional[ElementHandle] = None) -> Optional[str]:
        """
        Capture a screenshot and save it to the screenshot directory.
        
        Args:
            name: Base name for the screenshot file
            full_page: Whether to capture the full page or just viewport (default: False = viewport only)
            element: Optional element to highlight in the screenshot
            
        Returns:
            Path to the saved screenshot file or None if failed
        """
        logger.info(f"Capture screenshot requested: {name} (full_page: {full_page})")
        
        if not self.screenshot_dir:
            logger.warning("Screenshot directory not specified, skipping screenshot")
            return None

        try:
            # Get the current page
            page = await super().get_current_page()
            if not page:
                logger.error("Cannot capture screenshot: No active page available")
                return None
            
            # Generate unique filename with timestamp and counter
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            self._screenshot_count += 1
            filename = f"{name}_{timestamp}_{self._screenshot_count:03d}.png"
            filepath = os.path.join(self.screenshot_dir, filename)
            
            logger.debug(f"Screenshot will be saved to: {filepath}")
            
            # Handle element highlighting
            highlighted = False
            original_styles = {}
            
            if element:
                try:
                    # Store original styles and apply highlighting
                    original_styles = await element.evaluate("""el => {
                        return {
                            outline: el.style.outline,
                            boxShadow: el.style.boxShadow,
                            backgroundColor: el.style.backgroundColor
                        };
                    }""")
                    
                    await element.evaluate("""el => {
                        el.style.outline = '2px solid red';
                        el.style.boxShadow = '0 0 10px rgba(255,0,0,0.5)';
                        el.style.backgroundColor = 'rgba(255,0,0,0.1)';
                    }""")
                    highlighted = True
                    logger.debug("Element highlighted for screenshot")
                except Exception as e:
                    logger.warning(f"Failed to highlight element: {str(e)}")

            # Take screenshot with retry logic
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                try:
                    screenshot_options: Dict[str, Any] = {
                        "path": filepath,
                        "animations": "disabled",
                    }
                    
                    # Only set full_page to True if explicitly requested
                    if full_page:
                        screenshot_options["full_page"] = True
                    
                    await page.screenshot(**screenshot_options)
                    
                    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                        logger.info(f"📸 Screenshot captured successfully: {filepath}")
                        break
                    else:
                        logger.warning(f"Screenshot file missing or empty (attempt {attempt}/{max_attempts})")
                        if attempt == max_attempts:
                            return None
                except Exception as e:
                    logger.warning(f"Screenshot attempt {attempt} failed: {str(e)}")
                    if attempt == max_attempts:
                        return None
                    await asyncio.sleep(0.5)

            # Restore original element styles
            if highlighted and element:
                try:
                    await element.evaluate("""(el, styles) => {
                        el.style.outline = styles.outline;
                        el.style.boxShadow = styles.boxShadow;
                        el.style.backgroundColor = styles.backgroundColor;
                    }""", original_styles)
                    logger.debug("Element styles restored after screenshot")
                except Exception as e:
                    logger.warning(f"Failed to restore element styles: {str(e)}")

            return filepath

        except Exception as e:
            logger.error(f"❌ Failed to capture screenshot '{name}': {str(e)}")
            return None

    async def _capture_event_screenshot(self, event_name: str, element: Optional[ElementHandle] = None):
        """Internal method to capture event-specific screenshots."""
        logger.debug(f"Event triggered: {event_name}")
        
        if not self.capture_events:
            logger.debug(f"Event screenshot skipped (capture_events disabled): {event_name}")
            return
            
        if not self.screenshot_dir:
            logger.debug(f"Event screenshot skipped (no directory): {event_name}")
            return
        
        try:
            # Use default viewport-only screenshot for events
            filepath = await self.capture_screenshot(f"event_{event_name}", full_page=False, element=element)
            if filepath:
                logger.debug(f"Event screenshot captured: {event_name} -> {filepath}")
            else:
                logger.warning(f"Event screenshot failed: {event_name}")
        except Exception as e:
            logger.error(f"❌ Event screenshot error for '{event_name}': {str(e)}")

    # Override parent class methods to add screenshot capabilities
    
    # async def navigate_to(self, url: str, max_retries: int = 3):
    #     """Enhanced navigation with automatic screenshot capture, extended timeout, and retries."""
    #     logger.info(f"Navigating to URL: {url}")
        
    #     if self.capture_events:
    #         await self._capture_event_screenshot("pre_navigation")
        
    #     retry_count = 0
    #     last_error = None
        
    #     while retry_count < max_retries:
    #         try:
    #             # Get the current page
    #             page = await self.get_current_page()
                
    #             # Configure navigation options
    #             navigation_options = {
    #                 'timeout': 60000,  # 60 seconds timeout
    #                 'wait_until': 'networkidle',
    #                 'referer': ''
    #             }
                
    #             # Perform navigation
    #             await page.goto(url, **navigation_options)
    #             logger.info(f"Navigation completed: {url}")
                
    #             if self.capture_events:
    #                 await asyncio.sleep(0.5)
    #                 await self._capture_event_screenshot("post_navigation")
                
    #             return  # Success, exit the function
                
    #         except Exception as e:
    #             last_error = e
    #             retry_count += 1
    #             logger.warning(f"Navigation attempt {retry_count} failed: {str(e)}")
                
    #             if retry_count < max_retries:
    #                 # Wait before retrying, using exponential backoff
    #                 await asyncio.sleep(2 ** retry_count)
                
    #             if self.capture_events:
    #                 await self._capture_event_screenshot(f"navigation_error_attempt_{retry_count}")
        
    #     # If we get here, all retries failed
    #     logger.error(f"❌ Navigation failed after {max_retries} attempts: {str(last_error)}")
    #     raise last_error