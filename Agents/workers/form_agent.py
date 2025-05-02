import asyncio
from doctest import UnexpectedException
import json
import logging
from re import L
from shutil import ExecError
from typing import Awaitable, Dict, List, Any, Optional, Tuple, Union, Callable, Literal
import httpx
from langchain_core.runnables import RunnableLambda
from langgraph.graph import StateGraph, END
import traceback
# from langgraph.prebuilt import ToolNode
# from langgraph.graph.message import add_messages
from langgraph.graph.graph import CompiledGraph
from langchain_core.messages import HumanMessage, AIMessage
from browser_use import ActionResult, AgentHistoryList
# from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from Utils.prompts import (
    THINKER_PROMPT,
    EXEPROMPT,
    TASK_INSTRUCTIONS
)
from Utils.structured_llm import StructuredLLMHandler
from Utils.routing_module import InternalState, Router, RouteConfig
from Utils.schemas import (
    Task, 
    ResearchResult
)
from .Browser_Agent import BrowserAgentHandler
# Configure logging
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AutoAgent")

class ThinkerOutputStruct(BaseModel):
    """Pydantic model for the task analyzer response."""
    
    task_type: Literal["ACTION", "RESEARCH"] = Field(
        description="Type of task: ACTION for direct web actions, RESEARCH for information gathering tasks"
    )
    
    refined_task: str = Field(
        description="Enhanced version of the original task with all implicit actions made explicit",
        min_length=10,
        max_length=500
    )
    
    missing_information: List[str] = Field(
        description="List of specific questions about missing information that should be asked",
        min_items=1
    )
    
    constraints: List[str] = Field(
        description="Any limitations or special considerations the agent should be aware of",
        default_factory=list
    )
    
    
    class Config:
        schema_extra = {
            "example": {
                "task_type": "ACTION",
                "refined_task": "Purchase a t-shirt online that matches the user's preferences",
                "missing_information": [
                    "What color t-shirt would you prefer?",
                    "What size do you need?",
                    "Do you have a preferred brand or website?",
                    "What is your budget range?",
                    "What style of t-shirt (casual, formal, graphic, plain)?",
                    "What shipping address should be used?",
                    "What payment method would you like to use?"
                ],
                "constraints": [
                    "Need to access user payment information", 
                    "Requires shipping address"
                ]
            }
        }

class NextInstruction(BaseModel):
    instruction : str = Field(description="This field contains the new instruction that should be taken")
    
class InterruptionContext(BaseModel):
    interrup : bool
    question : Optional[str] = None

class ExeActionStruct(BaseModel):
    current_task_completed : bool 
    user_task_completed : bool
    next_step : Optional[str] = None
    final_response : Optional[str] = None

class ActionOutputStruct(BaseModel):
    instructions : List[str]

class ProcessContext(BaseModel):
    process_history : List[str] = Field(default_factory=list)
    next_step : Optional[str] = None
    
class AutoAgentState(BaseModel):
    """State model for AutoAgent"""
    user_task: str
    routes: Dict[str,List[str]] = Field(default_factory=dict)
    route_config : Dict[str,RouteConfig] =Field(default_factory=dict)
    sensitive_data : Optional[Dict] = None
    research_results: List[str] = Field(default_factory=list)
    tasks: List[Task] = Field(default_factory=list)
    messages: List[Union[HumanMessage, AIMessage]] = Field(default_factory=list)
    context_id : str
    results : Dict[str,Any] = Field(default_factory=dict)
    # send_list : Dict[str, List[InternalState]] = Field(default_factory=dict)
    # step : int = Field(default=0)
    # question : Optional[str] = None
    # process_context : ProcessContext = None
    # input : Dict[str,str] = Field(default_factory=dict)

class AutoAgent:
    """
    AutoAgent class for automating web tasks through prompting.
    Uses a Langgraph-based workflow to research, validate, and execute tasks.
    """
    
    def __init__(
        self,
        llm_dict :Dict[str,Any],
        fallback_llm : str = None,
        browser_agent : BrowserAgentHandler = None,
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
        self.timeout = timeout
        self.max_retries = max_retries
        self.verbose = verbose
        self._max_steps = max_steps
        self.LLMHandler = StructuredLLMHandler(llm_dict=llm_dict, 
                                               fallback_llm=fallback_llm)
        self._Router :Router = Router(name = "FormAgent")
        # Initialize HTTP client for API calls
        # self.http_client = httpx.AsyncClient(timeout=timeout)
        self.BrowserAgent = browser_agent or BrowserAgentHandler(llm_dict=llm_dict)
        # Set up the workflow graph
        self.workflow :CompiledGraph = self._build_workflow()
        
    def _build_workflow(self) -> StateGraph:
        """Build the workflow graph for the agent."""
        
        # Define the nodes
        workflow = StateGraph(AutoAgentState)
        
        # Add nodes
        workflow.add_node("thinker", self.thinker_node)
        workflow.add_node("executor", self.executor_node)
        workflow.add_node("human_input", self.human_node)
        
        # Define edges
        workflow.add_conditional_edges("thinker", self._Router.get_routing_function("thinker"))
        workflow.add_conditional_edges("executor", self._Router.get_routing_function("executor"))
        
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
    
    async def human_node(self, state: AutoAgentState):
        logger.info("Now taking user input")
        waiting = state.waiting
        step = state.step
        if waiting and step < self._loop_steps:
            logger.info(f"The question is : {state.question}")
            logger.info(f"The next step is :{state.process_context.next_step}")
            await asyncio.sleep(10)
        
        state.input["username"] = "amanragu200@gmail.com"
        return state
        
    async def executor_node(self, state: AutoAgentState) -> AutoAgentState:
        """
        Execute the validated tasks using the browser agent.
        
        Args:
            state: Current state of the agent
            
        Returns:
            Updated state with execution results
        """
        logger.info("Executing validated tasks")
        
        context_id = state.context_id
        task =  str({"task_description" :state.tasks[-1].task_description,
                 "missing_information" : state.tasks[-1].missing_info,
                 "constraints" : state.tasks[-1].constraints})
        sensitive_data = state.sensitive_data
        instruction_context = {
            "instruction" : ["Initial Step no instructions right now",],
            "agent_response" : ["Initial Step no agent response right now",],
        }
        step = 0
        failure = 0
        max_failures = 2
        last_run_results = []
        try:
            while step <= self._max_steps and failure <= max_failures:
                model_response : ExeActionStruct = await self.LLMHandler.get_structured_response(
                            prompt= EXEPROMPT, 
                            output_structure= ExeActionStruct,
                            use_model="google",
                            task = task,
                            previous_step = instruction_context.get("instruction")[-1],
                            agent_response = instruction_context.get("agent_response")[-1],
                            )
                    
                if model_response.user_task_completed:
                    print("Task is completed!!!")
                    state.results = model_response.final_response
                    print(f"Final Response {model_response.final_response}")
                    state.routes["executor"] = [END]
                    state.route_config["executor"] = RouteConfig(
                            from_node="executor",
                            conditional_nodes=[END]
                                    )
                    return state   
                            
                else:
                    if not model_response.current_task_completed:
                        failure += 1

                    next_action = model_response.next_step
                    instruction_context.get("instruction").append(next_action)
   
                    print(f"This is the main instruction for current step : --------->{next_action}")

                try:
                    try:
                        response_history : AgentHistoryList = await self.BrowserAgent.run_task(
                                        context_id=context_id,
                                        task = f"{next_action} \n {TASK_INSTRUCTIONS}",
                                        use_vision=True,
                                        sensitive_data=sensitive_data,
                                        last_result = last_run_results if last_run_results else None,
                                        next_action=None)
                    except Exception as e:
                        print("error while executing agent Browser.")
                        print(e)
                        raise e
                            
                    step += 1
                    browser_response = response_history.final_result()
                    last_result = ActionResult(
                        success=response_history.is_successful(),
                        is_done= response_history.is_done(),
                        extracted_content= browser_response,
                        error = None,
                        include_in_memory= True
                    )
                    last_run_results.append(last_result)
                    instruction_context.get("agent_response").append(browser_response)
                    continue
            
                except Exception as e:
                    logger.error(
                    f"[{state.context_id}] Task execution failed: {str(e)}\n"
                    f"Traceback: {traceback.format_exc()}"
                    )
                    break

            state.routes["executor"] = [END]
            state.route_config["executor"] = RouteConfig(
                    from_node="executor",
                    conditional_nodes=[END]
                )
            return state
        except Exception as e:
            raise e       
        
    async def run(self, user_task: str,context_id :str, sensitive_data : Dict =None) -> Dict[str, Any]:
        """
        Run the agent on a given query.
        
        Args:
            query: The user's query/task
            
        Returns:
            Results of the agent execution
        """
        try:
            # Prepare initial state
            initial_state = AutoAgentState(
                user_task=user_task,
                messages=[HumanMessage(content=user_task)],
                context_id=context_id,
                sensitive_data= sensitive_data
            )
            
            # Run the workflow
            try:
                final_state = await self.workflow.ainvoke(initial_state)
            except Exception as e:
                raise e
            
            print("Now closing context")
            await self.BrowserAgent.close_context(context_id=context_id)
            return final_state
        
        except Exception as e:
            logger.error(f"Error running agent: {str(e)}")
            raise e 
        
    async def close(self):
        """Close any open resources."""
        await self.http_client.aclose()