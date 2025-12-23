import streamlit as st

st.title("我的公开网站")
st.write("欢迎访问我的 Streamlit 网站！")
name = st.text_input("请输入你的名字")
if name:
    st.write(f"你好，{name}！")