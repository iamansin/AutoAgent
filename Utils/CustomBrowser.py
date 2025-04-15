import random
import asyncio
from typing import Dict, Optional, List, Union, Tuple
from pydantic import BaseModel, Field, ConfigDict
from browser_use.browser.browser import Browser, BrowserConfig, BrowserContext
from playwright.async_api import Page, Playwright

class StealthBrowserConfig(BrowserConfig):
    """Extended configuration for StealthBrowser with stealth-specific settings"""
    
    # Define stealth browser arguments as a class constant
    STEALTH_ARGS: List[str] = [
        "--disable-blink-features=AutomationControlled",
        "--disable-features=IsolateOrigins,site-per-process",
        "--disable-site-isolation-trials",
        "--disable-web-security",
        "--disable-features=BlockInsecurePrivateNetworkRequests",
        "--disable-accelerated-2d-canvas",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--disable-breakpad",
        "--disable-component-extensions-with-background-pages",
        "--disable-hang-monitor",
        "--disable-ipc-flooding-protection",
        "--disable-popup-blocking",
        "--disable-prompt-on-repost",
        "--metrics-recording-only",
        "--no-first-run",
        "--password-store=basic",
        "--use-mock-keychain",
        "--force-webrtc-ip-handling-policy=disable-non-proxied-udp",
    ]

    def __init__(
        self,
        *,
        user_agent: Optional[str] = None,
        geolocation: Optional[Dict[str, float]] = None,
        locale: str = "en-US",
        timezone_id: str = "America/New_York",
        viewport: Optional[Dict[str, int]] = None,
        minimum_wait_page_load_time: float = 1.0,
        **kwargs
    ):
        # First call parent's init with base browser config parameters
        super().__init__(**kwargs)
        
        # Set stealth-specific attributes
        self.user_agent = user_agent
        self.geolocation = geolocation
        self.locale = locale
        self.timezone_id = timezone_id
        self.viewport = viewport or {"width": 1920, "height": 1080}
        self.minimum_wait_page_load_time = minimum_wait_page_load_time
        
        # Add stealth args to browser arguments
        if not hasattr(self, 'extra_browser_args'):
            self.extra_browser_args = []
        self.extra_browser_args = list(set(self.extra_browser_args + self.STEALTH_ARGS))


class StealthBrowserContext(BrowserContext):
    """Extended browser context with stealth capabilities"""
    config: StealthBrowserConfig

    async def _setup_context(self):
        """Override context setup to add stealth features"""
        if not self.browser or not self.browser.playwright_browser:
            raise RuntimeError("Browser not initialized")

        try:
            context = await self.browser.playwright_browser.new_context(
                user_agent=self.config.user_agent or self._get_random_user_agent(),
                viewport=self.config.viewport,
                locale=self.config.locale,
                timezone_id=self.config.timezone_id,
                geolocation=self.config.geolocation,
                permissions=["geolocation", "notifications"],
                bypass_csp=True,
                accept_downloads=True,
                is_mobile=random.random() > 0.8,
                has_touch=random.random() > 0.5,
                device_scale_factor=1 if random.random() > 0.5 else 2,
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Upgrade-Insecure-Requests": "1",
                }
            )

            await self._apply_stealth_scripts(context)
            return context

        except Exception as e:
            raise RuntimeError(f"Failed to create stealth context: {str(e)}") from e


    async def _apply_stealth_scripts(self, context):
        """Apply stealth scripts to the context"""
        await context.add_init_script("""
        () => {
            // Overwrite the webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false,
                configurable: true
            });

            // Remove automation-related attributes
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
            
            // Overwrite Chrome functions
            if (window.chrome) {
                const originalChrome = window.chrome;
                window.chrome = {
                    ...originalChrome,
                    runtime: {
                        ...originalChrome.runtime,
                        connect: () => {},
                    }
                };
            }

            // Modify permissions API
            const originalPermissions = navigator.permissions;
            if (originalPermissions) {
                navigator.permissions = {
                    ...originalPermissions,
                    query: async (parameters) => ({
                        state: 'prompt',
                        onchange: null
                    })
                };
            }
            
            // Add language plugins
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en', 'es'],
                configurable: true
            });
            
            // Add touch points
            if (!('ontouchstart' in window)) {
                Object.defineProperty(navigator, 'maxTouchPoints', {
                    get: () => Math.floor(Math.random() * 5) + 1
                });
            }
            
            // Override plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => ([
                    {
                        name: 'Chrome PDF Plugin',
                        description: 'Portable Document Format',
                        filename: 'internal-pdf-viewer',
                        length: 1
                    },
                    {
                        name: 'Chrome PDF Viewer',
                        description: 'Portable Document Format',
                        filename: 'internal-pdf-viewer',
                        length: 1
                    }
                ])
            });
        }
        """)

    async def new_page(self) -> Page:
        """Create a new page with human-like behavior"""
        page = await super().new_page()
        await self._setup_human_behavior(page)
        return page

    async def _setup_human_behavior(self, page: Page):
        """Setup human-like behavior for the page"""
        original_click = page.click
        original_fill = page.fill

        async def human_click(selector: str, **kwargs):
            element = await page.query_selector(selector)
            if not element:
                raise Exception(f"Element with selector '{selector}' not found")
            
            box = await element.bounding_box()
            if not box:
                raise Exception(f"Could not get bounding box for element '{selector}'")
            
            await page.mouse.move(
                box["x"] + box["width"] * (0.3 + random.random() * 0.4),
                box["y"] + box["height"] * (0.3 + random.random() * 0.4),
                steps=20 + random.randint(0, 15)
            )
            
            await asyncio.sleep(0.1 + random.random() * 0.2)
            await original_click(selector, **kwargs)

        async def human_fill(selector: str, value: str, **kwargs):
            await human_click(selector)
            await page.press(selector, "Control+a")
            await asyncio.sleep(0.1 + random.random() * 0.15)
            await page.press(selector, "Backspace")
            await asyncio.sleep(0.1 + random.random() * 0.1)
            
            for char in value:
                await page.keyboard.type(char, delay=30 + random.random() * 100)
            
            await original_fill(selector, value, **kwargs)

        page.click = human_click
        page.fill = human_fill

    def _get_random_user_agent(self) -> str:
        """Get a random user agent string"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
        ]
        return random.choice(user_agents)

class StealthBrowser(Browser):
    """Extended Browser class with stealth capabilities"""
    
    def __init__(self, config: Optional[StealthBrowserConfig] = None):
        if config is None:
            config = StealthBrowserConfig()
        elif not isinstance(config, StealthBrowserConfig):
            config = StealthBrowserConfig(**config if isinstance(config, dict) else {})
        super().__init__(config)
        
    async def new_context(self, config: Optional[StealthBrowserConfig] = None) -> StealthBrowserContext:
        """Create a stealth browser context"""
        return StealthBrowserContext(config=config or self.config, browser=self)

# import os
# import time
# import random
# import asyncio
# from typing import Dict, List, Optional, Union, Any, Callable, Tuple
# from pathlib import Path

# from playwright.async_api import (
#     async_playwright, 
#     Browser, 
#     BrowserContext, 
#     Page, 
#     Error as PlaywrightError
# )


# class StealthBrowser:
#     """
#     A stealth browser class using Playwright to avoid bot detection.
#     Implements various anti-detection techniques and proper error handling.
#     """
    
#     def __init__(
#         self,
#         browser_type: str = "chromium",
#         headless: bool = False,
#         user_data_dir: Optional[str] = None,
#         proxy: Optional[Dict[str, str]] = None,
#         timeout: int = 30000,
#         retries: int = 3,
#         user_agent: Optional[str] = None,
#         viewport: Optional[Dict[str, int]] = None,
#         geolocation: Optional[Dict[str, float]] = None,
#         locale: str = "en-US",
#         timezone_id: str = "America/New_York",
#         extra_args: Optional[List[str]] = None
#     ):
#         """
#         Initialize the StealthBrowser.
        
#         Args:
#             browser_type: Type of browser to use ('chromium', 'firefox', or 'webkit')
#             headless: Whether to run in headless mode
#             user_data_dir: Directory to store user data
#             proxy: Proxy configuration {'server': 'address', 'username': 'user', 'password': 'pass'}
#             timeout: Default timeout in milliseconds
#             retries: Number of retries for operations
#             user_agent: Custom user agent string
#             viewport: Viewport size {'width': 1920, 'height': 1080}
#             geolocation: Geolocation {'latitude': 37.7749, 'longitude': -122.4194, 'accuracy': 100}
#             locale: Browser locale
#             timezone_id: Browser timezone
#             extra_args: Additional browser arguments
#         """
#         self.options = {
#             "browser_type": browser_type,
#             "headless": headless,
#             "user_data_dir": user_data_dir,
#             "proxy": proxy,
#             "timeout": timeout,
#             "retries": retries,
#             "user_agent": user_agent,
#             "viewport": viewport or {"width": 1920, "height": 1080},
#             "geolocation": geolocation,
#             "locale": locale,
#             "timezone_id": timezone_id,
#             "extra_args": extra_args or []
#         }
        
#         self.playwright = None
#         self.browser = None
#         self.context = None
#         self.page = None
    
#     async def launch(self) -> None:
#         """Launch the browser with stealth mode configurations."""
#         try:
#             # Start playwright
#             self.playwright = await async_playwright().start()
            
#             # Get browser type
#             browser_types = {
#                 "chromium": self.playwright.chromium,
#                 "firefox": self.playwright.firefox,
#                 "webkit": self.playwright.webkit
#             }
#             browser_launcher = browser_types.get(self.options["browser_type"].lower(), self.playwright.chromium)
            
#             # Get stealth args
#             args = self._get_stealth_args()
            
#             # Launch browser
#             self.browser = await browser_launcher.launch(
#                 headless=self.options["headless"],
#                 args=args,
#                 timeout=self.options["timeout"],
#                 downloads_path=os.path.join(os.getcwd(), "downloads")
#             )
            
#             # Create stealth context
#             self.context = await self._create_stealth_context()
            
#             # Create page
#             self.page = await self.context.new_page()
            
#             # Apply page stealth
#             await self._apply_page_stealth()
            
#             print(f"🚀 Stealth browser launched successfully ({self.options['browser_type']})")
#         except Exception as e:
#             await self.close()
#             raise Exception(f"Failed to launch browser: {self._format_error(e)}")
    
#     async def navigate(self, url: str) -> None:
#         """
#         Navigate to a URL with retry mechanism.
        
#         Args:
#             url: The URL to navigate to
#         """
#         if not self.page:
#             raise Exception("Browser not launched. Call launch() first")
        
#         max_retries = self.options["retries"]
#         attempts = 0
#         last_error = None
        
#         while attempts < max_retries:
#             try:
#                 print(f"Navigating to {url} (attempt {attempts + 1}/{max_retries})...")
                
#                 await self.page.goto(url, wait_until="domcontentloaded", timeout=self.options["timeout"])
                
#                 # Add a small delay to ensure page is fully loaded
#                 await asyncio.sleep(random.random() + 0.5)
                
#                 return
#             except Exception as e:
#                 last_error = e
#                 attempts += 1
#                 print(f"Navigation attempt {attempts} failed: {self._format_error(e)}")
                
#                 if attempts < max_retries:
#                     # Wait before retrying with exponential backoff
#                     await asyncio.sleep(2 ** attempts)
        
#         raise Exception(f"Failed to navigate to {url} after {max_retries} attempts: {self._format_error(last_error)}")
    
#     def get_page(self) -> Page:
#         """Get the current page instance."""
#         if not self.page:
#             raise Exception("Browser not launched. Call launch() first")
#         return self.page
    
#     async def take_screenshot(self, file_path: str) -> None:
#         """
#         Take a screenshot and save it to disk.
        
#         Args:
#             file_path: Path to save the screenshot
#         """
#         if not self.page:
#             raise Exception("Browser not launched. Call launch() first")
        
#         try:
#             directory = os.path.dirname(file_path)
#             if directory and not os.path.exists(directory):
#                 os.makedirs(directory, exist_ok=True)
            
#             await self.page.screenshot(path=file_path, full_page=True)
#             print(f"Screenshot saved to {file_path}")
#         except Exception as e:
#             raise Exception(f"Failed to take screenshot: {self._format_error(e)}")
    
#     async def with_retries(self, func: Callable, error_message: str, max_retries: Optional[int] = None) -> Any:
#         """
#         Execute a function within a try-catch block with retry mechanism.
        
#         Args:
#             func: Async function to execute
#             error_message: Error message prefix
#             max_retries: Maximum number of retries
            
#         Returns:
#             Result of the function
#         """
#         if max_retries is None:
#             max_retries = self.options["retries"]
            
#         attempts = 0
#         last_error = None
        
#         while attempts < max_retries:
#             try:
#                 return await func()
#             except Exception as e:
#                 last_error = e
#                 attempts += 1
                
#                 if attempts < max_retries:
#                     print(f"Attempt {attempts} failed: {self._format_error(e)}")
#                     # Wait before retrying with exponential backoff
#                     await asyncio.sleep(2 ** attempts)
        
#         raise Exception(f"{error_message} after {max_retries} attempts: {self._format_error(last_error)}")
    
#     async def close(self) -> None:
#         """Close the browser and all associated resources."""
#         try:
#             if self.page:
#                 try:
#                     await self.page.close()
#                 except:
#                     pass
#                 self.page = None
            
#             if self.context:
#                 try:
#                     await self.context.close()
#                 except:
#                     pass
#                 self.context = None
            
#             if self.browser:
#                 try:
#                     await self.browser.close()
#                 except:
#                     pass
#                 self.browser = None
                
#             if self.playwright:
#                 try:
#                     await self.playwright.stop()
#                 except:
#                     pass
#                 self.playwright = None
            
#             print("Browser closed successfully")
#         except Exception as e:
#             print(f"Error closing browser: {self._format_error(e)}")
    
#     async def _create_stealth_context(self) -> BrowserContext:
#         """Create a stealth browser context."""
#         if not self.browser:
#             raise Exception("Browser not launched")
        
#         context = await self.browser.new_context(
#             user_agent=self.options["user_agent"] or self._get_random_user_agent(),
#             viewport=self.options["viewport"],
#             locale=self.options["locale"],
#             timezone_id=self.options["timezone_id"],
#             geolocation=self.options["geolocation"],
#             permissions=["geolocation", "notifications"],
#             bypass_csp=True,
#             proxy=self.options["proxy"],
#             accept_downloads=True,
#             is_mobile=random.random() > 0.8,  # 20% chance of appearing as mobile
#             has_touch=random.random() > 0.5,  # Randomly enable touch
#             device_scale_factor=1 if random.random() > 0.5 else 2,  # Mix of standard and retina displays
#             java_script_enabled=True,
#             extra_http_headers={
#                 "Accept-Language": "en-US,en;q=0.9",
#                 "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
#                 "Sec-Fetch-Dest": "document",
#                 "Sec-Fetch-Mode": "navigate",
#                 "Sec-Fetch-Site": "none",
#                 "Sec-Fetch-User": "?1",
#                 "Upgrade-Insecure-Requests": "1",
#             }
#         )
        
#         return context
    
#     async def _apply_page_stealth(self) -> None:
#         """Apply additional stealth measures to the page."""
#         if not self.page:
#             return
        
#         # Hide webdriver
#         await self.page.add_init_script("""
#         () => {
#             // Overwrite the webdriver property to avoid detection
#             Object.defineProperty(navigator, 'webdriver', {
#                 get: () => false,
#                 configurable: true
#             });

#             // Remove automation-related attributes
#             delete window.cdc_adoQpoasnfa76pfcZLmcfl_;
#             delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
#             delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
#             delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
            
#             // Overwrite Chrome functions
#             if (window.chrome) {
#                 const originalChrome = window.chrome;
#                 window.chrome = {
#                     ...originalChrome,
#                     runtime: {
#                         ...originalChrome.runtime,
#                         connect: () => {},
#                     }
#                 };
#             }

#             // Modify the permissions API
#             const originalPermissions = navigator.permissions;
#             if (originalPermissions) {
#                 navigator.permissions = {
#                     ...originalPermissions,
#                     query: async (parameters) => {
#                         return {
#                             state: 'prompt',
#                             onchange: null
#                         };
#                     }
#                 };
#             }
            
#             // Add language plugins to appear more like a real browser
#             Object.defineProperty(navigator, 'languages', {
#                 get: () => ['en-US', 'en', 'es'],
#                 configurable: true
#             });
            
#             // Add a fake touch points function
#             if (!('ontouchstart' in window)) {
#                 Object.defineProperty(navigator, 'maxTouchPoints', {
#                     get: () => Math.floor(Math.random() * 5) + 1
#                 });
#             }
            
#             // Override plugins
#             Object.defineProperty(navigator, 'plugins', {
#                 get: () => {
#                     return [
#                         {
#                             name: 'Chrome PDF Plugin',
#                             description: 'Portable Document Format',
#                             filename: 'internal-pdf-viewer',
#                             length: 1
#                         },
#                         {
#                             name: 'Chrome PDF Viewer',
#                             description: 'Portable Document Format',
#                             filename: 'internal-pdf-viewer',
#                             length: 1
#                         }
#                     ];
#                 }
#             });
#         }
#         """)
        
#         # Enable human-like interactions
#         await self._enable_human_like_interactions()
    
#     async def _enable_human_like_interactions(self) -> None:
#         """Enable human-like mouse movements and interactions."""
#         if not self.page:
#             return
        
#         # We'll use this later to simulate human-like interactions
#         self._original_click = self.page.click
#         self._original_fill = self.page.fill
    
#     async def click(self, selector: str, **kwargs) -> None:
#         """
#         Click with human-like behavior.
        
#         Args:
#             selector: Element selector
#             **kwargs: Additional arguments for click
#         """
#         if not self.page:
#             raise Exception("Browser not launched. Call launch() first")
        
#         try:
#             # Find the element
#             element = await self.page.query_selector(selector)
#             if not element:
#                 raise Exception(f"Element with selector '{selector}' not found")
            
#             # Get the element's position
#             box = await element.bounding_box()
#             if not box:
#                 raise Exception(f"Could not get bounding box for element '{selector}'")
            
#             # Move to the element with a natural curve
#             await self.page.mouse.move(
#                 box["x"] + box["width"] * (0.3 + random.random() * 0.4),
#                 box["y"] + box["height"] * (0.3 + random.random() * 0.4),
#                 steps=20 + random.randint(0, 15)
#             )
            
#             # Small delay before clicking
#             await asyncio.sleep(0.1 + random.random() * 0.2)
            
#             # Click
#             await self._original_click(selector, **kwargs)
#         except Exception as e:
#             raise Exception(f"Failed to click on '{selector}': {self._format_error(e)}")
    
#     async def fill(self, selector: str, value: str, **kwargs) -> None:
#         """
#         Fill input with human-like typing.
        
#         Args:
#             selector: Element selector
#             value: Text to fill
#             **kwargs: Additional arguments for fill
#         """
#         if not self.page:
#             raise Exception("Browser not launched. Call launch() first")
        
#         try:
#             # Click the element first
#             await self.click(selector)
            
#             # Clear the field
#             await self.page.press(selector, "Control+a")
#             await asyncio.sleep(0.1 + random.random() * 0.15)
#             await self.page.press(selector, "Backspace")
#             await asyncio.sleep(0.1 + random.random() * 0.1)
            
#             # Type with random delays between keystrokes
#             for char in value:
#                 await self.page.keyboard.type(char, delay=30 + random.random() * 100)
            
#             # Call original fill for consistency
#             await self._original_fill(selector, value, **kwargs)
#         except Exception as e:
#             raise Exception(f"Failed to fill '{selector}' with '{value}': {self._format_error(e)}")
    
#     def _format_error(self, error: Any) -> str:
#         """Format error messages consistently."""
#         if not error:
#             return "Unknown error"
        
#         if hasattr(error, "message"):
#             return str(error.message)
#         return str(error)
    
#     def _get_stealth_args(self) -> List[str]:
#         """Get browser launch arguments for stealth mode."""
#         default_args = [
#             "--disable-blink-features=AutomationControlled",
#             "--disable-features=IsolateOrigins,site-per-process",
#             "--disable-site-isolation-trials",
#             "--disable-web-security",
#             "--disable-features=BlockInsecurePrivateNetworkRequests",
#             "--no-sandbox",
#             "--disable-dev-shm-usage",
#             "--disable-accelerated-2d-canvas",
#             "--disable-gpu",
#             "--window-size=1920,1080",
#             "--hide-scrollbars",
#             "--mute-audio",
#             "--ignore-certificate-errors",
#             "--ignore-certificate-errors-spki-list",
#             "--enable-features=NetworkService",
#             "--disable-background-timer-throttling",
#             "--disable-backgrounding-occluded-windows",
#             "--disable-renderer-backgrounding",
#             "--disable-breakpad",
#             "--disable-component-extensions-with-background-pages",
#             "--disable-extensions",
#             "--disable-hang-monitor",
#             "--disable-ipc-flooding-protection",
#             "--disable-popup-blocking",
#             "--disable-prompt-on-repost",
#             "--metrics-recording-only",
#             "--no-first-run",
#             "--password-store=basic",
#             "--use-mock-keychain",
#             "--force-webrtc-ip-handling-policy=disable-non-proxied-udp",
#             "--disable-setuid-sandbox",
#             "--no-default-browser-check",
#             "--no-experiments",
#             "--no-pings",
#         ]
        
#         return default_args + self.options["extra_args"]
    
#     def _get_random_user_agent(self) -> str:
#         """Get a random user agent string from a list of common ones."""
#         user_agents = [
#             "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
#             "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
#             "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
#             "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
#             "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
#             "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
#             "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
#         ]
        
#         return random.choice(user_agents)


# Example usage
# async def example():
#     """Example usage of StealthBrowser."""
#     browser = StealthBrowser(
#         browser_type="chromium",
#         headless=False,
#         viewport={"width": 1920, "height": 1080},
#         timeout=60000,
#         retries=3,
#     )
    
#     try:
#         await browser.launch()
#         await browser.navigate("https://gmail.com/")
        
#         # Example login flow
#         await browser.with_retries(
#             lambda: login_to_google(browser),
#             "Failed to log in to Google"
#         )
        
#         print("Login successful!")
        
#         # Save a screenshot
#         await browser.take_screenshot("./screenshots/google-login.png")
        
#         # Do other operations...
        
#     except Exception as e:
#         print(f"Error: {e}")
#     finally:
#         await browser.close()


# async def login_to_google(browser: StealthBrowser):
#     """Helper function for logging into Google."""
#     page = browser.get_page()
#     await browser.fill('input[type="email"]', "amanragu2002@gmail.com")
#     await browser.click('button:has-text("Next")')
#     await page.wait_for_selector('input[type="password"]')
#     await browser.fill('input[type="password"]', "your-password")
#     await browser.click('button:has-text("Next")')
    
#     # Wait for successful login
#     await page.wait_for_navigation(wait_until="networkidle")


# # To run the example
# if __name__ == "__main__":
#     asyncio.run(example())
