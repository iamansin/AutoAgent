# from datetime import datetime
# import os
# import logging
# import asyncio
# from typing import Optional, Dict, Any, List, Set
# import hashlib
# from io import BytesIO

# from browser_use.browser.context import BrowserContext, BrowserContextConfig, BrowserContextState
# from playwright.async_api import ElementHandle, Page

# # Set up detailed logging
# logger = logging.getLogger(__name__)

# class ExtendedBrowserContext(BrowserContext):
#     """
#     A class that extends BrowserContext to add smart screenshot capabilities.
#     Takes screenshots only when meaningful visual changes occur or on important events.
    
#     Last Updated: 2025-04-11
#     Author: iamansin (improved)
#     """
    
#     def __init__(
#         self,
#         browser,
#         config: BrowserContextConfig | None = None,
#         state: Optional[BrowserContextState] = None,
#         screenshot_dir: Optional[str] = "screenshot-dir",
#         capture_events: bool = False,
#         debug_level: int = logging.INFO,
#         min_screenshot_interval: float = 1.0,  # Minimum seconds between screenshots
#         visual_change_threshold: float = 0.05,  # 5% change threshold
#         important_events: Optional[List[str]] = None  # List of important events to capture
#     ):
#         """
#         Initialize ExtendedBrowserContext with smart screenshot capabilities.
        
#         Args:
#             browser: The browser instance
#             config: Browser context configuration
#             state: Browser context state
#             screenshot_dir: Directory to store screenshots
#             capture_events: Whether to enable automatic event capturing
#             debug_level: Logging level for screenshot operations
#             min_screenshot_interval: Minimum time between screenshots in seconds
#             visual_change_threshold: Minimum visual difference required (0-1)
#             important_events: List of events to always capture regardless of visual change
#         """
#         # Set up logging for this instance
#         self._setup_logging(debug_level)
        
#         logger.info("Initializing ExtendedBrowserContext with smart screenshot capabilities")

#         # Initialize parent BrowserContext
#         super().__init__(browser, config, state)
        
#         # Initialize screenshot-specific attributes
#         self.screenshot_dir = screenshot_dir
#         self.capture_events = capture_events
#         self._screenshot_count = 0
#         self._listeners_initialized = False
#         self.session = None  # Will be initialized in initialize()
        
#         # Smart screenshot settings
#         self.min_screenshot_interval = min_screenshot_interval
#         self.visual_change_threshold = visual_change_threshold
#         self._last_screenshot_time = datetime.utcnow()
#         self._last_screenshot_hash = None
        
#         # Set default important events if none provided
#         if important_events is None:
#             self.important_events = {
#                 "page_error", 
#                 "error_response_404", 
#                 "error_response_500",
#                 "form_submit",
#                 "navigation_complete"
#             }
#         else:
#             self.important_events = set(important_events)

#         logger.info(f"Screenshot settings - Directory: {screenshot_dir}, "
#                    f"Capture events: {capture_events}, "
#                    f"Interval: {min_screenshot_interval}s, "
#                    f"Change threshold: {visual_change_threshold*100}%")

#         if screenshot_dir:
#             # Create screenshot directory if it doesn't exist
#             try:
#                 os.makedirs(screenshot_dir, exist_ok=True)
#                 logger.info(f"📸 Screenshot directory created/confirmed: {screenshot_dir}")
#             except Exception as e:
#                 logger.error(f"❌ Failed to create screenshot directory: {str(e)}")
    
#     def _setup_logging(self, level):
#         """Set up logging with appropriate formatting"""
#         # Configure logger if not already configured
#         if not logger.handlers:
#             handler = logging.StreamHandler()
#             formatter = logging.Formatter('%(levelname)s - [%(name)s] - %(message)s')
#             handler.setFormatter(formatter)
#             logger.addHandler(handler)
        
#         logger.setLevel(level)
#         logger.info("Logger configured for ExtendedBrowserContext")
    
#     async def initialize(self):
#         """Initialize the context and set up event listeners"""
#         logger.info("Beginning context initialization")
        
#         try:
#             # Call parent initialization to set up session
#             await super()._initialize_session()
#             logger.info("Parent context initialization completed")
            
#             # Setup event listeners if not already done
#             if self.capture_events and not self._listeners_initialized:
#                 await self._setup_event_listeners()
            
#             logger.info("Context initialization completed successfully")
#         except Exception as e:
#             logger.error(f"❌ Context initialization failed: {str(e)}")
#             raise

    
#     async def _setup_event_listeners(self):
#         """Set up event listeners for smart automatic screenshots"""
#         logger.info("Setting up page event listeners with smart detection")
        
#         try:
#             # Initialize session if not already done
#             # if not self.session:
#             #     await self._initialize_session()
                
#             if not self.session or not self.session.context:
#                 logger.warning("Context not available for event listeners setup")
#                 return
            
#             # Add listeners to all pages
#             for page in self.session.context.pages:
#                 logger.info(f"Adding smart event listeners to page: {page.url}")
                
#                 # Track navigation state to reduce duplicate screenshots
#                 page_state = {
#                     "navigating": False,
#                     "last_url": page.url,
#                     "form_submitted": False
#                 }
                
#                 # Define event handlers
#                 async def on_navigation_started(url):
#                     page_state["navigating"] = True
#                     page_state["last_url"] = url
#                     logger.debug(f"Navigation started to: {url}")
                
#                 async def on_navigation_finished():
#                     if page_state["navigating"]:
#                         page_state["navigating"] = False
#                         curr_url = page.url
#                         if curr_url != page_state["last_url"]:
#                             logger.debug(f"Navigation completed to: {curr_url}")
#                             await self._smart_capture_event_screenshot("navigation_complete")
#                             page_state["last_url"] = curr_url
                
#                 async def on_load():
#                     logger.debug("Page load event detected")
#                     # Already captured in navigation_complete if URL changed
#                     if not page_state["navigating"]:
#                         await self._smart_capture_event_screenshot("page_load")
                
#                 async def on_dom_content_loaded():
#                     logger.debug("DOM content loaded event detected")
#                     # Skip this - we'll capture on visible changes instead
                
#                 async def on_popup(popup):
#                     logger.debug("Popup detected")
#                     await self._smart_capture_event_screenshot("popup_opened")
                
#                 async def on_dialog(dialog):
#                     logger.debug(f"Dialog detected: {dialog.type}")
#                     await self._smart_capture_event_screenshot(f"dialog_{dialog.type}")
                
#                 async def on_console(msg):
#                     if msg.type == "error":
#                         logger.debug("Console error detected")
#                         await self._smart_capture_event_screenshot("console_error")
                
#                 async def on_pageerror(error):
#                     logger.debug("Page error detected")
#                     await self._smart_capture_event_screenshot("page_error")
                
#                 async def on_request(request):
#                     # Only track main frame document requests
#                     if request.resource_type == "document" and request.is_navigation_request():
#                         logger.debug(f"Main document request: {request.url}")
#                         on_navigation_started(request.url)
                
#                 async def on_response(response):
#                     # Only track main frame document responses
#                     if response.request.resource_type == "document" and response.request.is_navigation_request():
#                         logger.debug(f"Main document response: {response.url}, status: {response.status}")
#                         await on_navigation_finished()
#                         if response.status >= 400:
#                             await self._smart_capture_event_screenshot(f"error_response_{response.status}")
                
#                 # Track DOM mutations for potential visual changes
#                 await page.evaluate("""() => {
#                     window._lastMutation = Date.now();
                    
#                     // Create mutation observer to track DOM changes
#                     const observer = new MutationObserver(() => {
#                         window._lastMutation = Date.now();
#                     });
                    
#                     // Observe all changes to the DOM
#                     observer.observe(document.documentElement, {
#                         childList: true,
#                         subtree: true,
#                         attributes: true,
#                         characterData: true
#                     });
                    
#                     // Track form submissions
#                     document.addEventListener('submit', function(e) {
#                         window._formSubmitted = true;
#                         window._lastSubmit = Date.now();
#                     }, true);
                    
#                     // Track clicks that might cause visual changes
#                     document.addEventListener('click', function(e) {
#                         if (e.target && (
#                             e.target.tagName === 'BUTTON' || 
#                             e.target.tagName === 'A' ||
#                             e.target.tagName === 'INPUT' && e.target.type === 'checkbox' ||
#                             e.target.tagName === 'INPUT' && e.target.type === 'radio' ||
#                             e.target.closest('button') ||
#                             e.target.closest('a') ||
#                             e.target.closest('[role="button"]') ||
#                             e.target.closest('[aria-expanded]')
#                         )) {
#                             window._significantClick = true;
#                             window._lastClick = Date.now();
#                         }
#                     }, true);
#                 }""")
                
#                 # Set up interval to check for visual changes
#                 async def check_for_changes():
#                     try:
#                         status = await page.evaluate("""() => {
#                             const result = {
#                                 formSubmitted: window._formSubmitted || false,
#                                 significantClick: window._significantClick || false,
#                                 lastMutation: window._lastMutation || 0,
#                                 lastClick: window._lastClick || 0,
#                                 lastSubmit: window._lastSubmit || 0
#                             };
                            
#                             // Reset the flags
#                             window._formSubmitted = false;
#                             window._significantClick = false;
                            
#                             return result;
#                         }""")
                        
#                         # Check for form submission
#                         if status.get("formSubmitted"):
#                             logger.debug("Form submission detected")
#                             page_state["form_submitted"] = True
#                             await self._smart_capture_event_screenshot("form_submit")
                        
#                         # Check for significant click
#                         if status.get("significantClick"):
#                             # Only capture if it's been a while since the last screenshot
#                             now = datetime.utcnow()
#                             time_diff = (now - self._last_screenshot_time).total_seconds()
#                             if time_diff >= self.min_screenshot_interval:
#                                 logger.debug("Significant click detected, checking for visual change")
#                                 # Delay slightly to allow visual changes to render
#                                 await asyncio.sleep(0.3)
#                                 await self._smart_capture_if_changed("click_interaction")
                    
#                     except Exception as e:
#                         logger.warning(f"Error checking for DOM changes: {str(e)}")
                
#                 # Set up periodic check for visual changes
#                 async def start_change_monitoring():
#                     while True:
#                         try:
#                             if page.is_closed():
#                                 break
#                             await check_for_changes()
#                             await asyncio.sleep(0.5)  # Check every 500ms
#                         except Exception as e:
#                             logger.warning(f"Change monitoring error: {str(e)}")
#                             break
                
#                 # Start monitoring in background
#                 asyncio.create_task(start_change_monitoring())
                
#                 # Add event listeners
#                 page.on("load", lambda: asyncio.ensure_future(on_load()))
#                 page.on("domcontentloaded", lambda: asyncio.ensure_future(on_dom_content_loaded()))
#                 page.on("popup", lambda popup: asyncio.ensure_future(on_popup(popup)))
#                 page.on("dialog", lambda dialog: asyncio.ensure_future(on_dialog(dialog)))
#                 page.on("console", lambda msg: asyncio.ensure_future(on_console(msg)))
#                 page.on("pageerror", lambda error: asyncio.ensure_future(on_pageerror(error)))
#                 page.on("request", lambda req: asyncio.ensure_future(on_request(req)))
#                 page.on("response", lambda res: asyncio.ensure_future(on_response(res)))
                
#             self._listeners_initialized = True
#             logger.info("Smart event listeners setup completed")
#         except Exception as e:
#             logger.error(f"❌ Failed to set up event listeners: {str(e)}")

#     async def _smart_capture_event_screenshot(self, event_name: str, element: Optional[ElementHandle] = None):
#         """Intelligently decide whether to capture a screenshot based on event importance."""
#         logger.debug(f"Event triggered: {event_name}")
        
#         if not self.capture_events:
#             logger.debug(f"Event screenshot skipped (capture_events disabled): {event_name}")
#             return
            
#         if not self.screenshot_dir:
#             logger.debug(f"Event screenshot skipped (no directory): {event_name}")
#             return
        
#         # Check if this is an important event that should always be captured
#         is_important = event_name in self.important_events
        
#         # Check if enough time has passed since the last screenshot
#         now = datetime.utcnow()
#         time_diff = (now - self._last_screenshot_time).total_seconds()
#         time_threshold_met = time_diff >= self.min_screenshot_interval
        
#         if is_important or time_threshold_met:
#             if is_important:
#                 logger.debug(f"Taking screenshot due to important event: {event_name}")
#                 await self._capture_with_context(event_name, element)
#             else:
#                 # For non-important events, check for visual changes
#                 logger.debug(f"Checking if event caused visual change: {event_name}")
#                 await self._smart_capture_if_changed(event_name, element)
#         else:
#             logger.debug(f"Skipping screenshot for {event_name} (too soon after last capture)")
    
#     async def _smart_capture_if_changed(self, event_name: str, element: Optional[ElementHandle] = None):
#         """Capture screenshot only if visual content has changed significantly."""
#         try:
#             page = await super().get_current_page()
#             if not page:
#                 return
            
#             # Capture screenshot to memory for comparison
#             screenshot_bytes = await page.screenshot(full_page=False)
            
#             # Calculate visual hash
#             current_hash = self._calculate_visual_hash(screenshot_bytes)
            
#             # If this is the first screenshot or hash is different enough
#             if (self._last_screenshot_hash is None or 
#                 self._hash_difference(current_hash, self._last_screenshot_hash) > self.visual_change_threshold):
                
#                 logger.debug(f"Visual change detected for {event_name}, capturing screenshot")
                
#                 # Save the already captured screenshot
#                 timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
#                 self._screenshot_count += 1
#                 filename = f"{event_name}_{timestamp}_{self._screenshot_count:03d}.png"
#                 filepath = os.path.join(self.screenshot_dir, filename)
                
#                 with open(filepath, 'wb') as f:
#                     f.write(screenshot_bytes)
                
#                 # Update tracking variables
#                 self._last_screenshot_hash = current_hash
#                 self._last_screenshot_time = datetime.utcnow()
                
#                 logger.info(f"📸 Visual change screenshot captured: {filepath}")
#                 return filepath
#             else:
#                 logger.debug(f"No significant visual change for {event_name}, skipping screenshot")
#                 return None
                
#         except Exception as e:
#             logger.error(f"❌ Error in smart capture: {str(e)}")
#             return None
    
#     def _calculate_visual_hash(self, image_bytes):
#         """Calculate a perceptual hash of screenshot for comparison."""
#         # Simple hashing - for real perceptual hashing, consider using a library like ImageHash
#         return hashlib.md5(image_bytes).hexdigest()
    
#     def _hash_difference(self, hash1, hash2):
#         """Calculate normalized difference between two hashes."""
#         # For actual perceptual hash comparison, this would measure Hamming distance
#         # This is a simplified comparison that returns a value between 0 and 1
#         if hash1 == hash2:
#             return 0.0
#         else:
#             # Count differing characters between hexadecimal hashes
#             diff = sum(c1 != c2 for c1, c2 in zip(hash1, hash2))
#             # Normalize by hash length
#             return diff / len(hash1)
    
#     async def _capture_with_context(self, event_name: str, element: Optional[ElementHandle] = None):
#         """Capture screenshot with additional context info."""
#         try:
#             # Generate unique filename with timestamp and counter
#             timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
#             self._screenshot_count += 1
#             filename = f"{event_name}_{timestamp}_{self._screenshot_count:03d}.png"
#             filepath = os.path.join(self.screenshot_dir, filename)
            
#             # Take screenshot
#             path = await self.capture_screenshot(event_name, full_page=False, element=element)
            
#             if path:
#                 # Update tracking variables
#                 page = await super().get_current_page()
#                 if page:
#                     with open(path, 'rb') as f:
#                         self._last_screenshot_hash = self._calculate_visual_hash(f.read())
#                 self._last_screenshot_time = datetime.utcnow()
            
#             return path
#         except Exception as e:
#             logger.error(f"❌ Failed to capture context screenshot: {str(e)}")
#             return None

#     async def capture_screenshot(self, name: str, full_page: bool = False, element: Optional[ElementHandle] = None) -> Optional[str]:
#         """
#         Capture a screenshot and save it to the screenshot directory.
        
#         Args:
#             name: Base name for the screenshot file
#             full_page: Whether to capture the full page or just viewport
#             element: Optional element to highlight in the screenshot
            
#         Returns:
#             Path to the saved screenshot file or None if failed
#         """
#         logger.info(f"Capture screenshot requested: {name} (full_page: {full_page})")
        
#         if not self.screenshot_dir:
#             logger.warning("Screenshot directory not specified, skipping screenshot")
#             return None

#         try:
#             # Get the current page
#             page = await super().get_current_page()
#             if not page:
#                 logger.error("Cannot capture screenshot: No active page available")
#                 return None
            
#             # Generate unique filename with timestamp and counter
#             timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
#             self._screenshot_count += 1
#             filename = f"{name}_{timestamp}_{self._screenshot_count:03d}.png"
#             filepath = os.path.join(self.screenshot_dir, filename)
            
#             logger.debug(f"Screenshot will be saved to: {filepath}")
            
#             # Handle element highlighting
#             highlighted = False
#             original_styles = {}
            
#             if element:
#                 try:
#                     # Store original styles and apply highlighting
#                     original_styles = await element.evaluate("""el => {
#                         return {
#                             outline: el.style.outline,
#                             boxShadow: el.style.boxShadow,
#                             backgroundColor: el.style.backgroundColor
#                         };
#                     }""")
                    
#                     await element.evaluate("""el => {
#                         el.style.outline = '2px solid red';
#                         el.style.boxShadow = '0 0 10px rgba(255,0,0,0.5)';
#                         el.style.backgroundColor = 'rgba(255,0,0,0.1)';
#                     }""")
#                     highlighted = True
#                     logger.debug("Element highlighted for screenshot")
#                 except Exception as e:
#                     logger.warning(f"Failed to highlight element: {str(e)}")

#             # Take screenshot with retry logic
#             max_attempts = 3
#             for attempt in range(1, max_attempts + 1):
#                 try:
#                     screenshot_options: Dict[str, Any] = {
#                         "path": filepath,
#                         "animations": "disabled",
#                     }
                    
#                     # Only set full_page to True if explicitly requested
#                     if full_page:
#                         screenshot_options["full_page"] = True
                    
#                     await page.screenshot(**screenshot_options)
                    
#                     if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
#                         logger.info(f"📸 Screenshot captured successfully: {filepath}")
#                         # Update tracking variables
#                         self._last_screenshot_time = datetime.utcnow()
#                         with open(filepath, 'rb') as f:
#                             self._last_screenshot_hash = self._calculate_visual_hash(f.read())
#                         break
#                     else:
#                         logger.warning(f"Screenshot file missing or empty (attempt {attempt}/{max_attempts})")
#                         if attempt == max_attempts:
#                             return None
#                 except Exception as e:
#                     logger.warning(f"Screenshot attempt {attempt} failed: {str(e)}")
#                     if attempt == max_attempts:
#                         return None
#                     await asyncio.sleep(0.5)

#             # Restore original element styles
#             if highlighted and element:
#                 try:
#                     await element.evaluate("""(el, styles) => {
#                         el.style.outline = styles.outline;
#                         el.style.boxShadow = styles.boxShadow;
#                         el.style.backgroundColor = styles.backgroundColor;
#                     }""", original_styles)
#                     logger.debug("Element styles restored after screenshot")
#                 except Exception as e:
#                     logger.warning(f"Failed to restore element styles: {str(e)}")

#             return filepath

#         except Exception as e:
#             logger.error(f"❌ Failed to capture screenshot '{name}': {str(e)}")
#             return None