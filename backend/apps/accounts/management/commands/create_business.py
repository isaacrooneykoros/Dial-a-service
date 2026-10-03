"""Create a business with its web address, branding, first branch and owner.

    python manage.py create_business --name "Mama Safi Laundry" --slug mamasafi \\
        --host mamasafi.localhost --branch Kilimani \\
        --owner-phone 0712345678 --owner-first-name Wanjiru --owner-last-name Kamau

The owner's password (and an optional 4-digit PIN for counter devices) is asked
for without echoing, or read from DIAL_OWNER_PASSWORD and DIAL_OWNER_PIN for
scripts. Passwords never go on the command line, where shells keep them in
history. Until self-serve sign-up (W-03, M6) this is how a business is added.

It lives in accounts, not tenancy, because it creates the owner: app
dependencies point one way (CLAUDE.md section 6.6).
"""

import getpass
import os
from typing import Any

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from apps.accounts.models import Role
from apps.accounts.phones import InvalidPhoneError
from apps.accounts.services.members import MemberDetails, create_member
from apps.accounts.services.pins import PinError
from apps.branches.services import create_branch
from apps.core.tenant_context import tenant_context
from apps.tenancy.models import Business
from apps.tenancy.services import BrandingDetails, create_business


def describe(error: ValidationError) -> str:
    if hasattr(error, "message_dict"):
        return "; ".join(f"{k}: {' '.join(v)}" for k, v in error.message_dict.items())
    return " ".join(error.messages)


class Command(BaseCommand):
    help = "Create a business with its address, branding, first branch and owner."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--name", required=True, help='Business name, e.g. "Mama Safi Laundry"')
        parser.add_argument("--slug", required=True, help="Web address name, e.g. mamasafi")
        parser.add_argument(
            "--host", help="Full host; default {slug}.localhost (development addresses)"
        )
        parser.add_argument("--app-name", help="Name shown in the apps; default: --name")
        parser.add_argument("--primary-color", default="#0F6B5C")
        parser.add_argument("--accent-color", default="#F2A900")
        parser.add_argument("--support-phone", default="", help="Shown to staff and customers")
        parser.add_argument("--branch", default="Main branch", help="First branch's name")
        parser.add_argument("--owner-phone", required=True)
        parser.add_argument("--owner-first-name", required=True)
        parser.add_argument("--owner-last-name", required=True)

    def secret(self, env_name: str, prompt: str, *, optional: bool = False) -> str | None:
        value = os.environ.get(env_name)
        if value is not None:
            return value or None
        first = getpass.getpass(prompt)
        if optional and not first:
            return None
        if getpass.getpass("Again: ") != first:
            raise CommandError("The two entries don't match.")
        return first

    def handle(self, *args: Any, **options: Any) -> None:
        slug = options["slug"]
        if Business.objects.filter(slug=slug).exists():
            raise CommandError(f"A business with the address name '{slug}' already exists.")
        password = self.secret("DIAL_OWNER_PASSWORD", "Owner's password: ")
        pin = self.secret(
            "DIAL_OWNER_PIN", "Owner's PIN (4 digits, Enter to skip): ", optional=True
        )
        if not password:
            raise CommandError("The owner needs a password.")

        try:
            # One transaction: a bad owner phone or password leaves no half-made business.
            with transaction.atomic():
                business = create_business(
                    name=options["name"],
                    slug=slug,
                    host=options["host"] or f"{slug}.localhost",
                    branding=BrandingDetails(
                        app_name=options["app_name"] or options["name"],
                        primary_color=options["primary_color"],
                        accent_color=options["accent_color"],
                        support_phone=options["support_phone"],
                    ),
                )
                with tenant_context(business.pk):
                    branch = create_branch(options["branch"])
                    create_member(
                        MemberDetails(
                            phone=options["owner_phone"],
                            first_name=options["owner_first_name"],
                            last_name=options["owner_last_name"],
                            role=Role.OWNER,
                            password=password,
                            branches=[branch],
                            pin=pin,
                        )
                    )
        except ValidationError as exc:
            raise CommandError(describe(exc)) from exc
        except InvalidPhoneError as exc:
            raise CommandError("Enter a Kenyan mobile number, like 0712 345 678.") from exc
        except PinError as exc:
            raise CommandError(f"That PIN can't be used ({exc.code}).") from exc

        self.stdout.write(self.style.SUCCESS(f"Created {business.name} ({slug})."))
