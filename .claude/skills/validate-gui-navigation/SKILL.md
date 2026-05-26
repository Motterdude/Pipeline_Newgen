# validate-gui-navigation

Valida a máquina de estados de navegação do Preview Plot (e de qualquer widget complexo PySide6) usando a abordagem **NavigationHarness** — stub leve que replica a lógica sem instanciar Qt.

## Quando usar

- Após qualquer edição em `src/pipeline_newgen_rev1/ui/preview_plot_tab.py` que toque: navegação, mode switching, presets, workspace load/save, populate_from_record, ou compare metric cycling.
- Quando o usuário reporta comportamento errático na GUI (modos pulando, escalas trocadas, crashes no render).
- Como smoke test antes de fechar uma sessão que tocou o Preview Plot.

## Passos

### 1. Rodar a suite de navegação

```bash
python -m unittest discover -s tests -p "test_preview_navigation.py" -v
```

Critério de sucesso: **94 tests OK**, 0 falhas, runtime < 1s.

### 2. Se algum teste falhar

Cada classe cobre um aspecto:

| Classe | Cobre |
|--------|-------|
| `TestArrowNavigation` | setas, wheel, wrap-around |
| `TestComboNavigation` | combo_plot_selector changes |
| `TestThumbnailNavigation` | clicks na thumbnail strip |
| `TestPresetNavigation` | aplicação de presets |
| `TestCompareMetricNavigation` | cycling de métricas compare |
| `TestModeStickiness` | **REGRESSÃO CORE** — modos não devem ser forçados na navegação |
| `TestSessionSync` | active_mode sincroniza imediatamente |
| `TestScaleMemory` | y_scales keyed por y_col, não por mode |
| `TestTitleIntegrity` | título correto após navegação |
| `TestCompareDfGuard` | crash prevention quando _compare_df é None |
| `TestWorkspaceRetrocompat` | workspace v2 JSON carrega sem trapping |
| `TestLockXBehavior` | lock_x interage com navigation corretamente |
| `TestPopulatingGuard` | flag _populating previne re-entrância |
| `TestBoundaryConditions` | 0 plots, 1 plot, NaN, records vazios |
| `TestStateTransitionMatrix` | transições entre todos os 7 plot types |

### 3. Adicionar testes para novas features

Se adicionou nova feature de navegação ou modo:

1. Identificar qual classe do harness precisa de novo método (ou nova classe).
2. Copiar a lógica VERBATIM do widget real para o `NavigationHarness`.
3. Escrever teste no padrão existente.
4. Rodar suite → 0 falhas.

### 4. Filosofia do NavigationHarness

**Problema**: PySide6 widgets crasham em ambientes headless (segfault em QPushButton.clicked.connect no offscreen platform via Git Bash no Windows).

**Solução**: Criar stubs mínimos (`_ComboStub`, `_EditStub`, `_CheckStub`) que replicam a interface de QComboBox/QLineEdit/QCheckBox sem dependência Qt. A lógica de navegação é copiada verbatim do widget real (não mocada, não simplificada) — isso garante que o teste valida o **mesmo código** que roda na GUI.

**Trade-off**: Se o widget real mudar a lógica de um método testado, o harness precisa ser atualizado manualmente. Isso é intencional — funciona como "contrato": qualquer divergência entre harness e widget é um bug a ser investigado.

### 5. Rodar suite completa

```bash
python -m unittest discover -s tests -p "test_*.py"
```

Confirmar que os 10 erros pré-existentes (bridges legados) são os únicos, e zero falhas novas.

## Não fazer

- Não tentar instanciar `PreviewPlotTab` diretamente em testes — vai dar segfault no ambiente headless.
- Não mockar os métodos de navegação — o ponto é testar a lógica REAL.
- Não deletar testes de regressão sem confirmar que o bug original não pode voltar.
