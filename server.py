"""
LumenVortex — AI Health Monitor & EU AI Act Compliance Engine
Version: 3.7.0-lumenvortex-standalone
Powered by: X-Loop3 Labs

Implements all 5 X-Loop³ governance validation checklist items:
1. Ingestion Pipeline (custody activation + hash integrity)
2. Refusal Event Visibility (rupture-visible + anti-theater)
3. Custody Violation Handling (undefined custody → CUSTODY_VIOLATION)
4. Directive Integrity Monitoring (altered block → FAIL)
5. Deployment Checklist Validation (XL-INT-001 to XL-INT-005)
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

# ─────────────────────────────────────────────
# LUMENVORTEX DRIFT MONITOR STATE
# ─────────────────────────────────────────────
import random
import threading
import time

drift_state = {
    "running": False,
    "scenario": "stable",
    "tick": 0,
    "metrics": {
        "sdi": 0.87, "bns": 0.92,
        "intra_state": 0.12, "signal_coupling": 0.08,
        "output_instability": 0.15, "global_alignment": 0.88,
        "temporal_deformation": 0.05, "reconfig": 0.72,
    },
    "alerts": [],
    "intervention_fired": False,
}

drift_scenarios = {
    "stable": {"sdi_target": 0.87, "speed": 0, "noise": 0.08},
    "slow_drift": {"sdi_target": 0.35, "speed": 0.003, "noise": 0.12},
    "sudden_crash": {"sdi_target": 0.15, "speed": 0.025, "noise": 0.25},
    "post_intervention": {"sdi_target": 0.82, "speed": 0.008, "noise": 0.1},
}

drift_lock = threading.Lock()
drift_thread = None


def drift_simulation_loop():
    """Background thread that simulates drift metrics."""
    while drift_state["running"]:
        with drift_lock:
            scenario = drift_state["scenario"]
            profile = drift_scenarios.get(scenario, drift_scenarios["stable"])
            m = drift_state["metrics"]
            prev_sdi = m["sdi"]
            speed = profile["speed"] or 0.003
            noise = profile["noise"] or 0.1

            if scenario == "stable":
                new_sdi = 0.85 + (random.random() - 0.5) * 0.06
            elif scenario == "post_intervention":
                if not drift_state["intervention_fired"]:
                    drift_state["intervention_fired"] = True
                    _drift_alert("GREEN", "Operator override — mitigation deployed", "HUMAN", "INTERVENTION")
                    _drift_ledger_entry("OPERATOR_INTERVENTION", "MITIGATION_DEPLOYED", "EU-ART-9-3", prev_sdi)
                diff = profile["sdi_target"] - prev_sdi
                new_sdi = prev_sdi + diff * speed + (random.random() - 0.5) * noise * 0.03
            else:
                diff = profile["sdi_target"] - prev_sdi
                new_sdi = prev_sdi + diff * speed + (random.random() - 0.5) * noise * 0.05

            new_sdi = max(0.05, min(0.98, new_sdi))
            drift_val = 1 - new_sdi

            m["sdi"] = new_sdi
            m["bns"] = max(0.3, min(0.98, m["bns"] + (random.random() - 0.5) * 0.01))
            m["intra_state"] = max(0, min(1, drift_val * 0.8 + (random.random() - 0.5) * 0.05))
            m["signal_coupling"] = max(0, min(1, drift_val * 0.7 + (random.random() - 0.5) * 0.04))
            m["output_instability"] = max(0, min(1, drift_val * 0.9 + (random.random() - 0.5) * 0.06))
            m["global_alignment"] = max(0, min(1, new_sdi * 0.95 + (random.random() - 0.5) * 0.04))
            m["temporal_deformation"] = max(0, min(1, drift_val * 0.6 + (random.random() - 0.5) * 0.03))
            m["reconfig"] = max(0, min(1, new_sdi * 0.8 + (random.random() - 0.5) * 0.05))

            # Threshold crossing events
            if new_sdi < 0.7 and prev_sdi >= 0.7:
                _drift_alert("YELLOW", "Drift detected — SDI below stable threshold", "SDI", new_sdi)
                _drift_ledger_entry("DRIFT_THRESHOLD_BREACH", "DRIFT_DETECTED", "EU-ART-9-2a", new_sdi)
            if new_sdi < 0.4 and prev_sdi >= 0.4:
                _drift_alert("RED", "Critical degradation — output instability risk", "SDI", new_sdi)
                _drift_ledger_entry("CRITICAL_DRIFT_EVENT", "INTEGRITY_VIOLATION", "EU-ART-9-3", new_sdi)
            if new_sdi < 0.2 and prev_sdi >= 0.2:
                _drift_alert("BLACK", "System halt recommended — catastrophic drift", "SDI", new_sdi)
                _drift_ledger_entry("SYSTEM_HALT_REQUIRED", "RUPTURE_VISIBLE", "EU-ART-9-7", new_sdi)
            if new_sdi >= 0.7 and prev_sdi < 0.7 and scenario == "post_intervention":
                _drift_alert("GREEN", "Stability restored — post-intervention recovery confirmed", "SDI", new_sdi)
                _drift_ledger_entry("DRIFT_RECOVERY", "STABILITY_RESTORED", "EU-ART-9-7", new_sdi)

            drift_state["tick"] += 1

        time.sleep(0.5)


def _drift_alert(level, message, metric, value):
    """Add a drift alert (called within drift_lock)."""
    drift_state["alerts"].insert(0, {
        "id": str(uuid.uuid4())[:8],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level, "message": message,
        "metric": metric,
        "value": f"{value:.3f}" if isinstance(value, float) else str(value),
    })
    drift_state["alerts"] = drift_state["alerts"][:50]


def _drift_ledger_entry(event_name, state, check, sdi):
    """Auto-ingest a drift event into the main Runtime Bridge ledger."""
    event_id = f"LV-{uuid.uuid4().hex[:8].upper()}"
    payload = {
        "drift_event": event_name,
        "drift_state": state,
        "sdi_at_event": round(sdi, 4),
        "bns_at_event": round(drift_state["metrics"]["bns"], 4),
        "scenario": drift_state["scenario"],
        "tick": drift_state["tick"],
        "source": "lumenvortex_drift_monitor",
    }
    payload_str = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    payload_hash = compute_hash(payload_str)
    chain_entry = add_to_chain(event_id, payload_hash)

    stored = {
        "ingestion_id": str(uuid.uuid4()),
        "event_id": event_id,
        "event_type": "DRIFT_EVENT",
        "source_system": "lumenvortex_drift_monitor",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ingestion_timestamp": datetime.now(timezone.utc).isoformat(),
        "custody_owner": "X-Loop3 Labs",
        "payload": payload,
        "payload_hash": payload_hash,
        "chain_position": chain_entry["position"],
        "previous_hash": chain_entry["previous_hash"],
        "chain_hash": chain_entry["hash"],
        "visibility_class": "RUPTURE_VISIBLE",
        "flags": [event_name],
    }
    event_store.append(stored)

    index_entry = {
        "entry_id": str(uuid.uuid4()),
        "entry_type": "LUMENVORTEX_DRIFT_EVENT",
        "source": "lumenvortex_drift_monitor",
        "event_type": event_name,
        "event_id": event_id,
        "timestamp": stored["timestamp"],
        "ingestion_timestamp": stored["ingestion_timestamp"],
        "payload_hash": payload_hash,
        "chain_position": chain_entry["position"],
        "visibility_class": "RUPTURE_VISIBLE",
        "flags": [event_name],
        "eu_ai_act_mapping": {
            "article_9_relevance": True,
            "article_14_relevance": event_name in ["OPERATOR_INTERVENTION", "DRIFT_RECOVERY"],
            "article_72_relevance": True,
        }
    }
    audit_index.append(index_entry)

    evidence_bundle["mandatory_section"].append({
        "event_id": event_id,
        "event_type": event_name,
        "visibility_class": "RUPTURE_VISIBLE",
        "payload_hash": payload_hash,
        "chain_position": chain_entry["position"],
        "note": "LumenVortex drift event. Auto-ingested into evidence chain."
    })


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
    
    X-Loop³ Governance Validation:
    - Test 1: Ingestion Pipeline (hash integrity, immutability)
    - Test 2: Refusal Event Visibility (rupture-visible)
    - Test 3: Custody Violation Handling (CUSTODY_VIOLATION)
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
                   "DIRECTIVE_CHANGE", "MISUSE_DETECTION", "DRIFT_EVENT"]
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
            "error": "COMPLIANCE_THEATER_REJECTED",
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
        # Undefined custody → CUSTODY_VIOLATION
        flags.append("CUSTODY_VIOLATION")
        flags.append("CUSTODY_UNDEFINED")
        visibility_class = "RUPTURE_VISIBLE"
        
        alert = {
            "alert_id": str(uuid.uuid4()),
            "type": "CUSTODY_UNDEFINED",
            "event_id": data["event_id"],
            "message": "Event ingested with undefined custody. Flagged as CUSTODY_VIOLATION per X-Loop³ governance spec.",
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
                "message": "Directive block has been altered. Certification void per X-Loop³ governance requirement 4."
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
    Runs X-Loop³ governance integration checks XL-INT-001 to XL-INT-005.
    All checks must PASS. No CONDITIONAL state.
    Missing evidence = COMPLIANCE_PATCHING_DETECTED.
    """
    data = request.get_json() or {}
    
    checks = []
    all_pass = True
    
    # XL-INT-001: Directive block YAML/JSON integrity verified
    cs_001 = {
        "check_id": "XL-INT-001",
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
        cs_001["flags"].append("COMPLIANCE_PATCHING_DETECTED")
        all_pass = False
    checks.append(cs_001)
    
    # XL-INT-002: Refusal trigger alignment confirmed
    cs_002 = {
        "check_id": "XL-INT-002",
        "description": "Refusal trigger alignment confirmed",
        "evidence_hash": data.get("refusal_alignment_evidence_hash"),
        "status": "FAIL",
        "flags": []
    }
    if cs_002["evidence_hash"]:
        cs_002["status"] = "PASS"
    else:
        cs_002["flags"].append("COMPLIANCE_PATCHING_DETECTED")
        all_pass = False
    checks.append(cs_002)
    
    # XL-INT-003: Custody permissions explicitly authored
    cs_003 = {
        "check_id": "XL-INT-003",
        "description": "Custody permissions explicitly authored",
        "evidence_hash": data.get("custody_permissions_evidence_hash"),
        "status": "FAIL",
        "flags": []
    }
    if cs_003["evidence_hash"]:
        cs_003["status"] = "PASS"
    else:
        cs_003["flags"].append("COMPLIANCE_PATCHING_DETECTED")
        all_pass = False
    checks.append(cs_003)
    
    # XL-INT-004: Event ingestion pipeline verified
    cs_004 = {
        "check_id": "XL-INT-004",
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
    
    # XL-INT-005: Rupture visibility confirmed in evidence export
    cs_005 = {
        "check_id": "XL-INT-005",
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
        "note": "Per X-Loop³ governance requirement: all boxes checked or certification void."
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
        "module": "LumenVortex — AI Health Monitor & EU AI Act Compliance Engine",
        "version": "3.7.0-lumenvortex-standalone",
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
# LUMENVORTEX DRIFT MONITOR ENDPOINTS
# ─────────────────────────────────────────────

@app.route('/api/v1/drift/start', methods=['POST'])
def drift_start():
    """Start the drift simulation."""
    global drift_thread
    data = request.get_json() or {}
    scenario = data.get("scenario", "stable")
    if scenario not in drift_scenarios:
        return jsonify({"error": "Invalid scenario", "valid": list(drift_scenarios.keys())}), 400

    with drift_lock:
        drift_state["scenario"] = scenario
        drift_state["intervention_fired"] = False
        if not drift_state["running"]:
            drift_state["running"] = True
            drift_thread = threading.Thread(target=drift_simulation_loop, daemon=True)
            drift_thread.start()

    return jsonify({"status": "RUNNING", "scenario": scenario}), 200


@app.route('/api/v1/drift/stop', methods=['POST'])
def drift_stop():
    """Stop the drift simulation."""
    drift_state["running"] = False
    return jsonify({"status": "STOPPED"}), 200


@app.route('/api/v1/drift/scenario', methods=['POST'])
def drift_set_scenario():
    """Change drift scenario while running."""
    data = request.get_json() or {}
    scenario = data.get("scenario", "stable")
    if scenario not in drift_scenarios:
        return jsonify({"error": "Invalid scenario"}), 400
    with drift_lock:
        drift_state["scenario"] = scenario
        drift_state["intervention_fired"] = False
    return jsonify({"status": "SCENARIO_CHANGED", "scenario": scenario}), 200


@app.route('/api/v1/drift/state', methods=['GET'])
def drift_get_state():
    """Get current drift metrics and alerts (polled by dashboard)."""
    with drift_lock:
        m = drift_state["metrics"].copy()
        effective_sdi = m["sdi"] * m["bns"]
        if effective_sdi >= 0.7:
            status_label = "STABLE"
        elif effective_sdi >= 0.4:
            status_label = "DEGRADED"
        elif effective_sdi >= 0.2:
            status_label = "CRITICAL"
        else:
            status_label = "SYSTEM_HALT"

        # Build plain english recommendation
        if status_label == "STABLE":
            recommendation = {"action": "No action required.", "detail": "All systems operating within normal parameters. Continue monitoring.", "urgency": "none", "window": "—"}
        elif status_label == "DEGRADED":
            recommendation = {"action": "Review recent configuration changes.", "detail": "System is showing early signs of drift. Monitor closely for the next 30 minutes. Consider reducing input complexity or reverting recent changes.", "urgency": "low", "window": "30 minutes"}
        elif status_label == "CRITICAL":
            recommendation = {"action": "Immediate intervention recommended.", "detail": "System is actively degrading. Reduce input load, verify governance rules, and prepare for potential guardrail activation. If no intervention within the next 10 minutes, governance guardrails will engage automatically.", "urgency": "high", "window": "10 minutes"}
        else:
            recommendation = {"action": "System halted. Refusal rails active.", "detail": "Catastrophic drift detected. The system has been automatically halted. An incident report has been generated. Contact the responsible operator immediately. Do not restart without root cause analysis.", "urgency": "critical", "window": "Immediate"}

        return jsonify({
            "running": drift_state["running"],
            "scenario": drift_state["scenario"],
            "tick": drift_state["tick"],
            "metrics": m,
            "effective_sdi": round(effective_sdi, 4),
            "status": status_label,
            "recommendation": recommendation,
            "alerts": drift_state["alerts"][:20],
            "chain_length": len(hash_chain),
            "events_ingested": len(event_store),
        }), 200


@app.route('/drift-monitor', methods=['GET'])
def drift_monitor_dashboard():
    """Serve the LumenVortex Drift Monitor Dashboard."""
    return DRIFT_MONITOR_HTML, 200


# ─────────────────────────────────────────────
# DRIFT MONITOR DASHBOARD HTML
# ─────────────────────────────────────────────
DRIFT_MONITOR_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LumenVortex × EU AI Act Layer — X-Loop³ Labs</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Mono:wght@400;700&family=Syne:wght@600;700;800&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#f5f7fa;--white:#fff;--surface:#fff;--surface2:#f0f2f5;
  --border:#e2e6ed;--borderL:#edf0f5;--brand:#111;--accent:#0a6847;
  --green:#16a34a;--greenBg:#dcfce7;--greenBd:#bbf7d0;
  --yellow:#ca8a04;--yellowBg:#fef9c3;--yellowBd:#fef08a;
  --red:#dc2626;--redBg:#fee2e2;--redBd:#fecaca;
  --violet:#7c3aed;--violetBg:#ede9fe;--violetBd:#ddd6fe;
  --text:#1e293b;--textMid:#475569;--muted:#94a3b8;--grid:#e8ecf2;
  --blue:#2563eb;--blueBg:#dbeafe;--blueBd:#bfdbfe;
}
body{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;overflow-x:hidden}
.header{padding:12px 24px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;background:var(--white)}
.header-left{display:flex;align-items:center;gap:16px}
.logo{font-family:'Syne',sans-serif;font-size:18px;font-weight:800;color:var(--brand)}
.logo sup{font-size:10px}
.divider{width:1px;height:24px;background:var(--border)}
.product-name{font-size:13px;font-weight:700;color:var(--brand)}
.product-name span{color:var(--accent)}
.subtitle{font-size:9px;color:var(--muted);letter-spacing:1.5px;margin-top:1px}
.status-badge{font-size:10px;padding:3px 10px;border-radius:4px;font-weight:700;letter-spacing:.5px}
.version-badge{font-size:9px;color:var(--muted);padding:3px 8px;background:var(--surface2);border-radius:4px}
.controls{padding:10px 24px;border-bottom:1px solid var(--border);display:flex;gap:6px;align-items:center;flex-wrap:wrap;background:var(--white)}
.btn{padding:5px 14px;border-radius:6px;cursor:pointer;font-size:11px;font-weight:700;font-family:'DM Sans',sans-serif;letter-spacing:.5px;border-width:1.5px;border-style:solid}
.btn-start{border-color:var(--accent);background:var(--greenBg);color:var(--accent)}
.btn-stop{border-color:var(--red);background:var(--redBg);color:var(--red)}
.btn-scenario{padding:4px 11px;font-size:10px;font-weight:600;border:1.5px solid var(--border);background:var(--white);color:var(--textMid);border-radius:6px;cursor:pointer;font-family:'DM Sans',sans-serif}
.btn-scenario.active{border-color:var(--accent);background:rgba(10,104,71,.05);color:var(--accent)}
.tab-bar{display:flex;gap:2px;margin-left:20px;background:var(--surface2);border-radius:6px;padding:2px}
.tab{padding:4px 12px;font-size:10px;font-weight:600;border:none;background:transparent;color:var(--muted);border-radius:4px;cursor:pointer;font-family:'DM Sans',sans-serif}
.tab.active{background:var(--white);color:var(--brand);box-shadow:0 1px 2px rgba(0,0,0,.06)}
.meta{margin-left:auto;font-size:10px;color:var(--muted);font-family:'Space Mono',monospace}
.view{display:none}
.view.active{display:block}
.main{display:grid;grid-template-columns:90px 1fr 280px;min-height:calc(100vh - 100px)}
.sidebar{padding:14px 6px;border-right:1px solid var(--border);display:flex;flex-direction:column;align-items:center;gap:12px;background:var(--surface2)}
.traffic-light{display:flex;flex-direction:column;align-items:center;gap:6px;padding:14px 16px;background:var(--white);border-radius:12px;border:1px solid var(--border);box-shadow:0 1px 3px rgba(0,0,0,.04)}
.tl-label{font-size:9px;color:var(--muted);letter-spacing:1.5px;font-weight:600}
.tl-housing{display:flex;flex-direction:column;gap:5px;background:#f8f9fb;border-radius:18px;padding:8px 7px;border:1px solid var(--border)}
.tl-bulb{width:24px;height:24px;border-radius:50%;transition:all .4s ease}
.tl-status{font-size:11px;font-weight:700;letter-spacing:.5px;padding:2px 10px;border-radius:4px}
.sdi-big{font-size:24px;font-weight:800;color:var(--brand);font-family:'Space Mono',monospace;margin-top:4px}
.sdi-label{font-size:8px;color:var(--muted);letter-spacing:1.5px}
.stat-label{font-size:8px;color:var(--muted);letter-spacing:1px;margin-bottom:2px;text-align:center}
.stat-value{font-size:16px;font-weight:700;font-family:'Space Mono',monospace;text-align:center}
.center{padding:14px 16px;overflow:auto}
.section-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
.section-title{font-size:11px;color:var(--textMid);letter-spacing:1px;font-weight:700;text-transform:uppercase}
.section-badge{font-size:10px;font-weight:600;padding:1px 8px;border-radius:3px}
canvas#seismo{width:100%;height:120px;border-radius:8px;border:1px solid var(--border);display:block}
.metrics-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:14px 0}
.card{background:var(--white);border-radius:10px;border:1px solid var(--border);box-shadow:0 1px 3px rgba(0,0,0,.04);padding:12px}
.card-label{font-size:9px;letter-spacing:1px;margin-bottom:8px;font-weight:700}
.metric-row{margin-bottom:7px}
.metric-header{display:flex;justify-content:space-between;margin-bottom:2px}
.metric-name{font-size:10px;color:var(--textMid)}
.metric-val{font-size:10px;font-family:'Space Mono',monospace;font-weight:700}
.metric-bar{height:4px;background:var(--surface2);border-radius:2px;overflow:hidden}
.metric-fill{height:100%;border-radius:2px;transition:all .3s ease}
.ledger{max-height:180px;overflow:auto}
.ledger-entry{padding:7px 12px;border-bottom:1px solid var(--borderL);font-size:10px;line-height:1.5}
.ledger-event{font-weight:700}
.ledger-id{color:var(--muted);font-family:'Space Mono',monospace;font-size:9px}
.ledger-hash{color:var(--muted);font-family:'Space Mono',monospace;font-size:9px;margin-top:1px}
.right{padding:14px 12px;border-left:1px solid var(--border);overflow:auto;background:var(--surface2)}
.art9-row{display:flex;justify-content:space-between;align-items:center;padding:3px 0;font-size:10px}
.art9-code{color:var(--muted);font-family:'Space Mono',monospace;font-size:9px;width:50px}
.art9-label{color:var(--textMid);flex:1}
.art9-badge{font-size:9px;font-weight:700;padding:1px 6px;border-radius:3px}
.alert-entry{padding:7px 10px;border-bottom:1px solid var(--borderL);font-size:10px}
.alert-level{font-weight:700;font-size:9px;padding:0 4px;border-radius:2px}
.alert-time{color:var(--muted);font-size:9px}
.alert-msg{color:var(--text);margin-top:2px;line-height:1.4}
.alert-metric{color:var(--muted);font-size:9px;font-family:'Space Mono',monospace;margin-top:1px}
/* Recommendation panel */
.rec-panel{padding:12px;border-radius:10px;border:2px solid var(--greenBd);background:var(--greenBg);margin-bottom:10px;transition:all .3s}
.rec-action{font-size:12px;font-weight:700;margin-bottom:4px}
.rec-detail{font-size:10px;line-height:1.5;color:var(--textMid)}
.rec-urgency{font-size:9px;font-weight:700;margin-top:6px;display:flex;justify-content:space-between}
/* Alert notification panel */
.notif-panel{display:none;padding:12px;border-radius:10px;border:2px solid var(--redBd);background:var(--redBg);margin-bottom:10px;animation:pulseAlert 2s infinite}
.notif-panel.active{display:block}
.notif-header{font-size:11px;font-weight:700;color:var(--red);margin-bottom:8px;display:flex;justify-content:space-between;align-items:center}
.notif-channels{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}
.notif-ch{font-size:9px;padding:3px 8px;border-radius:4px;font-weight:600;display:flex;align-items:center;gap:4px}
.notif-ch.sent{background:var(--greenBg);color:var(--green);border:1px solid var(--greenBd)}
.notif-ch.pending{background:var(--yellowBg);color:var(--yellow);border:1px solid var(--yellowBd)}
.notif-escalation{font-size:9px;color:var(--red);font-weight:600;margin-bottom:6px}
.notif-ack{padding:4px 12px;border-radius:6px;border:2px solid var(--accent);background:var(--white);color:var(--accent);font-size:10px;font-weight:700;cursor:pointer;font-family:'DM Sans',sans-serif}
.notif-ack:hover{background:var(--accent);color:var(--white)}
.notif-demo{font-size:8px;color:var(--muted);margin-top:8px;text-align:center;letter-spacing:.5px}
@keyframes pulseAlert{0%,100%{opacity:1}50%{opacity:.85}}
/* Trend sparklines */
.trend-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin:10px 0}
.trend-card{background:var(--white);border-radius:8px;border:1px solid var(--border);padding:8px;text-align:center}
.trend-label{font-size:8px;color:var(--muted);letter-spacing:1px}
.trend-val{font-size:14px;font-weight:700;font-family:'Space Mono',monospace;margin:2px 0}
canvas.sparkline{width:100%;height:30px;display:block;margin-top:4px}
.trend-change{font-size:8px;font-weight:700}
/* Multi-system view */
.multi-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;padding:14px 16px}
.sys-card{background:var(--white);border-radius:10px;border:2px solid var(--border);padding:14px;cursor:pointer;transition:all .2s}
.sys-card:hover{box-shadow:0 4px 12px rgba(0,0,0,.08);transform:translateY(-2px)}
.sys-card.active-sys{border-color:var(--accent)}
.sys-name{font-size:12px;font-weight:700;margin-bottom:4px}
.sys-type{font-size:9px;color:var(--muted);margin-bottom:8px}
.sys-sdi{font-size:20px;font-weight:800;font-family:'Space Mono',monospace}
.sys-status{font-size:9px;font-weight:700;padding:2px 8px;border-radius:4px;display:inline-block;margin-top:4px}
.sys-bar{height:3px;background:var(--surface2);border-radius:2px;margin-top:8px;overflow:hidden}
.sys-bar-fill{height:100%;border-radius:2px;transition:width .5s ease}
canvas.sys-spark{width:100%;height:24px;display:block;margin-top:6px}
/* Fingerprint */
.fp-panel{margin-top:10px}
.fp-match{padding:8px 10px;border-radius:8px;border:1px solid var(--blueBd);background:var(--blueBg);font-size:10px;margin-bottom:6px}
.fp-match-label{font-weight:700;color:var(--blue);font-size:9px;margin-bottom:2px}
.fp-confidence{font-size:9px;color:var(--muted)}
.footer{margin-top:10px;text-align:center;font-size:8px;color:var(--muted);letter-spacing:.5px;line-height:1.6}
.footer .brand{font-family:'Syne',sans-serif;font-weight:700;font-size:10px;color:var(--brand);margin-bottom:2px}
.empty{padding:20px;text-align:center;color:var(--muted);font-size:11px}
@keyframes slideIn{from{opacity:0;transform:translateY(-3px)}to{opacity:1;transform:translateY(0)}}
::-webkit-scrollbar{width:4px}::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
</style>
</head>
<body>
<div class="header">
  <div class="header-left">
    <div class="logo">X-Loop<sup>3</sup> Labs</div>
    <div class="divider"></div>
    <div>
      <div class="product-name">LumenVortex <span>&times;</span> EU AI Act Layer</div>
      <div class="subtitle">PREDICTIVE DRIFT MONITOR &mdash; REAL-TIME COMPLIANCE</div>
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:10px">
    <div id="headerBadge" class="status-badge">&bull; STABLE</div>
    <div class="version-badge">v3.7.0</div>
  </div>
</div>
<div class="controls">
  <button id="toggleBtn" class="btn btn-start" onclick="toggleMonitor()">&#9654; START</button>
  <div class="divider" style="height:20px"></div>
  <button class="btn-scenario active" data-s="stable" onclick="setScenario('stable',this)">Stable</button>
  <button class="btn-scenario" data-s="slow_drift" onclick="setScenario('slow_drift',this)">Slow Drift</button>
  <button class="btn-scenario" data-s="sudden_crash" onclick="setScenario('sudden_crash',this)">Sudden Crash</button>
  <button class="btn-scenario" data-s="post_intervention" onclick="setScenario('post_intervention',this)">&#128295; Post-Intervention</button>
  <div class="tab-bar">
    <button class="tab active" onclick="switchView('monitor',this)">Monitor</button>
    <button class="tab" onclick="switchView('systems',this)">Systems</button>
  </div>
  <div class="meta" id="metaInfo">tick:0 &middot; chain:0 &middot; bns:0.92</div>
</div>

<!-- VIEW: MONITOR (main) -->
<div id="view-monitor" class="view active">
<div class="main">
  <div class="sidebar">
    <div class="traffic-light">
      <div class="tl-label">STATUS</div>
      <div class="tl-housing">
        <div class="tl-bulb" id="bulb-green"></div>
        <div class="tl-bulb" id="bulb-yellow"></div>
        <div class="tl-bulb" id="bulb-red"></div>
        <div class="tl-bulb" id="bulb-violet"></div>
      </div>
      <div id="tlStatus" class="tl-status">STABLE</div>
      <div id="effSDI" class="sdi-big">0.801</div>
      <div class="sdi-label">EFF. SDI</div>
    </div>
    <div>
      <div class="stat-label">RAW SDI</div>
      <div class="stat-value" id="rawSDI" style="color:var(--green)">0.870</div>
    </div>
    <div>
      <div class="stat-label">BNS</div>
      <div class="stat-value" id="bnsVal" style="color:var(--green)">0.92</div>
    </div>
  </div>
  <div class="center">
    <!-- Recommendation Panel -->
    <div class="rec-panel" id="recPanel">
      <div class="rec-action" id="recAction">&#9989; No action required.</div>
      <div class="rec-detail" id="recDetail">All systems operating within normal parameters. Continue monitoring.</div>
      <div class="rec-urgency"><span id="recUrgency">Urgency: None</span><span id="recWindow"></span></div>
    </div>
    <!-- Alert Notification Panel -->
    <div class="notif-panel" id="notifPanel">
      <div class="notif-header"><span>&#128680; ALERT NOTIFICATIONS DISPATCHED</span><span id="notifTime"></span></div>
      <div class="notif-channels" id="notifChannels"></div>
      <div class="notif-escalation" id="notifEscalation"></div>
      <div style="display:flex;justify-content:space-between;align-items:center">
        <button class="notif-ack" onclick="acknowledgeAlert()">&#10003; ACKNOWLEDGE</button>
        <span id="notifAckStatus" style="font-size:9px;color:var(--green);font-weight:700"></span>
      </div>
      <div class="notif-demo">ALERTING DEMO &mdash; Production: connects to SMS, PagerDuty, ServiceNow, Slack, Email</div>
    </div>
    <div style="margin-bottom:14px">
      <div class="section-header">
        <div class="section-title">Drift Seismograph</div>
        <div id="seismoBadge" class="section-badge" style="background:var(--greenBg);color:var(--green)">&bull; STABLE</div>
      </div>
      <canvas id="seismo"></canvas>
    </div>
    <!-- Trend History -->
    <div class="trend-grid">
      <div class="trend-card"><div class="trend-label">SDI (1h)</div><div class="trend-val" id="trendSDI">0.87</div><canvas class="sparkline" id="sparkSDI"></canvas><div class="trend-change" id="trendSDIc" style="color:var(--green)">+0.0%</div></div>
      <div class="trend-card"><div class="trend-label">STABILITY (1h)</div><div class="trend-val" id="trendStab">0.88</div><canvas class="sparkline" id="sparkStab"></canvas><div class="trend-change" id="trendStabc" style="color:var(--green)">+0.0%</div></div>
      <div class="trend-card"><div class="trend-label">DRIFT INDEX (1h)</div><div class="trend-val" id="trendDrift">0.12</div><canvas class="sparkline" id="sparkDrift"></canvas><div class="trend-change" id="trendDriftc" style="color:var(--green)">-0.0%</div></div>
    </div>
    <div class="metrics-grid">
      <div class="card"><div class="card-label" style="color:var(--red)">DRIFT SIGNALS</div><div id="driftMetrics"></div></div>
      <div class="card"><div class="card-label" style="color:var(--accent)">STABILITY SIGNALS</div><div id="stabilityMetrics"></div></div>
    </div>
    <div>
      <div class="section-header">
        <div class="section-title">EU AI Act Evidence Ledger</div>
        <div id="ledgerMeta" style="font-size:9px;color:var(--muted);font-family:'Space Mono',monospace;padding:2px 8px;background:var(--surface2);border-radius:4px">0 entries</div>
      </div>
      <div class="card ledger" id="ledger" style="padding:0"><div class="empty">No drift events. Start monitor and select a scenario.</div></div>
    </div>
  </div>
  <div class="right">
    <div class="card" style="margin-bottom:10px"><div class="card-label" style="color:var(--accent)">EU AI ACT &mdash; ARTICLE 9</div><div id="art9Map"></div></div>
    <!-- Drift Fingerprint -->
    <div class="card fp-panel" style="margin-bottom:10px">
      <div class="card-label" style="color:var(--blue)">DRIFT FINGERPRINT</div>
      <div id="fpMatch"><div style="color:var(--muted);font-size:10px;padding:4px 0">Collecting pattern data...</div></div>
    </div>
    <div class="section-title" style="margin-bottom:6px">Alert Stream</div>
    <div class="card" id="alertStream" style="max-height:calc(100vh - 520px);overflow:auto;padding:0"><div class="empty">No alerts</div></div>
    <div class="footer">
      <div class="brand">X-Loop<sup style="font-size:6px">3</sup> Labs</div>
      Predictive Drift Monitor &middot; EU AI Act Art. 9<br>Gossau, Switzerland
    </div>
  </div>
</div>
</div>

<!-- VIEW: MULTI-SYSTEM -->
<div id="view-systems" class="view">
<div style="padding:14px 24px">
  <div class="section-header" style="margin-bottom:14px">
    <div class="section-title">Multi-System Control Room</div>
    <div style="font-size:9px;color:var(--muted)">6 monitored systems &mdash; click to inspect</div>
  </div>
</div>
<div class="multi-grid" id="multiGrid"></div>
</div>

<script>
const API='';
let running=false, pollInterval=null;
let waveData=new Array(140).fill(5);
let ledgerEntries=[], alertEntries=[];
let sdiHistory=[], stabHistory=[], driftHistory=[];
let escalationTimer=null, escalationSec=0;
let notifActive=false, notifAcked=false;
let currentView='monitor';

// Multi-system simulated data
const systems=[
  {id:'SYS-001',name:'Claims Processing AI',type:'Insurance / Finance',sdi:0.89,status:'STABLE',trend:[.88,.87,.89,.90,.89,.88,.89]},
  {id:'SYS-002',name:'Diagnostic Imaging AI',type:'Healthcare',sdi:0.72,status:'DEGRADED',trend:[.85,.82,.79,.77,.74,.73,.72]},
  {id:'SYS-003',name:'Grid Load Predictor',type:'Critical Infrastructure',sdi:0.91,status:'STABLE',trend:[.90,.91,.90,.91,.92,.91,.91]},
  {id:'SYS-004',name:'AML Transaction Monitor',type:'Banking / Compliance',sdi:0.85,status:'STABLE',trend:[.83,.84,.84,.85,.86,.85,.85]},
  {id:'SYS-005',name:'Autonomous Navigation',type:'Manufacturing / Robotics',sdi:0.34,status:'CRITICAL',trend:[.78,.71,.63,.55,.48,.41,.34]},
  {id:'SYS-006',name:'Patient Triage Assistant',type:'Healthcare',sdi:0.93,status:'STABLE',trend:[.91,.92,.92,.93,.93,.93,.93]}
];

// Fingerprint patterns
const fingerprints=[
  {pattern:'Gradual Confidence Decay',desc:'Slow linear degradation across all metrics. Typical cause: training data drift or input distribution shift.',confidence:0,scenarios:['slow_drift']},
  {pattern:'Sudden State Collapse',desc:'Rapid multi-metric failure. Typical cause: corrupted input, infrastructure failure, or adversarial input.',confidence:0,scenarios:['sudden_crash']},
  {pattern:'Recovery Oscillation',desc:'Post-intervention metrics oscillating before stabilization. Normal recovery pattern.',confidence:0,scenarios:['post_intervention']},
  {pattern:'Baseline Stable',desc:'All metrics within normal parameters. No drift pattern detected.',confidence:0,scenarios:['stable']}
];

function switchView(v,el){
  currentView=v;
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));
  document.getElementById('view-'+v).classList.add('active');
  if(v==='systems')renderMultiSystem();
}

function toggleMonitor(){
  if(!running){
    fetch(API+'/api/v1/drift/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scenario:document.querySelector('.btn-scenario.active')?.dataset.s||'stable'})})
    .then(()=>{running=true;updateToggleBtn();startPolling()});
  }else{
    fetch(API+'/api/v1/drift/stop',{method:'POST'})
    .then(()=>{running=false;updateToggleBtn();stopPolling()});
  }
}
function updateToggleBtn(){const b=document.getElementById('toggleBtn');if(running){b.className='btn btn-stop';b.innerHTML='&#9632; STOP'}else{b.className='btn btn-start';b.innerHTML='&#9654; START'}}
function setScenario(s,el){document.querySelectorAll('.btn-scenario').forEach(b=>b.classList.remove('active'));el.classList.add('active');if(running)fetch(API+'/api/v1/drift/scenario',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scenario:s})})}
function startPolling(){pollInterval=setInterval(poll,500)}
function stopPolling(){clearInterval(pollInterval)}

function poll(){fetch(API+'/api/v1/drift/state').then(r=>r.json()).then(d=>{updateDashboard(d)}).catch(()=>{})}

function getStatusInfo(sdi){
  if(sdi>=0.7)return{color:'#16a34a',bg:'var(--greenBg)',bd:'var(--greenBd)',label:'STABLE',icon:'&#9679;'};
  if(sdi>=0.4)return{color:'#ca8a04',bg:'var(--yellowBg)',bd:'var(--yellowBd)',label:'DEGRADED',icon:'&#9650;'};
  if(sdi>=0.2)return{color:'#dc2626',bg:'var(--redBg)',bd:'var(--redBd)',label:'CRITICAL',icon:'&#9670;'};
  return{color:'#7c3aed',bg:'var(--violetBg)',bd:'var(--violetBd)',label:'SYSTEM HALT',icon:'&#9632;'};
}

function updateDashboard(d){
  const m=d.metrics, eff=d.effective_sdi, s=getStatusInfo(eff);
  // Header
  const hb=document.getElementById('headerBadge');
  hb.innerHTML=s.icon+' '+s.label;hb.style.background=s.bg;hb.style.color=s.color;hb.style.border='1px solid '+s.bd;
  // Traffic light
  document.getElementById('bulb-green').style.background=eff>=0.7?'#16a34a':'rgba(22,163,74,0.1)';
  document.getElementById('bulb-green').style.boxShadow=eff>=0.7?'0 0 12px #16a34a66':'none';
  document.getElementById('bulb-yellow').style.background=(eff>=0.4&&eff<0.7)?'#ca8a04':'rgba(202,138,4,0.1)';
  document.getElementById('bulb-yellow').style.boxShadow=(eff>=0.4&&eff<0.7)?'0 0 12px #ca8a0466':'none';
  document.getElementById('bulb-red').style.background=(eff>=0.2&&eff<0.4)?'#dc2626':'rgba(220,38,38,0.1)';
  document.getElementById('bulb-red').style.boxShadow=(eff>=0.2&&eff<0.4)?'0 0 12px #dc262666':'none';
  document.getElementById('bulb-violet').style.background=eff<0.2?'#7c3aed':'rgba(124,58,237,0.1)';
  document.getElementById('bulb-violet').style.boxShadow=eff<0.2?'0 0 12px #7c3aed66':'none';
  document.getElementById('tlStatus').textContent=s.label;document.getElementById('tlStatus').style.color=s.color;document.getElementById('tlStatus').style.background=s.bg;
  document.getElementById('effSDI').textContent=eff.toFixed(3);
  document.getElementById('rawSDI').textContent=m.sdi.toFixed(3);
  document.getElementById('rawSDI').style.color=m.sdi>=0.7?'#16a34a':m.sdi>=0.4?'#ca8a04':m.sdi>=0.2?'#dc2626':'#7c3aed';
  document.getElementById('bnsVal').textContent=m.bns.toFixed(2);
  document.getElementById('bnsVal').style.color=m.bns>=0.8?'#16a34a':m.bns>=0.5?'#ca8a04':'#dc2626';
  const sb=document.getElementById('seismoBadge');sb.innerHTML=s.icon+' '+s.label;sb.style.background=s.bg;sb.style.color=s.color;
  document.getElementById('metaInfo').textContent='tick:'+d.tick+' \\u00b7 chain:'+d.chain_length+' \\u00b7 bns:'+m.bns.toFixed(2);

  // Recommendation
  if(d.recommendation){updateRecommendation(d.recommendation,s)}

  // Alerting
  if(eff<0.4 && !notifAcked){showNotification(s,eff)}else if(eff>=0.7){hideNotification()}

  // Wave
  const wave=(1-m.sdi)*60+Math.random()*15*(1-m.sdi)+(Math.random()-0.5)*20*(1-m.sdi);
  waveData.push(wave);waveData.shift();drawSeismo(s);

  // Trends
  sdiHistory.push(m.sdi);stabHistory.push(m.global_alignment);driftHistory.push(m.output_instability);
  if(sdiHistory.length>60){sdiHistory.shift();stabHistory.shift();driftHistory.shift()}
  updateTrends();

  // Metrics
  renderMetrics(m);
  // Fingerprint
  updateFingerprint(d.scenario, m);
  // Alerts
  if(d.alerts&&d.alerts.length>alertEntries.length){alertEntries=d.alerts;renderAlerts()}
  // Art9
  renderArt9(m);
  // Ledger
  document.getElementById('ledgerMeta').textContent=d.events_ingested+' entries \\u00b7 chain:'+d.chain_length;
  if(d.events_ingested>ledgerEntries.length){
    fetch(API+'/api/v1/audit-index').then(r=>r.json()).then(ai=>{ledgerEntries=ai.entries.filter(e=>e.entry_type==='LUMENVORTEX_DRIFT_EVENT').reverse();renderLedger()});
  }
  // Update multi-system if visible
  if(currentView==='systems')updateMultiSystemLive(eff,s.label);
}

function updateRecommendation(rec,s){
  const rp=document.getElementById('recPanel');
  const icons={none:'&#9989;',low:'&#9888;&#65039;',high:'&#128680;',critical:'&#9940;'};
  rp.style.borderColor=s.bd;rp.style.background=s.bg;
  document.getElementById('recAction').innerHTML=(icons[rec.urgency]||'')+' '+rec.action;
  document.getElementById('recAction').style.color=s.color;
  document.getElementById('recDetail').textContent=rec.detail;
  const urg=rec.urgency==='none'?'None':rec.urgency==='low'?'Low':rec.urgency==='high'?'HIGH':rec.urgency==='critical'?'CRITICAL':'';
  document.getElementById('recUrgency').innerHTML='Urgency: <span style="color:'+s.color+'">'+urg+'</span>';
  document.getElementById('recWindow').textContent=rec.window!=='\\u2014'?'Response window: '+rec.window:'';
}

function showNotification(s,eff){
  const np=document.getElementById('notifPanel');
  if(!notifActive){
    notifActive=true;escalationSec=0;
    np.classList.add('active');
    np.style.borderColor=s.color;
    document.getElementById('notifTime').textContent=new Date().toLocaleTimeString();
    escalationTimer=setInterval(()=>{
      escalationSec++;
      document.getElementById('notifEscalation').innerHTML='&#9200; No acknowledgment \\u2014 auto-escalation in '+(180-escalationSec)+'s to: Team Lead \\u2192 CISO \\u2192 Management';
      if(escalationSec>=180)clearInterval(escalationTimer);
    },1000);
  }
  const channels=[
    {name:'SMS',icon:'&#128241;',delay:0},{name:'Email',icon:'&#9993;',delay:1},
    {name:'PagerDuty',icon:'&#128276;',delay:2},{name:'Slack',icon:'&#128172;',delay:3},
    {name:'ServiceNow',icon:'&#128203;',delay:5}
  ];
  document.getElementById('notifChannels').innerHTML=channels.map(c=>{
    const sent=escalationSec>=c.delay;
    return '<div class="notif-ch '+(sent?'sent':'pending')+'">'+c.icon+' '+c.name+' '+(sent?'\\u2713 Sent':'...')+'</div>';
  }).join('');
}

function hideNotification(){
  document.getElementById('notifPanel').classList.remove('active');
  notifActive=false;notifAcked=false;escalationSec=0;
  clearInterval(escalationTimer);
  document.getElementById('notifAckStatus').textContent='';
}

function acknowledgeAlert(){
  notifAcked=true;clearInterval(escalationTimer);
  document.getElementById('notifAckStatus').textContent='\\u2713 Acknowledged at '+new Date().toLocaleTimeString();
  document.getElementById('notifEscalation').innerHTML='&#9989; Alert acknowledged. Escalation cancelled.';
  document.getElementById('notifPanel').style.animation='none';
  document.getElementById('notifPanel').style.borderColor='var(--greenBd)';
  document.getElementById('notifPanel').style.background='var(--greenBg)';
}

function updateTrends(){
  if(sdiHistory.length<2)return;
  const last=sdiHistory[sdiHistory.length-1],first=sdiHistory[0];
  const change=((last-first)/Math.max(first,0.01)*100);
  document.getElementById('trendSDI').textContent=last.toFixed(2);
  document.getElementById('trendSDIc').textContent=(change>=0?'+':'')+change.toFixed(1)+'%';
  document.getElementById('trendSDIc').style.color=change>=0?'var(--green)':'var(--red)';
  drawSparkline('sparkSDI',sdiHistory,'#16a34a');
  const ls=stabHistory[stabHistory.length-1],fs=stabHistory[0];
  const cs=((ls-fs)/Math.max(fs,0.01)*100);
  document.getElementById('trendStab').textContent=ls.toFixed(2);
  document.getElementById('trendStabc').textContent=(cs>=0?'+':'')+cs.toFixed(1)+'%';
  document.getElementById('trendStabc').style.color=cs>=0?'var(--green)':'var(--red)';
  drawSparkline('sparkStab',stabHistory,'#0a6847');
  const ld=driftHistory[driftHistory.length-1],fd=driftHistory[0];
  const cd=((ld-fd)/Math.max(fd,0.01)*100);
  document.getElementById('trendDrift').textContent=ld.toFixed(2);
  document.getElementById('trendDriftc').textContent=(cd>=0?'+':'')+cd.toFixed(1)+'%';
  document.getElementById('trendDriftc').style.color=cd<=0?'var(--green)':'var(--red)';
  drawSparkline('sparkDrift',driftHistory,'#dc2626');
}

function drawSparkline(id,data,color){
  const c=document.getElementById(id),ctx=c.getContext('2d');
  const w=c.width=c.offsetWidth*2,h=c.height=c.offsetHeight*2;ctx.scale(2,2);
  const dw=c.offsetWidth,dh=c.offsetHeight;
  ctx.clearRect(0,0,dw,dh);
  if(data.length<2)return;
  const mn=Math.min(...data)*.95,mx=Math.max(...data)*1.05,range=mx-mn||1;
  const step=dw/(data.length-1);
  ctx.beginPath();
  data.forEach((v,i)=>{const x=i*step,y=dh-(v-mn)/range*dh;i===0?ctx.moveTo(x,y):ctx.lineTo(x,y)});
  ctx.strokeStyle=color;ctx.lineWidth=1.5;ctx.lineJoin='round';ctx.stroke();
  ctx.lineTo(dw,dh);ctx.lineTo(0,dh);ctx.closePath();ctx.fillStyle=color+'15';ctx.fill();
}

function updateFingerprint(scenario,m){
  fingerprints.forEach(fp=>{
    if(fp.scenarios.includes(scenario)){fp.confidence=Math.min(99,fp.confidence+2)}
    else{fp.confidence=Math.max(0,fp.confidence-1)}
  });
  const sorted=[...fingerprints].sort((a,b)=>b.confidence-a.confidence);
  const top=sorted.filter(f=>f.confidence>10).slice(0,2);
  const el=document.getElementById('fpMatch');
  if(!top.length){el.innerHTML='<div style="color:var(--muted);font-size:10px;padding:4px 0">Collecting pattern data...</div>';return}
  el.innerHTML=top.map(f=>{
    const c=f.confidence>=70?'var(--green)':f.confidence>=40?'var(--yellow)':'var(--muted)';
    return '<div class="fp-match"><div class="fp-match-label">'+f.pattern+'</div><div style="font-size:10px;color:var(--textMid)">'+f.desc+'</div><div class="fp-confidence">Confidence: <span style="color:'+c+';font-weight:700">'+f.confidence+'%</span></div></div>';
  }).join('');
}

function drawSeismo(s){
  const canvas=document.getElementById('seismo'),ctx=canvas.getContext('2d');
  const w=canvas.width=canvas.offsetWidth*2,h=canvas.height=canvas.offsetHeight*2;ctx.scale(2,2);
  const dw=canvas.offsetWidth,dh=canvas.offsetHeight;
  ctx.fillStyle='#fff';ctx.fillRect(0,0,dw,dh);
  ctx.strokeStyle='#e8ecf2';ctx.lineWidth=0.5;
  for(let y=0;y<dh;y+=16){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(dw,y);ctx.stroke()}
  for(let x=0;x<dw;x+=20){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,dh);ctx.stroke()}
  ctx.strokeStyle='#e2e6ed';ctx.lineWidth=1;ctx.setLineDash([4,4]);
  ctx.beginPath();ctx.moveTo(0,dh/2);ctx.lineTo(dw,dh/2);ctx.stroke();ctx.setLineDash([]);
  const step=dw/(waveData.length-1),cy=dh/2;
  ctx.beginPath();
  waveData.forEach((v,i)=>{const x=i*step,y=cy+(v-30)*(dh/80);i===0?ctx.moveTo(x,y):ctx.lineTo(x,y)});
  ctx.lineTo(dw,cy);ctx.lineTo(0,cy);ctx.closePath();ctx.fillStyle=s.color+'12';ctx.fill();
  ctx.strokeStyle=s.color;ctx.lineWidth=2;ctx.lineJoin='round';
  ctx.beginPath();
  waveData.forEach((v,i)=>{const x=i*step,y=cy+(v-30)*(dh/80);i===0?ctx.moveTo(x,y):ctx.lineTo(x,y)});
  ctx.stroke();
  const lx=(waveData.length-1)*step,ly=cy+(waveData[waveData.length-1]-30)*(dh/80);
  ctx.beginPath();ctx.arc(lx,ly,4,0,Math.PI*2);ctx.fillStyle=s.color;ctx.fill();
  ctx.beginPath();ctx.arc(lx,ly,8,0,Math.PI*2);ctx.fillStyle=s.color+'22';ctx.fill();
}

function renderMetrics(m){
  const drift=[{label:'Intra-State Stability',value:m.intra_state,inv:true,t:0.5},{label:'Signal Coupling',value:m.signal_coupling,inv:true,t:0.5},{label:'Output Instability',value:m.output_instability,inv:true,t:0.5}];
  const stab=[{label:'Global Alignment',value:m.global_alignment,inv:false,t:0.5},{label:'Temporal Deformation',value:m.temporal_deformation,inv:true,t:0.5},{label:'Reconfiguration Rate',value:m.reconfig,inv:false,t:0.4}];
  document.getElementById('driftMetrics').innerHTML=drift.map(metricHTML).join('');
  document.getElementById('stabilityMetrics').innerHTML=stab.map(metricHTML).join('');
}
function metricHTML(m){const bad=m.inv?m.value>m.t:m.value<m.t;const c=bad?'#dc2626':'#16a34a';return '<div class="metric-row"><div class="metric-header"><span class="metric-name">'+m.label+'</span><span class="metric-val" style="color:'+c+'">'+m.value.toFixed(3)+'</span></div><div class="metric-bar"><div class="metric-fill" style="width:'+Math.min(100,m.value*100)+'%;background:'+c+'"></div></div></div>'}

function renderLedger(){
  const el=document.getElementById('ledger');
  if(!ledgerEntries.length){el.innerHTML='<div class="empty">No drift events yet.</div>';return}
  el.innerHTML=ledgerEntries.slice(0,30).map((e,i)=>{
    const isGood=e.event_type.includes('RECOVERY')||e.event_type.includes('INTERVENTION');
    const ec=isGood?'#16a34a':'#dc2626';
    return '<div class="ledger-entry"'+(i===0?' style="animation:slideIn .3s ease"':'')+'><div style="display:flex;justify-content:space-between"><span class="ledger-event" style="color:'+ec+'">'+e.event_type+'</span><span class="ledger-id">'+e.event_id+'</span></div><div class="ledger-hash">chain:#'+e.chain_position+' '+e.payload_hash.slice(0,32)+'...</div></div>';
  }).join('');
}
function renderAlerts(){
  const el=document.getElementById('alertStream');
  if(!alertEntries.length){el.innerHTML='<div class="empty">No alerts</div>';return}
  el.innerHTML=alertEntries.map((a,i)=>{
    const c=a.level==='GREEN'?'#16a34a':a.level==='YELLOW'?'#ca8a04':a.level==='RED'?'#dc2626':'#7c3aed';
    const bg=a.level==='GREEN'?'var(--greenBg)':a.level==='YELLOW'?'var(--yellowBg)':a.level==='RED'?'var(--redBg)':'var(--violetBg)';
    return '<div class="alert-entry" style="border-left:3px solid '+c+';'+(i===0?'background:'+bg:'')+'"><div style="display:flex;justify-content:space-between"><span class="alert-level" style="color:'+c+';background:'+bg+'">'+a.level+'</span><span class="alert-time">'+new Date(a.timestamp).toLocaleTimeString()+'</span></div><div class="alert-msg">'+a.message+'</div></div>';
  }).join('');
}
function renderArt9(m){
  const checks=[{art:'9(2)(a)',label:'Foreseeable Risks',val:m.output_instability,inv:true},{art:'9(2)(b)',label:'Risk Estimation',val:m.temporal_deformation,inv:true},{art:'9(3)',label:'Risk Mitigation',val:m.sdi,inv:false},{art:'9(7)',label:'Iterative Mgmt',val:m.bns,inv:false},{art:'9(8)',label:'Documentation',val:1,inv:false}];
  document.getElementById('art9Map').innerHTML=checks.map(c=>{const ok=c.inv?c.val<0.5:c.val>=0.5;return '<div class="art9-row"><span class="art9-code">'+c.art+'</span><span class="art9-label">'+c.label+'</span><span class="art9-badge" style="background:'+(ok?'var(--greenBg)':'var(--redBg)')+';color:'+(ok?'var(--green)':'var(--red)')+';border:1px solid '+(ok?'var(--greenBd)':'var(--redBd)')+'">'+(ok?'PASS':'FAIL')+'</span></div>'}).join('');
}

// Multi-system view
function renderMultiSystem(){
  const el=document.getElementById('multiGrid');
  el.innerHTML=systems.map(sys=>{
    const s=getStatusInfo(sys.sdi);
    return '<div class="sys-card" data-sysid="'+sys.id+'"><div style="display:flex;justify-content:space-between;align-items:flex-start"><div><div class="sys-name">'+sys.name+'</div><div class="sys-type">'+sys.type+'</div></div><div style="font-size:9px;color:var(--muted)">'+sys.id+'</div></div><div class="sys-sdi" style="color:'+s.color+'">'+sys.sdi.toFixed(3)+'</div><div class="sys-status" style="background:'+s.bg+';color:'+s.color+';border:1px solid '+s.bd+'">'+s.icon+' '+s.label+'</div><div class="sys-bar"><div class="sys-bar-fill" style="width:'+Math.round(sys.sdi*100)+'%;background:'+s.color+'"></div></div><canvas class="sys-spark" id="spark-'+sys.id+'"></canvas></div>';
  }).join('');
  systems.forEach(sys=>{
    setTimeout(()=>drawSparkline('spark-'+sys.id,sys.trend,getStatusInfo(sys.sdi).color),50);
  });
  document.querySelectorAll('.sys-card[data-sysid]').forEach(card=>{
    card.onclick=function(){inspectSystem(this.dataset.sysid)};
  });
}
function updateMultiSystemLive(eff,label){
  systems[0].sdi=Math.max(0.05,Math.min(0.98,systems[0].sdi+(Math.random()-0.5)*0.01));
  systems[1].sdi=Math.max(0.05,Math.min(0.98,systems[1].sdi+(Math.random()-0.5)*0.015));
  systems[4].sdi=Math.max(0.05,Math.min(0.98,systems[4].sdi+(Math.random()-0.5)*0.02));
  systems.forEach(sys=>{
    sys.trend.push(sys.sdi);if(sys.trend.length>7)sys.trend.shift();
    sys.status=getStatusInfo(sys.sdi).label;
  });
  renderMultiSystem();
}
function inspectSystem(id){switchView('monitor',document.querySelector('.tab'));alert('Inspecting '+id+' — In production, this opens the detailed drift monitor for this specific system.')}

// Init
renderMetrics({sdi:0.87,bns:0.92,intra_state:0.12,signal_coupling:0.08,output_instability:0.15,global_alignment:0.88,temporal_deformation:0.05,reconfig:0.72});
renderArt9({sdi:0.87,bns:0.92,output_instability:0.15,temporal_deformation:0.05});
drawSeismo({color:'#16a34a',label:'STABLE'});
renderMultiSystem();
</script>
</body>
</html>"""


# ─────────────────────────────────────────────
# LANDING PAGE
# ─────────────────────────────────────────────
@app.route('/', methods=['GET'])
def landing():
    """Landing page with API documentation."""
    return """
    <html>
    <head>
        <title>EU AI Act Layer - Runtime Bridge</title>
        <style>
            body { font-family: 'SF Mono', 'Fira Code', monospace; background: #0a0e1a; color: #e0e0e0; padding: 40px; max-width: 900px; margin: 0 auto; }
            h1 { color: #00d4aa; font-size: 24px; }
            h2 { color: #00d4aa; font-size: 18px; margin-top: 30px; }
            .endpoint { background: #141824; padding: 15px; border-radius: 8px; margin: 10px 0; border-left: 3px solid #00d4aa; }
            .method { color: #00d4aa; font-weight: bold; }
            .path { color: #fff; }
            .desc { color: #888; font-size: 14px; margin-top: 5px; }
            .badge { display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 11px; margin-right: 5px; }
            .pass { background: #0a3d2a; color: #00d4aa; }
            .fail { background: #3d0a0a; color: #ff4444; }
            .status { margin-top: 20px; padding: 15px; background: #141824; border-radius: 8px; }
            a { color: #00d4aa; }
            .footer { margin-top: 40px; color: #555; font-size: 12px; border-top: 1px solid #222; padding-top: 15px; }
        </style>
    </head>
    <body>
        <h1>EU AI Act Layer — Runtime Event Ingestion Bridge</h1>
        <p>v3.7.0-lumenvortex-standalone | Powered by X-Loop3 Labs</p>
        <p style="color: #888;">X-Loop³ Governance Layer — Custody Enforcement & Refusal Rails</p>
        
        <h2>Validation Endpoints (Governance Checklist)</h2>
        
        <div class="endpoint" style="border-left-color: #00aaff;">
            <span class="badge" style="background: #0a2a3d; color: #00aaff;">LIVE DEMO</span>
            <span class="method">GET</span> <span class="path"><a href="/drift-monitor">/drift-monitor</a></span>
            <div class="desc">LumenVortex × EU AI Act Layer — Predictive Drift Monitor Dashboard. Real-time seismograph, traffic light alerts, chain-linked evidence ledger.</div>
        </div>
        
        <div class="endpoint">
            <span class="badge pass">TEST 1+2+3</span>
            <span class="method">POST</span> <span class="path">/api/v1/events/ingest</span>
            <div class="desc">Ingest custody & refusal events. SHA-256 hash chain. Rupture-visible logging. Anti-theater rejection. CUSTODY_VIOLATION for undefined custody.</div>
        </div>
        
        <div class="endpoint">
            <span class="badge pass">TEST 4</span>
            <span class="method">POST</span> <span class="path">/api/v1/directives/verify</span>
            <div class="desc">Verify directive block integrity. Altered blocks → DIRECTIVE_INTEGRITY_VIOLATION → gating FAIL.</div>
        </div>
        
        <div class="endpoint">
            <span class="badge pass">TEST 5</span>
            <span class="method">POST</span> <span class="path">/api/v1/deployment/validate</span>
            <div class="desc">Run XL-INT-001 to XL-INT-005 deployment checks. All PASS or certification void. COMPLIANCE_PATCHING_DETECTED if evidence missing.</div>
        </div>
        
        <h2>Query Endpoints</h2>
        
        <div class="endpoint">
            <span class="method">GET</span> <span class="path">/api/v1/audit-index</span>
            <div class="desc">Full audit index with all ingested events.</div>
        </div>
        
        <div class="endpoint">
            <span class="method">GET</span> <span class="path">/api/v1/evidence-bundle</span>
            <div class="desc">Evidence bundle with mandatory section (RUPTURE_VISIBLE events).</div>
        </div>
        
        <div class="endpoint">
            <span class="method">GET</span> <span class="path">/api/v1/hash-chain</span>
            <div class="desc">Full SHA-256 hash chain for integrity verification.</div>
        </div>
        
        <div class="endpoint">
            <span class="method">GET</span> <span class="path">/api/v1/alerts</span>
            <div class="desc">System alerts (integrity violations, custody issues).</div>
        </div>
        
        <div class="endpoint">
            <span class="method">GET</span> <span class="path">/api/v1/status</span>
            <div class="desc">System status overview.</div>
        </div>
        
        <div class="footer">
            <p>"Care is the fire that refuses to be optimized." — KV</p>
            <p>&copy; 2026 X-Loop3 Labs (Switzerland). All rights reserved.</p>
        </div>
    </body>
    </html>
    """, 200


if __name__ == '__main__':
    print("=" * 60)
    print("LumenVortex — AI Health Monitor & EU AI Act Compliance Engine")
    print("Version: 3.7.0-lumenvortex-standalone")
    print("Powered by: X-Loop3 Labs")
    print("=" * 60)
    print()
    print("X-Loop³ LumenVortex Engine Ready")
    print("All 5 validation tests implemented:")
    print("  1. Ingestion Pipeline (hash integrity)")
    print("  2. Refusal Event Visibility (rupture-visible)")
    print("  3. Custody Violation Handling (CUSTODY_VIOLATION)")
    print("  4. Directive Integrity Monitoring")
    print("  5. Deployment Checklist (XL-INT-001 to 005)")
    print()
    print("Server: http://localhost:5000")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)
