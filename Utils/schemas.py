from enum import Enum, auto
from pydantic import BaseModel, Field
from typing_extensions import Optional,List
class TaskPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class ResearchResult(BaseModel):
    """Model for search results from research phase"""
    url: str
    title: str
    description: str
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    
class Task(BaseModel):
    """Model for a specific task to execute"""
    task_description: str
    website: Optional[str] = None
    priority: Optional[TaskPriority] = TaskPriority.MEDIUM
    validation_rules: Optional[List[str]] = None
    
class ThinkerOutputStruct(BaseModel):
    Task : str | None = Field(description="This field contains Task for execution if user task is simple.", default=None)
    Thought : str | None = Field(description="This field contains Thought for Research if user task is complex and requires Reserach.", default=None)
 