from django.urls import path
from . import views

app_name = 'qc_app'

urlpatterns = [
    path('', views.upload_files_view, name='home'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('upload/', views.upload_files_view, name='upload_files'),
    path('load-sample/<str:sample_id>/', views.load_sample_view, name='load_sample'),
    path('printable-report/', views.printable_report_view, name='printable_report'),
    path('api/checklist/toggle/<int:item_id>/', views.toggle_checklist_item, name='toggle_checklist_item'),
    path('api/checklist/reset/<str:session_id>/', views.reset_checklist, name='reset_checklist'),
    path('api/session/update/<str:session_id>/', views.update_session, name='update_session'),
    path('api/summary/', views.api_summary, name='api_summary'),
    path('api/fields/', views.api_fields, name='api_fields'),
    path('api/rejections/', views.api_rejections, name='api_rejections'),
    path('api/diff/', views.api_diff, name='api_diff'),
    path('export/fields/csv/', views.export_fields_csv, name='export_fields_csv'),
    path('export/diff/csv/', views.export_diff_csv, name='export_diff_csv'),
]

