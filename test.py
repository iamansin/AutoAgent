from Agents.main_agent import AutoAgent
from langchain_google_genai import ChatGoogleGenerativeAI
import os
from dotenv import load_dotenv
import asyncio
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# print(GOOGLE_API_KEY)

llm_gemini = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-001",
    temperature=0,
    api_key= GOOGLE_API_KEY,
    timeout=None,
    max_retries=2,
)
agent = AutoAgent(
    llm_dict={"google" : llm_gemini},
    fallback_llm=None,
    verbose=True
)

async def test_autoagent(user_task:str):
    try:
        response = await agent.run(user_task=user_task)
        print(response)
        
    except Exception as e:
        raise e
    
asyncio.run(test_autoagent("i want you to find and fill forms for funding rounds for stratups."))