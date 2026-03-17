import os
import sys
import argparse
import json
import pandas as pd
import re
import dash
from dash import dcc, html, dash_table
import plotly.express as px
from datetime import datetime
from flask import jsonify, request

# importar camada de dados e orquestrador
from .data import loader
from .service import orchestrator

# Caminho dos arquivos de saída
# usar data.loader para carregar os dados (apenas arquivos que começam com 'saida')
df = loader.carregar_dados()

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


# note: request/error detection and message helpers moved to relatorio_aproveitamento.processing

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
    # delegar toda lógica de carregamento/filtragem/agregação ao orquestrador
    try:
        fig_erro, data_resumo, data_mensagens = orchestrator.build_dashboard_data(resumo_sel, filtro_erro_grupo, filtro_empresa)
    except Exception:
        # em caso de erro inesperado, retornar estruturas vazias amigáveis
        fig_erro = px.bar(title='Erro ao gerar dados')
        data_resumo = []
        data_mensagens = []

    return fig_erro, data_resumo, data_mensagens
    # a lógica de resumo e agregação está centralizada em service.orchestrator

@app.server.route('/_debug/data')
def debug_data():
    try:
        fig_erro, data_resumo, data_mensagens = orchestrator.build_dashboard_data([], 'dia', [])
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
            return all_vals
        return dash.no_update
    except Exception as e:
        return dash.no_update

if __name__ == '__main__':
    # Run app; prefer using package entrypoint `python -m relatorio_aproveitamento` or this file directly
    app.run(host='0.0.0.0', port=8050, debug=False, use_reloader=False)

