
# Dashboard de Aproveitamento

Este diretório contém o dashboard (aplicação web) usado para visualizar os
resultados das extrações/consultas.

Resumo curto
- Visualiza resultados de extrações: resumo diário (total, sucesso, erros de requisição, ativos/inativos),
	distribuição de mensagens/erros e gráfico de erros (por dia ou hora).

Principais regras de entrada
- Lê somente arquivos Excel cujo nome COMEÇA com "saida" (case‑insensitive). Exemplos: `saida-2026-03.xlsx`.
- Aceita extensões `.xlsx` e `.xls`. Arquivos temporários do Excel (`~$...`) são ignorados.

Onde estão os componentes
- `dashboard.py` — aplicação Dash (UI).
- `data/loader.py` — camada de dados (ponto único de leitura, resolve pasta de entrada).
- `processing/processing.py` — funções de detecção/agregação de erros e mensagens.
- `service/orchestrator.py` — orquestrador que monta as figuras e tabelas consumidas pelo UI.
- `run_dashboard_launcher.py` & `run_dashboard.bat` — launcher GUI (escolhe pasta, inicia o servidor e abre o navegador).

Como executar
- Recomendado (GUI, Windows):
	1) Abra `relatorio_aproveitamento\run_dashboard.bat` (ou execute `python run_dashboard_launcher.py`).
	2) Selecione a pasta que contém os arquivos `saida-*.xlsx` quando solicitado.
	3) O launcher inicia o servidor e abre: http://127.0.0.1:8050

- Linha de comando (opcional):
	- Passando a pasta explicitamente:
		```powershell
		python relatorio_aproveitamento\dashboard.py --pasta-saidas "C:\caminho\para\Arquivos"
		```
	- Ou exportando a variável de ambiente (PowerShell):
		```powershell
		$env:DASHBOARD_PASTA_SAIDAS = 'C:\caminho\para\Arquivos'
		python relatorio_aproveitamento\dashboard.py
		```

Dependências
- Instale com pip (virtualenv recomendado):
	```powershell
	python -m pip install -r relatorio_aproveitamento\requirements.txt
	```

Troubleshooting rápido
- Se o navegador não abrir, acesse manualmente: http://127.0.0.1:8050
- Confirme que os arquivos têm nome começando por `saida` e extensão `.xlsx`/`.xls`.
- Se faltar alguma biblioteca, instale as dependências novamente com o comando acima.

Próximos passos possíveis
- Empacotar o launcher como .exe (PyInstaller) para distribuição sem Python.
- Persistir agregados em banco caso deseje histórico e consultas mais rápidas.

Se quiser, eu faço: gerar o .exe do launcher, ajustar `gerar_relatorio.py` para usar a mesma detecção de erros, ou adicionar testes unitários mínimos.
Se quiser, posso gerar um único executável (.exe) para Windows usando PyInstaller — diga se você prefere isso.



