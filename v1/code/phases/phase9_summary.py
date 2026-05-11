"""
phases/phase9_summary.py

Fase 9 — Sumário final e exportação de log.

Responsabilidades:
  - Recebe o CheckResult consolidado de todas as fases anteriores
  - Exibe resultado por fase na tela (PASS / FAIL / SKIP)
  - Exibe resultado geral (APROVADO / REPROVADO)
  - Salva log em disco interno e tenta exportar para pendrive
  - Aguarda confirmação do operador (qualquer botão) para encerrar

Esta fase nunca retorna FAIL para o CheckResult — ela apenas
exibe e persiste o que as fases anteriores produziram.
"""

import logging

from phases.base import Phase
from dsp.state import DspState
from dsp.reader import ButtonEvent
from result import CheckResult, PhaseResult, Status
import logger as app_logger

log = logging.getLogger(__name__)

BUTTON_LEGEND = "[ Qualquer botão: Encerrar ]"


class Phase9Summary(Phase):

    def __init__(self, check_result: CheckResult, session_id: str):
        super().__init__(phase_id=9, phase_name="Sumário Final")
        self._check_result = check_result
        self._session_id   = session_id

        # Exposto ao renderer
        self.overall_approved: bool       = False
        self.phase_summaries: list[dict]  = []   # [{name, status, items}]
        self.log_saved_internal: bool     = False
        self.log_saved_pendrive: bool     = False
        self.legend: str                  = BUTTON_LEGEND

    # ---------------------------------------------------------------- #
    # Interface Phase                                                   #
    # ---------------------------------------------------------------- #

    def on_enter(self, state: DspState) -> None:
        self._check_result.finish()
        self.overall_approved = self._check_result.approved
        self._build_summaries()
        self._save_logs()
        log.info(
            f"Fase 9: check concluído. "
            f"Resultado: {'APROVADO' if self.overall_approved else 'REPROVADO'}"
        )

    def update(self, state: DspState, events: list[ButtonEvent]) -> Status:
        # Qualquer botão encerra
        if self._any_button_pressed(events):
            return Status.PASS
        return Status.RUNNING

    def on_exit(self) -> PhaseResult:
        return self._finish(Status.PASS)

    # ---------------------------------------------------------------- #
    # Helpers internos                                                  #
    # ---------------------------------------------------------------- #

    def _build_summaries(self) -> None:
        """Prepara estrutura de dados para o renderer exibir."""
        self.phase_summaries = [
            {
                "id":     phase.phase_id,
                "name":   phase.phase_name,
                "status": phase.status,
                "items":  [
                    {
                        "name":     item.name,
                        "status":   item.status,
                        "measured": item.measured,
                        "note":     item.note,
                    }
                    for item in phase.items
                ],
            }
            for phase in self._check_result.phases
        ]

    def _save_logs(self) -> None:
        outcomes = app_logger.save_result(self._check_result, self._session_id)
        self.log_saved_internal = outcomes.get("internal", False)
        self.log_saved_pendrive = outcomes.get("pendrive", False)

        if not self.log_saved_internal:
            log.error("Fase 9: falha ao salvar log interno.")
        if not self.log_saved_pendrive:
            log.warning("Fase 9: log não exportado para pendrive.")
