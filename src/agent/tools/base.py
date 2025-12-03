"""
Abstract base class for agent tools.

All tools follow a standardized contract:
1. name: Unique identifier for the tool
2. description: LLM-readable description of tool purpose
3. execute(): Async method that performs the tool's action
4. Returns ToolResult with success status and data/error
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, Dict
from datetime import datetime


@dataclass
class ToolResult:
    """
    Standardized result from tool execution.
    
    Attributes:
        success: Whether the tool executed successfully
        data: Output data if successful (type depends on tool)
        error: Error message if failed
        metadata: Additional execution metadata (timing, retries, etc.)
    """
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Add timestamp to metadata."""
        if "timestamp" not in self.metadata:
            self.metadata["timestamp"] = datetime.utcnow().isoformat()
    
    @classmethod
    def ok(cls, data: Any, **metadata) -> "ToolResult":
        """Create successful result."""
        return cls(success=True, data=data, metadata=metadata)
    
    @classmethod
    def fail(cls, error: str, **metadata) -> "ToolResult":
        """Create failed result."""
        return cls(success=False, error=error, metadata=metadata)


class Tool(ABC):
    """
    Abstract base class for all agent tools.
    
    Each tool must:
    1. Define a unique name and description
    2. Implement async execute() method
    3. Return standardized ToolResult
    
    Tools are designed to be:
    - Independently testable (mock dependencies)
    - Composable (output of one feeds into another)
    - Observable (via ToolResult metadata)
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for the tool."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human/LLM-readable description of what this tool does."""
        pass
    
    @abstractmethod
    async def execute(self, input_data: Any) -> ToolResult:
        """
        Execute the tool with given input.
        
        Args:
            input_data: Input for the tool (type depends on specific tool)
            
        Returns:
            ToolResult with success status and output data or error
        """
        pass
    
    def __repr__(self) -> str:
        return f"<Tool: {self.name}>"


class BatchTool(Tool):
    """
    Extension of Tool for batch operations.
    
    Useful for tools that can process multiple items in parallel,
    like looking up multiple ICD codes at once.
    """
    
    @abstractmethod
    async def execute_batch(self, items: list) -> list[ToolResult]:
        """
        Execute tool on multiple items.
        
        Args:
            items: List of inputs to process
            
        Returns:
            List of ToolResults, one per input item
        """
        pass

