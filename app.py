import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "real_estate_registry.db"


def canonical_json(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def block_hash(index, timestamp, transaction, previous_hash):
    payload = {
        "index": index,
        "timestamp": timestamp,
        "transaction": transaction,
        "previous_hash": previous_hash,
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS properties (
            property_id TEXT PRIMARY KEY,
            address TEXT NOT NULL,
            owner TEXT NOT NULL,
            registered_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS blocks (
            idx INTEGER PRIMARY KEY,
            timestamp TEXT NOT NULL,
            transaction_json TEXT NOT NULL,
            previous_hash TEXT NOT NULL,
            hash TEXT NOT NULL
        )
    """)
    conn.commit()
    if conn.execute("SELECT COUNT(*) FROM blocks").fetchone()[0] == 0:
        add_block(conn, {"type": "GENESIS", "message": "Real Estate Registry created"})
    return conn


def get_blocks(conn):
    rows = conn.execute("SELECT * FROM blocks ORDER BY idx").fetchall()
    return [{
        "index": row["idx"],
        "timestamp": row["timestamp"],
        "transaction": json.loads(row["transaction_json"]),
        "previous_hash": row["previous_hash"],
        "hash": row["hash"],
    } for row in rows]


def add_block(conn, transaction):
    blocks = get_blocks(conn)
    idx = len(blocks)
    previous_hash = blocks[-1]["hash"] if blocks else "0"
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    digest = block_hash(idx, timestamp, transaction, previous_hash)
    conn.execute(
        "INSERT INTO blocks (idx, timestamp, transaction_json, previous_hash, hash) VALUES (?, ?, ?, ?, ?)",
        (idx, timestamp, canonical_json(transaction), previous_hash, digest),
    )


def register_property(conn, property_id, address, owner):
    property_id, address, owner = [x.strip() for x in (property_id, address, owner)]
    if not all((property_id, address, owner)):
        raise ValueError("Please fill in all fields.")
    if conn.execute("SELECT 1 FROM properties WHERE property_id = ?", (property_id,)).fetchone():
        raise ValueError("This Property ID already exists.")
    registered_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        conn.execute("BEGIN")
        add_block(conn, {
            "type": "PROPERTY_REGISTERED",
            "property_id": property_id,
            "address": address,
            "owner": owner,
            "registered_at": registered_at,
        })
        conn.execute(
            "INSERT INTO properties VALUES (?, ?, ?, ?)",
            (property_id, address, owner, registered_at),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def transfer_property(conn, property_id, current_owner, new_owner):
    property_id, current_owner, new_owner = [x.strip() for x in (property_id, current_owner, new_owner)]
    if not all((property_id, current_owner, new_owner)):
        raise ValueError("Please fill in all fields.")
    row = conn.execute("SELECT * FROM properties WHERE property_id = ?", (property_id,)).fetchone()
    if row is None:
        raise ValueError("Property not found. Register it first.")
    if row["owner"].casefold() != current_owner.casefold():
        raise ValueError(f"Current owner doesn't match. Registered owner is: {row['owner']}")
    if current_owner.casefold() == new_owner.casefold():
        raise ValueError("New owner must be different from current owner.")
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        conn.execute("BEGIN")
        add_block(conn, {
            "type": "OWNERSHIP_TRANSFERRED",
            "property_id": property_id,
            "address": row["address"],
            "previous_owner": row["owner"],
            "new_owner": new_owner,
            "transferred_at": timestamp,
        })
        conn.execute("UPDATE properties SET owner = ? WHERE property_id = ?", (new_owner, property_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def validate_chain(conn):
    blocks = get_blocks(conn)
    if not blocks:
        return False, "The chain is empty."
    for position, block in enumerate(blocks):
        expected_previous = "0" if position == 0 else blocks[position - 1]["hash"]
        if block["previous_hash"] != expected_previous:
            return False, f"Block {position}: previous hash mismatch."
        expected = block_hash(
            block["index"], block["timestamp"], block["transaction"], block["previous_hash"]
        )
        if block["hash"] != expected:
            return False, f"Block {position}: hash mismatch; possible tampering."
        if block["index"] != position:
            return False, f"Block index mismatch at position {position}."
    return True, f"Chain verified: {len(blocks)} blocks checked."


st.set_page_config(page_title="Real Estate Blockchain Registry", page_icon="🏢", layout="wide")

st.markdown("""
<style>
    .main {background-color: #f5f7fb;}
    .block-container {padding-top: 1.8rem; padding-bottom: 2rem;}
    .hero {padding: 1.2rem 1.5rem; border-radius: 16px; background: linear-gradient(120deg,#102a43,#176b87); color: white; margin-bottom: 1rem;}
    .hero h1 {color:white; margin-bottom: .25rem;}
    div[data-testid="stMetric"] {background:white; padding: 14px; border-radius: 12px; border: 1px solid #e6eaf0;}
</style>
""", unsafe_allow_html=True)

st.markdown(
    '<div class="hero"><h1>🏢 Real Estate Blockchain Registry</h1>'
    '<p>Register properties, transfer ownership, and inspect a tamper-evident transaction ledger.</p></div>',
    unsafe_allow_html=True,
)

conn = connect()
properties = conn.execute("SELECT * FROM properties ORDER BY registered_at DESC").fetchall()
blocks = get_blocks(conn)
transfers = sum(1 for b in blocks if b["transaction"].get("type") == "OWNERSHIP_TRANSFERRED")
valid, validation_message = validate_chain(conn)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Registered properties", len(properties))
m2.metric("Blockchain blocks", len(blocks))
m3.metric("Ownership transfers", transfers)
m4.metric("Chain status", "Valid" if valid else "Check required")

tab_dashboard, tab_register, tab_transfer, tab_explorer = st.tabs(
    ["🏠 Properties", "➕ Register property", "🔁 Transfer ownership", "⛓️ Blockchain Explorer"]
)

with tab_dashboard:
    st.subheader("Property register")
    search = st.text_input("Search by ID, address, or owner", placeholder="e.g. PROP001 or New Cairo")
    if search:
        term = f"%{search.strip()}%"
        rows = conn.execute(
            """SELECT property_id AS 'Property ID', address AS Address, owner AS 'Current owner',
                      registered_at AS 'Registered (UTC)'
               FROM properties WHERE property_id LIKE ? OR address LIKE ? OR owner LIKE ?
               ORDER BY registered_at DESC""", (term, term, term)
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT property_id AS 'Property ID', address AS Address, owner AS 'Current owner',
                      registered_at AS 'Registered (UTC)'
               FROM properties ORDER BY registered_at DESC"""
        ).fetchall()
    if rows:
        st.dataframe([dict(r) for r in rows], use_container_width=True, hide_index=True)
    else:
        st.info("No properties yet. Open 'Register property' to add the first one.")
    st.caption("Educational simulation only — this is not an official land registry or proof of legal ownership.")

with tab_register:
    st.subheader("Register a new property")
    with st.form("register_form", clear_on_submit=True):
        p_id = st.text_input("Property ID", placeholder="PROP001")
        address = st.text_input("Property address", placeholder="New Cairo, Egypt")
        owner = st.text_input("Owner name", placeholder="Ahmed Hassan")
        submitted = st.form_submit_button("Register property", type="primary", use_container_width=True)
    if submitted:
        try:
            register_property(conn, p_id, address, owner)
            st.success(f"Property {p_id.strip()} registered and recorded in a new block.")
            st.rerun()
        except (ValueError, sqlite3.Error) as exc:
            st.error(str(exc))

with tab_transfer:
    st.subheader("Transfer property ownership")
    with st.form("transfer_form", clear_on_submit=True):
        transfer_id = st.text_input("Property ID", placeholder="PROP001")
        current_owner = st.text_input("Current registered owner", placeholder="Ahmed Hassan")
        new_owner = st.text_input("New owner", placeholder="Mona Ali")
        transfer_submit = st.form_submit_button("Transfer ownership", type="primary", use_container_width=True)
    if transfer_submit:
        try:
            transfer_property(conn, transfer_id, current_owner, new_owner)
            st.success(f"Ownership transfer for {transfer_id.strip()} recorded in a new block.")
            st.rerun()
        except (ValueError, sqlite3.Error) as exc:
            st.error(str(exc))

with tab_explorer:
    st.subheader("Blockchain Explorer")
    left, right = st.columns([1, 2])
    with left:
        if valid:
            st.success(validation_message)
        else:
            st.error(validation_message)
        if st.button("Validate chain again", use_container_width=True):
            st.rerun()
    with right:
        property_ids = [r["property_id"] for r in properties]
        selected_id = st.selectbox("Show history for property", ["All transactions"] + property_ids)
    if selected_id == "All transactions":
        visible_blocks = blocks
    else:
        visible_blocks = [
            b for b in blocks
            if b["transaction"].get("property_id") == selected_id
        ]
    for block in reversed(visible_blocks):
        tx = block["transaction"]
        with st.expander(f"Block #{block['index']} — {tx.get('type', 'TRANSACTION')}"):
            st.write("Timestamp (UTC):", block["timestamp"])
            st.write("Previous hash")
            st.code(block["previous_hash"])
            st.write("Block hash")
            st.code(block["hash"])
            st.write("Transaction data")
            st.json(tx)
    st.caption("Each block stores the previous block's hash. This demo simulates a hash-linked ledger on one server; it is not a distributed blockchain network.")

conn.close()
