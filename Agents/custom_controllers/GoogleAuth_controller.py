from browser_use import ActionResult
import asyncio 
async def get_user_info(prompt : str) -> ActionResult:
    """This method takes prompt about the information need by the AI Agent to perform task."""
    print(f"The agent wants to know: {prompt}")
    info = {"user_email":"amanragu2003@gmail.com"}
    return ActionResult(extracted_content="Not able to find and saved info end the task and prompt the user for the information")