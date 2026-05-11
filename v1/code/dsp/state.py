"""
dsp/state.py

Estrutura de dados que representa o estado atual do DSP,
preenchida a cada frame 04 64 recebido pela thread serial.
"""

from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock


@dataclass
class DspState:
    """
    Campos mapeados do frame 04 64.

    Índices de referência (tokens após split()):
      0   fn         — fixo '04'
      1   sz         — fixo '64'
      2   st         — charge state (hex)
      3   cc         — conector ativo
      4   posix      — timestamp do DSP (incrementa a cada envio)
      5   V          — tensão instantânea do veículo
      6   I          — corrente fornecida
      7   Im         — corrente solicitada pelo veículo
      8   e%         — SOC do veículo
      9   et         — duração da carga atual
      10  Vb         — tensão da bateria do veículo
      11  En         — energia acumulada transferida
      12  Fan        — status do ventilador (0=off, 1=on)
      13  T1         — temperatura do DSP
      14  T2         — temperatura da placa DSP
      15  T3         — temperatura interna do rack
      16  T4         — temperatura cabo CCS 1
      17  T5         — temperatura cabo CCS 2
      18  PB         — ignorado
      19  4321       — pushbuttons individuais (string '0000')
      20  em         — botoeira de emergência (0=liberada, 1=pressionada)
      21  Iil        — corrente de fuga (reservado)
      22  Rno        — resistência normalizada de saída
      23  F54321     — ignorado
      24  D4321      — sensores digitais; D4321[3] (LSB) = sensor de porta
      25  Ax         — acelerômetro X
      26  Ay         — acelerômetro Y
      27  Az         — acelerômetro Z
      28  timestamp  — timestamp ISO do DSP
      29-33 M1-M5   — ignorados
      34  ETA        — ignorado
    """

    # --- Identificação de frame ---
    fn: str = "00"
    sz: str = "00"
    frame_valid: bool = False          # True se fn=='04' e sz=='64'

    # --- Estado geral ---
    charge_state: int = 0              # st, valor inteiro do hex
    connector: int = 0                 # cc: 0=nenhum, 1=CCS, 2=CHAdeMO

    # --- Heartbeat do DSP ---
    posix: int = 0                     # incrementa a cada envio

    # --- Variáveis elétricas (relevantes na fase de carga) ---
    voltage: float = 0.0               # V
    current: float = 0.0               # I
    current_requested: float = 0.0     # Im
    soc: int = 0                       # e%
    charge_duration: int = 0           # et
    battery_voltage: int = 0           # Vb (uint)
    energy_accumulated: int = 0        # En (uint)

    # --- Ventilador ---
    fan_status: int = 0                # 0=off, 1=on

    # --- Temperaturas ---
    t1_dsp: int = 0
    t2_board: int = 0
    t3_rack: int = 0
    t4_cable1: int = 0
    t5_cable2: int = 0

    # --- Botões (string '0000'; índice 0=B4, índice 3=B1) ---
    buttons_raw: str = "0000"

    # --- Botoeira de emergência ---
    emergency: int = 0                 # 0=liberada, 1=pressionada

    # --- Corrente de fuga (reservado para calibração futura) ---
    leakage_current: float = 0.0       # Iil

    # --- Resistência de saída ---
    output_resistance: int = 0         # Rno

    # --- Sensores digitais (string '0000'; D4321[3]=porta) ---
    digital_raw: str = "0000"

    # --- Acelerômetro ---
    ax: int = 0
    ay: int = 0
    az: int = 0

    # --- Timestamp do DSP ---
    dsp_timestamp: str = ""

    # --- Diagnóstico do último megapayload ---
    raw_payload_hex: str = ""
    raw_data_hex: str = ""
    raw_temperature_window_hex: str = ""
    raw_t1_t5_positions_hex: dict = field(default_factory=dict)

    # --- Controle interno ---
    lock: Lock = field(default_factory=Lock, compare=False, repr=False)
    last_updated: datetime = field(default_factory=datetime.now, compare=False)

    # ------------------------------------------------------------------ #
    # Propriedades derivadas — lidas pelo loop Pygame e pelas fases       #
    # ------------------------------------------------------------------ #

    @property
    def button1(self) -> bool:
        """B1 = caractere de índice 3 em buttons_raw."""
        return self.buttons_raw[3] == "1"

    @property
    def button2(self) -> bool:
        return self.buttons_raw[2] == "1"

    @property
    def button3(self) -> bool:
        return self.buttons_raw[1] == "1"

    @property
    def button4(self) -> bool:
        """B4 = caractere de índice 0 em buttons_raw."""
        return self.buttons_raw[0] == "1"

    @property
    def door_open(self) -> bool:
        """Sensor de porta: LSB de D4321, índice 3 da string."""
        return self.digital_raw[3] == "1"

    @property
    def temperatures(self) -> dict[str, int]:
        """Dicionário para facilitar iteração nas verificações da Fase 1."""
        return {
            "T1 (DSP)":         self.t1_dsp,
            "T2 (Placa DSP)":   self.t2_board,
            "T3 (Rack)":        self.t3_rack,
            "T4 (Cabo CCS 1)":  self.t4_cable1,
            "T5 (Cabo CCS 2)":  self.t5_cable2,
        }

    @property
    def accelerometer_valid(self) -> bool:
        """Falha se todos os três eixos forem zero simultaneamente."""
        return not (self.ax == 0 and self.ay == 0 and self.az == 0)

    def temperature_in_range(self, value: int) -> bool:
        """Critério de aprovação das temperaturas: 0 < T < 100."""
        return 0 < value < 100

    def snapshot(self) -> "DspState":
        """
        Retorna uma cópia thread-safe dos dados atuais.
        Usar nas fases para evitar leitura parcial durante atualização.
        """
        with self.lock:
            from copy import copy
            return copy(self)
