import streamlit as st
import pandas as pd
from utils.chart_generator import create_chart


def render_data_analysis():
    """渲染数据分析模块"""
    st.header("📊 智能数据分析")

    if st.session_state.data_df is not None:
        st.write("### 数据预览")
        st.dataframe(st.session_state.data_df.head(10), use_container_width=True)

        analysis_query = st.text_input("输入分析需求（示例：显示各月销售额趋势）")

        if analysis_query:
            with st.spinner('正在生成分析...'):
                try:
                    data_desc = f"""
                    数据集列名：{st.session_state.data_df.columns.tolist()}
                    数据类型：
                    {st.session_state.data_df.dtypes.to_string()}
                    数据样例：
                    {st.session_state.data_df.head(3).to_markdown()}
                    """

                    from modules.chat import get_ai_response
                    analysis_result = get_ai_response(
                        memory=st.session_state.data_memory,
                        user_prompt=f"分析需求：{analysis_query}\n{data_desc}",
                        system_prompt="你是一个数据分析专家，请根据提供的数据集进行专业分析，给出可视化建议"
                    )

                    st.write("### AI分析报告")
                    st.write(analysis_result)

                    # 自动生成图表
                    if "柱状图" in analysis_result:
                        create_chart(
                            input_data={
                                "columns": st.session_state.data_df.columns.tolist(),
                                "data": st.session_state.data_df.iloc[0].tolist()
                            },
                            chart_type="bar"
                        )
                    elif "折线图" in analysis_result:
                        create_chart(
                            input_data={
                                "columns": st.session_state.data_df.columns.tolist(),
                                "data": st.session_state.data_df.iloc[0].tolist()
                            },
                            chart_type="line"
                        )
                    elif "散点图" in analysis_result:
                        st.scatter_chart(st.session_state.data_df)

                except Exception as e:
                    st.error(f"分析失败：{str(e)}")
    else:
        st.info("请先在侧边栏上传数据文件")