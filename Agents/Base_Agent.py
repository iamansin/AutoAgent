import asyncio
from doctest import UnexpectedException
import json
import logging
from typing import Awaitable, Dict, List, Any, Optional, Tuple, Union, Callable, Literal
import httpx
from langgraph.graph import StateGraph, END
from langgraph.graph.graph import CompiledGraph
# from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from Utils.structured_llm import StructuredLLMHandler
from Utils.routing_module import InternalState, Router, RouteConfig
from Utils.schemas import (
    Task, 
    ResearchResult
)
from Utils.agent_registry.registry import AgentRegistry, AgentCard
# Configure logging
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AutoAgent")




class BaseAgent:
    """
    AutoAgent class for automating web tasks through prompting.
    Uses a Langgraph-based workflow to research, validate, and execute tasks.
    """
    
    def __init__(
        self,
        agent_registry : AgentRegistry,
        llm_dict :Dict[str,Any],
        fallback_llm : str = None,
        max_steps : int = 10,
        timeout: int = 30,
        max_retries: int = 3,
        verbose: bool = False,
    ):
        """
        Initialize the AutoAgent class.
        
        Args:
            llm: Language model to use for thinking and task generation
            search_api_key: API key for search engine
            search_engine: Search engine to use (duckduckgo or tavily)
            max_search_results: Maximum number of search results to process
            timeout: Timeout for API calls in seconds
            max_retries: Maximum number of retries for API calls
            verbose: Whether to log detailed information
        """
        self._llm_dict = llm_dict
        self._fallback_llm = fallback_llm 
        self.agent_registry = agent_registry
        self.timeout = timeout
        self.max_retries = max_retries
        self.verbose = verbose
        self._max_steps = max_steps
        self.LLMHandler = StructuredLLMHandler(llm_dict=llm_dict, 
                                               fallback_llm=fallback_llm)
        self._Router :Router = Router(name = "BaseAgent")
        # Initialize HTTP client for API calls
        self.http_client = httpx.AsyncClient(timeout=timeout)
        # Set up the workflow graph
        self.workflow :CompiledGraph = self._build_workflow()
        
    def _build_workflow(self) -> StateGraph:
        """Build the workflow graph for the agent."""
        
        # Define the nodes
        workflow = StateGraph(AutoAgentState)
        
        workflow.add_node("thinker", self.thinker_node)
        for agent in self.agent_registry
        
        # Add nodes
        workflow.add_node("researcher", self.researcher_node)
        # workflow.add_node("validator", RunnableLambda(self.validator_node))
        workflow.add_node("executor", self.executor_node)
        workflow.add_node("human_input", self.human_node)
        
        # Define edges
        workflow.add_conditional_edges("thinker", self._Router.get_routing_function("thinker"))
        workflow.add_conditional_edges("executor", self._Router.get_routing_function("executor"))
        # workflow.add_edge("human_input", "executor")
        # workflow.add_edge(["researcher", "executor"], "validator")
        # workflow.add_edge(["executor", "researcher"], END)
        # workflow.add_edge("thinker", END)
        
        # Set the entry point
        workflow.set_entry_point("thinker")
        
        # Compile the workflow
        return workflow.compile()
    
    async def thinker_node(self, state: AutoAgentState) -> AutoAgentState:
        """
        Consider the query and determine if research is needed or if the task is basic.
        
        Args:
            state: Current state of the agent
            
        Returns:
            Updated state with thinking results
        """
        
        try:
            user_task  = state.user_task
            response : ThinkerOutputStruct = await self.LLMHandler.get_structured_response(
                    prompt=THINKER_PROMPT, 
                    output_structure=ThinkerOutputStruct,
                    use_model="google",
                    user_task = user_task,
                )
            task_type = response.task_type
            
            if task_type == "ACTION":
                state.tasks.append(
                    Task(
                        task_description= response.refined_task,
                        missing_info = response.missing_information,
                        constraints = response.constraints
                    )
                )
                # state.messages.append(AIMessage(content= task))
                state.routes["thinker"] = ["executor"]
                state.route_config["thinker"] = RouteConfig(
                    from_node="thinker",
                    conditional_nodes=["executor"]
                )
                if self.verbose:
                    logger.info(f"Task for Execution:---> {response}")
                
            elif task_type == "RESEARCH":
                state.tasks.append(
                    Task(
                        task_description= response.refined_task,
                        missing_info = response.missing_information,
                        constraints = response.constraints
                    )
                )
                # state.messages.append(AIMessage(content=thought))
                state.routes["thinker"] = ["researcher"]
                state.route_config["thinker"] = RouteConfig(
                    from_node="thinker",
                    conditional_nodes=["researcher"]
                )
                if self.verbose:
                    logger.info(f"Thinking result:---> {response}")
                
            else:
                raise UnexpectedException("Got no thoughts and task from the Thinker node response:")
            
            return state
            
        except Exception as e:
            error_msg = f"Error in thinker_node: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
            raise e
    