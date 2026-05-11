# 03 — Convenções

## Linguagem e estilo

- Python 3.10.6 — usar `match/case`, `dataclass`, `typing` moderno
- PEP 8, exceto linhas até 100 caracteres
- Type hints em todas as assinaturas de função pública
- Docstrings em módulos e classes; funções simples dispensam

## Nomenclatura

| Elemento | Convenção | Exemplo |
|---|---|---|
| Módulos | snake_case | `phase1_auto.py` |
| Classes | PascalCase | `Phase1Auto`, `DspState` |
| Funções/métodos | snake_case | `on_enter`, `parse_frame` |
| Constantes | UPPER_SNAKE | `SERIAL_PORT`, `TEMP_MAX` |
| Privados | prefixo `_` | `_check_temperatures`, `_SubStep` |
| Enums internos de fase | `_SubStep`, `_Step` com prefixo `_` | evita exportação acidental |

## Estrutura de uma fase

Toda fase herda de `Phase` e implementa três métodos:

```python
def on_enter(self, state: DspState) -> None:
    # inicialização, comandos DSP iniciais, reset de estado interno

def update(self, state: DspState, events: list[ButtonEvent]) -> Status:
    # lógica principal; retorna RUNNING, PASS, FAIL ou SKIP

def on_exit(self) -> PhaseResult:
    # finaliza PhaseResult e retorna via self._finish(status)
```

Usar sempre `state.snapshot()` dentro de `update()` para leitura thread-safe.

Usar os helpers herdados para registrar resultados:
```python
self._pass("Nome do item", measured="valor lido")
self._fail("Nome do item", measured="valor", note="o que verificar")
self._skip("Nome do item", note="motivo")
```

## Atributos expostos ao renderer

Cada fase deve expor atributos públicos que o renderer usa para desenhar.
Convenção de nomenclatura:

| Tipo | Nome sugerido |
|---|---|
| Texto de instrução principal | `instruction` |
| Subtítulo do passo | `step_label` |
| Instrução secundária | `sub_instruction` |
| Legenda dos botões | `legend` |
| Countdown em segundos | `countdown: float` |
| Estado de sensor (bool/int) | nome do campo: `em_state`, `door_open`, `fan_status` |
| Leituras ao vivo | `live_readings: dict[str, str]` |

## Renderer

- Uma função privada `_render_phaseN` por fase
- Despacho via dicionário `_RENDERERS = {phase_id: func}`
- Componentes reutilizáveis prefixados com `_` (primitivas e componentes)
- Todos os componentes verticais retornam o `y` após si mesmos

## Constantes

Todas as constantes de configuração ficam em `config.py`.
Nenhuma fase ou componente de UI deve conter valores mágicos.

## Logging

Usar `logging.getLogger(__name__)` em cada módulo.
Níveis:
- `DEBUG`: frames seriais, detalhes de protocolo
- `INFO`: transições de fase, comandos enviados, resultados de itens
- `WARNING`: situações recuperáveis (pendrive ausente, fan_on não implementado)
- `ERROR`: falhas que comprometem o check (erro serial, falha ao salvar log)

## Comentários

- `# TODO:` para implementações pendentes conhecidas
- `# NOTE:` para explicações não óbvias de comportamento
- Evitar comentários que apenas repetem o código

---
_Última atualização: 2026-05-08_
