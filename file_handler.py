import streamlit as st
import pandas as pd
from langchain_core.messages import HumanMessage


def handle_uploaded_file(file):
    """
    处理上传的文件

    Args:
        file: 上传的文件对象
    """
    if not file:
        return

    try:
        file_type = file.name.split('.')[-1]

        # 处理数据文件
        if file_type in ['csv', 'xlsx']:
            df = pd.read_csv(file) if file_type == 'csv' else pd.read_excel(file)
            st.session_state.data_df = df
            st.success("数据加载成功！")
            st.dataframe(df.head(8), use_container_width=True, height=300)

        # 处理文本文件
        elif file_type == 'txt':
            if st.session_state.current_mode == "📚 文档问答":
                st.session_state.is_new_file = True
                with open(f'{st.session_state.session_id}.txt', 'w', encoding='utf-8') as f:
                    f.write(file.read().decode('utf-8'))
                st.success("文档上传成功！")
            else:
                st.session_state.txt_content = file.read().decode('utf-8')
                st.text_area("文本内容", st.session_state.txt_content, height=300)

    except Exception as e:
        st.error(f"文件处理失败：{str(e)}")


def render_history():
    """渲染历史记录，并在失败时提供用户友好的提示"""
    try:
        current_history = []
        if st.session_state.current_mode == "💬 智能聊天":
            # 获取聊天模式下的历史记录
            current_history = [msg["content"] for msg in st.session_state.chat_messages if msg["role"] == "human"]
        elif st.session_state.current_mode == "📚 文档问答":
            # 获取文档问答模式下的历史记录
            rag_memory = st.session_state.get('rag_memory')
            if rag_memory is not None:
                chat_history = rag_memory.load_memory_variables({}).get('chat_history', [])
                current_history = [msg.content for msg in chat_history if isinstance(msg, HumanMessage)]
            else:
                current_history = []

        if current_history:
            # 显示历史记录选择框
            selected = st.selectbox(
                "选择历史记录",
                options=[msg[:30] + "..." for msg in current_history],
                key="history_select"
            )
            if selected:
                st.write(f"**选中记录**: {selected}")
        else:
            st.write("暂无历史记录")
    except Exception as e:
        # 捕获异常并显示友好提示
        st.error(f"加载历史记录时遇到问题：{str(e)}。请尝试刷新页面或重新启动应用。")
        st.caption("提示：如果问题持续存在，请检查应用日志以获取更多详细信息。")


def clear_current_history():
    try:
        if st.session_state.current_mode == "💬 智能聊天":
            st.session_state.chat_messages = [{'role': 'ai', 'content': '你好！我是您的智能助手，请问有什么可以帮您？'}]
            st.session_state.chat_memory.clear()
        elif st.session_state.current_mode == "📚 文档问答":
            st.session_state.rag_memory.clear()
        elif st.session_state.current_mode == "📊 数据分析":
            st.session_state.data_memory.clear()
        st.success("当前模式历史记录已清除！")
    except Exception as e:
        st.error(f"清空历史失败：{str(e)}")