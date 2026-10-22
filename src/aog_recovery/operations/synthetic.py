"""Deterministic synthetic Operations scenarios (ARD-SYS-008, ARD-TST-009).

All data is invented for tests and demonstration: no real airline, flight, or package data.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from aog_recovery.adapters.local import LocalReadOnlyAdapter, MockResponseMode
from aog_recovery.adapters.protocols import ReadOnlyAdapter
from aog_recovery.contracts.case import AogCase, TraceContext
from aog_recovery.contracts.tool import ToolName
from aog_recovery.operations.models import (
    AircraftRecord,
    AircraftStatus,
    AlternateFlight,
    AlternateFlightData,
    CandidateOption,
    CarrierType,
    CrewCoverage,
    DisruptionKind,
    DisruptionRecord,
    DisruptionSeverity,
    EtaBasis,
    FleetAvailabilityData,
    FlightRecord,
    FlightScheduleData,
    NetworkStatusData,
    OperationsRequest,
    OptionKind,
    PackageGroup,
    PackageLoadData,
    PackageServiceLevel,
    ReroutePolicy,
)

T0 = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
SOURCE = "synthetic-operations-fixture"


def at(hour: int, minute: int = 0, day_offset: int = 0) -> datetime:
    return datetime(2026, 10, 21 + day_offset, hour, minute, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class Scenario:
    name: str
    title: str
    description: str
    request: OperationsRequest
    adapters: Mapping[ToolName, ReadOnlyAdapter]


def default_case() -> AogCase:
    return AogCase(
        case_id="AOG-SYN-0001",
        aircraft_id="N123AB",
        event_type="hydraulic_pump_failure",
        defect_summary="Hydraulic pump P-110 failure on N123AB at MIA",
        location="MIA",
        event_at=T0,
        created_at=T0 + timedelta(minutes=5),
        schema_version="1.0",
        trace_context=TraceContext(trace_id="trace-syn-0001", correlation_id="corr-syn-0001"),
    )


def default_schedule(
    *,
    service_critical: bool = False,
    crew: CrewCoverage = CrewCoverage.AVAILABLE,
    crew_available_from: datetime | None = None,
) -> FlightScheduleData:
    return FlightScheduleData(
        flights=(
            FlightRecord(
                flight_number="FX103",
                route="MIA-ORD",
                origin="MIA",
                destination="ORD",
                required_aircraft_type="A320",
                scheduled_departure=at(14),
                scheduled_arrival=at(17),
                assigned_aircraft_id="N123AB",
                service_critical=service_critical,
                crew_coverage=crew,
                crew_available_from=crew_available_from,
            ),
            FlightRecord(
                flight_number="FX440",
                route="ORD-MIA",
                origin="ORD",
                destination="MIA",
                required_aircraft_type="A320",
                scheduled_departure=at(23),
                scheduled_arrival=at(2, day_offset=1),
                assigned_aircraft_id="N981FX",
                service_critical=False,
                crew_coverage=CrewCoverage.AVAILABLE,
            ),
        )
    )


def default_fleet() -> FleetAvailabilityData:
    return FleetAvailabilityData(
        aircraft=(
            AircraftRecord(
                aircraft_id="N980FX",
                aircraft_type="A320",
                station="MIA",
                status=AircraftStatus.SERVICEABLE,
                available_from=at(14, 30),
                positioning_minutes=0,
                package_capacity=900,
            ),
            AircraftRecord(
                aircraft_id="N981FX",
                aircraft_type="A320",
                station="FLL",
                status=AircraftStatus.SERVICEABLE,
                available_from=at(15),
                positioning_minutes=60,
                package_capacity=700,
            ),
            AircraftRecord(
                aircraft_id="N700XX",
                aircraft_type="B767",
                station="MIA",
                status=AircraftStatus.SERVICEABLE,
                available_from=at(13),
                positioning_minutes=0,
                package_capacity=2000,
            ),
            AircraftRecord(
                aircraft_id="N205AB",
                aircraft_type="A320",
                station="MIA",
                status=AircraftStatus.IN_MAINTENANCE,
                available_from=at(13),
                positioning_minutes=0,
                package_capacity=900,
            ),
        )
    )


def default_packages() -> PackageLoadData:
    """Proposal test case 6: 1,200 packages (700 priority), 17:30 cut-off."""
    return PackageLoadData(
        groups=(
            PackageGroup(
                group_id="FX103-PRIORITY",
                flight_number="FX103",
                service_level=PackageServiceLevel.PRIORITY,
                time_critical=True,
                count=700,
                cutoff_at=at(17, 30),
            ),
            PackageGroup(
                group_id="FX103-STANDARD",
                flight_number="FX103",
                service_level=PackageServiceLevel.STANDARD,
                time_critical=False,
                count=500,
                cutoff_at=at(17, 30),
            ),
        ),
    )


BOTH_LEVELS = (PackageServiceLevel.PRIORITY, PackageServiceLevel.STANDARD)


def default_alternate_flights() -> AlternateFlightData:
    """Mock flight search: own-network and partner flights with spare package capacity."""
    return AlternateFlightData(
        flights=(
            AlternateFlight(
                flight_number="FX505",
                carrier_type=CarrierType.OWN,
                carrier_name="Company Express",
                origin="MIA",
                destination="ORD",
                departure_at=at(16),
                arrival_at=at(19),
                available_capacity=150,
                cost_per_package_usd=5,
                accepted_service_levels=BOTH_LEVELS,
            ),
            AlternateFlight(
                flight_number="PX150",
                carrier_type=CarrierType.PARTNER,
                carrier_name="Partner Air Cargo",
                origin="MIA",
                destination="ORD",
                departure_at=at(15, 30),
                arrival_at=at(18, 30),
                available_capacity=100,
                cost_per_package_usd=18,
                accepted_service_levels=(PackageServiceLevel.STANDARD,),
                booking_deadline=at(15),
            ),
            AlternateFlight(
                flight_number="PX220",
                carrier_type=CarrierType.PARTNER,
                carrier_name="Partner Air Cargo",
                origin="MIA",
                destination="ORD",
                departure_at=at(17),
                arrival_at=at(20),
                available_capacity=400,
                cost_per_package_usd=22,
                accepted_service_levels=BOTH_LEVELS,
                booking_deadline=at(15, 30),
            ),
            AlternateFlight(
                flight_number="PX310",
                carrier_type=CarrierType.PARTNER,
                carrier_name="Northern Freight Partner",
                origin="MIA",
                destination="ORD",
                departure_at=at(18, 30),
                arrival_at=at(21, 30),
                available_capacity=300,
                cost_per_package_usd=18,
                accepted_service_levels=BOTH_LEVELS,
                booking_deadline=at(16, 30),
            ),
            AlternateFlight(
                flight_number="FX620",
                carrier_type=CarrierType.OWN,
                carrier_name="Company Express",
                origin="ORD",
                destination="MIA",
                departure_at=at(18),
                arrival_at=at(21),
                available_capacity=500,
                cost_per_package_usd=5,
                accepted_service_levels=BOTH_LEVELS,
            ),
        )
    )


def default_network(description: str = "Thunderstorms forecast near ORD") -> NetworkStatusData:
    return NetworkStatusData(
        disruptions=(
            DisruptionRecord(
                disruption_id="disruption-ord-001",
                kind=DisruptionKind.WEATHER,
                station="ORD",
                severity=DisruptionSeverity.MEDIUM,
                description=description,
            ),
        )
    )


def make_adapters(
    schedule: FlightScheduleData,
    fleet: FleetAvailabilityData,
    packages: PackageLoadData,
    network: NetworkStatusData,
    *,
    alternates: AlternateFlightData | None = None,
    modes: Mapping[ToolName, MockResponseMode] | None = None,
    retrieved_at: datetime = T0,
) -> dict[ToolName, ReadOnlyAdapter]:
    chosen = modes or {}
    data = {
        ToolName.FLIGHT_SCHEDULE: schedule,
        ToolName.FLEET_AVAILABILITY: fleet,
        ToolName.PACKAGE_LOAD: packages,
        ToolName.ALTERNATE_FLIGHTS: alternates or default_alternate_flights(),
        ToolName.OPERATIONS_STATUS: network,
    }
    return {
        tool: LocalReadOnlyAdapter(
            tool_name=tool,
            source=f"{SOURCE}:{tool.value}",
            fixture_timestamp=retrieved_at,
            fixture_data=model.model_dump(),
            response_mode=chosen.get(tool, MockResponseMode.SUCCESS),
        )
        for tool, model in data.items()
    }


def default_adapters(
    modes: Mapping[ToolName, MockResponseMode] | None = None,
) -> dict[ToolName, ReadOnlyAdapter]:
    return make_adapters(
        default_schedule(), default_fleet(), default_packages(), default_network(), modes=modes
    )


def repair_original(
    eta: datetime | None = None, basis: EtaBasis = EtaBasis.CONFIRMED
) -> CandidateOption:
    return CandidateOption(
        option_id="OPT-REPAIR-P110",
        kind=OptionKind.REPAIR_ORIGINAL,
        description="Repair with original pump P-110 from local stock",
        readiness_eta=eta or at(15),
        eta_basis=basis,
        eta_evidence_references=("evidence-maintenance-eta-001",),
    )


def repair_alternate(
    eta: datetime | None = None, basis: EtaBasis = EtaBasis.ESTIMATED
) -> CandidateOption:
    return CandidateOption(
        option_id="OPT-REPAIR-P120",
        kind=OptionKind.REPAIR_ALTERNATE,
        description="Repair with upgraded pump P-120 transferred from another station",
        readiness_eta=eta or at(19),
        eta_basis=basis,
        eta_evidence_references=("evidence-materials-eta-001",),
    )


def swap_option() -> CandidateOption:
    return CandidateOption(
        option_id="OPT-SWAP",
        kind=OptionKind.SWAP,
        description="Substitute a spare aircraft on FX103",
    )


def delay_option(eta: datetime | None = None) -> CandidateOption:
    return CandidateOption(
        option_id="OPT-DELAY",
        kind=OptionKind.DELAY,
        description="Hold FX103 until the original aircraft is repaired",
        readiness_eta=eta or at(17, 30),
        eta_basis=EtaBasis.CONFIRMED,
        eta_evidence_references=("evidence-maintenance-eta-002",),
    )


def request_for(
    *candidates: CandidateOption,
    evaluated_at: datetime = T0 + timedelta(minutes=10),
    reroute_policy: ReroutePolicy | None = None,
) -> OperationsRequest:
    return OperationsRequest(
        schema_version="1.0",
        request_id="req-ops-0001",
        case=default_case(),
        affected_flight_numbers=("FX103",),
        candidates=tuple(candidates),
        evaluated_at=evaluated_at,
        reroute_policy=reroute_policy or ReroutePolicy(),
    )


def scenario_normal_repair() -> Scenario:
    return Scenario(
        name="normal_repair",
        title="Part and crew available, no conflict (proposal test case 1)",
        description="Repair with the original part; all sources current; packages held in place.",
        request=request_for(repair_original()),
        adapters=default_adapters(),
    )


def scenario_full_options() -> Scenario:
    return Scenario(
        name="full_options",
        title="Repair, alternate-part repair, and swap compared (test cases 2, 5, 6)",
        description="Three candidates with different delay, package, and cost outcomes.",
        request=request_for(repair_original(), repair_alternate(), swap_option()),
        adapters=default_adapters(),
    )


def scenario_swap_capacity() -> Scenario:
    return Scenario(
        name="swap_capacity",
        title="Swap limited by spare aircraft capacity (proposal test case 6)",
        description="1,200 packages (700 priority); spare aircraft holds 900; 17:30 cut-off.",
        request=request_for(swap_option()),
        adapters=make_adapters(
            default_schedule(),
            default_fleet(),
            default_packages(),
            default_network(),
            alternates=AlternateFlightData(flights=()),
        ),
    )


def scenario_conflicting_estimates() -> Scenario:
    return Scenario(
        name="conflicting_estimates",
        title="Maintenance says 3 hours, crew availability says 7 hours (conflicting data)",
        description="Crew is available only at 19:00; the ETA implies 15:30 readiness.",
        request=request_for(repair_original()),
        adapters=make_adapters(
            default_schedule(crew=CrewCoverage.DELAYED, crew_available_from=at(19)),
            default_fleet(),
            default_packages(),
            default_network(),
        ),
    )


def scenario_package_timeout() -> Scenario:
    return Scenario(
        name="package_timeout",
        title="Package load service times out (ARD-RES-002)",
        description="Flight analysis continues; package impact is named as missing analysis.",
        request=request_for(repair_original()),
        adapters=default_adapters({ToolName.PACKAGE_LOAD: MockResponseMode.TIMEOUT}),
    )


def scenario_partner_reroute() -> Scenario:
    return Scenario(
        name="partner_reroute",
        title="Late repair: reroute packages on own-network, then partner flights",
        description=(
            "Repair is ready only at 19:00. Packages need other flights: own-network capacity "
            "is used first, then partner flights, within booking deadlines and cut-offs."
        ),
        request=request_for(delay_option(at(19))),
        adapters=default_adapters(),
    )


def scenario_own_network_only() -> Scenario:
    return Scenario(
        name="own_network_only",
        title="Late repair, partner flights not permitted",
        description="Same late repair, but policy allows only the company's own flights.",
        request=request_for(
            delay_option(at(19)), reroute_policy=ReroutePolicy(allow_partner_flights=False)
        ),
        adapters=default_adapters(),
    )


SCENARIOS: dict[str, Callable[[], Scenario]] = {
    "normal_repair": scenario_normal_repair,
    "full_options": scenario_full_options,
    "swap_capacity": scenario_swap_capacity,
    "partner_reroute": scenario_partner_reroute,
    "own_network_only": scenario_own_network_only,
    "conflicting_estimates": scenario_conflicting_estimates,
    "package_timeout": scenario_package_timeout,
}
