from langchain_deepseek import ChatDeepSeek
import os

#
os.environ['DEEPSEEK_API_KEY'] = 'sk-实际的key'

def getDeepSeek():
    llm = ChatDeepSeek(model="deepseek-chat", temperature=0.1, streaming=True)
    return llm