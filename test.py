import asyncio
import logging
from auth_manager import AuthenticationManager, AuthResult
# from form_manager import FormAgent, FormAgentConfig

async def test_normal_form_submission():
    logging.basicConfig(level=logging.INFO)
    _auth_manager = AuthenticationManager()  # Ensure this is properly configured
    try:
        result : AuthResult= await _auth_manager.authenticate("google")
        if result.success:
            print("Successfully loged into Google accounts.")
            print(f"The cookies are : {result.cookies}")
            
        else:
            print(f"There was some error while authenticating : {result.error}")
    except Exception as e:
        print(e)
        
    # config = FormAgentConfig(debug_mode=True, screenshot_dir="screenshots")
    # agent = FormAgent(auth_manager, config)

    # await agent.initialize()
    # success = await agent.navigate_to("http://example.com/form")

    # if success:
    #     form_data = {
    #         "username": "testuser",
    #         "password": "securepassword123",
    #         "email": "test@example.com"
    #     }
    #     filled = await agent.fill_form(form_data)
    #     assert filled, "Form filling failed"

    #     # submitted = await agent.submit_form()
    #     # assert submitted, "Form submission failed"

    #     result = await agent.wait_for_success_indicator(success_selector=".success-message")
    #     assert result["success"], f"Form submission was not successful: {result}"
    # else:
    #     assert False, "Navigation to form page failed"

    # await agent.close()

if __name__ == "__main__":
    asyncio.run(test_normal_form_submission())

# import asyncio
# from pyppeteer import launch

# async def main():
#     browser = None
#     try:
#         print("Launching browser...")
#         browser = await launch(
#             headless=False,
#             executablePath="C:/Program Files/Google/Chrome/Application/chrome.exe",
#             args=['--no-sandbox', '--disable-setuid-sandbox']
#         )
        
#         print("Opening page...")
#         page = await browser.newPage()
        
#         print("Navigating to Google...")
#         await page.goto('https://google.com')
        
#         print("Taking screenshot...")
#         await page.screenshot({'path': 'screenshot.png'})
        
#         print("Closing page...")
#         await page.close()
#     except Exception as e:
#         print(f"Error: {str(e)}")
#     finally:
#         if browser:
#             print("Closing browser...")
#             await browser.close()
#             print("Browser closed.")

# if __name__ == '__main__':
#     asyncio.run(main())