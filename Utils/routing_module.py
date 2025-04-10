from xml.dom import ValidationErr
from pydantic import BaseModel, Field
from typing_extensions import Union, Dict, Callable, List
from langgraph.types import Send

class InternalState(BaseModel):
    def __init__(self, **kwargs):
        self.kwargs = {kwargs}
    
class Router:
    Router_mapings :Dict[str,Union[Callable]] = Field(default_factory=Dict)
    
    def _init_(self, name :str):
        self.name = name

    @classmethod
    def create_router(cls, 
                      state,
                      from_node :str,
                      direct_nodes : List[str] = None,
                      conditional_nodes : List[str] = None,
                      send : bool = False,
                      send_to :str = None,
                      ):
    
        def _routing_wrapper_(state,
                              route_from,
                              direct_nodes,
                              conditional_nodes,
                              send,
                              send_to,):
            
            if send:
                #Here internal_state_obj is of type : -> InternalState
                return [Send(send_to, {"Internal_state": internal_state_obj}) for internal_state_obj in state.send_list[route_from]]
            
            _next_nodes = direct_nodes
            _selected_nodes = state.routes[route_from]
            for node in conditional_nodes:
                if node in _selected_nodes:
                    _next_nodes.append(node)
            
            return _next_nodes
        
        if send and not send_to:
            raise ValueError("You must provide send_to node to for sending multiple states!")
        
        if not any(direct_nodes, conditional_nodes, send):
            raise ValidationErr(f"You must provide some way for routing from :{from_node}")
        
        wrapper_function = _routing_wrapper_(
            state,
            from_node,
            direct_nodes,
            conditional_nodes,
            send
        )
        
        cls.Router_mapings[from_node] = wrapper_function
        return True