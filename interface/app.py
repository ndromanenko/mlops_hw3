import altair as alt
import pandas as pd
import streamlit as st

from db import fetch_model_versions, fetch_recent_frauds, fetch_recent_scores
from kafka_broker import send_transactions, consume_scores
from logger_config import setup_logger, get_logger


@st.cache_resource
def init_logging():
    setup_logger()
    return get_logger("interface")


log = init_logging()

st.title("Fraud Детектор")

uploaded_file = st.file_uploader("Загрузите test.csv", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)

    st.write("Первые строки:")
    st.dataframe(df.head())
    st.write(f"Количество транзакций: {len(df)}")

    if st.button("Отправить транзакции"):
        progress = st.progress(0)
        sent = send_transactions(df, progress_callback=progress.progress)
        st.success(f"Отправлено транзакций: {sent}")


st.divider()

st.header("Результаты из базы данных")

if st.button("Посмотреть результаты"):
    try:
        with st.spinner("Читаю данные из баз данных..."):
            frauds = fetch_recent_frauds(limit=10)
            scores = fetch_recent_scores(limit=100)
            versions = fetch_model_versions()
    except Exception as exc:
        log.exception("Не удалось прочитать результаты из БД")
        st.error(f"Ошибка чтения из БД: {exc}")
    else:
        st.subheader("Версии модели")
        if versions:
            st.dataframe(pd.DataFrame(versions))
        else:
            st.info("В базе пока нет транзакций.")

        st.subheader("Последние 10 транзакций")
        if frauds:
            st.dataframe(pd.DataFrame(frauds))
        else:
            st.info("Фрод-транзакций в базе пока нет.")

        st.subheader(f"Распределение скоров последних {len(scores)} транзакций")
        if scores:
            chart = (
                alt.Chart(pd.DataFrame({"score": scores}))
                .mark_bar()
                .encode(
                    alt.X("score:Q", bin=alt.Bin(maxbins=30), title="score"),
                    alt.Y("count()", title="Количество"),
                )
            )
            st.altair_chart(chart, width="stretch")
        else:
            st.info("В базе пока нет транзакций.")
