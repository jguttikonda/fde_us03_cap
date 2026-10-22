"""ADK Web entry point for the synthetic AOG recovery chat."""

from aog_recovery.controller.adk_agent import build_controller_adk_agent
from aog_recovery.controller.demo_service import DemoControllerService

root_agent = build_controller_adk_agent(DemoControllerService())
