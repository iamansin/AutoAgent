from typing import Dict, List, Optional, Any, Union, Type
from pydantic import BaseModel, Field, validator
import logging
from functools import lru_cache

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("agent_registry")

class AgentCard(BaseModel):
    """Pydantic model to store information about a particular agent."""
    name: str = Field(..., description="Unique name identifier for the agent")
    description: str = Field(..., description="Description of the agent's capabilities")
    version: str = Field("1.0.0", description="Version of the agent")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Parameters the agent accepts")
    tags: List[str] = Field(default_factory=list, description="Tags describing the agent's domain or specialties")
    
    # @validator('name')
    # def name_must_be_valid(cls, v):
    #     if not v or not isinstance(v, str) or len(v.strip()) == 0:
    #         raise ValueError("Agent name cannot be empty")
    #     return v.strip()
    
    # @validator('description')
    # def description_must_be_valid(cls, v):
    #     if not v or not isinstance(v, str) or len(v.strip()) == 0:
    #         raise ValueError("Agent description cannot be empty")
    #     return v.strip()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the AgentCard to a dictionary."""
        return self.dict(exclude_none=True)


class AgentRegistry:
    """
    A registry for managing agent instances in a multi-agent system.
    Allows for registration, retrieval, and listing of available agents.
    """
    
    def __init__(self):
        self._agents: Dict[str, Any] = {}
        self._agent_cards: Dict[str, AgentCard] = {}
        logger.info("Agent Registry initialized")
    
    def register_agent(self, agent: Any, agent_card: AgentCard) -> None:
        """
        Register an agent with its corresponding information card.
        
        Args:
            agent: The agent instance to register
            agent_card: The AgentCard containing metadata about the agent
            
        Raises:
            ValueError: If an agent with the same name is already registered
        """
        name = agent_card.name
        
        if name in self._agents:
            logger.warning(f"Agent with name '{name}' is already registered. Overwriting.")
        
        self._agents[name] = agent
        self._agent_cards[name] = agent_card
        logger.info(f"Agent '{name}' registered successfully")
    
    def unregister_agent(self, name: str) -> bool:
        """
        Remove an agent from the registry.
        
        Args:
            name: The name of the agent to unregister
            
        Returns:
            bool: True if the agent was unregistered, False if it wasn't found
        """
        if name in self._agents:
            del self._agents[name]
            del self._agent_cards[name]
            logger.info(f"Agent '{name}' unregistered successfully")
            return True
        
        logger.warning(f"Attempted to unregister non-existent agent '{name}'")
        return False
    
    def get_agent(self, name: str) -> Any:
        """
        Retrieve an agent instance by name.
        
        Args:
            name: The name of the agent to retrieve
            
        Returns:
            The agent instance
            
        Raises:
            KeyError: If no agent with the given name is registered
        """
        if name not in self._agents:
            logger.error(f"Agent '{name}' not found in registry")
            raise KeyError(f"No agent registered with name '{name}'")
        
        return self._agents[name]
    
    @lru_cache(maxsize=1)
    def list_agents(self) -> Dict[str, str]:
        """
        Get a dictionary of all registered agents with their descriptions.
        
        Returns:
            Dict[str, str]: A dictionary mapping agent names to their descriptions
        """
        return {name: card.description for name, card in self._agent_cards.items()}
    
    def get_agents_by_names(self, names: List[str]) -> Dict[str, Any]:
        """
        Retrieve multiple agent instances by their names.
        
        Args:
            names: List of agent names to retrieve
            
        Returns:
            Dict[str, Any]: Dictionary mapping agent names to their instances
            
        Raises:
            KeyError: If any of the requested agents are not found
        """
        result = {}
        missing_agents = [name for name in names if name not in self._agents]
        
        if missing_agents:
            logger.error(f"The following agents were not found: {missing_agents}")
            raise KeyError(f"Missing agents: {', '.join(missing_agents)}")
        
        for name in names:
            result[name] = self._agents[name]
        
        return result
    
    def get_agent_card(self, name: str) -> AgentCard:
        """
        Get the information card for a specific agent.
        
        Args:
            name: The name of the agent
            
        Returns:
            AgentCard: The agent's information card
            
        Raises:
            KeyError: If no agent with the given name is registered
        """
        if name not in self._agent_cards:
            logger.error(f"Agent card for '{name}' not found")
            raise KeyError(f"No agent card registered for '{name}'")
        
        return self._agent_cards[name]
    
    def get_all_agent_cards(self) -> Dict[str, AgentCard]:
        """
        Get all registered agent cards.
        
        Returns:
            Dict[str, AgentCard]: Dictionary mapping agent names to their information cards
        """
        return dict(self._agent_cards)
    
    def find_agents_by_tags(self, tags: List[str], match_all: bool = False) -> List[str]:
        """
        Find agents that match the specified tags.
        
        Args:
            tags: List of tags to search for
            match_all: If True, only return agents that have all specified tags
                      If False, return agents that have any of the specified tags
                      
        Returns:
            List[str]: Names of agents that match the tag criteria
        """
        result = []
        
        for name, card in self._agent_cards.items():
            agent_tags = set(card.tags)
            search_tags = set(tags)
            
            if match_all:
                if search_tags.issubset(agent_tags):
                    result.append(name)
            else:
                if search_tags.intersection(agent_tags):
                    result.append(name)
                    
        return result
    
    def __len__(self) -> int:
        """Return the number of registered agents."""
        return len(self._agents)
    
    def __contains__(self, name: str) -> bool:
        """Check if an agent with the given name is registered."""
        return name in self._agents