from typing import Optional, Dict, Any
import time
from contextlib import contextmanager
from app.config import Config

try:
    from agentops import AgentOps
    AGENTOPS_AVAILABLE = True
except ImportError:
    AGENTOPS_AVAILABLE = False
    print("Warning: AgentOps not available. Install with: pip install agentops")


class AgentOpsInstrumentation:
    """Wrapper for AgentOps instrumentation."""
    
    def __init__(self):
        """Initialize AgentOps."""
        self.tracer: Optional[Any] = None
        if AGENTOPS_AVAILABLE and Config.AGENTOPS_API_KEY:
            try:
                self.tracer = AgentOps(
                    api_key=Config.AGENTOPS_API_KEY,
                    tags=[Config.AGENT_SERVICE_NAME],
                    instrument_function_calls=True
                )
            except Exception as e:
                print(f"Warning: Failed to initialize AgentOps: {e}")
                self.tracer = None
    
    @contextmanager
    def trace(self, name: str, tags: Optional[Dict[str, str]] = None):
        """
        Context manager for creating traces.
        
        Args:
            name: Name of the trace
            tags: Optional dictionary of tags
        """
        if not self.tracer:
            # No-op if AgentOps not available
            yield None
            return
        
        try:
            # Create trace
            trace = self.tracer.create_trace(name=name, tags=tags or {})
            start_time = time.time()
            yield trace
            
            # Log completion
            duration = time.time() - start_time
            if trace:
                self.tracer.record(
                    f"{name}_completed",
                    metadata={"duration_seconds": duration}
                )
        except Exception as e:
            print(f"Warning: AgentOps trace error: {e}")
            yield None
    
    def log_event(
        self,
        event_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log an event to AgentOps.
        
        Args:
            event_name: Name of the event
            metadata: Optional metadata dictionary
        """
        if not self.tracer:
            return
        
        try:
            self.tracer.record(event_name, metadata=metadata or {})
        except Exception as e:
            print(f"Warning: AgentOps log error: {e}")
    
    def end_session(self):
        """End AgentOps session."""
        if self.tracer:
            try:
                self.tracer.end_session("Success")
            except Exception as e:
                print(f"Warning: AgentOps end session error: {e}")


# Global instance
_instrumentation: Optional[AgentOpsInstrumentation] = None


def get_instrumentation() -> AgentOpsInstrumentation:
    """Get or create global instrumentation instance."""
    global _instrumentation
    if _instrumentation is None:
        _instrumentation = AgentOpsInstrumentation()
    return _instrumentation

