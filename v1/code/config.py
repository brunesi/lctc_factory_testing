from pathlib import Path

# ------------------------------------------------------------------ #
# Entrada DSP via journal                                             #
# ------------------------------------------------------------------ #

DSP_JOURNAL_SERVICE = "chargepoint.service"
DSP_JOURNAL_SINCE   = "30 seconds ago"
DSP_JOURNAL_PATTERN = "04 64"

# Leitor RFID — não usado no factory check atual,
# registrado aqui para referência futura
SERIAL_RFID = "/dev/ttyFTDI_RFID"

# ------------------------------------------------------------------ #
# Display                                                             #
# ------------------------------------------------------------------ #

SCREEN_WIDTH  = 600
SCREEN_HEIGHT = 1024
FPS           = 30
FULLSCREEN    = True    # False para janela (desenvolvimento)

# ------------------------------------------------------------------ #
# Arquivo de número de série                                          #
# ------------------------------------------------------------------ #

SERIAL_NUMBER_FILE = "/etc/factory/serial.conf"

# ------------------------------------------------------------------ #
# Log                                                                 #
# ------------------------------------------------------------------ #

LOG_INTERNAL_DIR = str(Path.home() / "factory_check_logs")
LOG_PENDRIVE_DIR = "/media/pendrive/log/factory_check"

# ------------------------------------------------------------------ #
# Timeouts (segundos)                                                 #
# ------------------------------------------------------------------ #

TIMEOUT_DSP_ALIVE        = 12    # aguarda 2 leituras do posix (~10s + margem)
TIMEOUT_BUTTON_TEST      = 10    # por botão na fase 2
TIMEOUT_PHASE_AUTOADVANCE = 5    # avanço automático após resumo da fase 1
TIMEOUT_LOAD_TEST        = 60    # aguarda conexão de veículo/maleta
TIMEOUT_EMERGENCY_STEP   = 15   # por passo na fase da botoeira


# ------------------------------------------------------------------ #
# Fase 1 — estabilização das leituras DSP                             #
# ------------------------------------------------------------------ #

# Após detectar que o POSIX do DSP incrementou, a Fase 1 não deve
# congelar imediatamente a primeira amostra recebida. Alguns campos do
# megapayload podem aparecer zerados por poucos ciclos no início da
# comunicação, embora o log posterior já esteja correto.

# ------------------------------------------------------------------ #
# Temperaturas                                                        #
# ------------------------------------------------------------------ #

TEMP_MIN = 0
TEMP_MAX = 100

# ------------------------------------------------------------------ #
# Rede                                                                #
# ------------------------------------------------------------------ #

PING_TELTONIKA   = "3.1.1.1"
PING_GOOGLE_DNS  = "8.8.8.8"
PING_CLOUDFLARE  = "1.1.1.1"
PING_GOOGLE_HOST = "google.com"
PING_CF_HOST     = "cloudflare.com"
PING_TIMEOUT_S   = 5
PING_COUNT       = 2

# ------------------------------------------------------------------ #
# Inspeções visuais                                                   #
# ------------------------------------------------------------------ #

INSPECTIONS_FILE = "factory_inspections.yaml"

# ------------------------------------------------------------------ #
# Charge states                                                       #
# ------------------------------------------------------------------ #

CHARGE_STATE_CCS_CONNECTED    = 0x32
CHARGE_STATE_CHADEMO_CONNECTED = 0x81
