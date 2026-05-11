# 05 — Pendências

Backlog priorizado. P1 = bloqueia uso em produção. P2 = importante. P3 = melhoria futura.

---

## P1 — Bloqueantes para uso em produção

### P1.1 — Testar parsing do frame `04 64` com serial real
Validar que o parser lida corretamente com o stream real do DSP, incluindo frames parciais, ruído na linha e reconexão após queda.

### P1.2 — Validar payloads dos comandos de contatora
Os bytes `0x0C / [0x01]` e `0x0C / [0x02]` foram extraídos do código existente (`send_contactor_command`). Confirmar com teste em hardware que a contatora responde corretamente.

### P1.3 — Testar renderização em tela física 600×1024
Verificar quebras de linha, tamanho de fontes, overflow de itens em listas longas. Ajustar constantes em `ui/theme.py` conforme necessário.

### P1.4 — Implementar processo de deploy do `serial.conf`
Definir e documentar como o arquivo `/etc/factory/serial.conf` é gerado e gravado junto com a imagem Clonezilla para cada rack.

---

## P2 — Importantes

### P2.1 — Implementar fan_on / fan_off no DSP
Definir o protocolo de comando para controle manual do ventilador e implementar em `dsp/commands.py`. Atualmente `fan_on` e `fan_off` retornam `False` com warning.

### P2.2 — Mock do DSP para desenvolvimento sem hardware
Script Python que simula o stream serial do DSP (`04 64 ...`) via porta virtual. Permite desenvolver e testar sem hardware conectado. Ver seção de sugestão abaixo.

### P2.3 — Teste de rede com IP de destino configurável
O IP do Teltonika (`3.1.1.1`) está em `config.py`. Confirmar que é o correto para o ambiente de fábrica do parceiro.

### P2.4 — Revisar orientação dos botões em hardware
O mapeamento `4321[0]=B4 ... 4321[3]=B1` foi inferido da estrutura do frame. Confirmar com teste manual que cada botão físico corresponde ao índice correto.

### P2.5 — Adicionar item 1.9 (módulos de potência) à Fase 7
Conforme decidido: check visual dos displays dos módulos. Adicionar à `factory_inspections.yaml`:
```yaml
- "Módulos de potência: displays sem códigos de falha ativos?"
```

### P2.6 — Scroll em listas longas de itens
A Fase 9 (sumário) pode ter mais itens do que cabem na tela. Implementar scroll básico via B3/B4 ou paginação automática.

---

## P3 — Melhorias futuras

### P3.1 — Log em formato Markdown
Conforme discutido: o log atual é texto plano. Formatar em Markdown para facilitar leitura e eventual integração com sistemas do parceiro.

### P3.2 — Exportação de QR code com resultado
Gerar QR code no sumário final codificando serial + resultado + timestamp. Operador fotografa com celular para rastreabilidade rápida.

### P3.3 — Política de falha configurável por item
Permitir ao parceiro marcar itens como `required: true/false` no YAML de inspeções. Itens não obrigatórios que falham não afetam o resultado geral.

### P3.4 — Refatorar Fases 3 e 4 para classe base `PhaseThreeStep`
As duas fases são estruturalmente idênticas. Se uma terceira fase com esse padrão surgir, vale extrair uma classe base parametrizável.

### P3.5 — Tela de calibração
Fase adicional futura: envio de dados de calibração ao DSP via `send_calibration_data`. Aguarda definição do processo de calibração de fábrica.

### P3.6 — Integração com sistema de rastreabilidade do parceiro
Enviar resultado do check para API do parceiro ao final. Depende de levantamento dos sistemas do parceiro.

### P3.7 — Hardware de apoio para testes de isolação
Teste mais profundo de isolação elétrica requer circuito auxiliar externo. Avaliar necessidade conforme maturidade da linha de produção.

---

## Sugestão de implementação: Mock DSP (P2.2)

```python
# mock_dsp.py — simula stream serial do DSP
import time, serial, threading

def generate_frame(posix):
    buttons = "0000"
    return (
        f"04 64 11 00 {posix:012d} 001 000 0.0 "
        f"100 00000000 410 37459 0 "
        f"38 30 24 28 29 "
        f"000 {buttons} 0 001 1000 00000 0000 "
        f"94 2028 -88 "
        f"{datetime.now().isoformat(timespec='milliseconds')} "
        f"00 00 00 00 00 1\n"
    )

# Usar com socat para criar par de portas virtuais:
# socat -d -d pty,raw,echo=0 pty,raw,echo=0
```

---
_Última atualização: 2026-05-08_
