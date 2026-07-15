from __future__ import annotations

from typing import List

from pydantic import BaseModel, ConfigDict


class ExpectedVehicle(BaseModel):
    """Ground truth for one vehicle passing the camera."""

    model_config = ConfigDict(frozen=True)

    plate: str  # "" = vehicle without plates (ask us about the rickshaw)
    color: str
    make: str
    direction: str  # IN | OUT
    appear_at: int  # ms, recording time
    vehicle_type: str = "car"


class RecordingCase(BaseModel):
    """One recording replayed against the system: N vehicles, one noise profile."""

    model_config = ConfigDict(frozen=True)

    lot_name: str
    case_name: str
    recording: str
    duration_ms: int
    all_vehicles: List[ExpectedVehicle]
    noise: dict = {}

    @property
    def case_id(self) -> str:
        return f"{self.lot_name}__{self.case_name}"


class VehicleCase(RecordingCase):
    """The same recording, but focused on one vehicle — the unit of parametrization."""

    current: ExpectedVehicle
