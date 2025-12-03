"""
Trajectory Logger - Execution audit trail for agent pipelines.

Provides detailed logging of each step in the extraction pipeline,
including tool calls, inputs/outputs, timing, and success/failure status.

This is essential for:
- Debugging extraction issues
- Understanding agent decision-making
- Compliance and audit requirements
- Performance optimization
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
import json


class StepStatus(str, Enum):
    """Status of an execution step."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TrajectoryStep:
    """
    A single step in the execution trajectory.
    
    Captures all relevant information about a tool execution,
    including timing, inputs, outputs, and any errors.
    """
    step_number: int
    step_name: str
    tool_name: str
    status: StepStatus = StepStatus.PENDING
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    
    # Input/Output
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    
    # Full data (optional, may be large)
    input_data: Optional[Any] = None
    output_data: Optional[Any] = None
    
    # Error information
    error: Optional[str] = None
    error_type: Optional[str] = None
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def start(self):
        """Mark step as started."""
        self.status = StepStatus.RUNNING
        self.started_at = datetime.utcnow()
    
    def complete(self, output_data: Any = None, output_summary: str = None):
        """Mark step as successfully completed."""
        self.status = StepStatus.SUCCESS
        self.completed_at = datetime.utcnow()
        self.output_data = output_data
        self.output_summary = output_summary
        self._calculate_duration()
    
    def fail(self, error: str, error_type: str = None):
        """Mark step as failed."""
        self.status = StepStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error = error
        self.error_type = error_type
        self._calculate_duration()
    
    def skip(self, reason: str = None):
        """Mark step as skipped."""
        self.status = StepStatus.SKIPPED
        self.completed_at = datetime.utcnow()
        if reason:
            self.metadata["skip_reason"] = reason
    
    def _calculate_duration(self):
        """Calculate step duration in milliseconds."""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            self.duration_ms = delta.total_seconds() * 1000
    
    def to_dict(self, include_full_data: bool = False) -> dict:
        """Convert step to dictionary for serialization."""
        result = {
            "step_number": self.step_number,
            "step_name": self.step_name,
            "tool_name": self.tool_name,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
        }
        
        if self.error:
            result["error"] = self.error
            result["error_type"] = self.error_type
        
        if self.metadata:
            result["metadata"] = self.metadata
        
        if include_full_data:
            result["input_data"] = self._serialize_data(self.input_data)
            result["output_data"] = self._serialize_data(self.output_data)
        
        return result
    
    def _serialize_data(self, data: Any) -> Any:
        """Safely serialize data for JSON output."""
        if data is None:
            return None
        if hasattr(data, "model_dump"):  # Pydantic model
            return data.model_dump()
        if hasattr(data, "__dict__"):  # Dataclass or object
            return {k: self._serialize_data(v) for k, v in data.__dict__.items()}
        if isinstance(data, (list, tuple)):
            return [self._serialize_data(item) for item in data]
        if isinstance(data, dict):
            return {k: self._serialize_data(v) for k, v in data.items()}
        if isinstance(data, datetime):
            return data.isoformat()
        return data


@dataclass
class Trajectory:
    """
    Complete execution trajectory for an agent run.
    
    Tracks:
    - All execution steps with timing and status
    - Overall pipeline success/failure
    - Aggregate statistics
    """
    agent_name: str
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    steps: List[TrajectoryStep] = field(default_factory=list)
    
    # Overall status
    success: bool = False
    final_error: Optional[str] = None
    
    # Input/Output summaries
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    
    def add_step(
        self,
        step_name: str,
        tool_name: str,
        input_summary: str = None,
        input_data: Any = None
    ) -> TrajectoryStep:
        """
        Add a new step to the trajectory.
        
        Args:
            step_name: Human-readable name for this step
            tool_name: Name of the tool being executed
            input_summary: Brief description of input
            input_data: Full input data (optional)
            
        Returns:
            The created TrajectoryStep (can be used to track completion)
        """
        step = TrajectoryStep(
            step_number=len(self.steps) + 1,
            step_name=step_name,
            tool_name=tool_name,
            input_summary=input_summary,
            input_data=input_data
        )
        self.steps.append(step)
        return step
    
    def complete(self, success: bool = True, error: str = None, output_summary: str = None):
        """
        Mark the trajectory as complete.
        
        Args:
            success: Whether the overall pipeline succeeded
            error: Error message if failed
            output_summary: Summary of final output
        """
        self.completed_at = datetime.utcnow()
        self.success = success
        self.final_error = error
        self.output_summary = output_summary
    
    @property
    def total_duration_ms(self) -> Optional[float]:
        """Total execution time in milliseconds."""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return delta.total_seconds() * 1000
        return None
    
    @property
    def step_count(self) -> int:
        """Number of steps in the trajectory."""
        return len(self.steps)
    
    @property
    def success_count(self) -> int:
        """Number of successful steps."""
        return sum(1 for s in self.steps if s.status == StepStatus.SUCCESS)
    
    @property
    def failed_count(self) -> int:
        """Number of failed steps."""
        return sum(1 for s in self.steps if s.status == StepStatus.FAILED)
    
    def get_statistics(self) -> dict:
        """Get aggregate statistics about the trajectory."""
        step_durations = [s.duration_ms for s in self.steps if s.duration_ms is not None]
        
        return {
            "total_steps": self.step_count,
            "successful_steps": self.success_count,
            "failed_steps": self.failed_count,
            "skipped_steps": sum(1 for s in self.steps if s.status == StepStatus.SKIPPED),
            "total_duration_ms": self.total_duration_ms,
            "avg_step_duration_ms": sum(step_durations) / len(step_durations) if step_durations else None,
            "slowest_step": max(
                ((s.step_name, s.duration_ms) for s in self.steps if s.duration_ms),
                key=lambda x: x[1],
                default=(None, None)
            )[0] if step_durations else None,
        }
    
    def to_dict(self, include_full_data: bool = False) -> dict:
        """
        Convert trajectory to dictionary for serialization.
        
        Args:
            include_full_data: Whether to include full input/output data for each step
            
        Returns:
            Dictionary representation of the trajectory
        """
        return {
            "agent_name": self.agent_name,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "success": self.success,
            "final_error": self.final_error,
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "statistics": self.get_statistics(),
            "steps": [step.to_dict(include_full_data) for step in self.steps]
        }
    
    def to_json(self, include_full_data: bool = False, indent: int = 2) -> str:
        """Convert trajectory to JSON string."""
        return json.dumps(self.to_dict(include_full_data), indent=indent, default=str)
    
    def __repr__(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        return f"<Trajectory: {self.agent_name} [{status}] {self.step_count} steps>"


class TrajectoryLogger:
    """
    Helper class for managing trajectory logging throughout agent execution.
    
    Usage:
        logger = TrajectoryLogger("ExtractionAgent")
        
        step = logger.start_step("Extract Entities", "entity_extraction")
        try:
            result = await extraction_tool.execute(input)
            logger.complete_step(step, result)
        except Exception as e:
            logger.fail_step(step, str(e))
        
        trajectory = logger.get_trajectory()
    """
    
    def __init__(self, agent_name: str, input_summary: str = None):
        """
        Initialize trajectory logger.
        
        Args:
            agent_name: Name of the agent being logged
            input_summary: Summary of the initial input
        """
        self.trajectory = Trajectory(agent_name=agent_name, input_summary=input_summary)
    
    def start_step(
        self,
        step_name: str,
        tool_name: str,
        input_summary: str = None,
        input_data: Any = None
    ) -> TrajectoryStep:
        """
        Start a new step and return the step object.
        
        Args:
            step_name: Human-readable name for the step
            tool_name: Name of the tool being executed
            input_summary: Brief description of input
            input_data: Full input data (optional)
            
        Returns:
            TrajectoryStep that has been started
        """
        step = self.trajectory.add_step(step_name, tool_name, input_summary, input_data)
        step.start()
        return step
    
    def complete_step(
        self,
        step: TrajectoryStep,
        output_data: Any = None,
        output_summary: str = None
    ):
        """
        Mark a step as successfully completed.
        
        Args:
            step: The step to complete
            output_data: Full output data (optional)
            output_summary: Brief description of output
        """
        step.complete(output_data, output_summary)
    
    def fail_step(self, step: TrajectoryStep, error: str, error_type: str = None):
        """
        Mark a step as failed.
        
        Args:
            step: The step that failed
            error: Error message
            error_type: Type/category of error
        """
        step.fail(error, error_type)
    
    def skip_step(self, step_name: str, tool_name: str, reason: str = None):
        """
        Record a skipped step.
        
        Args:
            step_name: Name of the skipped step
            tool_name: Name of the tool that would have been used
            reason: Why the step was skipped
        """
        step = self.trajectory.add_step(step_name, tool_name)
        step.skip(reason)
    
    def complete(self, success: bool = True, error: str = None, output_summary: str = None):
        """
        Complete the trajectory.
        
        Args:
            success: Whether the overall pipeline succeeded
            error: Error message if failed
            output_summary: Summary of final output
        """
        self.trajectory.complete(success, error, output_summary)
    
    def get_trajectory(self) -> Trajectory:
        """Get the completed trajectory."""
        return self.trajectory

