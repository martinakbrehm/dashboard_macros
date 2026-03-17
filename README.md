
# Dashboard de Aproveitamento

Este diretório contém o dashboard (aplicação web) usado para visualizar os
resultados das extrações/consultas.

O que o dashboard mostra
- Resumo diário: total, sucessos, erros de requisição, ativos e inativos.
- Distribuição de mensagens/erros: lista das mensagens mais frequentes.
- Gráfico de erros: contagem de erros por dia ou por hora.
- Tabelas filtráveis por data e por empresa (se a coluna `empresa` estiver presente).

Regras de leitura dos arquivos
- O dashboard carrega apenas arquivos Excel cujo nome COMEÇA com `saida` (ex.: `saida-entradas_01.xlsx`).
- Aceita extensões `.xlsx` e `.xls`.

Arquivos importantes
- `dashboard.py` — aplicação Dash.
- `run_dashboard_launcher.py` — launcher com interface para escolher a pasta de saída.
- `run_dashboard.bat` — atalho para Windows que chama o launcher.
- `.dashboard_config.json` — arquivo onde o launcher salva a pasta escolhida.
- `requirements.txt` — lista de dependências Python.

Como executar (passo a passo)

Opção A — GUI (Windows, recomendado):
1. Abra a pasta `relatorio_aproveitamento` e dê duplo clique em `run_dashboard.bat`.
2. Leia a mensagem e clique em "Escolher pasta". Selecione a pasta que contém os arquivos `saida-*.xlsx`.
3. O launcher iniciará o servidor e, quando estiver pronto, abrirá automaticamente o navegador em `http://127.0.0.1:8050`.

Opção B — Linha de comando:
- Rodando o dashboard apontando a pasta:

```powershell
python relatorio_aproveitamento\dashboard.py --pasta-saidas "C:\caminho\para\Arquivos"
```

- Ou definindo a variável de ambiente (PowerShell):

```powershell
$env:DASHBOARD_PASTA_SAIDAS = 'C:\caminho\para\Arquivos'
python relatorio_aproveitamento\dashboard.py
```

Instalação de dependências
1. Recomenda-se usar um virtualenv.
2. Instale as dependências:

```powershell
python -m pip install -r relatorio_aproveitamento\requirements.txt
```

Dicas rápidas / problemas comuns
- Se o navegador não abrir, abra manualmente: http://127.0.0.1:8050
- Verifique se os arquivos têm nome começando por `saida` e extensão `.xlsx`/`.xls`.
- Se houver erro de import (biblioteca faltando), rode o comando de instalação acima.

