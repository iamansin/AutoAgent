
from typing_extensions import Optional
from browser_use import Browser, ActionResult
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
import os 
from pydantic import BaseModel
from dotenv import load_dotenv
import logging
from textwrap import dedent
import uuid
# from Utils import structured_llm
# from main import ws_manager
from Utils.schemas import WebSocketMessage
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AutoAgent")

load_dotenv()

GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")

google_llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-001",
    temperature=0,
    api_key=GOOGLE_API_KEY,
    timeout=None,
    max_retries=2,
)
class ModelPrompt(BaseModel):
    prompt : str 

class InfoStructure(BaseModel):
    need_more_info : bool = False
    prompt : Optional[str] = None
    required_info : Optional[str] = None
 
class ResponseStructure(BaseModel):
    info_suff : bool
    debug_prompt : Optional[str] = None
    refined_prompt : Optional[str] = None
    
USER_INFO = {
    "10" : {
        "username" : "Aman Singh",
        "user_phone_number" : "+91-8083343",
        "user_email" : "amanragu2002@gmail.com",
        "gender" : "male",
        "preference" : {
            "language" : ["English", "Hindi"]
        },
        
    }
}

USER_INFO_PROMPT = dedent("""
User Information : {current_user_info},

Required Info by the Agent : {_prompt},

You are an Expert AI Agent, Your main task is to help another agent (browser Agent) to get information it requires about the user.
You are provided with The use_information and the required information, you task is to think and extract the infromaiton that can be passed to the Browser Agent.
***Most important:
- If the required information is not mentioned or found in the provided user information then you should rasie the "need_more_info" flag, 
and also prompt the user for the information that is required.
- If the information is sufficient then simply return the information in a structured format so that the other agent cam use it .
-You Must return response in the provided JSON format:
{{
    "need_more_info" : <Boolean value, True if yes, else False>,
    "prompt" : <If need_more_info  is True the this key contains a a prompt that has to be asked to the user for required infromation.>
    "required_info" : <If the required information is found, the this filed contains a structured format of the information.> 
}}
""")

USER_RESPONSE_PROMPT = dedent("""
You are a highly intelligent Agentic Thinker integrated within a Browser Agent that handles advanced web tasks. In the current interaction, you are provided with two pieces of information:

1. Agent Prompt: {agent_prompt}
2. User Input: {user_input}

Your task is to:
1. Analyze both the Agent Prompt and the User Input.
2. Determine whether the User Input sufficiently satisfies the request from the Agent Prompt by providing the necessary content, tone, and details. The User Input may contain both instructions and the actual content.
3. If the User Input fully meets the Agent Prompt's request and contains the necessary content, set "info_suff" to true.
4. If the User Input is incomplete, vague, or does not include the specific content requested, set "info_suff" to false.
5. If "info_suff" is false, generate a brief and clear "debug_prompt" instructing the user on what additional details or corrections are needed.
6. Optionally, provide a "refined_input" that retains the intended meaning of the User Input while correcting any errors or clarifying the content.
7. Do not add or hallucinate any extra details; use only the provided Agent Prompt and User Input.

Return ONLY a JSON object that strictly adheres to the following structure:
{{
  "info_suff": <bool>,
  "debug_prompt": <string or null>,
  "refined_input": <string or null>
}}

IMPORTANT:
- Ensure your output is valid JSON.
- Your entire response must be in valid JSON format without any additional commentary.

Proceed by evaluating the provided Agent Prompt and User Input, then return the result in the specified JSON structure.
""")


async def get_stored_info(user_id :str):
    return USER_INFO[user_id] 

async def get_user_input(prompt: str, session_id : str = "test101") -> str:
    response = input(f"{prompt} ::")
    USER_INFO["10"][prompt] = response
    return response
    # Send a user input request via WebSocket
    # response = 
    # return response
    # print(prompt)
    # llm_response = None
    # while True:
    #     try:
    #         # user_response = await ws_manager.request_user_input(llm_response if llm_response else prompt, session_id)
    #         user_response = input(f"{llm_response if llm_response else prompt}, Enter your response here:: ")
    #     except Exception as e:
    #         print (e)
    #         break
    #     parser = PydanticOutputParser(pydantic_object=ResponseStructure)
    #     llm_prompt = PromptTemplate(
    #             template=USER_RESPONSE_PROMPT,
    #             partial_variables={"format_instructions": parser.get_format_instructions()}
    #         )
    #     message = llm_prompt.format(agent_prompt=prompt, user_input = user_response )
        
    #     try:
    #         structured_llm = google_llm.with_structured_output(ResponseStructure)
    #         response: ResponseStructure= await structured_llm.ainvoke(message)
    #         if response.info_suff:
    #             if response.refined_prompt :
    #                 return response.refined_prompt
    #             else:
    #                 return user_response
            
    #         llm_response = response.debug_prompt
            
    #     except Exception as e:
    #         raise e



async def get_user_info(params: ModelPrompt) -> ActionResult:
    try:
        _prompt = params.prompt
        logger.info(f"Need Information about: {_prompt}")
        user_info = await get_stored_info(user_id="10")
        
        parser = PydanticOutputParser(pydantic_object=InfoStructure)
        prompt = PromptTemplate(
            template=USER_INFO_PROMPT,
            partial_variables={"format_instructions": parser.get_format_instructions()}
        )
        
        message = prompt.format(_prompt=_prompt, current_user_info=str(user_info))
        
        try:
            structured_llm = google_llm.with_structured_output(InfoStructure)
            response: InfoStructure = await structured_llm.ainvoke(message)
            
            if response.need_more_info:
                user_input = await get_user_input(response.prompt, session_id="10")
                return ActionResult(extracted_content=user_input)
            else:
                return ActionResult(extracted_content=response.required_info)
                
        except Exception as e:
            logger.error(f"Error processing LLM response: {e}")
            raise
            
    except Exception as e:
        logger.error(f"Error in get_user_info: {e}")
        raise