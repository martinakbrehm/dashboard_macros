"""
Launcher for the dashboard (moved inside relatorio_aproveitamento).
Opens a folder selection dialog to choose 'pasta_saidas', stores it in
.relatorio_aproveitamento/.dashboard_config.json and starts the dashboard
process with that path.

Usage: double-click this file or run `python run_dashboard_launcher.py`.
"""
import os
import sys
import json
import subprocess
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
except Exception:
    tk = None
import time
import urllib.request
import webbrowser

ROOT = os.path.abspath(os.path.dirname(__file__))
DASHBOARD_PY = os.path.join(ROOT, 'dashboard.py')
CONFIG_PATH = os.path.join(ROOT, '.dashboard_config.json')


def choose_folder():
    if tk is None:
        print('Tkinter not available; please run the dashboard with --pasta-saidas PATH')
        sys.exit(1)
    # Show a small instruction window before opening the folder dialog
    root = tk.Tk()
    root.title('Selecionar pasta de arquivos de saída')
    # keep window compact
    root.geometry('560x160')
    root.resizable(False, False)

    msg = (
        'Por favor, selecione a pasta que contém os arquivos de saída que o dashboard deve mapear.\n\n'
        'Depois de escolher a pasta, o dashboard será iniciado automaticamente e os arquivos desta pasta serão utilizados.'
    )
    lbl = tk.Label(root, text=msg, wraplength=520, justify='left')
    lbl.pack(padx=12, pady=(12,8), anchor='w')

    result = {'path': None}

    def on_choose():
        folder = filedialog.askdirectory(parent=root, title='Selecione a pasta de arquivos de saída (pasta_saidas)')
        if folder:
            result['path'] = folder
            root.destroy()

    def on_cancel():
        root.destroy()

    btn_frame = tk.Frame(root)
    btn_choose = tk.Button(btn_frame, text='Escolher pasta', width=16, command=on_choose)
    btn_choose.pack(side='left', padx=8)
    btn_cancel = tk.Button(btn_frame, text='Cancelar', width=12, command=on_cancel)
    btn_cancel.pack(side='left', padx=8)
    btn_frame.pack(pady=(6,12))

    # center the window on screen
    root.update_idletasks()
    x = (root.winfo_screenwidth() - root.winfo_width()) // 2
    y = (root.winfo_screenheight() - root.winfo_height()) // 3
    root.geometry(f'+{x}+{y}')

    root.mainloop()
    return result['path']


def save_config(path):
    data = {'pasta_saidas': path}
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print('Não foi possível salvar o arquivo de configuração:', e)


if __name__ == '__main__':
    folder = choose_folder()
    if not folder:
        print('Nenhuma pasta selecionada. Saindo.')
        sys.exit(0)
    folder = os.path.abspath(folder)
    save_config(folder)

    # Start the dashboard using the same Python interpreter
    cmd = [sys.executable, DASHBOARD_PY, '--pasta-saidas', folder]
    try:
        # Start in a new background process
        subprocess.Popen(cmd)
        print('Dashboard iniciado. Aguardando o servidor responder (abrindo no navegador automaticamente)...')
        # Poll the local server for readiness, then open the browser
        url = 'http://127.0.0.1:8050'
        for _ in range(30):  # ~15 seconds (30 * 0.5s)
            try:
                with urllib.request.urlopen(url, timeout=1) as r:
                    break
            except Exception:
                time.sleep(0.5)
        try:
            webbrowser.open(url)
            print(f'Abrindo {url} no navegador padrão.')
        except Exception:
            print(f'Servidor iniciado, mas não foi possível abrir o navegador automaticamente. Acesse: {url}')
    except Exception as e:
        print('Falha ao iniciar o dashboard:', e)
        sys.exit(1)
