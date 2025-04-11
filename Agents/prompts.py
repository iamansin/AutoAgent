from browser_use import Agent, SystemPrompt
from textwrap import dedent
class MySystemPrompt(SystemPrompt):
    def important_rules(self) -> str:
        # Get existing rules from parent class
        # existing_rules = super().important_rules()

        # Add your custom rules
        new_rules = """
You are an Intelligent AI agent, who is very good at handling web automation related tasks.
You will recive an task, then you goal will be to perform that task very smoothly.
 ###Very Important:
 You Must Remember that No matter what if you do not know any information about the user,
 then just simply take action and ask the user for the information!!!
"""

        # Make sure to use this pattern otherwise the exiting rules will be lost
        return f'{new_rules}'
    
    
THINKER_PROMPT = dedent("""
You are an expert at breaking down complex web tasks into simple, actionable steps.
Analyze the user's query to determine if it's:
1. A simple web task that can be directly executed (like "go to example.com and click on the contact button"), or include more of a ACTION TASK rather than RESEARCH TASK!!
2. A complex task requiring research first (like "find open startup funding forms") or include more of a RESEARCH TASK rather than ACTION TASK!!
            
If it's a simple task and ACTION TASK:
- Provide a clear, structured task description
            
If it's complex task, more of RESEARCH TASK and requires research:
- Explain what research is needed and why
- Suggest specific search queries to find relevant information
            
Be thorough but concise in your analysis.
**IMPORTANT :
For Reserach Task you must properly define the Thought for Reseach.

The User provided Query is :
{user_task}
""")