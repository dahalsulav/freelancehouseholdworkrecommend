# Generated by Django 3.2 on 2023-04-23 03:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0007_tasknotification'),
    ]

    operations = [
        migrations.AlterField(
            model_name='task',
            name='status',
            field=models.CharField(choices=[('requested', 'Requested'), ('in-progress', 'In progress'), ('completed', 'Completed'), ('rejected', 'Rejected'), ('vanished', 'Vanished')], default='requested', max_length=20),
        ),
    ]
