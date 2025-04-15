from typing import Optional, Any
from browser_use import ActionResult, Browser
import os
import base64
import json
from datetime import datetime
import websockets
from Utils.websocket_manager import ws_manager, WebSocketMessage
import uuid
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AutoAgent")

# Global configuration variables
SAVE_DIR = "./agent_screenshots"
FILENAME_PREFIX = "screenshot"
INCLUDE_TIMESTAMP = False
TRANSMIT = True
INCLUDE_STEP_NUMBER = True
QUALITY = 80
FULL_PAGE = False
BATCH_FOLDER = None

def setup_directories(batch_folder: Optional[str] = None) -> str:
    """Set up and return the directory path for saving screenshots."""
    save_path = SAVE_DIR
    if batch_folder:
        save_path = os.path.join(SAVE_DIR, batch_folder)
    os.makedirs(save_path, exist_ok=True)
    return save_path

async def save_and_transmit_screenshot(screenshot_b64: str, step: int, batch_folder: Optional[str] = None) -> bool:
    """Save screenshot to file and transmit via WebSocket if enabled."""
    try:
        if not screenshot_b64:
            return False

        save_path = setup_directories(batch_folder)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{FILENAME_PREFIX}_step{step}_{timestamp}.png"
        filepath = os.path.join(save_path, filename)

        # Save to file
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(screenshot_b64))

        # Transmit via WebSocket if enabled
        if TRANSMIT:
            message = WebSocketMessage(
                type="screenshot",
                content={
                    "image": screenshot_b64,
                    "step": step,
                    "timestamp": timestamp,
                    "filename": filename
                },
                session_id="10"
            )
            await ws_manager.send_message(message, "10")

        logger.info(f"Screenshot saved successfully: {filename}")
        return True

    except Exception as e:
        logger.error(f"Error processing screenshot at step {step}: {e}")
        return False

async def on_step_screenshot(state: Any, model_output: Any, step: int) -> None:
    """Handle screenshot processing for each step."""
    if hasattr(state, 'screenshot'):
        await save_and_transmit_screenshot(state.screenshot, step, BATCH_FOLDER)


