"""
dsp/protocol.py

Leitura binária de frames do DSP e decodificação do megapayload.

Extraído e adaptado de serialProtocol00345.py / PayloadDecoder.
Mantém apenas o necessário para o factory check.

Protocolo de frame:
  SOP (0x7E) | function(1B) | size_msb(1B) | size_lsb(1B) |
  data(size B) | checksum(1B) | EOP (0x7D)

  checksum = complemento de 2 de 8 bits sobre
             [function, size_msb, size_lsb, ...data]
"""

import struct
import logging

import serial

log = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Constantes de protocolo                                             #
# ------------------------------------------------------------------ #

SOP = b'\x7E'
EOP = b'\x7D'
FUNCTION_MEGAPAYLOAD = 0x04
MEGAPAYLOAD_DATA_SIZE = 0x40
MEGAPAYLOAD_PAYLOAD_SIZE = 3 + MEGAPAYLOAD_DATA_SIZE  # fn + size_msb + size_lsb + data[64]

# Formato equivalente ao método original colado pelo Bruno/Xezi, mas
# com pequenas melhorias de tipo:
#   - corrente requisitada: mantissa uint16 + expoente int8
#   - acelerômetro: int16 assinado em big-endian
#
# Tamanho total: 67 bytes = function(1) + size(2) + data(64).
MEGAPAYLOAD_STRUCT_FMT = '>BHBBI3B3B3BB3BH3B4BBBBB3BBBHHH3B3B15B'

# Este é deliberadamente o mesmo formato estrutural do método original
# PayloadDecoder.decode_payload() fornecido como referência:
#   function, size, charge_state, connector, posix,
#   V[3], I[3], current_max(H+b), SOC, charge_time[3],
#   battery_voltage(H), energy[3], fan, T1, T2, T3, T4,
#   push_buttons, emergency, T5, leakage_alarm, leakage_current(H),
#   active_power_sources, open_door_sensors, ax(H), ay(H), az(H),
#   remaining_time[3], output_resistance_alarm, output_resistance(H),
#   PM temps[5], reserved[15].
#
# Tamanho total: 67 bytes = function(1) + size(2) + data(64).
assert struct.calcsize(MEGAPAYLOAD_STRUCT_FMT) == MEGAPAYLOAD_PAYLOAD_SIZE


# ------------------------------------------------------------------ #
# Checksum                                                            #
# ------------------------------------------------------------------ #

def checksum_8_2s_complement(data: bytes) -> int:
    """Complemento de 2 de 8 bits. Se resultado = 0, retorna 0xFF."""
    total  = sum(data) & 0xFF
    result = (-total) & 0xFF
    return result if result != 0 else 0xFF


# ------------------------------------------------------------------ #
# Leitura de frame binário                                            #
# ------------------------------------------------------------------ #

def read_binary_frame(ser: serial.Serial) -> tuple[int, bytes] | None:
    """
    Lê um frame completo da porta serial.
    Retorna (function_code, payload) ou None se frame inválido.

    O payload retornado inclui function + size_msb + size_lsb + data.
    Isto é intencional porque o checksum é calculado exatamente sobre
    essa sequência de bytes.
    """
    while True:
        byte = ser.read(1)
        if not byte:
            log.warning("Timeout aguardando SOP.")
            return None
        if byte == SOP:
            break
        log.debug(f"Byte descartado aguardando SOP: 0x{byte.hex().upper()}")

    function_b = ser.read(1)
    size_msb   = ser.read(1)
    size_lsb   = ser.read(1)

    if len(function_b) < 1 or len(size_msb) < 1 or len(size_lsb) < 1:
        log.warning("Frame incompleto no cabeçalho.")
        return None

    size = struct.unpack('>H', size_msb + size_lsb)[0]

    data          = ser.read(size)
    checksum_byte = ser.read(1)
    eop           = ser.read(1)

    if len(data) < size:
        log.warning(f"Frame incompleto: esperado {size}B de dados, recebido {len(data)}B.")
        return None

    if len(checksum_byte) < 1:
        log.warning("Frame incompleto: checksum ausente.")
        return None

    if len(eop) < 1:
        log.warning("Frame incompleto: EOP ausente.")
        return None

    if eop != EOP:
        log.warning(f"EOP inválido: 0x{eop.hex().upper()}")
        return None

    payload = function_b + size_msb + size_lsb + data

    calculated = checksum_8_2s_complement(payload)
    received   = struct.unpack('>B', checksum_byte)[0]

    if calculated != received:
        log.warning(
            f"Checksum inválido: calculado=0x{calculated:02X} "
            f"recebido=0x{received:02X}"
        )
        return None

    return function_b[0], payload


# ------------------------------------------------------------------ #
# Decodificação do megapayload (function 0x04)                       #
# ------------------------------------------------------------------ #

def _u24_be(b0: int, b1: int, b2: int) -> int:
    """Converte três bytes big-endian para inteiro sem sinal."""
    return (b0 << 16) | (b1 << 8) | b2


def _bit_string(value: int, width: int = 8) -> str:
    """Retorna uma representação binária fixa, útil para bitfields."""
    return format(value & ((1 << width) - 1), f"0{width}b")


def decode_megapayload(payload: bytes) -> dict | None:
    """
    Decodifica o payload do megapayload (function 0x04).

    payload = function(1B) + size(2B) + data(64B) = 67 bytes.

    Esta versão foi reescrita para ficar estruturalmente equivalente ao
    método original PayloadDecoder.decode_payload(), evitando erro manual
    de deslocamento de índice. O mapeamento de T1..T5 permanece exatamente
    o mesmo do método original:

      T1 = d[25]
      T2 = d[26]
      T3 = d[27]
      T4 = d[28]
      T5 = d[31]

    Se T4/T5 aparecerem como zero na tela, os bytes d[28]/d[31] recebidos
    neste processo também estão zerados; por isso o retorno inclui campos
    de diagnóstico com a janela crua d[24:33].
    """
    if len(payload) < MEGAPAYLOAD_PAYLOAD_SIZE:
        log.warning(
            f"decode_megapayload: payload curto demais: {len(payload)}B "
            f"(mínimo {MEGAPAYLOAD_PAYLOAD_SIZE}B = fn + sz + 64 dados)"
        )
        return None

    if len(payload) > MEGAPAYLOAD_PAYLOAD_SIZE:
        log.debug(
            f"decode_megapayload: payload com {len(payload)}B; "
            f"ignorando bytes excedentes após os primeiros {MEGAPAYLOAD_PAYLOAD_SIZE}B."
        )
        payload = payload[:MEGAPAYLOAD_PAYLOAD_SIZE]

    unpacked = struct.unpack(MEGAPAYLOAD_STRUCT_FMT, payload)

    function_code = unpacked[0]
    size          = unpacked[1]

    if function_code != FUNCTION_MEGAPAYLOAD:
        log.warning(
            f"decode_megapayload: function inválida: 0x{function_code:02X} "
            f"(esperado 0x{FUNCTION_MEGAPAYLOAD:02X})"
        )
        return None

    if size != MEGAPAYLOAD_DATA_SIZE:
        log.warning(
            f"decode_megapayload: tamanho inválido: {size}B "
            f"(esperado {MEGAPAYLOAD_DATA_SIZE}B)"
        )
        return None

    # Mantém uma visão direta dos 64 bytes de dados para diagnóstico.
    d = payload[3:]

    charge_state = unpacked[2]
    connector    = unpacked[3]
    posix        = unpacked[4]

    voltage = _u24_be(unpacked[5], unpacked[6], unpacked[7])
    current = _u24_be(unpacked[8], unpacked[9], unpacked[10])

    current_requested = unpacked[11] * (10 ** unpacked[12])

    charge_percent  = unpacked[13]
    charge_time     = _u24_be(unpacked[14], unpacked[15], unpacked[16])
    battery_voltage = unpacked[17]
    energy          = _u24_be(unpacked[18], unpacked[19], unpacked[20])

    fan_status          = unpacked[21]
    temperature1        = unpacked[22]
    temperature2        = unpacked[23]
    temperature3        = unpacked[24]
    temperature4        = unpacked[25]
    push_buttons        = unpacked[26]
    emergency           = unpacked[27]
    temperature5        = unpacked[28]
    leakage_input_alarm = unpacked[29]
    leakage_current     = unpacked[30]

    active_power_sources = unpacked[31]
    open_door_sensors    = unpacked[32]

    # O método original trata os três eixos como uint16 big-endian (HHH).
    ax = unpacked[33]
    ay = unpacked[34]
    az = unpacked[35]

    remaining_time_to_full_soc = _u24_be(unpacked[36], unpacked[37], unpacked[38])
    output_resistance_alarm    = unpacked[39]
    output_resistance          = unpacked[40]

    power_module_temperatures = list(unpacked[41:46])

    # Mesmo mapeamento legado do projeto principal.
    button4 = bool(push_buttons & 0x40)
    button3 = bool(push_buttons & 0x10)
    button2 = bool(push_buttons & 0x20)
    button1 = bool(push_buttons & 0x80)
    buttons_raw = f"{int(button4)}{int(button3)}{int(button2)}{int(button1)}"

    digital_raw = (
        f"{int(bool(open_door_sensors & 0x08))}"
        f"{int(bool(open_door_sensors & 0x04))}"
        f"{int(bool(open_door_sensors & 0x02))}"
        f"{int(bool(open_door_sensors & 0x01))}"
    )

    return {
        "function":                         function_code,
        "size":                             size,
        "charge_state":                     charge_state,
        "connector":                        connector,
        "chademo_ccs":                      connector,
        "posix":                            posix,
        "voltage":                          float(voltage),
        "current":                          float(current),
        "current_delivered":                float(current),
        "current_requested":                float(current_requested),
        "current_max":                      float(current_requested),
        "soc":                              charge_percent,
        "charge_percent":                   charge_percent,
        "charge_duration":                  charge_time,
        "charge_time":                      charge_time,
        "battery_voltage":                  battery_voltage,
        "energy_accumulated":               energy,
        "energy":                           energy,
        "fan_status":                       fan_status,
        "t1_dsp":                           temperature1,
        "t2_board":                         temperature2,
        "t3_rack":                          temperature3,
        "t4_cable1":                        temperature4,
        "t5_cable2":                        temperature5,
        "temperature1":                     temperature1,
        "temperature2":                     temperature2,
        "temperature3":                     temperature3,
        "temperature4":                     temperature4,
        "temperature5":                     temperature5,
        "push_buttons":                     push_buttons,
        "push_buttons_bits":                _bit_string(push_buttons),
        "buttons_raw":                      buttons_raw,
        "emergency":                        emergency,
        "emergency_button":                 emergency,
        "leakage_input_alarm":              leakage_input_alarm,
        "leakage_current":                  float(leakage_current),
        "leakage_current_input":            float(leakage_current),
        "active_power_sources":             active_power_sources,
        "active_power_sources_bits":        _bit_string(active_power_sources),
        "open_door_sensors":                open_door_sensors,
        "open_door_sensors_bits":           _bit_string(open_door_sensors),
        "digital_raw":                      digital_raw,
        "ax":                               ax,
        "ay":                               ay,
        "az":                               az,
        "acelerometer_x":                   ax,
        "acelerometer_y":                   ay,
        "acelerometer_z":                   az,
        "remaining_time_to_full_soc":       remaining_time_to_full_soc,
        "full_remaining_time":              remaining_time_to_full_soc,
        "output_resistance_alarm":          output_resistance_alarm,
        "output_resistance":                output_resistance,
        "leakage_current_output_alarm":     output_resistance_alarm,
        "leakage_current_output":           output_resistance,
        "power_module_1_temperature":       power_module_temperatures[0],
        "power_module_2_temperature":       power_module_temperatures[1],
        "power_module_3_temperature":       power_module_temperatures[2],
        "power_module_4_temperature":       power_module_temperatures[3],
        "power_module_5_temperature":       power_module_temperatures[4],
        "temperature_pm1":                  power_module_temperatures[0],
        "temperature_pm2":                  power_module_temperatures[1],
        "temperature_pm3":                  power_module_temperatures[2],
        "temperature_pm4":                  power_module_temperatures[3],
        "temperature_pm5":                  power_module_temperatures[4],
        "power_module_temperatures":        power_module_temperatures,
        # Diagnóstico específico para o problema de T4/T5 zeradas.
        # d[24:33] = fan, T1, T2, T3, T4, push, emergency, T5, leakage_alarm
        "raw_payload_hex":                  payload.hex(" ").upper(),
        "raw_data_hex":                     d.hex(" ").upper(),
        "raw_temperature_window_hex":       d[24:33].hex(" ").upper(),
        "raw_t1_t5_positions_hex":          {
            "d25_t1": f"0x{d[25]:02X}",
            "d26_t2": f"0x{d[26]:02X}",
            "d27_t3": f"0x{d[27]:02X}",
            "d28_t4": f"0x{d[28]:02X}",
            "d31_t5": f"0x{d[31]:02X}",
        },
    }
