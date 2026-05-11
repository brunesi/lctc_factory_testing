"""
phases/phase8_network_load.py

Fase 8 — Rede e testes de carga (condicional).

Estrutura interna:

  NETWORK_CHECKS
    Executa 5 pings em sequência. Se 8.1 (Teltonika) falhar,
    os demais são registrados como SKIP (sem rota, sem sentido testar).
    Ao final, exibe resultado e avança para o menu de carga.

  LOAD_MENU
    Tela de seleção:
      B1 = Testar CCS
      B2 = Testar CHAdeMO
      B4 = Encerrar fase

  LOAD_CONNECTING (CCS ou CHAdeMO)
    Instrução para conectar maleta/veículo.
    Aguarda detecção do conector correto no frame DSP (timeout configurável).
    Timeout → SKIP do teste de carga, volta ao menu.

  LOAD_ACTIVE
    Conector detectado. Exibe leituras ao vivo (V, I, En, Rno).
    Verifica Rno: se em carga e Rno < 1000 → alerta de isolação.
    B4 = encerrar teste de carga → volta ao menu.

Testes de carga pulados não geram FAIL no resultado geral.
"""

import logging
import subprocess
import time
from enum import Enum, auto

from phases.base import Phase
from dsp.state import DspState
from dsp.reader import ButtonEvent
from result import PhaseResult, ItemResult, Status
import config

logger = logging.getLogger(__name__)

# Conector esperado por tipo de carga
CONNECTOR_CCS     = 1
CONNECTOR_CHADEMO = 2

# Rno esperado em carga (isolação ok)
RNO_LOAD_EXPECTED = 1000

BUTTON_LEGEND_MENU = (
    "[ B1: Testar CCS ]   [ B2: Testar CHAdeMO ]   [ B4: Encerrar ]"
)
BUTTON_LEGEND_LOAD = "[ B4: Encerrar teste de carga ]"


class _SubStep(Enum):
    NETWORK_CHECKS   = auto()
    LOAD_MENU        = auto()
    LOAD_CONNECTING  = auto()   # aguardando conexão do veículo/maleta
    LOAD_ACTIVE      = auto()   # carga em andamento


class Phase8NetworkLoad(Phase):

    def __init__(self):
        super().__init__(phase_id=8, phase_name="Rede e Testes de Carga")

        self._sub_step          = _SubStep.NETWORK_CHECKS
        self._network_done      = False
        self._connecting_type   = 0        # 1=CCS, 2=CHAdeMO
        self._connect_start     = 0.0
        self._load_readings: dict = {}     # snapshot de leituras ao encerrar

        # Exposto ao renderer
        self.current_check: str   = ""
        self.legend: str          = ""
        self.countdown: float     = 0.0
        self.live_readings: dict  = {}     # atualizado em LOAD_ACTIVE
        self.rno_alert: bool      = False  # alerta de isolação

    # ---------------------------------------------------------------- #
    # Interface Phase                                                   #
    # ---------------------------------------------------------------- #

    def on_enter(self, state: DspState) -> None:
        self._sub_step     = _SubStep.NETWORK_CHECKS
        self._network_done = False
        self.current_check = "Iniciando verificações de rede..."
        logger.info("Fase 8 iniciada.")

    def update(self, state: DspState, events: list[ButtonEvent]) -> Status:
        match self._sub_step:

            case _SubStep.NETWORK_CHECKS:
                return self._run_network_checks()

            case _SubStep.LOAD_MENU:
                return self._handle_load_menu(events)

            case _SubStep.LOAD_CONNECTING:
                return self._handle_connecting(state)

            case _SubStep.LOAD_ACTIVE:
                return self._handle_load_active(state, events)

        return Status.RUNNING

    def on_exit(self) -> PhaseResult:
        has_fail = any(
            item.status == Status.FAIL
            for item in self._result.items
        )
        return self._finish(Status.FAIL if has_fail else Status.PASS)

    # ---------------------------------------------------------------- #
    # Rede                                                             #
    # ---------------------------------------------------------------- #

    def _run_network_checks(self) -> Status:
        """
        Executa os 5 pings em sequência.
        Chamado uma única vez — bloqueia brevemente o loop
        (cada ping tem timeout curto via -W).
        Retorna RUNNING ao final e avança para LOAD_MENU.
        """
        self.current_check = "Verificando rede..."

        # 8.1 — Teltonika (link local)
        teltonika_ok = self._ping(
            host=config.PING_TELTONIKA,
            label="8.1 Link Teltonika",
            fail_note="Verificar cabo Ethernet e IP fixo da LattePanda (3.1.1.2)",
        )

        if not teltonika_ok:
            # Sem rota local — demais testes não fazem sentido
            for label in [
                "8.2 Rota internet (8.8.8.8)",
                "8.3 Rota internet redundante (1.1.1.1)",
                "8.4 DNS google.com",
                "8.5 DNS cloudflare.com",
            ]:
                self._skip(label, note="Pulado — link com Teltonika falhou")
        else:
            # 8.2 / 8.3 — rota para internet
            goog_ok = self._ping(
                host=config.PING_GOOGLE_DNS,
                label="8.2 Rota internet (8.8.8.8)",
                fail_note="Verificar conexão WAN do Teltonika (SIM card / cabo)",
            )
            cf_ok = self._ping(
                host=config.PING_CLOUDFLARE,
                label="8.3 Rota internet redundante (1.1.1.1)",
                fail_note="Verificar conexão WAN do Teltonika",
            )

            # 8.4 / 8.5 — resolução DNS (só testa se ao menos uma rota passou)
            if goog_ok or cf_ok:
                self._ping(
                    host=config.PING_GOOGLE_HOST,
                    label="8.4 DNS google.com",
                    fail_note="Verificar configuração de DNS no Teltonika",
                )
                self._ping(
                    host=config.PING_CF_HOST,
                    label="8.5 DNS cloudflare.com",
                    fail_note="Verificar configuração de DNS no Teltonika",
                )
            else:
                for label in ["8.4 DNS google.com", "8.5 DNS cloudflare.com"]:
                    self._skip(label, note="Pulado — sem rota para internet")

        self._network_done = True
        self._sub_step     = _SubStep.LOAD_MENU
        self.legend        = BUTTON_LEGEND_MENU
        self.current_check = "Rede verificada. Selecione o teste de carga."
        logger.info("Fase 8: verificações de rede concluídas.")
        return Status.RUNNING

    def _ping(self, host: str, label: str, fail_note: str) -> bool:
        """
        Executa ping via subprocess.
        Retorna True se bem-sucedido.
        """
        self.current_check = f"Ping {host}..."
        try:
            result = subprocess.run(
                ["ping", "-c", str(config.PING_COUNT),
                         "-W", str(config.PING_TIMEOUT_S), host],
                capture_output=True,
                timeout=config.PING_TIMEOUT_S * config.PING_COUNT + 2,
            )
            if result.returncode == 0:
                self._pass(label, measured=f"ping {host} OK")
                return True
            else:
                self._fail(label, measured=f"ping {host} sem resposta", note=fail_note)
                return False
        except subprocess.TimeoutExpired:
            self._fail(label, measured=f"ping {host} timeout", note=fail_note)
            return False
        except Exception as e:
            self._fail(label, measured=str(e), note=fail_note)
            return False

    # ---------------------------------------------------------------- #
    # Menu de carga                                                     #
    # ---------------------------------------------------------------- #

    def _handle_load_menu(self, events: list[ButtonEvent]) -> Status:
        self.legend = BUTTON_LEGEND_MENU

        if self._button_pressed(events, 1):
            self._start_connecting(CONNECTOR_CCS)
            return Status.RUNNING

        if self._button_pressed(events, 2):
            self._start_connecting(CONNECTOR_CHADEMO)
            return Status.RUNNING

        if self._button_pressed(events, 4):
            # Encerra fase sem teste de carga
            has_fail = any(
                item.status == Status.FAIL
                for item in self._result.items
            )
            return Status.FAIL if has_fail else Status.PASS

        return Status.RUNNING

    def _start_connecting(self, connector_type: int) -> None:
        self._connecting_type = connector_type
        self._connect_start   = time.monotonic()
        self._sub_step        = _SubStep.LOAD_CONNECTING
        self.legend           = ""
        self.countdown        = float(config.TIMEOUT_LOAD_TEST)
        label = "CCS" if connector_type == CONNECTOR_CCS else "CHAdeMO"
        self.current_check    = (
            f"Conecte a maleta de teste ou veículo {label}.\n"
            f"Aguardando detecção do conector..."
        )
        logger.info(f"Fase 8: aguardando conexão {label}.")

    # ---------------------------------------------------------------- #
    # Aguardando conexão                                               #
    # ---------------------------------------------------------------- #

    def _handle_connecting(self, state: DspState) -> Status:
        snap     = state.snapshot()
        elapsed  = time.monotonic() - self._connect_start
        self.countdown = max(0.0, config.TIMEOUT_LOAD_TEST - elapsed)
        label    = "CCS" if self._connecting_type == CONNECTOR_CCS else "CHAdeMO"

        # Conector correto detectado?
        if snap.connector == self._connecting_type:
            expected_state = (
                config.CHARGE_STATE_CCS_CONNECTED
                if self._connecting_type == CONNECTOR_CCS
                else config.CHARGE_STATE_CHADEMO_CONNECTED
            )
            if snap.charge_state == expected_state:
                self._pass(
                    f"Conexão {label} detectada",
                    measured=f"cc={snap.connector} st=0x{snap.charge_state:02X}",
                )
                self._sub_step = _SubStep.LOAD_ACTIVE
                self.legend    = BUTTON_LEGEND_LOAD
                self.current_check = f"Carga {label} em andamento."
                logger.info(f"Fase 8: conector {label} detectado.")
                return Status.RUNNING

        if elapsed >= config.TIMEOUT_LOAD_TEST:
            self._skip(
                f"Teste de carga {label}",
                note=f"Conector não detectado após {config.TIMEOUT_LOAD_TEST}s — teste pulado",
            )
            self._sub_step = _SubStep.LOAD_MENU
            self.legend    = BUTTON_LEGEND_MENU
            self.current_check = "Selecione o próximo teste ou encerre."
            logger.warning(f"Fase 8: timeout aguardando conector {label}.")
            return Status.RUNNING

        return Status.RUNNING

    # ---------------------------------------------------------------- #
    # Carga ativa                                                      #
    # ---------------------------------------------------------------- #

    def _handle_load_active(self, state: DspState, events: list[ButtonEvent]) -> Status:
        snap = state.snapshot()
        label = "CCS" if self._connecting_type == CONNECTOR_CCS else "CHAdeMO"

        # Atualiza leituras ao vivo para o renderer
        self.live_readings = {
            "Tensão (V)":       f"{snap.voltage:.1f} V",
            "Corrente (A)":     f"{snap.current:.1f} A",
            "Energia (Wh)":     f"{snap.energy_accumulated} Wh",
            "SOC (%)":          f"{snap.soc} %",
            "Rno":              str(snap.output_resistance),
        }

        # Alerta de isolação: Rno em carga deveria ser 1000
        self.rno_alert = (
            snap.connector != 0
            and snap.output_resistance not in (0, RNO_LOAD_EXPECTED)
        )

        # Operador encerra o teste
        if self._button_pressed(events, 4):
            self._record_load_result(snap, label)
            self._sub_step = _SubStep.LOAD_MENU
            self.legend    = BUTTON_LEGEND_MENU
            self.live_readings = {}
            self.rno_alert     = False
            self.current_check = "Selecione o próximo teste ou encerre."
            logger.info(f"Fase 8: teste de carga {label} encerrado pelo operador.")
            return Status.RUNNING

        return Status.RUNNING

    def _record_load_result(self, snap: DspState, label: str) -> None:
        """Registra snapshot das leituras elétricas ao encerrar a carga."""
        rno_ok = snap.output_resistance == RNO_LOAD_EXPECTED

        measured = (
            f"V={snap.voltage:.1f} I={snap.current:.1f} "
            f"En={snap.energy_accumulated}Wh Rno={snap.output_resistance}"
        )

        if rno_ok:
            self._pass(f"Leituras carga {label}", measured=measured)
        else:
            self._fail(
                f"Leituras carga {label}",
                measured=measured,
                note=(
                    f"Rno={snap.output_resistance} — esperado {RNO_LOAD_EXPECTED}. "
                    "Verificar isolação de saída."
                ),
            )
