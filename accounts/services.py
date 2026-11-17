import logging
from typing import Any, Dict, Optional, Tuple
from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from pharmacies.models import Pharmacy
from requests_app.models import Notification

logger = logging.getLogger('medfind')
User = get_user_model()


def register_customer(cleaned_data: Dict[str, Any]) -> User:
    """
    Registers a new customer user account and creates an initial welcome notification.
    """
    username = cleaned_data['username']
    email = cleaned_data['email']
    password = cleaned_data['password']
    phone_number = cleaned_data.get('phone_number', '')
    first_name = cleaned_data.get('first_name', '')
    last_name = cleaned_data.get('last_name', '')

    user = User(
        username=username,
        email=email,
        phone_number=phone_number,
        first_name=first_name,
        last_name=last_name,
        role='CUSTOMER',
    )
    user.set_password(password)
    user.save()

    # Welcome notification
    Notification.objects.create(
        user=user,
        message="Welcome to MediFind! Search medicines across your city and request real-time stock updates."
    )

    logger.info("New customer account registered: username=%s, email=%s", username, email)
    return user


def register_pharmacy(cleaned_data: Dict[str, Any]) -> Pharmacy:
    """
    Atomically registers a pharmacy owner account and their associated pharmacy profile.
    The pharmacy starts with is_approved=False, awaiting administrative vetting.
    """
    with transaction.atomic():
        # 1. Create Pharmacy Owner User
        user = User.objects.create_user(
            username=cleaned_data['username'],
            email=cleaned_data['email'],
            password=cleaned_data['password'],
            role='PHARMACY',
            phone_number=cleaned_data.get('owner_phone', ''),
            first_name=cleaned_data.get('owner_first_name', ''),
            last_name=cleaned_data.get('owner_last_name', '')
        )

        # 2. Create Pharmacy record linked to owner
        pharmacy = Pharmacy.objects.create(
            owner=user,
            pharmacy_name=cleaned_data['pharmacy_name'],
            registration_number=cleaned_data['registration_number'],
            address=cleaned_data['address'],
            city=cleaned_data['city'],
            state=cleaned_data.get('state', ''),
            pincode=cleaned_data['pincode'],
            phone_number=cleaned_data.get('phone_number', ''),
            latitude=cleaned_data.get('latitude') or None,
            longitude=cleaned_data.get('longitude') or None,
            is_approved=False
        )

        # 3. Create initial notification
        Notification.objects.create(
            user=user,
            message=f"Pharmacy registration for '{pharmacy.pharmacy_name}' received! Pending admin verification."
        )

        logger.info(
            "New pharmacy registered: name='%s', reg_no='%s', owner='%s'",
            pharmacy.pharmacy_name,
            pharmacy.registration_number,
            user.username
        )
        return pharmacy


def authenticate_user(request, username: str, password: str) -> Tuple[Optional[User], Optional[str]]:
    """
    Authenticates user credentials safely and returns (user, error_message).
    Logs security audit events without exposing credentials.
    """
    user = authenticate(request, username=username, password=password)
    if user is None:
        logger.warning("Failed login attempt for username: %s", username)
        return None, "Invalid username or password. Please verify your credentials."

    if not user.is_active:
        logger.warning("Login attempted for inactive user: %s", username)
        return None, "This account is inactive. Please contact support."

    logger.info("Successful authentication for user: %s (role=%s)", user.username, user.role)
    return user, None


def mark_notification_as_read(notification_id: int, user: User) -> Notification:
    """
    Marks a single notification as read, enforcing tenant scoping.
    """
    notif = get_object_or_404(Notification, pk=notification_id, user=user)
    notif.is_read = True
    notif.save(update_fields=['is_read'])
    return notif


def mark_all_notifications_as_read(user: User) -> int:
    """
    Marks all unread notifications for a user as read in a single update query.
    """
    return Notification.objects.filter(user=user, is_read=False).update(is_read=True)
