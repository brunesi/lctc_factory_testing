"""
phases/phase5_contactor.py

Fase 5 — Teste da contatora.

Dois passos assistidos, cada um confirmado pelo operador via botão:

  Passo 1 — WAIT_CLOSE_CONFIRM
    IPC envia comando de FECHAMENTO ao DSP.
    Operador ouve o clique e confirma:
      B1 = SIM (PASS)  |  B2 = NÃO (FAIL)  |  B3 = REPETIR comando

  Passo 2 — WAIT_OPEN_CONFIRM
    IPC envia comando de ABERTURA ao DSP.
    Operador ouve o clique e confirma:
      B1 = SIM (PASS)  |  B2 = NÃO (FAIL)  |  B3 = REPETIR comando

Resultado: PASS somente se ambos os passos foram confirmados.

Nota: o DSP não reporta o estado da contatora no frame de telemetria.
A confirmação depende exclusivamente da percepção auditiva do operador.
"""

import logging
import time
from enum import Enum, auto

from phases.base import Phase
from dsp.state import DspState
from dsp.reader import DspReader, ButtonEvent
from dsp import commands
from result import PhaseResult, Status

logger = logging.getLogger(__name__)


class _Step(Enum):
    WAIT_CLOSE_CONFIRM = auto()
    WAIT_OPEN_CONFIRM  = auto()


STEP_INSTRUCTIONS = {
    _Step.WAIT_CLOSE_CONFIRM: (
        "Passo 1 de 2  —  Fechamento",
        "Comando de FECHAMENTO enviado à contatora.\n"
        "Você ouviu o clique de fechamento?",
    ),
    _Step.WAIT_OPEN_CONFIRM: (
        "Passo 2 de 2  —  Abertura",
        "Comando de ABERTURA enviado à contatora.\n"
        "Você ouviu o clique de abertura?",
    ),
}

BUTTON_LEGEND = "[ B1: SIM / PASS ]   [ B2: NÃO / FAIL ]   [ B3: REPETIR ]"


class Phase5Contactor(Phase):

    def __init__(self, reader: DspReader):
        super().__init__(phase_id=5, phase_name="Contatora")
        self._reader = reader
        self._step   = _Step.WAIT_CLOSE_CONFIRM

        # Exposto ao renderer
        self.step_label: str  = ""
        self.instruction: str = ""
        self.legend: str      = BUTTON_LEGEND

    # ---------------------------------------------------------------- #
    # Interface Phase                                                   #
    # ---------------------------------------------------------------- #

    def on_enter(self, state: DspState) -> None:
        self._step = _Step.WAIT_CLOSE_CONFIRM
        self._update_display(_Step.WAIT_CLOSE_CONFIRM)
        self._send_close()
        logger.info("Fase 5 iniciada — comando de fechamento enviado.")

    def update(self, state: DspState, events: list[ButtonEvent]) -> Status:
        match self._step:
            case _Step.WAIT_CLOSE_CONFIRM:
                return self._handle_close_confirm(events)
            case _Step.WAIT_OPEN_CONFIRM:
                return self._handle_open_confirm(events)
        return Status.RUNNING

    def on_exit(self) -> PhaseResult:
        has_fail = any(
            item.status == Status.FAIL
            for item in self._result.items
        )
        return self._finish(Status.FAIL if has_fail else Status.PASS)

    # ---------------------------------------------------------------- #
    # Handlers por passo                                               #
    # ---------------------------------------------------------------- #

    def _handle_close_confirm(self, events: list[ButtonEvent]) -> Status:
        if self._button_pressed(events, 1):       # SIM
            self._pass("Fechamento da contatora", measured="clique confirmado pelo operador")
            self._go_to_open()
            return Status.RUNNING

        if self._button_pressed(events, 2):       # NÃO
            self._fail(
                "Fechamento da contatora",
                measured="clique não detectado pelo operador",
                note="Verificar contatora e cabeamento",
            )
            self._go_to_open()
            return Status.RUNNING

        if self._button_pressed(events, 3):       # REPETIR
            logger.info("Fase 5: repetindo comando de fechamento.")
            self._send_close()

        return Status.RUNNING

    def _handle_open_confirm(self, events: list[ButtonEvent]) -> Status:
        if self._button_pressed(events, 1):       # SIM
            self._pass("Abertura da contatora", measured="clique confirmado pelo operador")
            has_fail = any(
                item.status == Status.FAIL
                for item in self._result.items
            )
            return Status.FAIL if has_fail else Status.PASS

        if self._button_pressed(events, 2):       # NÃO
            self._fail(
                "Abertura da contatora",
                measured="clique não detectado pelo operador",
                note="Verificar contatora e cabeamento",
            )
            return Status.FAIL

        if self._button_pressed(events, 3):       # REPETIR
            logger.info("Fase 5: repetindo comando de abertura.")
            self._send_open()

        return Status.RUNNING

    # ---------------------------------------------------------------- #
    # Helpers internos                                                  #
    # ---------------------------------------------------------------- #

    def _go_to_open(self) -> None:
        self._step = _Step.WAIT_OPEN_CONFIRM
        self._update_display(_Step.WAIT_OPEN_CONFIRM)
        self._send_open()
        logger.info("Fase 5: avançando para confirmação de abertura.")

    def _send_close(self) -> None:
        ok = commands.contactor_close(self._reader)
        if not ok:
            logger.error("Fase 5: falha ao enviar comando de fechamento.")

    def _send_open(self) -> None:
        ok = commands.contactor_open(self._reader)
        if not ok:
            logger.error("Fase 5: falha ao enviar comando de abertura.")

    def _update_display(self, step: _Step) -> None:
        label, instruction = STEP_INSTRUCTIONS[step]
        self.step_label  = label
        self.instruction = instruction
