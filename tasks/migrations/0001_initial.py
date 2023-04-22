# Generated by Django 3.2 on 2023-03-23 18:17

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField()),
                ('start_time', models.DateTimeField()),
                ('end_time', models.DateTimeField()),
                ('location', models.CharField(max_length=255)),
                ('status', models.CharField(choices=[('requested', 'Requested'), ('in-progress', 'In Progress'), ('completed', 'Completed'), ('rejected', 'Rejected')], default='requested', max_length=50)),
                ('created_time', models.DateTimeField(auto_now_add=True)),
                ('updated_time', models.DateTimeField(auto_now=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tasks', to='users.customer')),
                ('worker', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='assigned_tasks', to='users.worker')),
            ],
        ),
        migrations.CreateModel(
            name='TaskRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('requested_time', models.DateTimeField(auto_now_add=True)),
                ('updated_time', models.DateTimeField(auto_now=True)),
                ('status', models.CharField(choices=[('requested', 'Requested'), ('accepted', 'Accepted'), ('rejected', 'Rejected')], default='requested', max_length=50)),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='task_requests', to='tasks.task')),
                ('worker', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='task_requests', to='users.worker')),
            ],
            options={
                'unique_together': {('task', 'worker')},
            },
        ),
    ]