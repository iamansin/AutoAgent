from browser_use import Agent, SystemPrompt
from textwrap import dedent
class MySystemPrompt(SystemPrompt):
    def important_rules(self) -> str:
        # Get existing rules from parent class
        existing_rules = super().important_rules()

        # Add your custom rules
        new_rules = """
9. MOST IMPORTANT RULE:
- ALWAYS Take Screen Shot using the provided tool for each step no matter what!!!
"""

        # Make sure to use this pattern otherwise the exiting rules will be lost
        return f'{existing_rules}\n{new_rules}'
    
    
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