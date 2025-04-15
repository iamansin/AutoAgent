import random
import time
import json
from typing import Optional
import asyncio
from playwright.async_api import Page, BrowserContext as PlaywrightContext

class BrowserStealth:
    def __init__(self, config: StealthConfig):
        self.config = config
        self._user_agents = self._load_user_agents()
        
    def _load_user_agents(self) -> list[str]:
        """Load modern user agents"""
        return [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            # Add more recent user agents here
        ]

    async def apply_stealth(self, context: PlaywrightContext, page: Page):
        """Apply all stealth techniques to the page"""
        await self._inject_stealth_scripts(page)
        await self._emulate_plugins(page)
        await self._setup_navigator_properties(page)
        await self._setup_webgl(page)
        await self._randomize_viewport(page)
        await self._setup_media_codecs(page)
        await self._emulate_permissions(context)
        await self._setup_browser_apis(page)

    async def _inject_stealth_scripts(self, page: Page):
        """Inject scripts to modify browser fingerprinting properties"""
        await page.add_init_script("""
            // Override property getters
            const overridePropertyDescriptor = (obj, prop, valueOrGetter) => {
                Object.defineProperty(obj, prop, {
                    get() {
                        if (typeof valueOrGetter === 'function') return valueOrGetter();
                        return valueOrGetter;
                    }
                });
            };

            // Modify navigator properties
            overridePropertyDescriptor(Navigator.prototype, 'webdriver', false);
            overridePropertyDescriptor(Navigator.prototype, 'hardwareConcurrency', () => Math.floor(Math.random() * 8) + 4);
            overridePropertyDescriptor(Navigator.prototype, 'deviceMemory', () => Math.floor(Math.random() * 8) + 4);
            
            // Override permissions query
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = async (parameters) => {
                if (parameters.name === 'notifications' || parameters.name === 'clipboard-read') {
                    return { state: "prompt", addEventListener: () => {} };
                }
                return originalQuery.call(window.navigator.permissions, parameters);
            };

            // Modify performance behavior
            const originalGetEntries = Performance.prototype.getEntries;
            Performance.prototype.getEntries = function() {
                const entries = originalGetEntries.apply(this, arguments);
                return entries.map(entry => {
                    if (entry.entryType === 'navigation') {
                        entry.timeOrigin += Math.random() * 100;
                    }
                    return entry;
                });
            };
        """)

    async def _emulate_plugins(self, page: Page):
        """Emulate common browser plugins"""
        if self.config.emulate_plugins:
            await page.add_init_script("""
                Object.defineProperty(navigator, 'plugins', {
                    get: () => {
                        const ChromePDFPlugin = { description: "Portable Document Format", filename: "internal-pdf-viewer", name: "Chrome PDF Plugin", MimeTypes: [] };
                        const ChromePDFViewer = { description: "", filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai", name: "Chrome PDF Viewer", MimeTypes: [] };
                        const NativeClient = { description: "", filename: "internal-nacl-plugin", name: "Native Client", MimeTypes: [] };
                        
                        return Object.freeze([ChromePDFPlugin, ChromePDFViewer, NativeClient]);
                    }
                });
            """)

    async def _setup_navigator_properties(self, page: Page):
        """Setup various navigator properties"""
        await page.add_init_script("""
            const randomValues = {
                maxTouchPoints: Math.floor(Math.random() * 5) + 1,
                hardwareConcurrency: Math.floor(Math.random() * 8) + 4,
                deviceMemory: Math.floor(Math.random() * 8) + 4,
            };

            Object.defineProperties(navigator, {
                maxTouchPoints: { get: () => randomValues.maxTouchPoints },
                hardwareConcurrency: { get: () => randomValues.hardwareConcurrency },
                deviceMemory: { get: () => randomValues.deviceMemory },
                appVersion: { get: () => '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' },
                platform: { get: () => 'Win32' },
            });
        """)

    async def _setup_webgl(self, page: Page):
        """Setup WebGL to avoid fingerprinting"""
        if self.config.enable_webgl:
            await page.add_init_script("""
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    // Spoof renderer info
                    if (parameter === 37445) return 'Intel Inc.';
                    if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                    return getParameter.apply(this, arguments);
                };
            """)

    async def _randomize_viewport(self, page: Page):
        """Set random viewport dimensions"""
        if self.config.random_viewport:
            width = random.randint(self.config.min_viewport_width, self.config.max_viewport_width)
            height = random.randint(self.config.min_viewport_height, self.config.max_viewport_height)
            await page.set_viewport_size({"width": width, "height": height})

    async def _setup_media_codecs(self, page: Page):
        """Emulate common media codecs"""
        await page.add_init_script("""
            // Override media capabilities
            if (navigator.mediaCapabilities) {
                const originalDecodingInfo = navigator.mediaCapabilities.decodingInfo;
                navigator.mediaCapabilities.decodingInfo = async function(config) {
                    const response = await originalDecodingInfo.call(navigator.mediaCapabilities, config);
                    response.supported = true;
                    response.smooth = true;
                    response.powerEfficient = true;
                    return response;
                };
            }
        """)

    async def _emulate_permissions(self, context: PlaywrightContext):
        """Setup default permissions"""
        permissions = [
            'geolocation',
            'notifications',
            'clipboard-read',
            'clipboard-write',
        ]
        for permission in permissions:
            try:
                await context.grant_permissions([permission])
            except:
                pass

    async def _setup_browser_apis(self, page: Page):
        """Setup various browser APIs to appear more human-like"""
        await page.add_init_script("""
            // Add fake battery API
            if (!navigator.getBattery) {
                navigator.getBattery = async () => ({
                    charging: true,
                    chargingTime: Infinity,
                    dischargingTime: Infinity,
                    level: 0.95,
                    addEventListener: () => {},
                });
            }

            // Add browser automation objects to make it look more like a real browser
            window.chrome = {
                app: {
                    InstallState: {
                        DISABLED: 'DISABLED',
                        INSTALLED: 'INSTALLED',
                        NOT_INSTALLED: 'NOT_INSTALLED'
                    },
                    RunningState: {
                        CANNOT_RUN: 'CANNOT_RUN',
                        READY_TO_RUN: 'READY_TO_RUN',
                        RUNNING: 'RUNNING'
                    },
                    getDetails: function() {},
                    getIsInstalled: function() {},
                    installState: function() {},
                    isInstalled: false,
                    runningState: function() {}
                },
                runtime: {
                    OnInstalledReason: {
                        CHROME_UPDATE: 'chrome_update',
                        INSTALL: 'install',
                        SHARED_MODULE_UPDATE: 'shared_module_update',
                        UPDATE: 'update'
                    },
                    OnRestartRequiredReason: {
                        APP_UPDATE: 'app_update',
                        OS_UPDATE: 'os_update',
                        PERIODIC: 'periodic'
                    },
                    PlatformArch: {
                        ARM: 'arm',
                        ARM64: 'arm64',
                        MIPS: 'mips',
                        MIPS64: 'mips64',
                        X86_32: 'x86-32',
                        X86_64: 'x86-64'
                    },
                    PlatformNaclArch: {
                        ARM: 'arm',
                        MIPS: 'mips',
                        MIPS64: 'mips64',
                        X86_32: 'x86-32',
                        X86_64: 'x86-64'
                    },
                    PlatformOs: {
                        ANDROID: 'android',
                        CROS: 'cros',
                        LINUX: 'linux',
                        MAC: 'mac',
                        OPENBSD: 'openbsd',
                        WIN: 'win'
                    },
                    RequestUpdateCheckStatus: {
                        NO_UPDATE: 'no_update',
                        THROTTLED: 'throttled',
                        UPDATE_AVAILABLE: 'update_available'
                    }
                }
            };
        """)

    async def random_delay(self):
        """Add random delay between actions"""
        if self.config.random_timing:
            delay = random.uniform(self.config.min_delay, self.config.max_delay)
            await asyncio.sleep(delay)

    def get_random_user_agent(self) -> str:
        """Get a random user agent from the list"""
        if self.config.random_user_agent:
            return random.choice(self._user_agents)
        return self._user_agents[0]