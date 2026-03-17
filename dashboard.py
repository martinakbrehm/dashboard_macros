import os
import sys
import argparse
import json
import pandas as pd
import re
import json
import dash
from dash import dcc, html, dash_table
import plotly.express as px
from datetime import datetime
from flask import jsonify, request

# Caminho dos arquivos de saída
CONFIG_PATH = os.path.join(os.path.dirname(__file__), '.dashboard_config.json')

def _get_pasta_saidas():
    # 1) Environment variable override
    env = os.environ.get('DASHBOARD_PASTA_SAIDAS')
    if env:
        return os.path.abspath(env)

    # 2) CLI argument --pasta-saidas or -p
    try:
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument('--pasta-saidas', '-p', default=None)
        args, _ = parser.parse_known_args()
        if args.pasta_saidas:
            return os.path.abspath(args.pasta_saidas)
    except Exception:
        pass

    # 3) Configuration file in the package folder
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                p = cfg.get('pasta_saidas') or cfg.get('pasta_saidas_path')
                if p:
                    return os.path.abspath(p)
    except Exception:
        pass

    # 4) Default path (original behavior)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'dados', 'Arquivos'))

PASTA_SAIDAS = _get_pasta_saidas()

def carregar_dados():
    arquivos_saida = []
    allowed_exts = ('.xlsx', '.xls')
    if os.path.isdir(PASTA_SAIDAS):
        for f in os.listdir(PASTA_SAIDAS):
            name = f.strip()
            lower = name.lower()
            reason = None
            # ignorar arquivos temporarios do Excel
            if lower.startswith('~$'):
                reason = 'temp file (~$...)'
            # aceitar qualquer arquivo cujo nome COMEÇA com 'saida' (case-insensitive)
            elif not lower.startswith('saida'):
                reason = 'does not start with "saida"'
            # aceitar apenas extensões permitidas
            elif not lower.endswith(allowed_exts):
                reason = f'unsupported extension, allowed: {allowed_exts}'
            if reason is None:
                arquivos_saida.append(os.path.join(PASTA_SAIDAS, f))
            else:
                # intentionally silent for production use
                pass
    # Silent startup: do not print debug info to terminal
    dfs = []
    for arq in arquivos_saida:
        try:
            df = pd.read_excel(arq)
            df['__arquivo_origem'] = os.path.basename(arq)
            dfs.append(df)
        except Exception:
            # ignore read errors silently to avoid terminal noise
            pass
    if not dfs:
        return pd.DataFrame()
    df_total = pd.concat(dfs, ignore_index=True)
    # Data loaded silently
    if 'data_hora' in df_total.columns:
        df_total['data_hora'] = pd.to_datetime(df_total['data_hora'], errors='coerce')
        df_total['dia'] = df_total['data_hora'].dt.date
    else:
        df_total['dia'] = None
    return df_total

df = carregar_dados()

# Mapeamento de rótulos para exibição mais profissional
COLUMN_LABELS = {
    'dia': 'Data',
    'total': 'Total',
    'sucesso': 'Sucesso',
    'erro_requisicao': 'Erros de requisição',
    'ativos': 'Ativos',
    'inativos': 'Inativos'
}
# Debug prints removed: keep module import/processing silent in production


# Função utilitária para detectar erros de requisição de forma mais abrangente
def detect_request_error(df_input, col_msg=None):
    """
    Retorna uma pd.Series booleana (índice igual ao df_input) indicando quais
    linhas representam erros de requisição.

    Estratégia:
    - Se existir a coluna 'Error', trata como erro quando seu valor não for 'FALSO'/'FALSE'/''/'0'.
    - Procura por palavras-chave conhecidas em colunas de mensagem (col_msg e outras possíveis)
      usando uma regex ampliada (TIMEOUT, LIMIT_EXCEEDED, ERRO, CONNECTION, REFUSED, 5xx, etc.).
    - Também procura por padrões numéricos HTTP 5xx (ex.: 500, 503).
    - Retorna Series de booleans.
    """
    if df_input is None or df_input.empty:
        return pd.Series([False] * 0, index=df_input.index if df_input is not None else [])

    idx = df_input.index
    base = pd.Series(False, index=idx)

    # 1) Coluna estruturada 'Error' (quando presente) — considerar erro se não for explicitamente 'FALSO'/'FALSE'/'0'/'')
    if 'Error' in df_input.columns:
        try:
            err_col = df_input['Error'].astype(str).fillna('').str.strip().str.upper()
            is_err_from_error_col = ~err_col.isin({'FALSO', 'FALSE', '0', ''})
            base = base | is_err_from_error_col
        except Exception:
            pass

    # 2) Construir regex ampliado para mensagens/textos
    # incluir termos conhecidos, mensagens de socket/connection e códigos HTTP 5xx
    keywords = [
        r'TIMEOUT', r'LIMIT_EXCEEDED', r'ERRO', r'ERROR', r'CONNECTION', r'CONNREFUSED',
        r'REFUSED', r'RESET', r'SOCKET', r'PEAK CONNECTIONS LIMIT', r'peak connections limit',
        r'EXCEEDED', r'UNAVAILABLE', r'UNREACHABLE', r'NAME OR SERVICE NOT KNOWN', r'EOF',
        r'502', r'503', r'504', r'500'
    ]
    # compile regex; use word boundaries for numeric codes
    kw_pattern = re.compile(r"(" + r"|".join(keywords) + r")", flags=re.IGNORECASE)

    # 3) Candidate columns to inspect
    text_cols = []
    if col_msg:
        if col_msg in df_input.columns:
            text_cols.append(col_msg)
    for c in ['Msg', 'mensagem', 'resposta', 'resposta_lista', 'Status']:
        if c in df_input.columns and c not in text_cols:
            text_cols.append(c)

    if text_cols:
        # criar uma string agregada por linha para busca rápida
        try:
            combined = df_input[text_cols].fillna('').astype(str).agg(' '.join, axis=1)
            found = combined.str.contains(kw_pattern)
            # também detectar códigos 5xx isolados (por exemplo 'HTTP 503' ou apenas '503')
            found_codes = combined.str.contains(r'\b5\d{2}\b', case=False, na=False)
            base = base | found | found_codes
        except Exception:
            pass

    return base


def sentence_case(s):
    """Return the string in sentence case: only the first character uppercase, the rest lowercase."""
    try:
        s2 = str(s).strip()
        if not s2:
            return s2
        return s2[0].upper() + s2[1:].lower()
    except Exception:
        return str(s)

# Layout do dashboard
external_stylesheets = ['https://fonts.googleapis.com/css?family=Roboto:400,700&display=swap',
                       'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css']
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
app.title = 'Dashboard de aproveitamento das macros'

# Estilos de títulos padronizados
TITLE_STYLE = {'fontFamily': 'Roboto', 'color': '#2c3e50', 'fontWeight': '700', 'fontSize': '22px'}
SECTION_TITLE_STYLE = {'fontFamily': 'Roboto', 'color': '#2980b9', 'fontWeight': '700', 'fontSize': '18px'}
SUBTITLE_STYLE = {'fontFamily': 'Roboto', 'color': '#2c3e50', 'fontWeight': '700', 'fontSize': '16px'}



# Registrar todas as requisições Flask para depuração do tráfego do Dash
@app.server.before_request
def _log_incoming_requests():
    try:
        path = request.path
        method = request.method
        # Intentionally silent: skip detailed Flask request logging to avoid terminal noise
    except Exception:
        # Não deixar falhar o servidor por causa do logger
        import traceback
        traceback.print_exc()

# Opções de filtro
opcoes_dia = sorted(df['dia'].dropna().unique()) if not df.empty else []
opcoes_empresa = sorted(df['empresa'].dropna().unique()) if not df.empty and 'empresa' in df.columns else []

app.layout = html.Div([
    html.Div([
        html.Img(src='https://img.icons8.com/color/48/000000/combo-chart--v2.png', style={'height': '48px', 'marginRight': '16px'}),
            html.H1('Dashboard de aproveitamento das macros', style={**TITLE_STYLE, 'display': 'inline-block', 'verticalAlign': 'middle', 'margin': 0}),
    ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '16px', 'marginTop': '16px'}),
    # Informações rápidas sobre os dados carregados
    html.Div([
        html.Span(f"Registros carregados: {len(df)}", style={'fontWeight':'600', 'marginRight':'16px'}),
        html.Span(f"Dias disponíveis: {len(opcoes_dia)}", style={'color':'#666'})
    ], style={'marginBottom':'12px', 'fontSize':'14px'}),
    # Barra superior de filtros (dias + empresa) — visual mais agradável e profissional
    html.Div([
        html.Div([
            html.Label('Filtrar dias', style={'fontWeight': '700', 'fontSize': '13px', 'marginBottom': '6px', 'display': 'block', 'color': '#2c3e50'}),
            dcc.Dropdown(
                id='resumo-dia-dropdown',
                options=[{'label': str(d), 'value': str(d)} for d in opcoes_dia],
                multi=True,
                clearable=True,
                placeholder='Todas as datas',
                style={'width': '100%'}
            ),
        ], style={'flex': '1', 'minWidth': '260px', 'background': '#ffffff', 'padding': '10px', 'borderRadius': '8px', 'boxShadow': '0 1px 6px rgba(44,62,80,0.06)'}),

        html.Div([
            html.Label('Filtrar empresa', style={'fontWeight': '700', 'fontSize': '13px', 'marginBottom': '6px', 'display': 'block', 'color': '#2c3e50'}),
            dcc.Dropdown(
                id='filtro-empresa-dropdown',
                options=[{'label': str(e), 'value': str(e)} for e in opcoes_empresa],
                multi=True,
                clearable=True,
                placeholder='Todas as empresas',
                style={'width': '100%'}
            ),
        ], style={'flex': '1', 'minWidth': '260px', 'background': '#ffffff', 'padding': '10px', 'borderRadius': '8px', 'boxShadow': '0 1px 6px rgba(44,62,80,0.06)'}),

    ], style={'display': 'flex', 'gap': '12px', 'alignItems': 'stretch', 'marginBottom': '12px', 'marginTop': '8px'}),
    html.Div([
        # Card: resumo diário (tabela)
        html.Div([
            html.H2('Resumo diário de extração', style={**SECTION_TITLE_STYLE, 'marginBottom': '8px'}),
            # dropdown moved to top of the dashboard (applies globally)
            dash_table.DataTable(
                id='tabela-resumo',
                columns=[{"name": COLUMN_LABELS.get(c, c), "id": c} for c in ['dia','total','sucesso','erro_requisicao','ativos','inativos']],
                data=[],
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'center', 'fontFamily': 'Roboto', 'fontSize': '15px', 'padding': '10px', 'whiteSpace': 'normal', 'height': 'auto'},
                style_header={**{'backgroundColor': '#2980b9', 'color': 'white', 'fontWeight': 'bold'}, **{'fontFamily': 'Roboto', 'fontSize': '15px'}},
                style_data_conditional=[
                    {'if': {'row_index': 'odd'}, 'backgroundColor': '#fafafa'}
                ],
                page_size=20
            ),
            html.P('Atualize a página para recarregar os dados dos arquivos.', style={'color': '#888', 'fontSize': '13px', 'marginTop': '8px'})
        ], style={'background': '#fff', 'borderRadius': '8px', 'boxShadow': '0 2px 8px #e0e0e0', 'padding': '16px', 'marginBottom': '18px'}),

        # Card: mensagens e gráfico (abaixo do resumo, no mesmo bloco pai)
        html.Div([
            # Tabela: distribuição de mensagens / erros
            html.Div([
                    html.H3('Distribuição de mensagens e erros', style={**SUBTITLE_STYLE, 'marginTop': '0', 'marginBottom': '8px'}),
                dash_table.DataTable(
                    id='tabela-mensagens',
                    columns=[{"name": 'Mensagem / erro', "id": 'mensagem'}, {"name": 'Quantidade', "id": 'quantidade'}],
                    data=[],
                    style_table={'overflowX': 'auto', 'borderRadius': '8px', 'boxShadow': '0 2px 8px #e0e0e0', 'marginTop': '12px'},
                    style_cell={'textAlign': 'left', 'fontFamily': 'Roboto', 'fontSize': '14px', 'padding': '8px', 'whiteSpace': 'normal', 'height': 'auto'},
                    style_header={**{'backgroundColor': '#2980b9', 'color': 'white', 'fontWeight': 'bold'}, **{'fontFamily': 'Roboto', 'fontSize': '15px'}},
                    style_data_conditional=[
                        {'if': {'row_index': 'odd'}, 'backgroundColor': '#fafafa'}
                    ],
                    page_size=10
                )
            ], style={'background': '#fff', 'borderRadius': '8px', 'boxShadow': '0 2px 8px #e0e0e0', 'padding': '12px', 'marginBottom': '22px'}),

            html.Div([
                html.Label('Agrupar erros de requisição por:', style={'fontWeight': '700', 'marginRight': '8px', 'fontSize': '14px'}),
                dcc.Dropdown(
                    id='filtro-erro-grupo',
                    options=[
                        {'label': 'Por dia', 'value': 'dia'},
                        {'label': 'Por hora', 'value': 'hora'}
                    ],
                    value='dia',
                    clearable=False,
                    style={'width': '220px', 'display': 'inline-block'}
                ),
            ], style={'marginBottom': '12px'}),

            html.Div(dcc.Graph(id='grafico-erro-dia', style={'height': '420px'}), style={'background': '#fff', 'borderRadius': '8px', 'boxShadow': '0 2px 8px #e0e0e0', 'padding': '12px'}),

        ], style={'width': '100%'}),

    ], style={'background': '#f4f6f8', 'padding': '28px', 'borderRadius': '10px', 'marginBottom': '32px'}),
    # footer removed as requested (previously showed developer/company and version)
    html.Div(style={'height': '8px'})
], style={'maxWidth': '1100px', 'margin': '0 auto', 'fontFamily': 'Roboto', 'background': '#fff', 'padding': '16px 0'})

# Adicionar logs detalhados no callback para depuração
@app.callback(
    [
        dash.dependencies.Output('grafico-erro-dia', 'figure'),
        dash.dependencies.Output('tabela-resumo', 'data'),
        dash.dependencies.Output('tabela-mensagens', 'data'),
    ],
    [
        dash.dependencies.Input('resumo-dia-dropdown', 'value'),
        dash.dependencies.Input('filtro-erro-grupo', 'value'),
        dash.dependencies.Input('filtro-empresa-dropdown', 'value')
    ]
)
def atualizar_dashboard(resumo_sel, filtro_erro_grupo, filtro_empresa):
    # Callback invoked; keep silent (no terminal debug prints)
    dff = df.copy()
    # aplicar filtro de dias (global)
    if resumo_sel:
        dff = dff[dff['dia'].astype(str).isin(resumo_sel)]
    else:
        # no day filter selected -> use all data
        pass
    # aplicar filtro de empresa (global)
    if filtro_empresa:
        try:
            if isinstance(filtro_empresa, list):
                dff = dff[dff['empresa'].astype(str).isin([str(x) for x in filtro_empresa])]
            else:
                dff = dff[dff['empresa'].astype(str) == str(filtro_empresa)]
        except Exception:
            # silently ignore filter errors
            pass

    # Dados filtrados disponíveis in-memory (no terminal output)

    # Preparar dados tabulares para a distribuição de mensagens
    col_msg = None
    for c in ['Msg', 'Status', 'Error', 'erro', 'mensagem', 'resposta', 'resposta_lista']:
        if c in dff.columns:
            col_msg = c
            break
    if col_msg:
        try:
            # Normalizar e remover mensagens indesejadas como 'N/A' e mensagens específicas
            series = dff[col_msg].dropna().astype(str).str.strip()
            # Excluir valores vazios, N/A e a mensagem específica 'ERRO: Destination name is null' (case-insensitive)
            exclude_upper = {'', 'N/A', 'ERRO: DESTINATION NAME IS NULL'}
            mask = ~series.str.upper().isin(exclude_upper)
            filtered = series[mask]
            cnt = filtered.value_counts().reset_index()
            cnt.columns = ['mensagem', 'quantidade']
            # Format mensagem to sentence case (only first letter uppercase)
            cnt['mensagem'] = cnt['mensagem'].apply(sentence_case)
            cnt = cnt.sort_values('quantidade', ascending=False)
            data_mensagens = cnt.to_dict('records')
            # grouped messages computed (silent)
        except Exception:
            # silent on grouping errors
            data_mensagens = []
    else:
        data_mensagens = []

    # Log para verificar os dados da tabela resumo
    if not dff.empty and 'dia' in dff.columns:
        # preparing resumo table (silent)
        pass
    else:
        # no data or 'dia' column missing
        pass

    # Erros de requisição por dia ou hora
    erro_req = detect_request_error(dff, col_msg) if col_msg else pd.Series([False]*len(dff), index=dff.index)
    if 'dia' in dff.columns:
        df_erro = dff.copy()
        df_erro['erro_req'] = erro_req
        if filtro_erro_grupo == 'hora' and 'data_hora' in dff.columns:
            df_erro['hora'] = df_erro['data_hora'].dt.strftime('%Y-%m-%d %H:00')
            # contar quantidade de registros que são erros por hora
            erro_por_hora = df_erro[df_erro['erro_req']].groupby('hora').size().reset_index(name='erros')
            # garantir que todas as horas presentes no filtro apareçam (mesmo com 0)
            all_hours = sorted(df_erro['hora'].dropna().unique())
            df_all_hours = pd.DataFrame({'hora': all_hours})
            erro_por_hora = df_all_hours.merge(erro_por_hora, on='hora', how='left').fillna(0)
            erro_por_hora['erros'] = erro_por_hora['erros'].astype(int)
            erro_por_hora['hora'] = erro_por_hora['hora'].astype(str)
            # erro_por_hora computed (silent)
            fig_erro = px.bar(erro_por_hora, x='hora', y='erros', title='Erros de requisição por hora', labels={'hora':'Hora', 'erros':'Erros'})
            max_err = erro_por_hora['erros'].max()
            if pd.isna(max_err):
                max_val = 0
            else:
                try:
                    max_val = int(max_err)
                except Exception:
                    max_val = int(float(max_err)) if not pd.isna(max_err) else 0
            # use autorange to avoid forcing [0,1] when counts are small; ensure integer ticks
            fig_erro.update_layout(
                template='plotly_white',
                xaxis_title='Hora',
                yaxis_title='Quantidade de erros',
                font={'family': 'Roboto', 'size': 14, 'color': '#2c3e50'},
                title={'font': {'family': 'Roboto', 'size': 16, 'color': '#2c3e50'}}
            )
            fig_erro.update_yaxes(autorange=True, tickformat='d')
        else:
            # contar quantidade de registros que são erros por dia
            erro_por_dia = df_erro[df_erro['erro_req']].groupby('dia').size().reset_index(name='erros')
            # garantir que todas as datas apareçam (mesmo com 0)
            all_days = sorted(dff['dia'].dropna().unique())
            df_all_days = pd.DataFrame({'dia': all_days})
            erro_por_dia = df_all_days.merge(erro_por_dia, on='dia', how='left').fillna(0)
            # ordenar por dia cronológico e garantir tipo inteiro para contagem
            erro_por_dia['dia_dt'] = pd.to_datetime(erro_por_dia['dia'])
            erro_por_dia = erro_por_dia.sort_values('dia_dt')
            erro_por_dia['erros'] = erro_por_dia['erros'].astype(int)
            # garantir que a coluna dia seja string para o eixo x
            erro_por_dia['dia'] = erro_por_dia['dia'].astype(str)
            # erro_por_dia computed (silent)
            fig_erro = px.bar(erro_por_dia, x='dia', y='erros', title='Erros de requisição por dia', labels={'dia':'Data', 'erros':'Erros'})
            max_err = erro_por_dia['erros'].max()
            if pd.isna(max_err):
                max_val = 0
            else:
                try:
                    max_val = int(max_err)
                except Exception:
                    max_val = int(float(max_err)) if not pd.isna(max_err) else 0
            # use autorange to avoid forcing [0,1] when counts are small; ensure integer ticks
            fig_erro.update_layout(
                template='plotly_white',
                xaxis_title='Data',
                yaxis_title='Quantidade de erros',
                font={'family': 'Roboto', 'size': 14, 'color': '#2c3e50'},
                title={'font': {'family': 'Roboto', 'size': 16, 'color': '#2c3e50'}}
            )
            fig_erro.update_yaxes(autorange=True, tickformat='d')
    # --- Tabela Resumo ---
    # dff já está filtrado por resumo_sel no topo da função
    dff_resumo = dff
    if not dff_resumo.empty and 'dia' in dff_resumo.columns:
        total_por_dia = dff_resumo.groupby('dia').size()
        # Recomputa máscaras sobre o DataFrame já filtrado para evitar reindex warnings
        # Reconstruir máscara de erro usando a função centralizada
        erro_req_resumo = detect_request_error(dff_resumo, col_msg)
        erro_req_por_dia = erro_req_resumo.groupby(dff_resumo['dia']).sum().reindex(total_por_dia.index, fill_value=0)
        sucesso_por_dia = total_por_dia - erro_req_por_dia
        if 'Status' in dff_resumo.columns:
            status_upper = dff_resumo['Status'].astype(str).str.upper()
            # máscaras iniciais baseadas em Status
            ativos_mask = status_upper == 'ATIVO'
            inativos_mask = status_upper == 'INATIVO'
            # Incluir mensagens específicas como 'inativos' adicionalmente
            # e remover essas mesmas linhas dos 'ativos' para evitar dupla contagem
            special_include = 'TITULARIDADE CONFIRMADA COM CONTRATO INATIVO'
            if col_msg and col_msg in dff_resumo.columns:
                try:
                    msg_upper = dff_resumo[col_msg].fillna('').astype(str).str.strip().str.upper()
                    inativos_mask = inativos_mask | (msg_upper == special_include)
                    # garantir que linhas com a mensagem especial não sejam contadas como ativos
                    ativos_mask = ativos_mask & (msg_upper != special_include)
                except Exception:
                    pass
        else:
            ativos_mask = pd.Series([False] * len(dff_resumo), index=dff_resumo.index)
            inativos_mask = pd.Series([False] * len(dff_resumo), index=dff_resumo.index)
        ativos_por_dia = ativos_mask.groupby(dff_resumo['dia']).sum().reindex(total_por_dia.index, fill_value=0)
        inativos_por_dia = inativos_mask.groupby(dff_resumo['dia']).sum().reindex(total_por_dia.index, fill_value=0)
        resumo = pd.DataFrame({
            'dia': total_por_dia.index.astype(str),
            'total': total_por_dia.values,
            'sucesso': sucesso_por_dia.values,
            'erro_requisicao': erro_req_por_dia.values,
            'ativos': ativos_por_dia.values,
            'inativos': inativos_por_dia.values,
        })
        if resumo_sel and isinstance(resumo_sel, list) and len(resumo_sel) > 1:
            soma = {
                'dia': 'Total',
                'total': int(resumo['total'].sum()),
                'sucesso': int(resumo['sucesso'].sum()),
                'erro_requisicao': int(resumo['erro_requisicao'].sum()),
                'ativos': int(resumo['ativos'].sum()),
                'inativos': int(resumo['inativos'].sum()),
            }
            resumo = pd.concat([resumo, pd.DataFrame([soma])], ignore_index=True)
        data_resumo = resumo.to_dict('records')
    else:
        data_resumo = []
        if 'fig_erro' not in locals():
            fig_erro = px.bar(title='Sem coluna data_hora')
            fig_erro.update_layout(
                template='plotly_white',
                font={'family': 'Roboto', 'size': 14, 'color': '#2c3e50'},
                title={'font': {'family': 'Roboto', 'size': 16, 'color': '#2c3e50'}}
            )
    # Retorna o gráfico de erros, a tabela resumo e a tabela de mensagens (na ordem dos Outputs)
    try:
        return fig_erro, data_resumo, data_mensagens
    except NameError:
        return px.bar(title='Sem dados'), [], []

@app.server.route('/_debug/data')
def debug_data():
    try:
        resumo_sel = []  # Simula seleção vazia
        filtro_erro_grupo = 'dia'
        filtro_empresa = []
        fig_erro, data_resumo, data_mensagens = atualizar_dashboard(resumo_sel, filtro_erro_grupo, filtro_empresa)
        return jsonify({
            'fig_erro': fig_erro.to_plotly_json(),
            'data_resumo': data_resumo,
            'data_mensagens': data_mensagens
        })
    except Exception as e:
        return jsonify({'error': str(e)})


# Se o usuário desmarcar todos os dias, selecionar todos automaticamente
@app.callback(
    dash.dependencies.Output('resumo-dia-dropdown', 'value'),
    [dash.dependencies.Input('resumo-dia-dropdown', 'value')],
    [dash.dependencies.State('resumo-dia-dropdown', 'options')]
)
def _ensure_resumo_selecionado(value, options):
    try:
        if not options:
            return dash.no_update
        all_vals = [opt['value'] for opt in options]
        if value is None or (isinstance(value, list) and len(value) == 0):
            print(f"[DEBUG] resumo-dia-dropdown vazio/no selection detected, selecionando todos ({len(all_vals)})")
            return all_vals
        return dash.no_update
    except Exception as e:
        print(f"[DEBUG] erro em _ensure_resumo_selecionado: {e}")
        return dash.no_update

if __name__ == '__main__':
    # Rodar sem reloader para manter o processo em execução em foreground
    # Bind em 0.0.0.0 para permitir acesso pelo IP da máquina na rede local
    # Nota: em versões recentes do Dash, use app.run
    # Testar rapidamente o callback sem precisar do navegador
    try:
        print('[dashboard] Executando teste rápido do callback...')
        res = atualizar_dashboard([], 'dia', [])
        if isinstance(res, tuple) and len(res) == 3:
            fig_test, data_resumo_test, data_mensagens_test = res
            print(f"[dashboard] teste callback -> resumo_rows={len(data_resumo_test)} mensagens_rows={len(data_mensagens_test)} fig_type={type(fig_test)}")
        else:
            print('[dashboard] teste callback retorno inesperado:', type(res))
    except Exception as e:
        import traceback
        print('[dashboard] erro no teste do callback:', e)
        traceback.print_exc()

    app.run(host='0.0.0.0', port=8050, debug=False, use_reloader=False)

