from typing import Dict, List, Callable, Optional, Any, Union
from pydantic import BaseModel, Field
from langgraph.types import Send
from enum import Enum
import logging
from functools import wraps

# Configure logging
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

class RouterException(Exception):
    """Base exception class for Router-related errors"""
    pass

class RouteConfigurationError(RouterException):
    """Raised when there's an issue with route configuration"""
    pass

class RouteNotFoundError(RouterException):
    """Raised when a requested route is not found"""
    pass

class RouteType(Enum):
    """Enum for different types of routing"""
    DIRECT = "direct"
    CONDITIONAL = "conditional"
    SEND = "send"

class InternalState(BaseModel):
    """
    Base model for internal state management
    """
    data: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **kwargs):
        super().__init__()
        self.data.update(kwargs)

class RouteConfig(BaseModel):
    """
    Configuration model for route definitions
    """
    from_node: str
    direct_nodes: Optional[List[str]] = Field(default_factory=list)
    conditional_nodes: Optional[List[str]] = Field(default_factory=list)
    send: bool = False
    send_to: Optional[str] = None


class Router:
    """
    Router class for managing conditional edges in langgraph.
    
    This class handles routing logic between nodes, supporting direct routing,
    conditional routing, and state sending between nodes.
    """
    
    _route_registry: Dict[str, Callable] = {}

    def __init__(self, name: str):
        """
        Initialize Router instance.
        
        Args:
            name (str): Unique identifier for the router instance
        """
        self.name = name
        self._validate_name(name)

    @staticmethod
    def _validate_name(name: str) -> None:
        """
        Validate router name.
        
        Args:
            name (str): Router name to validate
        
        Raises:
            RouteConfigurationError: If name is invalid
        """
        if not name or not isinstance(name, str):
            raise RouteConfigurationError("Router name must be a non-empty string")

    @staticmethod
    def _validate_nodes(nodes: List[str]) -> None:
        """
        Validate node list.
        
        Args:
            nodes (List[str]): List of node names to validate
        
        Raises:
            RouteConfigurationError: If any node name is invalid
        """
        if not all(isinstance(node, str) and node for node in nodes):
            raise RouteConfigurationError("All node names must be non-empty strings")

    @classmethod
    def _create_routing_function(
        cls,
        from_node :str
    ) -> Callable:
        """
        Create a routing function based on configuration.
        
        Args:
            state: The state object containing routing information
            config: Route configuration
        
        Returns:
            Callable: Wrapped routing function
        """
        @wraps(cls._create_routing_function)
        def routing_function(state):
            config :RouteConfig = state.route_config[from_node]
            try:
                if config.send:
                    return [
                        Send(
                            config.send_to,
                            {"internal_state": internal_state}
                        )
                        for internal_state in state.send_list.get(from_node, [])
                    ]
                
                next_nodes = []
                if hasattr(state, 'routes'):
                    selected_nodes = state.routes.get(from_node, [])
                    next_nodes.extend(
                        node for node in config.conditional_nodes
                        if node in selected_nodes
                    )
                

                LOGGER.debug(
                    f"Routing from {config.from_node} to nodes: {next_nodes}"
                )
                return next_nodes

            except Exception as e:
                LOGGER.error(
                    f"Error in routing function for {config.from_node}: {str(e)}",
                    exc_info=True
                )
                raise RouterException(
                    f"Routing error for {config.from_node}"
                ) from e

        return routing_function

    @classmethod
    def get_routing_function(
        cls,
        from_node: str,
    ) -> bool:
        """
        Create a new route configuration and register its routing function.
        
        Args:
            state: State object containing routing information
            from_node: Source node name
            direct_nodes: List of direct target nodes
            conditional_nodes: List of conditional target nodes
            send: Whether to enable state sending
            send_to: Target node for state sending
        
        Returns:
            bool: True if route creation was successful
        
        Raises:
            RouteConfigurationError: If route configuration is invalid
        """
        try:
            # if from_node not in cls._route_registry:
            #     raise RouteNotFoundError(
            #         f"No routing function found for {from_node}"
            #     )
            routing_func = cls._create_routing_function(from_node)
            cls._route_registry[from_node] = routing_func

            LOGGER.info(f"Successfully created router for {from_node}")
            return routing_func

        except Exception as e:
            LOGGER.error(
                f"Failed to create router for {from_node}: {str(e)}",
                exc_info=True
            )
            raise e 
            # raise RouteConfigurationError(
            #     f"Failed to create router for '{from_node}'"
            # ) from e

    @classmethod
    def clear_routes(cls) -> None:
        """Clear all registered routes and configurations"""
        cls._route_registry.clear()
        cls._route_configs.clear()
        LOGGER.info("Cleared all routes and configurations")