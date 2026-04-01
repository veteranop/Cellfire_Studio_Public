#!/usr/bin/env python3
"""Generate realistic antenna pattern XML files and catalog.json for Cellfire RF Studio."""

import json
import math
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ─── Pattern generation helpers ───────────────────────────────────────────────

def _clamp(v, lo, hi):
    return max(lo, min(hi, v))

def _pseudo_random(seed):
    """Simple deterministic pseudo-random for tiny variations."""
    x = math.sin(seed * 12.9898 + seed * 78.233) * 43758.5453
    return x - math.floor(x)  # 0..1

def _variation(angle, scale=0.3):
    return ((_pseudo_random(angle * 7.3 + 0.5) - 0.5) * 2) * scale


def omni_azimuth(angle, variation_db=0.3):
    """Omni antenna: near-constant gain in azimuth."""
    return round(_variation(angle, variation_db), 1)


def omni_elevation(angle, gain_dbi):
    """
    Omni elevation pattern. Higher gain = narrower elevation beam.
    angle: -90..90 degrees, 0 = horizon.
    """
    a = abs(angle)
    if gain_dbi <= 3:
        # Wide beam: -3dB at ±30°
        if a <= 30:
            g = -(a / 30.0) ** 2 * 3.0
        elif a <= 60:
            g = -3.0 - ((a - 30) / 30.0) ** 1.5 * 7.0
        elif a <= 90:
            g = -10.0 - ((a - 60) / 30.0) ** 1.2 * 15.0
        else:
            g = -25.0
    elif gain_dbi <= 5:
        if a <= 20:
            g = -(a / 20.0) ** 2 * 3.0
        elif a <= 40:
            g = -3.0 - ((a - 20) / 20.0) ** 1.5 * 7.0
        elif a <= 65:
            g = -10.0 - ((a - 40) / 25.0) ** 1.3 * 10.0
        else:
            g = -20.0 - ((a - 65) / 25.0) * 5.0
    elif gain_dbi <= 7:
        # -3dB at ±15°
        if a <= 15:
            g = -(a / 15.0) ** 2 * 3.0
        elif a <= 30:
            g = -3.0 - ((a - 15) / 15.0) ** 1.5 * 7.0
        elif a <= 50:
            g = -10.0 - ((a - 30) / 20.0) ** 1.5 * 10.0
        elif a <= 70:
            g = -20.0 - ((a - 50) / 20.0) * 5.0
        else:
            g = -25.0
    elif gain_dbi <= 10:
        # -3dB at ±10°
        if a <= 10:
            g = -(a / 10.0) ** 2 * 3.0
        elif a <= 20:
            g = -3.0 - ((a - 10) / 10.0) ** 1.5 * 7.0
        elif a <= 35:
            # first null region then sidelobe
            null_depth = -18.0
            t = (a - 20) / 15.0
            if t < 0.4:
                g = -10.0 - t / 0.4 * 8.0
            elif t < 0.6:
                g = null_depth
            else:
                g = null_depth + (1 - t) / 0.4 * 3.0  # sidelobe
        elif a <= 55:
            g = -15.0 - ((a - 35) / 20.0) * 5.0
        else:
            g = -20.0 - ((a - 55) / 35.0) * 8.0
    else:
        # Very high gain omni (>=10dBi): very narrow
        half_bw = max(3, 50.0 / gain_dbi)
        if a <= half_bw:
            g = -(a / half_bw) ** 2 * 3.0
        elif a <= half_bw * 2:
            g = -3.0 - ((a - half_bw) / half_bw) ** 1.5 * 10.0
        elif a <= half_bw * 3.5:
            t = (a - half_bw * 2) / (half_bw * 1.5)
            g = -13.0 - t * 5.0 + math.sin(t * math.pi) * 3.0  # sidelobe bump
        else:
            g = -20.0 - ((a - half_bw * 3.5) / (90 - half_bw * 3.5 + 0.01)) * 10.0

    g += _variation(angle, 0.3)
    return round(_clamp(g, -35.0, 0.5), 1)


def directional_azimuth(angle, beamwidth_h, front_to_back_db=25.0):
    """Yagi / directional azimuth. Main lobe at 0°, BW = beamwidth_h."""
    a = angle if angle <= 180 else angle - 360  # -180..180
    aa = abs(a)
    half_bw = beamwidth_h / 2.0

    if aa <= half_bw:
        g = -(aa / half_bw) ** 2 * 3.0
    elif aa <= half_bw * 2:
        t = (aa - half_bw) / half_bw
        g = -3.0 - t ** 1.5 * 7.0
    elif aa <= 90:
        t = (aa - half_bw * 2) / (90 - half_bw * 2 + 0.01)
        g = -10.0 - t * 8.0
        # sidelobe
        if 0.3 < t < 0.6:
            g += 3.0 * math.sin((t - 0.3) / 0.3 * math.pi)
    elif aa <= 150:
        g = -18.0 - ((aa - 90) / 60.0) * (front_to_back_db - 18.0)
    else:
        # back lobe region
        back_angle = aa - 150
        g = -front_to_back_db + math.sin(back_angle / 30.0 * math.pi) * 2.0

    g += _variation(angle, 0.3)
    return round(_clamp(g, -35.0, 0.5), 1)


def directional_elevation(angle, beamwidth_v, gain_dbi):
    """Yagi / directional elevation."""
    a = abs(angle)
    half_bw = beamwidth_v / 2.0

    if a <= half_bw:
        g = -(a / half_bw) ** 2 * 3.0
    elif a <= half_bw * 2.5:
        t = (a - half_bw) / (half_bw * 1.5)
        g = -3.0 - t ** 1.5 * 12.0
    else:
        g = -15.0 - ((a - half_bw * 2.5) / (90 - half_bw * 2.5 + 0.01)) * 15.0

    g += _variation(angle + 1000, 0.3)
    return round(_clamp(g, -35.0, 0.5), 1)


def panel_azimuth(angle, beamwidth_h, front_to_back_db=28.0):
    """Panel/sector antenna azimuth. Sharp rolloff past beamwidth."""
    a = angle if angle <= 180 else angle - 360
    aa = abs(a)
    half_bw = beamwidth_h / 2.0

    if aa <= half_bw:
        g = -(aa / half_bw) ** 2 * 3.0
    elif aa <= half_bw + 15:
        t = (aa - half_bw) / 15.0
        g = -3.0 - t ** 1.2 * 12.0
    elif aa <= 90:
        t = (aa - half_bw - 15) / (90 - half_bw - 15 + 0.01)
        g = -15.0 - t * 10.0
        # small sidelobe
        if 0.2 < t < 0.5:
            g += 2.0 * math.sin((t - 0.2) / 0.3 * math.pi)
    elif aa <= 150:
        g = -25.0 - ((aa - 90) / 60.0) * 3.0
    else:
        g = -front_to_back_db + math.sin((aa - 150) / 30.0 * math.pi) * 1.5

    g += _variation(angle, 0.2)
    return round(_clamp(g, -35.0, 0.5), 1)


def panel_elevation(angle, beamwidth_v):
    """Panel/sector antenna elevation."""
    a = abs(angle)
    half_bw = beamwidth_v / 2.0

    if a <= half_bw:
        g = -(a / half_bw) ** 2 * 3.0
    elif a <= half_bw * 2:
        t = (a - half_bw) / half_bw
        g = -3.0 - t ** 1.5 * 10.0
    elif a <= half_bw * 3.5:
        t = (a - half_bw * 2) / (half_bw * 1.5)
        g = -13.0 - t * 7.0 + math.sin(t * math.pi) * 2.5
    else:
        g = -20.0 - ((a - half_bw * 3.5) / (90 - half_bw * 3.5 + 0.01)) * 12.0

    g += _variation(angle + 500, 0.2)
    return round(_clamp(g, -35.0, 0.5), 1)


def dish_azimuth(angle, beamwidth_h, gain_dbi):
    """Dish antenna azimuth: very narrow main beam."""
    a = angle if angle <= 180 else angle - 360
    aa = abs(a)
    half_bw = beamwidth_h / 2.0

    if aa <= half_bw:
        g = -(aa / half_bw) ** 2 * 3.0
    elif aa <= half_bw * 2:
        t = (aa - half_bw) / half_bw
        g = -3.0 - t ** 1.3 * 15.0
    elif aa <= half_bw * 4:
        t = (aa - half_bw * 2) / (half_bw * 2)
        # first sidelobe
        g = -18.0 + math.sin(t * math.pi) * 3.0 - t * 5.0
    elif aa <= 90:
        g = -25.0 - ((aa - half_bw * 4) / (90 - half_bw * 4 + 0.01)) * 5.0
    else:
        g = -30.0 - ((aa - 90) / 90.0) * 5.0

    g += _variation(angle, 0.2)
    return round(_clamp(g, -40.0, 0.5), 1)


def dish_elevation(angle, beamwidth_v, gain_dbi):
    """Dish elevation, same physics as azimuth."""
    return dish_azimuth(angle if angle >= 0 else angle + 360, beamwidth_v, gain_dbi)


def dipole_azimuth(angle):
    """Half-wave dipole / simple omni azimuth."""
    return round(_variation(angle, 0.2), 1)


def dipole_elevation(angle):
    """Classic dipole elevation: cos pattern, nulls at ±90."""
    a = abs(angle)
    if a >= 89:
        g = -25.0
    else:
        g = 10 * math.log10(max(0.003, math.cos(math.radians(a)) ** 1.3))
    g += _variation(angle, 0.15)
    return round(_clamp(g, -30.0, 0.5), 1)


def isotropic_azimuth(angle):
    return 0.0

def isotropic_elevation(angle):
    return 0.0

def ground_plane_elevation(angle):
    """Quarter-wave ground plane: peak slightly above horizon, null below."""
    if angle < -5:
        a = abs(angle)
        g = -3.0 - (a / 90.0) ** 1.2 * 20.0
    elif angle <= 30:
        t = (angle + 5) / 35.0
        g = -0.5 + math.sin(t * math.pi / 2) * 0.5
    else:
        a = angle - 30
        g = -(a / 60.0) ** 1.5 * 15.0
    g += _variation(angle, 0.15)
    return round(_clamp(g, -30.0, 0.5), 1)


def fm_directional_azimuth(angle, beamwidth_h=120):
    """FM broadcast directional (like panel or sidemount)."""
    return panel_azimuth(angle, beamwidth_h, front_to_back_db=20.0)


def fm_omni_azimuth(angle):
    return omni_azimuth(angle, variation_db=0.5)


def log_periodic_azimuth(angle, beamwidth_h=65):
    """Log-periodic (LPDA) azimuth: moderate directivity."""
    return directional_azimuth(angle, beamwidth_h, front_to_back_db=20.0)


def log_periodic_elevation(angle, beamwidth_v=55):
    return directional_elevation(angle, beamwidth_v, 6)


# ─── XML generation ──────────────────────────────────────────────────────────

def generate_xml(antenna_type, az_func, el_func, bays=1):
    """Generate full XML string."""
    lines = ['<antenna>']
    lines.append(f'    <type>{antenna_type}</type>')
    lines.append(f'    <bays>{bays}</bays>')
    lines.append('    <azimuth>')
    for a in range(0, 360, 5):
        g = az_func(a)
        lines.append(f'        <point angle="{a}" gain="{g:.1f}"/>')
    lines.append('    </azimuth>')
    lines.append('    <elevation>')
    for a in range(-90, 91, 5):
        g = el_func(a)
        lines.append(f'        <point angle="{a}" gain="{g:.1f}"/>')
    lines.append('    </elevation>')
    lines.append('</antenna>')
    return '\n'.join(lines) + '\n'


# ─── Antenna definitions ─────────────────────────────────────────────────────

VENDORS = {
    "Andrew_CommScope": {
        "vendor_name": "Andrew / CommScope",
        "antennas": [
            {
                "id": "DB408-B", "name": "DB408-B", "part_number": "DB408-B",
                "gain_dbi": 8.5, "band": "UHF", "frequency_range": "406-512 MHz",
                "type": "Directional", "polarization": "Vertical",
                "beamwidth_h": 90, "beamwidth_v": 26,
                "description": "UHF panel antenna, 90 degree sector",
                "pattern": "panel"
            },
            {
                "id": "DB420-B", "name": "DB420-B", "part_number": "DB420-B",
                "gain_dbi": 10, "band": "UHF", "frequency_range": "406-512 MHz",
                "type": "Directional", "polarization": "Vertical",
                "beamwidth_h": 60, "beamwidth_v": 22,
                "description": "UHF panel antenna, 60 degree sector",
                "pattern": "panel"
            },
            {
                "id": "DB516-C", "name": "DB516-C", "part_number": "DB516-C",
                "gain_dbi": 3, "band": "VHF", "frequency_range": "150-174 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 60,
                "description": "VHF 3dBi collinear omnidirectional",
                "pattern": "omni"
            },
            {
                "id": "DB589", "name": "DB589", "part_number": "DB589",
                "gain_dbi": 6, "band": "UHF", "frequency_range": "450-470 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 30,
                "description": "UHF 6dBi collinear omnidirectional",
                "pattern": "omni"
            },
            {
                "id": "DB404-B", "name": "DB404-B", "part_number": "DB404-B",
                "gain_dbi": 2.15, "band": "UHF", "frequency_range": "406-512 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 78,
                "description": "UHF folded dipole, 2.15dBi omnidirectional",
                "pattern": "dipole"
            },
            {
                "id": "CPA8065-3F", "name": "CPA8065-3F", "part_number": "CPA8065-3F",
                "gain_dbi": 15, "band": "800/900 MHz", "frequency_range": "806-960 MHz",
                "type": "Directional", "polarization": "Dual (+/-45)",
                "beamwidth_h": 65, "beamwidth_v": 15,
                "description": "806-960MHz panel, 15dBi, 65 degree sector",
                "pattern": "panel"
            },
            {
                "id": "HBX-6516DS-VTM", "name": "HBX-6516DS-VTM", "part_number": "HBX-6516DS-VTM",
                "gain_dbi": 16.3, "band": "700/800/900 MHz", "frequency_range": "698-960 MHz",
                "type": "Directional", "polarization": "Dual (+/-45)",
                "beamwidth_h": 65, "beamwidth_v": 12,
                "description": "698-960MHz dual-band panel, 16.3dBi, 65 degree sector",
                "pattern": "panel"
            },
            {
                "id": "TBTD-6516-A", "name": "TBTD-6516-A", "part_number": "TBTD-6516-A",
                "gain_dbi": 15.7, "band": "700/800/900 MHz", "frequency_range": "698-960 MHz",
                "type": "Directional", "polarization": "Dual (+/-45)",
                "beamwidth_h": 65, "beamwidth_v": 14,
                "description": "698-960MHz tilt panel, 15.7dBi, 65 degree sector",
                "pattern": "panel"
            },
        ]
    },
    "Sinclair_Technologies": {
        "vendor_name": "Sinclair Technologies",
        "antennas": [
            {
                "id": "SC292-HF2HNF", "name": "SC292-HF2HNF", "part_number": "SC292-HF2HNF",
                "gain_dbi": 7.15, "band": "VHF", "frequency_range": "148-174 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 25,
                "description": "VHF 5dBd (7.15dBi) omni collinear",
                "pattern": "omni"
            },
            {
                "id": "SC329-HF2HNF", "name": "SC329-HF2HNF", "part_number": "SC329-HF2HNF",
                "gain_dbi": 8.15, "band": "UHF", "frequency_range": "406-512 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 20,
                "description": "UHF 6dBd (8.15dBi) omni collinear",
                "pattern": "omni"
            },
            {
                "id": "SC46A-HF1LDF", "name": "SC46A-HF1LDF", "part_number": "SC46A-HF1LDF",
                "gain_dbi": 12.15, "band": "700/800/900 MHz", "frequency_range": "700-1000 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 10,
                "description": "700-1000MHz 12.15dBi Aurora omni",
                "pattern": "omni"
            },
            {
                "id": "SD214-SF2P3SNF", "name": "SD214-SF2P3SNF", "part_number": "SD214-SF2P3SNF",
                "gain_dbi": 7, "band": "VHF", "frequency_range": "138-174 MHz",
                "type": "Directional", "polarization": "Vertical",
                "beamwidth_h": 60, "beamwidth_v": 50,
                "description": "VHF 7dBi directional yagi",
                "pattern": "yagi"
            },
            {
                "id": "SD505-SF1P1SNF", "name": "SD505-SF1P1SNF", "part_number": "SD505-SF1P1SNF",
                "gain_dbi": 9, "band": "UHF", "frequency_range": "406-512 MHz",
                "type": "Directional", "polarization": "Vertical",
                "beamwidth_h": 50, "beamwidth_v": 42,
                "description": "UHF 9dBi directional yagi",
                "pattern": "yagi"
            },
            {
                "id": "SP930-SF1P3SNF", "name": "SP930-SF1P3SNF", "part_number": "SP930-SF1P3SNF",
                "gain_dbi": 17, "band": "800/900 MHz", "frequency_range": "880-960 MHz",
                "type": "Directional", "polarization": "Vertical",
                "beamwidth_h": 60, "beamwidth_v": 12,
                "description": "880-960MHz panel 17dBi, 60 degree sector",
                "pattern": "panel"
            },
            {
                "id": "SC381-HF2HNF", "name": "SC381-HF2HNF", "part_number": "SC381-HF2HNF",
                "gain_dbi": 8.15, "band": "800 MHz", "frequency_range": "800-870 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 20,
                "description": "800-870MHz 6dBd omni collinear",
                "pattern": "omni"
            },
            {
                "id": "ST352-HF4HNFN", "name": "ST352-HF4HNFN", "part_number": "ST352-HF4HNFN",
                "gain_dbi": 8, "band": "UHF", "frequency_range": "350-380 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 22,
                "description": "UHF 350-380MHz TETRA omni, 8dBi",
                "pattern": "omni"
            },
        ]
    },
    "PCTEL": {
        "vendor_name": "PCTEL",
        "antennas": [
            {
                "id": "MFB9153", "name": "MFB9153", "part_number": "MFB9153",
                "gain_dbi": 3, "band": "900 MHz ISM", "frequency_range": "902-928 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 60,
                "description": "902-928MHz 3dBi fiberglass omni",
                "pattern": "omni"
            },
            {
                "id": "BMLPV500", "name": "BMLPV500", "part_number": "BMLPV500",
                "gain_dbi": 10, "band": "Broadband", "frequency_range": "698-2700 MHz",
                "type": "Directional", "polarization": "Vertical",
                "beamwidth_h": 65, "beamwidth_v": 55,
                "description": "698-2700MHz broadband LPDA 10dBi directional",
                "pattern": "lpda"
            },
            {
                "id": "GPS-TMG-SP", "name": "GPS-TMG-SP", "part_number": "GPS-TMG-SP",
                "gain_dbi": 3, "band": "GPS", "frequency_range": "1227-1575 MHz",
                "type": "Omnidirectional", "polarization": "RHCP",
                "beamwidth_h": 360, "beamwidth_v": 120,
                "description": "GPS L1/L2 timing antenna, 3dBi hemisphere pattern",
                "pattern": "gps"
            },
            {
                "id": "MHB5800", "name": "MHB5800", "part_number": "MHB5800",
                "gain_dbi": 8, "band": "5 GHz", "frequency_range": "4900-5850 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 18,
                "description": "4900-5850MHz 8dBi omni",
                "pattern": "omni"
            },
            {
                "id": "MPVL450", "name": "MPVL450", "part_number": "MPVL450",
                "gain_dbi": 3, "band": "UHF", "frequency_range": "450-470 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 60,
                "description": "450-470MHz 3dBi mobile whip omni",
                "pattern": "omni"
            },
            {
                "id": "FP_Series_900", "name": "FP Series 900", "part_number": "FP-900",
                "gain_dbi": 14, "band": "900 MHz", "frequency_range": "890-960 MHz",
                "type": "Directional", "polarization": "Vertical",
                "beamwidth_h": 90, "beamwidth_v": 18,
                "description": "900MHz flat panel, 14dBi, 90 degree sector",
                "pattern": "panel"
            },
        ]
    },
    "Laird_Connectivity": {
        "vendor_name": "Laird Connectivity",
        "antennas": [
            {
                "id": "FG1503", "name": "FG1503", "part_number": "FG1503",
                "gain_dbi": 3, "band": "VHF", "frequency_range": "150-174 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 60,
                "description": "VHF 150-174MHz 3dBi fiberglass omni",
                "pattern": "omni"
            },
            {
                "id": "FG4503", "name": "FG4503", "part_number": "FG4503",
                "gain_dbi": 3, "band": "UHF", "frequency_range": "450-470 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 60,
                "description": "UHF 450-470MHz 3dBi fiberglass omni",
                "pattern": "omni"
            },
            {
                "id": "FG8963", "name": "FG8963", "part_number": "FG8963",
                "gain_dbi": 3, "band": "800/900 MHz", "frequency_range": "896-940 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 60,
                "description": "896-940MHz 3dBi fiberglass omni",
                "pattern": "omni"
            },
            {
                "id": "YS1506", "name": "YS1506", "part_number": "YS1506",
                "gain_dbi": 10.2, "band": "VHF", "frequency_range": "150-174 MHz",
                "type": "Directional", "polarization": "Vertical",
                "beamwidth_h": 48, "beamwidth_v": 42,
                "description": "VHF 150-174MHz 10.2dBi 6-element yagi",
                "pattern": "yagi"
            },
            {
                "id": "YA4506", "name": "YA4506", "part_number": "YA4506",
                "gain_dbi": 10.2, "band": "UHF", "frequency_range": "450-470 MHz",
                "type": "Directional", "polarization": "Vertical",
                "beamwidth_h": 48, "beamwidth_v": 42,
                "description": "UHF 450-470MHz 10.2dBi 6-element yagi",
                "pattern": "yagi"
            },
            {
                "id": "CL49612P", "name": "CL49612P", "part_number": "CL49612P",
                "gain_dbi": 12, "band": "4.9 GHz", "frequency_range": "4940-4990 MHz",
                "type": "Directional", "polarization": "Dual (+/-45)",
                "beamwidth_h": 60, "beamwidth_v": 20,
                "description": "4940-4990MHz 12dBi sector panel, 60 degree",
                "pattern": "panel"
            },
        ]
    },
    "Kathrein": {
        "vendor_name": "Kathrein (Ericsson)",
        "antennas": [
            {
                "id": "80010541", "name": "80010541", "part_number": "80010541",
                "gain_dbi": 17.5, "band": "700/800/900 MHz", "frequency_range": "698-960 MHz",
                "type": "Directional", "polarization": "Dual (+/-45)",
                "beamwidth_h": 65, "beamwidth_v": 11,
                "description": "698-960MHz 17.5dBi panel, 65 degree sector",
                "pattern": "panel"
            },
            {
                "id": "80010248", "name": "80010248", "part_number": "80010248",
                "gain_dbi": 18, "band": "1.7-2.7 GHz", "frequency_range": "1710-2690 MHz",
                "type": "Directional", "polarization": "Dual (+/-45)",
                "beamwidth_h": 65, "beamwidth_v": 7,
                "description": "1710-2690MHz 18dBi panel, 65 degree sector",
                "pattern": "panel"
            },
            {
                "id": "K742215", "name": "K742215", "part_number": "K742215",
                "gain_dbi": 11, "band": "TETRA 380-400 MHz", "frequency_range": "380-400 MHz",
                "type": "Directional", "polarization": "Vertical",
                "beamwidth_h": 90, "beamwidth_v": 26,
                "description": "380-400MHz TETRA 11dBi panel, 90 degree sector",
                "pattern": "panel"
            },
            {
                "id": "K751631", "name": "K751631", "part_number": "K751631",
                "gain_dbi": 8, "band": "VHF", "frequency_range": "148-174 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 20,
                "description": "VHF 148-174MHz 8dBi 4-dipole collinear omni",
                "pattern": "omni"
            },
            {
                "id": "80010669", "name": "80010669", "part_number": "80010669",
                "gain_dbi": 17.5, "band": "Dual-band", "frequency_range": "698-960/1710-2690 MHz",
                "type": "Directional", "polarization": "Dual (+/-45)",
                "beamwidth_h": 65, "beamwidth_v": 11,
                "description": "698-960/1710-2690MHz dual-band panel 17.5dBi, 65 degree",
                "pattern": "panel"
            },
            {
                "id": "K722131", "name": "K722131", "part_number": "K722131",
                "gain_dbi": 12, "band": "UHF", "frequency_range": "450-470 MHz",
                "type": "Directional", "polarization": "Vertical",
                "beamwidth_h": 90, "beamwidth_v": 22,
                "description": "UHF 450-470MHz 12dBi panel, 90 degree sector",
                "pattern": "panel"
            },
        ]
    },
    "Cambium_Networks": {
        "vendor_name": "Cambium Networks",
        "antennas": [
            {
                "id": "C050900D021A", "name": "C050900D021A", "part_number": "C050900D021A",
                "gain_dbi": 25, "band": "5 GHz", "frequency_range": "4900-5975 MHz",
                "type": "Directional", "polarization": "Dual",
                "beamwidth_h": 8, "beamwidth_v": 8,
                "description": "5GHz 25dBi dish directional",
                "pattern": "dish"
            },
            {
                "id": "N000900L006A", "name": "N000900L006A", "part_number": "N000900L006A",
                "gain_dbi": 19, "band": "5 GHz", "frequency_range": "4900-5975 MHz",
                "type": "Directional", "polarization": "Dual (+/-45)",
                "beamwidth_h": 120, "beamwidth_v": 7,
                "description": "5GHz 19dBi sector, 120 degree",
                "pattern": "panel"
            },
            {
                "id": "C054045C002A", "name": "C054045C002A", "part_number": "C054045C002A",
                "gain_dbi": 17, "band": "5 GHz", "frequency_range": "4900-5975 MHz",
                "type": "Directional", "polarization": "Dual (+/-45)",
                "beamwidth_h": 90, "beamwidth_v": 8,
                "description": "5GHz 17dBi sector, 90 degree",
                "pattern": "panel"
            },
            {
                "id": "N000000L034A", "name": "N000000L034A", "part_number": "N000000L034A",
                "gain_dbi": 18, "band": "3 GHz", "frequency_range": "3300-3800 MHz",
                "type": "Directional", "polarization": "Dual (+/-45)",
                "beamwidth_h": 90, "beamwidth_v": 8,
                "description": "3GHz 18dBi sector, 90 degree",
                "pattern": "panel"
            },
        ]
    },
    "Ubiquiti": {
        "vendor_name": "Ubiquiti Inc.",
        "antennas": [
            {
                "id": "AM-5G17-90", "name": "AM-5G17-90", "part_number": "AM-5G17-90",
                "gain_dbi": 17, "band": "5 GHz", "frequency_range": "4900-5850 MHz",
                "type": "Directional", "polarization": "Dual",
                "beamwidth_h": 90, "beamwidth_v": 8,
                "description": "5GHz 17dBi sector, 90 degree",
                "pattern": "panel"
            },
            {
                "id": "AM-5G19-120", "name": "AM-5G19-120", "part_number": "AM-5G19-120",
                "gain_dbi": 19, "band": "5 GHz", "frequency_range": "4900-5850 MHz",
                "type": "Directional", "polarization": "Dual",
                "beamwidth_h": 120, "beamwidth_v": 6,
                "description": "5GHz 19dBi sector, 120 degree",
                "pattern": "panel"
            },
            {
                "id": "RD-5G30", "name": "RD-5G30", "part_number": "RD-5G30",
                "gain_dbi": 30, "band": "5 GHz", "frequency_range": "4900-5850 MHz",
                "type": "Directional", "polarization": "Dual",
                "beamwidth_h": 5, "beamwidth_v": 5,
                "description": "5GHz 30dBi dish",
                "pattern": "dish"
            },
            {
                "id": "LBE-5AC-Gen2", "name": "LBE-5AC-Gen2", "part_number": "LBE-5AC-Gen2",
                "gain_dbi": 23, "band": "5 GHz", "frequency_range": "5150-5875 MHz",
                "type": "Directional", "polarization": "Dual",
                "beamwidth_h": 10, "beamwidth_v": 10,
                "description": "5GHz 23dBi dish integrated",
                "pattern": "dish"
            },
        ]
    },
    "dbSpectra": {
        "vendor_name": "dbSpectra (Wireless Telecom Group)",
        "antennas": [
            {
                "id": "DS7A12P90U-N", "name": "DS7A12P90U-N", "part_number": "DS7A12P90U-N",
                "gain_dbi": 12, "band": "UHF", "frequency_range": "406-512 MHz",
                "type": "Directional", "polarization": "Vertical",
                "beamwidth_h": 90, "beamwidth_v": 22,
                "description": "UHF 406-512MHz 12dBi panel, 90 degree",
                "pattern": "panel"
            },
            {
                "id": "DS7C08PPYU", "name": "DS7C08PPYU", "part_number": "DS7C08PPYU",
                "gain_dbi": 8, "band": "700/800 MHz", "frequency_range": "764-869 MHz",
                "type": "Directional", "polarization": "Vertical",
                "beamwidth_h": 75, "beamwidth_v": 30,
                "description": "764-869MHz 8dBi panel, offset directional",
                "pattern": "panel"
            },
            {
                "id": "DS3A06P90U", "name": "DS3A06P90U", "part_number": "DS3A06P90U",
                "gain_dbi": 6, "band": "VHF", "frequency_range": "138-174 MHz",
                "type": "Directional", "polarization": "Vertical",
                "beamwidth_h": 90, "beamwidth_v": 40,
                "description": "VHF 138-174MHz 6dBi panel, 90 degree",
                "pattern": "panel"
            },
            {
                "id": "DS7A15P65U", "name": "DS7A15P65U", "part_number": "DS7A15P65U",
                "gain_dbi": 15, "band": "UHF", "frequency_range": "406-512 MHz",
                "type": "Directional", "polarization": "Vertical",
                "beamwidth_h": 65, "beamwidth_v": 15,
                "description": "UHF 406-512MHz 15dBi panel, 65 degree",
                "pattern": "panel"
            },
        ]
    },
    "Antenna_Specialists": {
        "vendor_name": "Antenna Specialists (PCTEL)",
        "antennas": [
            {
                "id": "ASP930T", "name": "ASP930T", "part_number": "ASP930T",
                "gain_dbi": 6, "band": "800/900 MHz", "frequency_range": "896-940 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 30,
                "description": "896-940MHz omni 6dBi collinear",
                "pattern": "omni"
            },
            {
                "id": "ASP558T", "name": "ASP558T", "part_number": "ASP558T",
                "gain_dbi": 6, "band": "UHF", "frequency_range": "450-470 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 30,
                "description": "UHF 450-470MHz omni 6dBi collinear",
                "pattern": "omni"
            },
            {
                "id": "ASPD7295T", "name": "ASPD7295T", "part_number": "ASPD7295T",
                "gain_dbi": 10, "band": "UHF", "frequency_range": "406-512 MHz",
                "type": "Directional", "polarization": "Vertical",
                "beamwidth_h": 50, "beamwidth_v": 45,
                "description": "UHF 406-512MHz yagi 10dBi directional",
                "pattern": "yagi"
            },
            {
                "id": "ASP572", "name": "ASP572", "part_number": "ASP572",
                "gain_dbi": 3, "band": "VHF", "frequency_range": "150-174 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 60,
                "description": "VHF 150-174MHz omni 3dBi collinear",
                "pattern": "omni"
            },
        ]
    },
    "Comtelco": {
        "vendor_name": "Comtelco",
        "antennas": [
            {
                "id": "BS450HRO", "name": "BS450HRO", "part_number": "BS450HRO",
                "gain_dbi": 6, "band": "UHF", "frequency_range": "450-470 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 30,
                "description": "UHF 450-470MHz omni 6dBi heavy duty collinear",
                "pattern": "omni"
            },
            {
                "id": "BS150-3", "name": "BS150-3", "part_number": "BS150-3",
                "gain_dbi": 3, "band": "VHF", "frequency_range": "150-174 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 60,
                "description": "VHF 150-174MHz omni 3dBi collinear",
                "pattern": "omni"
            },
            {
                "id": "BSYGI1506", "name": "BSYGI1506", "part_number": "BSYGI1506",
                "gain_dbi": 10, "band": "VHF", "frequency_range": "150-174 MHz",
                "type": "Directional", "polarization": "Vertical",
                "beamwidth_h": 48, "beamwidth_v": 42,
                "description": "VHF 150-174MHz yagi 10dBi 6-element",
                "pattern": "yagi"
            },
            {
                "id": "BS900-5", "name": "BS900-5", "part_number": "BS900-5",
                "gain_dbi": 5, "band": "800/900 MHz", "frequency_range": "896-940 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 35,
                "description": "896-940MHz omni 5dBi collinear",
                "pattern": "omni"
            },
        ]
    },
    "Telewave": {
        "vendor_name": "Telewave Inc.",
        "antennas": [
            {
                "id": "ANT450D6", "name": "ANT450D6", "part_number": "ANT450D6",
                "gain_dbi": 6, "band": "UHF", "frequency_range": "450-470 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 30,
                "description": "UHF 450-470MHz omni 6dBi collinear",
                "pattern": "omni"
            },
            {
                "id": "ANT150D3", "name": "ANT150D3", "part_number": "ANT150D3",
                "gain_dbi": 3, "band": "VHF", "frequency_range": "148-174 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 60,
                "description": "VHF 148-174MHz omni 3dBi collinear",
                "pattern": "omni"
            },
            {
                "id": "ANT150Y6", "name": "ANT150Y6", "part_number": "ANT150Y6",
                "gain_dbi": 10.2, "band": "VHF", "frequency_range": "148-174 MHz",
                "type": "Directional", "polarization": "Vertical",
                "beamwidth_h": 48, "beamwidth_v": 42,
                "description": "VHF 148-174MHz yagi 10.2dBi 6-element",
                "pattern": "yagi"
            },
            {
                "id": "ANT800F6", "name": "ANT800F6", "part_number": "ANT800F6",
                "gain_dbi": 6, "band": "800 MHz", "frequency_range": "806-896 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 30,
                "description": "806-896MHz omni 6dBi collinear",
                "pattern": "omni"
            },
        ]
    },
    "Diamond_Antenna": {
        "vendor_name": "Diamond Antenna",
        "antennas": [
            {
                "id": "X510HDN", "name": "X510HDN", "part_number": "X510HDN",
                "gain_dbi": 11.7, "band": "VHF/UHF Dual-band", "frequency_range": "144-148/430-440 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 12,
                "description": "VHF/UHF dual-band omni 8.3/11.7dBi collinear",
                "pattern": "omni"
            },
            {
                "id": "A430S10R2", "name": "A430S10R2", "part_number": "A430S10R2",
                "gain_dbi": 14.3, "band": "UHF", "frequency_range": "430-440 MHz",
                "type": "Directional", "polarization": "Horizontal",
                "beamwidth_h": 32, "beamwidth_v": 36,
                "description": "UHF 430-440MHz 10-element yagi 14.3dBi",
                "pattern": "yagi"
            },
            {
                "id": "A144S10R2", "name": "A144S10R2", "part_number": "A144S10R2",
                "gain_dbi": 13.2, "band": "VHF", "frequency_range": "144-148 MHz",
                "type": "Directional", "polarization": "Horizontal",
                "beamwidth_h": 34, "beamwidth_v": 38,
                "description": "VHF 144-148MHz 10-element yagi 13.2dBi",
                "pattern": "yagi"
            },
            {
                "id": "X200A", "name": "X200A", "part_number": "X200A",
                "gain_dbi": 8.0, "band": "VHF/UHF Dual-band", "frequency_range": "144-148/430-440 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 20,
                "description": "VHF/UHF dual-band omni 6.0/8.0dBi",
                "pattern": "omni"
            },
        ]
    },
    "Hustler": {
        "vendor_name": "Hustler (Laird)",
        "antennas": [
            {
                "id": "G7-150", "name": "G7-150", "part_number": "G7-150",
                "gain_dbi": 7, "band": "VHF", "frequency_range": "148-174 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 25,
                "description": "VHF 148-174MHz 7dBi collinear omni",
                "pattern": "omni"
            },
            {
                "id": "G6-450", "name": "G6-450", "part_number": "G6-450",
                "gain_dbi": 6, "band": "UHF", "frequency_range": "450-470 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 30,
                "description": "UHF 450-470MHz 6dBi collinear omni",
                "pattern": "omni"
            },
            {
                "id": "G7-800", "name": "G7-800", "part_number": "G7-800",
                "gain_dbi": 7, "band": "800 MHz", "frequency_range": "806-869 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 25,
                "description": "806-869MHz 7dBi collinear omni",
                "pattern": "omni"
            },
        ]
    },
    "Larsen": {
        "vendor_name": "Larsen (PCTEL)",
        "antennas": [
            {
                "id": "BSAOL150", "name": "BSAOL150", "part_number": "BSAOL150",
                "gain_dbi": 3, "band": "VHF", "frequency_range": "150-174 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 60,
                "description": "VHF 150-174MHz 3dBi omni collinear",
                "pattern": "omni"
            },
            {
                "id": "BSAOL450", "name": "BSAOL450", "part_number": "BSAOL450",
                "gain_dbi": 3, "band": "UHF", "frequency_range": "450-470 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 60,
                "description": "UHF 450-470MHz 3dBi omni collinear",
                "pattern": "omni"
            },
            {
                "id": "BSYAGI6E", "name": "BSYAGI6E", "part_number": "BSYAGI6E",
                "gain_dbi": 10.2, "band": "VHF", "frequency_range": "150-174 MHz",
                "type": "Directional", "polarization": "Vertical",
                "beamwidth_h": 48, "beamwidth_v": 42,
                "description": "VHF 150-174MHz 10.2dBi 6-element yagi",
                "pattern": "yagi"
            },
        ]
    },
    "Shakespeare": {
        "vendor_name": "Shakespeare Marine",
        "antennas": [
            {
                "id": "Style_4431", "name": "Style 4431", "part_number": "4431",
                "gain_dbi": 3, "band": "Marine VHF", "frequency_range": "156-163 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 60,
                "description": "Marine VHF 156-163MHz 3dBi omni",
                "pattern": "omni"
            },
            {
                "id": "Style_5225_XT", "name": "Style 5225-XT", "part_number": "5225-XT",
                "gain_dbi": 8, "band": "Marine VHF", "frequency_range": "156-163 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 20,
                "description": "Marine VHF 156-163MHz 8dBi high-gain omni",
                "pattern": "omni"
            },
            {
                "id": "Galaxy_5018", "name": "Galaxy 5018", "part_number": "5018",
                "gain_dbi": 17, "band": "Marine VHF", "frequency_range": "156-163 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 5,
                "description": "Marine VHF 156-163MHz 17dBi high-gain omni",
                "pattern": "omni"
            },
        ]
    },
    "Tram_Browning": {
        "vendor_name": "Tram / Browning",
        "antennas": [
            {
                "id": "Model_1480", "name": "Model 1480", "part_number": "1480",
                "gain_dbi": 6.7, "band": "VHF", "frequency_range": "144-148 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 28,
                "description": "VHF 144-148MHz 6.7dBi collinear omni",
                "pattern": "omni"
            },
            {
                "id": "Model_1486", "name": "Model 1486", "part_number": "1486",
                "gain_dbi": 9.5, "band": "UHF", "frequency_range": "440-450 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 15,
                "description": "UHF 440-450MHz 9.5dBi collinear omni",
                "pattern": "omni"
            },
            {
                "id": "Model_6051", "name": "Model 6051", "part_number": "6051",
                "gain_dbi": 2, "band": "VHF", "frequency_range": "146-167 MHz",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 78,
                "description": "VHF 146-167MHz 2dBi fiberglass omni",
                "pattern": "dipole"
            },
        ]
    },
    "Jampro": {
        "vendor_name": "Jampro Antennas",
        "antennas": [
            {
                "id": "JLCP", "name": "JLCP", "part_number": "JLCP",
                "gain_dbi": 5, "band": "FM Broadcast", "frequency_range": "88-108 MHz",
                "type": "Directional", "polarization": "Circular",
                "beamwidth_h": 120, "beamwidth_v": 50,
                "description": "FM 88-108MHz circular polarized sidemount directional",
                "pattern": "fm_dir"
            },
            {
                "id": "JMPC_CP", "name": "JMPC-CP", "part_number": "JMPC-CP",
                "gain_dbi": 8, "band": "FM Broadcast", "frequency_range": "88-108 MHz",
                "type": "Directional", "polarization": "Circular",
                "beamwidth_h": 90, "beamwidth_v": 35,
                "description": "FM 88-108MHz multi-station CP panel",
                "pattern": "panel"
            },
            {
                "id": "JAHD", "name": "JAHD", "part_number": "JAHD",
                "gain_dbi": 4, "band": "FM Broadcast", "frequency_range": "88-108 MHz",
                "type": "Omnidirectional", "polarization": "Circular",
                "beamwidth_h": 360, "beamwidth_v": 45,
                "description": "FM 88-108MHz high-power dipole omni",
                "pattern": "omni"
            },
        ]
    },
    "Shively_Labs": {
        "vendor_name": "Shively Labs",
        "antennas": [
            {
                "id": "Model_6014", "name": "Model 6014", "part_number": "6014",
                "gain_dbi": 6.5, "band": "FM Broadcast", "frequency_range": "88-108 MHz",
                "type": "Directional", "polarization": "Circular",
                "beamwidth_h": 100, "beamwidth_v": 40,
                "description": "FM 88-108MHz CP panel directional",
                "pattern": "panel"
            },
            {
                "id": "Model_6810", "name": "Model 6810", "part_number": "6810",
                "gain_dbi": 3.5, "band": "FM Broadcast", "frequency_range": "88-108 MHz",
                "type": "Omnidirectional", "polarization": "Circular",
                "beamwidth_h": 360, "beamwidth_v": 50,
                "description": "FM 88-108MHz broadband CP slot omni",
                "pattern": "omni"
            },
            {
                "id": "Model_6832", "name": "Model 6832", "part_number": "6832",
                "gain_dbi": 7, "band": "FM Broadcast", "frequency_range": "88-108 MHz",
                "type": "Directional", "polarization": "Circular",
                "beamwidth_h": 90, "beamwidth_v": 35,
                "description": "FM 88-108MHz high-power CP panel",
                "pattern": "panel"
            },
        ]
    },
    "ETS_Lindgren": {
        "vendor_name": "ETS-Lindgren",
        "antennas": [
            {
                "id": "Model_3164_06", "name": "Model 3164-06", "part_number": "3164-06",
                "gain_dbi": 6, "band": "Broadband", "frequency_range": "1-18 GHz",
                "type": "Directional", "polarization": "Linear",
                "beamwidth_h": 65, "beamwidth_v": 55,
                "description": "1-18GHz log-periodic broadband 6dBi",
                "pattern": "lpda"
            },
            {
                "id": "Model_3115", "name": "Model 3115", "part_number": "3115",
                "gain_dbi": 12, "band": "Broadband", "frequency_range": "750 MHz-18 GHz",
                "type": "Directional", "polarization": "Linear",
                "beamwidth_h": 40, "beamwidth_v": 35,
                "description": "750MHz-18GHz double-ridge horn 12dBi",
                "pattern": "yagi"
            },
            {
                "id": "Model_3106B", "name": "Model 3106B", "part_number": "3106B",
                "gain_dbi": 5, "band": "Broadband", "frequency_range": "200 MHz-2 GHz",
                "type": "Directional", "polarization": "Linear",
                "beamwidth_h": 70, "beamwidth_v": 60,
                "description": "200MHz-2GHz log-periodic 5dBi",
                "pattern": "lpda"
            },
        ]
    },
    "Generic": {
        "vendor_name": "Generic / Reference",
        "antennas": [
            {
                "id": "Ideal_Isotropic", "name": "Ideal Isotropic", "part_number": "ISOTROPIC",
                "gain_dbi": 0, "band": "All", "frequency_range": "All frequencies",
                "type": "Omnidirectional", "polarization": "N/A",
                "beamwidth_h": 360, "beamwidth_v": 360,
                "description": "0dBi perfect isotropic radiator (reference)",
                "pattern": "isotropic"
            },
            {
                "id": "Half_Wave_Dipole", "name": "Half-Wave Dipole", "part_number": "DIPOLE",
                "gain_dbi": 2.15, "band": "All", "frequency_range": "All frequencies",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 78,
                "description": "2.15dBi standard half-wave dipole pattern",
                "pattern": "dipole"
            },
            {
                "id": "Quarter_Wave_Ground_Plane", "name": "Quarter-Wave Ground Plane", "part_number": "GROUND-PLANE",
                "gain_dbi": 2, "band": "All", "frequency_range": "All frequencies",
                "type": "Omnidirectional", "polarization": "Vertical",
                "beamwidth_h": 360, "beamwidth_v": 80,
                "description": "2dBi standard quarter-wave ground plane vertical",
                "pattern": "ground_plane"
            },
            {
                "id": "Generic_Sector_90", "name": "Generic 90-degree Sector", "part_number": "SECTOR-90",
                "gain_dbi": 12, "band": "All", "frequency_range": "All frequencies",
                "type": "Directional", "polarization": "Vertical",
                "beamwidth_h": 90, "beamwidth_v": 22,
                "description": "Generic 12dBi 90 degree sector panel",
                "pattern": "panel"
            },
        ]
    },
}


def get_pattern_funcs(ant):
    """Return (az_func, el_func, ant_type, bays) based on pattern type."""
    pat = ant["pattern"]
    bw_h = ant.get("beamwidth_h", 90)
    bw_v = ant.get("beamwidth_v", 30)
    gain = ant["gain_dbi"]

    if pat == "omni":
        return (
            lambda a: omni_azimuth(a),
            lambda a: omni_elevation(a, gain),
            "Omnidirectional", 1
        )
    elif pat == "dipole":
        return (
            lambda a: dipole_azimuth(a),
            lambda a: dipole_elevation(a),
            "Omnidirectional", 1
        )
    elif pat == "isotropic":
        return (
            lambda a: isotropic_azimuth(a),
            lambda a: isotropic_elevation(a),
            "Omnidirectional", 1
        )
    elif pat == "ground_plane":
        return (
            lambda a: omni_azimuth(a, 0.15),
            lambda a: ground_plane_elevation(a),
            "Omnidirectional", 1
        )
    elif pat == "yagi":
        return (
            lambda a, bw=bw_h: directional_azimuth(a, bw, 25.0),
            lambda a, bw=bw_v, g=gain: directional_elevation(a, bw, g),
            "Directional", 1
        )
    elif pat == "panel":
        return (
            lambda a, bw=bw_h: panel_azimuth(a, bw, 28.0),
            lambda a, bw=bw_v: panel_elevation(a, bw),
            "Directional", 1
        )
    elif pat == "dish":
        return (
            lambda a, bw=bw_h, g=gain: dish_azimuth(a, bw, g),
            lambda a, bw=bw_v, g=gain: dish_elevation(a, bw, g),
            "Directional", 1
        )
    elif pat == "lpda":
        return (
            lambda a, bw=bw_h: log_periodic_azimuth(a, bw),
            lambda a, bw=bw_v: log_periodic_elevation(a, bw),
            "Directional", 1
        )
    elif pat == "fm_dir":
        return (
            lambda a, bw=bw_h: fm_directional_azimuth(a, bw),
            lambda a, bw=bw_v: panel_elevation(a, bw),
            "Directional", 1
        )
    elif pat == "gps":
        # GPS: hemispherical, good above horizon, drops off below
        return (
            lambda a: omni_azimuth(a, 0.3),
            lambda a: ground_plane_elevation(a),
            "Omnidirectional", 1
        )
    else:
        raise ValueError(f"Unknown pattern type: {pat}")


def main():
    total_antennas = 0
    vendor_index = []

    for vendor_dir, vendor_data in VENDORS.items():
        vname = vendor_data["vendor_name"]
        ants = vendor_data["antennas"]
        vpath = os.path.join(BASE_DIR, vendor_dir)
        os.makedirs(vpath, exist_ok=True)

        catalog_antennas = []
        for ant in ants:
            az_func, el_func, ant_type, bays = get_pattern_funcs(ant)
            xml_content = generate_xml(ant_type, az_func, el_func, bays)
            xml_filename = f"{ant['id']}.xml"
            xml_path = os.path.join(vpath, xml_filename)
            with open(xml_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            print(f"  Wrote {xml_path}")

            catalog_antennas.append({
                "id": ant["id"],
                "name": ant["name"],
                "manufacturer": vname,
                "part_number": ant["part_number"],
                "gain_dbi": ant["gain_dbi"],
                "band": ant["band"],
                "frequency_range": ant["frequency_range"],
                "type": ant["type"],
                "polarization": ant["polarization"],
                "beamwidth_h": ant["beamwidth_h"],
                "beamwidth_v": ant["beamwidth_v"],
                "xml_file": xml_filename,
                "description": ant["description"]
            })

        catalog = {
            "vendor": vname,
            "antennas": catalog_antennas
        }
        catalog_path = os.path.join(vpath, "catalog.json")
        with open(catalog_path, 'w', encoding='utf-8') as f:
            json.dump(catalog, f, indent=2)
        print(f"  Wrote {catalog_path}")

        vendor_index.append({
            "id": vendor_dir,
            "name": vname,
            "antenna_count": len(ants),
            "catalog_url": f"antennas/{vendor_dir}/catalog.json"
        })
        total_antennas += len(ants)

    # Master index
    master_index = {
        "version": "1.0",
        "description": "Cellfire RF Studio Public Antenna Library",
        "last_updated": "2026-04-01",
        "vendors": vendor_index,
        "total_antennas": total_antennas
    }
    index_path = os.path.join(BASE_DIR, "catalog_index.json")
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(master_index, f, indent=2)
    print(f"\nWrote master index: {index_path}")
    print(f"Total antennas: {total_antennas}")
    print(f"Total vendors: {len(VENDORS)}")


if __name__ == "__main__":
    main()
