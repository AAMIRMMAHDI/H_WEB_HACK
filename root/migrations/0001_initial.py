# Generated by Django 5.2.3 on 2025-07-02 12:43

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Client",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("client_id", models.CharField(max_length=255, unique=True)),
                ("token", models.CharField(max_length=255)),
                ("last_seen", models.DateTimeField(default=django.utils.timezone.now)),
                ("last_command", models.TextField(blank=True, null=True)),
                ("command_id", models.UUIDField(blank=True, null=True)),
                ("last_output", models.TextField(blank=True, null=True)),
            ],
            options={
                "db_table": "root_client",
            },
        ),
    ]
