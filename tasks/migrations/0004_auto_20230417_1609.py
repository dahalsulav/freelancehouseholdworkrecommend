# Generated by Django 3.2 on 2023-04-17 10:24

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0003_auto_20230417_1456'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='task',
            name='hourly_rate',
        ),
        migrations.RemoveField(
            model_name='task',
            name='total_cost',
        ),
    ]
