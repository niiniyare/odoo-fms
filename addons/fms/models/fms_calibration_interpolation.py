"""Pure interpolation logic for calibration chart dip-height → volume conversion.

Isolated here so it can be used by fms.tank.dip.reading (and later by
ATG/PTS-2 imports) without duplicating the algorithm.

This module contains NO Odoo ORM code — just plain Python so it is trivially
unit-testable without a database.
"""


class CalibrationInterpolationError(Exception):
    """Raised when the dip height is outside the chart's calibrated range."""


def interpolate_volume(dip_height_mm: float, lines: list[tuple[float, float]]) -> float:
    """Linear interpolation of volume from a calibration strapping table.

    Args:
        dip_height_mm: Measured dip height in millimetres (must be >= 0).
        lines: List of (dip_height_mm, volume_litres) tuples representing the
               calibration chart, sorted ascending by dip_height_mm.
               Must contain at least two entries.

    Returns:
        Interpolated volume in litres (float).

    Raises:
        CalibrationInterpolationError: If dip_height_mm is below the chart's
            minimum or above its maximum, or if the chart has fewer than two rows.
        ValueError: If dip_height_mm is negative.
    """
    if dip_height_mm < 0:
        raise ValueError(f"Dip height {dip_height_mm} mm cannot be negative.")

    if len(lines) < 2:
        raise CalibrationInterpolationError(
            "Calibration chart has fewer than 2 rows — cannot interpolate."
        )

    # Sort defensively in case caller did not sort
    sorted_lines = sorted(lines, key=lambda t: t[0])

    lo_h, lo_v = sorted_lines[0]
    hi_h, hi_v = sorted_lines[-1]

    if dip_height_mm < lo_h:
        raise CalibrationInterpolationError(
            f"Dip height {dip_height_mm:.1f} mm is below the chart minimum "
            f"{lo_h:.1f} mm."
        )
    if dip_height_mm > hi_h:
        raise CalibrationInterpolationError(
            f"Dip height {dip_height_mm:.1f} mm exceeds the chart maximum "
            f"{hi_h:.1f} mm."
        )

    # Exact match — no interpolation needed
    for h, v in sorted_lines:
        if abs(h - dip_height_mm) < 1e-9:
            return v

    # Find the bracketing pair
    for i in range(len(sorted_lines) - 1):
        h0, v0 = sorted_lines[i]
        h1, v1 = sorted_lines[i + 1]
        if h0 <= dip_height_mm <= h1:
            # Linear interpolation
            fraction = (dip_height_mm - h0) / (h1 - h0)
            return v0 + fraction * (v1 - v0)

    # Should never reach here
    raise CalibrationInterpolationError(
        f"Could not bracket dip height {dip_height_mm:.1f} mm in chart."
    )
