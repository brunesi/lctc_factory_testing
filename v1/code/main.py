"""
main.py

Entry point do factory check.

Responsabilidades:
  - Ler número de série
  - Configurar logging
  - Inicializar Pygame e tela
  - Criar DspState, DspReader e fila de eventos
  - Instanciar todas as fases
  - Executar loop principal (update → render → transição)
  - Encerrar limpo ao final

Execução:
  python3 main.py
"""

import queue
import sys
import time

import pygame

import config
import logger as app_logger
from dsp.state import DspState
from dsp.reader import DspReader
from result import CheckResult, Status
from ui import renderer
from ui.theme import C, L, F

# Fases
from phases.phase1_auto        import Phase1Auto
from phases.phase2_buttons      import Phase2Buttons
from phases.phase3_emergency    import Phase3Emergency
from phases.phase4_door         import Phase4Door
from phases.phase5_contactor    import Phase5Contactor
from phases.phase6_fan          import Phase6Fan
from phases.phase7_inspections  import Phase7Inspections
from phases.phase8_network_load import Phase8NetworkLoad
from phases.phase9_summary      import Phase9Summary


# ------------------------------------------------------------------ #
# Número de série                                                     #
# ------------------------------------------------------------------ #

def _read_serial_number() -> str:
    from pathlib import Path
    path = Path(config.SERIAL_NUMBER_FILE)
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return "SN-DESCONHECIDO"


# ------------------------------------------------------------------ #
# Tela de erro fatal (DSP não respondeu)                             #
# ------------------------------------------------------------------ #

def _show_fatal_dsp_error(screen: pygame.Surface,
                          clock: pygame.time.Clock) -> None:
    """
    Exibida quando a Fase 1 falha por falta de comunicação com o DSP.
    Fica na tela até o operador pressionar qualquer botão ou ESC.
    """
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if event.type == pygame.KEYDOWN:
                return

        screen.fill(C.BG)

        # Faixa de erro
        band = pygame.Rect(0, 0, L.W, 120)
        pygame.draw.rect(screen, C.ALERT_BG, band)
        pygame.draw.line(screen, C.FAIL, (0, 120), (L.W, 120), 3)

        F.result_large.render   # garante que a fonte está pronta
        surf = F.result_large.render("ERRO FATAL", True, C.FAIL)
        screen.blit(surf, surf.get_rect(center=(L.W // 2, 60)))

        # Mensagem
        lines = [
            "DSP não respondeu dentro do tempo limite.",
            "",
            "Verifique:",
            "  · Cabo USB entre LattePanda e DSP",
            "  · Alimentação do DSP",
            f"  · Porta serial: {config.SERIAL_PORT}",
            "",
            "O check não pode prosseguir.",
            "Corrija o problema e reinicie o sistema.",
        ]
        y = 150
        for line in lines:
            if line:
                surf = F.body.render(line, True, C.TEXT_PRIMARY)
                screen.blit(surf, (L.MARGIN, y))
            y += F.body.get_linesize() + 8

        # Rodapé
        pygame.draw.line(screen, C.BORDER, (0, L.FOOTER_Y), (L.W, L.FOOTER_Y))
        legend = F.legend.render(
            "Pressione qualquer botão para encerrar", True, C.TEXT_MUTED
        )
        screen.blit(legend, legend.get_rect(
            center=(L.W // 2, L.FOOTER_Y + L.FOOTER_H // 2)
        ))

        pygame.display.flip()
        clock.tick(config.FPS)


# ------------------------------------------------------------------ #
# Tela de boot / boas-vindas                                         #
# ------------------------------------------------------------------ #

def _show_boot_screen(screen: pygame.Surface,
                      clock: pygame.time.Clock,
                      serial_number: str,
                      event_queue: queue.Queue) -> None:
    """
    Exibida antes do check começar.
    Avança após TIMEOUT_PHASE_AUTOADVANCE segundos OU qualquer botão.
    """
    start = time.monotonic()
    while True:
        # Eventos pygame (teclado — útil em desenvolvimento)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            if event.type == pygame.KEYDOWN:
                return

        # Botão físico via fila DSP
        if not event_queue.empty():
            try:
                event_queue.get_nowait()
            except queue.Empty:
                pass
            return

        elapsed  = time.monotonic() - start
        remaining = config.TIMEOUT_PHASE_AUTOADVANCE - elapsed
        if remaining <= 0:
            return

        screen.fill(C.BG)

        # Logo / título
        t = F.result_large.render("FACTORY CHECK", True, C.ACCENT)
        screen.blit(t, t.get_rect(center=(L.W // 2, 220)))

        t = F.heading.render("Verificação de montagem", True, C.TEXT_SECONDARY)
        screen.blit(t, t.get_rect(center=(L.W // 2, 290)))

        # Número de série
        pygame.draw.rect(screen, C.BG_PANEL,
                         pygame.Rect(L.MARGIN, 360, L.W - 2 * L.MARGIN, 70),
                         border_radius=8)
        t = F.mono_small.render("NÚMERO DE SÉRIE", True, C.TEXT_MUTED)
        screen.blit(t, t.get_rect(center=(L.W // 2, 375)))
        t = F.mono.render(serial_number, True, C.TEXT_PRIMARY)
        screen.blit(t, t.get_rect(center=(L.W // 2, 403)))

        # Countdown
        frac = remaining / config.TIMEOUT_PHASE_AUTOADVANCE
        bar  = pygame.Rect(L.MARGIN, 470, L.W - 2 * L.MARGIN, 6)
        pygame.draw.rect(screen, C.BG_PANEL, bar, border_radius=3)
        fill = pygame.Rect(L.MARGIN, 470,
                           int((L.W - 2 * L.MARGIN) * frac), 6)
        pygame.draw.rect(screen, C.ACCENT, fill, border_radius=3)

        t = F.body_small.render(
            f"Iniciando em {remaining:.0f}s  —  pressione qualquer botão para iniciar já",
            True, C.TEXT_MUTED,
        )
        screen.blit(t, t.get_rect(center=(L.W // 2, 490)))

        pygame.display.flip()
        clock.tick(config.FPS)


# ------------------------------------------------------------------ #
# Loop principal                                                      #
# ------------------------------------------------------------------ #

def main() -> None:
    # --- Sessão e log ---
    session_id    = app_logger.make_session_id()
    app_logger.setup_logging(session_id)

    import logging
    log = logging.getLogger(__name__)
    log.info(f"Factory check iniciado. Sessão: {session_id}")

    serial_number = _read_serial_number()
    log.info(f"Número de série: {serial_number}")

    # --- DSP ---
    dsp_state   = DspState()
    event_queue: queue.Queue = queue.Queue()
    dsp_reader  = DspReader(
        port=config.SERIAL_PORT,
        baud=config.SERIAL_BAUD,
        state=dsp_state,
        event_queue=event_queue,
    )
    dsp_reader.start()
    log.info("DspReader iniciado.")

    # --- CheckResult ---
    check_result = CheckResult(serial_number=serial_number)

    # --- Fases ---
    # Phase9 recebe check_result por referência —
    # estará totalmente populado quando on_enter() for chamado.
    phases = [
        Phase1Auto(),
        Phase2Buttons(),
        Phase3Emergency(),
        Phase4Door(),
        Phase5Contactor(reader=dsp_reader),
        Phase6Fan(reader=dsp_reader),
        Phase7Inspections(),
        Phase8NetworkLoad(),
        Phase9Summary(check_result=check_result, session_id=session_id),
    ]

    # --- Pygame ---
    pygame.init()
    flags  = pygame.FULLSCREEN if config.FULLSCREEN else 0
    screen = pygame.display.set_mode(
        (config.SCREEN_WIDTH, config.SCREEN_HEIGHT), flags
    )
    pygame.display.set_caption("Factory Check")
    pygame.mouse.set_visible(False)
    clock  = pygame.time.Clock()
    F.init()   # carrega fontes após pygame.init()

    log.info("Pygame inicializado.")

    # --- Tela de boot ---
    _show_boot_screen(screen, clock, serial_number, event_queue)

    # --- Loop principal ---
    current_idx   = 0
    current_phase = phases[current_idx]
    current_phase.on_enter(dsp_state)
    running = True

    while running:
        # Eventos pygame (ESC para sair em desenvolvimento)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

        # Drena fila de ButtonEvents do DSP
        btn_events = []
        while True:
            try:
                btn_events.append(event_queue.get_nowait())
            except queue.Empty:
                break

        # Atualiza fase atual
        status = current_phase.update(dsp_state, btn_events)

        # Renderiza
        renderer.render(screen, current_phase)
        pygame.display.flip()
        clock.tick(config.FPS)

        # Transição de fase
        if status != Status.RUNNING:
            phase_result = current_phase.on_exit()
            check_result.add_phase(phase_result)
            log.info(
                f"Fase {current_phase.phase_id} encerrada: "
                f"{phase_result.status.name}"
            )

            # Erro fatal: DSP não respondeu na Fase 1
            if current_phase.phase_id == 1 and status == Status.FAIL:
                log.error("Erro fatal: DSP não respondeu. Encerrando check.")
                _show_fatal_dsp_error(screen, clock)
                running = False
                break

            # Avança para a próxima fase
            current_idx += 1
            if current_idx >= len(phases):
                running = False
                break

            current_phase = phases[current_idx]
            current_phase.on_enter(dsp_state)
            log.info(f"Iniciando Fase {current_phase.phase_id}: {current_phase.name}")

    # --- Encerramento ---
    log.info("Encerrando factory check.")
    dsp_reader.stop()
    pygame.quit()
    log.info(
        f"Check encerrado. Resultado: "
        f"{'APROVADO' if check_result.approved else 'REPROVADO'}"
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
