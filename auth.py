# -*- coding: utf-8 -*-
"""
Proteção por senha do dashboard.

COMO FUNCIONA
    Segue o padrão recomendado na documentação do Streamlit: a senha fica em
    `st.secrets`, nunca no código nem no repositório, e a comparação usa
    `hmac.compare_digest` em vez de `==`. A diferença importa: o `==` de strings
    em Python sai no primeiro caractere diferente, e o tempo de resposta vaza
    quantos caracteres iniciais estão certos. O `compare_digest` gasta o mesmo
    tempo em qualquer caso.

    O estado fica em `st.session_state`, então quem acerta a senha continua
    autenticado enquanto a aba do navegador estiver aberta. A senha digitada é
    apagada do estado logo após a verificação, para não ficar guardada na sessão.

ONDE COLOCAR A SENHA
    Local:      `.streamlit/secrets.toml` (está no .gitignore)
    Hospedagem: painel do app no Streamlit Community Cloud, em Settings > Secrets

    Formato, nos dois casos:

        senha = "sua-senha-aqui"

O QUE ELA PROTEGE
    Protege o acesso ao dashboard, e apenas isso. Se o repositório for público,
    a planilha dentro dele continua pública, senha ou não. A recomendação sobre
    isso está no README.
"""

import hmac

import streamlit as st

CHAVE_SESSAO = "autenticado"
CHAVE_ERRO = "senha_incorreta"
CHAVE_CAMPO = "campo_senha"


def _senha_configurada() -> str | None:
    """
    Lê a senha de `st.secrets`, aceitando as chaves 'senha' e 'password'.

    Devolve None quando não há segredo configurado. Acessar `st.secrets` sem
    arquivo de segredos levanta exceção, daí o try.
    """
    try:
        for chave in ("senha", "password"):
            if chave in st.secrets:
                # O strip aqui e o do lado digitado se espelham: senha colada
                # de um e-mail costuma vir com espaço ou quebra de linha grudada.
                valor = str(st.secrets[chave]).strip()
                if valor:
                    return valor
    except Exception:
        return None
    return None


def _verificar() -> None:
    """
    Verifica a senha digitada. É chamada tanto pelo Enter no campo quanto pelo
    botão Entrar.

    Os dois primeiros ifs existem por causa de um detalhe do Streamlit: quando o
    usuário digita e clica no botão, o `on_change` do campo dispara ANTES do
    `on_click` do botão, na mesma execução. Sem as guardas, a primeira chamada
    autenticava e limpava o campo, e a segunda relia o campo agora vazio e
    marcava "senha incorreta" por cima do sucesso. Quem apertava Enter entrava;
    quem clicava no botão não.
    """
    if st.session_state.get(CHAVE_SESSAO, False):
        return  # já autenticado nesta execução: nada a refazer
    digitada = st.session_state.get(CHAVE_CAMPO, "").strip()
    if not digitada:
        return  # campo vazio não é tentativa, então não marca erro

    esperada = _senha_configurada()
    # Comparação em bytes: `compare_digest` recusa str com caractere fora do
    # ASCII, e uma senha com acento levantaria exceção em vez de simplesmente
    # não bater. O tempo constante é preservado.
    ok = bool(esperada) and hmac.compare_digest(
        digitada.encode("utf-8"), esperada.encode("utf-8")
    )
    st.session_state[CHAVE_SESSAO] = ok
    st.session_state[CHAVE_ERRO] = not ok
    # A senha digitada não fica guardada na sessão depois da verificação.
    st.session_state[CHAVE_CAMPO] = ""


def _estilo_login() -> None:
    """Estilo da tela de entrada, no mesmo tom do restante do painel."""
    st.markdown(
        """
        <style>
          [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none; }
          .block-container { padding-top: 5rem; max-width: 560px; }
          .login-topo { border-left: 4px solid #1c4b82; padding-left: 1rem; margin-bottom: 1.6rem; }
          .login-titulo { font-size: 1.45rem; font-weight: 700; color: #10131a; line-height: 1.25; }
          .login-sub { font-size: 0.95rem; color: #5a6270; margin-top: 0.35rem; line-height: 1.5; }
          .login-rodape { font-size: 0.8rem; color: #8a8f98; margin-top: 2rem; line-height: 1.5;
                          border-top: 1px solid #e3e8ee; padding-top: 0.9rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def exigir_senha() -> None:
    """
    Bloqueia a execução enquanto a senha não for informada corretamente.

    Deve ser chamada logo depois de `st.set_page_config`, antes de qualquer
    leitura de dado: o `st.stop()` interrompe o script inteiro, então nada do
    conteúdo protegido chega a ser processado nem enviado ao navegador.
    """
    if st.session_state.get(CHAVE_SESSAO, False):
        return

    _estilo_login()

    st.markdown(
        '<div class="login-topo">'
        '<div class="login-titulo">Anomalias de Faturamento</div>'
        '<div class="login-sub">Dashboard gerencial · acesso restrito</div>'
        "</div>",
        unsafe_allow_html=True,
    )

    if _senha_configurada() is None:
        st.error(
            "Este dashboard ainda não tem senha configurada, e por isso está bloqueado.",
            icon="🔒",
        )
        st.markdown(
            "Para liberar o acesso, defina o segredo `senha`:\n\n"
            "- **Rodando local:** crie o arquivo `.streamlit/secrets.toml` com a linha "
            "`senha = \"sua-senha\"`. Há um modelo em `.streamlit/secrets.toml.example`.\n"
            "- **No Streamlit Community Cloud:** abra o app, vá em "
            "**Settings › Secrets** e cole a mesma linha."
        )
        st.stop()

    st.text_input(
        "Senha de acesso",
        type="password",
        key=CHAVE_CAMPO,
        on_change=_verificar,
        placeholder="Digite a senha",
    )
    st.button("Entrar", on_click=_verificar, type="primary")

    if st.session_state.get(CHAVE_ERRO, False):
        st.error("Senha incorreta. Tente novamente.", icon="⚠️")

    st.markdown(
        '<div class="login-rodape">'
        "Análise das retenções de faturamento do período, com diagnóstico, "
        "achados de qualidade de dado e recomendações. Se você deveria ter acesso "
        "e não tem a senha, peça a quem enviou o link."
        "</div>",
        unsafe_allow_html=True,
    )
    st.stop()


def botao_sair(container=None) -> None:
    """Encerra a sessão autenticada. Fica na barra lateral do painel."""
    alvo = container if container is not None else st
    if alvo.button("Sair", width="stretch"):
        st.session_state[CHAVE_SESSAO] = False
        st.session_state[CHAVE_ERRO] = False
        st.rerun()
