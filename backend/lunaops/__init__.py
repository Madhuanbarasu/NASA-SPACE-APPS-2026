"""LUNA-OPS: Lunar Landing Site Navigator science engine and API.

All scientific quantities are computed in this package (blueprint C09).
The API serves them unchanged; the browser only visualizes them.
"""

__version__ = "0.1.0"
ALGORITHM_VERSION = "1.5.0"  # 1.5.0 (Phase 4): Earth's spin axis is the pole of date (CIP: IAU 2006 precession + IAU 2000B nutation) instead of the frozen J2000 pole, which moves Earth limb (upper/lower edge) values and events slightly; 1.4.0 (Phase 3): IERS 2010 oblate Earth limb, exact Sun-Earth joint visibility, limb-darkened power series, sub-bin peak excess, power metrics integrate known intervals only, unknown error-map variance never borrowed; 1.3.0: exact-geometry horizon sigma (site-product variance regularized at L_corr) with product identity per bin, cross-product discrepancy allowance, near-field and uncertainty flags (horizon values unchanged); 1.2.0: exact spherical-cap disks, error maps tied to their DEM, terrain refusals; 1.1.1: exact ray stopping, spherical disks, eclipse-centre events
