from browser_use import Agent, Controller, Browser, BrowserConfig, LLM
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from typing import Optional, Union, Dict, Any, List
import os
import asyncio
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("BrowserAgentHandler")

class BrowserAgentHandler:
    """
    Handles the creation and management of Browser-Use agents.
    
    This class encapsulates the logic for creating and configuring Browser-Use agents,
    setting up the browser context, and executing tasks with proper error handling.
    """
    
    def __init__(
        self, 
        browser_config: Optional[BrowserConfig] = None, 
        context_config: Optional[BrowserContextConfig] = None,
        log_dir: str = "logs"
    ):
        """
        Initialize the BrowserAgentHandler with browser and context configurations.
        
        Args:
            browser_config: Configuration for the browser (optional)
            context_config: Configuration for the browser context (optional)
            log_dir: Directory to store agent logs (default: "logs")
        """
        self.agent = None
        self._browser_config = browser_config if browser_config else BrowserConfig()
        self._context_config = context_config if context_config else BrowserContextConfig()
        self._browser = None
        self._browser_context = None
        self._controllers = []
        self._log_dir = log_dir
        
        # Create logs directory if it doesn't exist
        os.makedirs(self._log_dir, exist_ok=True)
        
        logger.info("BrowserAgentHandler initialized with configurations")
    
    async def initialize_browser(self) -> None:
        """
        Initialize the browser and browser context.
        
        Raises:
            RuntimeError: If browser initialization fails
        """
        try:
            logger.info("Initializing browser...")
            self._browser = await Browser.create(self._browser_config)
            
            logger.info("Creating browser context...")
            self._browser_context = await self._browser.new_context(self._context_config)
            
            logger.info("Browser and context initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            # Clean up any partially initialized resources
            await self.close()
            raise RuntimeError(f"Browser initialization failed: {e}")
    
    def add_controller(self, controller: Controller) -> None:
        """
        Add a controller to be used by the agent.
        
        Args:
            controller: The controller to add
        """
        if controller not in self._controllers:
            self._controllers.append(controller)
            logger.info(f"Added controller to agent handler")
    
    def get_timestamp_path(self, base_path: str) -> str:
        """
        Generate a timestamped path for logs.
        
        Args:
            base_path: Base directory for logs
            
        Returns:
            Path with timestamp appended
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{base_path}_{timestamp}"
    
    async def create_agent(
        self, 
        task: str,
        llm: LLM,
        use_vision: bool = True,
        save_conversation: bool = True,
        agent_kwargs: Optional[Dict[str, Any]] = None
    ) -> Agent:
        """
        Create a Browser-Use agent with the specified task and configuration.
        
        Args:
            task: The task description for the agent
            llm: Language model to use for the agent
            use_vision: Whether to enable vision capabilities
            save_conversation: Whether to save the conversation logs
            agent_kwargs: Additional keyword arguments for the Agent constructor
            
        Returns:
            The created Agent instance
            
        Raises:
            RuntimeError: If the browser is not initialized or agent creation fails
        """
        if not self._browser or not self._browser_context:
            logger.error("Browser or context not initialized")
            raise RuntimeError("Browser and context must be initialized before creating an agent")
        
        try:
            # Create a combined controller if multiple controllers are provided
            combined_controller = None
            if self._controllers:
                if len(self._controllers) == 1:
                    combined_controller = self._controllers[0]
                else:
                    # Create a new controller that combines all registered controllers
                    # This is a simplified approach - you may need to implement
                    # a proper controller combination mechanism
                    combined_controller = Controller()
                    logger.warning("Multiple controllers provided - combining them is not fully implemented")
                    # Use the first controller for now
                    combined_controller = self._controllers[0]
            
            # Set up default agent kwargs
            kwargs = {
                "task": task,
                "llm": llm,
                "use_vision": use_vision,
                "browser": self._browser,
                "browser_context": self._browser_context
            }
            
            # Add controller if available
            if combined_controller:
                kwargs["controller"] = combined_controller
            
            # Add conversation logging if enabled
            if save_conversation:
                conversation_path = self.get_timestamp_path(f"{self._log_dir}/conversation")
                kwargs["save_conversation_path"] = conversation_path
            
            # Add any additional kwargs
            if agent_kwargs:
                kwargs.update(agent_kwargs)
            
            # Create the agent
            logger.info(f"Creating agent with task: {task}")
            self.agent = Agent(**kwargs)
            
            return self.agent
            
        except Exception as e:
            logger.error(f"Failed to create agent: {e}")
            raise RuntimeError(f"Agent creation failed: {e}")
    
    async def run_task(
        self, 
        task: Optional[str] = None, 
        llm: Optional[LLM] = None,
        use_vision: bool = True,
        timeout: Optional[float] = None,
        agent_kwargs: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Create an agent if needed, and run the specified task.
        
        Args:
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
            # Initialize browser if not done yet
            if not self._browser or not self._browser_context:
                await self.initialize_browser()
            
            # Create a new agent if none exists or if a new task is provided
            if self.agent is None:
                if not task or not llm:
                    raise ValueError("Task and LLM must be provided when creating a new agent")
                
                self.agent = await self.create_agent(
                    task=task,
                    llm=llm,
                    use_vision=use_vision,
                    agent_kwargs=agent_kwargs
                )
            elif task:  # Update existing agent's task
                self.agent.task = task
            
            # Run the agent with timeout if specified
            if timeout:
                result = await asyncio.wait_for(self.agent.run(), timeout=timeout)
            else:
                result = await self.agent.run()
                
            logger.info("Agent completed task successfully")
            return result
            
        except asyncio.TimeoutError:
            logger.error(f"Task execution timed out after {timeout} seconds")
            raise RuntimeError(f"Task execution timed out after {timeout} seconds")
        except Exception as e:
            logger.error(f"Error during task execution: {e}")
            raise RuntimeError(f"Task execution failed: {e}")
    
    async def close(self) -> None:
        """
        Close the browser and clean up resources.
        """
        try:
            if self._browser_context:
                logger.info("Closing browser context...")
                await self._browser_context.close()
                self._browser_context = None
                
            if self._browser:
                logger.info("Closing browser...")
                await self._browser.close()
                self._browser = None
                
            logger.info("Resources cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            # We still want to set these to None even if there's an error
            self._browser_context = None
            self._browser = None
    
    async def __aenter__(self):
        """
        Async context manager entry.
        """
        await self.initialize_browser()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Async context manager exit.
        """
        await self.close()