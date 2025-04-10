from typing import Type, Dict, Any, Optional, Union, Tuple
from pydantic import BaseModel, ValidationError
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain.chat_models.base import BaseChatModel
import asyncio
import logging
from datetime import datetime
from functools import lru_cache
import json
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

class LLMResponseStatus(Enum):
    """Enum for tracking LLM response status"""
    SUCCESS = "success"
    RETRY = "retry"
    FAILURE = "failure"

class LLMException(Exception):
    """Base exception class for LLM-related errors"""
    pass

class LLMConfigurationError(LLMException):
    """Raised when there's an issue with LLM configuration"""
    pass

class LLMResponseError(LLMException):
    """Raised when there's an issue with LLM response"""
    pass

class PromptFormattingError(LLMException):
    """Raised when there's an issue with prompt formatting"""
    pass

class StructuredLLMHandler:
    """
    A production-grade handler for structured LLM responses with fallback support.
    
    Attributes:
        _llm_dict (Dict[str, BaseChatModel]): Dictionary containing main and fallback LLMs
        _cache_ttl (int): Time-to-live for cached responses in seconds
        _max_retries (int): Maximum number of retry attempts
        _retry_delay (float): Delay between retries in seconds
    """

    def __init__(
        self,
        llm_dict: Dict[str, BaseChatModel],
        fallback_llm : str = None,
        cache_ttl: int = 3600,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Initialize the StructuredLLMHandler.

        Args:
            llm_dict: Dictionary containing 'main_llm' and 'fall_back_llm'
            cache_ttl: Cache time-to-live in seconds (default: 1 hour)
            max_retries: Maximum number of retry attempts (default: 3)
            retry_delay: Delay between retries in seconds (default: 1.0)

        Raises:
            LLMConfigurationError: If LLM configuration is invalid
        """
        # self._validate_llm_dict(llm_dict)
        self._llm_dict = llm_dict
        self._main_llm , self._fallback_llm = self._set_llm(llm_dict, fallback_llm)
        self._cache_ttl = cache_ttl
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._response_cache = {}
        
    @staticmethod
    def _set_llm(
        llm_dict: Dict[str, BaseChatModel],
        fallback_llm_key: Optional[str] = None
    ) -> Tuple[Optional[BaseChatModel], Optional[BaseChatModel]]:
        """
        Sets the main and fallback LLMs from the provided dictionary.

        Args:
            llm_dict (Dict[str, BaseChatModel]): Dictionary of LLM instances.
            fallback_llm_key (Optional[str]): Optional key for fallback LLM.

        Returns:
            Tuple[Optional[BaseChatModel], Optional[BaseChatModel]]: (main_llm, fallback_llm)

        Raises:
            ValueError: If llm_dict is empty or fallback key doesn't exist.
        """
        if not llm_dict:
            raise ValueError("LLM dictionary cannot be empty.")

        keys = list(llm_dict.keys())

        main_llm = llm_dict[keys[0]]

        fallback_llm = None
        if fallback_llm_key:
            if fallback_llm_key not in llm_dict:
                LOGGER.warning(f"Fallback LLM key '{fallback_llm_key}' not found in llm_dict.")
            else:
                fallback_llm = llm_dict[fallback_llm_key]
        elif len(keys) > 1:
            fallback_llm = llm_dict[keys[1]]

        return main_llm, fallback_llm
            
    @staticmethod
    def _validate_llm_dict(llm_dict: Dict[str, BaseChatModel]) -> None:
        """
        Validate the LLM dictionary configuration.

        Args:
            llm_dict: Dictionary containing LLM instances

        Raises:
            LLMConfigurationError: If configuration is invalid
        """

        for key, llm_object in llm_dict.items():
            if not isinstance(llm_object, BaseChatModel):
                raise LLMConfigurationError(
                    f"LLM of {key} must be an instance of BaseChatModel, Got : {type(llm_object)} Object."
                )

    def _get_parser(self, output_structure: Type[BaseModel]) -> PydanticOutputParser:
        """
        Get or create a cached parser for the output structure.

        Args:
            output_structure: Pydantic model class for output structure

        Returns:
            PydanticOutputParser instance
        """
        return PydanticOutputParser(pydantic_object=output_structure)

    async def _format_prompt(
        self,
        prompt_template: str,
        output_structure: Type[BaseModel],
        **kwargs
    ) -> str:
        """
        Format the prompt with error handling.

        Args:
            prompt_template: Template string with formatting placeholders
            output_structure: Pydantic model for output structure
            **kwargs: Variables for prompt formatting

        Returns:
            Formatted prompt string

        Raises:
            PromptFormattingError: If prompt formatting fails
        """
        try:
            parser = self._get_parser(output_structure)
            template = PromptTemplate(
                template=prompt_template,
                partial_variables={"format_instructions": parser.get_format_instructions()}
            )
            return template.format(**kwargs)
        except Exception as e:
            LOGGER.exception("Failed to format prompt")
            raise PromptFormattingError(f"Prompt formatting failed: {str(e)}") from e

    async def _handle_llm_response(
        self,
        llm: BaseChatModel,
        message: str,
        output_structure: Type[BaseModel]
    ) -> tuple[LLMResponseStatus, Optional[BaseModel]]:
        """
        Handle LLM response with validation and error handling.

        Args:
            llm: LLM instance to use
            message: Formatted prompt message
            output_structure: Expected output structure

        Returns:
            Tuple of (response status, structured response or None)
        """
        try:
            structured_llm = llm.with_structured_output(output_structure)
            response = await structured_llm.ainvoke(message)
            
            if not response:
                LOGGER.warning("Empty response received from LLM")
                return LLMResponseStatus.RETRY, None

            # Validate response against the output structure
            if not isinstance(response, output_structure):
                LOGGER.error(f"Invalid response type: {type(response)}")
                return LLMResponseStatus.RETRY, None

            return LLMResponseStatus.SUCCESS, response

        except ValidationError as e:
            LOGGER.error(f"Response validation error: {str(e)}")
            # return LLMResponseStatus.RETRY, None
            raise e 
        except Exception as e:
            LOGGER.error(f"LLM invocation error: {str(e)}", exc_info=True)
            raise e 
            # return LLMResponseStatus.RETRY, None

    def _get_cache_key(self, prompt: str, output_structure: Type[BaseModel]) -> str:
        """
        Generate a unique cache key for the prompt and output structure.

        Args:
            prompt: Formatted prompt
            output_structure: Output structure class

        Returns:
            Cache key string
        """
        return f"{hash(prompt)}:{output_structure.__name__}"

    async def get_structured_response(
        self,
        output_structure: Type[BaseModel],
        prompt: str,
        use_model :str = None,
        retry_attempts: Optional[int] = None,
        use_cache: bool = False,
        **kwargs
    ) -> BaseModel:
        """
        Get a structured response from the LLM with caching, retry, and fallback support.

        Args:
            output_structure: Pydantic model for structured output
            prompt: Prompt template
            retry_attempts: Number of retry attempts (optional)
            use_cache: Whether to use response caching
            **kwargs: Variables for prompt formatting

        Returns:
            Instance of output_structure

        Raises:
            LLMException: If all LLM attempts fail
            PromptFormattingError: If prompt formatting fails
        """
        retry_attempts = retry_attempts or self._max_retries
        
        # Format the prompt
        formatted_prompt = await self._format_prompt(prompt, output_structure, **kwargs)
        main_model = self._llm_dict[use_model] if use_model else self._main_llm
        # # Check cache if enabled
        # if use_cache:
        #     cache_key = self._get_cache_key(formatted_prompt, output_structure)
        #     cached_response = self._response_cache.get(cache_key)
        #     if cached_response:
        #         cache_time, response = cached_response
        #         if (datetime.now().timestamp() - cache_time) < self._cache_ttl:
        #             LOGGER.info("Returning cached response")
        #             return response

        # Try main LLM with retries
        for attempt in range(1, retry_attempts + 1):
            LOGGER.info(f"Attempt {attempt}/{retry_attempts} with main LLM")
            status, response = await self._handle_llm_response(
                main_model,
                formatted_prompt,
                output_structure
            )

            if status == LLMResponseStatus.SUCCESS and response:
            #     if use_cache:
            #         self._response_cache[cache_key] = (datetime.now().timestamp(), response)
                return response

            if attempt < retry_attempts:
                await asyncio.sleep(self._retry_delay)

        # Try fallback LLM
        LOGGER.warning("Main LLM failed, trying fallback LLM")
        status, response = await self._handle_llm_response(
            self._fallback_llm,
            formatted_prompt,
            output_structure
        )

        if status == LLMResponseStatus.SUCCESS and response:
            # if use_cache:
            #     self._response_cache[cache_key] = (datetime.now().timestamp(), response)
            return response

        raise LLMResponseError(
            "Failed to get structured response from both main and fallback LLMs"
        )

    # async def clear_cache(self) -> None:
    #     """Clear the response cache"""
    #     self._response_cache.clear()