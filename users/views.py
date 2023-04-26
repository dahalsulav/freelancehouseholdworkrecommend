from django.conf import settings
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import LoginView, LogoutView
from django.core.mail import send_mail
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.views import View
from django.views.generic import CreateView, UpdateView, DetailView, ListView
from django.contrib import messages
from .forms import (
    CustomerRegistrationForm,
    WorkerRegistrationForm,
    CustomerUpdateForm,
    WorkerUpdateForm,
)
from .models import User, Customer, Worker, HourlyRateApproval
from .tokens import account_activation_token
from django.http import HttpResponseRedirect
from tasks.models import Task
from django.contrib.auth.decorators import login_required
from tasks.forms import TaskCreateForm
from django.db.models import Avg, Count, Q
from .recommendations import get_worker_recommendations
from tasks.models import TaskNotification


def base_view(request):
    if hasattr(request.user, "customer"):
        # Retrieve the latest task notifications
        task_notifications = TaskNotification.objects.filter(
            customer=request.user.customer
        ).order_by("-created_time")[:5]

        context = {
            "task_notifications": task_notifications,
        }
        return render(request, "users/home.html", context)
    return render(request, "users/home.html")


class CustomerRegistrationView(CreateView):
    model = User
    form_class = CustomerRegistrationForm
    template_name = "users/customer_registration.html"
    success_url = reverse_lazy("users:login")

    def form_valid(self, form):
        response = super().form_valid(form)

        # Send email to the customer with the activation link
        mail_subject = "Activate your account"
        message = render_to_string(
            "users/activation_email.txt",
            {
                "user": self.object,
                "domain": self.request.META["HTTP_HOST"],
                "uid": urlsafe_base64_encode(force_bytes(self.object.pk)),
                "token": account_activation_token.make_token(self.object),
            },
        )
        to_email = form.cleaned_data.get("email")
        send_mail(
            mail_subject,
            message,
            settings.EMAIL_HOST_USER,
            [to_email],
            fail_silently=False,
        )

        # Optionally, send notification email to admin (not implemented)

        messages.success(
            self.request,
            "Please confirm your email address to complete the registration.",
        )
        return response


class CustomerUpdateView(LoginRequiredMixin, UpdateView):
    model = Customer
    form_class = CustomerUpdateForm
    template_name = "users/customer_update.html"
    success_url = reverse_lazy("users:profile")

    def get_object(self):
        return self.request.user.customer

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({"instance": self.get_object()})
        return kwargs


class WorkerRegistrationView(CreateView):
    model = User
    form_class = WorkerRegistrationForm
    template_name = "users/worker_registration.html"
    success_url = reverse_lazy("users:login")

    def form_valid(self, form):
        response = super().form_valid(form)

        # Set approved_by_admin to False by default
        worker = self.object.worker
        worker.approved_by_admin = False
        worker.save()

        # Send email to the worker with the activation link
        mail_subject = "Activate your account"
        message = render_to_string(
            "users/activation_email.txt",
            {
                "user": self.object,
                "domain": self.request.META["HTTP_HOST"],
                "uid": urlsafe_base64_encode(force_bytes(self.object.pk)),
                "token": account_activation_token.make_token(self.object),
            },
        )
        to_email = form.cleaned_data.get("email")
        send_mail(
            mail_subject,
            message,
            settings.EMAIL_HOST_USER,
            [to_email],
            fail_silently=False,
        )

        messages.success(
            self.request,
            "Please confirm your email address to complete the registration.",
        )
        return response


class WorkerUpdateView(LoginRequiredMixin, UpdateView):
    model = Worker
    form_class = WorkerUpdateForm
    template_name = "users/worker_update.html"
    success_url = reverse_lazy("users:profile")

    def get_object(self):
        return self.request.user.worker

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({"instance": self.get_object()})
        return kwargs


class CustomLoginView(LoginView):
    template_name = "users/login.html"

    def get_success_url(self):
        return reverse_lazy("users:home")

    def form_valid(self, form):
        username = self.request.POST["username"]
        password = self.request.POST["password"]
        user = authenticate(self.request, username=username, password=password)

        if user is not None and user.is_active:
            if user.is_customer and not user.customer.email_verified:
                messages.warning(
                    self.request, "Please verify your email address before logging in."
                )
                return self.form_invalid(form)
            elif user.is_worker and not user.worker.email_verified:
                messages.warning(
                    self.request, "Please verify your email address before logging in."
                )
                return self.form_invalid(form)
            elif user.is_worker and not user.worker.approved_by_admin:
                messages.warning(
                    self.request, "Your account is pending approval from the admin."
                )
                return self.form_invalid(form)
            else:
                login(self.request, user)
                messages.success(self.request, "Logged in successfully.")
                return redirect(self.get_success_url())
        else:
            messages.warning(self.request, "Invalid username or password.")
            return self.form_invalid(form)


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy("users:home")


class ActivateAccountView(View):
    def get(self, request, *args, **kwargs):
        uidb64 = kwargs["uidb64"]
        token = kwargs["token"]
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        if user is not None and account_activation_token.check_token(user, token):
            if user.is_customer:
                user.customer.email_verified = True
                user.is_active = True
                user.customer.save()
                user.save()
                messages.success(
                    request, "Your account has been activated successfully."
                )
                return redirect("users:login")
            elif user.is_worker:
                user.worker.email_verified = True
                user.is_active = True
                user.worker.save()
                user.save()
                messages.success(
                    request, "Your account has been activated successfully."
                )
                return redirect("users:login")
        else:
            print("Invalid activation link")
            messages.error(request, "Invalid activation link.")
            return redirect("users:login")


class ActivateWorkerView(View):
    def get(self, request, *args, **kwargs):
        uidb64 = kwargs["uidb64"]
        token = kwargs["token"]
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            worker = Worker.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, Worker.DoesNotExist):
            worker = None

        if worker is not None and default_token_generator.check_token(
            worker.user, token
        ):
            worker.email_verified = True
            worker.user.is_active = True
            worker.save()
            worker.user.save()
            messages.success(request, "Worker account has been activated successfully.")
            return redirect("users:login")
        else:
            messages.error(request, "Invalid activation link.")
            return redirect("users:login")


class ResendActivationLinkView(View):
    def post(self, request, *args, **kwargs):
        email = request.POST.get("email")
        try:
            user = User.objects.get(email=email)
            if not user.is_active:
                if user.is_customer and not user.customer.email_verified:
                    send_activation_email(user, request)
                elif user.is_worker and not user.worker.email_verified:
                    send_activation_email(user, request)
                messages.success(
                    request, "Activation link has been resent to your email."
                )
            else:
                messages.error(request, "Account is already active.")
        except User.DoesNotExist:
            messages.error(request, "No account found with the provided email.")
        return redirect("users:login")


class UserProfileView(LoginRequiredMixin, DetailView):
    template_name = "users/user_profile.html"

    def get_object(self):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        if user.is_customer:
            context["customer"] = user.customer
        elif user.is_worker:
            context["worker"] = user.worker
        return context


class WorkerProfileView(LoginRequiredMixin, DetailView):
    model = Worker
    template_name = "users/worker_profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        worker = get_object_or_404(Worker, pk=self.kwargs["pk"])

        # Calculate the average rating for the worker
        avg_rating = Task.objects.filter(
            worker=worker, status="completed", rating__isnull=False
        ).aggregate(Avg("rating"))["rating__avg"]
        context["avg_rating"] = round(avg_rating, 1) if avg_rating else None

        # Count the number of completed tasks for the worker
        completed_tasks_count = Task.objects.filter(
            worker=worker, status="completed"
        ).count()
        context["completed_tasks_count"] = (
            completed_tasks_count if completed_tasks_count > 0 else None
        )

        return context
