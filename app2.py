import json
import re
import time
import uuid
import pandas as pd
import streamlit as st
import plotly.express as px
import sys
import os
import ssl
from langchain.chains.conversation.base import ConversationChain
from langchain.chains.conversational_retrieval.base import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain_openai import ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent
from langchain.embeddings.huggingface import HuggingFaceEmbeddings

# 设置环境变量
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["LANG"] = "C.UTF-8"
os.environ["LC_ALL"] = "C.UTF-8"
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# 创建自定义SSL上下文以解决证书问题
custom_ssl_context = ssl.create_default_context()
custom_ssl_context.check_hostname = False
custom_ssl_context.verify_mode = ssl.CERT_NONE


# ============================================================
# 文件上传处理功能
# ============================================================
def process_uploaded_file(uploaded_file):
    """处理上传的文件"""
    try:
        file_ext = uploaded_file.name.split(".")[-1].lower()
        session_id = str(uuid.uuid4())

        if file_ext in ["csv", "xlsx"]:
            if file_ext == "csv":
                st.session_state.data_df = pd.read_csv(uploaded_file)
                st.session_state.current_mode = "📊 数据分析"
                st.success("CSV文件已成功加载！")
            else:  # xlsx
                excel_file = pd.ExcelFile(uploaded_file)
                sheet_names = excel_file.sheet_names

                if 'selected_sheet' not in st.session_state:
                    st.session_state.selected_sheet = sheet_names[0] if sheet_names else None

                if st.session_state.selected_sheet not in sheet_names:
                    st.session_state.selected_sheet = sheet_names[0] if sheet_names else None

                with st.sidebar:
                    st.subheader("Excel工作表选择")
                    if sheet_names:
                        current_index = sheet_names.index(
                            st.session_state.selected_sheet) if st.session_state.selected_sheet in sheet_names else 0

                        selected_sheet = st.selectbox(
                            "请选择要分析的工作表",
                            sheet_names,
                            index=current_index
                        )

                        st.session_state.selected_sheet = selected_sheet
                        st.session_state.data_df = excel_file.parse(selected_sheet)
                        st.session_state.current_mode = "📊 数据分析"
                        st.success(f"Excel文件的工作表 '{selected_sheet}' 已成功加载！")
                    else:
                        st.error("Excel文件中没有找到任何工作表！")

        elif file_ext == "txt":
            content = uploaded_file.read().decode("utf-8")
            st.session_state.txt_content = content
            st.session_state.session_id = session_id
            st.session_state.is_new_file = True
            st.session_state.current_mode = "📚 文档问答"
            st.success("文本文件已成功上传！")

        else:
            st.error("不支持的文件类型！")

    except Exception as e:
        st.error(f"文件处理失败: {str(e)}")


# ============================================================
# 提示词模板
# ============================================================
# 数据框代理提示词模板 - 优化版
DF_AGENT_PROMPT_TEMPLATE = """
你是一个数据分析专家，请根据以下数据框和用户问题提供回答。
必须严格按照指定格式回复，否则系统将无法解析！

**数据框预览**:
{df_head}

**用户问题**: {query}

**响应格式要求**:
- 纯文本回答 (如果没有可视化需求)
- 或JSON格式 (如果需要展示图表):
{{
    "answer": "详细文本解释(解释用户问题)和统计结果:",
    "charts": [
        {{
            "type": "bar/line/pie/scatter/box/hist/area",
            "data": {{"columns": ["类别A", "类别B", ...], "data": [数值1, 数值2, ...]}},
            "title": "图表标题 (可选)"
        }}
    ]
}}

**重要规则**:
1. 处理日期时使用 'ME' 代替 'M'
2. 如果遇到错误，返回 JSON 格式的错误信息: {{"error": "错误描述", "answer": "错误信息"}}
3. 不要包含任何额外解释或代码
4. 用户没有明确要求图表时，请仅返回文本答案
5. 不要返回数据预览内容，用户已经在上传文件时看到数据预览
6. 对于需要代码计算的问题，使用以下格式调用工具:
   Thought: 分析问题并确定需要使用的工具
   Action: python_repl_ast
   Action Input: 要执行的 Python 代码（确保代码简洁完整）
7. 日期处理请使用: pd.to_datetime(df['列名'], format='%Y-%m-%d')
8. 不要尝试直接执行代码，必须通过工具调用
9. 生成图表时，不要尝试保存文件，直接返回图表数据
10. 确保月份格式统一为 "YYYY-MM"（例如 "2020-03"）
11. 确保每个月份数据唯一，没有重复
12. 图表数据格式必须严格遵循:
    {{
        "type": "line/bar/pie/scatter/box/hist/area",
        "data": {{"columns": ["月份", "销售额"], "data": [["2020-01", 5409855], ["2020-02", 4608455], ...]}},
        "title": "图表标题 (可选)"
    }}
13. 确保图表数据中每个数组元素都包含 2 个值：[月份, 销售额]
14. 月份格式必须统一为 "YYYY-MM"（例如 "2020-03"）
15. 确保每个月份数据唯一，没有重复
16. 确保JSON格式正确：键名使用双引号，字符串值使用双引号，数值不使用引号
"""

# 文本代理提示词模板
TEXT_AGENT_PROMPT_TEMPLATE = "你是一个乐于助人的AI助手，用中文回答问题"

# RAG代理提示词模板
RAG_AGENT_PROMPT_TEMPLATE = "你是一个专业的数据分析助手，请根据用户的数据或问题提供准确、详细的回答"


# ============================================================
# 主应用功能
# ============================================================
# 初始化会话状态
def init_session_state():
    if 'current_session_messages' not in st.session_state:
        st.session_state.current_session_messages = [
            {'role': 'ai', 'content': '你好，我是你的AI助手，请问有什么能帮助你吗？'}]
    if 'history_sessions' not in st.session_state:
        st.session_state.history_sessions = []  # 存储所有历史会话
    if 'memory' not in st.session_state:
        st.session_state.memory = ConversationBufferMemory(return_messages=True)
    if 'data_df' not in st.session_state:
        st.session_state.data_df = None
    if 'txt_content' not in st.session_state:
        st.session_state.txt_content = None
    if 'viewing_history' not in st.session_state:
        st.session_state.viewing_history = False
    if 'current_session_index' not in st.session_state:
        st.session_state.current_session_index = None
    if 'session_id' not in st.session_state:
        st.session_state.session_id = uuid.uuid4().hex
    if 'is_new_file' not in st.session_state:
        st.session_state.is_new_file = True
    if 'API_KEY' not in st.session_state:
        st.session_state.API_KEY = ""
    if 'selected_model' not in st.session_state:
        st.session_state.selected_model = "gpt-4o-mini"
    if 'model_temperature' not in st.session_state:
        st.session_state.model_temperature = 0.7
    if 'model_max_length' not in st.session_state:
        st.session_state.model_max_length = 1000
    if 'system_prompt' not in st.session_state:
        st.session_state.system_prompt = RAG_AGENT_PROMPT_TEMPLATE
    if 'current_mode' not in st.session_state:
        st.session_state.current_mode = "💬 聊天对话"
    if 'selected_sheet' not in st.session_state:
        st.session_state.selected_sheet = None
    if 'processing_complete' not in st.session_state:
        st.session_state.processing_complete = False
    if 'file_uploader_key' not in st.session_state:
        st.session_state.file_uploader_key = str(uuid.uuid4())


# 生成统计图表 (使用Plotly)
def create_chart(input_data, chart_type):
    """生成统计图表"""
    try:
        # 确保标题使用UTF-8编码
        title = input_data.get("title", "默认图表")
        if isinstance(title, str):
            title = title.encode('utf-8', 'ignore').decode('utf-8')
        # 检查数据格式 - 处理两种格式
        if isinstance(input_data["data"][0], list):
            # 处理二维数组格式 [["月份", 销售额], ...]
            df_data = pd.DataFrame(
                input_data["data"],
                columns=input_data["columns"]
            )
        else:
            # 处理一维数组格式 ["月份1", "月份2", ...] 和 [销售额1, 销售额2, ...]
            df_data = pd.DataFrame({
                input_data["columns"][0]: input_data["data"],
                input_data["columns"][1]: input_data["data"]
            })

        # 确保所有列名都是字符串类型
        df_data.columns = df_data.columns.astype(str)

        # 根据图表类型生成不同的可视化
        if chart_type == "bar":
            fig = px.bar(
                df_data,
                x=df_data.columns[0],
                y=df_data.columns[1],
                title=input_data.get("title", "柱状图")
            )
            st.plotly_chart(fig, use_container_width=True)

        elif chart_type == "line":
            fig = px.line(
                df_data,
                x=df_data.columns[0],
                y=df_data.columns[1],
                title=input_data.get("title", "折线图"),
                markers=True
            )
            st.plotly_chart(fig, use_container_width=True)

        elif chart_type == "pie":
            fig = px.pie(
                df_data,
                names=df_data.columns[0],
                values=df_data.columns[1],
                title=input_data.get("title", "饼图")
            )
            st.plotly_chart(fig, use_container_width=True)

        elif chart_type == "scatter":
            fig = px.scatter(
                df_data,
                x=df_data.columns[0],
                y=df_data.columns[1],
                title=input_data.get("title", "散点图")
            )
            st.plotly_chart(fig, use_container_width=True)

        elif chart_type == "box":
            fig = px.box(
                df_data,
                y=df_data.columns[1],
                title=input_data.get("title", "箱线图")
            )
            st.plotly_chart(fig, use_container_width=True)

        elif chart_type == "hist":
            fig = px.histogram(
                df_data,
                x=df_data.columns[1],
                title=input_data.get("title", "直方图")
            )
            st.plotly_chart(fig, use_container_width=True)

        elif chart_type == "area":
            fig = px.area(
                df_data,
                x=df_data.columns[0],
                y=df_data.columns[1],
                title=input_data.get("title", "面积图")
            )
            st.plotly_chart(fig, use_container_width=True)

        else:
            st.error(f"不支持的图表类型: {chart_type}")

    except Exception as e:
        st.error(f"图表生成出错：{e}")
        st.error(f"数据格式: {input_data}")


# 文本代理 - 处理无文件情况
def text_agent(query):
    try:
        model = ChatOpenAI(
            api_key=st.session_state.API_KEY,
            base_url='https://twapi.openai-hk.com/v1',
            model=st.session_state.selected_model,
            temperature=st.session_state.model_temperature,
            max_tokens=st.session_state.model_max_length
        )
        chain = ConversationChain(llm=model, memory=st.session_state.memory)
        return chain.invoke({'input': query})['response']
    except Exception as e:
        st.error(f"文本处理出错：{e}")
        return "无法处理您的请求，请检查配置或重试。"


# 增强JSON解析能力
def safe_json_parse(response_text):
    """安全地解析可能包含额外内容的JSON字符串"""
    try:
        # 尝试直接解析整个响应
        return json.loads(response_text)
    except json.JSONDecodeError:
        try:
            # 尝试提取JSON部分
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            if start_idx != -1 and end_idx != 0:
                json_str = response_text[start_idx:end_idx]
                return json.loads(json_str)
        except:
            pass

    # 尝试提取JSON代码块
    try:
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
            return json.loads(json_str)
    except:
        pass

    # 尝试使用正则表达式提取JSON
    try:
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
    except:
        pass

    return None


# 数据框代理 - 处理CSV/Excel文件
def dataframe_agent(df, query):
    try:
        # 使用提示词模板
        structured_prompt = DF_AGENT_PROMPT_TEMPLATE.format(
            df_head=df.head(3).to_string(),
            query=query
        )

        # 创建代理 - 显式设置响应编码，并启用错误处理
        agent = create_pandas_dataframe_agent(
            ChatOpenAI(
                api_key=st.session_state.API_KEY,
                base_url='https://twapi.openai-hk.com/v1',
                model=st.session_state.selected_model,
                temperature=0.2,
                max_tokens=st.session_state.model_max_length,
                model_kwargs={'response_format': {'type': 'text'}}  # 确保响应是文本格式
            ),
            df,
            verbose=True,
            handle_parsing_errors=True,  # 启用错误处理
            max_iterations=3,
            allow_dangerous_code=True,
            include_df_in_prompt=True
        )

        # 获取代理响应并显式解码为UTF-8
        response = agent.invoke(structured_prompt)['output']

        # 显式编码为UTF-8
        if isinstance(response, str):
            response = response.encode('utf-8', 'ignore').decode('utf-8')

        # 尝试解析为结构化数据
        parsed_response = safe_json_parse(response)
        if parsed_response:
            return parsed_response

        # 如果解析失败，返回原始响应
        return {"answer": response}

    except Exception as e:
        st.error(f"数据分析出错：{e}")
        return {
            "error": str(e),
            "answer": "系统处理数据时出错"
        }


# ============================================================
# RAG代理 - 使用小型Hugging Face嵌入模型
# ============================================================
def rag_agent(query):
    try:
        # 如果是新文件，处理文本
        if st.session_state.is_new_file:
            # 使用小型Hugging Face嵌入模型
            em = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",  # 小型高效模型
                model_kwargs={'device': 'cpu'},  # 使用CPU
                encode_kwargs={'normalize_embeddings': True},
                ssl_context=custom_ssl_context  # 使用自定义SSL上下文
            )

            # 进度指示器
            progress_bar = st.progress(0)
            status_text = st.empty()

            # 分块处理文本
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=100,
                separators=["\n\n", "\n", "。", "！", "？", "，", "、", ""]
            )

            # 显示处理状态
            status_text.text("正在分割文本...")
            texts = text_splitter.split_text(st.session_state.txt_content)
            progress_bar.progress(30)

            # 显示处理状态
            status_text.text(f"正在处理 {len(texts)} 个文本块...")

            # 分批处理避免内存不足
            batch_size = 20  # 减少批处理大小以防止超时
            db = None

            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]

                # 显示处理状态
                status_text.text(f"处理块 {i + 1}-{min(i + batch_size, len(texts))}/{len(texts)}...")

                try:
                    if db is None:
                        db = FAISS.from_texts(batch, em)
                    else:
                        batch_db = FAISS.from_texts(batch, em)
                        db.merge_from(batch_db)
                except Exception as e:
                    st.error(f"处理文本块时出错: {e}")
                    continue

                progress = min(30 + 70 * (i + batch_size) / len(texts), 100)
                progress_bar.progress(int(progress))

            if db is None:
                st.error("无法创建向量数据库，请重试或上传较小的文件")
                return {"answer": "文本处理失败，请重试或上传较小的文件"}

            st.session_state.db = db
            st.session_state.is_new_file = False

            # 完成处理
            progress_bar.progress(100)
            status_text.text("文本处理完成！")
            time.sleep(0.5)  # 让用户看到完成消息
            progress_bar.empty()
            status_text.empty()
            st.session_state.processing_complete = True

        # 创建检索链
        model = ChatOpenAI(
            api_key=st.session_state.API_KEY,
            base_url='https://twapi.openai-hk.com/v1',
            model=st.session_state.selected_model,
            temperature=st.session_state.model_temperature,
            max_tokens=st.session_state.model_max_length,
            request_timeout=60  # 增加超时时间
        )

        retriever = st.session_state.db.as_retriever(
            search_kwargs={"k": 3}  # 减少检索结果数量
        )

        # 显式加载聊天历史
        chat_history = st.session_state.memory.load_memory_variables({})["history"]

        chain = ConversationalRetrievalChain.from_llm(
            llm=model,
            retriever=retriever,
            return_source_documents=True,
            max_tokens_limit=3000,  # 限制token数量
            verbose=True
        )

        # 使用进度条显示处理状态
        with st.spinner('🤖 AI正在分析文档内容...'):
            result = chain.invoke({
                "question": query,
                "chat_history": chat_history
            })

        # 添加源文档信息
        sources = list(set([doc.metadata.get('source', '未知来源') for doc in result['source_documents']]))
        answer = f"{result['answer']}\n\n**来源**: {', '.join(sources)}"

        return {"answer": answer}

    except Exception as e:
        st.error(f"文本处理出错：{e}")
        return {"answer": "处理文本内容超时，请尝试上传更小的文件或简化您的问题。"}


# 主应用
def main():
    # 设置页面配置（确保中文字符支持）
    st.set_page_config(
        page_title="SuperAI 智能分析助手",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    init_session_state()

    # 页面标题
    header_container = st.container()
    with header_container:
        cols = st.columns([1, 8, 1])
        with cols[1]:
            st.markdown("""
                <div style="text-align:center; margin-bottom:40px">
                    <h1 style="margin-bottom:0">SuperAI 智能分析助手🚀</h1>
                    <p style="color:#6C63FF; font-size:1.2rem">数据洞察从未如此简单</p>
                </div>
            """, unsafe_allow_html=True)

    # 侧边栏
    with st.sidebar:
        st.title("超级智能分析助手")
        api_key = st.text_input('请输入OpenAI API Key', type='password', value=st.session_state.API_KEY)
        if api_key:
            st.session_state.API_KEY = api_key

        if st.button("🔄 新建会话", use_container_width=True):
            # 保存当前会话到历史会话
            if len(st.session_state.current_session_messages) > 1:  # 避免保存只有欢迎消息的会话
                new_session = {
                    'id': uuid.uuid4().hex,
                    'messages': st.session_state.current_session_messages.copy(),
                    'timestamp': time.strftime("%Y-%m-%d %H:%M", time.localtime())
                }
                st.session_state.history_sessions.append(new_session)

            # 重置当前会话
            st.session_state.current_session_messages = [
                {'role': 'ai', 'content': '你好，我是你的AI助手，请问有什么能帮助你吗？'}]
            st.session_state.memory = ConversationBufferMemory(return_messages=True)
            st.session_state.viewing_history = False
            st.session_state.data_df = None
            st.session_state.txt_content = None
            st.session_state.is_new_file = True
            st.session_state.session_id = uuid.uuid4().hex
            st.session_state.file_uploader_key = str(uuid.uuid4())  # 生成新的随机键
            st.rerun()

        st.divider()

        # 历史会话
        st.subheader("📜 历史会话")
        if st.session_state.history_sessions:
            for i, session in enumerate(st.session_state.history_sessions):
                # 查找第一条用户消息作为预览
                user_preview = ""
                for msg in session['messages']:
                    if msg['role'] == 'human':
                        user_preview = msg['content'][:30] + ('...' if len(msg['content']) > 30 else '')
                        break

                st.caption(f"📅 {session['timestamp']}")
                st.caption(f"🗣️ 用户: {user_preview}")

                col1, col2 = st.columns([3, 1])
                with col1:
                    if st.button(f"查看会话 {i + 1}", key=f"view_{i}", use_container_width=True):
                        st.session_state.viewing_history = True
                        st.session_state.current_session_index = i
                with col2:
                    if st.button("❌", key=f"delete_{i}", use_container_width=True):
                        del st.session_state.history_sessions[i]
                        st.rerun()
                st.divider()
        else:
            st.caption("暂无历史会话")
        st.divider()

        # 模型配置
        st.subheader("⚙️ 模型配置")
        st.session_state.selected_model = st.selectbox(
            "选择AI模型",
            ["gpt-4o", "gpt-4o-mini", "gpt-4", "gpt-3.5-turbo"],
            index=1,
            help="选择要使用的AI模型"
        )

        st.session_state.model_temperature = st.slider(
            "温度 (Temperature)",
            0.0, 1.0, 0.7, 0.1,
            help="控制生成文本的随机性，值越高越有创意，值越低越稳定"
        )

        st.session_state.model_max_length = st.slider(
            "最大生成长度",
            100, 4000, 1000, 100,
            help="限制AI生成的最大token数量"
        )

        st.session_state.system_prompt = st.text_area(
            "系统提示词",
            RAG_AGENT_PROMPT_TEMPLATE,
            help="指导AI如何回答问题的系统级提示"
        )

    # 查看历史会话
    if st.session_state.viewing_history and st.session_state.current_session_index is not None:
        st.subheader("📜 历史消息")
        session = st.session_state.history_sessions[st.session_state.current_session_index]

        for message in session['messages']:
            with st.chat_message("user" if message["role"] == "human" else "assistant"):
                st.write(message["content"])

        if st.button("↩️ 返回当前对话", use_container_width=True):
            st.session_state.viewing_history = False
            st.rerun()

    # 主界面 - 文件上传和聊天
    else:
        # 文件上传区域
        st.subheader("📤 上传数据文件")
        file = st.file_uploader(
            "上传CSV、Excel或TXT文件",
            type=["csv", "xlsx", "txt"],
            label_visibility="collapsed",
            key=st.session_state.file_uploader_key
        )

        # 处理文件上传
        if file:
            process_uploaded_file(file)

        # 显示当前模式
        st.markdown(f"**当前模式**: {st.session_state.current_mode}")

        # 重置文件状态逻辑
        if file is None and (st.session_state.data_df is not None or st.session_state.txt_content is not None):
            # 用户已删除文件，重置相关状态
            st.session_state.data_df = None
            st.session_state.txt_content = None
            st.session_state.is_new_file = True
            st.toast("文件已移除，现在可进行文本问答")
            # 清除预览区域
            st.rerun()
        elif file:
            # 处理文件上传后显示预览
            try:
                file_type = file.name.split('.')[-1].lower()
                if file_type in ['csv', 'xlsx']:
                    with st.expander("👀 数据预览", expanded=True):
                        st.dataframe(st.session_state.data_df.head(10), use_container_width=True)
                        st.caption(
                            f"数据维度: {st.session_state.data_df.shape[0]} 行 × {st.session_state.data_df.shape[1]} 列")
                elif file_type == 'txt':
                    with st.expander("📝 文本内容预览", expanded=True):
                        st.text_area("", st.session_state.txt_content, height=300, label_visibility="collapsed")
            except Exception as e:
                st.error(f"文件预览错误: {str(e)}")

        # 显示当前会话聊天历史
        for message in st.session_state.current_session_messages:
            with st.chat_message("user" if message["role"] == "human" else "assistant"):
                st.write(message["content"])

        # 用户输入
        if prompt := st.chat_input("请输入您的问题...", key="user_input"):
            if not st.session_state.API_KEY:
                st.error('🔑 请输入OpenAI API Key')
                st.stop()

            # 添加用户消息到当前会话
            st.session_state.current_session_messages.append({'role': 'human', 'content': prompt})

            with st.chat_message("user"):
                st.write(prompt)

            # AI处理区域
            with st.spinner('🤖 AI正在思考，请稍等...'):
                try:
                    # 根据文件类型选择处理方式
                    if st.session_state.data_df is not None:
                        response = dataframe_agent(st.session_state.data_df, prompt)
                    elif st.session_state.txt_content is not None:
                        response = rag_agent(prompt)
                    else:
                        # 没有文件时使用文本代理
                        response = {"answer": text_agent(prompt)}

                    # 确保response是字典类型
                    if not isinstance(response, dict):
                        response = {"answer": str(response)}

                    # 处理错误响应
                    if "error" in response:
                        st.error(f"错误: {response['error']}")
                        ai_response = response.get("answer", "数据分析失败")
                    else:
                        # 提取文本回答
                        ai_response = response.get("answer", "没有获取到回答内容")

                        # 图表关键词列表
                        chart_keywords = ["图表", "柱状图", "折线图", "饼图", "可视化", "展示图", "散点图", "箱线图",
                                          "直方图", "面积图", "月度销售额"]

                        # 只在用户明确要求图表且response是字典时才检查
                        if isinstance(response, dict) and "charts" in response:
                            if any(kw in prompt.lower() for kw in chart_keywords):
                                for chart in response["charts"]:
                                    if "type" in chart and "data" in chart:
                                        create_chart(chart["data"], chart["type"])
                        else:
                            # 移除可能的图表生成消息
                            ai_response = ai_response.split("\n\n已生成")[0]

                    # 添加AI响应到当前会话
                    st.session_state.current_session_messages.append({'role': 'ai', 'content': ai_response})

                    # 显示AI响应
                    with st.chat_message("assistant"):
                        if "error" in response:
                            st.error(ai_response)
                        else:
                            st.write(ai_response)

                except Exception as e:
                    error_msg = f"处理请求时出错: {str(e)}"
                    st.session_state.current_session_messages.append({'role': 'ai', 'content': error_msg})
                    with st.chat_message("assistant"):
                        st.error(error_msg)


if __name__ == "__main__":
    main()