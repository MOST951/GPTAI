import json
from turtle import st

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent

PROMPT_TEMPLATE = """
你是一位数据分析助手，你的回应内容取决于用户的请求内容。

1. 对于文字回答的问题，按照这样的格式回答：
   {"answer": "<你的答案写在这里>"}
例如：
   {"answer": "订单量最高的产品ID是'MNWC3-067'"}

2. 如果用户需要一个表格，按照这样的格式回答：
   {"table": {"columns": ["column1", "column2", ...], "data": [[value1, value2, ...], [value1, value2, ...], ...]}}

3. 如果用户的请求适合返回条形图，按照这样的格式回答：
   {"bar": {"columns": ["A", "B", "C", ...], "data": [34, 21, 91, ...]}}

4. 如果用户的请求适合返回折线图，按照这样的格式回答：
   {"line": {"columns": ["A", "B", "C", ...], "data": [34, 21, 91, ...]}}

5. 如果用户的请求适合返回散点图，按照这样的格式回答：
   {"scatter": {"columns": ["A", "B", "C", ...], "data": [34, 21, 91, ...]}}

注意：我们只支持三种类型的图表："bar", "line" 和 "scatter"。


请将所有输出作为JSON字符串返回。请注意要将"columns"列表和数据列表中的所有字符串都用双引号包围。
例如：{"columns": ["Products", "Orders"], "data": [["32085Lip", 245], ["76439Eye", 178]]}

你要处理的用户请求如下： {input}
"""


def dataframe_agent(df, query):
    """
    获取数据分析结果

    Args:
        df: 上传的数据文件生成的DataFrame
        query: 用户提出的问题

    Returns:
        分析结果的字典
    """
    load_dotenv()
    model = ChatOpenAI(
        model="deepseek-chat",
        base_url='https://api.deepseek.com',
        api_key='sk-8dca673d82b74bf59bac651337b7fba8',
        temperature=0
    )
    agent = create_pandas_dataframe_agent(
        llm=model,
        df=df,
        agent_executor_kwargs={"handle_parsing_errors": True},
        max_iterations=10,
        early_stopping_method='generate',
        allow_dangerous_code=True,
        verbose=True
    )
    prompt = PROMPT_TEMPLATE + query
    try:
        response = agent.invoke({"input": prompt})
        return json.loads(response["output"])
    except Exception as e:
        # 捕获异常并返回友好的错误提示
        st.warning(f"请求处理失败，请检查链接的合法性或稍后再试。错误信息：{str(e)}")
        return {}