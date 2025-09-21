import os
import json
import uuid
from datetime import datetime

import redis
import streamlit as st

# ------------------ Redis Connection ------------------
REDIS_URL = os.environ.get(
    "REDIS_URL",
    "redis://default:LH4lU3ExCKk9M3NN4NEEAcwfYW4RwHez@redis-18364.c73.us-east-1-2.ec2.redns.redis-cloud.com:18364"
)
redis = redis.from_url(REDIS_URL, decode_responses=True)

NOTE_KEY_PREFIX = "note:"
NOTE_INDEX_SET = "note:index"

# ------------------ Helpers ------------------
def create_note(title, content, starred=False):
    note_id = str(uuid.uuid4())
    note = {
        "id": note_id,
        "title": title,
        "content": content,
        "starred": starred,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    redis.set(NOTE_KEY_PREFIX + note_id, json.dumps(note))
    redis.sadd(NOTE_INDEX_SET, note_id)
    return note

def get_note(note_id):
    data = redis.get(NOTE_KEY_PREFIX + note_id)
    return json.loads(data) if data else None

def update_note(note_id, title, content, starred):
    note = get_note(note_id)
    if note:
        note["title"] = title
        note["content"] = content
        note["starred"] = starred
        redis.set(NOTE_KEY_PREFIX + note_id, json.dumps(note))
    return note

def delete_note(note_id):
    redis.delete(NOTE_KEY_PREFIX + note_id)
    redis.srem(NOTE_INDEX_SET, note_id)

def delete_all_notes():
    ids = redis.smembers(NOTE_INDEX_SET)
    for note_id in ids:
        redis.delete(NOTE_KEY_PREFIX + note_id)
    redis.delete(NOTE_INDEX_SET)

def list_all_note_ids():
    return list(redis.smembers(NOTE_INDEX_SET))

def list_notes(search="", starred_only=False):
    notes = []
    for nid in list_all_note_ids():
        note = get_note(nid)
        if note:
            if search and search.lower() not in note["title"].lower() and search.lower() not in note["content"].lower():
                continue
            if starred_only and not note["starred"]:
                continue
            notes.append(note)
    return sorted(notes, key=lambda x: x["created_at"], reverse=True)

# ------------------ UI ------------------
st.set_page_config(page_title="Notes App", page_icon="📝", layout="wide")

st.title("📝 Notes App — Streamlit + Redis")

# Sidebar (Create note + sample + delete all)
st.sidebar.header("Create a note")

new_title = st.sidebar.text_input("Title")
new_content = st.sidebar.text_area("Content")
new_star = st.sidebar.checkbox("⭐ Star (important)")

if st.sidebar.button("Create"):
    if new_title.strip() or new_content.strip():
        create_note(new_title.strip(), new_content.strip(), new_star)
        st.sidebar.success("Note created!")
        st.rerun()
    else:
        st.sidebar.warning("Please add title or content!")

if st.sidebar.button("📌 Create sample note"):
    create_note("Sample Note", "This is a sample note.", False)
    st.rerun()

if st.sidebar.button("🗑️ Delete all notes"):
    delete_all_notes()
    st.sidebar.success("All notes deleted!")
    st.rerun()

# Main layout
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Notes")
    q = st.text_input("🔍 Search")
    starred_only = st.checkbox("Show only ⭐ starred notes")

    notes = list_notes(search=q.strip(), starred_only=starred_only)

    if not notes:
        st.info("No notes yet. Create one from the sidebar!")
    else:
        for note in notes:
            with st.container():
                st.markdown(f"**{note['title']}**  \n*{note['created_at']}* {'⭐' if note['starred'] else ''}")
                c1, c2 = st.columns([5, 1])
                with c1:
                    if st.button("View / Edit", key="view_" + note["id"]):
                        st.session_state["selected_note_id"] = note["id"]
                        st.rerun()
                with c2:
                    if st.button("🗑️", key="del_" + note["id"]):
                        delete_note(note["id"])
                        st.rerun()

with col2:
    st.subheader("View / Edit")
    if "selected_note_id" in st.session_state:
        note_id = st.session_state["selected_note_id"]
        note = get_note(note_id)
        if note:
            new_t = st.text_input("Title", note["title"])
            new_c = st.text_area("Content", note["content"])
            new_s = st.checkbox("⭐ Star (important)", value=note["starred"])

            if st.button("Update"):
                update_note(note_id, new_t, new_c, new_s)
                st.success("Note updated!")
                st.rerun()
        else:
            st.warning("Note not found.")
    else:
        st.info("Select a note to view/edit.")
