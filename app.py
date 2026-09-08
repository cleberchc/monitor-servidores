import json
import streamlit as st
import paramiko
from concurrent.futures import ThreadPoolExecutor, as_completed

st.set_page_config(page_title="Monitor de Servidores", layout="wide", page_icon="🖥️")

st.title("🖥️ Monitor de Carga de Servidores")

# Inicializa o estado dos servidores
if "servers" not in st.session_state:
    st.session_state.servers = []

# Sidebar para upload de JSON
st.sidebar.header("Configurações")
uploaded_file = st.sidebar.file_uploader("Carregar arquivo JSON de servidores", type=["json"])

if uploaded_file is not None:
    try:
        data = json.load(uploaded_file)
        st.session_state.servers = data
        st.sidebar.success(f"Carregados {len(data)} servidores com sucesso!")
    except Exception as e:
        st.sidebar.error(f"Erro ao ler arquivo JSON: {e}")

# Função para conectar SSH e pegar o loadavg
def fetch_server_load(server):
    host = server.get("host")
    user = server.get("user")
    password = server.get("password")
    key = server.get("key")
    port = int(server.get("port", 22))
    name = server.get("name", host)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        if password:
            client.connect(host, port=port, username=user, password=password, timeout=5)
        elif key:
            client.connect(host, port=port, username=user, key_filename=key, timeout=5)
        else:
            client.connect(host, port=port, username=user, timeout=5)

        stdin, stdout, stderr = client.exec_command("cat /proc/loadavg")
        output = stdout.read().decode().strip()
        client.close()

        if output:
            parts = output.split()
            load1, load5, load15 = parts[0], parts[1], parts[2]
            return {
                "name": name,
                "host": host,
                "status": "online",
                "load1": load1,
                "load5": load5,
                "load15": load15,
                "error": None
            }
        else:
            return {"name": name, "host": host, "status": "error", "error": "Resposta vazia do servidor"}
    except Exception as e:
        return {"name": name, "host": host, "status": "offline", "error": str(e)}

# Interface Principal
if not st.session_state.servers:
    st.info("Por favor, faça upload do arquivo JSON na barra lateral para iniciar o monitoramento.")
else:
    if st.button("🔄 Atualizar Cargas Agora", type="primary"):
        st.rerun()

    st.subheader("Status dos Servidores")

    # Executa as consultas SSH em paralelo
    results = []
    with st.spinner("Conectando aos servidores via SSH..."):
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(fetch_server_load, s) for s in st.session_state.servers]
            for future in as_completed(futures):
                results.append(future.result())

    # Exibe em colunas (cards)
    cols = st.columns(3)
    for idx, res in enumerate(results):
        col = cols[idx % 3]
        with col:
            with st.container(border=True):
                st.markdown(f"### 🖥️ {res['name']}")
                st.caption(f"Host: `{res['host']}`")

                if res["status"] == "online":
                    st.success("🟢 Online")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("1 min", res["load1"])
                    c2.metric("5 min", res["load5"])
                    c3.metric("15 min", res["load15"])
                else:
                    st.error(f"🔴 Offline / Erro")
                    st.caption(f"Detalhe: {res.get('error', 'Sem conexão')}")
