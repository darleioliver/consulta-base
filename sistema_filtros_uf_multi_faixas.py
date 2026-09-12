import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st


# =========================================================
# CONFIGURAÇÃO
# =========================================================

st.set_page_config(
    page_title="Consulta da Base",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Consulta da Base de Contatos")
st.caption(
    "Consulta com múltiplos Estados, CBOs, Cidades e Faixas de renda."
)


# =========================================================
# LOCALIZAR BANCO SQLITE
# =========================================================

PASTA_SCRIPT = Path(__file__).resolve().parent

bancos = sorted(
    list(PASTA_SCRIPT.glob("*.sqlite")) +
    list(PASTA_SCRIPT.glob("*.db"))
)

if not bancos:
    st.error(
        "Nenhum arquivo .sqlite ou .db foi encontrado na mesma pasta."
    )
    st.info(
        "Coloque o base_contagens.sqlite na mesma pasta "
        "do sistema_filtros_uf.py e atualize a página."
    )
    st.stop()

if len(bancos) == 1:
    BANCO = bancos[0]
else:
    BANCO = Path(
        st.selectbox(
            "Banco de dados",
            bancos,
            format_func=lambda p: p.name
        )
    )

st.success(f"✅ Base carregada: {BANCO.name}")


# =========================================================
# CONEXÃO
# =========================================================

def conectar():
    uri = BANCO.resolve().as_uri() + "?mode=ro"

    conn = sqlite3.connect(
        uri,
        uri=True,
        timeout=30
    )

    conn.execute("PRAGMA query_only = ON;")
    conn.execute("PRAGMA busy_timeout = 30000;")

    try:
        yield conn
    finally:
        conn.close()


def consulta_valor(sql, params=()):
    for conn in conectar():
        resultado = conn.execute(
            sql,
            params
        ).fetchone()

        if not resultado or resultado[0] is None:
            return 0

        return int(resultado[0])


def consulta_df(sql, params=()):
    for conn in conectar():
        return pd.read_sql_query(
            sql,
            conn,
            params=params
        )


# =========================================================
# VALIDAR BANCO
# =========================================================

for conn in conectar():
    tabelas = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }


necessarias = {
    "contagem_uf",
    "contagem_cbo",
    "contagem_cidade",
    "contagem_faixa",

    "contagem_uf_cbo",
    "contagem_uf_cidade",
    "contagem_uf_faixa",

    "contagem_cbo_cidade",
    "contagem_cbo_faixa",
    "contagem_cidade_faixa",
    "contagem_completa",

    "contagem_uf_cbo_cidade",
    "contagem_uf_cbo_faixa",
    "contagem_uf_cidade_faixa",
    "contagem_uf_completa",

    "resumo_arquivos",
}


faltando = necessarias - tabelas

if faltando:
    st.error(
        "Esse banco está incompleto para os filtros múltiplos."
    )
    st.write("Tabelas faltando:")
    st.code("\n".join(sorted(faltando)))
    st.info(
        "Gere novamente o base_contagens.sqlite usando "
        "gerar_relatorio_com_uf.py."
    )
    st.stop()


# =========================================================
# CARREGAR OPÇÕES
# =========================================================

@st.cache_data(show_spinner=False)
def carregar_lista(
    caminho_banco,
    tabela,
    coluna,
    numerico=False
):
    uri = Path(
        caminho_banco
    ).resolve().as_uri() + "?mode=ro"

    conn = sqlite3.connect(
        uri,
        uri=True,
        timeout=30
    )

    try:
        if numerico:
            sql = f"""
                SELECT {coluna}
                FROM {tabela}
                WHERE {coluna} IS NOT NULL
                  AND TRIM({coluna}) <> ''
                ORDER BY
                    CASE
                        WHEN {coluna} GLOB '[0-9]*'
                        THEN CAST({coluna} AS INTEGER)
                        ELSE 999999999
                    END,
                    {coluna}
            """
        else:
            sql = f"""
                SELECT {coluna}
                FROM {tabela}
                WHERE {coluna} IS NOT NULL
                  AND TRIM({coluna}) <> ''
                ORDER BY {coluna}
            """

        df = pd.read_sql_query(
            sql,
            conn
        )

        return (
            df[coluna]
            .astype(str)
            .tolist()
        )

    finally:
        conn.close()


@st.cache_data(show_spinner=False)
def carregar_cidades_por_ufs(
    caminho_banco,
    ufs_tuple
):
    """
    Sem UF selecionada:
        mostra todas as cidades.

    Com uma ou várias UFs:
        mostra somente as cidades pertencentes às UFs selecionadas.
    """

    uri = Path(
        caminho_banco
    ).resolve().as_uri() + "?mode=ro"

    conn = sqlite3.connect(
        uri,
        uri=True,
        timeout=30
    )

    try:
        if not ufs_tuple:
            sql = """
                SELECT cidade
                FROM contagem_cidade
                WHERE cidade IS NOT NULL
                  AND TRIM(cidade) <> ''
                ORDER BY cidade
            """

            params = ()

        else:
            placeholders = ", ".join(
                ["?"] * len(ufs_tuple)
            )

            sql = f"""
                SELECT DISTINCT cidade
                FROM contagem_uf_cidade
                WHERE uf IN ({placeholders})
                  AND cidade IS NOT NULL
                  AND TRIM(cidade) <> ''
                ORDER BY cidade
            """

            params = tuple(ufs_tuple)

        df = pd.read_sql_query(
            sql,
            conn,
            params=params
        )

        return (
            df["cidade"]
            .astype(str)
            .tolist()
        )

    finally:
        conn.close()


try:
    ufs = carregar_lista(
        str(BANCO),
        "contagem_uf",
        "uf"
    )

    cbos = carregar_lista(
        str(BANCO),
        "contagem_cbo",
        "cbo"
    )

    faixas = carregar_lista(
        str(BANCO),
        "contagem_faixa",
        "faixa_renda_id",
        numerico=True
    )

except Exception as erro:
    st.error("Não foi possível carregar os filtros.")
    st.exception(erro)
    st.stop()



# =========================================================
# DESCRIÇÃO DAS FAIXAS DE RENDA
# =========================================================

FAIXAS_RENDA_DESCRICAO = {
    "1": "R$ 0 até R$ 999",
    "2": "R$ 1.000 até R$ 1.499",
    "3": "R$ 1.500 até R$ 1.999",
    "4": "R$ 2.000 até R$ 2.499",
    "5": "R$ 2.500 até R$ 2.999",
    "6": "R$ 3.000 até R$ 3.999",
    "7": "R$ 4.000 até R$ 4.999",
    "8": "R$ 5.000 até R$ 5.999",
    "9": "R$ 6.000 até R$ 6.999",
    "10": "R$ 7.000 até R$ 7.999",
    "11": "R$ 8.000 até R$ 8.999",
    "12": "R$ 9.000 até R$ 20.000",
}


def formatar_faixa_renda(valor):
    valor = str(valor)
    descricao = FAIXAS_RENDA_DESCRICAO.get(valor)

    if descricao:
        return f"{valor} — {descricao}"

    return valor


# =========================================================
# SESSION STATE
# =========================================================

if "filtro_ufs" not in st.session_state:
    st.session_state.filtro_ufs = []

if "filtro_cbos" not in st.session_state:
    st.session_state.filtro_cbos = []

if "filtro_cidades" not in st.session_state:
    st.session_state.filtro_cidades = []

if "filtro_faixas" not in st.session_state:
    st.session_state.filtro_faixas = []


def limpar_filtros():
    st.session_state.filtro_ufs = []
    st.session_state.filtro_cbos = []
    st.session_state.filtro_cidades = []
    st.session_state.filtro_faixas = []


# =========================================================
# FILTROS
# =========================================================

st.subheader("🔎 Filtros")

col1, col2, col3, col4, col5 = st.columns(
    [1.25, 1.45, 2.5, 1.45, 0.8]
)


# ---------------------------------------------------------
# ESTADOS - múltipla seleção
# ---------------------------------------------------------

with col1:
    ufs_selecionadas = st.multiselect(
        "Estados (UF)",
        ufs,
        key="filtro_ufs",
        placeholder="Todos os estados"
    )


# ---------------------------------------------------------
# CIDADES - dependem das UFs selecionadas
# ---------------------------------------------------------

cidades_disponiveis = carregar_cidades_por_ufs(
    str(BANCO),
    tuple(ufs_selecionadas)
)


# Remove automaticamente cidades que não pertencem
# mais aos estados selecionados.
st.session_state.filtro_cidades = [
    cidade
    for cidade in st.session_state.filtro_cidades
    if cidade in cidades_disponiveis
]


# ---------------------------------------------------------
# CBO - múltipla seleção
# ---------------------------------------------------------

with col2:
    cbos_selecionados = st.multiselect(
        "CBOs",
        cbos,
        key="filtro_cbos",
        placeholder="Todos os CBOs"
    )


# ---------------------------------------------------------
# CIDADES - múltipla seleção
# ---------------------------------------------------------

with col3:
    cidades_selecionadas = st.multiselect(
        "Cidades",
        cidades_disponiveis,
        key="filtro_cidades",
        placeholder="Todas as cidades"
    )


# ---------------------------------------------------------
# FAIXA DE RENDA - múltipla seleção
# ---------------------------------------------------------

with col4:
    faixas_selecionadas = st.multiselect(
        "Faixas de renda",
        faixas,
        key="filtro_faixas",
        placeholder="Todas as faixas",
        format_func=formatar_faixa_renda
    )


with col5:
    st.write("")
    st.write("")

    st.button(
        "🧹 Limpar",
        on_click=limpar_filtros,
        use_container_width=True
    )


# =========================================================
# CONSULTA
# =========================================================

def consultar_quantidade(
    ufs_selecionadas,
    cbos_selecionados,
    cidades_selecionadas,
    faixas_selecionadas
):

    ativos = {}

    if ufs_selecionadas:
        ativos["uf"] = ufs_selecionadas

    if cbos_selecionados:
        ativos["cbo"] = cbos_selecionados

    if cidades_selecionadas:
        ativos["cidade"] = cidades_selecionadas

    if faixas_selecionadas:
        ativos["faixa_renda_id"] = faixas_selecionadas


    # -----------------------------------------------------
    # NENHUM FILTRO
    # -----------------------------------------------------

    if not ativos:
        return consulta_valor(
            """
            SELECT COALESCE(
                SUM(linhas_processadas),
                0
            )
            FROM resumo_arquivos
            WHERE status = 'OK'
            """
        )


    # -----------------------------------------------------
    # DESCOBRE QUAL TABELA USAR
    # -----------------------------------------------------

    chave = tuple(
        campo
        for campo in (
            "uf",
            "cbo",
            "cidade",
            "faixa_renda_id"
        )
        if campo in ativos
    )


    mapa_tabelas = {
        ("uf",):
            "contagem_uf",

        ("cbo",):
            "contagem_cbo",

        ("cidade",):
            "contagem_cidade",

        ("faixa_renda_id",):
            "contagem_faixa",


        ("uf", "cbo"):
            "contagem_uf_cbo",

        ("uf", "cidade"):
            "contagem_uf_cidade",

        ("uf", "faixa_renda_id"):
            "contagem_uf_faixa",

        ("cbo", "cidade"):
            "contagem_cbo_cidade",

        ("cbo", "faixa_renda_id"):
            "contagem_cbo_faixa",

        ("cidade", "faixa_renda_id"):
            "contagem_cidade_faixa",


        ("uf", "cbo", "cidade"):
            "contagem_uf_cbo_cidade",

        ("uf", "cbo", "faixa_renda_id"):
            "contagem_uf_cbo_faixa",

        ("uf", "cidade", "faixa_renda_id"):
            "contagem_uf_cidade_faixa",

        ("cbo", "cidade", "faixa_renda_id"):
            "contagem_completa",


        (
            "uf",
            "cbo",
            "cidade",
            "faixa_renda_id"
        ):
            "contagem_uf_completa",
    }


    tabela = mapa_tabelas.get(
        chave
    )

    if tabela is None:
        return 0


    # -----------------------------------------------------
    # MONTA WHERE COM IN PARA TODOS OS FILTROS
    # -----------------------------------------------------

    clausulas = []
    params = []

    for campo in chave:

        valores = ativos[campo]

        placeholders = ", ".join(
            ["?"] * len(valores)
        )

        clausulas.append(
            f"{campo} IN ({placeholders})"
        )

        params.extend(
            valores
        )


    sql = f"""
        SELECT COALESCE(
            SUM(quantidade),
            0
        )
        FROM {tabela}
        WHERE {" AND ".join(clausulas)}
    """


    return consulta_valor(
        sql,
        tuple(params)
    )


try:
    quantidade = consultar_quantidade(
        ufs_selecionadas,
        cbos_selecionados,
        cidades_selecionadas,
        faixas_selecionadas
    )

except Exception as erro:
    st.error(
        "A consulta falhou, mas o sistema permaneceu aberto."
    )
    st.exception(erro)
    st.stop()


# =========================================================
# RESULTADO
# =========================================================

st.divider()

r1, r2 = st.columns(
    [1, 3]
)


with r1:
    st.metric(
        "Contatos encontrados",
        f"{quantidade:,}".replace(",", ".")
    )


def resumir_selecao(
    valores,
    texto_todos,
    limite=5
):
    if not valores:
        return texto_todos

    if len(valores) <= limite:
        return ", ".join(
            valores
        )

    primeiros = ", ".join(
        valores[:limite]
    )

    restantes = (
        len(valores) - limite
    )

    return (
        f"{primeiros} "
        f"(+{restantes})"
    )


with r2:
    st.write(
        "**Filtros aplicados:**"
    )

    texto_ufs = resumir_selecao(
        ufs_selecionadas,
        "TODOS"
    )

    texto_cbos = resumir_selecao(
        cbos_selecionados,
        "TODOS"
    )

    texto_cidades = resumir_selecao(
        cidades_selecionadas,
        "TODAS"
    )

    texto_faixas = resumir_selecao(
        faixas_selecionadas,
        "TODAS"
    )

    st.write(
        f"Estados: **{texto_ufs}**  |  "
        f"CBOs: **{texto_cbos}**  |  "
        f"Cidades: **{texto_cidades}**  |  "
        f"Faixas: **{texto_faixas}**"
    )


# =========================================================
# RANKINGS
# =========================================================

st.divider()

col_a, col_b, col_c = st.columns(3)


def formatar_df_ranking(df):
    if (
        not df.empty
        and "Contatos" in df.columns
    ):
        df["Contatos"] = (
            df["Contatos"]
            .apply(
                lambda x:
                f"{int(x):,}".replace(",", ".")
            )
        )

    return df


try:

    # -----------------------------------------------------
    # ESTADOS
    # -----------------------------------------------------

    with col_a:
        st.subheader(
            "🗺️ Estados"
        )

        if not ufs_selecionadas:

            top_uf = consulta_df(
                """
                SELECT
                    uf AS UF,
                    quantidade AS Contatos
                FROM contagem_uf
                ORDER BY quantidade DESC
                LIMIT 27
                """
            )

        else:

            placeholders = ", ".join(
                ["?"] * len(ufs_selecionadas)
            )

            top_uf = consulta_df(
                f"""
                SELECT
                    uf AS UF,
                    quantidade AS Contatos
                FROM contagem_uf
                WHERE uf IN ({placeholders})
                ORDER BY quantidade DESC
                """,
                tuple(ufs_selecionadas)
            )

        st.dataframe(
            formatar_df_ranking(top_uf),
            use_container_width=True,
            hide_index=True
        )


    # -----------------------------------------------------
    # CIDADES
    # -----------------------------------------------------

    with col_b:
        st.subheader(
            "🏙️ Cidades"
        )

        if not ufs_selecionadas:

            top_cidades = consulta_df(
                """
                SELECT
                    cidade AS Cidade,
                    quantidade AS Contatos
                FROM contagem_cidade
                ORDER BY quantidade DESC
                LIMIT 20
                """
            )

        else:

            placeholders = ", ".join(
                ["?"] * len(ufs_selecionadas)
            )

            top_cidades = consulta_df(
                f"""
                SELECT
                    cidade AS Cidade,
                    SUM(quantidade) AS Contatos
                FROM contagem_uf_cidade
                WHERE uf IN ({placeholders})
                GROUP BY cidade
                ORDER BY Contatos DESC
                LIMIT 20
                """,
                tuple(ufs_selecionadas)
            )

        st.dataframe(
            formatar_df_ranking(top_cidades),
            use_container_width=True,
            hide_index=True
        )


    # -----------------------------------------------------
    # CBOS
    # -----------------------------------------------------

    with col_c:
        st.subheader(
            "💼 CBOs"
        )

        if not ufs_selecionadas:

            top_cbos = consulta_df(
                """
                SELECT
                    cbo AS CBO,
                    quantidade AS Contatos
                FROM contagem_cbo
                ORDER BY quantidade DESC
                LIMIT 20
                """
            )

        else:

            placeholders = ", ".join(
                ["?"] * len(ufs_selecionadas)
            )

            top_cbos = consulta_df(
                f"""
                SELECT
                    cbo AS CBO,
                    SUM(quantidade) AS Contatos
                FROM contagem_uf_cbo
                WHERE uf IN ({placeholders})
                GROUP BY cbo
                ORDER BY Contatos DESC
                LIMIT 20
                """,
                tuple(ufs_selecionadas)
            )

        st.dataframe(
            formatar_df_ranking(top_cbos),
            use_container_width=True,
            hide_index=True
        )


except Exception as erro:
    st.warning(
        "Não foi possível carregar um dos rankings."
    )
    st.exception(erro)


# =========================================================
# RODAPÉ
# =========================================================

st.caption(
    "Filtros múltiplos: Estados, CBOs, Cidades e Faixas de renda. "
    "Ao escolher um ou mais estados, a lista de cidades é limitada "
    "automaticamente às cidades desses estados."
)
