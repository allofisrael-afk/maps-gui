"""MPM — Modified Point Mass (4-DOF) trajectory model, per the STANAG 4355 structure.

Modules:
    projectile   – physical data and aerodynamic coefficient tables
    atmosphere   – atmospheric profile (standard or met by layers)
    met_sources  – live forecast (Open-Meteo), geocoding, met CSV
    geodesy      – distance and azimuth between coordinates (Vincenty, WGS84)
    engine       – equations of motion and RK4 integration
    fire_control – firing solution, firing table, fitting-factor calibration
    bridge       – JSON request/response interface for other projects
"""
__version__ = "1.0.0"
