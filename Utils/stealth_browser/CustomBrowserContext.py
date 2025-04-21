from browser_use import Browser
from browser_use.browser.context import BrowserContext, BrowserContextConfig, BrowserContextState
from playwright.async_api import Browser as PlaywrightBrowser
import os 
import asyncio
import json
import logging
import random
from browser_use.dom.service import DomService
from browser_use.dom.views import DOMElementNode, SelectorMap
from browser_use.browser.views import (
	BrowserError,
	BrowserState,
	TabInfo,
	URLNotAllowedError,
)
from browser_use.utils import time_execution_async, time_execution_sync
from typing_extensions import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ExtendedContext(BrowserContext):
    
    def __init__(self, browser: Browser, 
                 config: BrowserContextConfig = BrowserContextConfig(), 
                 state: BrowserContextState | None = None, 
                 current_context = None):
        self.current_context = current_context
        super().__init__(browser, config, state)
        
    async def _create_context(self, browser: PlaywrightBrowser):
        """Creates a new browser context with enhanced anti-detection measures and loads cookies if available."""
        if self.browser.config.cdp_url and len(browser.contexts) > 0:
            context = browser.contexts[0]
        
        if self.current_context:
            logger.warning("Using Existing Context!!")
            context = self.current_context
        else:
            # Enhanced stealth configurations
            context = await browser.new_context(
                no_viewport=True,
                user_agent=self.config.user_agent or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                java_script_enabled=True,
                bypass_csp=self.config.disable_security,
                ignore_https_errors=self.config.disable_security,
                record_video_dir=self.config.save_recording_path,
                record_video_size=self.config.browser_window_size,
                locale=self.config.locale or 'en-US',
                geolocation= {'latitude': 40.7128, 'longitude': -74.0060},
                permissions=['geolocation'],
                timezone_id='America/New_York',
                color_scheme='no-preference',
                reduced_motion='no-preference',
                forced_colors='none',
            )

        if self.config.trace_path:
            await context.tracing.start(screenshots=True, snapshots=True, sources=True)

        # Load cookies if they exist
        if self.config.cookies_file and os.path.exists(self.config.cookies_file):
            with open(self.config.cookies_file, 'r') as f:
                try:
                    cookies = json.load(f)

                    valid_same_site_values = ['Strict', 'Lax', 'None']
                    for cookie in cookies:
                        if 'sameSite' in cookie:
                            if cookie['sameSite'] not in valid_same_site_values:
                                logger.warning(
                                    f"Fixed invalid sameSite value '{cookie['sameSite']}' to 'None' for cookie {cookie.get('name')}"
                                )
                                cookie['sameSite'] = 'None'
                    logger.info(f'🍪  Loaded {len(cookies)} cookies from {self.config.cookies_file}')
                    await context.add_cookies(cookies)

                except json.JSONDecodeError as e:
                    logger.error(f'Failed to parse cookies file: {str(e)}')

        # Modified anti-detection script with safer DOM manipulation
        await context.add_init_script(
            r"""
            // Comprehensive anti-detection script
            
            // Basic webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Chrome runtime presence
            window.chrome = {
                runtime: {
                    connect: () => {},
                    sendMessage: () => {},
                    onMessage: {
                        addListener: () => {},
                        removeListener: () => {}
                    },
                    onInstalled: { 
                        addListener: () => {} 
                    },
                    getPlatformInfo: () => {},
                    getManifest: () => ({version: '120.0.0.0'})
                },
                loadTimes: () => {},
                csi: () => {},
                app: {
                    getDetails: () => {},
                    getIsInstalled: () => {}
                }
            };
            
            // Prevent detection via error stack traces
            const originalGetStackTrace = Error.prototype.stack;
            Object.defineProperty(Error.prototype, 'stack', {
                get() {
                    return originalGetStackTrace && originalGetStackTrace
                        .call(this)
                        .replace(/(\n.*at\s)(.*puppeteer.*|.*playwright.*)/g, '$1');
                }
            });
            
            // Language and plugins
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    const plugins = [
                        {
                            0: {type: "application/pdf", suffixes: "pdf", description: "Portable Document Format"},
                            name: "Chrome PDF Plugin",
                            description: "Portable Document Format",
                            filename: "internal-pdf-viewer",
                            length: 1
                        },
                        {
                            0: {type: "application/pdf", suffixes: "pdf", description: "Portable Document Format"},
                            name: "Chrome PDF Viewer",
                            description: "Portable Document Format",
                            filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai",
                            length: 1
                        },
                        {
                            0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                            name: "PDF Viewer",
                            description: "Portable Document Format",
                            filename: "internal-pdf-viewer",
                            length: 1
                        }
                    ];
                    
                    // Make plugins appear as a real Array + PluginArray
                    const pluginArray = Object.create(Object.getPrototypeOf(navigator.plugins));
                    plugins.forEach((plugin, i) => {
                        pluginArray[i] = plugin;
                    });
                    pluginArray.length = plugins.length;
                    
                    // Add required functions
                    pluginArray.item = function(index) { return this[index]; };
                    pluginArray.namedItem = function(name) {
                        for (const plugin of plugins) {
                            if (plugin.name === name) return plugin;
                        }
                        return null;
                    };
                    
                    return pluginArray;
                }
            });
            
            // Mimic a proper mimeTypes collection
            Object.defineProperty(navigator, 'mimeTypes', {
                get: () => {
                    const mimeTypes = [
                        {type: "application/pdf", suffixes: "pdf", description: "Portable Document Format", enabledPlugin: {name: "Chrome PDF Plugin"}},
                        {type: "text/pdf", suffixes: "pdf", description: "Portable Document Format", enabledPlugin: {name: "Chrome PDF Viewer"}}
                    ];
                    
                    const mimeTypeArray = Object.create(Object.getPrototypeOf(navigator.mimeTypes));
                    mimeTypes.forEach((mimeType, i) => {
                        mimeTypeArray[i] = mimeType;
                    });
                    mimeTypeArray.length = mimeTypes.length;
                    
                    mimeTypeArray.item = function(index) { return this[index]; };
                    mimeTypeArray.namedItem = function(name) {
                        for (const mime of mimeTypes) {
                            if (mime.type === name) return mime;
                        }
                        return null;
                    };
                    
                    return mimeTypeArray;
                }
            });
            
            // Override permissions API
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => {
                if (parameters.name === 'notifications') {
                    return Promise.resolve({ state: Notification.permission });
                }
                if (parameters.name === 'clipboard-read' || parameters.name === 'clipboard-write') {
                    return Promise.resolve({ state: "prompt" });
                }
                return originalQuery(parameters);
            };
            
            // Fix shadow DOM detection
            (function() {
                const originalAttachShadow = Element.prototype.attachShadow;
                Element.prototype.attachShadow = function attachShadow(options) {
                    return originalAttachShadow.call(this, { ...options, mode: "open" });
                };
            })();
            
            // Stop canvas fingerprinting
            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(type) {
                // Is it in a test environment?
                const context = this.getContext('2d');
                if (context) {
                    const imageData = context.getImageData(0, 0, this.width, this.height);
                    const pixels = imageData.data;
                    
                    // Slight random variations on the pixels
                    for (let i = 0; i < pixels.length; i += 4) {
                        // Only modify non-transparent pixels slightly (not noticeable to human)
                        if (pixels[i + 3] > 0) {
                            for (let j = 0; j < 3; j++) {
                                const val = pixels[i + j];
                                // Add tiny random variation [-1, 0, 1]
                                pixels[i + j] = Math.max(0, Math.min(255, val + (Math.floor(Math.random() * 3) - 1)));
                            }
                        }
                    }
                    context.putImageData(imageData, 0, 0);
                }
                return originalToDataURL.apply(this, arguments);
            };
            
            // Alter WebGL fingerprinting
            const getParameterProxied = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                // UNMASKED_VENDOR_WEBGL and UNMASKED_RENDERER_WEBGL
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel Iris OpenGL Engine';
                }
                return getParameterProxied.call(this, parameter);
            };
            
            // Fix iframe contentWindow access
            const originalContentWindow = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'contentWindow');
            Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
                get() {
                    const window = originalContentWindow.get.call(this);
                    if (!window) return null;
                    
                    try {
                        // Test if cross-origin
                        window.self;
                        return window;
                    } catch (e) {
                        // Return a proxy for cross-origin iframes to avoid exceptions
                        return new Proxy({}, {
                            get: function() {
                                return undefined;
                            }
                        });
                    }
                }
            });
            
            // Override User Agent Client Hints API if available
            if (navigator.userAgentData) {
                Object.defineProperty(navigator, 'userAgentData', {
                    get: () => ({
                        brands: [
                            {brand: "Google Chrome", version: "120"},
                            {brand: "Chromium", version: "120"},
                            {brand: "Not=A?Brand", version: "99"}
                        ],
                        mobile: false,
                        platform: "Windows",
                        getHighEntropyValues: () => Promise.resolve({
                            architecture: "x86",
                            bitness: "64",
                            brands: [
                                {brand: "Google Chrome", version: "120"},
                                {brand: "Chromium", version: "120"},
                                {brand: "Not=A?Brand", version: "99"}
                            ],
                            fullVersionList: [
                                {brand: "Google Chrome", version: "120.0.6099.109"},
                                {brand: "Chromium", version: "120.0.6099.109"},
                                {brand: "Not=A?Brand", version: "99.0.0.0"}
                            ],
                            mobile: false,
                            model: "",
                            platform: "Windows",
                            platformVersion: "10.0.0",
                            uaFullVersion: "120.0.6099.109"
                        })
                    })
                });
            }
            
            // Override getBattery
            if (navigator.getBattery) {
                navigator.getBattery = () => Promise.resolve({
                    charging: true,
                    chargingTime: 0,
                    dischargingTime: Infinity,
                    level: 1,
                    addEventListener: () => {},
                    removeEventListener: () => {}
                });
            }
            
            // Override connection API
            if (navigator.connection) {
                Object.defineProperties(navigator.connection, {
                    effectiveType: {
                        get: () => '4g'
                    },
                    rtt: {
                        get: () => 50
                    },
                    downlink: {
                        get: () => 10
                    },
                    saveData: {
                        get: () => false
                    }
                });
            }
            
            // Override hardwareConcurrency and deviceMemory
            Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
            Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
            
            // Modified: Only apply subtle DOM position changes that won't affect functionality
            // Completely disable position modifications for interactive elements
            const originalGetBoundingClientRect = Element.prototype.getBoundingClientRect;
            Element.prototype.getBoundingClientRect = function() {
                const rect = originalGetBoundingClientRect.apply(this, arguments);
                
                // Check if this is an interactive element that needs precise positioning
                const tagName = this.tagName ? this.tagName.toLowerCase() : '';
                const isInteractive = ['input', 'textarea', 'select', 'button', 'a'].includes(tagName) || 
                                      this.getAttribute('role') === 'button' ||
                                      this.getAttribute('contenteditable') === 'true';
                
                // Don't modify positions for interactive elements
                if (!isInteractive) {
                    // Use an extremely small offset that won't affect functionality
                    const offset = 0.00000001; // Virtually unnoticeable
                    rect.x += offset;
                    rect.y += offset;
                    rect.width += offset;
                    rect.height += offset;
                    rect.top += offset;
                    rect.right += offset;
                    rect.bottom += offset;
                    rect.left += offset;
                }
                
                return rect;
            };
            """
        )

        # Modified human-like interactions script with safer event handling
        await context.add_init_script(
            r"""
            // Modified human-like interaction patterns with minimal DOM interference
            (function() {
                const originalAddEventListener = EventTarget.prototype.addEventListener;
                EventTarget.prototype.addEventListener = function(type, listener, options) {
                    // Only modify non-critical events on non-interactive elements
                    if (type === 'mousemove' || type === 'touchmove') {
                        // Determine if this is an interactive element that needs precise events
                        const isInteractive = (this instanceof HTMLInputElement || 
                                              this instanceof HTMLTextAreaElement || 
                                              this instanceof HTMLSelectElement ||
                                              this instanceof HTMLButtonElement ||
                                              this instanceof HTMLAnchorElement ||
                                              (this instanceof HTMLElement && 
                                                (this.getAttribute('role') === 'button' ||
                                                 this.getAttribute('contenteditable') === 'true')));
                                                 
                        // Only wrap listener if it's not an interactive element
                        if (!isInteractive) {
                            const wrappedListener = function(event) {
                                // Don't modify events created by real users
                                if (!event.isTrusted) {
                                    if (event.clientX !== undefined) {
                                        // Use extremely minimal randomness that won't affect functionality
                                        const randomFactor = (Math.random() * 0.005) - 0.0025; // Tiny range
                                        
                                        // Only modify if property doesn't already have getter/setter
                                        if (!Object.getOwnPropertyDescriptor(event, '_clientX')) {
                                            try {
                                                Object.defineProperty(event, '_clientX', {
                                                    value: event.clientX + randomFactor,
                                                    writable: true
                                                });
                                                
                                                Object.defineProperty(event, 'clientX', {
                                                    get: function() { return this._clientX; }
                                                });
                                            } catch (e) {
                                                // Silently fail if we can't modify the event
                                                // This prevents breaking UI frameworks
                                            }
                                        }
                                        
                                        if (!Object.getOwnPropertyDescriptor(event, '_clientY')) {
                                            try {
                                                Object.defineProperty(event, '_clientY', {
                                                    value: event.clientY + randomFactor,
                                                    writable: true
                                                });
                                                
                                                Object.defineProperty(event, 'clientY', {
                                                    get: function() { return this._clientY; }
                                                });
                                            } catch (e) {
                                                // Silently fail
                                            }
                                        }
                                    }
                                }
                                
                                // Call the original listener
                                return listener.apply(this, arguments);
                            };
                            
                            return originalAddEventListener.call(this, type, wrappedListener, options);
                        }
                    }
                    
                    // For all other cases, use the original event listener
                    return originalAddEventListener.call(this, type, listener, options);
                };
            })();
            """
        )

        return context
    
    @time_execution_async('--input_text_element_node')
    async def _input_text_element_node(self, element_node: DOMElementNode, text: str):
        """
        Input text into an element with a more reliable approach.
        Uses a combination of methods to maximize compatibility with various UI frameworks.
        """
        try:
            element_handle = await super().get_locate_element(element_node)

            if element_handle is None:
                raise BrowserError(f'Element: {repr(element_node)} not found')

            # Ensure element is ready for input
            try:
                await element_handle.wait_for_element_state('stable', timeout=1000)
                is_hidden = await element_handle.is_hidden()
                if not is_hidden:
                    await element_handle.scroll_into_view_if_needed(timeout=1000)
            except Exception as e:
                logger.debug(f"Non-critical error preparing element: {str(e)}")
                pass

            # Get element properties to determine input method
            tag_handle = await element_handle.get_property('tagName')
            tag_name = (await tag_handle.json_value()).lower()
            is_contenteditable = await element_handle.get_property('isContentEditable')
            readonly_handle = await element_handle.get_property('readOnly')
            disabled_handle = await element_handle.get_property('disabled')

            readonly = await readonly_handle.json_value() if readonly_handle else False
            disabled = await disabled_handle.json_value() if disabled_handle else False

            # Modified approach that works better with various UI frameworks
            if ((await is_contenteditable.json_value()) or tag_name == 'input') and not (readonly or disabled):
                # First focus on the element
                await element_handle.focus()
                await asyncio.sleep(0.2)
                
                # Common approach to clear the field
                await element_handle.evaluate('''(el) => {
                    // Clear the field using the most compatible approach
                    if (el.tagName.toLowerCase() === 'input' || el.tagName.toLowerCase() === 'textarea') {
                        el.value = '';
                    } else if (el.isContentEditable) {
                        el.textContent = '';
                    }
                }''')
                
                await asyncio.sleep(0.2)
                
                # Determine best input method based on field type
                # We use fill for some cases and typing for others for better compatibility
                input_type = ""
                if tag_name == "input":
                    type_handle = await element_handle.get_property('type')
                    input_type = await type_handle.json_value()
                
                # Use different typing strategies based on element type
                # but avoid any specific site or field-type logic
                if tag_name == 'textarea' or (await is_contenteditable.json_value()):
                    # For text areas and rich text editors, use human-like typing
                    await self.human_like_typing(element_handle, text)
                else:
                    # For standard input fields, use a more reliable approach that
                    # works better with form validation and auto-completion
                    try: 
                        # Try fill first as it's more reliable for modern frameworks
                        await element_handle.fill(text)
                        await asyncio.sleep(0.3)  # Let the UI update
                        
                        # Check if the text actually got entered (some frameworks clear it)
                        value = await element_handle.evaluate('el => el.value')
                        if not value and text:  # If field is empty but should have text
                            # Fall back to type method
                            await element_handle.evaluate('el => el.value = ""')  # Clear again
                            await self.human_like_typing(element_handle, text, reduced_randomness=True)
                    except Exception:
                        # If fill fails, fall back to typing
                        await self.human_like_typing(element_handle, text, reduced_randomness=True)
                
                # Adding a small delay after input helps with reactivity
                await asyncio.sleep(0.3)
                
                # Press Tab after entering text to trigger validation and move focus
                # This helps with many UI frameworks' input handling
                await element_handle.press('Tab')
            else:
                # For other elements, use fill
                await asyncio.sleep(0.1)
                await element_handle.fill(text)
                await asyncio.sleep(0.2)
                
        except Exception as e:
            logger.debug(f'❌  Failed to input text into element: {repr(element_node)}. Error: {str(e)}')
            raise BrowserError(f'Failed to input text into index {element_node.highlight_index}')
        
    @time_execution_async('--click_element_node')
    async def _click_element_node(self, element_node: DOMElementNode) -> Optional[str]:
        """
        Optimized method to click an element with better compatibility across frameworks.
        """
        page = await super().get_current_page()

        try:
            element_handle = await super().get_locate_element(element_node)

            if element_handle is None:
                raise Exception(f'Element: {repr(element_node)} not found')

            # Add minimal delay before clicking
            await asyncio.sleep(0.2)

            async def perform_click(click_func):
                """Performs the actual click, handling both download
                and navigation scenarios."""
                if self.config.save_downloads_path:
                    try:
                        # Try short-timeout expect_download to detect a file download has been been triggered
                        async with page.expect_download(timeout=5000) as download_info:
                            await click_func()
                        download = await download_info.value
                        # Determine file path
                        suggested_filename = download.suggested_filename
                        unique_filename = await super()._get_unique_filename(self.config.save_downloads_path, suggested_filename)
                        download_path = os.path.join(self.config.save_downloads_path, unique_filename)
                        await download.save_as(download_path)
                        logger.debug(f'⬇️  Download triggered. Saved file to: {download_path}')
                        return download_path
                    except TimeoutError:
                        # If no download is triggered, treat as normal click
                        logger.debug('No download triggered within timeout. Checking navigation...')
                        await page.wait_for_load_state()
                        await super()._check_and_handle_navigation(page)
                else:
                    # Standard click logic if no download is expected
                    await click_func()
                    await page.wait_for_load_state()
                    await super()._check_and_handle_navigation(page)

            try:
                # First ensure element is ready for interaction
                await element_handle.wait_for_element_state('stable', timeout=2000)
                # Scroll element into view for more reliable clicking
                await element_handle.scroll_into_view_if_needed()
                
                # Try direct click first - most reliable for standard elements
                return await perform_click(lambda: element_handle.click(
                    force=False,  # Don't force click - let Playwright handle visibility checks
                    delay=10,      # Slight delay for more realistic clicking 
                    timeout=2000   # Generous timeout
                ))
            except URLNotAllowedError as e:
                raise e
            except Exception as e:
                logger.debug(f"Standard click failed: {str(e)}. Trying JS click.")
                try:
                    # If standard click fails, try JavaScript click
                    # This works better for some frameworks and custom elements
                    return await perform_click(lambda: page.evaluate('''(el) => {
                        // Dispatch proper mouse events before clicking for better compatibility
                        const rect = el.getBoundingClientRect();
                        const x = rect.left + rect.width / 2;
                        const y = rect.top + rect.height / 2;
                        
                        // Create and dispatch more realistic events
                        const mouseOverEvent = new MouseEvent('mouseover', {
                            bubbles: true,
                            cancelable: true,
                            view: window,
                            clientX: x,
                            clientY: y
                        });
                        el.dispatchEvent(mouseOverEvent);
                        
                        // Short delay
                        setTimeout(() => {
                            // Then click
                            el.click();
                        }, 10);
                    }''', element_handle))
                except URLNotAllowedError as e:
                    raise e
                except Exception as e:
                    raise Exception(f'All click methods failed: {str(e)}')

        except URLNotAllowedError as e:
            raise e
        except Exception as e:
            raise Exception(f'Failed to click element: {repr(element_node)}. Error: {str(e)}')

    async def human_like_typing(self, element_handle, text: str, min_delay: int = 50, max_delay: int = 150, reduced_randomness: bool = False):
        """
        Types text with random delays between keystrokes to simulate human typing.
        
        Args:
            element_handle: The playwright element handle to type into
            text: The text to type
            min_delay: Minimum delay between keystrokes in milliseconds
            max_delay: Maximum delay between keystrokes in milliseconds
            reduced_randomness: If True, uses more consistent timing for better reliability
        """
        if not element_handle:
            raise BrowserError("No element provided for typing")
        
        # Make sure the element is in focus
        try:
            await element_handle.focus()
        except Exception:
            pass
        
        # Adjust delay parameters for reduced randomness if needed
        if reduced_randomness:
            min_delay = max(min_delay, 30)  # Ensure minimum delay is reasonable
            max_delay = min(min_delay + 50, max_delay)  # Reduce variance
        
        # Type each character with random delay
        for char in text:
            # Calculate delay for this character
            delay = random.randint(min_delay, max_delay)
            
            # Type the character with the calculated delay
            try:
                await element_handle.type(char, delay=delay)
            except Exception:
                # If typing fails, try inserting the text directly
                try:
                    await element_handle.evaluate(f'el => {{el.value += "{char}";}}')
                except Exception:
                    # If all fails, continue to next character
                    pass
            
            # Add random longer pauses occasionally to simulate human thinking
            # Less frequent and shorter if reduced_randomness is True
            pause_chance = 0.05 if reduced_randomness else 0.1
            pause_max = 0.3 if reduced_randomness else 0.5
            
            if random.random() < pause_chance:
                await asyncio.sleep(random.uniform(0.1, pause_max))