import os
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.conf import settings

from .models import AppraisalSession, ChecklistItem
from .services.analyzer import (
    parse_html_order,
    parse_xml_report,
    compare_marked_fields,
    verify_rejection_reasons,
    compute_xml_differences,
    extract_pdf_diff_details,
    evaluate_confirmation_checklist_rules
)

SAMPLE_PACKAGES = [
    {'id': '2610-01636', 'lender': 'East Coast Capital', 'rejections': 1, 'borrower': 'John M & Mary R', 'val': '$705,000'},
    {'id': '269-03093', 'lender': 'Churchill Real Estate', 'rejections': 4, 'borrower': 'Charli Tapia', 'val': '$1,550,000'},
    {'id': '2610-01207', 'lender': 'theLender', 'rejections': 5, 'borrower': 'David Chen', 'val': '$170,000'},
    {'id': '2610-02155', 'lender': 'Loanguys.com', 'rejections': 3, 'borrower': 'Robert Green', 'val': '$75,000'},
    {'id': '2610-02182', 'lender': 'Logan Finance', 'rejections': 2, 'borrower': 'Sarah Jenkins', 'val': '$550,000'},
    {'id': '267-01580', 'lender': 'Visio Lending', 'rejections': 1, 'borrower': 'Michael Scott', 'val': '$600,000'},
    {'id': '269-02863', 'lender': 'Lendoor LLC', 'rejections': 2, 'borrower': 'Emily Watson', 'val': '$460,000'},
]

def resolve_file_path(path):
    if not path:
        return ""
    if os.path.exists(path):
        return path
    
    # Try relative to BASE_DIR
    p1 = os.path.join(settings.BASE_DIR, path)
    if os.path.exists(p1):
        return p1

    # Try in reports/
    basename = os.path.basename(path)
    p2 = os.path.join(settings.BASE_DIR, 'reports', basename)
    if os.path.exists(p2):
        return p2

    # Try in media/uploads/
    p3 = os.path.join(settings.MEDIA_ROOT, 'uploads', basename)
    if os.path.exists(p3):
        return p3

    p4 = os.path.join(settings.BASE_DIR, 'media', 'uploads', basename)
    if os.path.exists(p4):
        return p4

    return path

def get_or_create_default_session(session_id='default'):
    default_html = resolve_file_path(os.path.join(settings.BASE_DIR, 'reports', '269-03093.html'))
    default_old = resolve_file_path(os.path.join(settings.BASE_DIR, 'reports', '269-03093.xml'))
    default_new = resolve_file_path(os.path.join(settings.BASE_DIR, 'reports', '269-03093_Revised.xml'))

    session, created = AppraisalSession.objects.get_or_create(
        session_id=session_id,
        defaults={
            'appraisal_number': '269-03093',
            'order_html_path': default_html,
            'old_xml_path': default_old,
            'new_xml_path': default_new,
            'reviewer_name': 'QC Appraisal Specialist',
            'reviewer_notes': 'All four revision rejection items have been fully resolved by the vendor. Borrower name corrected to Charli Tapia, Outside Entry basement improvement added, bath adjustments reconciled across narrative and grid, and 3rd bathroom photo provided. Recommend approval for delivery to Churchill Real Estate.',
            'qc_status': 'APPROVED',
            'signed_off_at': timezone.now()
        }
    )
    # Self-heal invalid or moved file paths for existing sessions
    updated = False
    if not os.path.exists(session.order_html_path):
        resolved = resolve_file_path(session.order_html_path)
        if os.path.exists(resolved):
            session.order_html_path = resolved
            updated = True
    if not os.path.exists(session.old_xml_path):
        resolved = resolve_file_path(session.old_xml_path)
        if os.path.exists(resolved):
            session.old_xml_path = resolved
            updated = True
    if not os.path.exists(session.new_xml_path):
        resolved = resolve_file_path(session.new_xml_path)
        if os.path.exists(resolved):
            session.new_xml_path = resolved
            updated = True
    if updated:
        session.save(update_fields=['order_html_path', 'old_xml_path', 'new_xml_path'])

    return session

def dashboard_view(request):
    session_id = request.GET.get('session_id', 'default')
    session = get_or_create_default_session(session_id)

    # Resolve file paths
    html_path = resolve_file_path(session.order_html_path)
    old_xml_path = resolve_file_path(session.old_xml_path)
    new_xml_path = resolve_file_path(session.new_xml_path)

    # 1. Parse and Compare
    html_data = parse_html_order(html_path)
    old_xml_data = parse_xml_report(old_xml_path)
    new_xml_data = parse_xml_report(new_xml_path)

    # Update session appraisal number if detected
    if html_data.get('appraisal_number') and session.appraisal_number != html_data.get('appraisal_number'):
        session.appraisal_number = html_data.get('appraisal_number')
        session.save(update_fields=['appraisal_number'])

    # 2. Marked Fields Matching
    field_comparison = compare_marked_fields(html_data, old_xml_data, new_xml_data)

    # 3. Rejection Reason Cross Verification
    rejection_verifications = verify_rejection_reasons(html_data, old_xml_path, new_xml_path)

    # 4. XML Differences
    xml_differences = compute_xml_differences(old_xml_path, new_xml_path)

    # 5. PDF Diff Details with RapidFuzz Rejection Linking
    pdf_page_diffs = extract_pdf_diff_details(old_xml_path, new_xml_path, rejection_items=html_data.get('rejection_items', []))

    # 5b. Confirmation Checklist 8 Standard Rules
    checklist_execution_time, confirmation_rules_results = evaluate_confirmation_checklist_rules(old_xml_path, new_xml_path, html_data)

    # Dynamic reviewer notes if default or outdated
    client_name = html_data.get('client_name') or 'Client'
    corr_rejections = sum(1 for r in rejection_verifications if r.get('is_corrected'))
    if not session.reviewer_notes or 'Churchill Real Estate' in session.reviewer_notes and client_name != 'Churchill Real Estate':
        if len(rejection_verifications) > 0 and corr_rejections == len(rejection_verifications):
            session.reviewer_notes = f"All {len(rejection_verifications)} revision rejection items have been fully resolved by the vendor. Marked fields and XML/PDF revisions verified. Recommend approval for delivery to {client_name}."
        elif len(rejection_verifications) > 0:
            session.reviewer_notes = f"{corr_rejections} of {len(rejection_verifications)} revision items verified. Further appraiser clarification recommended prior to delivery to {client_name}."
        else:
            session.reviewer_notes = f"Appraisal #{session.appraisal_number} reviewed and verified with no revision rejections. Cleared for delivery to {client_name}."
        session.save(update_fields=['reviewer_notes'])

    # Summary metrics
    total_fields = len(field_comparison)
    matched_fields = sum(1 for f in field_comparison if f['match_new'])
    mismatched_fields = total_fields - matched_fields

    total_rejections = len(rejection_verifications)
    corrected_rejections = sum(1 for r in rejection_verifications if r['is_corrected'])

    total_diffs = len(xml_differences)
    
    rules_total = len(confirmation_rules_results)
    rules_passed = sum(1 for r in confirmation_rules_results if r['is_yes'])
    rules_pct = int((rules_passed / rules_total * 100)) if rules_total > 0 else 0

    # Group diffs by category
    diff_categories = {}
    for d in xml_differences:
        cat = d['category']
        diff_categories.setdefault(cat, []).append(d)

    context = {
        'session': session,
        'html_data': html_data,
        'old_xml_data': old_xml_data,
        'new_xml_data': new_xml_data,
        'field_comparison': field_comparison,
        'rejection_verifications': rejection_verifications,
        'xml_differences': xml_differences,
        'diff_categories': diff_categories,
        'pdf_page_diffs': pdf_page_diffs,
        'confirmation_rules_results': confirmation_rules_results,
        'checklist_execution_time': checklist_execution_time,
        'samples': SAMPLE_PACKAGES,
        'metrics': {
            'total_fields': total_fields,
            'matched_fields': matched_fields,
            'mismatched_fields': mismatched_fields,
            'total_rejections': total_rejections,
            'corrected_rejections': corrected_rejections,
            'total_diffs': total_diffs,
            'rules_total': rules_total,
            'rules_passed': rules_passed,
            'rules_pct': rules_pct,
        }
    }

    return render(request, 'qc_app/dashboard.html', context)


@csrf_exempt
def toggle_checklist_item(request, item_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            item = get_object_or_404(ChecklistItem, id=item_id)
            if 'is_verified' in data:
                item.is_verified = bool(data['is_verified'])
            if 'notes' in data:
                item.notes = str(data['notes'])
            item.save()

            session = item.session
            total_checks = session.checklist_items.count()
            verified_checks = session.checklist_items.filter(is_verified=True).count()
            pct = int((verified_checks / total_checks * 100)) if total_checks > 0 else 0

            return JsonResponse({
                'success': True,
                'item_id': item.id,
                'is_verified': item.is_verified,
                'notes': item.notes,
                'verified_count': verified_checks,
                'total_count': total_checks,
                'percent': pct
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid method'}, status=405)


@csrf_exempt
def update_session(request, session_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            session = get_object_or_404(AppraisalSession, session_id=session_id)
            if 'reviewer_name' in data:
                session.reviewer_name = data['reviewer_name']
            if 'reviewer_notes' in data:
                session.reviewer_notes = data['reviewer_notes']
            if 'qc_status' in data:
                session.qc_status = data['qc_status']
                if data['qc_status'] == 'APPROVED':
                    session.signed_off_at = timezone.now()
            session.save()
            return JsonResponse({'success': True, 'qc_status': session.qc_status})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid method'}, status=405)


def reset_checklist(request, session_id):
    session = get_object_or_404(AppraisalSession, session_id=session_id)
    return redirect(f"/dashboard/?session_id={session.session_id}#tab-checklist")


def printable_report_view(request):
    session_id = request.GET.get('session_id', 'default')
    session = get_or_create_default_session(session_id)

    html_path = resolve_file_path(session.order_html_path)
    old_xml_path = resolve_file_path(session.old_xml_path)
    new_xml_path = resolve_file_path(session.new_xml_path)

    html_data = parse_html_order(html_path)
    old_xml_data = parse_xml_report(old_xml_path)
    new_xml_data = parse_xml_report(new_xml_path)

    field_comparison = compare_marked_fields(html_data, old_xml_data, new_xml_data)
    rejection_verifications = verify_rejection_reasons(html_data, old_xml_path, new_xml_path)
    xml_differences = compute_xml_differences(old_xml_path, new_xml_path)
    checklist_execution_time, confirmation_rules_results = evaluate_confirmation_checklist_rules(old_xml_path, new_xml_path, html_data)

    context = {
        'session': session,
        'html_data': html_data,
        'old_xml_data': old_xml_data,
        'new_xml_data': new_xml_data,
        'field_comparison': field_comparison,
        'rejection_verifications': rejection_verifications,
        'xml_differences': xml_differences,
        'confirmation_rules_results': confirmation_rules_results,
        'checklist_execution_time': checklist_execution_time,
        'now': timezone.now()
    }
    return render(request, 'qc_app/printable_report.html', context)


# REST API endpoints
def api_summary(request):
    session_id = request.GET.get('session_id', 'default')
    session = get_or_create_default_session(session_id)
    html_path = resolve_file_path(session.order_html_path)
    old_xml_path = resolve_file_path(session.old_xml_path)
    new_xml_path = resolve_file_path(session.new_xml_path)

    html_data = parse_html_order(html_path)
    old_xml_data = parse_xml_report(old_xml_path)
    new_xml_data = parse_xml_report(new_xml_path)

    fields = compare_marked_fields(html_data, old_xml_data, new_xml_data)
    rejections = verify_rejection_reasons(html_data, old_xml_path, new_xml_path)
    diffs = compute_xml_differences(old_xml_path, new_xml_path)

    return JsonResponse({
        'appraisal_number': session.appraisal_number,
        'qc_status': session.qc_status,
        'reviewer_name': session.reviewer_name,
        'marked_fields_count': len(fields),
        'matched_count': sum(1 for f in fields if f['match_new']),
        'rejections_count': len(rejections),
        'rejections_corrected': sum(1 for r in rejections if r['is_corrected']),
        'xml_diffs_count': len(diffs),
        'checklist_progress': f"{session.checklist_items.filter(is_verified=True).count()}/{session.checklist_items.count()}"
    })


def api_fields(request):
    session_id = request.GET.get('session_id', 'default')
    session = get_or_create_default_session(session_id)
    html_path = resolve_file_path(session.order_html_path)
    old_xml_path = resolve_file_path(session.old_xml_path)
    new_xml_path = resolve_file_path(session.new_xml_path)

    html_data = parse_html_order(html_path)
    old_xml_data = parse_xml_report(old_xml_path)
    new_xml_data = parse_xml_report(new_xml_path)
    fields = compare_marked_fields(html_data, old_xml_data, new_xml_data)
    return JsonResponse({'fields': fields})


def api_rejections(request):
    session_id = request.GET.get('session_id', 'default')
    session = get_or_create_default_session(session_id)
    html_path = resolve_file_path(session.order_html_path)
    old_xml_path = resolve_file_path(session.old_xml_path)
    new_xml_path = resolve_file_path(session.new_xml_path)

    html_data = parse_html_order(html_path)
    rejections = verify_rejection_reasons(html_data, old_xml_path, new_xml_path)
    return JsonResponse({'rejections': rejections})


def api_diff(request):
    session_id = request.GET.get('session_id', 'default')
    session = get_or_create_default_session(session_id)
    old_xml_path = resolve_file_path(session.old_xml_path)
    new_xml_path = resolve_file_path(session.new_xml_path)
    diffs = compute_xml_differences(old_xml_path, new_xml_path)
    return JsonResponse({'differences': diffs})


import csv

def export_fields_csv(request):
    session_id = request.GET.get('session_id', 'default')
    session = get_or_create_default_session(session_id)
    html_path = resolve_file_path(session.order_html_path)
    old_xml_path = resolve_file_path(session.old_xml_path)
    new_xml_path = resolve_file_path(session.new_xml_path)

    html_data = parse_html_order(html_path)
    old_xml_data = parse_xml_report(old_xml_path)
    new_xml_data = parse_xml_report(new_xml_path)
    fields = compare_marked_fields(html_data, old_xml_data, new_xml_data)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="Marked_Fields_{session.appraisal_number}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Field Name', 'Value from HTML Order', 'Value from Old Report (XML)', 'Value from Revised Report (XML)', 'Status', 'Notes'])
    for f in fields:
        writer.writerow([f['field_name'], f['html_val'], f['old_val'], f['new_val'], f['status'], f['notes']])

    return response


def export_diff_csv(request):
    session_id = request.GET.get('session_id', 'default')
    session = get_or_create_default_session(session_id)
    old_xml_path = resolve_file_path(session.old_xml_path)
    new_xml_path = resolve_file_path(session.new_xml_path)
    diffs = compute_xml_differences(old_xml_path, new_xml_path)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="XML_Differences_{session.appraisal_number}.csv"'

    old_name = os.path.basename(old_xml_path) or 'Old_Report.xml'
    new_name = os.path.basename(new_xml_path) or 'Revised_Report.xml'

    writer = csv.writer(response)
    writer.writerow(['Category', 'XPath / Attribute', f'Old Value ({old_name})', f'New Value ({new_name})', 'Significance / Rejection Impact'])
    for d in diffs:
        writer.writerow([d['category'], d['xpath'], d['old_val'], d['new_val'], d['impact']])

    return response


def upload_files_view(request):
    if request.method == 'GET' and request.GET.get('session_id'):
        return redirect(f"/dashboard/?session_id={request.GET.get('session_id')}")

    samples = SAMPLE_PACKAGES

    if request.method == 'POST':
        try:
            upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads')
            os.makedirs(upload_dir, exist_ok=True)

            order_file = request.FILES.get('order_file')
            old_xml_file = request.FILES.get('old_xml_file')
            new_xml_file = request.FILES.get('new_xml_file')

            if not (order_file and old_xml_file and new_xml_file):
                return render(request, 'qc_app/upload.html', {'error': 'Please provide all 3 files: Order HTML, Old XML, and Revised XML.', 'samples': samples})

            import uuid
            new_session_id = str(uuid.uuid4())[:8]

            order_path = os.path.join(upload_dir, f"{new_session_id}_{order_file.name}")
            old_path = os.path.join(upload_dir, f"{new_session_id}_{old_xml_file.name}")
            new_path = os.path.join(upload_dir, f"{new_session_id}_{new_xml_file.name}")

            with open(order_path, 'wb+') as dest:
                for chunk in order_file.chunks():
                    dest.write(chunk)
            with open(old_path, 'wb+') as dest:
                for chunk in old_xml_file.chunks():
                    dest.write(chunk)
            with open(new_path, 'wb+') as dest:
                for chunk in new_xml_file.chunks():
                    dest.write(chunk)

            # Create session
            session = AppraisalSession.objects.create(
                session_id=new_session_id,
                order_html_path=order_path,
                old_xml_path=old_path,
                new_xml_path=new_path,
                reviewer_name='QC Reviewer',
                qc_status='IN_REVIEW'
            )

            return redirect(f"/dashboard/?session_id={new_session_id}")
        except Exception as e:
            return render(request, 'qc_app/upload.html', {'error': f"Upload failed: {str(e)}", 'samples': samples})

    return render(request, 'qc_app/upload.html', {'samples': samples})


def load_sample_view(request, sample_id):
    html_name = f"{sample_id}.html"
    old_name = f"{sample_id}.xml"
    new_name = f"{sample_id}_Revised.xml"

    html_path = resolve_file_path(os.path.join(settings.BASE_DIR, 'reports', html_name))
    old_path = resolve_file_path(os.path.join(settings.BASE_DIR, 'reports', old_name))
    if not os.path.exists(old_path):
        old_path = resolve_file_path(os.path.join(settings.BASE_DIR, 'reports', f"{sample_id}.XML"))
    
    new_path = resolve_file_path(os.path.join(settings.BASE_DIR, 'reports', new_name))
    if not os.path.exists(new_path):
        new_path = resolve_file_path(os.path.join(settings.BASE_DIR, 'reports', f"{sample_id}_Revised.XML"))

    session, created = AppraisalSession.objects.get_or_create(
        session_id=sample_id,
        defaults={
            'appraisal_number': sample_id,
            'order_html_path': html_path,
            'old_xml_path': old_path,
            'new_xml_path': new_path,
            'reviewer_name': 'Senior QC Specialist',
            'qc_status': 'IN_REVIEW'
        }
    )
    if not created:
        session.order_html_path = html_path
        session.old_xml_path = old_path
        session.new_xml_path = new_path
        session.save(update_fields=['order_html_path', 'old_xml_path', 'new_xml_path'])

    return redirect(f"/dashboard/?session_id={sample_id}")
