"""
dsp/commands.py

Placeholders temporários para comandos ao DSP.

A entrada de telemetria foi migrada da serial para leitura do journal do
chargepoint.service. A saída de comandos será redefinida na próxima etapa.

Os nomes das funções foram mantidos para preservar a interface usada pelas
fases 5 e 6.
"""


def contactor_close(reader) -> bool:
    """Placeholder: fecha a contatora."""
    pass


def contactor_open(reader) -> bool:
    """Placeholder: abre a contatora."""
    pass


def fan_on(reader) -> bool:
    """Placeholder: liga o ventilador."""
    pass


def fan_off(reader) -> bool:
    """Placeholder: desliga o ventilador."""
    pass
