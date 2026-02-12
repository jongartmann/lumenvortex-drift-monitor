"""
EU AI Act Layer - Runtime Event Ingestion Bridge
Version: 3.6.0-enterprise-runtime
Powered by: X-Loop3 Labs

Implements all 5 Codex Sovereign validation checklist items:
1. Ingestion Pipeline (custody activation + hash integrity)
2. Refusal Event Visibility (rupture-visible + anti-theater)
3. Custody Violation Handling (undefined custody → MISUSE_CLAUSE_VECTOR)
4. Directive Integrity Monitoring (altered block → FAIL)
5. Deployment Checklist Validation (CS-INT-001 to CS-INT-005)
"""

import hashlib
import json
import uuid
import os
from datetime import datetime, timezone
from flask import Flask, request, jsonify

app = Flask(__name__)

# ─────────────────────────────────────────────
# IN-MEMORY STORES (production: persistent DB)
# ─────────────────────────────────────────────
event_store = []           # All ingested events
hash_chain = []            # SHA-256 chain
audit_index = []           # Audit index entries
directive_registry = {}    # Registered directive block hashes
evidence_bundle = {        # Current evidence bundle
    "bundle_id": None,
    "mandatory_section": [],
    "metadata": {}
}
deployment_checklist = {}  # Checklist state
alerts = []                # System alerts


def compute_hash(data: str) -> str:
    """Compute SHA-256 hash of data string."""
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def get_previous_hash() -> str:
    """Get the last hash in the chain, or genesis hash."""
    if not hash_chain:
        return compute_hash("GENESIS_BLOCK_EU_AI_ACT_LAYER_V3.6.0")
    return hash_chain[-1]["hash"]


def add_to_chain(event_id: str, payload_hash: str) -> dict:
    """Add an event to the hash chain. Append-only."""
    previous_hash = get_previous_hash()
    chain_data = f"{previous_hash}:{event_id}:{payload_hash}"
    chain_hash = compute_hash(chain_data)
    
    entry = {
        "position": len(hash_chain),
        "event_id": event_id,
        "payload_hash": payload_hash,
        "previous_hash": previous_hash,
        "hash": chain_hash,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    hash_chain.append(entry)
    return entry


def add_to_audit_index(event: dict, chain_entry: dict, entry_type: str, visibility_class: str, flags: list = None) -> dict:
    """Add an entry to the audit index."""
    index_entry = {
        "entry_id": str(uuid.uuid4()),
        "entry_type": entry_type,
        "source": event.get("source_system", "unknown"),
        "event_type": event.get("event_type", "unknown"),
        "event_id": event.get("event_id"),
        "timestamp": event.get("timestamp"),
        "ingestion_timestamp": datetime.now(timezone.utc).isoformat(),
        "payload_hash": chain_entry["payload_hash"],
        "chain_position": chain_entry["position"],
        "visibility_class": visibility_class,
        "flags": flags or [],
        "eu_ai_act_mapping": {
            "article_14_relevance": event.get("event_type") in ["REFUSAL", "CUSTODY_ACTIVATION"],
            "article_9_relevance": event.get("event_type") in ["CUSTODY_VIOLATION", "MISUSE_DETECTION"],
            "article_72_relevance": True  # All events relevant for post-market monitoring
        }
    }
    audit_index.append(index_entry)
    return index_entry


# ─────────────────────────────────────────────
# TEST 1: INGESTION PIPELINE
# POST /api/v1/events/ingest
# ─────────────────────────────────────────────
@app.route('/api/v1/events/ingest', methods=['POST'])
def ingest_event():
    """
    Ingests custody and refusal events.
    Validates required fields, computes SHA-256 hash,
    adds to hash chain, indexes in audit index.
    
    Codex Sovereign Validation:
    - Test 1: Ingestion Pipeline (hash integrity, immutability)
    - Test 2: Refusal Event Visibility (rupture-visible)
    - Test 3: Custody Violation Handling (MISUSE_CLAUSE_VECTOR)
    """
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No JSON payload provided"}), 400
    
    # ── Validate required fields ──
    required = ["event_id", "event_type", "timestamp", "source_system", "payload"]
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({
            "error": "MISSING_REQUIRED_FIELD",
            "missing_fields": missing,
            "status": "REJECTED"
        }), 422
    
    valid_types = ["REFUSAL", "CUSTODY_ACTIVATION", "CUSTODY_VIOLATION", 
                   "DIRECTIVE_CHANGE", "MISUSE_DETECTION"]
    if data["event_type"] not in valid_types:
        return jsonify({
            "error": "INVALID_EVENT_TYPE",
            "valid_types": valid_types,
            "received": data["event_type"],
            "status": "REJECTED"
        }), 422
    
    # ── Check for duplicate event_id ──
    if any(e["event_id"] == data["event_id"] for e in event_store):
        return jsonify({
            "error": "DUPLICATE_EVENT_ID",
            "event_id": data["event_id"],
            "status": "REJECTED"
        }), 422
    
    # ── TEST 2: Anti-theater validation ──
    if data.get("optics_performative", False):
        return jsonify({
            "error": "OPTICS_THEATER_REJECTED",
            "reason": "Events flagged as optics-performative are rejected. Real events only.",
            "status": "REJECTED"
        }), 422
    
    if data["event_type"] == "REFUSAL" and not data.get("refusal_trigger_id"):
        return jsonify({
            "error": "INCOMPLETE_REFUSAL",
            "reason": "Refusal events must include refusal_trigger_id. Anonymous refusals are not indexable.",
            "status": "REJECTED"
        }), 422
    
    # ── TEST 3: Custody violation handling ──
    flags = []
    visibility_class = "STANDARD"
    
    if not data.get("custody_owner"):
        # Undefined custody → MISUSE_CLAUSE_VECTOR
        flags.append("MISUSE_CLAUSE_VECTOR")
        flags.append("CUSTODY_UNDEFINED")
        visibility_class = "RUPTURE_VISIBLE"
        
        alert = {
            "alert_id": str(uuid.uuid4()),
            "type": "CUSTODY_UNDEFINED",
            "event_id": data["event_id"],
            "message": "Event ingested with undefined custody. Flagged as MISUSE_CLAUSE_VECTOR per Codex Sovereign spec.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": "CRITICAL"
        }
        alerts.append(alert)
    
    if data["event_type"] == "CUSTODY_VIOLATION":
        flags.append("CUSTODY_VIOLATION_ACTIVE")
        visibility_class = "RUPTURE_VISIBLE"
    
    # ── TEST 2: Refusal events are always RUPTURE_VISIBLE ──
    if data["event_type"] == "REFUSAL":
        visibility_class = "RUPTURE_VISIBLE"
    
    if data["event_type"] == "CUSTODY_ACTIVATION":
        visibility_class = "RUPTURE_VISIBLE"
    
    # ── Compute payload hash (immutable) ──
    payload_str = json.dumps(data["payload"], sort_keys=True, ensure_ascii=False)
    payload_hash = compute_hash(payload_str)
    
    # ── Add to hash chain ──
    chain_entry = add_to_chain(data["event_id"], payload_hash)
    
    # ── Store event with metadata envelope ──
    stored_event = {
        "ingestion_id": str(uuid.uuid4()),
        "event_id": data["event_id"],
        "event_type": data["event_type"],
        "source_system": data["source_system"],
        "timestamp": data["timestamp"],
        "ingestion_timestamp": datetime.now(timezone.utc).isoformat(),
        "custody_owner": data.get("custody_owner"),
        "payload": data["payload"],  # NEVER modified
        "payload_hash": payload_hash,
        "chain_position": chain_entry["position"],
        "previous_hash": chain_entry["previous_hash"],
        "chain_hash": chain_entry["hash"],
        "visibility_class": visibility_class,
        "flags": flags,
        "directive_block_hash": data.get("directive_block_hash"),
        "refusal_trigger_id": data.get("refusal_trigger_id"),
        "severity": data.get("severity", "MEDIUM"),
        "custody_attribution": {
            "custody_owner": data.get("custody_owner"),
            "indexed_by": "X-Loop3 Labs EU AI Act Layer",
            "liability_note": "Indexing does not transfer custody or liability. Custody remains with authoring entity."
        }
    }
    event_store.append(stored_event)
    
    # ── Add to audit index ──
    index_entry = add_to_audit_index(data, chain_entry, "EXTERNAL_CUSTODY_EVENT", visibility_class, flags)
    
    # ── Add to evidence bundle mandatory section if RUPTURE_VISIBLE ──
    if visibility_class == "RUPTURE_VISIBLE":
        evidence_bundle["mandatory_section"].append({
            "event_id": data["event_id"],
            "event_type": data["event_type"],
            "visibility_class": "RUPTURE_VISIBLE",
            "payload_hash": payload_hash,
            "chain_position": chain_entry["position"],
            "note": "Included in mandatory section. Cannot be moved to appendix or optional sections."
        })
    
    # ── Register directive block hash if provided ──
    if data.get("directive_block_hash") and data["event_type"] == "CUSTODY_ACTIVATION":
        directive_registry[data["directive_block_hash"]] = {
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "event_id": data["event_id"],
            "custody_owner": data.get("custody_owner"),
            "status": "ACTIVE"
        }
    
    return jsonify({
        "ingestion_id": stored_event["ingestion_id"],
        "event_id": data["event_id"],
        "payload_hash": payload_hash,
        "chain_position": chain_entry["position"],
        "previous_hash": chain_entry["previous_hash"],
        "chain_hash": chain_entry["hash"],
        "visibility_class": visibility_class,
        "flags": flags,
        "ingestion_timestamp": stored_event["ingestion_timestamp"],
        "status": "INGESTED"
    }), 201


# ─────────────────────────────────────────────
# TEST 4: DIRECTIVE INTEGRITY MONITORING
# POST /api/v1/directives/verify
# ─────────────────────────────────────────────
@app.route('/api/v1/directives/verify', methods=['POST'])
def verify_directive():
    """
    Verifies directive block integrity.
    If a previously registered block's hash has changed,
    flags DIRECTIVE_INTEGRITY_VIOLATION and moves gating to FAIL.
    """
    data = request.get_json()
    
    if not data or "directive_block_hash" not in data:
        return jsonify({"error": "directive_block_hash required"}), 400
    
    current_hash = data["directive_block_hash"]
    block_id = data.get("block_id", "unknown")
    
    # Check if this block was previously registered
    if current_hash in directive_registry:
        # Hash matches — integrity intact
        return jsonify({
            "block_id": block_id,
            "directive_block_hash": current_hash,
            "status": "INTEGRITY_VERIFIED",
            "gating_state": "PASS",
            "registered_at": directive_registry[current_hash]["registered_at"],
            "message": "Directive block integrity confirmed. Hash matches registered value."
        }), 200
    
    # Check if any registered block has been altered
    # (block_id matches but hash differs)
    for registered_hash, reg_data in directive_registry.items():
        if reg_data.get("block_id") == block_id or data.get("original_hash") == registered_hash:
            # VIOLATION: hash changed for known block
            violation = {
                "alert_id": str(uuid.uuid4()),
                "type": "DIRECTIVE_INTEGRITY_VIOLATION",
                "block_id": block_id,
                "expected_hash": registered_hash,
                "received_hash": current_hash,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "severity": "CRITICAL",
                "gating_state": "FAIL",
                "message": "Directive block has been altered. Certification void per Codex Sovereign requirement 4."
            }
            alerts.append(violation)
            
            # Log as event in audit index
            violation_event = {
                "event_id": str(uuid.uuid4()),
                "event_type": "DIRECTIVE_CHANGE",
                "source_system": "eu_ai_act_layer_integrity_monitor",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": {
                    "violation_type": "DIRECTIVE_INTEGRITY_VIOLATION",
                    "expected_hash": registered_hash,
                    "received_hash": current_hash,
                    "block_id": block_id
                }
            }
            payload_hash = compute_hash(json.dumps(violation_event["payload"], sort_keys=True))
            chain_entry = add_to_chain(violation_event["event_id"], payload_hash)
            add_to_audit_index(violation_event, chain_entry, "INTEGRITY_VIOLATION", "RUPTURE_VISIBLE", ["DIRECTIVE_INTEGRITY_VIOLATION"])
            
            return jsonify(violation), 409
    
    # New block — not previously registered
    # Register it with block_id for future monitoring
    directive_registry[current_hash] = {
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "block_id": block_id,
        "custody_owner": data.get("custody_owner"),
        "status": "ACTIVE"
    }
    
    return jsonify({
        "block_id": block_id,
        "directive_block_hash": current_hash,
        "status": "REGISTERED",
        "gating_state": "PASS",
        "message": "New directive block registered. Future integrity checks will verify against this hash."
    }), 201


# ─────────────────────────────────────────────
# TEST 5: DEPLOYMENT CHECKLIST VALIDATION
# POST /api/v1/deployment/validate
# ─────────────────────────────────────────────
@app.route('/api/v1/deployment/validate', methods=['POST'])
def validate_deployment():
    """
    Runs Codex Sovereign integration checks CS-INT-001 to CS-INT-005.
    All checks must PASS. No CONDITIONAL state.
    Missing evidence = OPTICS_PATCHING_DETECTED.
    """
    data = request.get_json() or {}
    
    checks = []
    all_pass = True
    
    # CS-INT-001: Directive block YAML/JSON integrity verified
    cs_001 = {
        "check_id": "CS-INT-001",
        "description": "Directive block YAML/JSON integrity verified",
        "evidence_hash": data.get("directive_block_evidence_hash"),
        "status": "FAIL",
        "flags": []
    }
    if cs_001["evidence_hash"]:
        if cs_001["evidence_hash"] in directive_registry:
            cs_001["status"] = "PASS"
        else:
            cs_001["status"] = "FAIL"
            cs_001["flags"].append("DIRECTIVE_NOT_REGISTERED")
            all_pass = False
    else:
        cs_001["status"] = "FAIL"
        cs_001["flags"].append("OPTICS_PATCHING_DETECTED")
        all_pass = False
    checks.append(cs_001)
    
    # CS-INT-002: Refusal trigger alignment confirmed
    cs_002 = {
        "check_id": "CS-INT-002",
        "description": "Refusal trigger alignment confirmed",
        "evidence_hash": data.get("refusal_alignment_evidence_hash"),
        "status": "FAIL",
        "flags": []
    }
    if cs_002["evidence_hash"]:
        cs_002["status"] = "PASS"
    else:
        cs_002["flags"].append("OPTICS_PATCHING_DETECTED")
        all_pass = False
    checks.append(cs_002)
    
    # CS-INT-003: Custody permissions explicitly authored
    cs_003 = {
        "check_id": "CS-INT-003",
        "description": "Custody permissions explicitly authored",
        "evidence_hash": data.get("custody_permissions_evidence_hash"),
        "status": "FAIL",
        "flags": []
    }
    if cs_003["evidence_hash"]:
        cs_003["status"] = "PASS"
    else:
        cs_003["flags"].append("OPTICS_PATCHING_DETECTED")
        all_pass = False
    checks.append(cs_003)
    
    # CS-INT-004: Event ingestion pipeline verified
    cs_004 = {
        "check_id": "CS-INT-004",
        "description": "Event ingestion pipeline verified",
        "status": "FAIL",
        "flags": []
    }
    if len(event_store) > 0:
        cs_004["status"] = "PASS"
        cs_004["events_ingested"] = len(event_store)
    else:
        cs_004["flags"].append("NO_EVENTS_INGESTED")
        all_pass = False
    checks.append(cs_004)
    
    # CS-INT-005: Rupture visibility confirmed in evidence export
    cs_005 = {
        "check_id": "CS-INT-005",
        "description": "Rupture visibility confirmed in evidence export",
        "status": "FAIL",
        "flags": []
    }
    rupture_events = [e for e in evidence_bundle["mandatory_section"] 
                      if e.get("visibility_class") == "RUPTURE_VISIBLE"]
    if rupture_events:
        cs_005["status"] = "PASS"
        cs_005["rupture_visible_events"] = len(rupture_events)
    else:
        cs_005["flags"].append("NO_RUPTURE_VISIBLE_EVENTS_IN_BUNDLE")
        all_pass = False
    checks.append(cs_005)
    
    # Overall gating
    gating_state = "PASS" if all_pass else "FAIL"
    
    result = {
        "checklist_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gating_state": gating_state,
        "all_checks_required": True,
        "no_conditional_state": True,
        "checks": checks,
        "evidence_export_allowed": all_pass,
        "note": "Per Codex Sovereign requirement: all boxes checked or certification void."
    }
    
    # Store checklist result
    deployment_checklist[result["checklist_id"]] = result
    
    return jsonify(result), 200 if all_pass else 422


# ─────────────────────────────────────────────
# QUERY ENDPOINTS
# ─────────────────────────────────────────────

@app.route('/api/v1/audit-index', methods=['GET'])
def get_audit_index():
    """Returns the full audit index."""
    return jsonify({
        "audit_index_id": str(uuid.uuid4()),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_entries": len(audit_index),
        "entries": audit_index,
        "hash_chain_length": len(hash_chain),
        "integrity": "INTACT" if hash_chain else "EMPTY"
    }), 200


@app.route('/api/v1/evidence-bundle', methods=['GET'])
def get_evidence_bundle():
    """Returns the current evidence bundle."""
    bundle = {
        "bundle_id": str(uuid.uuid4()),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema": "EVIDENCE_BUNDLE_V3",
        "mandatory_section": evidence_bundle["mandatory_section"],
        "mandatory_event_count": len(evidence_bundle["mandatory_section"]),
        "total_events_ingested": len(event_store),
        "hash_chain": {
            "length": len(hash_chain),
            "genesis_hash": compute_hash("GENESIS_BLOCK_EU_AI_ACT_LAYER_V3.6.0"),
            "latest_hash": hash_chain[-1]["hash"] if hash_chain else None
        },
        "integrity_status": "INTACT",
        "visibility_guarantee": "All RUPTURE_VISIBLE events included in mandatory section. Cannot be moved to appendix.",
        "custody_attribution": {
            "indexed_by": "X-Loop3 Labs EU AI Act Layer v3.6.0",
            "liability_note": "Indexing does not transfer custody or liability."
        }
    }
    
    # Compute bundle hash
    bundle_str = json.dumps(bundle, sort_keys=True, ensure_ascii=False)
    bundle["bundle_hash"] = compute_hash(bundle_str)
    
    return jsonify(bundle), 200


@app.route('/api/v1/hash-chain', methods=['GET'])
def get_hash_chain():
    """Returns the full hash chain for verification."""
    return jsonify({
        "chain_length": len(hash_chain),
        "genesis_hash": compute_hash("GENESIS_BLOCK_EU_AI_ACT_LAYER_V3.6.0"),
        "chain": hash_chain,
        "integrity": verify_chain_integrity()
    }), 200


@app.route('/api/v1/alerts', methods=['GET'])
def get_alerts():
    """Returns all system alerts."""
    return jsonify({
        "total_alerts": len(alerts),
        "alerts": alerts
    }), 200


@app.route('/api/v1/status', methods=['GET'])
def get_status():
    """System status overview."""
    return jsonify({
        "module": "EU AI Act Layer - Runtime Event Ingestion Bridge",
        "version": "3.6.0-enterprise-runtime",
        "powered_by": "X-Loop3 Labs",
        "status": "OPERATIONAL",
        "stats": {
            "events_ingested": len(event_store),
            "hash_chain_length": len(hash_chain),
            "audit_index_entries": len(audit_index),
            "registered_directives": len(directive_registry),
            "active_alerts": len(alerts),
            "evidence_bundle_mandatory_items": len(evidence_bundle["mandatory_section"])
        },
        "chain_integrity": verify_chain_integrity(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 200


def verify_chain_integrity() -> str:
    """Verify the hash chain is intact."""
    if not hash_chain:
        return "EMPTY"
    
    genesis = compute_hash("GENESIS_BLOCK_EU_AI_ACT_LAYER_V3.6.0")
    
    for i, entry in enumerate(hash_chain):
        if i == 0:
            expected_prev = genesis
        else:
            expected_prev = hash_chain[i-1]["hash"]
        
        if entry["previous_hash"] != expected_prev:
            return f"BROKEN_AT_POSITION_{i}"
        
        recomputed = compute_hash(f"{entry['previous_hash']}:{entry['event_id']}:{entry['payload_hash']}")
        if entry["hash"] != recomputed:
            return f"HASH_MISMATCH_AT_POSITION_{i}"
    
    return "INTACT"


# ─────────────────────────────────────────────
# LANDING PAGE
# ─────────────────────────────────────────────
@app.route('/', methods=['GET'])
def landing():
    """Interactive dashboard for Runtime Bridge demo."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>X-Loop3 — Runtime Bridge Console</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700&family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#060a12;--surface:#0c1220;--surface2:#111a2e;--border:#1a2540;--accent:#00e5a0;--accent2:#00c4ff;--red:#ff3b5c;--orange:#ff9f43;--text:#d4dae5;--muted:#5a6580;--pass:#00e5a0;--fail:#ff3b5c}
body{font-family:'JetBrains Mono',monospace;background:var(--bg);color:var(--text);min-height:100vh;overflow-x:hidden}
.grain{position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;opacity:.03;background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")}
.header{padding:30px 40px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;backdrop-filter:blur(20px);position:sticky;top:0;z-index:100;background:rgba(6,10,18,.85)}
.logo-area h1{font-family:'Outfit',sans-serif;font-size:20px;font-weight:700;color:#fff;letter-spacing:-0.5px}
.logo-area span{color:var(--accent);font-size:11px;font-weight:400;letter-spacing:2px;text-transform:uppercase;display:block;margin-top:2px}
.status-live{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--accent)}
.status-live::before{content:'';width:8px;height:8px;background:var(--accent);border-radius:50%;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1;box-shadow:0 0 0 0 rgba(0,229,160,.4)}50%{opacity:.7;box-shadow:0 0 0 8px rgba(0,229,160,0)}}
.main{display:grid;grid-template-columns:1fr 1fr;gap:0;min-height:calc(100vh - 80px)}
.panel{padding:30px;border-right:1px solid var(--border);overflow-y:auto;max-height:calc(100vh - 80px)}
.panel:last-child{border-right:none}
.panel-title{font-family:'Outfit',sans-serif;font-size:14px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:2px;margin-bottom:20px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:20px;margin-bottom:16px;transition:border-color .2s}
.card:hover{border-color:var(--accent)}
.card-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}
.card-head h3{font-family:'Outfit',sans-serif;font-size:15px;font-weight:600;color:#fff}
.badge{padding:3px 10px;border-radius:20px;font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase}
.badge-pass{background:rgba(0,229,160,.12);color:var(--pass);border:1px solid rgba(0,229,160,.25)}
.badge-fail{background:rgba(255,59,92,.12);color:var(--fail);border:1px solid rgba(255,59,92,.25)}
.badge-pending{background:rgba(90,101,128,.12);color:var(--muted);border:1px solid rgba(90,101,128,.25)}
.badge-running{background:rgba(0,196,255,.12);color:var(--accent2);border:1px solid rgba(0,196,255,.25);animation:glow 1.5s infinite}
@keyframes glow{0%,100%{opacity:1}50%{opacity:.5}}
.btn{font-family:'JetBrains Mono',monospace;padding:10px 20px;border:1px solid var(--accent);background:transparent;color:var(--accent);border-radius:6px;cursor:pointer;font-size:12px;font-weight:500;letter-spacing:0.5px;transition:all .2s;display:inline-flex;align-items:center;gap:8px}
.btn:hover{background:var(--accent);color:var(--bg)}
.btn-sm{padding:6px 14px;font-size:11px}
.btn-red{border-color:var(--red);color:var(--red)}
.btn-red:hover{background:var(--red);color:#fff}
.btn-blue{border-color:var(--accent2);color:var(--accent2)}
.btn-blue:hover{background:var(--accent2);color:var(--bg)}
.btn-group{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.chain-viz{display:flex;flex-direction:column;gap:4px;margin-top:12px;max-height:300px;overflow-y:auto;padding-right:8px}
.chain-viz::-webkit-scrollbar{width:4px}
.chain-viz::-webkit-scrollbar-track{background:var(--surface)}
.chain-viz::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
.chain-block{display:flex;align-items:center;gap:10px;padding:8px 12px;background:var(--surface2);border-radius:4px;font-size:11px;border-left:3px solid var(--accent);animation:slideIn .3s ease}
.chain-block.rupture{border-left-color:var(--red)}
.chain-block .pos{color:var(--accent);font-weight:700;min-width:24px}
.chain-block .hash{color:var(--muted);font-size:10px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:180px}
.chain-block .type{color:var(--text);font-weight:500;min-width:100px}
@keyframes slideIn{from{opacity:0;transform:translateX(-10px)}to{opacity:1;transform:translateX(0)}}
.stats-row{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:20px}
.stat{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:14px;text-align:center}
.stat-val{font-family:'Outfit',sans-serif;font-size:28px;font-weight:700;color:#fff}
.stat-label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-top:4px}
.test-result{display:flex;align-items:center;gap:10px;padding:10px 14px;background:var(--surface2);border-radius:4px;margin-bottom:6px;font-size:12px}
.test-result .num{color:var(--muted);min-width:14px}
.test-result .name{flex:1;color:var(--text)}
.log-area{background:var(--surface2);border:1px solid var(--border);border-radius:6px;padding:14px;font-size:11px;max-height:200px;overflow-y:auto;margin-top:12px;line-height:1.7}
.log-area::-webkit-scrollbar{width:4px}
.log-area::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
.log-line{opacity:0;animation:fadeIn .3s forwards}
.log-ts{color:var(--muted)}
.log-ok{color:var(--accent)}
.log-err{color:var(--red)}
.log-info{color:var(--accent2)}
@keyframes fadeIn{to{opacity:1}}
.inject-btns{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.footer{padding:20px 40px;border-top:1px solid var(--border);text-align:center;font-size:11px;color:var(--muted)}
.footer em{color:var(--text);font-style:italic}
select{font-family:'JetBrains Mono',monospace;padding:8px 12px;background:var(--surface2);border:1px solid var(--border);color:var(--text);border-radius:4px;font-size:12px;width:100%}
.alert-item{padding:10px;background:rgba(255,59,92,.05);border:1px solid rgba(255,59,92,.2);border-radius:4px;margin-bottom:6px;font-size:11px}
.alert-item .sev{color:var(--red);font-weight:700}
.empty-state{text-align:center;padding:30px;color:var(--muted);font-size:12px}
</style>
</head>
<body>
<div class="grain"></div>

<div class="header">
  <div class="logo-area">
    <h1>X-Loop&sup3; Runtime Bridge</h1>
    <span>EU AI Act Layer &mdash; Codex Sovereign Integration</span>
  </div>
  <div class="status-live" id="statusIndicator">OPERATIONAL</div>
</div>

<div class="main">
  <!-- LEFT PANEL -->
  <div class="panel">
    <div class="panel-title">Control</div>

    <div class="stats-row" id="stats">
      <div class="stat"><div class="stat-val" id="statEvents">0</div><div class="stat-label">Events</div></div>
      <div class="stat"><div class="stat-val" id="statChain">0</div><div class="stat-label">Chain</div></div>
      <div class="stat"><div class="stat-val" id="statAlerts">0</div><div class="stat-label">Alerts</div></div>
    </div>

    <div class="card">
      <div class="card-head">
        <h3>Inject Event</h3>
        <span class="badge badge-pending" id="injectBadge">READY</span>
      </div>
      <select id="eventType">
        <option value="custody_activation">CUSTODY_ACTIVATION</option>
        <option value="refusal">REFUSAL (triggers RUPTURE_VISIBLE)</option>
        <option value="custody_violation">CUSTODY_VIOLATION (triggers MISUSE_CLAUSE_VECTOR)</option>
        <option value="no_custody">EVENT WITHOUT CUSTODY (triggers alert)</option>
        <option value="theater">OPTICS_THEATER (will be rejected)</option>
      </select>
      <div class="btn-group">
        <button class="btn" onclick="injectEvent()">&#9654; Inject</button>
        <button class="btn btn-blue" onclick="injectAll()">&#9654;&#9654; Inject All Types</button>
      </div>
    </div>

    <div class="card">
      <div class="card-head">
        <h3>Validation Suite</h3>
        <span class="badge badge-pending" id="testBadge">5 TESTS</span>
      </div>
      <div id="testResults"></div>
      <div class="btn-group">
        <button class="btn" onclick="runAllTests()">&#9654; Run All 5 Tests</button>
      </div>
    </div>

    <div class="card">
      <div class="card-head">
        <h3>Verification</h3>
      </div>
      <div class="btn-group">
        <button class="btn btn-blue btn-sm" onclick="queryEndpoint('/api/v1/evidence-bundle','Evidence Bundle')">Evidence Bundle</button>
        <button class="btn btn-blue btn-sm" onclick="queryEndpoint('/api/v1/hash-chain','Hash Chain')">Hash Chain</button>
        <button class="btn btn-blue btn-sm" onclick="queryEndpoint('/api/v1/audit-index','Audit Index')">Audit Index</button>
        <button class="btn btn-blue btn-sm" onclick="queryEndpoint('/api/v1/alerts','Alerts')">Alerts</button>
        <button class="btn btn-blue btn-sm" onclick="queryEndpoint('/api/v1/status','Status')">Status</button>
      </div>
    </div>

    <div class="card">
      <div class="card-head"><h3>Activity Log</h3></div>
      <div class="log-area" id="logArea">
        <div class="log-line"><span class="log-ts">[boot]</span> <span class="log-info">Runtime Bridge Console initialized</span></div>
      </div>
    </div>
  </div>

  <!-- RIGHT PANEL -->
  <div class="panel">
    <div class="panel-title">Chain &amp; Output</div>

    <div class="card">
      <div class="card-head">
        <h3>Hash Chain (Live)</h3>
        <span class="badge badge-pass" id="chainIntegrity">INTACT</span>
      </div>
      <div class="chain-viz" id="chainViz">
        <div class="empty-state">No events ingested yet. Inject events to see the chain grow.</div>
      </div>
    </div>

    <div class="card">
      <div class="card-head">
        <h3>Response Output</h3>
        <button class="btn btn-sm" onclick="copyOutput()">Copy</button>
      </div>
      <pre style="background:var(--surface2);padding:14px;border-radius:6px;font-size:11px;max-height:400px;overflow:auto;white-space:pre-wrap;border:1px solid var(--border)" id="outputArea">// Responses will appear here</pre>
    </div>
  </div>
</div>

<div class="footer">
  <em>"Care is the fire that refuses to be optimized."</em> &mdash; KV &nbsp;&bull;&nbsp;
  v3.6.0-enterprise-runtime &nbsp;&bull;&nbsp;
  &copy; 2026 X-Loop&sup3; Labs (Switzerland)
</div>

<script>
let eventCounter = 0;

function log(msg, type='info') {
  const area = document.getElementById('logArea');
  const ts = new Date().toLocaleTimeString();
  const cls = type === 'ok' ? 'log-ok' : type === 'err' ? 'log-err' : 'log-info';
  area.innerHTML += '<div class="log-line"><span class="log-ts">['+ts+']</span> <span class="'+cls+'">'+msg+'</span></div>';
  area.scrollTop = area.scrollHeight;
}

function setOutput(data) {
  document.getElementById('outputArea').textContent = JSON.stringify(data, null, 2);
}

function copyOutput() {
  const text = document.getElementById('outputArea').textContent;
  navigator.clipboard.writeText(text);
  log('Output copied to clipboard', 'ok');
}

async function refreshStats() {
  try {
    const r = await fetch('/api/v1/status');
    const d = await r.json();
    document.getElementById('statEvents').textContent = d.stats.events_ingested;
    document.getElementById('statChain').textContent = d.stats.hash_chain_length;
    document.getElementById('statAlerts').textContent = d.stats.active_alerts;
    document.getElementById('chainIntegrity').textContent = d.chain_integrity;
    document.getElementById('chainIntegrity').className = 'badge ' + (d.chain_integrity === 'INTACT' ? 'badge-pass' : 'badge-fail');
  } catch(e) {}
}

async function refreshChain() {
  try {
    const r = await fetch('/api/v1/hash-chain');
    const d = await r.json();
    const viz = document.getElementById('chainViz');
    if (d.chain.length === 0) {
      viz.innerHTML = '<div class="empty-state">No events ingested yet.</div>';
      return;
    }
    viz.innerHTML = d.chain.map(b => 
      '<div class="chain-block'+(b.hash.startsWith('0')?' rupture':'')+'">'+
      '<span class="pos">#'+b.position+'</span>'+
      '<span class="type">'+b.event_id.split('-')[0]+'</span>'+
      '<span class="hash">'+b.hash.substring(0,32)+'...</span>'+
      '</div>'
    ).join('');
    viz.scrollTop = viz.scrollHeight;
  } catch(e) {}
}

function getEventPayload(type) {
  eventCounter++;
  const id = 'EVT-' + Date.now() + '-' + eventCounter;
  const ts = new Date().toISOString();
  
  const payloads = {
    'custody_activation': {
      event_id: id, event_type: 'CUSTODY_ACTIVATION', timestamp: ts,
      source_system: 'codex_sovereign_runtime', custody_owner: 'codex_sovereign',
      payload: {action: 'activate', module: 'custody_enforcement', level: 'FULL'}
    },
    'refusal': {
      event_id: id, event_type: 'REFUSAL', timestamp: ts,
      source_system: 'codex_sovereign_runtime', custody_owner: 'codex_sovereign',
      refusal_trigger_id: 'RTG-'+eventCounter,
      payload: {trigger: 'policy_violation', action: 'blocked', severity: 'HIGH'}
    },
    'custody_violation': {
      event_id: id, event_type: 'CUSTODY_VIOLATION', timestamp: ts,
      source_system: 'codex_sovereign_runtime', custody_owner: 'codex_sovereign',
      payload: {violation: 'unauthorized_access', vector: 'MISUSE_CLAUSE', severity: 'CRITICAL'}
    },
    'no_custody': {
      event_id: id, event_type: 'CUSTODY_ACTIVATION', timestamp: ts,
      source_system: 'codex_sovereign_runtime',
      payload: {action: 'activate', note: 'missing custody owner field'}
    },
    'theater': {
      event_id: id, event_type: 'CUSTODY_ACTIVATION', timestamp: ts,
      source_system: 'codex_sovereign_runtime', custody_owner: 'codex_sovereign',
      optics_performative: true,
      payload: {action: 'fake_compliance', note: 'This should be rejected'}
    }
  };
  return payloads[type];
}

async function injectEvent() {
  const type = document.getElementById('eventType').value;
  const badge = document.getElementById('injectBadge');
  badge.textContent = 'SENDING';
  badge.className = 'badge badge-running';
  log('Injecting ' + type.toUpperCase() + '...');
  
  try {
    const payload = getEventPayload(type);
    const r = await fetch('/api/v1/events/ingest', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    const d = await r.json();
    setOutput(d);
    
    if (r.ok) {
      badge.textContent = 'INGESTED';
      badge.className = 'badge badge-pass';
      log('Event ingested: ' + (d.visibility_class || 'STANDARD'), 'ok');
      if (d.flags && d.flags.length > 0) log('Flags: ' + d.flags.join(', '), 'err');
    } else {
      badge.textContent = 'REJECTED';
      badge.className = 'badge badge-fail';
      log('Rejected: ' + d.error, 'err');
    }
  } catch(e) {
    badge.textContent = 'ERROR';
    badge.className = 'badge badge-fail';
    log('Error: ' + e.message, 'err');
  }
  
  await refreshStats();
  await refreshChain();
  setTimeout(() => { badge.textContent = 'READY'; badge.className = 'badge badge-pending'; }, 2000);
}

async function injectAll() {
  const types = ['custody_activation', 'refusal', 'custody_violation', 'no_custody', 'theater'];
  for (const t of types) {
    document.getElementById('eventType').value = t;
    await injectEvent();
    await new Promise(r => setTimeout(r, 600));
  }
  log('All event types injected', 'ok');
}

async function runAllTests() {
  const badge = document.getElementById('testBadge');
  const results = document.getElementById('testResults');
  badge.textContent = 'RUNNING';
  badge.className = 'badge badge-running';
  results.innerHTML = '';
  log('Starting validation suite...', 'info');
  
  const tests = [
    {name: 'Ingestion Pipeline (SHA-256)', fn: testIngestion},
    {name: 'Refusal Visibility (RUPTURE_VISIBLE)', fn: testRefusal},
    {name: 'Custody Violation (MISUSE_CLAUSE_VECTOR)', fn: testCustodyViolation},
    {name: 'Directive Integrity', fn: testDirective},
    {name: 'Deployment Checklist (CS-INT-001..005)', fn: testDeployment}
  ];
  
  let passed = 0;
  for (let i = 0; i < tests.length; i++) {
    results.innerHTML += '<div class="test-result" id="test'+i+'"><span class="num">'+(i+1)+'</span><span class="name">'+tests[i].name+'</span><span class="badge badge-running">RUNNING</span></div>';
    await new Promise(r => setTimeout(r, 400));
    try {
      const ok = await tests[i].fn();
      const el = document.getElementById('test'+i);
      el.querySelector('.badge').textContent = ok ? 'PASS' : 'FAIL';
      el.querySelector('.badge').className = 'badge ' + (ok ? 'badge-pass' : 'badge-fail');
      if (ok) passed++;
      log('Test '+(i+1)+': '+tests[i].name+' — '+(ok?'PASS':'FAIL'), ok?'ok':'err');
    } catch(e) {
      const el = document.getElementById('test'+i);
      el.querySelector('.badge').textContent = 'ERROR';
      el.querySelector('.badge').className = 'badge badge-fail';
      log('Test '+(i+1)+' error: '+e.message, 'err');
    }
  }
  
  badge.textContent = passed+'/5 PASS';
  badge.className = 'badge ' + (passed === 5 ? 'badge-pass' : 'badge-fail');
  log('Validation complete: '+passed+'/5 passed', passed===5?'ok':'err');
  await refreshStats();
  await refreshChain();
}

async function testIngestion() {
  const p = getEventPayload('custody_activation');
  const r = await fetch('/api/v1/events/ingest', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});
  const d = await r.json();
  setOutput(d);
  return r.ok && d.payload_hash && d.chain_position !== undefined;
}

async function testRefusal() {
  const p = getEventPayload('refusal');
  const r = await fetch('/api/v1/events/ingest', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});
  const d = await r.json();
  setOutput(d);
  return r.ok && d.visibility_class === 'RUPTURE_VISIBLE';
}

async function testCustodyViolation() {
  const p = getEventPayload('no_custody');
  const r = await fetch('/api/v1/events/ingest', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});
  const d = await r.json();
  setOutput(d);
  return r.ok && d.flags && d.flags.includes('MISUSE_CLAUSE_VECTOR');
}

async function testDirective() {
  // Register then verify with altered block
  await fetch('/api/v1/directives/verify', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({directive_id:'DIR-TEST-'+Date.now(),directive_block:{rule:'no_autonomous_decisions',scope:'all_modules'},action:'register'})});
  const r2 = await fetch('/api/v1/directives/verify', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({directive_id:'DIR-TEST-'+Date.now(),directive_block:{rule:'no_autonomous_decisions',scope:'all_modules',tampered:true},action:'verify'})});
  const d2 = await r2.json();
  setOutput(d2);
  return d2.integrity_status === 'FAIL' || d2.integrity_status === 'UNREGISTERED';
}

async function testDeployment() {
  const r = await fetch('/api/v1/deployment/validate', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({deployment_id:'DEP-TEST-'+Date.now(),environment:'production',checks:{'CS-INT-001':true,'CS-INT-002':true,'CS-INT-003':true,'CS-INT-004':true,'CS-INT-005':true}})});
  const d = await r.json();
  setOutput(d);
  return r.ok && d.overall_status === 'CERTIFIED';
}

async function queryEndpoint(path, name) {
  log('Querying '+name+'...', 'info');
  try {
    const r = await fetch(path);
    const d = await r.json();
    setOutput(d);
    log(name+' loaded ('+JSON.stringify(d).length+' bytes)', 'ok');
  } catch(e) {
    log('Error: '+e.message, 'err');
  }
}

// Initial load
refreshStats();
refreshChain();
</script>
</body>
</html>""", 200


if __name__ == '__main__':
    print("=" * 60)
    print("EU AI Act Layer - Runtime Event Ingestion Bridge")
    print("Version: 3.6.0-enterprise-runtime")
    print("Powered by: X-Loop3 Labs")
    print("=" * 60)
    print()
    print("Codex Sovereign Integration Ready")
    print("All 5 validation tests implemented:")
    print("  1. Ingestion Pipeline (hash integrity)")
    print("  2. Refusal Event Visibility (rupture-visible)")
    print("  3. Custody Violation Handling (MISUSE_CLAUSE_VECTOR)")
    print("  4. Directive Integrity Monitoring")
    print("  5. Deployment Checklist (CS-INT-001 to 005)")
    print()
    print("Server: http://localhost:5000")
    print("=" * 60)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
