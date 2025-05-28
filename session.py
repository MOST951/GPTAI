import streamlit as st


def init_session_state():
    """初始化所有会话状态"""
    if 'current_mode' not in st.session_state:
        st.session_state.current_mode = "💬 智能聊天"

    # 聊天模块状态
    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = [{'role': 'ai', 'content': '你好！我是您的智能助手，请问有什么可以帮您？'}]
    if 'chat_memory' not in st.session_state:
        st.session_state.chat_memory = None

    # 文档问答模块状态
    if 'rag_memory' not in st.session_state:
        st.session_state.rag_memory = None
    if 'session_id' not in st.session_state:
        st.session_state.session_id = None
    if 'rag_db' not in st.session_state:
        st.session_state.rag_db = None
    if 'is_new_file' not in st.session_state:
        st.session_state.is_new_file = True

    # 数据分析模块状态
    if 'data_memory' not in st.session_state:
        st.session_state.data_memory = None
    if 'data_df' not in st.session_state:
        st.session_state.data_df = None