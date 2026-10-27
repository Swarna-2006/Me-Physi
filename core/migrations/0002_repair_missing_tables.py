
from django.db import migrations


def create_missing_tables(apps, schema_editor):
    connection = schema_editor.connection
    existing_tables = set(connection.introspection.table_names())

    for model_name in ("Notification", "DoctorAvailability"):
        model = apps.get_model("core", model_name)
        table_name = model._meta.db_table

        if table_name not in existing_tables:
            schema_editor.create_model(model)
            existing_tables.add(table_name)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            create_missing_tables,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
