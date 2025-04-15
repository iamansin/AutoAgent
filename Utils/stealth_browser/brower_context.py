# Add these imports at the top
from .config import StealthConfig
from .stealth_browser import BrowserStealth
from browser_use import BrowserContextConfig, Browser
from browser_use.browser.context import BrowserContextState, BrowserSession
from typing_extensions import Optional
import uuid 
from playwright.async_api import Page
from playwright.sync_api
import random
class BrowserContext:
    def __init__(
        self,
        browser: 'Browser',
        config: BrowserContextConfig | None = None,
        state: Optional[BrowserContextState] = None,
        stealth_config: Optional[StealthConfig] = None,
    ):
        self.context_id = str(uuid.uuid4())
        self.config = config or BrowserContextConfig(**(browser.config.model_dump() if browser.config else {}))
        self.browser = browser
        self.state = state or BrowserContextState()
        self.stealth_config = stealth_config or StealthConfig()
        self.stealth = BrowserStealth(self.stealth_config)
        
        # Initialize these as None - they'll be set up when needed
        self.session: BrowserSession | None = None
        self.active_tab: Page | None = None

    async def _create_context(self, browser: Browser):
        """Creates a new browser context with stealth measures"""
        if self.browser.config.cdp_url and len(browser.contexts) > 0:
            context = browser.contexts[0]
        elif self.browser.config.browser_binary_path and len(browser.contexts) > 0:
            context = browser.contexts[0]
        else:
            # Enhanced context creation with stealth settings
            context = await browser.new_context(
                no_viewport=True,
                user_agent=self.stealth.get_random_user_agent(),
                java_script_enabled=True,
                bypass_csp=self.config.disable_security,
                ignore_https_errors=self.config.disable_security,
                record_video_dir=self.config.save_recording_path,
                record_video_size=self.config.browser_window_size.model_dump(),
                record_har_path=self.config.save_har_path,
                locale=self.config.locale,
                http_credentials=self.config.http_credentials,
                is_mobile=self.config.is_mobile,
                has_touch=self.config.has_touch,
                geolocation=self.config.geolocation,
                permissions=self.config.permissions,
                timezone_id=self.config.timezone_id,
                # Additional stealth settings
                proxy={
                    'server': 'http://proxy-server.example.com:8080',  # Configure your proxy
                    'username': 'user',
                    'password': 'pass',
                } if hasattr(self.config, 'proxy') and self.config.proxy else None,
                device_scale_factor=random.uniform(1, 2),  # Random device scale
                reduced_motion='reduce',  # Reduce motion to avoid detection
                force_color_profile='srgb',  # Use standard color profile
            )

            # Apply stealth measures to the context
            await context.add_init_script("""
                // Override navigator properties
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            """)

        # Apply stealth measures to new pages
        context.on("page", self._handle_new_page)

        return context

    async def _handle_new_page(self, page: Page):
        """Apply stealth measures to newly created pages"""
        await self.stealth.apply_stealth(self.session.context, page)

    async def _click_element_node(self, element_node: DOMElementNode) -> Optional[str]:
        """Enhanced click with random delays and human-like behavior"""
        try:
            # Add random delay before clicking
            await self.stealth.random_delay()
            
            element_handle = await self.get_locate_element(element_node)
            
            if element_handle is None:
                raise Exception(f'Element: {repr(element_node)} not found')

            # Simulate human-like mouse movement
            page = await self.get_current_page()
            
            # Random offset within element boundaries
            box = await element_handle.bounding_box()
            if box:
                x_offset = random.uniform(5, box['width'] - 5)
                y_offset = random.uniform(5, box['height'] - 5)
                
                # Move mouse with realistic acceleration
                await page.mouse.move(
                    box['x'] + x_offset,
                    box['y'] + y_offset,
                    steps=random.randint(5, 10)  # Random steps for natural movement
                )

            # Rest of the original click logic...
            return await super()._click_element_node(element_node)

        except Exception as e:
            raise Exception(f'Failed to click element: {repr(element_node)}. Error: {str(e)}')

    async def _input_text_element_node(self, element_node: DOMElementNode, text: str):
        """Enhanced text input with human-like typing behavior"""
        try:
            element_handle = await self.get_locate_element(element_node)
            
            if element_handle is None:
                raise BrowserError(f'Element: {repr(element_node)} not found')

            # Random initial delay
            await self.stealth.random_delay()

            # Get element properties
            tag_handle = await element_handle.get_property('tagName')
            tag_name = (await tag_handle.json_value()).lower()
            
            # Clear existing text with random backspaces
            current_value = await element_handle.input_value()
            if current_value:
                for _ in current_value:
                    await element_handle.press('Backspace')
                    await asyncio.sleep(random.uniform(0.01, 0.03))

            # Type text with random delays between characters
            for char in text:
                await element_handle.type(char, delay=random.uniform(50, 150))
                
                # Occasional longer pause
                if random.random() < 0.1:
                    await asyncio.sleep(random.uniform(0.1, 0.3))

            # Random delay after typing
            await self.stealth.random_delay()

        except Exception as e:
            logger.debug(f'❌  Failed to input text into element: {repr(element_node)}. Error: {str(e)}')
            raise BrowserError(f'Failed to input text into index {element_node.highlight_index}')