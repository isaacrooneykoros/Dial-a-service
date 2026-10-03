"""Development data: two businesses to try the apps with (CLAUDE.md section 7).

    python manage.py seed_dev

Creates Mama Safi Laundry (mamasafi.localhost) and CleanPro Dry Cleaners
(cleanpro.localhost), each with its own brand colours, one branch, and an owner,
a manager and a staff member with passwords and PINs, then prints the logins.
Running it again changes nothing except setting the same passwords and PINs
again, so the printed logins always work.

The accounts are fake and the password is printed on purpose, so this refuses
to run with production settings.
"""

from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Role
from apps.accounts.phones import format_local
from apps.accounts.services.members import MemberDetails, ensure_member
from apps.branches.services import get_or_create_branch
from apps.core.tenant_context import tenant_context
from apps.tenancy.models import Business
from apps.tenancy.services import BrandingDetails, create_business

# Development only: fake people on fake numbers (0700 000 1xx and 0700 000 2xx).
# Not a secret: printed by design for fake local accounts; refused in production.
DEV_PASSWORD = "dial-dev-pass"  # noqa: S105


@dataclass(frozen=True)
class SeedPerson:
    role: Role
    first_name: str
    last_name: str
    phone: str
    pin: str


@dataclass(frozen=True)
class SeedBusiness:
    slug: str
    name: str
    app_name: str
    primary_color: str
    accent_color: str
    support_phone: str
    branch: str
    people: tuple[SeedPerson, ...]


SEED: tuple[SeedBusiness, ...] = (
    SeedBusiness(
        slug="mamasafi",
        name="Mama Safi Laundry",
        app_name="Mama Safi",
        primary_color="#7A1F5C",
        accent_color="#F2A900",
        support_phone="+254700000100",
        branch="Kilimani",
        people=(
            SeedPerson(Role.OWNER, "Wanjiru", "Kamau", "+254700000101", "2468"),
            SeedPerson(Role.MANAGER, "Achieng", "Otieno", "+254700000102", "1357"),
            SeedPerson(Role.STAFF, "Juma", "Mwangi", "+254700000103", "4826"),
        ),
    ),
    SeedBusiness(
        slug="cleanpro",
        name="CleanPro Dry Cleaners",
        app_name="CleanPro",
        primary_color="#1D4ED8",
        accent_color="#10B981",
        support_phone="+254700000200",
        branch="Westlands",
        people=(
            SeedPerson(Role.OWNER, "Kevin", "Odhiambo", "+254700000201", "2468"),
            SeedPerson(Role.MANAGER, "Faith", "Njeri", "+254700000202", "1357"),
            SeedPerson(Role.STAFF, "Brian", "Kiprop", "+254700000203", "4826"),
        ),
    ),
)


def is_production() -> bool:
    return str(settings.SETTINGS_MODULE).endswith(".production")


def seed_business(seed: SeedBusiness) -> Business:
    business = Business.objects.filter(slug=seed.slug).first()
    if business is None:
        business = create_business(
            name=seed.name,
            slug=seed.slug,
            host=f"{seed.slug}.localhost",
            branding=BrandingDetails(
                app_name=seed.app_name,
                primary_color=seed.primary_color,
                accent_color=seed.accent_color,
                support_phone=seed.support_phone,
            ),
        )
    with tenant_context(business.pk):
        branch = get_or_create_branch(seed.branch)
        for person in seed.people:
            ensure_member(
                MemberDetails(
                    phone=person.phone,
                    first_name=person.first_name,
                    last_name=person.last_name,
                    role=person.role,
                    password=DEV_PASSWORD,
                    branches=[branch],
                    pin=person.pin,
                )
            )
    return business


class Command(BaseCommand):
    help = "Create two development businesses with logins (never in production)."

    def handle(self, *args: Any, **options: Any) -> None:
        if is_production():
            raise CommandError("seed_dev creates fake accounts and never runs in production.")
        with transaction.atomic():
            for seed in SEED:
                seed_business(seed)

        port = settings.APP_LINK_PORT
        self.stdout.write(self.style.SUCCESS("Development data is ready.\n"))
        for seed in SEED:
            base = f"{settings.APP_LINK_SCHEME}://{seed.slug}.localhost{port}"
            self.stdout.write(f"{seed.name}  {base}")
            self.stdout.write(f"  Staff app {base}/staff/login   Console {base}/console/login")
            for person in seed.people:
                self.stdout.write(
                    f"  {person.role.label:<9} {person.first_name} {person.last_name:<10} "
                    f"phone {format_local(person.phone)}  PIN {person.pin}"
                )
            self.stdout.write("")
        self.stdout.write(f"Every account's password: {DEV_PASSWORD}")
