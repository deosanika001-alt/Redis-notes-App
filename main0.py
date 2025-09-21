import os
import json
import uuid
from datetime import datetime
import streamlit as st
from redis import Redis

# ---------------------------------------------------
# Redis connection
# ---------------------------------------------------
# Put your Redis Cloud connection string here
REDIS_URL = os.environ.get(
    "REDIS_URL",
    "redis://default:LH4lU3ExCKk9M3NN4NEEAcwfYW4RwHez@redis-18364.c73.us-east-1-2.ec2.redns.redis-cloud.com:18364"
)

redis = Redis.from_url(REDIS_URL, decode_responses=True)

NOTE_KEY_PREFIX = "note:"
NOTE_INDEX_SET = "notes:ids"


# ---------------------------------------------------
# Helper functions
# ---------------------------------------------------
def now_iso():
    return datetime.utcnow().isoformat() + "Z"


def create_note(title, content, starred=False):
    note_id = str(uuid.uuid4())
    note = {
        "id": note_id,
        "title": title,
        "content": content,
        "starred": "1" if starred else "0",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    redis.set(NOTE_KEY_PREFIX + note_id, json.dumps(note))
    redis.sadd(NOTE_INDEX_SET, note_id)
    return note


def update_note(note_id, title, content, starred):
    key = NOTE_KEY_PREFIX + note_id
    raw = redis.get(key)
    if not raw:
        return None
    note = json.loads(raw)
    note["title"] = title
    note["content"] = content
    note["starred"] = "1" if starred else "0"
    note["updated_at"] = now_iso()
    redis.set(key, json.dumps(note))
    return note


def delete_note(note_id):
    redis.delete(NOTE_KEY_PREFIX + note_id)
    redis.srem(NOTE_INDEX_SET, note_id)


def get_note(note_id):
    raw = redis.get(NOTE_KEY_PREFIX + note_id)
    return json.loads(raw) if raw else None


def list_all_note_ids():
    return list(redis.smembers(NOTE_INDEX_SET))


def list_notes(search_query="", starred_only=False):
    notes = []
    for note_id in list_all_note_ids():
        n = get_note(note_id)
        if not n:
            continue
        if starred_only and n["starred"] != "1":
            continue
        if search_query:
            q = search_query.lower()
            if q not in (n["title"].lower() + " " + n["content"].lower()):
                continue
        notes.append(n)
    notes.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return notes


# ---------------------------------------------------
# Streamlit UI
# ---------------------------------------------------
st.set_page_config(page_title="Notes App", page_icon="🗒️", layout="wide")
st.title("🗒️ Notes App — Streamlit + Redis")


# Sidebar: Create + Search
with st.sidebar:
    st.header("Create a note")
    with st.form("create_form", clear_on_submit=True):
        new_title = st.text_input("Title")
        new_content = st.text_area("Content", height=150)
        new_star = st.checkbox("Star (important)")
        submitted = st.form_submit_button("Create")
        if submitted:
            if not new_title.strip() and not new_content.strip():
                st.warning("Please add title or content.")
            else:
                create_note(new_title.strip(), new_content.strip(), new_star)
                from streamlit import rerun
                rerun()

    st.markdown("---")
    st.header("Search & Filter")
    q = st.text_input("Search")
    starred_only = st.checkbox("Show only starred notes")


# Main: Notes list + Editor
col_list, col_view = st.columns([1.4, 2.6])

with col_list:
    st.subheader("Notes")
    notes = list_notes(search_query=q.strip(), starred_only=starred_only)
    if not notes:
        st.info("No notes found.")
    else:
        for n in notes:
            cols = st.columns([0.07, 0.7, 0.4, 0.2])

            # Toggle star
            star_btn = cols[0].button("★" if n["starred"] == "1" else "☆", key=f"star_{n['id']}")
            if star_btn:
                update_note(n["id"], n["title"], n["content"], not (n["starred"] == "1"))
                from streamlit import rerun
                rerun()

            # Open note
            title_btn = cols[1].button(n["title"] or "(untitled)", key=f"open_{n['id']}")
            cols[2].write(n["updated_at"][:19].replace("T", " "))
            del_btn = cols[3].button("Delete", key=f"del_{n['id']}")

            if del_btn:
                delete_note(n["id"])
                from streamlit import rerun
                rerun()

            if title_btn:
                st.session_state["open_note_id"] = n["id"]
                from streamlit import rerun
                rerun()


with col_view:
    st.subheader("View / Edit")
    open_id = st.session_state.get("open_note_id")
    if open_id:
        note = get_note(open_id)
        if not note:
            st.warning("Note not found.")
            st.session_state.pop("open_note_id", None)
        else:
            with st.form("edit_form"):
                t = st.text_input("Title", value=note["title"])
                c = st.text_area("Content", value=note["content"], height=250)
                s = st.checkbox("Star", value=(note["starred"] == "1"))
                save = st.form_submit_button("Save")
                close = st.form_submit_button("Close")
                if save:
                    update_note(open_id, t.strip(), c.strip(), s)
                    st.success("Saved.")
                    from streamlit import rerun
                    rerun()
                if close:
                    st.session_state.pop("open_note_id", None)
                    from streamlit import rerun
                    rerun()
    else:
        st.info("Select a note to view/edit.")


# Stats
all_notes = list_notes()
st.sidebar.markdown("---")
st.sidebar.subheader("Stats")
st.sidebar.write(f"Total notes: {len(all_notes)}")
st.sidebar.write(f"Starred notes: {len([n for n in all_notes if n['starred']=='1'])}")
