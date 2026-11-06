from django.db import models
from django.utils import timezone

class AppraisalSession(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('IN_REVIEW', 'In Review'),
        ('APPROVED', 'Approved for Delivery'),
        ('REVISION_REQUIRED', 'Revision Required'),
    ]

    session_id = models.CharField(max_length=100, unique=True, default='default')
    appraisal_number = models.CharField(max_length=100, default='269-03093')
    order_html_path = models.CharField(max_length=500, default='reports/269-03093.html')
    old_xml_path = models.CharField(max_length=500, default='reports/269-03093.xml')
    new_xml_path = models.CharField(max_length=500, default='reports/269-03093_Revised.xml')
    reviewer_name = models.CharField(max_length=200, default='Senior QC Analyst')
    reviewer_notes = models.TextField(blank=True, default='')
    qc_status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING')
    signed_off_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Session {self.session_id} - Appraisal #{self.appraisal_number}"


class ChecklistItem(models.Model):
    CATEGORY_CHOICES = [
        ('FIELD_MATCH', 'Order Form Field Matching'),
        ('REJECTION_FIX', 'Rejection Reason Verification'),
        ('REPORT_DIFF', 'XML Structure & Addenda Differences'),
        ('COMPLIANCE', 'Compliance & Reviewer Sign-Off'),
    ]

    session = models.ForeignKey(AppraisalSession, on_delete=models.CASCADE, related_name='checklist_items')
    item_id = models.CharField(max_length=50)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='FIELD_MATCH')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_verified = models.BooleanField(default=False)
    auto_status = models.CharField(max_length=50, default='CHECK_REQUIRED')
    notes = models.TextField(blank=True, default='')
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"[{self.category}] {self.title} - {'Verified' if self.is_verified else 'Pending'}"
