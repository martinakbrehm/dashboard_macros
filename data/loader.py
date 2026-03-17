import os
import json
import argparse
import pandas as pd


def _resolve_pasta_saidas(override=None):
    """Resolve a pasta de entradas com a ordem: override, env, CLI, config file, default."""
    # 1) explicit override
    if override:
        return os.path.abspath(override)

    # 2) environment variable
    env = os.environ.get('DASHBOARD_PASTA_SAIDAS')
    if env:
        return os.path.abspath(env)

    # 3) CLI arg (--pasta-saidas)
    try:
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument('--pasta-saidas', '-p', default=None)
        args, _ = parser.parse_known_args()
        if args.pasta_saidas:
            return os.path.abspath(args.pasta_saidas)
    except Exception:
        pass

    # 4) config file near the package
    try:
        cfg_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.dashboard_config.json'))
        if os.path.exists(cfg_path):
            with open(cfg_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                p = cfg.get('pasta_saidas') or cfg.get('pasta_saidas_path')
                if p:
                    return os.path.abspath(p)
    except Exception:
        pass

    # 5) sensible default (project layout)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'dados', 'Arquivos'))


def carregar_dados(pasta_saidas=None):
    """Carrega arquivos Excel cujo nome-base começa com 'saida' da pasta especificada.

    Retorna um DataFrame pandas. Em caso de nenhum arquivo válido, retorna DataFrame vazio.
    """
    pasta = _resolve_pasta_saidas(pasta_saidas)
    arquivos_saida = []
    allowed_exts = ('.xlsx', '.xls')
    if os.path.isdir(pasta):
        for f in os.listdir(pasta):
            name = f.strip()
            lower = name.lower()
            if lower.startswith('~$'):
                continue
            if not lower.startswith('saida'):
                continue
            if not lower.endswith(allowed_exts):
                continue
            arquivos_saida.append(os.path.join(pasta, f))

    dfs = []
    for arq in arquivos_saida:
        try:
            df = pd.read_excel(arq)
            df['__arquivo_origem'] = os.path.basename(arq)
            dfs.append(df)
        except Exception:
            # leitura silenciosa; arquivos corrompidos/ilegíveis são ignorados
            continue

    if not dfs:
        return pd.DataFrame()

    df_total = pd.concat(dfs, ignore_index=True)
    if 'data_hora' in df_total.columns:
        df_total['data_hora'] = pd.to_datetime(df_total['data_hora'], errors='coerce')
        df_total['dia'] = df_total['data_hora'].dt.date
    else:
        df_total['dia'] = None

    return df_total
