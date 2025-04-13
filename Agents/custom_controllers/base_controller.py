from browser_use import Controller, ActionResult, Browser
from typing import Type, Callable, Awaitable
from git import Optional
from pydantic import BaseModel

class ControllerRegistry:
    """Registry for managing multiple controller actions in a modular way."""
    
    def __init__(self):
        self._controller = Controller()
        self._registered_actions = {}
    
    def register_action(self, name :str, 
                        description: str,
                        handler: Callable | Awaitable,
                        param_model: Optional[Type[BaseModel]] = None):
        """Register an action with the controller.
        
        Args:
            name: The name of the action
            description: The description of the action 
            param_model: The Pydantic model for the action parameters
            handler: The sync/async function that implements the action
        """
        action_decorator = self._controller.action(description)
                                                #    param_model=param_model)
        
        registered_action = action_decorator(handler)
        self._registered_actions[name] = registered_action
        return registered_action

    def get_controller(self):
        """Get the controller with all registered actions.
        
        Returns:
            The configured controller object ready to be passed to an agent
        """
        return self._controller