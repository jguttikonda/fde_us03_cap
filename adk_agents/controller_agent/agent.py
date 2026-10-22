"""ADK Web root for the synthetic Controller demonstration."""

from aog_recovery.controller.demo_adk_agent import build_controller_demo_adk_agent
from aog_recovery.operations.settings import OperationsSettings

root_agent = build_controller_demo_adk_agent(
    OperationsSettings(),
    require_model_credential=True,
)
