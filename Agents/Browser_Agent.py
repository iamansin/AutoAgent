from multiprocessing import context
from re import S
from browser_use import ActionResult, Agent, Browser, BrowserConfig
from browser_use.browser.context import BrowserContextConfig, BrowserContext
from typing import Optional, Union, Dict, Any, List, Tuple
import os
import asyncio
import logging
from datetime import datetime
import uuid
from langchain.chat_models.base import BaseChatModel
from browser_use.agent.views import AgentState
from Utils.stealth_browser.CustomBrowser import StealthBrowser
from .custom_controllers.base_controller import ControllerRegistry
# from Agents.custom_controllers.ScreenShot_controller import on_step_screenshot
from Utils.prompts import MySystemPrompt
from Utils.schemas import WebSocketMessage
import base64
from Utils.stealth_browser.CustomBrowserContext import ExtendedContext# Set up logging
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("BrowserAgentHandler")
# Global configuration variables
SAVE_DIR = "./agent_screenshots"
FILENAME_PREFIX = "screenshot"
INCLUDE_TIMESTAMP = False
INCLUDE_STEP_NUMBER = True
QUALITY = 80
FULL_PAGE = False
BATCH_FOLDER = None




    
class BrowserAgentHandler:
    """
    Singleton class that handles browser instances, contexts, and agents.
    
    This class manages a limited pool of browser instances, each with a maximum
    number of contexts. It ensures resource efficiency and provides mechanisms
    for user interaction during browser automation tasks.
    """
    
    # Singleton instance
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(BrowserAgentHandler, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(
        self,
        # ws_manager,
        llm_dict : Dict[str, BaseChatModel],
        max_browsers: int = 10,
        max_contexts_per_browser: int = 10,
        ss_interval : float = 2.5,
        browser_config: Optional[BrowserConfig] = None,
        context_config: Optional[BrowserContextConfig] = None,
        custom_controller: Optional[ControllerRegistry] = None,
        use_planner_model : bool = False,
        planner_model : str = None,
        on_step_screenshot : bool = True,
        current_context = None,
        use_agent_state : Optional[bool] = False,
        transmit_ss : bool = False,
        max_steps : int = 25,
        log_dir: str = "logs"
    ):
        """
        Initialize the BrowserAgentHandler with browser and context configurations.
        
        Args:
            max_browsers: Maximum number of browser instances allowed
            max_contexts_per_browser: Maximum contexts per browser instance
            browser_config: Configuration for the browser (optional)
            context_config: Configuration for the browser context (optional)
            custom_controller: Custom controller registry (optional)
            log_dir: Directory to store agent logs (default: "logs")
        """
        # Avoid re-initialization if already initialized
        if self._initialized:
            return
        
        # self.ws_manager = ws_manager
        self._max_browsers = max_browsers
        self._max_contexts_per_browser = max_contexts_per_browser
        self._browser_config = browser_config 
        self._context_config = context_config or BrowserContextConfig()
        self._ss_interval = ss_interval
        self._custom_controller = custom_controller
        self._log_dir = log_dir
        self._llm_dict =  llm_dict
        self._llm = [model for model in llm_dict.values()][0]
        self.use_agent_state = use_agent_state
        self.TRANSMIT = transmit_ss
        self.max_steps = max_steps
        # Map of browser instances and their contexts
        # {browser_id: {"browser": Browser, "contexts": {context_id: context_obj}}}
        self._current_context = current_context
        self._browsers = {}
        
        # Map of context_id to browser_id
        self._context_to_browser = {}
        
        # Map of context_id to agent
        self._context_to_agent = {}
        
        # Input queue for each context
        self._input_queues = {}
        
        self._use_planner_model = use_planner_model
        self.planner_model = planner_model
        self._on_step_screenshot = on_step_screenshot
        # Create logs directory if it doesn't exist
        # os.makedirs(self._log_dir, exist_ok=True)
        
        self._initialized = True
        logger.info(f"BrowserAgentHandler initialized with max {max_browsers} browsers, "
                   f"{max_contexts_per_browser} contexts per browser")
    
    async def _create_browser(self) -> str:
        """
        Create a new browser instance if the limit hasn't been reached.
        
        Returns:
            browser_id: Unique ID for the created browser
            
        Raises:
            RuntimeError: If maximum number of browsers is reached
        """
        if len(self._browsers) >= self._max_browsers:
            raise RuntimeError(f"Maximum number of browsers ({self._max_browsers}) reached")
        
        try:
            browser_id = str(uuid.uuid4())
            logger.info(f"Creating new browser with ID: {browser_id}")
            browser = StealthBrowser(config= self._browser_config)

            logger.info("Using Browser-use Browser!!!")
            self._browsers[browser_id] = {
                "browser": browser,
                "contexts": {}
            }
            
            logger.info(f"Browser {browser_id} created successfully")
            return browser_id
            
        except Exception as e:
            logger.error(f"Failed to create browser: {e}")
            raise RuntimeError(f"Browser creation failed: {e}")
    
    async def get_available_browser(self) -> str:
        """
        Get an available browser ID that can handle more contexts.
        Creates a new browser if needed.
        
        Returns:
            browser_id: ID of an available browser
            
        Raises:
            RuntimeError: If no browsers are available and max limit is reached
        """
        # Check existing browsers for available context slots
        if self._browsers:
            for browser_id, browser_data in self._browsers.items():
                if len(browser_data["contexts"]) < self._max_contexts_per_browser:
                    return browser_id
            
        # No available browsers, create a new one if possible
        return await self._create_browser()
    
    async def create_context(self, context_id: Optional[str] = None) -> str:
        """
        Create a new browser context in an available browser.
        
        Args:
            context_id: Optional custom ID for the context (generated if not provided)
            
        Returns:
            context_id: Unique ID for the created context
            
        Raises:
            RuntimeError: If no browsers are available or context creation fails
        """
        try:
            browser_id = await self.get_available_browser()
            
            # Generate context ID if not provided
            if not context_id:
                context_id = str(uuid.uuid4())
            
            logger.info(f"Creating context {context_id} in browser {browser_id}")
            
            # Create browser context
            browser : StealthBrowser = self._browsers[browser_id]["browser"]
            
            if self._on_step_screenshot:
                # current_context = browser.create_stealth_context()
                context = ExtendedContext(browser=browser,
                                          config=self._context_config)
                                        #   current_context=current_context)
                # context = BrowserContext(
                #     browser=browser,
                #     config=self._context_config
                # )
                logger.warning("Using Current context by Browser-use")
                
            # else:
            #     context = ExtendedBrowserContext(
            #         browser=browser,
            #         config=self._context_config,
            #         screenshot_dir=f"agent_screenshots/{context_id}",
            #         screenshot_interval=self._ss_interval,
            #         transmit=False,
            #         debug_level=logging.WARNING
            #     )
            #     logger.info(f"Now intialising BrowserContext : {context_id or 101}")
            #     await context.initialize()
                
            # Store context references
            self._browsers[browser_id]["contexts"][context_id] = context
            self._context_to_browser[context_id] = browser_id
            
            logger.info(f"Context {context_id} created successfully")
            return context_id
            
        except Exception as e:
            logger.error(f"Failed to create context: {e}")
            # Clean up any queues created
            if context_id in self._input_queues:
                del self._input_queues[context_id]
            raise RuntimeError(f"Context creation failed: {e}")
    
    async def get_context(self, context_id: str):
        """
        Get a browser context by ID.
        
        Args:
            context_id: ID of the context to retrieve
            
        Returns:
            The browser context object or None if not found
        """
        if context_id not in self._context_to_browser:
            logger.warning(f"Context {context_id} not found")
            logger.warning(f"Creating new Context with : {context_id}")
            id = await self.create_context(context_id=context_id)
            
        browser_id = self._context_to_browser[context_id]
        return self._browsers[browser_id]["contexts"].get(context_id)
    
    def set_up_callback(self, context_id :str):
        
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
                if self.TRANSMIT:
                    message = WebSocketMessage(
                        type="screenshot",
                        content={
                            "image": screenshot_b64,
                            "step": step,
                            "timestamp": timestamp,
                            "filename": filename
                        },
                        session_id=context_id
                    )
                    await self.ws_manager.send_message(message, context_id)

                logger.info(f"Screenshot saved successfully: {filename}")
                return True

            except Exception as e:
                logger.error(f"Error processing screenshot at step {step}: {e}")
                return False

        async def on_step_screenshot(state: Any, model_output: Any, step: int) -> None:
            """Handle screenshot processing for each step."""
            if hasattr(state, 'screenshot'):
                await save_and_transmit_screenshot(state.screenshot, step, BATCH_FOLDER)
                
        return on_step_screenshot
    
    async def create_agent(
        self,
        context_id: str,
        task: str,
        browser = None,
        use_vision: bool = True,
        agent_kwargs: Optional[Dict[str, Any]] = None,
        sensitive_data= None,
        last_result : Optional[List[ActionResult]] = None,
        next_action : Optional[str] = None
    ) -> Agent:
        """
        Create a Browser-Use agent for a specific context.
        
        Args:
            context_id: ID of the context to associate with the agent
            task: The task description for the agent
            llm: Language model to use for the agent
            use_vision: Whether to enable vision capabilities
            save_conversation: Whether to save the conversation logs
            agent_kwargs: Additional keyword arguments for the Agent constructor
            
        Returns:
            The created Agent instance
            
        Raises:
            ValueError: If context doesn't exist or already has an agent
            RuntimeError: If agent creation fails
        """
        # Check if context exists
        context = await self.get_context(context_id)
        if not context:
            raise ValueError(f"Context {context_id} does not exist")
        
        # # Check if context already has an agent
        # if context_id in self._context_to_agent:
        #     raise ValueError(f"Context {context_id} already has an associated agent")

        try:
            # Set up agent kwargs
            kwargs = {
                "task": task,
                "llm": self._llm,
                "use_vision": use_vision,
                # "browser" : browser,
                "browser_context": context,
                # "system_prompt_class" : MySystemPrompt,
                # "save_conversation_path" : "logs/conversation"
            }
            
            # Add controller if available
            if self._custom_controller:
                kwargs["controller"] = self._custom_controller 
                
            if self._use_planner_model:
                if self.planner_model:
                    kwargs["planner_llm"] = self._llm_dict[self.planner_model]
                else:
                    kwargs["planner_llm"] = next(iter(self._llm_dict.values()))
                    
            if self._on_step_screenshot:
                
                kwargs["register_new_step_callback"] = self.set_up_callback(context_id)
                
            if sensitive_data: 
                kwargs["sensitive_data"] = sensitive_data
                    
            if agent_kwargs:
                kwargs.update(agent_kwargs)
            
            if self.use_agent_state:
         
                kwargs["injected_agent_state"] = AgentState(
                    last_result= last_result if last_result else None,
                    last_plan= next_action
                )
            # Create the agent
            # logger.info(f"Creating agent for context {context_id} with task: {task}")
            agent = Agent(**kwargs)
            
            # # Store agent reference
            # self._context_to_agent[context_id] = agent
            
            return agent
            
        except Exception as e:
            logger.error(f"Failed to create agent for context {context_id}: {e}")
            raise RuntimeError(f"Agent creation failed: {e}")
    
    async def run_task(
        self,
        context_id: str,
        task: Optional[str] = None,
        browser = None,
        use_vision: bool = True,
        timeout: Optional[float] = None,
        agent_kwargs: Optional[Dict[str, Any]] = None,
        sensitive_data : Dict[str,Any] = None,
        last_result : Optional[List[ActionResult]] = None,
        next_action : Optional[str] = None
    ) -> Any:
        """
        Run a task with an existing or new agent for the specified context.
        
        Args:
            context_id: ID of the context
            task: Task description (optional if agent already exists)
            llm: Language model (required if creating new agent)
            use_vision: Whether to use vision capabilities
            timeout: Maximum time in seconds for task execution
            agent_kwargs: Additional agent configuration parameters
            
        Returns:
            The result of the agent's run
            
        Raises:
            ValueError: If insufficient parameters are provided
            RuntimeError: If task execution fails
        """
        try:
            # Get existing agent or create new one
            # agent = self._context_to_agent.get(context_id)
            
            if not task:
                raise ValueError("Task and LLM must be provided when creating a new agent")
          
            agent = await self.create_agent(
                    context_id=context_id,
                    task=task,
                    browser=browser,
                    use_vision=use_vision,
                    agent_kwargs=agent_kwargs,
                    sensitive_data =sensitive_data,
                    last_result = last_result,
                    next_action = next_action
                )
            

            # Run the agent with timeout if specified
            if timeout:
                result = await asyncio.wait_for(agent.run(max_steps=self.max_steps), timeout=timeout)
            else:
                result = await agent.run(max_steps=self.max_steps)
                
            logger.info(f"Agent for context {context_id} completed task successfully")
            return result
            
        except asyncio.TimeoutError:
            logger.error(f"Task execution for context {context_id} timed out after {timeout} seconds")
            raise RuntimeError(f"Task execution timed out after {timeout} seconds")
        except Exception as e:
            logger.error(f"Error during task execution for context {context_id}: {e}")
            raise RuntimeError(f"Task execution failed: {e}")
    
    async def close_context(self, context_id: str) -> bool:
        """
        Close a specific browser context and clean up resources.
        
        Args:
            context_id: ID of the context to close
            
        Returns:
            True if successful, False if context not found
        """
        if context_id not in self._context_to_browser:
            logger.warning(f"Context {context_id} not found for closing")
            return False
            
        try:
            browser_id = self._context_to_browser[context_id]
            context = self._browsers[browser_id]["contexts"].get(context_id)
            
            if context:
                logger.info(f"Closing context {context_id}...")
                await context.close()
                
                # Clean up references
                del self._browsers[browser_id]["contexts"][context_id]
                del self._context_to_browser[context_id]
                
                if context_id in self._context_to_agent:
                    del self._context_to_agent[context_id]
                    
                # if context_id in self._input_queues:
                #     del self._input_queues[context_id]
                    
                logger.info(f"Context {context_id} closed and resources cleaned up")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Error closing context {context_id}: {e}")
            return False
    
    async def close_browser(self, browser_id: str) -> bool:
        """
        Close a specific browser and all its contexts.
        
        Args:
            browser_id: ID of the browser to close
            
        Returns:
            True if successful, False if browser not found
        """
        if browser_id not in self._browsers:
            logger.warning(f"Browser {browser_id} not found for closing")
            return False
            
        try:
            # Close all contexts first
            contexts = list(self._browsers[browser_id]["contexts"].keys())
            for context_id in contexts:
                await self.close_context(context_id)
                
            # Close the browser
            browser = self._browsers[browser_id]["browser"]
            logger.info(f"Closing browser {browser_id}...")
            await browser.close()
            
            # Clean up references
            del self._browsers[browser_id]
            
            logger.info(f"Browser {browser_id} closed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error closing browser {browser_id}: {e}")
            return False
    
    async def close_all(self) -> None:
        """
        Close all browsers and clean up all resources.
        """
        try:
            browser_ids = list(self._browsers.keys())
            for browser_id in browser_ids:
                await self.close_browser(browser_id)
                
            logger.info("All browsers and resources cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def _get_timestamp_path(self, base_path: str) -> str:
        """
        Generate a timestamped path for logs.
        
        Args:
            base_path: Base directory for logs
            
        Returns:
            Path with timestamp appended
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{base_path}_{timestamp}"
    
    def has_pending_input_requests(self, context_id: str) -> bool:
        """
        Check if a context has pending input requests.
        
        Args:
            context_id: ID of the context to check
            
        Returns:
            True if there are pending input requests, False otherwise
        """
        if context_id in self._input_queues:
            return True
        else:
            return False
    
    async def __aenter__(self):
        """
        Async context manager entry.
        """
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Async context manager exit.
        """
        await self.close_all()