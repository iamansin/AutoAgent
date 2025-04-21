import random
import asyncio
from typing import Dict, Optional, List, Union, Tuple
from pydantic import BaseModel, Field, ConfigDict
from browser_use.browser.browser import Browser, BrowserConfig, BrowserContext
from playwright.async_api import Page, Playwright, async_playwright

class StealthBrowserConfig(BrowserConfig):
    """Extended browser configuration for stealth features"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    viewport_width: int = Field(default=1920, description="Browser viewport width")
    viewport_height: int = Field(default=1080, description="Browser viewport height")
    user_agent: str = Field(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        description="Custom user agent string"
    )
    geolocation: Dict[str, float] = Field(
        default={
            "latitude": 40.7128,
            "longitude": -74.0060
        },
        description="Geolocation coordinates"
    )
    enhanced_args: List[str] = Field(
    default=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-site-isolation-trials',
                    '--disable-features=UserAgentClientHint',
                    '--no-sandbox',
                    '--disable-webgl',
                    '--disable-threaded-scrolling',
                    '--disable-threaded-animation',
                    '--disable-extensions'
                
        # # Essential stealth arguments
        # '--disable-blink-features=AutomationControlled',  # Critical for avoiding automation detection
        # '--enable-automation=false',  # New: explicitly disable automation flag
        
        # # Hardware acceleration and rendering (keep these enabled for normal browser behavior)
        # '--enable-gpu',  # Changed from disable-gpu to enable it like normal browsers
        # '--ignore-gpu-blocklist',  # New: ensure GPU acceleration works
        # '--enable-hardware-overlays',  # New: enable hardware overlays for video
        
        # # Privacy and security (balanced approach)
        # '--disable-features=IsolateOrigins',  # Keep this for compatibility
        # '--disable-features=UserAgentClientHint',  # Important for preventing fingerprinting
        # '--disable-features=TranslateUI',  # Keep this to avoid translation popups
        
        # # Performance settings
        # '--disable-dev-shm-usage',  # Keep for stability
        # '--no-first-run',  # Avoid first-run dialogs
        # '--password-store=basic',  # New: enable basic password storage like regular browsers
        
        # # Media handling
        # '--autoplay-policy=user-gesture-required',  # New: require user interaction for autoplay
        # '--enable-audio-service',  # New: enable audio service instead of muting
        
        # # Browser behavior
        # '--enable-background-networking',  # Changed: allow background networking like normal browsers
        # '--enable-background-timer-throttling',  # Changed: allow normal timer behavior
        # '--enable-backgrounding-occluded-windows',  # Changed: allow normal window behavior
        
        # # Extensions and components
        # '--enable-extensions',  # Changed: allow extensions like normal browsers
        # '--enable-component-extensions',  # New: enable component extensions
        
        # # Display and rendering
        # '--force-color-profile=srgb',  # Keep this for consistent color rendering
        # '--enable-font-antialiasing',  # New: enable normal font rendering
        # '--enable-smooth-scrolling',  # New: enable smooth scrolling like normal browsers
        
        # # Additional human-like features
        # '--enable-pepper-3d',  # New: enable 3D graphics
        # '--enable-javascript-harmony',  # New: enable modern JavaScript features
        # '--enable-media-stream',  # New: enable media streaming
        # '--enable-webgl',  # New: enable WebGL
        # '--enable-webrtc',  # New: enable WebRTC
        ],
        description="Enhanced stealth arguments for browser"
    )

class StealthBrowser(Browser):
    """Enhanced browser class with stealth features"""
    def __init__(self, config: Optional[StealthBrowserConfig] = None):
        """Initialize stealth browser with optional configuration"""
        super().__init__()
        self._browser = None
        self._playwright = None
        self.config = config or StealthBrowserConfig()
        
    async def get_playwright_browser(self):
        """Get or create the playwright browser with enhanced stealth settings"""
        if self._browser:
            return self._browser
        
        try:
            # Start playwright if not already started
            if not self._playwright:
                self._playwright = await async_playwright().start()
            
            # Combine user-provided args with enhanced stealth args
            browser_args = []
            enhanced_args = self.config.enhanced_args if isinstance(self.config.enhanced_args, list) else []
            window_size_arg = f'--window-size={self.config.viewport_width},{self.config.viewport_height}'
            combined_args = list(set(browser_args + enhanced_args + [window_size_arg]))
            #  = list(set(browser_args + self.config.enhanced_args + window_size_arg))
            
            # Launch the browser with enhanced stealth settings
            self._browser = await self._playwright.chromium.launch(
                headless=self.config.headless,
                args=combined_args,
                chromium_sandbox=False,
                ignore_default_args=['--enable-automation'],
                slow_mo=random.uniform(0.5, 2.0),  # Randomized slow_mo for more human-like behavior
            )
            
            return self._browser
            
        except Exception as e:
            await self.cleanup()
            raise e
    
    async def cleanup(self):
        """Clean up browser resources"""
        if self._browser:
            try:
                await self._browser.close()
            except:
                pass
            finally:
                self._browser = None
                
        if self._playwright:
            try:
                await self._playwright.stop()
            except:
                pass
            finally:
                self._playwright = None
                
    # async def create_context(self) -> BrowserContext:
    #     """Create a new browser context with stealth settings"""
    #     browser = await self.get_playwright_browser()
        
    #     context = await browser.new_context(
    #         viewport={'width': self.config.viewport_width, 'height': self.config.viewport_height},
    #         user_agent=self.config.user_agent,
    #         device_scale_factor=1,
    #         has_touch=False,
    #         is_mobile=False,
    #         locale='en-US',
    #         timezone_id='America/New_York',
    #         permissions=['geolocation'],
    #         geolocation=self.config.geolocation,
    #         java_script_enabled=True,
    #         bypass_csp=True,
    #     )
        
    #     # Add stealth scripts to modify navigator properties
    #     await context.add_init_script("""
    #         () => {
    #             const originalQuery = window.navigator.permissions.query;
    #             window.navigator.permissions.query = (parameters) => (
    #                 parameters.name === 'notifications' ?
    #                     Promise.resolve({ state: Notification.permission }) :
    #                     originalQuery(parameters)
    #             );
                
    #             Object.defineProperties(navigator, {
    #                 webdriver: { get: () => undefined },
    #                 languages: { get: () => ['en-US', 'en'] },
    #                 plugins: {
    #                     get: () => [
    #                         {
    #                             name: 'Chrome PDF Plugin',
    #                             description: 'Portable Document Format',
    #                             filename: 'internal-pdf-viewer'
    #                         }
    #                     ]
    #                 },
    #                 platform: { get: () => 'Win32' }
    #             });
                
    #             // Overwrite the `navigator.mediaDevices` property
    #             if (navigator.mediaDevices === undefined) {
    #                 navigator.mediaDevices = {};
    #             }
                
    #             // Overwrite WebGL properties
    #             const getParameter = WebGLRenderingContext.prototype.getParameter;
    #             WebGLRenderingContext.prototype.getParameter = function(parameter) {
    #                 if (parameter === 37445) {
    #                     return 'Intel Open Source Technology Center';
    #                 }
    #                 if (parameter === 37446) {
    #                     return 'Mesa DRI Intel(R) HD Graphics (Skylake GT2)';
    #                 }
    #                 return getParameter.apply(this, arguments);
    #             };
    #         }
    #     """)
        
    #     return BrowserContext(context=context, browser=self)
    
