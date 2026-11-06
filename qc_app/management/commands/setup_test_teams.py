from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group

class Command(BaseCommand):
    help = 'Create test teams and user accounts for testing the Appraisal QC application and printable reports'

    def handle(self, *args, **options):
        # 1. Define Teams / Groups
        teams_data = [
            {
                'group': 'Team Alpha - Lead QC Specialists',
                'username': 'team_alpha',
                'first_name': 'Team Alpha',
                'last_name': 'Lead Reviewer',
                'email': 'alpha@appraisalqc.local',
                'role': 'Team Alpha - Lead QC Specialist',
                'password': 'qcpass123',
                'is_staff': True,
                'is_superuser': False,
            },
            {
                'group': 'Team Beta - Revision Verification Auditors',
                'username': 'team_beta',
                'first_name': 'Team Beta',
                'last_name': 'Revision Auditor',
                'email': 'beta@appraisalqc.local',
                'role': 'Team Beta - Senior Revision Auditor',
                'password': 'qcpass123',
                'is_staff': True,
                'is_superuser': False,
            },
            {
                'group': 'Team Gamma - Compliance & Rules Inspectors',
                'username': 'team_gamma',
                'first_name': 'Team Gamma',
                'last_name': 'Compliance Inspector',
                'email': 'gamma@appraisalqc.local',
                'role': 'Team Gamma - Compliance & Rules Inspector',
                'password': 'qcpass123',
                'is_staff': True,
                'is_superuser': False,
            },
            {
                'group': 'Team Delta - AMC Operations & Delivery QA',
                'username': 'team_delta',
                'first_name': 'Team Delta',
                'last_name': 'Operations QA',
                'email': 'delta@appraisalqc.local',
                'role': 'Team Delta - AMC Operations Analyst',
                'password': 'qcpass123',
                'is_staff': True,
                'is_superuser': False,
            },
        ]

        # 2. Superuser / Admin
        admin_user, admin_created = User.objects.get_or_create(username='admin')
        admin_user.first_name = 'QC'
        admin_user.last_name = 'Administrator'
        admin_user.email = 'admin@appraisalqc.local'
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.set_password('admin123')
        admin_user.save()
        status_admin = 'Created' if admin_created else 'Updated'
        self.stdout.write(self.style.SUCCESS(f"[{status_admin}] Superuser: admin (password: admin123)"))

        # 3. Create Teams and Users
        for t in teams_data:
            group, _ = Group.objects.get_or_create(name=t['group'])
            user, created = User.objects.get_or_create(username=t['username'])
            user.first_name = t['first_name']
            user.last_name = t['last_name']
            user.email = t['email']
            user.is_staff = t['is_staff']
            user.is_superuser = t['is_superuser']
            user.set_password(t['password'])
            user.save()
            user.groups.add(group)

            action = 'Created' if created else 'Updated'
            self.stdout.write(self.style.SUCCESS(
                f"[{action}] Team: {t['group']}\n"
                f"         Username: {t['username']} | Password: {t['password']} | Role: {t['role']}"
            ))

        self.stdout.write(self.style.SUCCESS("\nAll testing teams and accounts successfully configured!"))
