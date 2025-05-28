import streamlit as st
from modules.chat import render_chat, handle_chat_input, get_ai_response
from modules.document_qa import render_document_qa
from modules.data_analysis import render_data_analysis
from utils.session import init_session_state
from utils.file_handler import handle_uploaded_file, render_history, clear_current_history


def render_sidebar():
    """渲染侧边栏"""
    with st.sidebar:
        st.title("⚙️ 控制面板")

        # 模型配置
        st.subheader("模型设置")
        st.session_state.selected_model = st.selectbox(
            "AI模型",
            ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo", "gpt-4"],
            index=0,
            help="选择要使用的AI模型"
        )
        st.session_state.model_temperature = st.slider(
            "温度值",
            0.0, 1.0, 0.7, 0.1,
            help="控制回答的创造性（0=保守，1=创新）"
        )
        st.session_state.model_max_length = st.slider(
            "最大长度",
            100, 2000, 1000,
            help="控制回答的最大长度"
        )
        st.session_state.system_prompt = st.text_area(
            "系统提示词",
            "你是一个专业的人工智能助手，用中文简洁准确地回答问题",
            height=100
        )

        # 文件上传
        st.subheader("数据管理")
        uploaded_file = st.file_uploader(
            "上传文件（支持CSV/Excel/TXT）",
            type=["csv", "xlsx", "txt"],
            help="根据当前模式自动处理文件类型"
        )
        handle_uploaded_file(uploaded_file)

        # 历史消息
        st.subheader("对话历史")
        render_history()

        if st.button("🗑️ 清空当前历史"):
            clear_current_history()


def main():
    """主应用逻辑"""
    init_session_state()

    # 页面标题
    st.markdown("""
        <div style="text-align:center; margin-bottom:40px">
            <h1 style="margin-bottom:0">SuperAI 智能分析助手🚀</h1>
            <p style="color:#6C63FF; font-size:1.2rem">数据洞察从未如此简单</p>
        </div>
    """, unsafe_allow_html=True)

    # 渲染侧边栏
    render_sidebar()

    # 模式选择
    st.session_state.current_mode = st.sidebar.radio(
        "功能导航",
        ["💬 智能聊天", "📚 文档问答", "📊 数据分析"],
        horizontal=True,
        label_visibility="collapsed"
    )

    # 路由到对应模块
    if st.session_state.current_mode == "💬 智能聊天":
        render_chat()
    elif st.session_state.current_mode == "📚 文档问答":
        render_document_qa()
    elif st.session_state.current_mode == "📊 数据分析":
        render_data_analysis()


if __name__ == "__main__":
    main()