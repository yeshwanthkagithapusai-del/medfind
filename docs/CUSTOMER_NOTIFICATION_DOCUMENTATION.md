# Customer Notification Center Documentation

## 1. Overview

The **Notification Center** provides asynchronous, real-time alerts for MediFind users. It keeps patients informed of pharmacy responses, inquiry status changes, and critical account milestones while maintaining strict tenant isolation.

---

## 2. Notification Data Model

Located in `requests_app/models.py`:

```python
class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    message = models.TextField()
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
```

- **`is_read` Indexing**: Indexed (`db_index=True`) for rapid unread badge count queries.
- **Cascade Deletion**: Notifications are purged cleanly if the user account is deleted.

---

## 3. System Notification Triggers

Notifications are generated across the platform by service-layer operations:

| Event | Recipient | Triggering Function | Notification Message Template |
| :--- | :--- | :--- | :--- |
| **Customer Registration** | New Patient | `accounts.services.register_customer` | *"Welcome to MediFind! Search prescription medicines..."* |
| **Pharmacy Registration** | New Owner | `accounts.services.register_pharmacy` | *"Welcome to MediFind Pharmacy Portal! Your store is pending verification..."* |
| **Pharmacy Approval** | Pharmacy Owner | `pharmacies.services.toggle_pharmacy_approval` | *"Your pharmacy '[Name]' has been approved by the MediFind Administrator."* |
| **New Inquiry Received** | Pharmacy Owner | `requests_app.services.create_availability_inquiry` | *"New availability request for '[Medicine]' ([Qty] units) from [Username]."* |
| **Inquiry Responded** | Patient | `requests_app.services.respond_to_availability_inquiry` | *"[Pharmacy] updated your request for '[Medicine]' to: [Status]."* |

---

## 4. Notification Interface & User Capabilities

### 4.1 Global Navbar Counter
Configured in `accounts/context_processors.py`:
```python
def user_notifications_count(request):
    if request.user.is_authenticated:
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return {'unread_notifications_count': count}
    return {'unread_notifications_count': 0}
```
Exposes `{{ unread_notifications_count }}` across all templates, rendering a red pill badge in the header navigation whenever unread alerts exist.

### 4.2 Notifications Center (`/accounts/notifications/`)
- **Filter Tabs**:
  - `All Notifications`: Complete chronologically ordered notification history.
  - `Unread Alerts`: Active notifications requiring patient acknowledgment.
  - `Archived / Read`: Previously acknowledged notifications.
- **Read/Unread Indicators**:
  - Unread notifications render with highlighted backgrounds, prominent bell icons, and *"Unread"* badges.
  - Read notifications render cleanly in muted slate with checkmarks.
- **Mark as Read**: Individual CSRF-protected POST action to `/accounts/notifications/<pk>/read/`.
- **Mark All as Read**: Bulk CSRF-protected POST action to `/accounts/notifications/mark-all-read/`, executing `Notification.objects.filter(user=user, is_read=False).update(is_read=True)` in a single database statement.
- **Pagination**: 10 alerts per page preserving active filter states.

---

## 5. Security & Isolation Verification

1. **Strict Ownership Verification**:
   - `Notification.objects.filter(user=request.user)` ensures no user can list another user's notifications.
2. **Unauthorized Mutation Interception**:
   - Attempting to mark another user's notification as read via `mark_notification_read(pk)` executes `get_object_or_404(Notification, pk=pk, user=request.user)`. Unauthorized IDs immediately return HTTP 404 without altering database state.
3. **CSRF & Method Protection**:
   - All state-changing read actions require HTTP POST with valid CSRF tokens (`@require_POST`). GET requests return HTTP 405 Method Not Allowed.
