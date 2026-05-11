"""
ui/theme.py

Tema visual do factory check — kiosk industrial, 600×1024 portrait.

Estética: terminal de controle. Fundo escuro profundo, tipografia
técnica, status semafórico sem ambiguidade. Funcional e limpo.

Uso:
    from ui.theme import Theme
    t = Theme()
    t.init_fonts()   # chamar após pygame.init()
"""

import pygame


# ------------------------------------------------------------------ #
# Paleta de cores                                                     #
# ------------------------------------------------------------------ #

class Color:
    # Fundos
    BG              = (13,  17,  23)    # #0d1117 — fundo principal
    BG_PANEL        = (22,  27,  34)    # #161b22 — painéis / cards
    BG_HEADER       = (30,  37,  48)    # #1e2530 — cabeçalho de fase

    # Texto
    TEXT_PRIMARY    = (230, 237, 243)   # #e6edf3 — texto principal
    TEXT_SECONDARY  = (139, 148, 158)   # #8b949e — texto secundário
    TEXT_MUTED      = ( 72,  79,  88)   # #484f58 — texto apagado

    # Status semafórico
    PASS            = ( 63, 185,  80)   # #3fb950 — verde
    FAIL            = (248,  81,  73)   # #f85149 — vermelho
    SKIP            = (210, 153,  34)   # #d29922 — âmbar
    PENDING         = ( 72,  79,  88)   # #484f58 — cinza
    RUNNING         = ( 88, 166, 255)   # #58a6ff — azul

    # Acentos
    ACCENT          = ( 88, 166, 255)   # #58a6ff — azul primário
    ACCENT_DIM      = ( 31,  53,  82)   # #1f3552 — azul escuro

    # Bordas
    BORDER          = ( 48,  54,  61)   # #30363d
    BORDER_BRIGHT   = ( 72,  79,  88)   # #484f58

    # Alerta
    ALERT_BG        = ( 56,  23,  23)   # fundo de alerta vermelho
    ALERT_BORDER    = (248,  81,  73)

    # Fundo do resultado geral
    APPROVED_BG     = ( 14,  43,  18)   # verde escuro
    REPROVADO_BG    = ( 56,  23,  23)   # vermelho escuro


# ------------------------------------------------------------------ #
# Layout — zonas fixas em pixels (600×1024)                          #
# ------------------------------------------------------------------ #

class Layout:
    W = 600
    H = 1024

    MARGIN          = 24    # margem lateral e vertical padrão
    PADDING         = 16    # padding interno de painéis

    # Cabeçalho de fase
    HEADER_Y        = 0
    HEADER_H        = 72
    HEADER_BOTTOM   = HEADER_Y + HEADER_H

    # Barra de progresso / countdown (logo abaixo do header)
    BAR_Y           = HEADER_BOTTOM
    BAR_H           = 8
    BAR_BOTTOM      = BAR_Y + BAR_H

    # Área de conteúdo principal
    CONTENT_Y       = BAR_BOTTOM + MARGIN
    FOOTER_H        = 80
    FOOTER_Y        = H - FOOTER_H
    CONTENT_H       = FOOTER_Y - CONTENT_Y - MARGIN
    CONTENT_BOTTOM  = CONTENT_Y + CONTENT_H

    # Área de conteúdo como rect
    CONTENT_RECT    = pygame.Rect(MARGIN, CONTENT_Y, W - 2 * MARGIN, CONTENT_H)

    # Rodapé (legenda de botões)
    FOOTER_RECT     = pygame.Rect(0, FOOTER_Y, W, FOOTER_H)

    # Separador de itens
    ITEM_H          = 52    # altura de cada linha de resultado
    ITEM_GAP        = 4     # espaço entre linhas


# ------------------------------------------------------------------ #
# Fontes                                                              #
# ------------------------------------------------------------------ #

class Fonts:
    """
    Carregado via init_fonts() após pygame.init().
    Usa fontes do sistema Ubuntu 16.04 com fallbacks seguros.
    """
    phase_title:  pygame.font.Font = None   # cabeçalho de fase
    heading:      pygame.font.Font = None   # títulos de seção
    body:         pygame.font.Font = None   # instrução principal
    body_small:   pygame.font.Font = None   # instrução secundária
    mono:         pygame.font.Font = None   # valores numéricos / medidos
    mono_small:   pygame.font.Font = None   # valores secundários
    legend:       pygame.font.Font = None   # rodapé de botões
    result_large: pygame.font.Font = None   # APROVADO / REPROVADO

    # Candidatos por categoria (pygame tenta na ordem, usa o primeiro disponível)
    _SANS  = ["Ubuntu", "DejaVu Sans", "Liberation Sans", "FreeSans", None]
    _MONO  = ["Ubuntu Mono", "DejaVu Sans Mono", "Liberation Mono", "FreeMono", None]

    @classmethod
    def init(cls) -> None:
        cls.phase_title  = cls._load(_FontSpec(_SANS=cls._SANS, size=30, bold=True))
        cls.heading      = cls._load(_FontSpec(_SANS=cls._SANS, size=24, bold=True))
        cls.body         = cls._load(_FontSpec(_SANS=cls._SANS, size=26))
        cls.body_small   = cls._load(_FontSpec(_SANS=cls._SANS, size=21))
        cls.mono         = cls._load(_FontSpec(_SANS=cls._MONO, size=24, bold=True))
        cls.mono_small   = cls._load(_FontSpec(_SANS=cls._MONO, size=19))
        cls.legend       = cls._load(_FontSpec(_SANS=cls._SANS, size=19))
        cls.result_large = cls._load(_FontSpec(_SANS=cls._SANS, size=44, bold=True))

    @classmethod
    def _load(cls, spec: "_FontSpec") -> pygame.font.Font:
        for name in spec.candidates:
            try:
                font = pygame.font.SysFont(name, spec.size, bold=spec.bold)
                return font
            except Exception:
                continue
        # Fallback absoluto — fonte padrão do pygame
        return pygame.font.Font(None, spec.size)


class _FontSpec:
    """Agrupa parâmetros para carregar uma fonte."""
    def __init__(self, _SANS: list, size: int, bold: bool = False):
        self.candidates = _SANS
        self.size       = size
        self.bold       = bold


# ------------------------------------------------------------------ #
# Mapeamento status → cor                                             #
# ------------------------------------------------------------------ #

STATUS_COLOR = {
    "PASS":    Color.PASS,
    "FAIL":    Color.FAIL,
    "SKIP":    Color.SKIP,
    "PENDING": Color.PENDING,
    "RUNNING": Color.RUNNING,
}


def status_color(status) -> tuple:
    """Aceita Status enum ou string."""
    key = status.name if hasattr(status, "name") else str(status)
    return STATUS_COLOR.get(key, Color.PENDING)


def status_label(status) -> str:
    """Símbolo curto para exibição em linha."""
    key = status.name if hasattr(status, "name") else str(status)
    return {
        "PASS":    "✓  PASS",
        "FAIL":    "✗  FAIL",
        "SKIP":    "–  SKIP",
        "PENDING": "·  ···",
        "RUNNING": "»  ···",
    }.get(key, "?")


# ------------------------------------------------------------------ #
# Instância global (importada pelos módulos de UI)                   #
# ------------------------------------------------------------------ #

# Uso: from ui.theme import C, L, F, status_color, status_label
# Após pygame.init(): Fonts.init()
C = Color
L = Layout
F = Fonts
