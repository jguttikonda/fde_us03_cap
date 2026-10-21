from typing import Protocol

from aog_recovery.contracts.agent import AgentRole
from aog_recovery.contracts.tool import ToolName, ToolRequest, ToolResult


class ReadOnlyAdapter(Protocol):
    tool_name: ToolName
    allowed_roles: frozenset[AgentRole]

    def read(self, request: ToolRequest, caller_role: AgentRole) -> ToolResult: ...
