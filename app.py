import streamlit as st
from wikipedia_extractor_core import (
    WikipediaExtractor,
    format_txt,
    numbered_filename,
    safe_filename,
)


st.set_page_config(page_title="Wikipedia Extractor", layout="wide")


def record_download(filename):
    if filename not in st.session_state.downloaded_filenames:
        st.session_state.downloaded_filenames.append(filename)


defaults = {
    "topic": None,
    "article": None,
    "titles": None,
    "selected": None,
    "sections": [],
    "saved_path": None,
    "pending_overwrite": None,
    "pending_filename": None,
    "downloaded_filenames": [],
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

if (
    st.session_state.article is None
    and (
        st.session_state.titles
        or st.session_state.sections
    )
):
    st.session_state.titles = None
    st.session_state.selected = None
    st.session_state.sections = []
    st.session_state.downloaded_filenames = []
    st.rerun()


with st.sidebar:
    st.header("Wikipedia Extractor")

    if st.button("Start Over"):
        st.session_state.clear()
        st.rerun()


st.title("Wikipedia Article Extractor")

with st.expander("How to use this app"):
    st.write(
        "1. Enter a topic.\n"
        "2. Select sections.\n"
        "3. Click Extract.\n"
        "4. Click Download."
    )

progress_columns = st.columns(4)
progress_columns[0].caption(
    "✅ Search" if st.session_state.topic else "Search"
)
progress_columns[1].caption(
    "✅ Select" if st.session_state.titles else "Select"
)
progress_columns[2].caption(
    "✅ Extract" if st.session_state.sections else "Extract"
)
progress_columns[3].caption(
    "✅ Download"
    if st.session_state.downloaded_filenames
    else "Download"
)

with st.form("topic_search"):
    topic = st.text_input("Enter a topic")
    submitted = st.form_submit_button("Search")

if submitted:
    if topic.strip():
        st.session_state.topic = topic.strip()
        article = WikipediaExtractor(st.session_state.topic)
        st.session_state.article = article

        if article.error:
            st.error(article.error)
            st.session_state.titles = None
            st.session_state.selected = []
            st.session_state.sections = []
        else:
            st.success(f"Loaded: {article.title}")
            st.write(article.url)
            st.session_state.titles = article.section_titles()
            st.session_state.selected = []
            st.session_state.sections = []
            if len(st.session_state.titles) <= 1:
                st.warning("This article has no usable sections.")
                st.session_state.titles = None


if st.session_state.titles:
    st.subheader("Sections")
    st.session_state.selected = st.multiselect(
        "Select sections",
        options=st.session_state.titles,
        default=st.session_state.selected,
    )

    if st.button("Extract"):
        if not st.session_state.selected:
            st.warning("Select at least one section to extract.")
        else:
            st.session_state.sections = [
                st.session_state.article.extract(title)
                for title in st.session_state.selected
            ]


if st.session_state.sections:
    st.subheader("Preview")
    with st.container(border=True):
        for section in st.session_state.sections:
            st.markdown(f"### {section['title']}")
            blocks = section["blocks"]

            if not blocks:
                st.caption("(no extractable content)")

            for block in blocks:
                if block["type"] == "paragraph":
                    st.write(block["text"])
                elif block["type"] == "subheading":
                    st.markdown(f"#### {block['text']}")
                elif block["type"] == "list":
                    for number, item in enumerate(block["items"], 1):
                        marker = f"{number}." if block["ordered"] else "-"
                        st.markdown(f"{marker} {item}")
                elif block["type"] == "table":
                    st.dataframe(block["rows"])

    article = st.session_state.article
    proposed_filename = safe_filename(article.title) + ".txt"

    if proposed_filename in st.session_state.downloaded_filenames:
        st.warning(
            "You already downloaded a file with this name in this "
            "session. Downloading again will add (2) to the name."
        )

    download_filename = proposed_filename
    number = 2
    while download_filename in st.session_state.downloaded_filenames:
        download_filename = numbered_filename(proposed_filename, number)
        number += 1

    st.download_button(
        label="Download .txt",
        data=format_txt(
            article.title,
            article.url,
            st.session_state.sections,
        ),
        file_name=download_filename,
        mime="text/plain",
        key="download_btn",
        on_click=record_download,
        args=(download_filename,),
    )

st.caption("Content from Wikipedia, CC BY-SA 4.0.")
st.write(st.session_state)
