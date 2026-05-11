"""
ui/renderer.py

Renderizador do factory check.

Estrutura:
  Camada 1 — Primitivas:   _text, _wrap_text, _rect, _line
  Camada 2 — Componentes:  _header, _footer, _bar, _item_row,
                            _instruction_box, _state_indicator,
                            _readings_table
  Camada 3 — Por fase:     _render_phase1 … _render_phase9
  Pública:                  render(screen, phase, check_result)
"""

import pygame
from ui.theme import C, L, F, status_color, status_label
from result import Status


# ================================================================== #
# CAMADA 1 — PRIMITIVAS                                              #
# ================================================================== #

def _text(screen, font, text: str, color, x: int, y: int,
          anchor: str = "topleft") -> pygame.Rect:
    """Renderiza uma linha de texto. anchor: topleft|center|topright."""
    surf = font.render(text, True, color)
    rect = surf.get_rect()
    setattr(rect, anchor, (x, y))
    screen.blit(surf, rect)
    return rect


def _wrap_text(screen, font, text: str, color,
               x: int, y: int, max_width: int,
               line_gap: int = 6) -> int:
    """
    Renderiza texto com quebra de linha automática.
    Retorna o y final após o último linha.
    Suporta '\\n' explícito no texto.
    """
    paragraphs = text.split("\n")
    cy = y
    for para in paragraphs:
        words  = para.split()
        line   = ""
        for word in words:
            test = (line + " " + word).strip()
            if font.size(test)[0] <= max_width:
                line = test
            else:
                if line:
                    _text(screen, font, line, color, x, cy)
                    cy += font.get_linesize() + line_gap
                line = word
        if line:
            _text(screen, font, line, color, x, cy)
            cy += font.get_linesize() + line_gap
    return cy


def _rect(screen, color, rect: pygame.Rect,
          radius: int = 6, border: int = 0,
          border_color=None) -> None:
    """Retângulo com cantos arredondados, opcional borda."""
    pygame.draw.rect(screen, color, rect, border_radius=radius)
    if border and border_color:
        pygame.draw.rect(screen, border_color, rect,
                         width=border, border_radius=radius)


def _hline(screen, color, y: int, x1: int = 0,
           x2: int = L.W, width: int = 1) -> None:
    pygame.draw.line(screen, color, (x1, y), (x2, y), width)


# ================================================================== #
# CAMADA 2 — COMPONENTES                                             #
# ================================================================== #

def _header(screen, phase_id: int, phase_name: str) -> None:
    """Faixa superior com ID e nome da fase."""
    _rect(screen, C.BG_HEADER, pygame.Rect(0, L.HEADER_Y, L.W, L.HEADER_H))
    _hline(screen, C.BORDER_BRIGHT, L.HEADER_BOTTOM)

    id_text = f"FASE {phase_id:02d}"
    _text(screen, F.mono_small, id_text, C.ACCENT,
          L.MARGIN, L.HEADER_Y + 12)
    _text(screen, F.phase_title, phase_name.upper(), C.TEXT_PRIMARY,
          L.MARGIN, L.HEADER_Y + 34)


def _footer(screen, legend: str) -> None:
    """Rodapé com legenda dos botões."""
    _hline(screen, C.BORDER, L.FOOTER_Y)
    _rect(screen, C.BG_PANEL, L.FOOTER_RECT, radius=0)
    if legend:
        _text(screen, F.legend, legend, C.TEXT_SECONDARY,
              L.W // 2, L.FOOTER_Y + L.FOOTER_H // 2,
              anchor="center")


def _progress_bar(screen, fraction: float,
                  color=None, bg=None) -> None:
    """
    Barra fina abaixo do header.
    fraction: 0.0 a 1.0 (preenchimento da esquerda para direita).
    Útil para countdown (fraction = restante/total).
    """
    color = color or C.ACCENT
    bg    = bg or C.BG_PANEL
    bar   = pygame.Rect(0, L.BAR_Y, L.W, L.BAR_H)
    _rect(screen, bg, bar, radius=0)
    if fraction > 0:
        fill = pygame.Rect(0, L.BAR_Y, int(L.W * min(fraction, 1.0)), L.BAR_H)
        _rect(screen, color, fill, radius=0)


def _item_row(screen, y: int, name: str, status,
              measured: str = "", note: str = "") -> int:
    """
    Linha de resultado de item.
    Retorna o y da próxima linha.
    """
    row = pygame.Rect(L.MARGIN, y, L.W - 2 * L.MARGIN, L.ITEM_H)
    _rect(screen, C.BG_PANEL, row, radius=4)

    # Badge de status (retângulo colorido à esquerda)
    badge_w = 6
    badge   = pygame.Rect(L.MARGIN, y, badge_w, L.ITEM_H)
    _rect(screen, status_color(status), badge, radius=0)

    # Label de status
    s_label = status_label(status)
    s_color = status_color(status)
    _text(screen, F.mono_small, s_label, s_color,
          L.MARGIN + badge_w + 10, y + 8)

    # Nome do item
    name_x = L.MARGIN + badge_w + 110
    _text(screen, F.body_small, _truncate(name, F.body_small, 280),
          C.TEXT_PRIMARY, name_x, y + 8)

    # Valor medido (direita)
    if measured:
        _text(screen, F.mono_small, _truncate(measured, F.mono_small, 160),
              C.TEXT_SECONDARY, L.W - L.MARGIN, y + 8,
              anchor="topright")

    # Nota de falha (linha abaixo, se houver espaço)
    if note and status == Status.FAIL:
        _text(screen, F.body_small,
              _truncate(note, F.body_small, L.W - 2 * L.MARGIN - badge_w - 10),
              C.TEXT_MUTED, L.MARGIN + badge_w + 10, y + 30)

    return y + L.ITEM_H + L.ITEM_GAP


def _instruction_box(screen, y: int,
                     title: str, body: str,
                     sub: str = "") -> int:
    """
    Painel de instrução ao operador.
    Retorna o y logo abaixo do painel.
    """
    x       = L.MARGIN
    width   = L.W - 2 * L.MARGIN
    pad     = L.PADDING

    # Calcula altura necessária
    title_h = F.heading.get_linesize() + pad
    body_lines = _count_wrap_lines(F.body, body, width - 2 * pad)
    body_h  = body_lines * (F.body.get_linesize() + 6) + pad
    sub_h   = (F.body_small.get_linesize() + 6) if sub else 0
    total_h = title_h + body_h + sub_h + 2 * pad

    panel = pygame.Rect(x, y, width, total_h)
    _rect(screen, C.BG_PANEL, panel, radius=8,
          border=1, border_color=C.BORDER_BRIGHT)

    cy = y + pad
    if title:
        _text(screen, F.heading, title, C.ACCENT, x + pad, cy)
        cy += F.heading.get_linesize() + pad

    cy = _wrap_text(screen, F.body, body, C.TEXT_PRIMARY,
                    x + pad, cy, width - 2 * pad)

    if sub:
        cy += 4
        _wrap_text(screen, F.body_small, sub, C.TEXT_SECONDARY,
                   x + pad, cy, width - 2 * pad)
        cy += F.body_small.get_linesize() + 6

    return y + total_h + L.MARGIN


def _state_indicator(screen, y: int,
                     label: str, active: bool,
                     active_color=None, inactive_color=None) -> None:
    """
    Indicador circular de estado (ex: botoeira, porta).
    active=True → colorido. active=False → apagado.
    """
    active_color   = active_color   or C.FAIL
    inactive_color = inactive_color or C.PASS
    color  = active_color if active else inactive_color
    cx     = L.W // 2
    radius = 28
    pygame.draw.circle(screen, color, (cx, y + radius), radius)
    pygame.draw.circle(screen, C.BORDER_BRIGHT, (cx, y + radius), radius, 2)
    _text(screen, F.body_small, label, C.TEXT_PRIMARY,
          cx, y + 2 * radius + 10, anchor="center")


def _readings_table(screen, y: int, readings: dict,
                    rno_alert: bool = False) -> int:
    """
    Tabela de leituras elétricas em tempo real.
    Retorna y abaixo da tabela.
    """
    x     = L.MARGIN
    width = L.W - 2 * L.MARGIN
    row_h = 44

    for i, (label, value) in enumerate(readings.items()):
        bg    = C.BG_PANEL if i % 2 == 0 else C.BG_HEADER
        alert = rno_alert and label == "Rno"
        bg    = C.ALERT_BG if alert else bg
        row   = pygame.Rect(x, y, width, row_h)
        _rect(screen, bg, row, radius=4)

        lbl_color = C.ALERT_BORDER if alert else C.TEXT_SECONDARY
        val_color = C.ALERT_BORDER if alert else C.ACCENT

        _text(screen, F.body_small, label, lbl_color, x + L.PADDING, y + 12)
        _text(screen, F.mono, value, val_color,
              x + width - L.PADDING, y + 10, anchor="topright")

        if alert:
            _text(screen, F.body_small, "⚠ verificar isolação",
                  C.ALERT_BORDER, x + L.PADDING, y + 26)

        y += row_h + 2

    return y + L.MARGIN


def _button_row_visual(screen, y: int, active_button: int) -> None:
    """
    Representação visual dos 4 botões físicos.
    O botão ativo é destacado.
    """
    total_w = L.W - 2 * L.MARGIN
    btn_w   = (total_w - 3 * 8) // 4   # 4 botões, 3 gaps de 8px
    btn_h   = 48
    x_start = L.MARGIN

    for i in range(1, 5):
        bx      = x_start + (i - 1) * (btn_w + 8)
        btn_r   = pygame.Rect(bx, y, btn_w, btn_h)
        active  = (i == active_button)
        bg      = C.ACCENT      if active else C.BG_PANEL
        border  = C.ACCENT      if active else C.BORDER
        label_c = C.BG          if active else C.TEXT_SECONDARY
        _rect(screen, bg, btn_r, radius=6, border=2, border_color=border)
        _text(screen, F.mono_small, f"B{i}", label_c,
              bx + btn_w // 2, y + btn_h // 2, anchor="center")


def _overall_result_banner(screen, approved: bool) -> None:
    """Faixa grande de APROVADO / REPROVADO."""
    bg    = C.APPROVED_BG if approved else C.REPROVADO_BG
    color = C.PASS        if approved else C.FAIL
    label = "APROVADO"    if approved else "REPROVADO"
    band  = pygame.Rect(0, L.HEADER_BOTTOM + L.BAR_H,
                        L.W, 90)
    _rect(screen, bg, band, radius=0)
    _hline(screen, color, band.top,  width=3)
    _hline(screen, color, band.bottom, width=3)
    _text(screen, F.result_large, label, color,
          L.W // 2, band.top + 22, anchor="center")


# ================================================================== #
# CAMADA 3 — RENDERIZADORES POR FASE                                 #
# ================================================================== #

def _render_phase1(screen, phase) -> None:
    from phases.phase1_auto import _SubStep
    _header(screen, phase.phase_id, phase.phase_name)

    in_advance = phase._sub_step == _SubStep.AUTO_ADVANCE
    if in_advance:
        total = __import__("config").TIMEOUT_PHASE_AUTOADVANCE
        frac  = phase.countdown / total if total else 0
        _progress_bar(screen, frac, color=C.ACCENT)
    else:
        _progress_bar(screen, 0)

    y = L.CONTENT_Y

    # Instrução atual
    y = _instruction_box(screen, y,
                         title="",
                         body=phase.current_check)

    # Lista de resultados acumulados
    items = phase._result.items
    for item in items:
        if y + L.ITEM_H > L.CONTENT_BOTTOM:
            break
        y = _item_row(screen, y,
                      item.name, item.status,
                      item.measured, item.note)

    # Rodapé
    legend = "Pressione qualquer botão para avançar" if in_advance else ""
    _footer(screen, legend)


def _render_phase2(screen, phase) -> None:
    _header(screen, phase.phase_id, phase.phase_name)

    total = __import__("config").TIMEOUT_BUTTON_TEST
    frac  = phase.countdown / total if total else 0
    _progress_bar(screen, frac,
                  color=C.RUNNING if frac > 0.3 else C.FAIL)

    y = L.CONTENT_Y

    # Progresso
    done  = phase._current_index
    total_btns = len(phase._buttons_to_test)
    _text(screen, F.mono_small,
          f"Botão  {done + 1}  de  {total_btns}",
          C.TEXT_SECONDARY, L.W // 2, y, anchor="center")
    y += F.mono_small.get_linesize() + L.MARGIN

    # Instrução principal
    from phases.phase2_buttons import BUTTON_LABELS
    desc = BUTTON_LABELS.get(phase.current_button, f"Botão {phase.current_button}")
    y = _instruction_box(
        screen, y,
        title=f"Pressione o  BOTÃO {phase.current_button}",
        body=desc,
        sub=f"Tempo restante: {phase.countdown:.0f}s",
    )

    # Visual dos botões físicos
    _button_row_visual(screen, y, active_button=phase.current_button)
    y += 48 + L.MARGIN + L.MARGIN

    # Resultados anteriores
    for item in phase._result.items:
        if y + L.ITEM_H > L.CONTENT_BOTTOM:
            break
        y = _item_row(screen, y, item.name, item.status, item.measured)

    _footer(screen, "")


def _render_phase3(screen, phase) -> None:
    _render_three_step(
        screen, phase,
        state_label="PRESSIONADA" if phase.em_state else "LIBERADA",
        state_active=bool(phase.em_state),
        active_color=C.FAIL,
        inactive_color=C.PASS,
        indicator_label="Botoeira",
    )


def _render_phase4(screen, phase) -> None:
    _render_three_step(
        screen, phase,
        state_label="ABERTA" if phase.door_open else "FECHADA",
        state_active=phase.door_open,
        active_color=C.SKIP,
        inactive_color=C.PASS,
        indicator_label="Porta",
    )


def _render_three_step(screen, phase,
                       state_label, state_active,
                       active_color, inactive_color,
                       indicator_label) -> None:
    """Layout comum para Fases 3 e 4."""
    _header(screen, phase.phase_id, phase.phase_name)

    total = __import__("config").TIMEOUT_EMERGENCY_STEP
    frac  = phase.countdown / total if total else 0
    _progress_bar(screen, frac,
                  color=C.RUNNING if frac > 0.25 else C.FAIL)

    y = L.CONTENT_Y

    y = _instruction_box(
        screen, y,
        title=phase.step_label,
        body=phase.instruction,
        sub=phase.sub_instruction
            + f"  ({phase.countdown:.0f}s)",
    )

    # Indicador de estado
    _state_indicator(screen, y, state_label,
                     state_active, active_color, inactive_color)
    y += 80 + L.MARGIN

    # Resultados anteriores
    for item in phase._result.items:
        if y + L.ITEM_H > L.CONTENT_BOTTOM:
            break
        y = _item_row(screen, y, item.name, item.status, item.measured)

    _footer(screen, "")


def _render_phase5(screen, phase) -> None:
    _header(screen, phase.phase_id, phase.phase_name)
    _progress_bar(screen, 0)

    y = L.CONTENT_Y
    y = _instruction_box(screen, y,
                         title=phase.step_label,
                         body=phase.instruction)

    for item in phase._result.items:
        if y + L.ITEM_H > L.CONTENT_BOTTOM:
            break
        y = _item_row(screen, y, item.name, item.status,
                      item.measured, item.note)

    _footer(screen, phase.legend)


def _render_phase6(screen, phase) -> None:
    _header(screen, phase.phase_id, phase.phase_name)
    _progress_bar(screen, 0)

    y = L.CONTENT_Y
    y = _instruction_box(screen, y, title="", body=phase.instruction)

    # Indicador do campo fan_status do frame
    fan_on = phase.fan_status == 1
    label  = "LIGADO" if fan_on else "DESLIGADO"
    _state_indicator(screen, y, f"fan_status = {label}",
                     active=fan_on,
                     active_color=C.PASS,
                     inactive_color=C.TEXT_MUTED)
    y += 80 + L.MARGIN

    # Aviso TODO
    note = "Nota: comando de ventilador ainda não implementado no DSP."
    _wrap_text(screen, F.body_small, note, C.TEXT_MUTED,
               L.MARGIN, y, L.W - 2 * L.MARGIN)

    _footer(screen, phase.legend)


def _render_phase7(screen, phase) -> None:
    _header(screen, phase.phase_id, phase.phase_name)
    _progress_bar(screen, 0)

    y = L.CONTENT_Y

    # Progresso
    _text(screen, F.mono_small, phase.progress,
          C.TEXT_SECONDARY, L.W // 2, y, anchor="center")
    y += F.mono_small.get_linesize() + L.MARGIN

    # Pergunta atual
    if phase.current_question:
        y = _instruction_box(screen, y,
                             title="Inspeção visual",
                             body=phase.current_question)

    # Resultados anteriores (compactos)
    for item in phase._result.items:
        if y + L.ITEM_H > L.CONTENT_BOTTOM:
            break
        y = _item_row(screen, y, item.name, item.status)

    _footer(screen, phase.legend)


def _render_phase8(screen, phase) -> None:
    from phases.phase8_network_load import _SubStep
    _header(screen, phase.phase_id, phase.phase_name)

    sub = phase._sub_step

    if sub == _SubStep.LOAD_CONNECTING:
        total = __import__("config").TIMEOUT_LOAD_TEST
        frac  = phase.countdown / total if total else 0
        _progress_bar(screen, frac, color=C.RUNNING)
    else:
        _progress_bar(screen, 0)

    y = L.CONTENT_Y

    if sub == _SubStep.NETWORK_CHECKS:
        y = _instruction_box(screen, y, title="Verificando rede...",
                             body=phase.current_check)
        for item in phase._result.items:
            if y + L.ITEM_H > L.CONTENT_BOTTOM:
                break
            y = _item_row(screen, y, item.name, item.status,
                          item.measured, item.note)

    elif sub == _SubStep.LOAD_MENU:
        # Sumário de rede
        net_items = [i for i in phase._result.items
                     if i.name.startswith("8.")]
        for item in net_items[:5]:
            if y + L.ITEM_H > L.CONTENT_BOTTOM - 120:
                break
            y = _item_row(screen, y, item.name, item.status, item.measured)

        y += L.MARGIN
        y = _instruction_box(screen, y, title="Testes de carga",
                             body="Selecione o conector a testar,\n"
                                  "ou encerre a fase.")

    elif sub == _SubStep.LOAD_CONNECTING:
        y = _instruction_box(screen, y,
                             title="Aguardando conexão...",
                             body=phase.current_check,
                             sub=f"Timeout: {phase.countdown:.0f}s")

    elif sub == _SubStep.LOAD_ACTIVE:
        y = _instruction_box(screen, y,
                             title=phase.current_check,
                             body="Leituras em tempo real:")
        if phase.live_readings:
            y = _readings_table(screen, y, phase.live_readings,
                                rno_alert=phase.rno_alert)

    _footer(screen, phase.legend)


def _render_phase9(screen, phase) -> None:
    _header(screen, phase.phase_id, phase.phase_name)
    _progress_bar(screen, 0)
    _overall_result_banner(screen, phase.overall_approved)

    y = L.CONTENT_Y + 100   # compensar o banner

    # Resultado por fase
    for ps in phase.phase_summaries:
        if y + L.ITEM_H > L.CONTENT_BOTTOM:
            break
        y = _item_row(screen, y,
                      f"Fase {ps['id']:02d} — {ps['name']}",
                      ps["status"])

    # Status do log
    y = max(y, L.CONTENT_BOTTOM - 60)
    log_parts = []
    if phase.log_saved_internal:
        log_parts.append("Log: disco interno ✓")
    if phase.log_saved_pendrive:
        log_parts.append("pendrive ✓")
    if not phase.log_saved_internal:
        log_parts.append("Log: FALHA ao salvar ✗")

    if log_parts:
        _text(screen, F.mono_small, "  |  ".join(log_parts),
              C.TEXT_SECONDARY, L.W // 2,
              L.CONTENT_BOTTOM - 30, anchor="center")

    _footer(screen, phase.legend)


# ================================================================== #
# DESPACHO PRINCIPAL                                                 #
# ================================================================== #

_RENDERERS = {
    1: _render_phase1,
    2: _render_phase2,
    3: _render_phase3,
    4: _render_phase4,
    5: _render_phase5,
    6: _render_phase6,
    7: _render_phase7,
    8: _render_phase8,
    9: _render_phase9,
}


def render(screen: pygame.Surface, phase) -> None:
    """
    Ponto de entrada público.
    Limpa a tela e renderiza a fase atual.
    """
    screen.fill(C.BG)
    renderer = _RENDERERS.get(phase.phase_id)
    if renderer:
        renderer(screen, phase)
    else:
        # Fase desconhecida — tela de fallback
        _header(screen, phase.phase_id, phase.phase_name)
        _text(screen, F.body, "Renderizador não implementado.",
              C.TEXT_MUTED, L.W // 2, L.H // 2, anchor="center")
        _footer(screen, "")


# ================================================================== #
# UTILITÁRIOS INTERNOS                                               #
# ================================================================== #

def _truncate(text: str, font: pygame.font.Font, max_w: int) -> str:
    """Trunca texto com '…' se ultrapassar max_w pixels."""
    if font.size(text)[0] <= max_w:
        return text
    while text and font.size(text + "…")[0] > max_w:
        text = text[:-1]
    return text + "…"


def _count_wrap_lines(font: pygame.font.Font,
                      text: str, max_width: int) -> int:
    """Conta quantas linhas wrap_text precisará."""
    count = 0
    for para in text.split("\n"):
        words = para.split()
        line  = ""
        for word in words:
            test = (line + " " + word).strip()
            if font.size(test)[0] <= max_width:
                line = test
            else:
                if line:
                    count += 1
                line = word
        if line:
            count += 1
    return max(count, 1)
