"""
phases/phase1_auto.py

Fase 1 — Testes automáticos (sem interação do operador).

Sub-etapas internas:
  CHECKING_DSP   — aguarda posix incrementar (confirma DSP vivo)
  RUNNING_CHECKS — executa checks 1.2–1.10 em sequência
  AUTO_ADVANCE   — exibe resumo, countdown antes de avançar

Política de falha:
  - Item 1.1 (DSP vivo): falha INTERROMPE a fase inteira (retorna FAIL imediatamente)
  - Demais itens: falha é registrada, execução continua
  - Resultado final: FAIL se qualquer item falhou, PASS caso contrário
"""

import logging
import time
from enum import Enum, auto

from phases.base import Phase
from dsp.state import DspState
from dsp.reader import ButtonEvent
from result import PhaseResult, Status
from logger import check_pendrive
import config

logger = logging.getLogger(__name__)


class _SubStep(Enum):
    CHECKING_DSP   = auto()
    RUNNING_CHECKS = auto()
    AUTO_ADVANCE   = auto()


class Phase1Auto(Phase):

    def __init__(self):
        super().__init__(phase_id=1, phase_name="Testes Automáticos")

        self._sub_step = _SubStep.CHECKING_DSP

        # Para detecção de DSP vivo
        self._entry_posix: int = 0
        self._step_start_time: float = 0.0

        # Para countdown de avanço automático
        self._advance_start_time: float = 0.0

        # Exposto ao renderer
        self.current_check: str = "Aguardando DSP..."
        self.countdown: float = 0.0

    # ---------------------------------------------------------------- #
    # Interface Phase                                                   #
    # ---------------------------------------------------------------- #

    def on_enter(self, state: DspState) -> None:
        snap = state.snapshot()
        self._entry_posix   = snap.posix
        self._step_start_time = time.monotonic()
        self.current_check  = "1.1 — Verificando comunicação com DSP"
        logger.info(
            f"Fase 1 iniciada. posix inicial={self._entry_posix}"
        )

    def update(self, state: DspState, events: list[ButtonEvent]) -> Status:

        match self._sub_step:

            case _SubStep.CHECKING_DSP:
                return self._check_dsp_alive(state)

            case _SubStep.RUNNING_CHECKS:
                self._run_all_checks(state)
                # Todos os checks executam em um único frame
                self._sub_step = _SubStep.AUTO_ADVANCE
                self._advance_start_time = time.monotonic()
                return Status.RUNNING

            case _SubStep.AUTO_ADVANCE:
                elapsed = time.monotonic() - self._advance_start_time
                self.countdown = max(
                    0.0,
                    config.TIMEOUT_PHASE_AUTOADVANCE - elapsed
                )
                # Avanço automático por timeout OU qualquer botão
                if elapsed >= config.TIMEOUT_PHASE_AUTOADVANCE or \
                        self._any_button_pressed(events):
                    final = self._determine_final_status()
                    return final

        return Status.RUNNING

    def on_exit(self) -> PhaseResult:
        return self._finish(self._status)

    # ---------------------------------------------------------------- #
    # Sub-etapa 1: DSP vivo                                            #
    # ---------------------------------------------------------------- #

    def _check_dsp_alive(self, state: DspState) -> Status:
        snap = state.snapshot()
        elapsed = time.monotonic() - self._step_start_time

        if snap.posix != self._entry_posix:
            # Posix mudou — DSP está enviando frames
            self._pass(
                "1.1 DSP comunicação",
                measured=f"posix={snap.posix}",
            )
            self.current_check = "Executando verificações..."
            self._sub_step = _SubStep.RUNNING_CHECKS
            return Status.RUNNING

        if elapsed >= config.TIMEOUT_DSP_ALIVE:
            self._fail(
                "1.1 DSP comunicação",
                measured=f"posix sem alteração após {config.TIMEOUT_DSP_ALIVE}s",
                note="Verifique cabo USB e alimentação do DSP",
            )
            # Falha crítica — encerra a fase imediatamente
            logger.error("Fase 1: DSP não respondeu. Encerrando fase.")
            self._status = Status.FAIL
            return Status.FAIL

        # Ainda aguardando
        self.current_check = (
            f"1.1 — Aguardando DSP... "
            f"({config.TIMEOUT_DSP_ALIVE - elapsed:.0f}s)"
        )
        return Status.RUNNING

    # ---------------------------------------------------------------- #
    # Sub-etapa 2: checks rápidos (executam todos de uma vez)          #
    # ---------------------------------------------------------------- #

    def _run_all_checks(self, state: DspState) -> None:
        snap = state.snapshot()

        self._check_temperatures(snap)
        self._check_accelerometer(snap)
        self._check_connector(snap)
        self._check_pendrive()

    def _check_temperatures(self, snap: DspState) -> None:
        for label, value in snap.temperatures.items():
            item_name = f"Temperatura {label}"
            measured  = f"{value}°C"

            if snap.temperature_in_range(value):
                self._pass(item_name, measured=measured)
            else:
                if value <= config.TEMP_MIN:
                    raw_positions = getattr(snap, "raw_t1_t5_positions_hex", {}) or {}
                    raw_window = getattr(snap, "raw_temperature_window_hex", "") or "indisponível"
                    note = (
                        "Sensor lendo zero — verificar conexão do sensor. "
                        f"Diagnóstico raw d[24:33]={raw_window}; posições={raw_positions}"
                    )
                else:
                    note = f"Temperatura acima de {config.TEMP_MAX}°C — verificar ventilação"
                self._fail(item_name, measured=measured, note=note)

    def _check_accelerometer(self, snap: DspState) -> None:
        measured = f"x={snap.ax} y={snap.ay} z={snap.az}"
        if snap.accelerometer_valid:
            self._pass("1.7 Acelerômetro", measured=measured)
        else:
            self._fail(
                "1.7 Acelerômetro",
                measured=measured,
                note="Todos os eixos zero — verificar conexão do acelerômetro",
            )

    def _check_connector(self, snap: DspState) -> None:
        connector_names = {0: "nenhum", 1: "CCS", 2: "CHAdeMO"}
        measured = connector_names.get(snap.connector, str(snap.connector))

        if snap.connector == 0:
            self._pass("1.8 Conector", measured=measured)
        else:
            self._fail(
                "1.8 Conector",
                measured=measured,
                note="Conector detectado como ativo — esperado: nenhum conectado",
            )

    def _check_pendrive(self) -> None:
        if check_pendrive():
            self._pass("1.10 Pendrive", measured="presente e gravável")
        else:
            self._fail(
                "1.10 Pendrive",
                measured="não detectado",
                note="Insira o pendrive no slot correto antes de continuar",
            )

    # ---------------------------------------------------------------- #
    # Resultado final                                                   #
    # ---------------------------------------------------------------- #

    def _determine_final_status(self) -> Status:
        from result import Status as S
        has_fail = any(
            item.status == S.FAIL
            for item in self._result.items
        )
        return S.FAIL if has_fail else S.PASS
