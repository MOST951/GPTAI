import streamlit as st
from langchain_openai import ChatOpenAI
from langchain.chains import ConversationalRetrievalChain
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS


def render_document_qa():
    """渲染文档问答模块"""
    st.header("📚 文档智能问答")

    # 问题输入
    question = st.text_input("请输入您的问题", key="doc_question")

    if question and st.session_state.get('session_id'):
        with st.spinner('正在分析文档...'):
            try:
                if st.session_state.is_new_file:
                    loader = TextLoader(f'{st.session_state.session_id}.txt', encoding='utf-8')
                    docs = loader.load()

                    text_splitter = RecursiveCharacterTextSplitter(
                        chunk_size=1000,
                        chunk_overlap=200,
                        separators=["\n\n", "\n", "。", "！", "？", "，"]
                    )
                    texts = text_splitter.split_documents(docs)

                    st.session_state.rag_db = FAISS.from_documents(
                        texts,
                        embedding=None  # 使用默认的embedding
                    )
                    st.session_state.is_new_file = False

                model = ChatOpenAI(
                    model=st.session_state.selected_model,
                    api_key=st.secrets['API_KEY'],
                    base_url='https://api.openai.com/v1',
                    temperature=0.2
                )

                qa_chain = ConversationalRetrievalChain.from_llm(
                    llm=model,
                    retriever=st.session_state.rag_db.as_retriever(
                        search_type="mmr",
                        search_kwargs={'k': 3}
                    ),
                    memory=st.session_state.rag_memory,
                    return_source_documents=True
                )

                result = qa_chain({'question': question})

                st.subheader("答案")
                st.write(result['answer'])

                with st.expander("参考文档片段"):
                    for doc in result['source_documents']:
                        st.markdown(f"**来源**: `{doc.metadata['source']}`")
                        st.text(doc.page_content[:300] + "...")
                        st.divider()

            except Exception as e:
                st.error(f"文档处理失败：{str(e)}")