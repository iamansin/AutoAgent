from browser_use import Agent, Controller, Browser, BrowserConfig
from browser_use.browser.context import BrowserContextConfig
from typing import Optional, Union, Dict, Any, List, Tuple
import os
import asyncio
import logging
from datetime import datetime
import uuid
from asyncio import Future, Queue
from Utils.CustomBrowserContext import ExtendedBrowserContext
from .custom_controllers.base_controller import ControllerRegistry

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("BrowserAgentHandler")

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
        max_browsers: int = 10,
        max_contexts_per_browser: int = 10,
        browser_config: Optional[BrowserConfig] = None,
        context_config: Optional[BrowserContextConfig] = None,
        custom_controller: Optional[ControllerRegistry] = None,
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
            
        self._max_browsers = max_browsers
        self._max_contexts_per_browser = max_contexts_per_browser
        self._browser_config = browser_config if browser_config else BrowserConfig()
        self._context_config = context_config if context_config else BrowserContextConfig()
        self._custom_controller = custom_controller
        self._log_dir = log_dir
        
        # Map of browser instances and their contexts
        # {browser_id: {"browser": Browser, "contexts": {context_id: context_obj}}}
        self._browsers = {}
        
        # Map of context_id to browser_id
        self._context_to_browser = {}
        
        # Map of context_id to agent
        self._context_to_agent = {}
        
        # Input queue for each context
        self._input_queues = {}
        
        # Create logs directory if it doesn't exist
        os.makedirs(self._log_dir, exist_ok=True)
        
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
            
            browser = Browser(self._browser_config)
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
            
            # Create input queue for this context
            self._input_queues[context_id] = Queue()
            
            logger.info(f"Creating context {context_id} in browser {browser_id}")
            
            # Create browser context
            browser = self._browsers[browser_id]["browser"]
            context = ExtendedBrowserContext(
                browser=browser,
                config=self._context_config,
                screenshot_dir=f"agent_screenshots/{context_id}",
                screenshot_interval=1.9,
                transmit=False,
                debug_level=logging.WARNING
            )
            
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
    
    def get_context(self, context_id: str) -> Optional[ExtendedBrowserContext]:
        """
        Get a browser context by ID.
        
        Args:
            context_id: ID of the context to retrieve
            
        Returns:
            The browser context object or None if not found
        """
        if context_id not in self._context_to_browser:
            logger.warning(f"Context {context_id} not found")
            return None
            
        browser_id = self._context_to_browser[context_id]
        return self._browsers[browser_id]["contexts"].get(context_id)
    
    async def create_agent(
        self,
        context_id: str,
        task: str,
        llm: Any,
        use_vision: bool = True,
        save_conversation: bool = True,
        agent_kwargs: Optional[Dict[str, Any]] = None
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
        context = self.get_context(context_id)
        if not context:
            raise ValueError(f"Context {context_id} does not exist")
        
        # Check if context already has an agent
        if context_id in self._context_to_agent:
            raise ValueError(f"Context {context_id} already has an associated agent")
        
        try:
            # Set up agent kwargs
            kwargs = {
                "task": task,
                "llm": llm,
                "use_vision": use_vision,
                "browser_context": context
            }
            
            # Add controller if available
            if self._custom_controller:
                kwargs["controller"] = self._custom_controller
            
            # # Add conversation logging if enabled
            # if save_conversation:
            #     conversation_path = self._get_timestamp_path(f"{self._log_dir}/{context_id}_conversation")
            #     kwargs["save_conversation_path"] = conversation_path
            
            # Add custom callback for input handling
            # kwargs["custom_callback"] = self._create_input_callback(context_id)
            
            # Add any additional kwargs
            if agent_kwargs:
                kwargs.update(agent_kwargs)
            
            # Create the agent
            logger.info(f"Creating agent for context {context_id} with task: {task}")
            agent = Agent(**kwargs)
            
            # Store agent reference
            self._context_to_agent[context_id] = agent
            
            return agent
            
        except Exception as e:
            logger.error(f"Failed to create agent for context {context_id}: {e}")
            raise RuntimeError(f"Agent creation failed: {e}")
    
    # def _create_input_callback(self, context_id: str):
    #     """
    #     Create a callback function for handling user input within browser-use.
        
    #     Args:
    #         context_id: ID of the context
            
    #     Returns:
    #         Callback function that can be used by browser-use
    #     """
    #     async def input_callback(prompt: str) -> str:
    #         """
    #         Custom callback that allows browser_use to request input from the user.
            
    #         Args:
    #             prompt: The prompt to show the user
                
    #         Returns:
    #             User input as a string
    #         """
    #         # Create a future that will be resolved when input is received
    #         input_future = Future()
            
    #         # Put the request for input in the shared state
    #         await self.request_user_input(context_id, prompt, input_future)
            
    #         # Wait for the result
    #         return await input_future
            
    #     return input_callback
    
    # async def request_user_input(self, context_id: str, prompt: str, future: Future) -> None:
    #     """
    #     Request input from the user during agent execution.
        
    #     Args:
    #         context_id: ID of the context requesting input
    #         prompt: The prompt to show the user
    #         future: Future to resolve with user input
    #     """
    #     if context_id not in self._input_queues:
    #         logger.error(f"No input queue for context {context_id}")
    #         future.set_exception(ValueError(f"No input queue for context {context_id}"))
    #         return
            
    #     # Add the request to the queue
    #     await self._input_queues[context_id].put({
    #         "prompt": prompt,
    #         "future": future
    #     })
        
    #     logger.info(f"Input requested for context {context_id}: {prompt}")
    
    # async def provide_user_input(self, context_id: str, input_value: str) -> bool:
    #     """
    #     Provide user input for a pending input request.
        
    #     Args:
    #         context_id: ID of the context to provide input for
    #         input_value: User input value
            
    #     Returns:
    #         True if input was processed, False if no pending requests
            
    #     Raises:
    #         ValueError: If context doesn't exist
    #     """
    #     if context_id not in self._input_queues:
    #         raise ValueError(f"Context {context_id} does not exist or has no input queue")
            
    #     queue = self._input_queues[context_id]
        
    #     if queue.empty():
    #         logger.warning(f"No pending input requests for context {context_id}")
    #         return False
            
    #     # Get the request
    #     request = await queue.get()
    #     future = request["future"]
        
    #     # Resolve the future with the input
    #     if not future.done():
    #         future.set_result(input_value)
    #         logger.info(f"Input provided for context {context_id}")
    #         return True
    #     else:
    #         logger.warning(f"Input request for context {context_id} already resolved")
    #         return False
    
    async def run_task(
        self,
        context_id: str,
        task: Optional[str] = None,
        llm: Optional[Any] = None,
        use_vision: bool = True,
        timeout: Optional[float] = None,
        agent_kwargs: Optional[Dict[str, Any]] = None
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
            agent = self._context_to_agent.get(context_id)
            
            if agent is None:
                if not task or not llm:
                    raise ValueError("Task and LLM must be provided when creating a new agent")
                
                agent = await self.create_agent(
                    context_id=context_id,
                    task=task,
                    llm=llm,
                    use_vision=use_vision,
                    agent_kwargs=agent_kwargs
                )
            elif task:  # Update existing agent's task
                agent.task = task
            
            # Run the agent with timeout if specified
            if timeout:
                result = await asyncio.wait_for(agent.run(), timeout=timeout)
            else:
                result = await agent.run()
                
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
                    
                if context_id in self._input_queues:
                    del self._input_queues[context_id]
                    
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
        if context_id not in self._input_queues:
            return False
        return not self._input_queues[context_id].empty()
    
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