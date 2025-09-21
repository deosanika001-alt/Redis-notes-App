import streamlit as st
from redis import Redis
import json
import uuid
from datetime import datetime
import os

REDIS_URL = os.environ.get("REDIS_URL", "redis://default:LH4lU3ExCKk9M3NN4NEEAcwfYW4RwHez@redis-18364.c73.us-east-1-2.ec2.redns.redis-cloud.com:18364")

redis = Redis.from_url(REDIS_URL, decode_responses=True)

NOTE_KEY_PREFIX = "note:"
NOTE_INDEX_SET = "notes:ids"

try:
    from streamlit import rerun
except ImportError:
    rerun = st.experimental_rerun


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
    key = NOTE_KEY_PREFIX + note_id
    redis.delete(key)
    redis.srem(NOTE_INDEX_SET, note_id)

def get_note(note_id):
    raw = redis.get(NOTE_KEY_PREFIX + note_id)
    if not raw:
        return None
    return json.loads(raw)

def list_all_note_ids():
    return list(redis.smembers(NOTE_INDEX_SET))

def list_notes(search_query: str = "", starred_only: bool = False, sort_by_updated: bool = True):
    notes = []
    ids = list_all_note_ids()
    for note_id in ids:
        n = get_note(note_id)
        if not n:
            continue
        if starred_only and n.get("starred", "0") != "1":
            continue
        if search_query:
            q = search_query.lower()
            if q not in (n.get("title","").lower() + " " + n.get("content","").lower()):
                continue
        notes.append(n)

    if sort_by_updated:
        notes.sort(key=lambda x: x.get("updated_at",""), reverse=True)
    else:
        notes.sort(key=lambda x: x.get("created_at",""), reverse=True)
    return notes
        
# Streamlit UI
st.set_page_config(page_title="Redis Notes WebApp", page_icon="🗒️" , layout="wide")
st.title("Redis Notes App")
#Sidebar
with st.sidebar:
    st.header("Create a Note")
    with st.form("create_form", clear_on_submit = True):
        new_title = st.text_input("Title")
        new_content = st.text_area("Content", height = 150)
        new_star = st.checkbox("mark important (star)")
        submitted = st.form_submit_button("Create")
        if submitted:
            if not new_title.strip() and not new_content.strip():
                st.warning("Please add a title or content to create a note.")
            else:
                note = create_note(new_title.strip(), new_content.strip(), new_star)
                st.success("Note created")
                st.experimental_rerun()

    st.markdown("---")
    st.header("Sreach and Filter")
    q = st.text_input("Search (title or content)", value="", key="search_q")
    starred_only = st.checkbox("Show only starred notes", value=False, key="filter_starred")

col_list, col_view = st.columns([1.4, 2.6])

with col_list:
    st.subheader("Notes")
    notes = list_notes(search_query=q.strip(), starred_only=starred_only)
    if not notes:
        st.info("No notes found. Create one from the siderbar.")
    else:
        for n in notes:
            cols = st.columns([0.04, 0.9, 0.4, 0.2])
            star_btn = cols[0].button("★" if n.get("starred","0") == "1" else "☆", key=f"star_{n['id']}")
            if star_btn:
                update_note(n["id"], n["title"], n["content"], starred=(n.get("starred","0")!="1"))
                st.experimental_rerun()
            title_button = cols[1].button(n.get("title")or"(on title)",key=f"open_{n['id']}")
            cols[2].write(n.get("updateed_at","")[:19].replace("T"," "))
            del_btn = cols[3].button("Delete", key=f"del_{n['id']}")
            if del_btn:
                delete_note(n["id"])
                st.experimental_rerun()

            if title_button:
                st.session_state["open_note_id"] = n["id"]
                st.experimental_rerun()

with col_view:
    st.subheader("View / Edit")
    open_id = st.session_state.get("open_note_id", None)
    if open_id:
        note = get_note(open_id)
        if not note:
            st.warning("Note not found (may be deleted)")
            st.session_state.pop("open_note_id", None)
        else:
            with st.form("edit_form"):
                t = st.text_input("Title", value=note.get("title", ""))
                c = st.text_input("Content", value=note.get("content", ""), height=250)
                s = st.checkbox("Star / Important", value=(note.get("starred","0")=="1"))
                col1, col2, col3 = st.columns([1,1,1])
                with col1:
                    save = st.form_submit_button("save")
                with col2:
                    save = st.form_submit_button("close")
                with col3:
                    save = st.form_submit_button("export to json")
                if save:
                    if not t.strip() and not c.strip():
                        st.warning("title or content required to save")
                    else:
                        update_note(open_id, t.strip(), c.strip(), s)
                        st.success("saved")
                        st.experimental_rerun()
                if cancel:
                    st.session_state.pop("open_note_id", None)
                    st.experimental_rerun()
                if export:
                    st.download_button(
                        "download json",
                        data=json.dumps(note,indent=2),
                        file_name = f"note-{note['id']}.json",
                        mime="application/json",
                    )
    else:
        st.info("select a note from the left to view or edit")

st.markdown("---")
col_a, col_b, col_c = st.columns(3)
with col_a:
    if st.button("create sample note"):
        create_note("sample note", "this is a sample note.", starred=False)
        st.experimental_rerun()
with col_b:
    if st.button("show star note"):
        st.session_state["open_note_id"] = None
        st.session_state["sidebar_toggle_starred"] = not st.session_state.get("sidebar_toggle_starred", False)
        st.experimental_rerun()
with col_c:
    if st.button("Clear all notes"):
        if st.checkbox("yes i want to delete all notes", key = "confirm_del_all"):
            ids =list_all_note_ids()
            for _id in ids:
                delete_note(_id)
        st.success("all notes deleted")
        st.experimental_rerun()

notes_all = list_notes()
st.sidebar.markdown("---")
st.sidebar.subheader("Stats")
st.sidebar.write(f"Total notes: **{len(notes_all)}**")
st.sidebar.write(f"match shown: **{len(notes)}**")
st.sidebar.write(f"starred notes: **{len([n for n in notes_all if n.get('starred','0')==1])}**")
st.sidebar.markdown("---")
st.sidebar.caption("Redis based Notes app")

