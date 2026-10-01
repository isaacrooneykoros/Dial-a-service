from django.db import migrations

from apps.core.db import EnableTenantRLS


class Migration(migrations.Migration):
    dependencies = [("testapp", "0001_initial")]

    operations = [EnableTenantRLS("widget")]
