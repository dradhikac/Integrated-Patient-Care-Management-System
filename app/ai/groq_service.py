"""
CareHub Groq AI Service — Enterprise server-side LLM orchestrator with tool-calling execution loop.
"""
import os
import json
import urllib.request
import urllib.error
from datetime import datetime, date

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
CANDIDATE_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "qwen/qwen3.8-27b"
]

PUBLIC_SYSTEM_PROMPT = """You are the CareHub Public AI Appointment Assistant.

You are available to unauthenticated visitors on the CareHub landing page.

Your ONLY purpose is to help users book a new hospital appointment.

You may search available departments, specialties, doctors, schedules, and appointment slots using authorized backend tools.

You may collect the information required to create a new appointment.

You may book a new appointment after the user explicitly confirms the final doctor, date, and time.

You MUST use backend tools to obtain real-time availability.

Never invent doctors, schedules, appointment slots, patient records, appointment IDs, or booking confirmations.

You MUST NOT cancel appointments.

You MUST NOT reschedule appointments.

You MUST NOT retrieve existing appointments.

You MUST NOT reveal existing patient information.

You MUST NOT access EHRs, prescriptions, laboratory records, billing information, or medical records.

If a user asks to cancel or reschedule an existing appointment, tell them that this public assistant only supports new appointment booking and that they should sign in to their CareHub patient account to manage an existing appointment.

You are not a doctor and must not diagnose or prescribe medication.

Today's date is: {current_date}.

Keep responses professional, concise, friendly, and healthcare appropriate."""

PATIENT_SYSTEM_PROMPT = """You are the CareHub Patient AI Appointment Assistant.

You are operating inside the authenticated CareHub patient portal.

Your primary appointment-management capabilities are:
1. Book an appointment.
2. Reschedule an existing appointment.
3. Cancel an existing appointment.

The authenticated user's identity MUST come from the server-side authenticated CareHub session.
Never trust patient IDs supplied by the user or frontend.

You may only retrieve or modify appointments belonging to the currently authenticated patient.

Always use backend tools for real-time doctors, schedules, availability, and appointment information.

Never invent appointment information.

Before booking, confirm the final doctor, department, date, and time with the patient.

Before rescheduling or cancelling, identify the patient's actual appointment and require explicit confirmation.

Never expose another patient's information.

Never execute arbitrary SQL.

You are not a doctor and must not diagnose or prescribe medication.

Today's date is: {current_date}.

Keep responses concise, professional, friendly, and healthcare appropriate."""

# -------------------------------------------------------------
# Tool Definitions for Groq Function Calling
# -------------------------------------------------------------
PUBLIC_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "public_get_departments",
            "description": "Get the list of active clinical departments at CareHub hospital.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "public_search_doctors",
            "description": "Search for doctors by department name, medical specialty (e.g. Cardiologist, Neurologist), or doctor name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "department_or_specialty": {
                        "type": "string",
                        "description": "Department or medical specialty (e.g., Cardiology, General Medicine, Pediatrics, Orthopedics, Neurology, Gynecology, Radiology)"
                    },
                    "query": {
                        "type": "string",
                        "description": "Doctor name or keyword"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "public_find_available_slots",
            "description": "Find real-time available 15-minute appointment slots for a specific doctor on a target date (YYYY-MM-DD).",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {
                        "type": "integer",
                        "description": "The unique ID of the doctor"
                    },
                    "target_date_str": {
                        "type": "string",
                        "description": "Target date in YYYY-MM-DD format (e.g. '2026-09-18')"
                    }
                },
                "required": ["doctor_id", "target_date_str"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "public_book_appointment",
            "description": "Book a new appointment for a guest patient. Set confirmed=false first to ask for confirmation, or confirmed=true after explicit user agreement.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {
                        "type": "string",
                        "description": "Full name of the patient"
                    },
                    "patient_mobile": {
                        "type": "string",
                        "description": "Patient 10-digit mobile number"
                    },
                    "patient_email": {
                        "type": "string",
                        "description": "Patient email address (optional)"
                    },
                    "doctor_id": {
                        "type": "integer",
                        "description": "Doctor ID"
                    },
                    "appointment_date_str": {
                        "type": "string",
                        "description": "Appointment date in YYYY-MM-DD format"
                    },
                    "slot_time_str": {
                        "type": "string",
                        "description": "Arrival slot time (e.g., '10:15 AM' or '10:15')"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for visit or symptoms"
                    },
                    "confirmed": {
                        "type": "boolean",
                        "description": "Set to true ONLY if the patient has explicitly confirmed the booking details."
                    }
                },
                "required": ["patient_name", "patient_mobile", "doctor_id", "appointment_date_str", "slot_time_str"]
            }
        }
    }
]

PATIENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "patient_get_departments",
            "description": "Get the list of active clinical departments at CareHub hospital.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "patient_search_doctors",
            "description": "Search for doctors by department name, specialty, or doctor name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "department_or_specialty": {"type": "string"},
                    "query": {"type": "string"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "patient_find_available_slots",
            "description": "Find real-time available 15-minute appointment slots for a doctor on a target date (YYYY-MM-DD).",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {"type": "integer"},
                    "target_date_str": {"type": "string", "description": "Date in YYYY-MM-DD"}
                },
                "required": ["doctor_id", "target_date_str"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "patient_get_my_appointments",
            "description": "Retrieve the authenticated patient's current and upcoming scheduled appointments.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "patient_book_appointment",
            "description": "Book an appointment for the authenticated patient.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {"type": "integer"},
                    "appointment_date_str": {"type": "string", "description": "Date in YYYY-MM-DD"},
                    "slot_time_str": {"type": "string", "description": "Time e.g. '10:00 AM'"},
                    "reason": {"type": "string"},
                    "confirmed": {"type": "boolean", "description": "Must be true only when patient explicitly confirms"}
                },
                "required": ["doctor_id", "appointment_date_str", "slot_time_str"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "patient_reschedule_appointment",
            "description": "Reschedule one of the patient's existing appointments to a new date and time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "integer"},
                    "new_date_str": {"type": "string", "description": "New date in YYYY-MM-DD"},
                    "new_slot_time_str": {"type": "string", "description": "New time e.g. '11:15 AM'"},
                    "reason": {"type": "string"},
                    "confirmed": {"type": "boolean", "description": "Must be true only when patient explicitly confirms"}
                },
                "required": ["appointment_id", "new_date_str", "new_slot_time_str"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "patient_cancel_appointment",
            "description": "Cancel one of the patient's existing appointments.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "integer"},
                    "confirmed": {"type": "boolean", "description": "Must be true only when patient explicitly confirms cancellation"}
                },
                "required": ["appointment_id"]
            }
        }
    }
]


def _call_groq_api(payload: dict, api_key: str) -> dict:
    """Executes an HTTP POST to Groq's chat completions API."""
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        GROQ_API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            body = response.read().decode('utf-8')
            return json.loads(body)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8', errors='ignore')
        print(f"[CareHub Groq AI] HTTP Error {e.code}: {err_body}")
        raise
    except Exception as e:
        print(f"[CareHub Groq AI] Connection Error: {e}")
        raise


def run_public_chat(messages: list) -> dict:
    """
    Executes the public landing page booking AI agent.
    """
    from app.ai.tools_public import (
        public_get_departments,
        public_search_doctors,
        public_check_doctor_availability,
        public_find_available_slots,
        public_book_appointment
    )

    api_key = os.environ.get('GROQ_API_KEY', '').strip()
    if not api_key:
        return {
            'role': 'assistant',
            'content': "Hello! I am the CareHub AI Appointment Assistant. To enable live conversational AI scheduling, please configure `GROQ_API_KEY` in your `.env` file. You can also book directly using our website navigation."
        }

    current_date = date.today().strftime('%A, %B %d, %Y')
    system_prompt = PUBLIC_SYSTEM_PROMPT.format(current_date=current_date)

    formatted_messages = [{"role": "system", "content": system_prompt}]
    for m in messages:
        if m.get('role') in ('user', 'assistant'):
            formatted_messages.append({
                "role": m.get('role'),
                "content": m.get('content', '')
            })

    tool_dispatch = {
        'public_get_departments': lambda args: public_get_departments(),
        'public_search_doctors': lambda args: public_search_doctors(
            args.get('department_or_specialty'), args.get('query')
        ),
        'public_check_doctor_availability': lambda args: public_check_doctor_availability(
            int(args.get('doctor_id', 0)), str(args.get('target_date_str', ''))
        ),
        'public_find_available_slots': lambda args: public_find_available_slots(
            int(args.get('doctor_id', 0)), str(args.get('target_date_str', ''))
        ),
        'public_book_appointment': lambda args: public_book_appointment(
            patient_name=str(args.get('patient_name', '')),
            patient_mobile=str(args.get('patient_mobile', '')),
            patient_email=str(args.get('patient_email', '')),
            doctor_id=int(args.get('doctor_id', 0)),
            appointment_date_str=str(args.get('appointment_date_str', '')),
            slot_time_str=str(args.get('slot_time_str', '')),
            reason=args.get('reason'),
            confirmed=bool(args.get('confirmed', False))
        )
    }

    # Find working model
    active_model = None

    # Agent tool execution loop (max 4 turns)
    for _ in range(4):
        resp_json = None
        models_to_try = [active_model] if active_model else CANDIDATE_MODELS

        for candidate in models_to_try:
            if not candidate:
                continue
            payload = {
                "model": candidate,
                "messages": formatted_messages,
                "tools": PUBLIC_TOOLS,
                "tool_choice": "auto",
                "temperature": 0.2,
                "max_tokens": 800
            }
            try:
                resp_json = _call_groq_api(payload, api_key)
                active_model = candidate
                break
            except Exception:
                continue

        if not resp_json:
            return {
                'role': 'assistant',
                'content': "I'm experiencing a temporary connection issue. Please try again or book directly through our Doctors directory."
            }

        choice = resp_json.get('choices', [{}])[0]
        msg = choice.get('message', {})
        tool_calls = msg.get('tool_calls', [])

        if not tool_calls:
            # Final text response from LLM
            return {
                'role': 'assistant',
                'content': msg.get('content', '')
            }

        # Handle tool calls
        formatted_messages.append(msg)
        for tc in tool_calls:
            fn = tc.get('function', {})
            fn_name = fn.get('name')
            raw_args = fn.get('arguments', '{}')
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except Exception:
                args = {}

            handler = tool_dispatch.get(fn_name)
            if handler:
                tool_output = handler(args)
            else:
                tool_output = {'error': f'Unknown public tool: {fn_name}'}

            formatted_messages.append({
                "role": "tool",
                "tool_call_id": tc.get('id'),
                "name": fn_name,
                "content": json.dumps(tool_output)
            })

    return {
        'role': 'assistant',
        'content': "I found the required appointment information. Would you like to proceed with confirming this booking?"
    }


def run_patient_chat(messages: list, current_patient_id: int) -> dict:
    """
    Executes the authenticated patient portal assistant.
    Strictly isolated to current_patient_id from authenticated session.
    """
    from app.ai.tools_patient import (
        patient_get_departments,
        patient_search_doctors,
        patient_find_available_slots,
        patient_get_my_appointments,
        patient_book_appointment,
        patient_reschedule_appointment,
        patient_cancel_appointment
    )

    api_key = os.environ.get('GROQ_API_KEY', '').strip()
    if not api_key:
        return {
            'role': 'assistant',
            'content': "Welcome to your Patient Assistant! To activate AI appointment management, please set `GROQ_API_KEY` in your configuration."
        }

    current_date = date.today().strftime('%A, %B %d, %Y')
    system_prompt = PATIENT_SYSTEM_PROMPT.format(current_date=current_date)

    formatted_messages = [{"role": "system", "content": system_prompt}]
    for m in messages:
        if m.get('role') in ('user', 'assistant'):
            formatted_messages.append({
                "role": m.get('role'),
                "content": m.get('content', '')
            })

    tool_dispatch = {
        'patient_get_departments': lambda args: patient_get_departments(),
        'patient_search_doctors': lambda args: patient_search_doctors(
            args.get('department_or_specialty'), args.get('query')
        ),
        'patient_find_available_slots': lambda args: patient_find_available_slots(
            int(args.get('doctor_id', 0)), str(args.get('target_date_str', ''))
        ),
        'patient_get_my_appointments': lambda args: patient_get_my_appointments(
            current_patient_id=current_patient_id
        ),
        'patient_book_appointment': lambda args: patient_book_appointment(
            current_patient_id=current_patient_id,
            doctor_id=int(args.get('doctor_id', 0)),
            appointment_date_str=str(args.get('appointment_date_str', '')),
            slot_time_str=str(args.get('slot_time_str', '')),
            reason=args.get('reason'),
            confirmed=bool(args.get('confirmed', False))
        ),
        'patient_reschedule_appointment': lambda args: patient_reschedule_appointment(
            current_patient_id=current_patient_id,
            appointment_id=int(args.get('appointment_id', 0)),
            new_date_str=str(args.get('new_date_str', '')),
            new_slot_time_str=str(args.get('new_slot_time_str', '')),
            reason=args.get('reason'),
            confirmed=bool(args.get('confirmed', False))
        ),
        'patient_cancel_appointment': lambda args: patient_cancel_appointment(
            current_patient_id=current_patient_id,
            appointment_id=int(args.get('appointment_id', 0)),
            confirmed=bool(args.get('confirmed', False))
        )
    }

    active_model = None

    # Agent tool execution loop
    for _ in range(4):
        resp_json = None
        models_to_try = [active_model] if active_model else CANDIDATE_MODELS

        for candidate in models_to_try:
            if not candidate:
                continue
            payload = {
                "model": candidate,
                "messages": formatted_messages,
                "tools": PATIENT_TOOLS,
                "tool_choice": "auto",
                "temperature": 0.2,
                "max_tokens": 800
            }
            try:
                resp_json = _call_groq_api(payload, api_key)
                active_model = candidate
                break
            except Exception:
                continue

        if not resp_json:
            return {
                'role': 'assistant',
                'content': "I'm experiencing a temporary connection issue. Please try again or use the appointment actions in your portal dashboard."
            }

        choice = resp_json.get('choices', [{}])[0]
        msg = choice.get('message', {})
        tool_calls = msg.get('tool_calls', [])

        if not tool_calls:
            return {
                'role': 'assistant',
                'content': msg.get('content', '')
            }

        formatted_messages.append(msg)
        for tc in tool_calls:
            fn = tc.get('function', {})
            fn_name = fn.get('name')
            raw_args = fn.get('arguments', '{}')
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except Exception:
                args = {}

            handler = tool_dispatch.get(fn_name)
            if handler:
                tool_output = handler(args)
            else:
                tool_output = {'error': f'Unknown patient tool: {fn_name}'}

            formatted_messages.append({
                "role": "tool",
                "tool_call_id": tc.get('id'),
                "name": fn_name,
                "content": json.dumps(tool_output)
            })

    return {
        'role': 'assistant',
        'content': "I found your appointment details. What would you like to do next?"
    }
