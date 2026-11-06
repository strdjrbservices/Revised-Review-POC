"""
PythonAnywhere WSGI Configuration for strdjrbservices1
======================================================
Domain: strdjrbservices1.pythonanywhere.com
File:   /var/www/strdjrbservices1_pythonanywhere_com_wsgi.py
Project: Revised-Review-POC
"""

import os
import sys

# -----------------------------------------------------------------------------
# 1. Project Directory Configuration
# -----------------------------------------------------------------------------
# Absolute path to your project directory on PythonAnywhere:
PROJECT_DIR = '/home/strdjrbservices1/Revised-Review-POC'

# Fallback auto-detection if folder was named differently
if not os.path.exists(PROJECT_DIR):
    home_dir = os.path.expanduser('~')
    candidates = [
        'Revised-Review-POC',
        'appraisal-hub',
        'Update POC',
        'XML POC - Copy',
        'XML-POC',
        'xml-poc',
    ]
    for candidate in candidates:
        test_path = os.path.join(home_dir, candidate)
        if os.path.exists(os.path.join(test_path, 'manage.py')):
            PROJECT_DIR = test_path
            break

# Ensure project directory is first in Python's module search path
if os.path.exists(PROJECT_DIR) and PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

# -----------------------------------------------------------------------------
# 2. Virtual Environment Configuration (Optional explicit fallback)
# -----------------------------------------------------------------------------
# If you configured the Virtualenv path in the Web tab, PythonAnywhere loads it
# automatically. In case it doesn't, this ensures site-packages are detected:
virtualenv_path = '/home/strdjrbservices1/.virtualenvs/qc-env'
site_packages_candidates = [
    os.path.join(virtualenv_path, 'lib', 'python3.11', 'site-packages'),
    os.path.join(virtualenv_path, 'lib', 'python3.12', 'site-packages'),
    os.path.join(virtualenv_path, 'lib', 'python3.10', 'site-packages'),
]
for sp in site_packages_candidates:
    if os.path.exists(sp) and sp not in sys.path:
        sys.path.insert(1, sp)

# -----------------------------------------------------------------------------
# 3. Environment Variables (.env support)
# -----------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    env_file = os.path.join(PROJECT_DIR, '.env')
    if os.path.exists(env_file):
        load_dotenv(env_file)
except ImportError:
    pass

# Set Django settings module
os.environ['DJANGO_SETTINGS_MODULE'] = 'appraisal_qc_project.settings'

# -----------------------------------------------------------------------------
# 4. WSGI Application
# -----------------------------------------------------------------------------
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
