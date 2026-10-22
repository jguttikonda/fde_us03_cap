from aog_recovery.controller.demo_service import DemoControllerService


async def test_demo_service_requests_missing_intake_fields_without_running_agents() -> None:
    result = await DemoControllerService().assess(
        {
            "scenario_id": "part_available_remote",
            "case": {"case_id": "AOG-CHAT-001"},
        }
    )

    assert result["status"] == "awaiting_data"
    assert result["human_approval_required"] is True
    assert result["findings"]
    assert "No specialist assessment has run" in result["chat_response"]


async def test_demo_service_rejects_unknown_scenario_without_fallback() -> None:
    result = await DemoControllerService().assess(
        {"scenario_id": "part_found_somewhere", "case": {}}
    )

    assert result["status"] == "rejected"
    assert result["findings"][0]["code"] == "unknown_synthetic_scenario"
    assert "scenario is not available" in result["chat_response"]


async def test_demo_service_rejects_operational_action_fields() -> None:
    result = await DemoControllerService().assess(
        {
            "scenario_id": "part_available_remote",
            "execute_transfer": True,
            "case": {"case_id": "AOG-CHAT-001"},
        }
    )

    assert result["status"] == "awaiting_data"
    assert any(finding["code"] == "extra_forbidden" for finding in result["findings"])
