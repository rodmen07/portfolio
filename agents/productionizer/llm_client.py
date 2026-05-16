"""
Unified LLM client supporting both Anthropic Claude and OpenAI GPT models.
Abstracts away API differences for seamless model swapping.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResponse:
    """Unified response format from any LLM provider."""
    content: list[Any]
    stop_reason: str
    input_tokens: int
    output_tokens: int
    raw_response: Any


class UnifiedLLMClient:
    """Unified interface for Claude (Anthropic) and GPT (OpenAI) models."""
    
    def __init__(self, model: str | None = None):
        self.model = model or self._detect_model()
        self._client = None
        self._provider = self._detect_provider()
    
    def _detect_provider(self) -> str:
        """Detect which provider based on model name."""
        if "gpt" in self.model.lower():
            return "openai"
        elif "claude" in self.model.lower():
            return "anthropic"
        else:
            raise ValueError(f"Unknown model: {self.model}")
    
    def _detect_model(self) -> str:
        """Detect model from environment or use default."""
        model = os.environ.get("LLM_MODEL")
        if model:
            return model
        # Default to GPT-4o Mini for cost efficiency
        return "gpt-4o-mini"
    
    @property
    def provider(self) -> str:
        return self._provider
    
    def _get_anthropic_client(self) -> Any:
        """Lazy load Anthropic client."""
        if self._provider != "anthropic":
            raise ValueError("Model is not Claude")
        
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        return anthropic.Anthropic(api_key=api_key)
    
    def _get_openai_client(self) -> Any:
        """Lazy load OpenAI client."""
        if self._provider != "openai":
            raise ValueError("Model is not GPT")
        
        import openai
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")
        return openai.OpenAI(api_key=api_key)
    
    def create_message(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 8096,
    ) -> LLMResponse:
        """Create a message using the configured model."""
        if self._provider == "anthropic":
            return self._create_anthropic_message(system, messages, tools, max_tokens)
        else:
            return self._create_openai_message(system, messages, tools, max_tokens)
    
    def _create_anthropic_message(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 8096,
    ) -> LLMResponse:
        """Create message via Anthropic API."""
        client = self._get_anthropic_client()
        
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
        
        response = client.messages.create(**kwargs)
        
        return LLMResponse(
            content=response.content,
            stop_reason=response.stop_reason,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            raw_response=response,
        )
    
    def _create_openai_message(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 8096,
    ) -> LLMResponse:
        """Create message via OpenAI API."""
        client = self._get_openai_client()
        
        # Prepare messages with system prompt
        full_messages = [{"role": "system", "content": system}] + messages
        
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": full_messages,
        }
        if tools:
            # Convert Anthropic tool format to OpenAI format if needed
            kwargs["tools"] = self._convert_tools_to_openai(tools)
        
        response = client.chat.completions.create(**kwargs)
        
        # Convert OpenAI response to unified format
        content = []
        for choice in response.choices:
            if choice.message.content:
                content.append({"type": "text", "text": choice.message.content})
            
            # Handle tool calls
            if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
                for tool_call in choice.message.tool_calls:
                    content.append({
                        "type": "tool_use",
                        "id": tool_call.id,
                        "name": tool_call.function.name,
                        "input": tool_call.function.arguments if isinstance(tool_call.function.arguments, dict) else {},
                    })
        
        # Determine stop reason
        stop_reason = "end_turn"
        if response.choices and response.choices[0].finish_reason == "tool_calls":
            stop_reason = "tool_use"
        
        return LLMResponse(
            content=content,
            stop_reason=stop_reason,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            raw_response=response,
        )
    
    @staticmethod
    def _convert_tools_to_openai(anthropic_tools: list[dict]) -> list[dict]:
        """Convert Anthropic tool format to OpenAI tool format."""
        openai_tools = []
        for tool in anthropic_tools:
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                }
            }
            openai_tools.append(openai_tool)
        return openai_tools


def create_client(model: str | None = None) -> UnifiedLLMClient:
    """Factory function to create a unified LLM client."""
    return UnifiedLLMClient(model)
