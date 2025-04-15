from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class StealthConfig:
    """Configuration for browser stealth settings"""
    enable_stealth: bool = True
    # Viewport and window settings
    random_viewport: bool = True  # Randomize viewport dimensions
    min_viewport_width: int = 1024
    max_viewport_width: int = 1920
    min_viewport_height: int = 768
    max_viewport_height: int = 1080
    
    # User agent settings
    random_user_agent: bool = True
    user_agent_template: str = "Mozilla/5.0 ({os}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36"
    
    # Browser behavior
    enable_webgl: bool = True  # Some sites check WebGL fingerprint
    emulate_plugins: bool = True  # Emulate common plugins
    emulate_webgl_vendor: str = "Google Inc. (Intel)"  # Specific WebGL vendor
    touch_events: bool = True  # Emulate touch events support
    
    # Performance and timing settings
    random_timing: bool = True  # Add random delays to actions
    min_delay: float = 0.5  # Minimum delay in seconds
    max_delay: float = 2.0  # Maximum delay in seconds
    
    # Additional fingerprint settings
    languages: list[str] = ("en-US", "en")
    platform: str = "Win32"
    enable_audio: bool = True