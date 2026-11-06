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
        return os.path.abspath(path)
    
    basename = os.path.basename(path)
    candidates = [
        os.path.join(settings.BASE_DIR, path),
        # Check subdirectories in reports
        os.path.join(settings.BASE_DIR, 'reports', 'order', basename),
        os.path.join(settings.BASE_DIR, 'reports', 'old', basename),
        os.path.join(settings.BASE_DIR, 'reports', 'revised', basename),
        os.path.join(settings.BASE_DIR, 'reports', basename),
        # Check subdirectories in media/uploads
        os.path.join(settings.MEDIA_ROOT, 'uploads', 'order', basename),
        os.path.join(settings.MEDIA_ROOT, 'uploads', 'old', basename),
        os.path.join(settings.MEDIA_ROOT, 'uploads', 'revised', basename),
        os.path.join(settings.MEDIA_ROOT, 'uploads', basename),
        os.path.join(settings.BASE_DIR, 'media', 'uploads', 'order', basename),
        os.path.join(settings.BASE_DIR, 'media', 'uploads', 'old', basename),
        os.path.join(settings.BASE_DIR, 'media', 'uploads', 'revised', basename),
        os.path.join(settings.BASE_DIR, 'media', 'uploads', basename),
        # Check root directories
        os.path.join(settings.BASE_DIR, 'order', basename),
        os.path.join(settings.BASE_DIR, 'old', basename),
        os.path.join(settings.BASE_DIR, 'revised', basename),
    ]
    for cand in candidates:
        if os.path.exists(cand):
            return os.path.abspath(cand)

    return path

def find_package_files(package_id):
    """
    Finds order HTML, baseline XML, and revised XML across separate directories
    (order/, old/, and revised/).
    """
    # 1. Order HTML
    order_candidates = [
        os.path.join(settings.MEDIA_ROOT, 'uploads', 'order', f"{package_id}.html"),
        os.path.join(settings.BASE_DIR, 'reports', 'order', f"{package_id}.html"),
        os.path.join(settings.BASE_DIR, 'order', f"{package_id}.html"),
        os.path.join(settings.BASE_DIR, 'reports', f"{package_id}.html"),
        os.path.join(settings.MEDIA_ROOT, 'uploads', f"{package_id}.html"),
    ]
    order_path = ""
    for c in order_candidates:
        if os.path.exists(c):
            order_path = os.path.abspath(c)
            break
    if not order_path:
        for search_dir in [
            os.path.join(settings.MEDIA_ROOT, 'uploads', 'order'),
            os.path.join(settings.BASE_DIR, 'reports', 'order'),
            os.path.join(settings.BASE_DIR, 'order'),
            os.path.join(settings.MEDIA_ROOT, 'uploads'),
            os.path.join(settings.BASE_DIR, 'reports'),
        ]:
            if os.path.exists(search_dir):
                for f in os.listdir(search_dir):
                    if package_id in f and f.lower().endswith(('.html', '.htm')):
                        order_path = os.path.abspath(os.path.join(search_dir, f))
                        break
            if order_path:
                break

    # 2. Old Baseline XML
    old_candidates = [
        os.path.join(settings.MEDIA_ROOT, 'uploads', 'old', f"{package_id}.xml"),
        os.path.join(settings.MEDIA_ROOT, 'uploads', 'old', f"{package_id}.XML"),
        os.path.join(settings.BASE_DIR, 'reports', 'old', f"{package_id}.xml"),
        os.path.join(settings.BASE_DIR, 'reports', 'old', f"{package_id}.XML"),
        os.path.join(settings.BASE_DIR, 'old', f"{package_id}.xml"),
        os.path.join(settings.BASE_DIR, 'old', f"{package_id}.XML"),
        os.path.join(settings.BASE_DIR, 'reports', f"{package_id}.xml"),
        os.path.join(settings.BASE_DIR, 'reports', f"{package_id}.XML"),
        os.path.join(settings.MEDIA_ROOT, 'uploads', f"{package_id}.xml"),
        os.path.join(settings.MEDIA_ROOT, 'uploads', f"{package_id}.XML"),
    ]
    old_path = ""
    for c in old_candidates:
        if os.path.exists(c):
            old_path = os.path.abspath(c)
            break
    if not old_path:
        for search_dir in [
            os.path.join(settings.MEDIA_ROOT, 'uploads', 'old'),
            os.path.join(settings.BASE_DIR, 'reports', 'old'),
            os.path.join(settings.BASE_DIR, 'old'),
            os.path.join(settings.MEDIA_ROOT, 'uploads'),
            os.path.join(settings.BASE_DIR, 'reports'),
        ]:
            if os.path.exists(search_dir):
                for f in os.listdir(search_dir):
                    if package_id in f and f.lower().endswith('.xml') and '_revised' not in f.lower():
                        old_path = os.path.abspath(os.path.join(search_dir, f))
                        break
            if old_path:
                break

    # 3. Revised XML
    revised_candidates = [
        os.path.join(settings.MEDIA_ROOT, 'uploads', 'revised', f"{package_id}_Revised.xml"),
        os.path.join(settings.MEDIA_ROOT, 'uploads', 'revised', f"{package_id}_Revised.XML"),
        os.path.join(settings.BASE_DIR, 'reports', 'revised', f"{package_id}_Revised.xml"),
        os.path.join(settings.BASE_DIR, 'reports', 'revised', f"{package_id}_Revised.XML"),
        os.path.join(settings.BASE_DIR, 'revised', f"{package_id}_Revised.xml"),
        os.path.join(settings.BASE_DIR, 'revised', f"{package_id}_Revised.XML"),
        os.path.join(settings.BASE_DIR, 'reports', f"{package_id}_Revised.xml"),
        os.path.join(settings.BASE_DIR, 'reports', f"{package_id}_Revised.XML"),
        os.path.join(settings.MEDIA_ROOT, 'uploads', f"{package_id}_Revised.xml"),
        os.path.join(settings.MEDIA_ROOT, 'uploads', f"{package_id}_Revised.XML"),
    ]
    revised_path = ""
    for c in revised_candidates:
        if os.path.exists(c):
            revised_path = os.path.abspath(c)
            break
    if not revised_path:
        for search_dir in [
            os.path.join(settings.MEDIA_ROOT, 'uploads', 'revised'),
            os.path.join(settings.BASE_DIR, 'reports', 'revised'),
            os.path.join(settings.BASE_DIR, 'revised'),
            os.path.join(settings.MEDIA_ROOT, 'uploads'),
            os.path.join(settings.BASE_DIR, 'reports'),
        ]:
            if os.path.exists(search_dir):
                for f in os.listdir(search_dir):
                    if package_id in f and f.lower().endswith('.xml') and '_revised' in f.lower():
                        revised_path = os.path.abspath(os.path.join(search_dir, f))
                        break
            if revised_path:
                break

    return order_path, old_path, revised_path

def get_all_packages():
    """Returns all packages, combining default samples and dynamically detected/uploaded packages."""
    packages_map = {p['id']: dict(p) for p in SAMPLE_PACKAGES}
    
    # Check sessions in DB
    for s in AppraisalSession.objects.all():
        num = s.appraisal_number or s.session_id
        if num not in packages_map:
            lender_name = 'Uploaded Package'
            try:
                if s.order_html_path and os.path.exists(resolve_file_path(s.order_html_path)):
                    hdata = parse_html_order(resolve_file_path(s.order_html_path))
                    if hdata.get('client_name'):
                        lender_name = hdata.get('client_name')
            except Exception:
                pass
            packages_map[num] = {
                'id': num,
                'lender': lender_name,
                'rejections': 0,
                'borrower': 'Uploaded',
                'val': 'N/A'
            }

    return list(packages_map.values())

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
    rules_passed = sum(1 for r in confirmation_rules_results if r.get('is_passed', r.get('is_yes', False)))
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
        'samples': get_all_packages(),
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

    all_packages = get_all_packages()
    target_package = request.GET.get('target_package') or '2610-01636'

    if request.method == 'POST':
        try:
            # 1. Ensure separate directories exist for order, old, and revised
            order_dir = os.path.join(settings.MEDIA_ROOT, 'uploads', 'order')
            old_dir = os.path.join(settings.MEDIA_ROOT, 'uploads', 'old')
            revised_dir = os.path.join(settings.MEDIA_ROOT, 'uploads', 'revised')

            reports_order = os.path.join(settings.BASE_DIR, 'reports', 'order')
            reports_old = os.path.join(settings.BASE_DIR, 'reports', 'old')
            reports_revised = os.path.join(settings.BASE_DIR, 'reports', 'revised')

            root_order = os.path.join(settings.BASE_DIR, 'order')
            root_old = os.path.join(settings.BASE_DIR, 'old')
            root_revised = os.path.join(settings.BASE_DIR, 'revised')

            for d in [order_dir, old_dir, revised_dir, reports_order, reports_old, reports_revised, root_order, root_old, root_revised]:
                os.makedirs(d, exist_ok=True)

            order_file = request.FILES.get('order_file')
            old_xml_file = request.FILES.get('old_xml_file')
            new_xml_file = request.FILES.get('new_xml_file')

            if not (order_file and old_xml_file and new_xml_file):
                return render(request, 'qc_app/upload.html', {
                    'error': 'Please provide all 3 files: Order HTML, Old XML, and Revised XML.',
                    'packages': all_packages,
                    'samples': all_packages,
                    'target_package': target_package
                })

            # Read order content to inspect appraisal_number
            order_bytes = order_file.read()
            selected_target = request.POST.get('target_package', '').strip()

            # Save temporary file to parse HTML
            temp_order_path = os.path.join(order_dir, f"temp_{order_file.name}")
            with open(temp_order_path, 'wb+') as dest:
                dest.write(order_bytes)

            parsed_html = {}
            try:
                parsed_html = parse_html_order(temp_order_path)
            except Exception:
                pass
            finally:
                if os.path.exists(temp_order_path):
                    try:
                        os.remove(temp_order_path)
                    except OSError:
                        pass

            # Determine package ID:
            # If user selected a specific target package (e.g. 2610-01636), save to that package.
            # Otherwise use parsed appraisal_number or default to '2610-01636'.
            if selected_target and selected_target != 'auto':
                package_id = selected_target
            elif parsed_html.get('appraisal_number'):
                package_id = parsed_html['appraisal_number']
            else:
                package_id = target_package or '2610-01636'

            # 2. Save order file to separate order/ directory
            order_path = os.path.join(order_dir, f"{package_id}.html")
            with open(order_path, 'wb+') as dest:
                dest.write(order_bytes)
            # Sync to reports/order/ and root order/
            with open(os.path.join(reports_order, f"{package_id}.html"), 'wb+') as dest:
                dest.write(order_bytes)
            with open(os.path.join(root_order, f"{package_id}.html"), 'wb+') as dest:
                dest.write(order_bytes)

            # 3. Save old baseline XML file to separate old/ directory
            old_bytes = old_xml_file.read()
            old_path = os.path.join(old_dir, f"{package_id}.xml")
            with open(old_path, 'wb+') as dest:
                dest.write(old_bytes)
            with open(os.path.join(reports_old, f"{package_id}.xml"), 'wb+') as dest:
                dest.write(old_bytes)
            # Handle potential uppercase .XML in reports
            if os.path.exists(os.path.join(reports_old, f"{package_id}.XML")):
                with open(os.path.join(reports_old, f"{package_id}.XML"), 'wb+') as dest:
                    dest.write(old_bytes)
            with open(os.path.join(root_old, f"{package_id}.xml"), 'wb+') as dest:
                dest.write(old_bytes)

            # 4. Save revised XML file to separate revised/ directory
            revised_bytes = new_xml_file.read()
            new_path = os.path.join(revised_dir, f"{package_id}_Revised.xml")
            with open(new_path, 'wb+') as dest:
                dest.write(revised_bytes)
            with open(os.path.join(reports_revised, f"{package_id}_Revised.xml"), 'wb+') as dest:
                dest.write(revised_bytes)
            # Handle potential uppercase .XML in reports
            if os.path.exists(os.path.join(reports_revised, f"{package_id}_Revised.XML")):
                with open(os.path.join(reports_revised, f"{package_id}_Revised.XML"), 'wb+') as dest:
                    dest.write(revised_bytes)
            with open(os.path.join(root_revised, f"{package_id}_Revised.xml"), 'wb+') as dest:
                dest.write(revised_bytes)

            # 5. Save/update session for the circle-marked package
            session, created = AppraisalSession.objects.get_or_create(
                session_id=package_id,
                defaults={
                    'appraisal_number': package_id,
                    'order_html_path': order_path,
                    'old_xml_path': old_path,
                    'new_xml_path': new_path,
                    'reviewer_name': 'QC Reviewer',
                    'qc_status': 'IN_REVIEW'
                }
            )
            session.appraisal_number = package_id
            session.order_html_path = order_path
            session.old_xml_path = old_path
            session.new_xml_path = new_path
            session.qc_status = 'IN_REVIEW'
            session.save()

            # Also update any existing session with appraisal_number=package_id
            AppraisalSession.objects.filter(appraisal_number=package_id).update(
                order_html_path=order_path,
                old_xml_path=old_path,
                new_xml_path=new_path
            )

            return redirect(f"/dashboard/?session_id={package_id}")
        except Exception as e:
            return render(request, 'qc_app/upload.html', {
                'error': f"Upload failed: {str(e)}",
                'packages': all_packages,
                'samples': all_packages,
                'target_package': target_package
            })

    return render(request, 'qc_app/upload.html', {
        'packages': all_packages,
        'samples': all_packages,
        'target_package': target_package
    })


def load_sample_view(request, sample_id):
    html_path, old_path, new_path = find_package_files(sample_id)

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
        session.appraisal_number = sample_id
        session.order_html_path = html_path
        session.old_xml_path = old_path
        session.new_xml_path = new_path
        session.save(update_fields=['appraisal_number', 'order_html_path', 'old_xml_path', 'new_xml_path'])

    return redirect(f"/dashboard/?session_id={sample_id}")
