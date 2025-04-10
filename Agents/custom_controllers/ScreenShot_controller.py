# controllers/screenshot_controller.py
from pydantic import BaseModel
from typing import Optional
from browser_use import ActionResult, Browser
import os
import base64
import json
from datetime import datetime
import websockets


class TakeScreenshotParams(BaseModel):
    """Parameters for taking a screenshot."""
    save_dir: str = "./screenshots"
    websocket_url: str = "ws://localhost:8765"
    filename_prefix: Optional[str] = "screenshot"
    quality: Optional[int] = 80
    full_page: Optional[bool] = True
    include_timestamp: Optional[bool] = True
    transmit: Optional[bool] = False  # NEW parameter


async def take_screenshot(params: TakeScreenshotParams, browser: Browser) -> ActionResult:
    """
    Takes a screenshot of the current page.
    - If `transmit` is False: saves to disk.
    - If `transmit` is True: sends via WebSocket.
    """
    try:
        # Create directory if saving locally
        if not params.transmit:
            os.makedirs(params.save_dir, exist_ok=True)
            print("Created screenshots dir!!!")
        
        # Get current page
        page = await browser.get_current_page()
        
        if not page:
            print("There was some problem while getting the page...")
            return ActionResult(success=False, message="No active page found")
        
        # Generate filename with timestamp if enabled
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S") if params.include_timestamp else ""
        filename = f"{params.filename_prefix}_{timestamp}.png" if params.include_timestamp else f"{params.filename_prefix}.png"
        file_path = os.path.join(params.save_dir, filename)

        print("Taking the screen shot!")
        # Take screenshot
        screenshot_buffer = await page.screenshot(
            path=file_path if not params.transmit else None,
            full_page=params.full_page,
            quality=params.quality if params.quality else None,
            type="png"
        )
        print("taken screen shot!!!!")
        websocket_status = False
        if params.transmit:
            base64_screenshot = base64.b64encode(screenshot_buffer).decode('utf-8')
            websocket_status = await send_via_websocket(
                params.websocket_url,
                {
                    "type": "screenshot",
                    "filename": filename,
                    "data": base64_screenshot,
                    "timestamp": datetime.now().isoformat(),
                    "url": await page.url()
                }
            )

        return ActionResult(
            success=True,
            message="Screenshot transmitted via WebSocket" if params.transmit else f"Screenshot saved at {file_path}",
            data={
                "file_path": file_path if not params.transmit else None,
                "websocket_sent": websocket_status,
                "url": await page.url()
            }
        )
        
    except Exception as e:
        return ActionResult(
            success=False,
            message=f"Error taking screenshot: {str(e)}"
        )


async def send_via_websocket(websocket_url: str, data: dict) -> bool:
    """Sends data to a WebSocket server."""
    try:
        async with websockets.connect(websocket_url) as websocket:
            await websocket.send(json.dumps(data))
            return True
    except Exception as e:
        print(f"WebSocket error: {e}")
        return False
