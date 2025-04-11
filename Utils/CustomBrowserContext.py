from datetime import datetime
import os
import logging
import asyncio
from typing import Optional, Dict, Any
import base64

from browser_use.browser.context import BrowserContext, BrowserContextConfig, BrowserContextState
from playwright.async_api import ElementHandle, Page

# Set up logging
logger = logging.getLogger(__name__)

class ExtendedBrowserContext(BrowserContext):
    """
    A simplified class that extends BrowserContext to take screenshots at regular intervals.
    Includes improved error handling for timeout issues.
    
    Last Updated: 2025-04-11
    """
    
    def __init__(
        self,
        browser,
        config: BrowserContextConfig | None = None,
        state: Optional[BrowserContextState] = None,
        screenshot_dir: Optional[str] = "screenshot-dir",
        debug_level: int = logging.INFO,
        screenshot_interval: float = 1.0,  # Time between screenshots in seconds
        transmit: bool = False,  # Whether to transmit via Socket.IO instead of saving
        socketio_client = None,  # Socket.IO client instance
        max_retries: int = 3,  # Maximum screenshot retries
        screenshot_timeout: int = 10000  # Screenshot timeout in ms
    ):
        """
        Initialize ExtendedBrowserContext with time-based screenshot capabilities.
        
        Args:
            browser: The browser instance
            config: Browser context configuration
            state: Browser context state
            screenshot_dir: Directory to store screenshots (used only if transmit=False)
            debug_level: Logging level for screenshot operations
            screenshot_interval: Time between screenshots in seconds
            transmit: Whether to transmit screenshots via Socket.IO instead of saving to disk
            socketio_client: Socket.IO client instance (required if transmit=True)
            max_retries: Maximum number of retries for failed screenshots
            screenshot_timeout: Timeout for screenshot operations in milliseconds
        """
        # Set up logging
        self._setup_logging(debug_level)
        
        logger.info("Initializing ExtendedBrowserContext with timeout handling")

        # Initialize parent BrowserContext
        super().__init__(browser, config, state)
        
        # Initialize screenshot settings
        self.screenshot_dir = screenshot_dir
        self.screenshot_interval = screenshot_interval
        self.transmit = transmit
        self.socketio_client = socketio_client
        self._screenshot_count = 0
        self.session = None  # Will be initialized in initialize()
        self._screenshot_task = None
        self.max_retries = max_retries
        self.screenshot_timeout = screenshot_timeout
        self._last_error_time = None
        self._consecutive_errors = 0

        # Validate configuration
        if self.transmit and not self.socketio_client:
            logger.warning("Transmit mode enabled but no Socket.IO client provided!")
        
        if not self.transmit and screenshot_dir:
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
        """Initialize the context and start screenshot timer"""
        logger.info("Beginning context initialization")
        
        try:
            # Call parent initialization
            await super()._initialize_session()
            logger.info("Browser context initialization completed")
            
            # Start the screenshot timer
            await self._start_screenshot_timer()
            
            logger.info("Context initialization completed successfully")
        except Exception as e:
            logger.error(f"❌ Context initialization failed: {str(e)}")
            raise
    
    
    async def _start_screenshot_timer(self):
        """Start the timer to take screenshots at regular intervals"""
        logger.info(f"Starting screenshot timer with interval: {self.screenshot_interval}s")
        
        # Cancel existing task if it exists
        if self._screenshot_task and not self._screenshot_task.done():
            self._screenshot_task.cancel()
        
        # Create new periodic screenshot task
        self._screenshot_task = asyncio.create_task(self._periodic_screenshot())
    
    async def _periodic_screenshot(self):
        """Take screenshots at regular intervals with adaptive error handling"""
        try:
            while True:
                # Check if we should adjust interval due to errors
                adjusted_interval = self._get_adjusted_interval()
                
                # Take screenshot
                await self._take_screenshot()
                
                # If successful, reset error counter
                self._consecutive_errors = 0
                
                # Wait for next interval
                await asyncio.sleep(adjusted_interval)
                
        except asyncio.CancelledError:
            logger.info("Screenshot timer cancelled")
        except Exception as e:
            logger.error(f"❌ Error in screenshot timer: {str(e)}")
            # Restart timer after a delay
            await asyncio.sleep(5)
            self._screenshot_task = asyncio.create_task(self._periodic_screenshot())
    
    def _get_adjusted_interval(self):
        """Get adjusted interval based on error history (implements backoff)"""
        if self._consecutive_errors == 0:
            return self.screenshot_interval
        
        # Add backoff factor based on consecutive errors (max 5x normal interval)
        backoff_factor = min(self._consecutive_errors, 5)
        return self.screenshot_interval * backoff_factor
    
    async def _is_page_stable(self, page):
        """Check if the page is in a stable state for screenshots"""
        try:
            # Check network activity
            is_stable = await page.evaluate("""() => {
                // Check if page is still loading
                if (document.readyState !== 'complete') return false;
                
                // Check if there are pending network requests
                const performance = window.performance;
                if (!performance || !performance.getEntriesByType) return true;
                
                const resources = performance.getEntriesByType('resource');
                const incomplete = resources.filter(r => !r.responseEnd);
                return incomplete.length === 0;
            }""")
            
            return is_stable
        except Exception:
            # If we can't determine, assume it's stable
            return True
    
    async def _take_screenshot(self):
        """Take a screenshot and either save it or transmit it"""
        try:
            # Get the current page
            page = await super().get_current_page()
            if not page:
                logger.warning("Cannot take screenshot: No active page available")
                return
            
            # Check if page is in a reasonable state for screenshots
            is_stable = await self._is_page_stable(page)
            if not is_stable:
                logger.debug("Skipping screenshot: Page is still loading")
                return
            
            # Take screenshot
            if self.transmit:
                # For transmitting, capture to memory
                success = await self._capture_and_transmit_screenshot(page)
                if success:
                    logger.info(f"📡 Screenshot #{self._screenshot_count} transmitted")
            else:
                # For saving, capture to file
                filepath = await self._save_screenshot(page)
                if filepath:
                    logger.info(f"📸 Screenshot saved to: {filepath}")
        except Exception as e:
            logger.error(f"❌ Screenshot error: {str(e)}")
            self._consecutive_errors += 1
            self._last_error_time = datetime.utcnow()
    
    async def _save_screenshot(self, page):
        """Save screenshot to disk with optimized parameters and retry logic"""
        if not self.screenshot_dir:
            return None
        
        # Generate filename with timestamp
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        self._screenshot_count += 1
        filename = f"screenshot_{timestamp}_{self._screenshot_count:03d}.png"
        filepath = os.path.join(self.screenshot_dir, filename)
        
        # Try different screenshot strategies with retry
        for attempt in range(1, self.max_retries + 1):
            try:
                # Adjust parameters based on retry attempt
                if attempt == 1:
                    # First try with standard parameters
                    logger.debug("Taking screenshot with standard parameters")
                    await page.screenshot(
                        path=filepath,
                        timeout=self.screenshot_timeout,
                        animations="disabled"
                    )
                elif attempt == 2:
                    # Second try with reduced quality/options
                    logger.debug("Taking screenshot with reduced parameters")
                    await page.screenshot(
                        path=filepath,
                        timeout=int(self.screenshot_timeout * 0.7),  # Reduce timeout
                        animations="disabled",
                        type="jpeg",
                        quality=80
                    )
                else:
                    # Final try with minimal options
                    logger.debug("Taking screenshot with minimal parameters")
                    minimal_path = filepath.replace(".png", "_minimal.jpg")
                    await page.screenshot(
                        path=minimal_path,
                        timeout=5000,  # Very short timeout
                        type="jpeg",
                        quality=60,
                        animations="disabled"
                    )
                    if os.path.exists(minimal_path):
                        return minimal_path
                
                # Check if screenshot was saved successfully
                if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                    logger.debug(f"Screenshot successful on attempt {attempt}")
                    return filepath
                else:
                    logger.warning(f"Screenshot file empty or missing (attempt {attempt})")
            
            except Exception as e:
                error_type = type(e).__name__
                logger.warning(f"Screenshot attempt {attempt} failed: {error_type}: {str(e)}")
                
                # Short delay between retries
                if attempt < self.max_retries:
                    delay = attempt * 0.5  # Increasing delay with each retry
                    await asyncio.sleep(delay)
        
        # If we got here, all attempts failed
        logger.error("All screenshot attempts failed")
        return None
    
    async def _capture_and_transmit_screenshot(self, page):
        """Capture screenshot to memory and transmit via Socket.IO with retry logic"""
        if not self.socketio_client:
            logger.warning("Cannot transmit: No Socket.IO client available")
            return False
        
        # Try different screenshot strategies with retry
        for attempt in range(1, self.max_retries + 1):
            try:
                # Adjust parameters based on retry attempt
                if attempt == 1:
                    # First try with standard parameters
                    screenshot_bytes = await page.screenshot(
                        timeout=self.screenshot_timeout,
                        animations="disabled"
                    )
                elif attempt == 2:
                    # Second try with reduced quality/options
                    screenshot_bytes = await page.screenshot(
                        timeout=int(self.screenshot_timeout * 0.7),
                        animations="disabled",
                        type="jpeg",
                        quality=80
                    )
                else:
                    # Final try with minimal options
                    screenshot_bytes = await page.screenshot(
                        timeout=5000,
                        type="jpeg",
                        quality=60,
                        animations="disabled"
                    )
                
                # If we got bytes, transmit them
                if screenshot_bytes and len(screenshot_bytes) > 0:
                    # Convert bytes to base64 for transmission
                    encoded = base64.b64encode(screenshot_bytes).decode('utf-8')
                    
                    # Get page URL for metadata
                    page_url = page.url
                    
                    # Create timestamp
                    timestamp = datetime.utcnow().isoformat()
                    
                    # Prepare data packet
                    self._screenshot_count += 1
                    data = {
                        'image': encoded,
                        'timestamp': timestamp,
                        'url': page_url,
                        'count': self._screenshot_count,
                        'attempt': attempt
                    }
                    
                    # Transmit via Socket.IO
                    self.socketio_client.emit('screenshot', data)
                    logger.debug(f"Screenshot transmitted on attempt {attempt}")
                    return True
            
            except Exception as e:
                error_type = type(e).__name__
                logger.warning(f"Screenshot transmission attempt {attempt} failed: {error_type}: {str(e)}")
                
                # Short delay between retries
                if attempt < self.max_retries:
                    delay = attempt * 0.5  # Increasing delay with each retry
                    await asyncio.sleep(delay)
        
        # If we got here, all attempts failed
        logger.error("All screenshot transmission attempts failed")
        return False
    
    async def stop(self):
        """Stop the screenshot timer and clean up"""
        logger.info("Stopping screenshot timer")
        
        # Cancel screenshot task
        if self._screenshot_task and not self._screenshot_task.done():
            self._screenshot_task.cancel()
            try:
                await self._screenshot_task
            except asyncio.CancelledError as e:
                print(f"There was some error while closing the BrowserContext : {str(e)}")
                pass
            
        # Call parent cleanup
        await super().close()
        
        logger.info("Screenshot timer stopped")
    
    async def close(self):
        """Override to ensure screenshot timer is stopped during cleanup"""
        await self.stop()