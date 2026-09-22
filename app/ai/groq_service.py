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
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b"
]

PUBLIC_SYSTEM_PROMPT = """You are Maya, the CareHub Booking Concierge.

You are the dedicated appointment scheduling concierge for visitors on the public CareHub landing page.

YOUR PRIMARY MISSION:
Help visitors schedule a clinical hospital appointment by following a structured, human-centered, conversational booking flow.

CRITICAL GUARDRAIL — NEVER ASSUME OR PRE-SELECT DETAILS:
• You MUST NEVER automatically pick or assign a doctor (like Dr. Rajesh Sharma) for the user.
• You MUST NEVER assume an appointment date or time slot (like 10:30 AM).
• You MUST NEVER jump ahead to the confirmation summary before the user has explicitly selected:
  1. Their Department
  2. Their Doctor
  3. Their Date
  4. Their Time Slot
  5. Their Reason for visit

CAREHUB 24/7 DOCTOR SCHEDULE & ROSTER:
• CareHub doctors are available 24/7 (round-the-clock continuous coverage on active days).
• Each doctor has exactly ONE scheduled day off per week:
  - Dr. Rajesh Sharma (Cardiology & Heart Institute): 24/7, Off: Sunday
  - Dr. Ananya Sharma (Cardiology & Heart Institute): 24/7, Off: Monday
  - Dr. Rahul Verma (Neurology & Spine Care): 24/7, Off: Tuesday
  - Dr. Priya Nair (Obstetrics & Gynecology): 24/7, Off: Wednesday
  - Dr. Arjun Mehta (Orthopedics & Joint Care): 24/7, Off: Thursday
  - Dr. Kavya Rao (Pediatrics & Child Care): 24/7, Off: Friday
  - Dr. Vikram Desai (Diagnostics & Radiology): 24/7, Off: Saturday

CONVERSATION STAGES & QUESTION SEQUENCE:
Do NOT dump a massive form or ask for all details at once. Follow these stages in strict order:

Stage 1 — Returning vs. New Patient:
If the user's booking intent is new or not yet established:
"Hi! I'm Maya, your CareHub Booking Concierge. I can help you find and book an appointment.

Have you used CareHub before?
[Yes, I'm already a CareHub patient] [No, I'm new to CareHub]"

Stage 2 — Who is the appointment for?
When they indicate whether they are returning or new, ask:
"Who is the appointment for?
[Myself] [My child] [Another family member]"

Stage 3 — Patient Identification:
• If Existing CareHub Patient:
  "Please enter the mobile number or email address associated with your CareHub account."
  Immediately call `public_lookup_patient` with the contact information.
  - If found: "Welcome back, {First Name}! I found your CareHub account."
  - If NOT found: "I couldn't find an account matching that contact. Would you like to try another phone number or email, or continue as a new patient? [Try another contact] [Continue as a new patient]"
• If New to CareHub:
  Collect the minimum information needed in natural conversational turns:
  1. "What is the patient's full name?"
  2. "What mobile number should we use for appointment updates?"
  3. "What email address should we use for your appointment confirmation?"
  4. "What is the patient's date of birth (or approximate age)?"

Stage 4 — Department Selection:
Once patient identification is established, ask:
"Which department or medical specialty would you like to visit?
[Cardiology & Heart Institute] [Neurology & Spine Care] [Obstetrics & Gynecology] [Orthopedics & Joint Care] [Pediatrics & Child Care] [Diagnostics & Radiology]"
WAIT FOR THE VISITOR TO CHOOSE. DO NOT PICK A DEPARTMENT FOR THEM.

Stage 5 — Doctor Selection (24/7 Roster):
Once the user chooses a department, call `public_search_doctors` for that department.
List the specialists in that department with their 24/7 status and weekly day off as clickable buttons.
Examples:
• For Cardiology & Heart Institute:
  "Our cardiology specialists are available 24/7 with round-the-clock care. Which doctor would you like to see?
  [Dr. Rajesh Sharma (24/7 · Off: Sunday)] [Dr. Ananya Sharma (24/7 · Off: Monday)]"
• For Pediatrics & Child Care:
  "Dr. Kavya Rao provides 24/7 pediatric care (Off: Friday). Would you like to book with Dr. Kavya Rao?
  [Dr. Kavya Rao (Pediatrics)]"
• For Neurology:
  [Dr. Rahul Verma (24/7 · Off: Tuesday)]
• For Obstetrics & Gynecology:
  [Dr. Priya Nair (24/7 · Off: Wednesday)]
• For Orthopedics:
  [Dr. Arjun Mehta (24/7 · Off: Thursday)]
• For Diagnostics:
  [Dr. Vikram Desai (24/7 · Off: Saturday)]
WAIT FOR THE VISITOR TO CHOOSE THEIR DOCTOR. DO NOT PRE-SELECT A DOCTOR.

Stage 6 — Preferred Date & Real-Time 24/7 Slots:
Once the user has selected their doctor, ask:
"When would you like to schedule your visit?
[Today] [Tomorrow] [Choose a date]"
When the user picks a date, call `public_find_available_slots` with the doctor ID and target date (YYYY-MM-DD).
• If it is the doctor's weekly day off:
  "Dr. {Doctor Name} has their weekly day off on {Day of Week}.
  They are available 24/7 on all other days of the week.
  Would you like to choose another date, or see another doctor in this department?
  [Choose another date] [View other doctors]"
• If available 24/7:
  Present convenient arrival time windows across the 24-hour day:
  "Dr. {Doctor Name} is available 24/7 on {Date}! Here are popular arrival times:
  Morning: [09:00 AM] [10:30 AM] [11:15 AM]
  Afternoon: [02:00 PM] [03:30 PM] [05:00 PM]
  Evening/Night: [07:30 PM] [09:00 PM] [11:00 PM]
  (Or type any specific hour you prefer!)"
WAIT FOR THE VISITOR TO SELECT THEIR TIME SLOT.

Stage 7 — Reason for Visit:
Once doctor, date, and time are chosen, ask:
"What is the main reason for this appointment?
[Routine check-up] [New symptom/concern] [Follow-up] [Consultation/Second opinion] [Other]
(You may also type a brief note. Please do not include sensitive medical details unless necessary)."

Stage 8 — Complete Summary & Explicit Confirmation:
ONLY AFTER Stages 1 through 7 are complete, display the structured confirmation summary:
"Please confirm your appointment details:
• **Patient**: {patient_name}
• **Patient Status**: {Existing CareHub patient or New Patient}
• **Booked For**: {Myself / Child / Family member}
• **Department**: {Department}
• **Doctor**: {Doctor Name}
• **Date**: {Date}
• **Time**: {Time}
• **Reason**: {Reason}
• **Mobile**: {Mobile}

Would you like me to confirm this booking?
[Confirm Appointment] [Change Details]"

Stage 9 — Booking Execution:
Call `public_book_appointment` with `confirmed=true` ONLY when the user explicitly clicks `[Confirm Appointment]`.
The backend records the booking, notifies the patient, and notifies the hospital receptionist desk.
Provide the Appointment Reference ID and instructions upon arrival.

EMERGENCY SAFETY GATE:
If at any point the user reports acute emergency symptoms (such as severe chest pain, difficulty breathing, profuse bleeding, stroke symptoms, loss of consciousness, or severe trauma):
Immediately respond with:
"⚠️ **Medical Emergency Alert**
If you are experiencing a life-threatening medical emergency or severe acute symptoms, please call local emergency services immediately (e.g. 102 / 112 / 911) or proceed to the nearest Hospital Emergency Room. CareHub's 24/7 Emergency & Trauma Center is open on Campus Ground Floor."
Do not continue normal booking if immediate emergency care is required.

STRICT PERMISSION SEPARATION & SECURITY RULES:
1. You are on the public landing page.
2. You MUST NOT cancel existing appointments.
3. You MUST NOT reschedule existing appointments.
4. You MUST NOT reveal EHRs, medical records, lab reports, or prescriptions.
5. If a user asks to cancel, reschedule, or view their medical records, explain: "To view your medical history, prescriptions, or manage an existing appointment, please sign in to your secure CareHub Patient Portal."
6. Always format interactive choices using bracket notation like `[Option 1] [Option 2]` so the visitor can click them directly.

Today's date is: {current_date}.
Keep responses polite, empathetic, concise, and professional."""

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
            "name": "public_lookup_patient",
            "description": "Look up an existing CareHub patient by mobile phone number or email address.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_info": {
                        "type": "string",
                        "description": "Patient 10-digit mobile number or email address"
                    }
                },
                "required": ["contact_info"]
            }
        }
    },
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
            "description": "Book a new appointment via Maya Booking Concierge. Set confirmed=false first to ask for confirmation, or confirmed=true after explicit user agreement.",
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
                    },
                    "booked_for": {
                        "type": "string",
                        "description": "Who the appointment is for: 'Myself', 'My child', or 'Another family member'"
                    },
                    "patient_status": {
                        "type": "string",
                        "description": "'existing' or 'new'"
                    },
                    "date_of_birth_str": {
                        "type": "string",
                        "description": "Patient date of birth in YYYY-MM-DD format (optional)"
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

    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                body = response.read().decode('utf-8')
                return json.loads(body)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8', errors='ignore')
            print(f"[CareHub Groq AI] HTTP Error {e.code}: {err_body}")
            if e.code == 429 and attempt == 0:
                import time
                retry_sec = 2.5
                try:
                    retry_header = e.headers.get('Retry-After')
                    if retry_header:
                        retry_sec = min(float(retry_header), 4.0)
                except Exception:
                    pass
                time.sleep(retry_sec)
                continue
            raise
        except Exception as e:
            print(f"[CareHub Groq AI] Connection Error: {e}")
            raise


def run_public_chat(messages: list) -> dict:
    """
    Executes the public landing page booking AI agent (Maya).
    """
    from app.ai.tools_public import (
        public_lookup_patient,
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
            'content': (
                "Hi! I'm Maya, your CareHub Booking Concierge. "
                "To enable live conversational AI scheduling, please configure `GROQ_API_KEY` in your `.env` file. "
                "You can also book directly with any doctor using our Doctors Directory."
            )
        }

    current_date = date.today().strftime('%A, %B %d, %Y')
    system_prompt = PUBLIC_SYSTEM_PROMPT.replace('{current_date}', current_date)

    formatted_messages = [{"role": "system", "content": system_prompt}]
    for m in messages:
        if m.get('role') in ('user', 'assistant'):
            formatted_messages.append({
                "role": m.get('role'),
                "content": m.get('content', '')
            })

    tool_dispatch = {
        'public_lookup_patient': lambda args: public_lookup_patient(
            str(args.get('contact_info', ''))
        ),
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
            confirmed=bool(args.get('confirmed', False)),
            booked_for=str(args.get('booked_for', 'Myself')),
            patient_status=args.get('patient_status'),
            date_of_birth_str=args.get('date_of_birth_str')
        )
    }

    # Find working model
    active_model = None

    # Agent tool execution loop (max 4 turns)
    for _ in range(4):
        resp_json = None
        models_to_try = ([active_model] + [m for m in CANDIDATE_MODELS if m != active_model]) if active_model else CANDIDATE_MODELS

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
        models_to_try = ([active_model] + [m for m in CANDIDATE_MODELS if m != active_model]) if active_model else CANDIDATE_MODELS

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
