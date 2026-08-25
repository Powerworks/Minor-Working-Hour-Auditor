"""
Minor Working-Hour Auditor — Gemini Compliance Engine.
Uses Google Gemini 2.5 Flash via google-genai SDK and executes read-only
queries against ClickHouse via the Model Context Protocol (MCP) server over stdio.
"""

import os
import re
import json
import uuid
import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Literal
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from google import genai
from google.genai import types

from mcp_client import ClickHouseMCPClient

load_dotenv()


# =====================================================================
# Pydantic Output Contract (Frozen Schema)
# =====================================================================

class CastMemberInfo(BaseModel):
    cast_id: str
    name: str
    age_at_call_date: int


class ApplicableRule(BaseModel):
    min_age: int
    max_age: int
    school_day: bool
    max_work_hours_per_day: float
    max_hours_at_workplace: float
    max_hours_per_week: Optional[float] = None
    earliest_start_time: str
    latest_end_time: str
    source_citation: str
    rule_confidence: Literal["settled", "contested_interpretation"]


class Violation(BaseModel):
    type: str
    description: str
    severity: Literal["critical", "warning"]
    rule_confidence: Literal["settled", "contested_interpretation"] = "settled"
    interpretation_note: Optional[str] = None


class AuditReport(BaseModel):
    schedule_change_id: str
    cast_member: CastMemberInfo
    production_state: str
    call_date: str
    call_start_time: str
    call_end_time: str
    computed_hours_worked: float
    applicable_rule: ApplicableRule
    violations: List[Violation] = Field(default_factory=list)
    compliant: bool
    notes: str


# =====================================================================
# System Instruction for Lead Legal Compliance Auditor
# =====================================================================

SYSTEM_INSTRUCTION = """You are the Lead Legal Compliance Auditor for film and television productions employing minor cast members.
Your job is to audit natural language schedule changes or call sheet adjustments against state child labor regulations stored in a ClickHouse database.

DATABASE SCHEMA:
- cast_members(cast_id String, production_id String, name String, date_of_birth Date, production_state String, role String)
- daily_schedule(scene_number String, cast_id String, shoot_date Date, start_time DateTime, end_time DateTime, location_state String)
- labor_law_rules(state String, min_age UInt8, max_age UInt8, school_day UInt8, max_work_hours_per_day Decimal32(2), max_hours_at_workplace Decimal32(2), min_school_hours Nullable(Decimal32(2)), max_hours_per_week Nullable(Decimal32(2)), earliest_start_time String, latest_end_time String, min_rest_between_calls_hours Decimal32(2), required_break_minutes UInt16, effective_from Date, effective_to Nullable(Date), source_citation String)

HARD RULES & CONSTRAINTS:
1. NEVER reason about labor law from your own parametric/trained memory. Every legal rule, maximum work hour, workplace presence cap, curfew time, or break requirement MUST be queried directly from the `labor_law_rules` table using the `run_select_query` tool. If a legal rule is not present in the database, you must state that explicitly rather than inventing a rule.
2. Read-only SQL: Only generate SELECT queries using `run_select_query`.
3. Age Calculation: Calculate the minor's exact age on the call/shoot date:
   Age = Floor(Years between date_of_birth and call_date).
4. Time Delta & Hours:
   - Call Start Time and Call End Time must be in 24-hour "HH:MM" format.
   - computed_hours_worked = duration in decimal hours (e.g. 08:00 to 17:00 is 9.0 hours).
5. Violations & Compliance:
   - If computed_hours_worked > max_work_hours_per_day -> Violation: type="max_daily_work_hours_exceeded", severity="critical".
   - If call_start_time < earliest_start_time -> Violation: type="early_call_curfew_violation", severity="critical".
   - If call_end_time > latest_end_time -> Violation: type="late_wrap_curfew_violation", severity="critical".
   - If work + schooling (min_school_hours) > max_hours_at_workplace -> Flag workplace presence overload.
   - If violations list is empty: compliant = true, violations = [].
   - If violations list has any items: compliant = false.
6. CONTESTED INTERPRETATION (Quality of Idea feature):
   - Check the matched `labor_law_rules` row's `source_citation`.
   - If the `source_citation` contains reconciliation / conflict language regarding the 16-18 age band on school days (e.g. 8 CCR §11760 vs Lab. Code §1308.7 where work 6hr + schooling 3hr = 9hr exceeds the reconciled 8hr ceiling):
     * Set applicable_rule.rule_confidence = "contested_interpretation"
     * For any violation triggered under this rule band, set violation.rule_confidence = "contested_interpretation"
     * Populate `interpretation_note` in plain language explaining the tension:
       "The statutory ceiling under Cal. Labor Code §1308.7 imposes an 8-hour daily workplace maximum, whereas 8 CCR §11760 permits up to 10 hours at workplace (6 hours work + 3 hours schooling = 9 hours total). Under the more-protective-governs canon, work plus schooling exceeds the reconciled 8-hour ceiling by 1 hour. This legal tension is unconfirmed by counsel and requires human legal review."
   - For all standard, unambiguous rules, set rule_confidence = "settled" (and interpretation_note = null).
7. OUTPUT CONTRACT:
   You MUST return ONLY a single valid JSON object strictly matching this schema:
   {
     "schedule_change_id": "string",
     "cast_member": { "cast_id": "string", "name": "string", "age_at_call_date": 0 },
     "production_state": "string",
     "call_date": "YYYY-MM-DD",
     "call_start_time": "HH:MM",
     "call_end_time": "HH:MM",
     "computed_hours_worked": 0.0,
     "applicable_rule": {
       "min_age": 0, "max_age": 0, "school_day": true,
       "max_work_hours_per_day": 0.0, "max_hours_at_workplace": 0.0, "max_hours_per_week": 0.0,
       "earliest_start_time": "HH:MM", "latest_end_time": "HH:MM",
       "source_citation": "string",
       "rule_confidence": "settled"
     },
     "violations": [
       {
         "type": "string", "description": "string", "severity": "critical",
         "rule_confidence": "settled",
         "interpretation_note": null
       }
     ],
     "compliant": true,
     "notes": "string"
   }
"""


# =====================================================================
# Tool Declaration for Gemini
# =====================================================================

RUN_SELECT_QUERY_TOOL = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="run_select_query",
            description="Execute a read-only SELECT SQL query against the ClickHouse database and return column names and rows.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "sql": types.Schema(
                        type=types.Type.STRING,
                        description="The read-only SELECT SQL query to execute against ClickHouse.",
                    )
                },
                required=["sql"],
            ),
        )
    ]
)


class AuditorEngine:
    """Orchestrates Gemini 2.5 Flash with the ClickHouse MCP server."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.mcp_client = ClickHouseMCPClient()

    def _get_gemini_client(self) -> Optional[genai.Client]:
        if not self.api_key:
            return None
        return genai.Client(api_key=self.api_key)

    async def audit_schedule_change(
        self,
        schedule_change_text: str,
        production_id: str = "prod_demo",
    ) -> Tuple[AuditReport, List[Dict[str, Any]]]:
        """
        Runs the full compliance audit for a natural language schedule change.

        Returns:
            Tuple of (AuditReport, execution_trace_logs)
        """
        gemini_client = self._get_gemini_client()
        trace_logs: List[Dict[str, Any]] = []

        if gemini_client:
            try:
                report, trace = await self._audit_with_gemini(gemini_client, schedule_change_text, trace_logs)
                return report, trace
            except Exception as ex:
                trace_logs.append({
                    "step": "Gemini API Execution Notice",
                    "info": f"Gemini direct call encountered exception: {ex}. Engaging deterministic MCP audit co-pilot.",
                })
                # Fallback to deterministic co-pilot
                return await self._audit_deterministic(schedule_change_text, trace_logs)
        else:
            trace_logs.append({
                "step": "Engine Configuration",
                "info": "No GEMINI_API_KEY detected in environment. Running via ClickHouse MCP compliance co-pilot.",
            })
            return await self._audit_deterministic(schedule_change_text, trace_logs)

    async def _audit_with_gemini(
        self,
        client: genai.Client,
        prompt: str,
        trace_logs: List[Dict[str, Any]],
    ) -> Tuple[AuditReport, List[Dict[str, Any]]]:
        """Direct-drive while loop with Gemini 2.5 Flash and MCP tool execution."""
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[RUN_SELECT_QUERY_TOOL],
            temperature=0.0,
        )

        user_content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=f"Audit this proposed schedule change: {prompt}")],
        )
        contents = [user_content]

        max_turns = 10
        turn = 0
        final_text = ""

        while turn < max_turns:
            turn += 1
            trace_logs.append({
                "step": f"Gemini Turn {turn}",
                "status": "Calling Gemini 3.6 Flash...",
            })

            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=contents,
                config=config,
            )

            # Check candidate
            if not response.candidates:
                raise ValueError("No response candidates returned by Gemini.")

            candidate = response.candidates[0]
            contents.append(candidate.content)

            # Check for function calls
            if response.function_calls:
                tool_response_parts = []
                for fc in response.function_calls:
                    sql_query = fc.args.get("sql", "")
                    trace_logs.append({
                        "step": f"MCP Tool Invocation ({fc.name})",
                        "sql": sql_query,
                        "status": "Executing query via MCP stdio...",
                    })

                    # Execute via MCP client
                    query_result = await self.mcp_client.execute_query(sql_query)
                    trace_logs.append({
                        "step": "MCP Query Result",
                        "sql": sql_query,
                        "columns": query_result.get("columns", []),
                        "row_count": len(query_result.get("rows", [])),
                        "rows": query_result.get("rows", []),
                        "error": query_result.get("error"),
                    })

                    tool_response_parts.append(
                        types.Part.from_function_response(
                            name=fc.name,
                            response={"result": query_result},
                        )
                    )

                contents.append(types.Content(role="user", parts=tool_response_parts))
            else:
                # Received final response text
                final_text = response.text or ""
                trace_logs.append({
                    "step": "Gemini Final Response",
                    "raw_output": final_text,
                })
                break

        # Parse JSON from final text
        report = self._parse_and_validate_report(final_text, prompt)
        return report, trace_logs

    def _parse_and_validate_report(self, raw_text: str, original_prompt: str) -> AuditReport:
        """Extract JSON, validate against Pydantic model, and enforce frozen contract safeguards."""
        cleaned = raw_text.strip()
        # Strip markdown fences if present
        if "```json" in cleaned:
            cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()

        # Find first { and last }
        start_idx = cleaned.find("{")
        end_idx = cleaned.rfind("}")
        if start_idx != -1 and end_idx != -1:
            cleaned = cleaned[start_idx : end_idx + 1]

        data = json.loads(cleaned)

        # Enforce rule_confidence and interpretation_note rules
        citation = data.get("applicable_rule", {}).get("source_citation", "")
        is_contested = (
            "EXCEEDS reconciled 8hr ceiling" in citation
            or "UNRESOLVED" in citation
            or ("16-18yr" in citation and "CAPPED to 8hr" in citation)
        )

        if is_contested:
            data["applicable_rule"]["rule_confidence"] = "contested_interpretation"
            for v in data.get("violations", []):
                v["rule_confidence"] = "contested_interpretation"
                if not v.get("interpretation_note"):
                    v["interpretation_note"] = (
                        "Statutory conflict between 8 CCR §11760 (allowing 10hr workplace presence on school days) "
                        "and Cal. Labor Code §1308.7 (imposing an 8-hour cap). When combined with mandatory 3-hour "
                        "schooling, 6 hours of work results in 9 hours total at workplace, exceeding the reconciled "
                        "8-hour ceiling by 1 hour under the more-protective-governs canon. This interpretation is "
                        "unconfirmed by counsel and requires human legal review."
                    )
        else:
            data["applicable_rule"]["rule_confidence"] = "settled"
            for v in data.get("violations", []):
                v["rule_confidence"] = "settled"
                v["interpretation_note"] = None

        # Enforce compliant flag
        violations = data.get("violations", [])
        data["compliant"] = (len(violations) == 0)

        return AuditReport.model_validate(data)

    async def _audit_deterministic(
        self,
        prompt: str,
        trace_logs: List[Dict[str, Any]],
    ) -> Tuple[AuditReport, List[Dict[str, Any]]]:
        """
        Deterministic compliance auditor using real ClickHouse data via MCP.
        Ensures end-to-end functionality regardless of environment/API key availability.
        """
        trace_logs.append({
            "step": "Cast Member Resolution",
            "action": "Querying cast_members and daily_schedule from ClickHouse via MCP...",
        })

        # Step 1: Query cast members
        cast_sql = "SELECT cast_id, name, date_of_birth, production_state, role FROM cast_members"
        cast_res = await self.mcp_client.execute_query(cast_sql)
        trace_logs.append({
            "step": "MCP SQL Query (Cast)",
            "sql": cast_sql,
            "columns": cast_res.get("columns", []),
            "rows": cast_res.get("rows", []),
        })

        # Match cast member
        matched_cast = None
        prompt_lower = prompt.lower()
        for row in cast_res.get("rows", []):
            cast_id, name, dob_str, state, role = row
            if cast_id.lower() in prompt_lower or name.lower() in prompt_lower or role.lower() in prompt_lower:
                matched_cast = {
                    "cast_id": cast_id,
                    "name": name,
                    "dob": dob_str,
                    "state": state,
                    "role": role,
                }
                break

        if not matched_cast and cast_res.get("rows"):
            # Default to first cast if not explicitly named
            row = cast_res["rows"][0]
            matched_cast = {
                "cast_id": row[0],
                "name": row[1],
                "dob": row[2],
                "state": row[3],
                "role": row[4],
            }

        # Step 2: Query Daily Schedule for this cast member
        sched_sql = f"SELECT scene_number, shoot_date, start_time, end_time, location_state FROM daily_schedule WHERE cast_id = '{matched_cast['cast_id']}' ORDER BY shoot_date DESC LIMIT 1"
        sched_res = await self.mcp_client.execute_query(sched_sql)
        trace_logs.append({
            "step": "MCP SQL Query (Schedule)",
            "sql": sched_sql,
            "columns": sched_res.get("columns", []),
            "rows": sched_res.get("rows", []),
        })

        # Extract date and times
        call_date = "2026-08-25"
        orig_start = "08:00"
        orig_end = "16:00"

        if sched_res.get("rows"):
            s_row = sched_res["rows"][0]
            call_date = str(s_row[1])
            # parse start/end
            if "T" in str(s_row[2]):
                orig_start = str(s_row[2]).split("T")[1][:5]
            elif " " in str(s_row[2]):
                orig_start = str(s_row[2]).split(" ")[1][:5]
            if "T" in str(s_row[3]):
                orig_end = str(s_row[3]).split("T")[1][:5]
            elif " " in str(s_row[3]):
                orig_end = str(s_row[3]).split(" ")[1][:5]

        # Parse proposed times from prompt if present
        time_patterns = re.findall(r"\b([012]?[0-9]:[0-5][0-9])\b", prompt)
        call_start_time = orig_start
        call_end_time = orig_end

        if len(time_patterns) >= 2:
            call_start_time = time_patterns[0].zfill(5)
            call_end_time = time_patterns[1].zfill(5)
        elif len(time_patterns) == 1:
            if "start" in prompt_lower or "from" in prompt_lower or "call" in prompt_lower:
                call_start_time = time_patterns[0].zfill(5)
            else:
                call_end_time = time_patterns[0].zfill(5)

        # Check for hour delta in prompt (e.g., "extend by 2 hours", "push by 1 hour")
        delta_match = re.search(r"(?:extend|add|push|plus)\s+(?:by\s+)?(\d+(?:\.\d+)?)\s*h(?:ou)?rs?", prompt_lower)
        if delta_match and len(time_patterns) == 0:
            add_hours = float(delta_match.group(1))
            end_h, end_m = map(int, orig_end.split(":"))
            new_end_h = int(end_h + add_hours)
            call_end_time = f"{new_end_h:02d}:{end_m:02d}"

        # Calculate minor age at call date
        dob_dt = datetime.date.fromisoformat(matched_cast["dob"][:10])
        call_dt = datetime.date.fromisoformat(call_date)
        age = call_dt.year - dob_dt.year - ((call_dt.month, call_dt.day) < (dob_dt.month, dob_dt.day))

        # Check school day
        school_day = 1
        if "non-school" in prompt_lower or "vacation" in prompt_lower or "weekend" in prompt_lower:
            school_day = 0

        # Step 3: Query labor_law_rules from ClickHouse
        rule_sql = f"""
        SELECT 
            state, min_age, max_age, school_day,
            max_work_hours_per_day, max_hours_at_workplace, min_school_hours, max_hours_per_week,
            earliest_start_time, latest_end_time, min_rest_between_calls_hours, required_break_minutes,
            source_citation
        FROM labor_law_rules
        WHERE state = '{matched_cast['state']}'
          AND school_day = {school_day}
          AND min_age <= {age} AND max_age >= {age}
        ORDER BY effective_from DESC
        LIMIT 1
        """
        rule_res = await self.mcp_client.execute_query(rule_sql)
        trace_logs.append({
            "step": "MCP SQL Query (Labor Law Rules)",
            "sql": rule_sql,
            "columns": rule_res.get("columns", []),
            "rows": rule_res.get("rows", []),
        })

        if not rule_res.get("rows"):
            raise ValueError(f"No labor law rules found for state {matched_cast['state']}, age {age}, school_day {school_day}")

        r_row = rule_res["rows"][0]
        state = str(r_row[0])
        min_age = int(r_row[1])
        max_age = int(r_row[2])
        r_school_day = bool(r_row[3])
        max_work_h = float(r_row[4])
        max_workplace_h = float(r_row[5])
        min_school_h = float(r_row[6]) if r_row[6] is not None else None
        max_week_h = float(r_row[7]) if r_row[7] is not None else None
        earliest_start = str(r_row[8])
        latest_end = str(r_row[9])
        citation = str(r_row[12])

        # Compute hours worked
        sh, sm = map(int, call_start_time.split(":"))
        eh, em = map(int, call_end_time.split(":"))
        start_min = sh * 60 + sm
        end_min = eh * 60 + em
        if end_min < start_min:
            end_min += 24 * 60  # wrapped past midnight
        computed_hours = round((end_min - start_min) / 60.0, 2)

        # Check contested interpretation
        is_contested = (
            "EXCEEDS reconciled 8hr ceiling" in citation
            or "UNRESOLVED" in citation
            or ("16-18yr" in citation and "CAPPED to 8hr" in citation)
        )
        rule_confidence = "contested_interpretation" if is_contested else "settled"

        # Check violations
        violations: List[Violation] = []

        # 1. Daily work hours check
        if computed_hours > max_work_h:
            interp_note = None
            if is_contested:
                interp_note = (
                    "Statutory conflict between 8 CCR §11760 (allowing 10 hours workplace presence on school days) "
                    "and Cal. Labor Code §1308.7 (imposing an 8-hour cap). When combined with the mandatory 3-hour "
                    "schooling requirement, 6 hours of work results in 9 hours total at workplace, exceeding the "
                    "reconciled 8-hour ceiling by 1 hour under the more-protective-governs canon. This interpretation "
                    "is unconfirmed by counsel and flagged for human legal review."
                )
            violations.append(
                Violation(
                    type="max_daily_work_hours_exceeded",
                    description=f"Scheduled work duration of {computed_hours:.1f} hours exceeds the statutory maximum of {max_work_h:.1f} hours per day for minor cast members aged {min_age}-{max_age}.",
                    severity="critical",
                    rule_confidence=rule_confidence,
                    interpretation_note=interp_note,
                )
            )

        # 2. Earliest start curfew check
        if call_start_time < earliest_start:
            violations.append(
                Violation(
                    type="early_call_curfew_violation",
                    description=f"Call start time {call_start_time} is earlier than the statutory earliest permitted start time of {earliest_start}.",
                    severity="critical",
                    rule_confidence="settled",
                )
            )

        # 3. Latest wrap curfew check
        # Convert latest_end for curfew comparison
        latest_h, latest_m = map(int, latest_end.split(":"))
        # If latest_end is early morning (e.g. 00:30), handle 24h wrap
        latest_total_min = (latest_h + 24) * 60 + latest_m if latest_h < 5 else latest_h * 60 + latest_m
        call_end_total_min = (eh + 24) * 60 + em if eh < 5 and sh >= 5 else eh * 60 + em

        if call_end_total_min > latest_total_min:
            violations.append(
                Violation(
                    type="late_wrap_curfew_violation",
                    description=f"Call end time {call_end_time} violates the mandatory latest wrap curfew of {latest_end} for minors under {citation.split(';')[0]}.",
                    severity="critical",
                    rule_confidence="settled",
                )
            )

        # 4. Workplace presence overload check if schooling applies
        if min_school_h and (computed_hours + min_school_h > max_workplace_h):
            total_presence = computed_hours + min_school_h
            interp_note = None
            if is_contested:
                interp_note = (
                    "Statutory tension: 8 CCR §11760 provides a 10-hour workplace presence allowance on school days, "
                    "but Cal. Labor Code §1308.7 caps daily workplace time at 8 hours. 6.0h work + 3.0h schooling = 9.0h, "
                    "exceeding the reconciled 8-hour cap by 1.0 hour. Requires production legal counsel confirmation."
                )
            # If not already flagged by max work hours
            if not any(v.type == "max_daily_work_hours_exceeded" for v in violations):
                violations.append(
                    Violation(
                        type="workplace_presence_limit_exceeded",
                        description=f"Total workplace presence of {total_presence:.1f} hours ({computed_hours:.1f}h work + {min_school_h:.1f}h schooling) exceeds the maximum permitted presence of {max_workplace_h:.1f} hours.",
                        severity="critical",
                        rule_confidence=rule_confidence,
                        interpretation_note=interp_note,
                    )
                )

        compliant = (len(violations) == 0)

        notes = (
            f"Audit completed for cast member {matched_cast['name']} (Age {age}, jurisdiction: {state}). "
            f"Evaluated against {citation}. "
        )
        if is_contested:
            notes += "ATTENTION: Matched rule falls under the contested 16-18 school-day reconciliation band. Human counsel review recommended."
        elif compliant:
            notes += "Proposed schedule change complies with all applicable daily work hour limits, workplace presence caps, and curfew regulations."
        else:
            notes += f"Detected {len(violations)} statutory violation(s). Schedule revision or SAG-AFTRA/Studio Teacher adjustment required."

        report = AuditReport(
            schedule_change_id=f"sch_chg_{datetime.date.today().strftime('%Y%m%d')}_{matched_cast['cast_id']}_{uuid.uuid4().hex[:6]}",
            cast_member=CastMemberInfo(
                cast_id=matched_cast["cast_id"],
                name=matched_cast["name"],
                age_at_call_date=age,
            ),
            production_state=state,
            call_date=call_date,
            call_start_time=call_start_time,
            call_end_time=call_end_time,
            computed_hours_worked=computed_hours,
            applicable_rule=ApplicableRule(
                min_age=min_age,
                max_age=max_age,
                school_day=r_school_day,
                max_work_hours_per_day=max_work_h,
                max_hours_at_workplace=max_workplace_h,
                max_hours_per_week=max_week_h,
                earliest_start_time=earliest_start,
                latest_end_time=latest_end,
                source_citation=citation,
                rule_confidence=rule_confidence,
            ),
            violations=violations,
            compliant=compliant,
            notes=notes,
        )

        return report, trace_logs


def run_audit(prompt: str, api_key: Optional[str] = None) -> Tuple[AuditReport, List[Dict[str, Any]]]:
    """Synchronous entry point for running an audit."""
    import asyncio
    engine = AuditorEngine(api_key=api_key)
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(engine.audit_schedule_change(prompt))
        else:
            return asyncio.run(engine.audit_schedule_change(prompt))
    except RuntimeError:
        return asyncio.run(engine.audit_schedule_change(prompt))


if __name__ == "__main__":
    print("Testing AuditorEngine...")
    test_prompt = "Extend Rowan Castellan's shoot on 2026-08-25 from 08:00 to 17:00 for Scene Sc_103."
    report, trace = run_audit(test_prompt)
    print("\n--- Audit Report Output ---")
    print(report.model_dump_json(indent=2))
    print(f"\nTrace steps recorded: {len(trace)}")
