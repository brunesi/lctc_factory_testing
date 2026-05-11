"""
dsp/protocol.py

Parser textual do frame DSP 04 64 capturado a partir do journal do
chargepoint.service.

A entrada esperada é uma linha já filtrada por:

    journalctl -u chargepoint.service --since "30 seconds ago" -o cat -f | grep "04 64"

Exemplo:

    04 64 11 00 001778496436 000 000   0.0 000 00000000 000 00000   0 20 12 07 11 12 000 0000  0 001 0000  00000  0000       80     2038      -56 2026-05-11T07:47:17.325 00 00 00 00 00 0

Ordem dos campos:

    fn sz st cc posix V I Im e% et Vb En Fan T1 T2 T3 T4 T5 PB 4321 em Iil Rno F54321 D4321 Ax Ay Az timestamp M1 M2 M3 M4 M5 ETA
"""

import logging
import re
from datetime import datetime

log = logging.getLogger(__name__)

FUNCTION_MEGAPAYLOAD = 0x04
FRAME_FUNCTION_TOKEN = "04"
FRAME_SIZE_TOKEN = "64"
FRAME_TOKEN_COUNT = 35

# Remove sequências ANSI/VT100 como \x1b[93m e \x1b[0m que podem vir do
# journal quando a aplicação original colore a linha antes de registrar.
ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_ansi(text: str) -> str:
    """Remove códigos ANSI/VT100 de cor/formatação."""
    return ANSI_ESCAPE_RE.sub("", text)


def _as_int(token: str, field: str) -> int:
    try:
        return int(token)
    except ValueError as exc:
        raise ValueError(f"campo {field} inválido para int: {token!r}") from exc


def _as_float(token: str, field: str) -> float:
    try:
        return float(token)
    except ValueError as exc:
        raise ValueError(f"campo {field} inválido para float: {token!r}") from exc


def _as_hex_int(token: str, field: str) -> int:
    try:
        return int(token, 16)
    except ValueError as exc:
        raise ValueError(f"campo {field} inválido para hex: {token!r}") from exc


def _validate_bit_string(token: str, width: int, field: str) -> str:
    if len(token) != width or any(ch not in "01" for ch in token):
        raise ValueError(
            f"campo {field} inválido: esperado string binária com {width} bits, recebido {token!r}"
        )
    return token


def _validate_timestamp(token: str) -> str:
    """
    Valida o timestamp ISO do DSP quando possível, mas mantém o valor
    textual original no retorno para evitar perda de precisão/formato.
    """
    try:
        datetime.fromisoformat(token)
    except ValueError:
        log.debug(f"timestamp DSP fora do formato ISO esperado: {token!r}")
    return token


def parse_journal_frame(line: str) -> dict | None:
    """
    Decodifica uma linha textual do frame DSP 04 64.

    Retorna um dicionário compatível com os nomes consumidos por DspReader
    e DspState, ou None quando a linha não é um frame válido.
    """
    original_line = line.rstrip("\n")
    raw_line = strip_ansi(original_line).strip()
    if not raw_line:
        return None

    tokens = raw_line.split()

    if len(tokens) < FRAME_TOKEN_COUNT:
        log.warning(
            f"Frame 04 64 incompleto: recebido {len(tokens)} tokens, "
            f"esperado pelo menos {FRAME_TOKEN_COUNT}. Linha limpa: {raw_line!r}; "
            f"linha original: {original_line!r}"
        )
        return None

    if tokens[0] != FRAME_FUNCTION_TOKEN or tokens[1] != FRAME_SIZE_TOKEN:
        log.debug(
            f"Linha ignorada: tokens iniciais inválidos após limpeza ANSI: "
            f"{tokens[:2]!r}; linha original: {original_line!r}"
        )
        return None

    try:
        charge_state = _as_hex_int(tokens[2], "st")
        connector = _as_int(tokens[3], "cc")
        posix = _as_int(tokens[4], "posix")

        voltage = _as_int(tokens[5], "V")
        current = _as_int(tokens[6], "I")
        current_requested = _as_float(tokens[7], "Im")
        charge_percent = _as_int(tokens[8], "e%")
        charge_time = _as_int(tokens[9], "et")
        battery_voltage = _as_int(tokens[10], "Vb")
        energy = _as_int(tokens[11], "En")

        fan_status = _as_int(tokens[12], "Fan")
        temperature1 = _as_int(tokens[13], "T1")
        temperature2 = _as_int(tokens[14], "T2")
        temperature3 = _as_int(tokens[15], "T3")
        temperature4 = _as_int(tokens[16], "T4")
        temperature5 = _as_int(tokens[17], "T5")

        buttons_raw = _validate_bit_string(tokens[19], 4, "4321")
        emergency = _as_int(tokens[20], "em")
        leakage_current = _as_float(tokens[21], "Iil")
        output_resistance = _as_int(tokens[22], "Rno")
        digital_raw = _validate_bit_string(tokens[24], 4, "D4321")

        ax = _as_int(tokens[25], "Ax")
        ay = _as_int(tokens[26], "Ay")
        az = _as_int(tokens[27], "Az")
        dsp_timestamp = _validate_timestamp(tokens[28])
        eta = tokens[34]

    except ValueError as exc:
        log.warning(f"Falha ao decodificar frame 04 64: {exc}. Linha limpa: {raw_line!r}")
        return None

    return {
        "function": FUNCTION_MEGAPAYLOAD,
        "fn": tokens[0],
        "size": FRAME_SIZE_TOKEN,
        "sz": tokens[1],
        "charge_state": charge_state,
        "connector": connector,
        "chademo_ccs": connector,
        "posix": posix,
        "voltage": float(voltage),
        "current": float(current),
        "current_delivered": float(current),
        "current_requested": float(current_requested),
        "current_max": float(current_requested),
        "soc": charge_percent,
        "charge_percent": charge_percent,
        "charge_duration": charge_time,
        "charge_time": charge_time,
        "battery_voltage": battery_voltage,
        "energy_accumulated": energy,
        "energy": energy,
        "fan_status": fan_status,
        "t1_dsp": temperature1,
        "t2_board": temperature2,
        "t3_rack": temperature3,
        "t4_cable1": temperature4,
        "t5_cable2": temperature5,
        "temperature1": temperature1,
        "temperature2": temperature2,
        "temperature3": temperature3,
        "temperature4": temperature4,
        "temperature5": temperature5,
        "buttons_raw": buttons_raw,
        "emergency": emergency,
        "emergency_button": emergency,
        "leakage_current": float(leakage_current),
        "leakage_current_input": float(leakage_current),
        "output_resistance": output_resistance,
        "digital_raw": digital_raw,
        "ax": ax,
        "ay": ay,
        "az": az,
        "acelerometer_x": ax,
        "acelerometer_y": ay,
        "acelerometer_z": az,
        "dsp_timestamp": dsp_timestamp,
        "eta": eta,
        "raw_journal_line": raw_line,
        "raw_journal_line_original": original_line,
        "raw_tokens": tokens,
    }
