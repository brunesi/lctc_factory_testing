# 06 — Gotchas

Conhecimento negativo: bugs conhecidos, armadilhas, "não faça X porque Y".

---

## Frame DSP

### O campo `|0|` não existe no frame real
O campo de potência calculada (`|0|`) aparece em logs de pós-processamento do projeto principal, mas **não existe no stream serial real**. O parser foi escrito sem ele. Se você ver um frame com esse campo ao analisar logs antigos, é artefato de script de análise — não adicione ao parser.

### O frame tem exatamente 35 tokens
`split()` do frame real produz 35 tokens (índices 0–34). Qualquer frame com contagem diferente é descartado pelo parser como inválido. Não tente "consertar" frames curtos — eles indicam corrupção ou frame parcial.

### `posix` é o clock interno do DSP, não Unix time
O campo `posix` (índice 4) incrementa a cada envio do DSP, mas **não** é necessariamente o timestamp Unix atual. Não use para calcular tempo absoluto — use apenas para detectar que o DSP está vivo (valor mudou entre duas leituras).

---

## Botões

### A string `4321` tem ordem invertida
O campo `4321` (índice 19) é a string `"0000"` onde:
- `[0]` = B4 (quarto botão)
- `[3]` = B1 (primeiro botão)

A ordem é invertida em relação ao número do botão. A propriedade `DspState.button1` já lida com isso, mas se acessar `buttons_raw` diretamente, atenção.

### Botões precisam de detecção de borda, não de estado
Se você ler `dsp_state.button1` a cada frame do loop Pygame (30fps) e o botão ficar pressionado por 200ms, vai processar o mesmo botão ~6 vezes. Sempre use os `ButtonEvent` da fila — eles já aplicam detecção de borda (`0→1` apenas).

---

## Threading

### Nunca leia DspState diretamente em `update()`
Sempre use `state.snapshot()` dentro de `update()`. Ler campos diretamente sem o lock pode resultar em estado parcialmente atualizado se a thread serial atualizar o objeto ao mesmo tempo.

### `DspReader.send()` pode retornar `False` silenciosamente
Se a porta serial cair e a thread ainda não reconectou, `send()` retorna `False`. As funções em `commands.py` logam o erro mas não levantam exceção. As fases precisam checar o retorno se a confirmação for crítica.

---

## Pygame

### `Fonts.init()` deve ser chamado após `pygame.init()`
As fontes são `None` até `F.init()` ser chamado. Chamar o renderer antes disso levanta `AttributeError`. Em `main.py`, a ordem correta é: `pygame.init()` → `F.init()` → primeiro render.

### `pygame.FULLSCREEN` em Ubuntu 16.04 com resolução não-nativa
Se a resolução do monitor físico não for exatamente 600×1024, o Pygame pode escalar ou recortar a imagem. Testar em hardware real. Alternativa: usar `pygame.NOFRAME` e posicionar a janela manualmente se houver problema.

### Pings bloqueiam o loop durante a Fase 8
Os 5 pings em `_run_network_checks()` rodam de forma síncrona via `subprocess`. A tela congela durante esse tempo (até ~50s no pior caso). Isso é aceitável para uma tela de fábrica, mas o operador pode achar que o sistema travou. Se for problema, mover pings para thread de background.

---

## Protocolo DSP

### Checksum zero vira 0xFF
A função `checksum_8_2s_complement` do protocolo tem um caso especial: se o complemento de 2 resultar em zero, retorna `0xFF` em vez de `0x00`. Isso está replicado em `dsp/commands.py::_checksum()`. Não "corrija" esse comportamento — é intencional no protocolo proprietário.

### Porta serial do DSP: `/dev/ttyFTDI_serialCODICO`
O mapeamento udev usa nomes persistentes baseados no serial do FTDI. A porta do DSP é `/dev/ttyFTDI_serialCODICO` e do leitor RFID é `/dev/ttyFTDI_RFID`. Se a porta não aparecer, verificar se as regras udev estão instaladas corretamente no sistema.

---

## Inspeções visuais

### YAML carregado em `on_enter`, não no construtor
`Phase7Inspections` lê o arquivo YAML em `on_enter()`. Se o arquivo não existir, a fase encerra como SKIP. Não falha silenciosamente — loga erro com o caminho completo. Verificar o log se as inspeções não aparecerem.

---
_Última atualização: 2026-05-08_

### DSP não envia dados sem DTR/RTS em nível 1 — CRÍTICO
Ao abrir a porta serial, o driver Linux força DTR e RTS para zero. O DSP usa essas linhas como enable e não envia nada sem elas em nível 1. O `DspReader` deve fazer imediatamente após abrir a porta:
```python
ser.dtr = False   # de-assert → nível 1 (lógica invertida no hardware)
ser.rts = False   # de-assert → nível 1
```
Sem isso, `read_binary_frame()` fica bloqueado indefinidamente aguardando SOP.

### Mapeamento de bytes do megapayload estava incorreto — CORRIGIR NA PRÓXIMA CONVERSA
O mapeamento em `dsp/protocol.py` foi inferido do código Python de produção e tem erros nos campos após T3 (índice 25). A documentação oficial byte a byte (`megapayload.docx`) é a fonte de verdade. Campos confirmadamente errados: T4, T5, acelerômetro (x, y, z). Rno SIM existe no frame binário (ao contrário do que foi assumido). Na nova conversa: reescrever `decode_megapayload()` integralmente a partir do docx.
