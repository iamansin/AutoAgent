import asyncio
import logging
from typing import Dict, List, Optional, Any, Union, Set
import re
import json
import os
import time
from datetime import datetime
from enum import Enum

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from auth_manager import AuthenticationManager, AuthResult
from Utils.CustomBrowser import BrowserOptions


class FormField:
    """Represents a form field with its properties and validations."""
    
    def __init__(
        self,
        name: str,
        selector: str,
        field_type: str = "text", 
        required: bool = False,
        validation: Optional[str] = None,
        options: Optional[List[str]] = None,
        default_value: Optional[str] = None
    ):
        self.name = name
        self.selector = selector
        self.field_type = field_type  # text, select, checkbox, radio, etc.
        self.required = required
        self.validation = validation  # regex pattern or function name
        self.options = options  # for select, radio, checkbox groups
        self.default_value = default_value


class FormManagerConfig:
    """Configuration for the form agent."""
    
    def __init__(
        self,
        timeout: int = 30,
        retry_attempts: int = 3,
        retry_delay: int = 2,
        screenshot_dir: Optional[str] = None,
        debug_mode: bool = False,
        auto_submit: bool = False,
        wait_after_fill: int = 0
    ):
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.screenshot_dir = screenshot_dir
        self.debug_mode = debug_mode
        self.auto_submit = auto_submit
        self.wait_after_fill = wait_after_fill  # Seconds to wait after filling before submission
        
        # Create screenshot directory if specified
        if self.screenshot_dir and not os.path.exists(self.screenshot_dir):
            os.makedirs(self.screenshot_dir, exist_ok=True)


class FormManager:
    """
    Agent for automating form filling tasks.
    
    This class handles navigation, form detection, filling and submission while 
    utilizing the authentication system to maintain a persistent session.
    """
    
    def __init__(
        self,
        auth_manager: AuthenticationManager,
        config: Optional[FormManagerConfig] = None
    ):
        self.auth_manager = auth_manager
        self.config = config or FormManagerConfig()
        self.logger = logging.getLogger(__name__)
        self.page: Optional[Page] = None
        self._initialised: bool = False
    
    async def initialize(self) -> None:
        """Initialize the agent if not already initialized."""
        if not self.page:
            # Get a page from the browser manager
            self.page = await self.auth_manager.get_browser_page()
            self._initialised = True
            self.logger.info("Form agent initialized with a new page")
    
    async def navigate_to(self, url: str) -> bool:
        """
        Navigate to the specified URL.
        
        Args:
            url (str): The URL to navigate to.
            
        Returns:
            bool: True if navigation was successful, False otherwise.
            
        """
        
        if not self._initialised:
            await self.initialize()
        
        try:
            self.logger.info(f"Navigating to {url}")
            response = await self.page.goto(url, wait_until="networkidle", timeout=self.config.timeout * 1000)
            
            if not response.ok:
                self.logger.error(f"Navigation failed: {response.status} {response.status_text}")
                if self.config.debug_mode and self.config.screenshot_dir:
                    await self._take_screenshot("navigation_error")
                return False
                
            self.logger.info(f"Successfully navigated to {url}")
            return True
        except PlaywrightTimeoutError:
            self.logger.error(f"Navigation timeout: {url}")
            if self.config.debug_mode and self.config.screenshot_dir:
                await self._take_screenshot("navigation_timeout")
            return False
        except Exception as e:
            self.logger.error(f"Navigation error: {str(e)}")
            if self.config.debug_mode and self.config.screenshot_dir:
                await self._take_screenshot("navigation_exception")
            return False
    
    async def detect_form(self, form_selector: str = "form") -> Optional[Dict[str, FormField]]:
        """
        Detect form fields on the current page.
        
        Args:
            form_selector (str): CSS selector for the form.
            
        Returns:
            Optional[Dict[str, FormField]]: Dictionary of detected form fields or None if form not found.
        """
        if not self._initialised:
            await self.initialize()
        
        try:
            # Check if form exists
            form_exists = await self.page.evaluate(f'!!document.querySelector("{form_selector}")')
            if not form_exists:
                self.logger.warning(f"No form found with selector: {form_selector}")
                return None
                
            # Get all input, select, and textarea elements within the form
            form_elements = await self.page.evaluate(f'''() => {{
                const form = document.querySelector("{form_selector}");
                const elements = Array.from(form.querySelectorAll('input, select, textarea'));
                
                return elements.map(el => {{
                    const name = el.name || el.id || '';
                    const type = el.type || el.tagName.toLowerCase();
                    const required = el.required || false;
                    const placeholder = el.placeholder || '';
                    const selector = el.tagName.toLowerCase() + 
                        (el.id ? '#' + el.id : '') + 
                        (el.name ? '[name="' + el.name + '"]' : '');
                    
                    let options = null;
                    if (el.tagName.toLowerCase() === 'select') {{
                        options = Array.from(el.options).map(opt => opt.value);
                    }}
                    
                    return {{
                        name,
                        type,
                        required,
                        placeholder,
                        selector,
                        options
                    }};
                }}).filter(el => el.name || el.selector); // Filter out elements without name or selector
            }}''')
            
            # Convert to FormField objects
            detected_fields = {}
            for element in form_elements:
                field = FormField(
                    name=element['name'],
                    selector=element['selector'],
                    field_type=element['type'],
                    required=element['required'],
                    options=element['options']
                )
                detected_fields[element['name']] = field
                
            self.logger.info(f"Detected {len(detected_fields)} form fields")
            return detected_fields
        except Exception as e:
            self.logger.error(f"Error detecting form: {str(e)}")
            if self.config.debug_mode and self.config.screenshot_dir:
                await self._take_screenshot("form_detection_error")
            return None
    
    async def fill_form(
        self, 
        form_data: Dict[str, Any], 
        form_selector: str = "form",
        submit_selector: Optional[str] = None
    ) -> bool:
        """
        Fill form with provided data and optionally submit it.
        
        Args:
            form_data (Dict[str, Any]): Dictionary mapping field names to values.
            form_selector (str): CSS selector for the form.
            submit_selector (Optional[str]): CSS selector for the submit button.
            
        Returns:
            bool: True if form filling and submission was successful, False otherwise.
        """
        if not self._initialised:
            await self.initialize()
        
        try:
            # Detect the form first to get field details
            form_fields = await self.detect_form(form_selector)
            if not form_fields:
                self.logger.error("Cannot fill form: No form detected")
                return False
                
            # Fill each field based on its type
            for field_name, value in form_data.items():
                if field_name in form_fields:
                    field = form_fields[field_name]
                    await self._fill_field(field, value)
                else:
                    self.logger.warning(f"Field not found in form: {field_name}")
            
            # Take screenshot after filling if debug mode
            if self.config.debug_mode and self.config.screenshot_dir:
                await self._take_screenshot("after_form_fill")
                
            # Wait if configured
            if self.config.wait_after_fill > 0:
                await asyncio.sleep(self.config.wait_after_fill)
            
            # Submit the form if auto-submit is enabled or submit_selector is provided
            if self.config.auto_submit or submit_selector:
                return await self.submit_form(form_selector, submit_selector)
                
            return True
        except Exception as e:
            self.logger.error(f"Error filling form: {str(e)}")
            if self.config.debug_mode and self.config.screenshot_dir:
                await self._take_screenshot("form_fill_error")
            return False
    
    async def _fill_field(self, field: FormField, value: Any) -> None:
        """
        Fill a specific form field with the provided value.
        
        Args:
            field (FormField): The field to fill.
            value (Any): The value to fill the field with.
        """
        # Wait for the field to be available
        try:
            await self.page.wait_for_selector(field.selector, timeout=self.config.timeout * 1000)
        except PlaywrightTimeoutError:
            self.logger.warning(f"Field selector timed out: {field.selector}")
            return
            
        try:
            field_type = field.field_type.lower()
            
            # Handle different field types
            if field_type in ('text', 'email', 'password', 'tel', 'url', 'number', 'search'):
                # Clear existing value first
                await self.page.evaluate(f'document.querySelector("{field.selector}").value = ""')
                # Type new value
                await self.page.fill(field.selector, str(value))
                self.logger.info(f"Filled text field: {field.name}")
                
            elif field_type == 'textarea':
                # Clear existing value is handled by fill in Playwright
                await self.page.fill(field.selector, str(value))
                self.logger.info(f"Filled textarea: {field.name}")
                
            elif field_type == 'select-one':
                # Select option in Playwright
                await self.page.select_option(field.selector, value=str(value))
                self.logger.info(f"Selected option in select: {field.name}")
                
            elif field_type == 'checkbox':
                # Set checkbox state in Playwright
                current_state = await self.page.evaluate(f'document.querySelector("{field.selector}").checked')
                if (value and not current_state) or (not value and current_state):
                    await self.page.check(field.selector) if value else await self.page.uncheck(field.selector)
                self.logger.info(f"Toggled checkbox: {field.name}")
                
            elif field_type == 'radio':
                # Click the radio button
                await self.page.check(field.selector)
                self.logger.info(f"Selected radio button: {field.name}")
                
            elif field_type == 'file':
                # Upload file in Playwright
                await self.page.set_input_files(field.selector, value)
                self.logger.info(f"Uploaded file to: {field.name}")
                
            elif field_type == 'date':
                # Clear existing value
                await self.page.evaluate(f'document.querySelector("{field.selector}").value = ""')
                # Set date value
                await self.page.fill(field.selector, str(value))
                self.logger.info(f"Set date for: {field.name}")
                
            else:
                # Default to setting value via JavaScript for other field types
                await self.page.evaluate(f'''
                    document.querySelector("{field.selector}").value = "{value}";
                ''')
                self.logger.info(f"Set value for field: {field.name}")
                
        except Exception as e:
            self.logger.error(f"Error filling field {field.name}: {str(e)}")
            if self.config.debug_mode and self.config.screenshot_dir:
                await self._take_screenshot(f"field_error_{field.name}")

    async def submit_form(
        self, 
        form_selector: str = "form", 
        submit_selector: Optional[str] = None
    ) -> bool:
        """
        Submit the form and wait for navigation to complete.
        
        Args:
            form_selector (str): CSS selector for the form.
            submit_selector (Optional[str]): CSS selector for the submit button.
                If None, the form will be submitted via JavaScript.
                
        Returns:
            bool: True if submission was successful, False otherwise.
        """
        await self.initialize()
        
        try:
            # First check if the form exists
            form_exists = await self.page.evaluate(f'!!document.querySelector("{form_selector}")')
            if not form_exists:
                self.logger.warning(f"Cannot submit: Form not found with selector: {form_selector}")
                return False
            
            # Take screenshot before submission if debug mode
            if self.config.debug_mode and self.config.screenshot_dir:
                await self._take_screenshot("before_submit")
            
            try:
                # Submit the form with wait_for_navigation
                if submit_selector:
                    # Find and click the submit button
                    button_exists = await self.page.evaluate(f'!!document.querySelector("{submit_selector}")')
                    if not button_exists:
                        self.logger.warning(f"Submit button not found: {submit_selector}")
                        return False
                        
                    self.logger.info(f"Clicking submit button: {submit_selector}")
                    # In Playwright, we can wait for navigation after the click
                    await self.page.click(submit_selector)
                    await self.page.wait_for_load_state("networkidle", timeout=self.config.timeout * 1000)
                else:
                    # Submit via JavaScript
                    self.logger.info("Submitting form via JavaScript")
                    await self.page.evaluate(f'document.querySelector("{form_selector}").submit()')
                    await self.page.wait_for_load_state("networkidle", timeout=self.config.timeout * 1000)
                
                self.logger.info("Form submitted successfully")
                
                # Take screenshot after submission if debug mode
                if self.config.debug_mode and self.config.screenshot_dir:
                    await self._take_screenshot("after_submit")
                    
                return True
            except PlaywrightTimeoutError:
                self.logger.warning("Form submission timed out waiting for navigation")
                if self.config.debug_mode and self.config.screenshot_dir:
                    await self._take_screenshot("submit_timeout")
                return False
                
        except Exception as e:
            self.logger.error(f"Error submitting form: {str(e)}")
            if self.config.debug_mode and self.config.screenshot_dir:
                await self._take_screenshot("submit_error")
            return False

    async def wait_for_success_indicator(
        self, 
        success_selector: str,
        error_selector: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Wait for success or error indicators after form submission.
        
        Args:
            success_selector (str): CSS selector for the success indicator.
            error_selector (Optional[str]): CSS selector for the error indicator.
            timeout (Optional[int]): Custom timeout in seconds.
            
        Returns:
            Dict[str, Any]: Results containing success status and any messages.
        """
        await self.initialize()
        
        timeout = timeout or self.config.timeout
        result = {
            'success': False,
            'message': None,
            'errors': []
        }
        
        try:
            # In Playwright, we need to use a different approach for waiting for multiple selectors
            combined_selector = f"{success_selector}, {error_selector}" if error_selector else success_selector
            
            # Wait for either selector to appear
            try:
                element = await self.page.wait_for_selector(combined_selector, timeout=timeout * 1000)
                
                # Determine which selector matched
                is_success = await element.evaluate(f'(el) => el.matches("{success_selector}")')
                
                if is_success:
                    # Success case
                    result['success'] = True
                    success_text = await element.inner_text()
                    result['message'] = success_text.strip()
                    self.logger.info(f"Form submission successful: {success_text}")
                elif error_selector:
                    # Error case - confirm it's the error selector
                    is_error = await element.evaluate(f'(el) => el.matches("{error_selector}")')
                    if is_error:
                        error_text = await element.inner_text()
                        result['message'] = error_text.strip()
                        result['errors'].append(error_text.strip())
                        self.logger.warning(f"Form submission error: {error_text}")
                    
            except PlaywrightTimeoutError:
                self.logger.warning(f"Timed out waiting for success/error indicator")
                result['message'] = "Timed out waiting for result"
                    
            # Take screenshot if debug mode
            if self.config.debug_mode and self.config.screenshot_dir:
                await self._take_screenshot(
                    "success_indicator" if result['success'] else "error_indicator"
                )
                
            return result
        except Exception as e:
            self.logger.error(f"Error waiting for result: {str(e)}")
            if self.config.debug_mode and self.config.screenshot_dir:
                await self._take_screenshot("indicator_error")
            result['message'] = f"Error: {str(e)}"
            return result

    async def extract_form_errors(self, error_selector: str = ".error, .form-error") -> List[str]:
        """
        Extract form validation errors from the page.
        
        Args:
            error_selector (str): CSS selector for error messages.
            
        Returns:
            List[str]: List of error messages.
        """
        await self.initialize()
        
        try:
            # Check if there are any error elements
            error_elements = await self.page.query_selector_all(error_selector)
            if not error_elements:
                return []
            
            # Extract error messages
            errors = []
            for element in error_elements:
                text = await element.inner_text()
                errors.append(text.strip())
            
            if errors:
                self.logger.warning(f"Found form errors: {errors}")
                if self.config.debug_mode and self.config.screenshot_dir:
                    await self._take_screenshot("form_errors")
                    
            return errors
        except Exception as e:
            self.logger.error(f"Error extracting form errors: {str(e)}")
            return []

    async def _take_screenshot(self, name_prefix: str) -> Optional[str]:
        """
        Take a screenshot of the current page state.
        
        Args:
            name_prefix (str): Prefix for the screenshot filename.
            
        Returns:
            Optional[str]: Path to the saved screenshot or None if failed.
        """
        if not self.config.screenshot_dir:
            return None
            
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{name_prefix}_{timestamp}.png"
            filepath = os.path.join(self.config.screenshot_dir, filename)
            
            # In Playwright, screenshot takes a path parameter directly
            await self.page.screenshot(path=filepath, full_page=True)
            self.logger.info(f"Screenshot saved: {filepath}")
            return filepath
        except Exception as e:
            self.logger.error(f"Error taking screenshot: {str(e)}")
            return None

    async def close(self) -> None:
        """Close the page and clean up resources."""
        if self.page:
            try:
                await self.page.close()
                self.logger.info("Form agent page closed")
            except Exception as e:
                self.logger.error(f"Error closing page: {str(e)}")
            finally:
                self.page = None