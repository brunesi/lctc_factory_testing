"""
phases/phase4_door.py

Fase 4 — Teste do sensor de porta.

Três passos sequenciais com timeout individual (mesmo padrão da Fase 3):

  Passo 1 — VERIFY_CLOSED
    Aguarda sensor de porta = 0 (fechada).
    Se já fechada: PASS imediato, avança.

  Passo 2 — WAIT_OPEN
    Instrução: "Abra a porta do rack."
    Aguarda transição fechada→aberta (door_open: False→True).

  Passo 3 — WAIT_CLOSED
    Instrução: "Feche a porta do rack."
    Aguarda transição aberta→fechada (door_open: True→False).

Resultado: PASS somente se os três passos passaram.

Campo monitorado: D4321[3] (LSB), via DspState.door_open.
  False = porta fechada
  True  = porta aberta
"""

import logging
import time
from enum import Enum, auto

from phases.base import Phase
from dsp.state import DspState
from dsp.reader import ButtonEvent
from result import PhaseResult, Status
import config

logger = logging.getLogger(__name__)


class _Step(Enum):
    VERIFY_CLOSED = auto()
    WAIT_OPEN     = auto()
    WAIT_CLOSED   = auto()


STEP_INSTRUCTIONS = {
    _Step.VERIFY_CLOSED: (
        "Passo 1 de 3",
        "Verifique que a porta do rack\nestá FECHADA.",
        "Aguardando confirmação...",
    ),
    _Step.WAIT_OPEN: (
        "Passo 2 de 3",
        "ABRA a porta do rack.",
        "Aguardando abertura...",
    ),
    _Step.WAIT_CLOSED: (
        "Passo 3 de 3",
        "FECHE a porta do rack.",
        "Aguardando fechamento...",
    ),
}


class Phase4Door(Phase):

    def __init__(self):
        super().__init__(phase_id=4, phase_name="Sensor de Porta")

        self._step        = _Step.VERIFY_CLOSED
        self._step_start  = 0.0
        self._prev_open   = False

        # Exposto ao renderer
        self.step_label: str      = ""
        self.instruction: str     = ""
        self.sub_instruction: str = ""
        self.countdown: float     = 0.0
        self.door_open: bool      = False

    # ---------------------------------------------------------------- #
    # Interface Phase                                                   #
    # ---------------------------------------------------------------- #

    def on_enter(self, state: DspState) -> None:
        snap = state.snapshot()
        self._prev_open  = snap.door_open
        self._step_start = time.monotonic()
        self._update_display(_Step.VERIFY_CLOSED)
        logger.info(
            f"Fase 4 iniciada. estado inicial da porta: door_open={snap.door_open}"
        )

    def update(self, state: DspState, events: list[ButtonEvent]) -> Status:
        snap = state.snapshot()
        self.door_open = snap.door_open
        self.countdown = max(
            0.0,
            config.TIMEOUT_EMERGENCY_STEP - (time.monotonic() - self._step_start),
        )

        match self._step:
            case _Step.VERIFY_CLOSED:
                return self._handle_verify_closed(snap)
            case _Step.WAIT_OPEN:
                return self._handle_wait_open(snap)
            case _Step.WAIT_CLOSED:
                return self._handle_wait_closed(snap)

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

    def _handle_verify_closed(self, snap: DspState) -> Status:
        if not snap.door_open:
            self._pass("Passo 1: porta fechada", measured="door=0")
            return self._go_to(_Step.WAIT_OPEN)

        if self._timed_out():
            self._fail(
                "Passo 1: porta fechada",
                measured="door=1",
                note="Porta permaneceu aberta — feche a porta antes de continuar",
            )
            return self._go_to(_Step.WAIT_OPEN)

        return Status.RUNNING

    def _handle_wait_open(self, snap: DspState) -> Status:
        # Transição fechada→aberta
        if not self._prev_open and snap.door_open:
            self._pass("Passo 2: porta aberta", measured="door=0→1")
            self._prev_open = snap.door_open
            return self._go_to(_Step.WAIT_CLOSED)

        if self._timed_out():
            self._fail(
                "Passo 2: porta aberta",
                measured=f"door={int(snap.door_open)} (sem transição após {config.TIMEOUT_EMERGENCY_STEP}s)",
                note="Abra a porta do rack",
            )
            self._prev_open = snap.door_open
            return self._go_to(_Step.WAIT_CLOSED)

        self._prev_open = snap.door_open
        return Status.RUNNING

    def _handle_wait_closed(self, snap: DspState) -> Status:
        # Transição aberta→fechada
        if self._prev_open and not snap.door_open:
            self._pass("Passo 3: porta fechada novamente", measured="door=1→0")
            self._prev_open = snap.door_open
            has_fail = any(
                item.status == Status.FAIL
                for item in self._result.items
            )
            return Status.FAIL if has_fail else Status.PASS

        if self._timed_out():
            self._fail(
                "Passo 3: porta fechada novamente",
                measured=f"door={int(snap.door_open)} (sem transição após {config.TIMEOUT_EMERGENCY_STEP}s)",
                note="Feche a porta do rack",
            )
            self._prev_open = snap.door_open
            return Status.FAIL

        self._prev_open = snap.door_open
        return Status.RUNNING

    # ---------------------------------------------------------------- #
    # Helpers internos                                                  #
    # ---------------------------------------------------------------- #

    def _timed_out(self) -> bool:
        return (time.monotonic() - self._step_start) >= config.TIMEOUT_EMERGENCY_STEP

    def _go_to(self, step: _Step) -> Status:
        self._step       = step
        self._step_start = time.monotonic()
        self._update_display(step)
        logger.info(f"Fase 4: avançando para {step.name}")
        return Status.RUNNING

    def _update_display(self, step: _Step) -> None:
        label, instruction, sub = STEP_INSTRUCTIONS[step]
        self.step_label      = label
        self.instruction     = instruction
        self.sub_instruction = sub
        self.countdown       = float(config.TIMEOUT_EMERGENCY_STEP)
