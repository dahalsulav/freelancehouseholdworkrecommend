from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from decimal import Decimal
from django.utils import timezone
import uuid

from .models import Task, TaskNotification
from users.models import Worker, Customer

User = get_user_model()


class TaskCreateViewTestCase(TestCase):
    def setUp(self):
        # Create a customer user
        self.customer_user = User.objects.create_user(
            username="customer1", email="customer1@test.com", password="test1234"
        )
        self.customer = Customer.objects.create(user=self.customer_user)

        # Create a worker user
        self.worker_user = User.objects.create_user(
            username="worker1", email="worker1@test.com", password="test1234"
        )
        self.worker = Worker.objects.create(
            user=self.worker_user, hourly_rate=20.0, is_available=True
        )

        # Create a task
        self.task = Task.objects.create(
            title="Test Task",
            customer=self.customer,
            start_time=timezone.now(),
            end_time=timezone.now(),
        )

        # Create a client
        self.client = Client()

    def test_task_create_view_redirects_to_login(self):
        # Send a GET request to the TaskCreateView
        response = self.client.get(reverse("tasks:task_create"))

        # Check that the user is redirected to the login page
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/accounts/login/?next=/tasks/create/")

    def test_task_create_view_create_task(self):
        # Login as the customer user
        self.client.login(username="customer1", password="test1234")

        # Send a POST request to the TaskCreateView
        response = self.client.post(
            reverse("tasks:task_create"),
            {
                "title": "Test Task 2",
                "description": "Test description",
                "start_time": timezone.now(),
                "end_time": timezone.now(),
            },
        )

        # Check that the task is created successfully
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Task.objects.count(), 2)
        self.assertEqual(Task.objects.last().title, "Test Task 2")
