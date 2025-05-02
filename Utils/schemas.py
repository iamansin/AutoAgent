from enum import Enum, auto
from pydantic import BaseModel, Field
from typing_extensions import Optional,List,Dict,Any

class ResearchResult(BaseModel):
    """Model for search results from research phase"""
    url: str
    title: str
    description: str
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    
class Task(BaseModel):
    """Model for a specific task to execute"""
    task_description: str
    constraints : List[str]

class WebSocketMessage(BaseModel):
    type: str
    content: Dict[str, Any]
    session_id: str
    request_id: Optional[str] = None