import streamlit as st
from langchain_openai import ChatOpenAI
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory


def get_ai_response(memory, user_prompt, system_prompt="", model_name='gpt-4o-mini',
                    temperature=0.2, top_p=0.1, frequency_penalty=0, max_tokens=512):
    """
    通用AI响应生成函数

    Args:
        memory: 会话记忆
        user_prompt: 用户提示
        system_prompt: 系统提示
        model_name: 模型名称
        temperature: 温度参数
        top_p: 百分比排名参数
        frequency_penalty: 频率惩罚力度
        max_tokens: 最大token数量

    Returns:
        AI响应
    """
    try:
        if not st.session_state.API_KEY:
            return "请先在侧边栏输入有效的API密钥"

        model = ChatOpenAI(
            model=model_name,
            api_key=st.secrets['API_KEY'],
            base_url='https://api.openai.com/v1',
            temperature=temperature,
            max_tokens=max_tokens
        )
        chain = ConversationChain(llm=model, memory=memory)
        full_prompt = f"System: {system_prompt}\nUser: {user_prompt}"
        response = chain.invoke({'input': full_prompt})['response']
        return response
    except Exception as e:
        st.error(f"AI请求失败，请检查您的网络连接或API密钥配置。错误信息：{str(e)}")
        return "无法生成响应，请检查配置"


def get_ai_response(client, *, sys_prompt='', user_prompt='', model_name='gpt-4o-mini',
                     temperature=0.2, top_p=0.1, frequency_penalty=0, max_tokens=512):
    """
    获取大模型API响应

    :param client: OpenAI客户端
    :param sys_prompt: 系统提示词
    :param user_prompt: 用户提示词
    :param model_name: 模型名称
    :param temperature: 温度参数（0~2）
    :param top_p: 百分比排名参数（0~1）
    :param frequency_penalty: 频率惩罚力度（-2~2）
    :param max_tokens: 最大token数量
    :return: 响应的内容
    """
    messages = []
    if sys_prompt:
        messages.append({'role': 'system', 'content': sys_prompt})
    if user_prompt:
        messages.append({'role': 'user', 'content': user_prompt})
    response = client.chat.completions.create(
        model=model_name,
        temperature=temperature,
        top_p=top_p,
        frequency_penalty=frequency_penalty,
        messages=messages,
        max_tokens=max_tokens,
        stream=False
    )
    return response.choices[0].message.content


def render_chat():
    """渲染聊天模块"""
    st.header("💬 智能聊天")

    # 显示消息历史
    for msg in st.session_state.chat_messages:
        role = "user" if msg["role"] == "human" else "assistant"
        with st.chat_message(role):
            st.write(msg["content"])

    # 处理用户输入
    if prompt := st.chat_input("请输入您的问题..."):
        handle_chat_input(prompt)


def handle_chat_input(prompt):
    """
    处理聊天输入

    Args:
        prompt: 用户输入的提示
    """
    if not st.session_state.API_KEY:
        st.warning("🔑 请先在侧边栏输入API密钥")
        return

    # 添加用户消息
    st.session_state.chat_messages.append({'role': 'human', 'content': prompt})

    # 获取AI响应
    with st.spinner('思考中...'):
        response = get_ai_response(
            memory=st.session_state.chat_memory,
            user_prompt=prompt,
            system_prompt=st.session_state.system_prompt
        )

    # 添加AI响应
    st.session_state.chat_messages.append({'role': 'ai', 'content': response})
    st.rerun()