
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
import os
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

google_llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-001",
    temperature=0,
    api_key=GOOGLE_API_KEY,
    timeout=None,
    max_retries=2,
)

openai_llm = ChatOpenAI(
    model = "gpt-4o-mini-2024-07-18",
    api_key=OPENAI_API_KEY,
)

response = openai_llm.invoke("hello")
print(response.content)