import asyncio
from doctest import UnexpectedException
import json
import logging
from shutil import ExecError
from typing import Awaitable, Dict, List, Any, Optional, Tuple, Union, Callable
import httpx
from langchain_core.runnables import RunnableLambda
from langgraph.graph import StateGraph, END
# from langgraph.prebuilt import ToolNode
# from langgraph.graph.message import add_messages
from langgraph.graph.graph import CompiledGraph
from langchain_core.messages import HumanMessage, AIMessage
# from langchain_openai import ChatOpenAI

from pydantic import BaseModel, Field
from .prompts import THINKER_PROMPT
from Utils.structured_llm import StructuredLLMHandler
from Utils.routing_module import InternalState, Router, RouteConfig
from Utils.schemas import (
    Task, 
    TaskPriority,
    ThinkerOutputStruct,
    ResearchResult
)
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AutoAgent")

class AutoAgentState(BaseModel):
    """State model for AutoAgent"""
    user_task: str
    thoughts: List[str] = Field(default_factory=list)
    routes: Dict[str,List[str]] = Field(default_factory=dict)
    route_config : Dict[str,RouteConfig] =Field(default_factory=dict)
    research_results: List[str] = Field(default_factory=list)
    tasks: List[Task] = Field(default_factory=list)
    execution_results: List[Dict[str, Any]] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    send_list : Dict[str, List[InternalState]] = Field(default_factory=dict)
    messages: List[Union[HumanMessage, AIMessage]] = Field(default_factory=list)

class AutoAgent:
    """
    AutoAgent class for automating web tasks through prompting.
    Uses a Langgraph-based workflow to research, validate, and execute tasks.
    """
    
    def __init__(
        self,
        llm_dict :Dict[str,Any],
        fallback_llm : str = None,
        search_api_key: Optional[str] = None,
        search_engine: str = "duckduckgo",
        max_search_results: int = 10,
        timeout: int = 30,
        max_retries: int = 3,
        verbose: bool = False
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
        self.search_api_key = search_api_key
        self.search_engine = search_engine
        self.max_search_results = max_search_results
        self.timeout = timeout
        self.max_retries = max_retries
        self.verbose = verbose
        self.LLMHandler = StructuredLLMHandler(llm_dict=llm_dict, 
                                               fallback_llm=fallback_llm)
        self._Router :Router = Router(name = "autoagent")
        # Initialize HTTP client for API calls
        self.http_client = httpx.AsyncClient(timeout=timeout)
        
        # Set up the workflow graph
        self.workflow :CompiledGraph = self._build_workflow()
        
    def _build_workflow(self) -> StateGraph:
        """Build the workflow graph for the agent."""
        
        # Define the nodes
        workflow = StateGraph(AutoAgentState)
        
        # Add nodes
        workflow.add_node("thinker", self.thinker_node)
        workflow.add_node("researcher", self.researcher_node)
        # workflow.add_node("validator", RunnableLambda(self.validator_node))
        workflow.add_node("executor", self.executor_node)
        
        # Define edges
        workflow.add_conditional_edges("thinker", self._Router.get_routing_function("thinker"))
        # workflow.add_edge("researcher", "validator")
        workflow.add_edge(["executor", "researcher"], END)
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
        logger.info(f"Thinking about query: {state.user_task}")
        
        try:
            user_task = state.user_task
            
            response : ThinkerOutputStruct = await self.LLMHandler.get_structured_response(
                    prompt=THINKER_PROMPT, 
                    output_structure=ThinkerOutputStruct,
                    use_model="google",
                    user_task = user_task,
                )
            task,thought = response.Task, response.Thought
            
            if task:
                state.tasks.append(
                    Task(
                        task_description= task
                    )
                )
                state.messages.append(AIMessage(content= task))
                state.routes["thinker"] = ["executor"]
                state.route_config["thinker"] = RouteConfig(
                    from_node="thinker",
                    conditional_nodes=["executor"]
                )
                if self.verbose:
                    logger.info(f"Task for Execution:---> {task}")
                
            elif thought:
                # Update state with thinking results
                state.thoughts.append(thought)
                state.messages.append(AIMessage(content=thought))
                state.routes["thinker"] = ["researcher"]
                state.route_config["thinker"] = RouteConfig(
                    from_node="thinker",
                    conditional_nodes=["researcher"]
                )
                if self.verbose:
                    logger.info(f"Thinking result:---> {thought}")
                
            else:
                raise UnexpectedException("Got no thoughts and task from the Thinker node response:")
            
            return state
            
        except Exception as e:
            error_msg = f"Error in thinker_node: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
            raise e
    
    async def researcher_node(self, state: AutoAgentState) -> AutoAgentState:
        """
        Perform web research based on the thinking results.
        
        Args:
            state: Current state of the agent
            
        Returns:
            Updated state with research results
        """
        logger.info("Starting research based on thoughts")
        return state
        # if not state.thoughts:
        #     state.errors.append("No thoughts provided for research")
        #     return state
        
        # try:
        #     # Extract search queries from thoughts
        #     system_prompt = """
        #     Based on the following thought about a user query, extract specific search queries that would help find the most relevant information. 
        #     Return ONLY the search queries as a JSON list of strings, with no additional text. Example:
        #     ["startup funding applications 2025", "open startup funding forms"]
        #     """
            
        #     messages = [
        #         {"role": "system", "content": system_prompt},
        #         {"role": "user", "content": f"Thought: {state.thoughts[-1]}"}
        #     ]
            
        #     response = await self.llm.ainvoke(messages)
        #     search_queries_text = response.content
            
        #     # Extract the JSON part
        #     try:
        #         # Find the JSON array in the response
        #         json_start = search_queries_text.find("[")
        #         json_end = search_queries_text.rfind("]") + 1
                
        #         if json_start >= 0 and json_end > json_start:
        #             search_queries_json = search_queries_text[json_start:json_end]
        #             search_queries = json.loads(search_queries_json)
        #         else:
        #             # Fallback: try to parse the entire response as JSON
        #             search_queries = json.loads(search_queries_text)
                
        #         if not isinstance(search_queries, list):
        #             search_queries = [str(search_queries)]
        #     except json.JSONDecodeError:
        #         # If JSON parsing fails, use a simple string splitting approach
        #         search_queries = [q.strip(' "\'') for q in search_queries_text.split(',')]
                
        #     # Execute the search for each query
        #     all_results = []
        #     for query in search_queries:
        #         results = await self._execute_search(query)
        #         all_results.extend(results)
            
        #     # Remove duplicates based on URL
        #     unique_results = []
        #     seen_urls = set()
        #     for result in all_results:
        #         if result.url not in seen_urls:
        #             seen_urls.add(result.url)
        #             unique_results.append(result)
            
        #     # Sort by relevance score
        #     unique_results.sort(key=lambda x: x.relevance_score, reverse=True)
            
        #     # Limit to max_search_results
        #     state.research_results = unique_results[:self.max_search_results]
            
        #     # Log results if verbose
        #     if self.verbose:
        #         logger.info(f"Found {len(state.research_results)} unique research results")
            
        #     return state
            
        # except Exception as e:
        #     error_msg = f"Error in researcher_node: {str(e)}"
        #     logger.error(error_msg)
        #     state.errors.append(error_msg)
        #     return state
    
    async def _execute_search(self, query: str) -> List[ResearchResult]:
        """
        Execute a search query using the configured search engine.
        
        Args:
            query: Search query string
            
        Returns:
            List of search results
        """
        results = []
        
        try:
            if self.search_engine == "duckduckgo":
                results = await self._search_duckduckgo(query)
            elif self.search_engine == "tavily":
                results = await self._search_tavily(query)
            else:
                raise ValueError(f"Unsupported search engine: {self.search_engine}")
                
            # Log search results if verbose
            if self.verbose:
                logger.info(f"Search for '{query}' returned {len(results)} results")
                
            return results
            
        except Exception as e:
            logger.error(f"Error executing search for '{query}': {str(e)}")
            return []
    
    async def _search_duckduckgo(self, query: str) -> List[ResearchResult]:
        """
        Search using DuckDuckGo.
        
        Args:
            query: Search query string
            
        Returns:
            List of search results
        """
        # Simulate DuckDuckGo search using a free API
        # Note: In a production environment, you'd use a proper DuckDuckGo API or integration
        url = "https://api.duckduckgo.com/"
        
        for attempt in range(self.max_retries):
            try:
                response = await self.http_client.get(
                    url,
                    params={"q": query, "format": "json", "no_html": "1", "no_redirect": "1"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    results = []
                    
                    # Process results from DuckDuckGo
                    for i, abstract in enumerate(data.get("AbstractText", [])):
                        results.append(
                            ResearchResult(
                                url=data.get("AbstractURL", f"https://example.com/result/{i}"),
                                title=data.get("Heading", f"Result {i}"),
                                description=abstract,
                                relevance_score=0.9 - (i * 0.05)  # Simple relevance score based on position
                            )
                        )
                    
                    # Also add results from the "RelatedTopics" if available
                    for i, topic in enumerate(data.get("RelatedTopics", [])):
                        if isinstance(topic, dict) and "Text" in topic and "FirstURL" in topic:
                            results.append(
                                ResearchResult(
                                    url=topic["FirstURL"],
                                    title=topic.get("Result", f"Related Result {i}"),
                                    description=topic["Text"],
                                    relevance_score=0.8 - (i * 0.03)
                                )
                            )
                    
                    return results
                
                # Handle rate limiting
                if response.status_code == 429:
                    wait_time = min(2 ** attempt, 60)  # Exponential backoff
                    logger.warning(f"Rate limited by DuckDuckGo API. Retrying in {wait_time} seconds.")
                    await asyncio.sleep(wait_time)
                    continue
                    
                logger.warning(f"DuckDuckGo search failed with status code {response.status_code}")
                return []
                
            except Exception as e:
                logger.error(f"Error in DuckDuckGo search: {str(e)}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)  # Wait a bit before retrying
                
        return []  # Return empty list if all attempts failed
    
    async def _search_tavily(self, query: str) -> List[ResearchResult]:
        """
        Search using Tavily API.
        
        Args:
            query: Search query string
            
        Returns:
            List of search results
        """
        if not self.search_api_key:
            logger.warning("No Tavily API key provided, cannot perform search")
            return []
            
        url = "https://api.tavily.com/search"
        headers = {
            "Authorization": f"Bearer {self.search_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": query,
            "max_results": self.max_search_results,
            "search_depth": "advanced"
        }
        
        for attempt in range(self.max_retries):
            try:
                response = await self.http_client.post(url, headers=headers, json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    results = []
                    
                    for i, result in enumerate(data.get("results", [])):
                        results.append(
                            ResearchResult(
                                url=result.get("url", ""),
                                title=result.get("title", f"Result {i}"),
                                description=result.get("content", "No description"),
                                relevance_score=result.get("relevance_score", 0.9 - (i * 0.05))
                            )
                        )
                        
                    return results
                    
                # Handle rate limiting    
                if response.status_code == 429:
                    wait_time = min(2 ** attempt, 60)  # Exponential backoff
                    logger.warning(f"Rate limited by Tavily API. Retrying in {wait_time} seconds.")
                    await asyncio.sleep(wait_time)
                    continue
                
                logger.warning(f"Tavily search failed with status code {response.status_code}")
                return []
                
            except Exception as e:
                logger.error(f"Error in Tavily search: {str(e)}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)  # Wait a bit before retrying
                
        return []  # Return empty list if all attempts failed
    
    async def validator_node(self, state: AutoAgentState) -> AutoAgentState:
        """
        Validate the research results and create tasks for execution.
        
        Args:
            state: Current state of the agent
            
        Returns:
            Updated state with validated tasks
        """
        logger.info("Validating research results and creating tasks")
        
        if not state.research_results:
            state.errors.append("No research results to validate")
            return state
            
        try:
            # Format research results for LLM consumption
            research_results_str = "\n".join([
                f"URL: {result.url}\nTitle: {result.title}\nDescription: {result.description}\n"
                for result in state.research_results
            ])
            
            system_prompt = """
            You are an expert at validating web search results and creating actionable tasks.
            Review the research results and create specific tasks to execute on the most relevant websites.
            
            For each website that seems relevant to the query, create a task with:
            1. The website URL
            2. A clear description of what should be done on that website
            3. Any validation rules to ensure the task is completed correctly
            
            Return your answer as a JSON array of tasks with this format:
            [
                {
                    "website": "https://example.com",
                    "task_description": "Navigate to the funding application page and fill out the form with startup information",
                    "priority": "high|medium|low",
                    "validation_rules": ["Check if form submission was successful", "Verify confirmation message"]
                }
            ]
            
            Only include websites that are truly relevant to the query. Limit to the 5 most promising websites.
            """
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Query: {state.query}\n\nResearch Results:\n{research_results_str}"}
            ]
            
            response = await self.llm.ainvoke(messages)
            tasks_text = response.content
            
            # Extract tasks from response
            try:
                # Find the JSON array in the response
                json_start = tasks_text.find("[")
                json_end = tasks_text.rfind("]") + 1
                
                if json_start >= 0 and json_end > json_start:
                    tasks_json = tasks_text[json_start:json_end]
                    tasks_data = json.loads(tasks_json)
                else:
                    # Fallback: try to parse the entire response as JSON
                    tasks_data = json.loads(tasks_text)
                
                # Convert to Task objects
                tasks = []
                for task_data in tasks_data:
                    priority = TaskPriority.MEDIUM  # Default
                    
                    # Parse priority if present
                    if "priority" in task_data:
                        priority_str = task_data["priority"].lower()
                        if priority_str == "high":
                            priority = TaskPriority.HIGH
                        elif priority_str == "low":
                            priority = TaskPriority.LOW
                    
                    task = Task(
                        website=task_data["website"],
                        task_description=task_data["task_description"],
                        priority=priority,
                        validation_rules=task_data.get("validation_rules", [])
                    )
                    tasks.append(task)
                
                # Sort tasks by priority
                tasks.sort(key=lambda x: {
                    TaskPriority.HIGH: 0,
                    TaskPriority.MEDIUM: 1,
                    TaskPriority.LOW: 2
                }[x.priority])
                
                state.tasks = tasks
                
                # Log results if verbose
                if self.verbose:
                    logger.info(f"Created {len(state.tasks)} tasks from research results")
                
                return state
            
            except json.JSONDecodeError as e:
                error_msg = f"Error parsing tasks JSON: {str(e)}. Raw response: {tasks_text}"
                logger.error(error_msg)
                state.errors.append(error_msg)
                return state
                
        except Exception as e:
            error_msg = f"Error in validator_node: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
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
        
        
        # try:
        #     # Generate a summary of the tasks for execution
        #     task_summary = "Task Summary:\n"
        #     for idx, task in enumerate(state.tasks, 1):
        #         task_summary += f"{idx}. {task.website} - {task.task_description} (Priority: {task.priority.value})\n"
            
        #     # This would be where your browser agent integration goes
        #     # For this implementation, we'll just simulate the execution and results
            
        #     # Simulate execution results
        #     execution_results = []
        #     for task in state.tasks:
        #         # This is a placeholder for the actual browser agent execution
        #         # In a real implementation, you would call your browser agent here
        #         execution_result = {
        #             "website": task.website,
        #             "task": task.task_description,
        #             "status": "simulated",  # In real implementation: "success", "failure", or "partial"
        #             "notes": f"This is a simulated execution for {task.website}",
        #         }
                
        #         execution_results.append(execution_result)
            
        #     # Update state with execution results
        #     state.execution_results = execution_results
            
        #     # Generate final summary
        #     system_prompt = """
        #     Review the executed tasks and create a concise summary of what was accomplished.
        #     Include:
        #     1. Number of tasks successfully executed
        #     2. Key information discovered or actions performed
        #     3. Any issues encountered
            
        #     Be clear and direct in your summary.
        #     """
            
        #     execution_results_str = "\n".join([
        #         f"Website: {result['website']}\nTask: {result['task']}\nStatus: {result['status']}\nNotes: {result['notes']}"
        #         for result in execution_results
        #     ])
            
        #     messages = [
        #         {"role": "system", "content": system_prompt},
        #         {"role": "user", "content": f"Original Query: {state.query}\n\nExecution Results:\n{execution_results_str}"}
        #     ]
            
        #     response = await self.llm.ainvoke(messages)
        #     summary = response.content
            
        #     # Add summary to messages
        #     state.messages.append(AIMessage(content=summary))
            
        #     # Log results if verbose
        #     if self.verbose:
        #         logger.info(f"Executed {len(state.execution_results)} tasks")
        #         logger.info(f"Summary: {summary}")
            
        #     return state
            
        # except Exception as e:
        #     error_msg = f"Error in executor_node: {str(e)}"
        #     logger.error(error_msg)
        #     state.errors.append(error_msg)
        #     return state
    
    async def run(self, user_task: str) -> Dict[str, Any]:
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
                messages=[HumanMessage(content=user_task)]
            )
            
            # Run the workflow
            try:
                final_state = await self.workflow.ainvoke(initial_state)
            
            except Exception as e:
                raise e
            # Format and return results
            # return {
            #     "query": user_task,
            #     # "messages": [{"role": msg.type, "content": msg.content} for msg in final_state.messages],
            #     # "research_results": [result.dict() for result in final_state.research_results],
            #     "tasks": [task.dict() for task in final_state.tasks],
            #     # "execution_results": final_state.execution_results,
            #     "errors": final_state.errors
            # }
            return final_state
        
        except Exception as e:
            logger.error(f"Error running agent: {str(e)}")
            raise e 
            # return {
            #     "query": user_task,
            #     "error": str(e),
            #     "status": "failed"
            # }
    
    async def close(self):
        """Close any open resources."""
        await self.http_client.aclose()

