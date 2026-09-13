"""
CareHub AI Chatbot Routes — Endpoints for Public Landing Page and Authenticated Patient Portal AI.
"""
from flask import request, jsonify
from flask_login import login_required, current_user
from app.ai import ai_bp
from app.auth.utils import role_required
from app.patients.models import Patient
from app.ai.groq_service import run_public_chat, run_patient_chat

@ai_bp.route('/public/status', methods=['GET'])
def public_status():
    """Health status and configuration check for public AI."""
    import os
    has_key = bool(os.environ.get('GROQ_API_KEY'))
    return jsonify({
        'status': 'online',
        'service': 'CareHub Public AI Appointment Assistant',
        'ai_enabled': has_key
    })

@ai_bp.route('/public/chat', methods=['POST'])
def public_chat():
    """
    Public unauthenticated endpoint for landing page appointment booking AI.
    Strictly restricted to finding availability and booking new appointments.
    """
    data = request.get_json() or {}
    messages = data.get('messages', [])

    if not messages or not isinstance(messages, list):
        return jsonify({
            'success': False,
            'error': 'Invalid messages payload.'
        }), 400

    # Ensure last message is from user
    last_msg = messages[-1]
    user_text = last_msg.get('content', '').strip().lower()

    # Pre-flight security guard against cancellation/rescheduling queries on public endpoint
    refusal_keywords = ['cancel my appointment', 'cancel appointment', 'reschedule my appointment', 'reschedule appointment', 'view my appointment', 'my appointments', 'my prescription', 'my lab report', 'my ehr', 'my medical record']
    if any(k in user_text for k in refusal_keywords):
        if 'cancel' in user_text:
            return jsonify({
                'success': True,
                'message': {
                    'role': 'assistant',
                    'content': "I can only help with booking a new appointment here. To cancel or manage an existing appointment, please sign in to your CareHub patient account."
                }
            })
        elif 'reschedule' in user_text:
            return jsonify({
                'success': True,
                'message': {
                    'role': 'assistant',
                    'content': "I can only help with booking a new appointment here. To reschedule an existing appointment, please sign in to your CareHub patient account."
                }
            })
        else:
            return jsonify({
                'success': True,
                'message': {
                    'role': 'assistant',
                    'content': "For your privacy and security, appointment history, medical records, and prescriptions can only be viewed after signing in to your CareHub patient account."
                }
            })

    try:
        response_msg = run_public_chat(messages)
        return jsonify({
            'success': True,
            'message': response_msg
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'An unexpected error occurred while processing your request. Please try again.'
        }), 500


@ai_bp.route('/patient/chat', methods=['POST'])
@login_required
@role_required('Patient')
def patient_chat():
    """
    Authenticated patient portal endpoint.
    Strictly isolated to current_user's patient record.
    """
    # Resolve current patient from authenticated session
    patient = None
    if current_user.email:
        patient = Patient.query.filter_by(email=current_user.email).first()
    if not patient and hasattr(current_user, 'patient_profile') and current_user.patient_profile:
        patient = current_user.patient_profile

    if not patient:
        return jsonify({
            'success': False,
            'error': 'Patient record is not linked to this authenticated session.'
        }), 403

    data = request.get_json() or {}
    messages = data.get('messages', [])

    if not messages or not isinstance(messages, list):
        return jsonify({
            'success': False,
            'error': 'Invalid messages payload.'
        }), 400

    try:
        response_msg = run_patient_chat(messages, current_patient_id=patient.id)
        return jsonify({
            'success': True,
            'patient_name': patient.full_name,
            'patient_code': patient.patient_code,
            'message': response_msg
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'An unexpected error occurred while processing your request. Please try again.'
        }), 500
