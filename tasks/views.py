from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import CreateView, UpdateView, DetailView, ListView
from django.contrib.auth.models import Group
from .models import Task, TaskNotification
from .forms import TaskCreateForm, TaskStatusUpdateForm
from users.models import Worker
from django.utils.decorators import method_decorator
from django.core import serializers
from decimal import Decimal
from django.db.models import Q, Count, Avg
from django.utils import timezone
import uuid


class TaskCreateView(LoginRequiredMixin, CreateView):
    model = Task
    form_class = TaskCreateForm
    template_name = "tasks/task_create.html"
    success_url = reverse_lazy("tasks:task_list")

    def form_valid(self, form):
        # Set the customer for the task
        form.instance.customer = self.request.user.customer

        # Get the start and end times for the task
        start_time = form.cleaned_data.get("start_time")
        end_time = form.cleaned_data.get("end_time")

        # Get the available workers for the given time range
        available_workers = Worker.objects.filter(is_available=True)

        # Check for conflicting tasks with in-progress status
        conflicting_tasks = Task.objects.filter(
            worker__in=available_workers,
            status="in-progress",
            start_time__lt=end_time,
            end_time__gt=start_time,
        ).distinct()

        # Exclude the workers with conflicting tasks
        available_workers = available_workers.exclude(task__in=conflicting_tasks)

        # Get the related workers based on their skills
        query = form.cleaned_data.get("title")
        related_workers = (
            available_workers.filter(skills__icontains=query)
            .annotate(
                rating=Avg("task__rating"),
                tasks_completed=Count("task", filter=Q(task__status="completed")),
            )
            .order_by("-tasks_completed", "-rating")
        )

        # Generate a new request ID
        request_id = str(uuid.uuid4())

        # Send the task request to the related workers
        top_five_workers = []
        related_workers_count = 0
        for worker in related_workers[:5]:
            task = form.save(commit=False)
            task.pk = None  # Create a new task instance
            task.worker = worker
            task.request_id = request_id  # Set the request ID
            print(task.request_id)
            task.save()
            top_five_workers.append(worker.user.username)
            related_workers_count += 1

        # Print the list of related workers who have been sent the task request
        if related_workers_count > 0:
            print(
                f"{related_workers_count} related workers have been sent the task request"
            )
            print(f"{top_five_workers}")
        else:
            print("No related workers found for the task request")

        messages.success(self.request, "Task created successfully!")
        return super().form_valid(form)


def is_worker(user):
    return user.is_authenticated and user.is_worker


class TaskUpdateView(LoginRequiredMixin, UpdateView):
    model = Task
    form_class = TaskStatusUpdateForm
    template_name = "tasks/task_update.html"
    success_url = reverse_lazy("tasks:task_list")

    def form_valid(self, form):
        task = form.save(commit=False)
        if task.status == "in-progress":
            # Assign task to worker
            worker = self.request.user.worker
            task.worker = worker
            task.hourly_rate = worker.hourly_rate
            task.start_time = task.start_time.replace(tzinfo=None)
            task.end_time = task.end_time.replace(tzinfo=None)
            task.total_cost = (
                Decimal((task.end_time - task.start_time).total_seconds() / 3600)
                * task.hourly_rate
            )
            task.save()

            # Update other tasks with same request_id to "vanished"
            Task.objects.filter(request_id=task.request_id).exclude(id=task.id).update(
                status="vanished"
            )

            # Create notification message
            TaskNotification.objects.create(
                task=task,
                message=f"Worker - {task.worker.user.username} has accepted the task:'{task.title}'",
                created_time=timezone.now(),
                customer=task.customer,
            )
        else:
            task.save()
            # Create notification message
            message = None
            if task.status == "completed":
                message = f"Worker - {task.worker.user.username} has completed the task:'{task.title}'"
            elif task.status == "rejected":
                message = f"Worker - {task.worker.user.username} has rejected the task:'{task.title}'"
            if message:
                TaskNotification.objects.create(
                    task=task,
                    message=message,
                    created_time=timezone.now(),
                    customer=task.customer,
                )

        messages.success(self.request, _("Task status updated successfully."))
        return super().form_valid(form)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        task = self.get_object()
        if self.request.GET.get("from_requested") == "true":
            # If called from requested status, show only in-progress and rejected options
            form.fields["status"].choices = [
                ("in-progress", "In Progress"),
                ("rejected", "Rejected"),
            ]
        elif task.status == "in-progress":
            # If called from in-progress status, show only completed option
            form.fields["status"].choices = [("completed", "Completed")]
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        task = self.get_object()
        if task.status == "completed":
            context["show_update_status"] = False
        else:
            context["show_update_status"] = True
        return context


class TaskDetailView(LoginRequiredMixin, DetailView):
    model = Task
    template_name = "tasks/task_detail.html"


class TaskListView(LoginRequiredMixin, ListView):
    model = Task
    template_name = "tasks/task_list.html"
    context_object_name = "tasks"

    def get_queryset(self):
        user = self.request.user
        if user.is_customer:
            tasks = Task.objects.filter(customer=user.customer).order_by(
                "-created_time"
            )
        elif user.is_worker:
            tasks = Task.objects.filter(worker=user.worker).order_by("-created_time")
        else:
            tasks = Task.objects.none()
        return tasks

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        if user.is_customer:
            customer = user.customer
            context["requested_tasks"] = Task.objects.filter(
                customer=customer, status="requested"
            )
            context["rejected_tasks"] = Task.objects.filter(
                customer=customer, status="rejected"
            )
            context["completed_tasks"] = Task.objects.filter(
                customer=customer, status="completed"
            )
            context["in_progress_tasks"] = Task.objects.filter(
                customer=customer, status="in-progress"
            )
        elif user.is_worker:
            worker = user.worker
            context["requested_tasks"] = Task.objects.filter(
                worker=worker, status="requested"
            )
            context["rejected_tasks"] = Task.objects.filter(
                worker=worker, status="rejected"
            )
            context["completed_tasks"] = Task.objects.filter(
                worker=worker, status="completed"
            )
            context["in_progress_tasks"] = Task.objects.filter(
                worker=worker, status="in-progress"
            )
        return context


@login_required
def task_accept(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if task.worker is not None:
        messages.warning(request, _("Task is already assigned to a worker."))
    else:
        task.worker = request.user.worker
        task.status = "in-progress"
        task.save()
        messages.success(request, _("Task accepted successfully."))
    return redirect("users:home")


@login_required
def task_reject(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if task.worker is not None:
        task.worker = None
        task.status = "requested"
        task.save()
        messages.success(request, _("Task rejected successfully."))
    else:
        messages.warning(request, _("Task is not assigned to any worker."))
    return redirect("users:home")


@login_required
def task_complete(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if task.worker is not None and task.worker == request.user.worker:
        task.status = "completed"
        task.save()
        messages.success(request, _("Task completed successfully."))
    else:
        messages.warning(request, _("Task is not assigned to you."))
    return redirect("users:home")


@login_required
def task_rate(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if task.status == "completed" and task.customer.user == request.user:
        if request.method == "POST":
            rating = request.POST.get("rating")
            review = request.POST.get("review")
            task.rating = rating
            task.review = review
            task.save()
            messages.success(request, _("Task rated successfully."))
            return redirect("users:home")
        elif task.rating is not None:
            return render(request, "tasks/task_rating.html", {"task": task})
        else:
            return render(request, "tasks/task_rate.html", {"task": task})
    else:
        messages.warning(request, _("Task is not completed or not assigned to you."))
        return redirect("users:home")
