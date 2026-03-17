import pandas as pd
import plotly.express as px
from ..data import loader
from ..processing import processing


def build_dashboard_data(resumo_sel, filtro_erro_grupo, filtro_empresa, pasta_saidas=None):
    """Carrega dados via data.loader, aplica filtros e retorna (fig_erro, data_resumo, data_mensagens).

    - resumo_sel: list of date strings (YYYY-MM-DD) or empty
    - filtro_erro_grupo: 'dia' or 'hora'
    - filtro_empresa: list or single value or empty
    - pasta_saidas: override path
    """
    df = loader.carregar_dados(pasta_saidas)

    # Defensive: se vazio
    if df is None or df.empty:
        fig_empty = px.bar(title='Sem dados')
        return fig_empty, [], []

    dff = df.copy()

    # aplicar filtro de dias (global)
    if resumo_sel:
        try:
            dff = dff[dff['dia'].astype(str).isin(resumo_sel)]
        except Exception:
            pass

    # aplicar filtro de empresa (global)
    if filtro_empresa:
        try:
            if isinstance(filtro_empresa, list):
                dff = dff[dff['empresa'].astype(str).isin([str(x) for x in filtro_empresa])]
            else:
                dff = dff[dff['empresa'].astype(str) == str(filtro_empresa)]
        except Exception:
            pass

    col_msg = processing.pick_message_column(dff)
    data_mensagens = processing.aggregate_messages(dff, col_msg)

    # Erros de requisição
    erro_req = processing.detect_request_error(dff, col_msg) if col_msg else pd.Series([False] * len(dff), index=dff.index)
    df_erro = dff.copy()
    df_erro['erro_req'] = erro_req

    # figura: por hora ou por dia
    if filtro_erro_grupo == 'hora' and 'data_hora' in dff.columns:
        df_erro['hora'] = df_erro['data_hora'].dt.strftime('%Y-%m-%d %H:00')
        erro_por_hora = df_erro[df_erro['erro_req']].groupby('hora').size().reset_index(name='erros')
        all_hours = sorted(df_erro['hora'].dropna().unique())
        df_all_hours = pd.DataFrame({'hora': all_hours})
        erro_por_hora = df_all_hours.merge(erro_por_hora, on='hora', how='left').fillna(0)
        erro_por_hora['erros'] = erro_por_hora['erros'].astype(int)
        erro_por_hora['hora'] = erro_por_hora['hora'].astype(str)
        fig_erro = px.bar(erro_por_hora, x='hora', y='erros', title='Erros de requisição por hora', labels={'hora': 'Hora', 'erros': 'Erros'})
        fig_erro.update_layout(template='plotly_white', xaxis_title='Hora', yaxis_title='Quantidade de erros')
        fig_erro.update_yaxes(autorange=True, tickformat='d')
    else:
        erro_por_dia = df_erro[df_erro['erro_req']].groupby('dia').size().reset_index(name='erros')
        all_days = sorted(dff['dia'].dropna().unique())
        df_all_days = pd.DataFrame({'dia': all_days})
        erro_por_dia = df_all_days.merge(erro_por_dia, on='dia', how='left').fillna(0)
        erro_por_dia['dia_dt'] = pd.to_datetime(erro_por_dia['dia'])
        erro_por_dia = erro_por_dia.sort_values('dia_dt')
        erro_por_dia['erros'] = erro_por_dia['erros'].astype(int)
        erro_por_dia['dia'] = erro_por_dia['dia'].astype(str)
        fig_erro = px.bar(erro_por_dia, x='dia', y='erros', title='Erros de requisição por dia', labels={'dia': 'Data', 'erros': 'Erros'})
        fig_erro.update_layout(template='plotly_white', xaxis_title='Data', yaxis_title='Quantidade de erros')
        fig_erro.update_yaxes(autorange=True, tickformat='d')

    # --- Tabela Resumo ---
    data_resumo = []
    if not dff.empty and 'dia' in dff.columns:
        total_por_dia = dff.groupby('dia').size()
        erro_req_resumo = processing.detect_request_error(dff, col_msg)
        erro_req_por_dia = erro_req_resumo.groupby(dff['dia']).sum().reindex(total_por_dia.index, fill_value=0)
        sucesso_por_dia = total_por_dia - erro_req_por_dia

        if 'Status' in dff.columns:
            status_upper = dff['Status'].astype(str).str.upper()
            ativos_mask = status_upper == 'ATIVO'
            inativos_mask = status_upper == 'INATIVO'
            special_include = 'TITULARIDADE CONFIRMADA COM CONTRATO INATIVO'
            if col_msg and col_msg in dff.columns:
                try:
                    msg_upper = dff[col_msg].fillna('').astype(str).str.strip().str.upper()
                    inativos_mask = inativos_mask | (msg_upper == special_include)
                    ativos_mask = ativos_mask & (msg_upper != special_include)
                except Exception:
                    pass
        else:
            ativos_mask = pd.Series([False] * len(dff), index=dff.index)
            inativos_mask = pd.Series([False] * len(dff), index=dff.index)

        ativos_por_dia = ativos_mask.groupby(dff['dia']).sum().reindex(total_por_dia.index, fill_value=0)
        inativos_por_dia = inativos_mask.groupby(dff['dia']).sum().reindex(total_por_dia.index, fill_value=0)

        resumo = pd.DataFrame({
            'dia': total_por_dia.index.astype(str),
            'total': total_por_dia.values,
            'sucesso': sucesso_por_dia.values,
            'erro_requisicao': erro_req_por_dia.values,
            'ativos': ativos_por_dia.values,
            'inativos': inativos_por_dia.values,
        })

        # se várias datas selecionadas, inserir linha de soma
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

    return fig_erro, data_resumo, data_mensagens
