"""
phases/phase7_inspections.py

Fase 7 — Inspeções visuais.

Carrega a lista de perguntas de factory_inspections.yaml.
Exibe uma pergunta por vez. Operador responde via botão:

  B1 = PASS  |  B2 = FAIL  |  B4 = PULAR esta inspeção

Itens pulados são registrados como SKIP — não geram FAIL.
Resultado da fase: FAIL se qualquer item foi FAIL.

O arquivo YAML é recarregado a cada execução, permitindo
que o parceiro edite a lista sem modificar o código.
"""

import logging
from pathlib import Path

import yaml  # pip install pyyaml

from phases.base import Phase
from dsp.state import DspState
from dsp.reader import ButtonEvent
from result import PhaseResult, Status
import config

logger = logging.getLogger(__name__)

BUTTON_LEGEND = "[ B1: PASS ]   [ B2: FAIL ]   [ B4: PULAR ]"


class Phase7Inspections(Phase):

    def __init__(self):
        super().__init__(phase_id=7, phase_name="Inspeções Visuais")

        self._questions: list[str] = []
        self._index: int = 0

        # Exposto ao renderer
        self.current_question: str = ""
        self.progress: str         = ""    # ex: "3 / 10"
        self.legend: str           = BUTTON_LEGEND

    # ---------------------------------------------------------------- #
    # Interface Phase                                                   #
    # ---------------------------------------------------------------- #

    def on_enter(self, state: DspState) -> None:
        self._questions = self._load_questions()
        self._index     = 0

        if not self._questions:
            logger.warning(
                "Fase 7: nenhuma pergunta carregada. "
                f"Verifique {config.INSPECTIONS_FILE}"
            )

        self._update_display()
        logger.info(
            f"Fase 7 iniciada. {len(self._questions)} inspeções carregadas."
        )

    def update(self, state: DspState, events: list[ButtonEvent]) -> Status:
        # Sem perguntas: encerra imediatamente como SKIP
        if not self._questions:
            self._skip("Inspeções visuais", note="Arquivo de inspeções vazio ou não encontrado")
            return Status.SKIP

        if self._button_pressed(events, 1):     # PASS
            self._pass(
                self._questions[self._index],
                measured="confirmado pelo operador",
            )
            return self._advance()

        if self._button_pressed(events, 2):     # FAIL
            self._fail(
                self._questions[self._index],
                measured="reprovado pelo operador",
                note="Corrigir antes de liberar o rack",
            )
            return self._advance()

        if self._button_pressed(events, 4):     # PULAR
            self._skip(
                self._questions[self._index],
                note="Pulado pelo operador",
            )
            return self._advance()

        return Status.RUNNING

    def on_exit(self) -> PhaseResult:
        has_fail = any(
            item.status == Status.FAIL
            for item in self._result.items
        )
        return self._finish(Status.FAIL if has_fail else Status.PASS)

    # ---------------------------------------------------------------- #
    # Helpers internos                                                  #
    # ---------------------------------------------------------------- #

    def _advance(self) -> Status:
        self._index += 1

        if self._index >= len(self._questions):
            has_fail = any(
                item.status == Status.FAIL
                for item in self._result.items
            )
            return Status.FAIL if has_fail else Status.PASS

        self._update_display()
        return Status.RUNNING

    def _update_display(self) -> None:
        if not self._questions:
            self.current_question = ""
            self.progress         = "0 / 0"
            return

        self.current_question = self._questions[self._index]
        self.progress         = f"{self._index + 1} / {len(self._questions)}"

    def _load_questions(self) -> list[str]:
        path = Path(config.INSPECTIONS_FILE)
        if not path.exists():
            logger.error(f"Arquivo não encontrado: {path.resolve()}")
            return []
        try:
            with path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f)
            questions = data.get("inspections", [])
            if not isinstance(questions, list):
                raise ValueError("Campo 'inspections' não é uma lista.")
            return [str(q) for q in questions]
        except Exception as e:
            logger.error(f"Erro ao carregar {path}: {e}")
            return []
